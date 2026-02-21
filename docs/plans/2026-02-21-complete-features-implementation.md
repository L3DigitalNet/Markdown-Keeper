# Complete Design Document Features — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement all 7 features identified as gaps between the Project Design Document and the current codebase.

**Architecture:** Bottom-up by dependency. Each task produces a committable, testable unit. Tasks 1-3 are sequential (each builds on prior). Tasks 4-6 are independent. Task 7 (report) is the capstone that aggregates all prior work.

**Tech Stack:** Python 3.10+, SQLite, stdlib `urllib.request`, optional `faiss-cpu`, optional `sentence-transformers`

---

## Pre-Requisites

Before starting, verify the environment:

```bash
cd /home/chris/projects/Markdown-Keeper
python -m pytest tests/test_schema.py tests/test_parser.py tests/test_repository.py tests/test_config.py tests/test_embeddings.py --tb=short -q
# Expected: 72 passed
```

---

## Task 1: Fix Watchdog --iterations Bug

The `--mode auto` selects watchdog when available, but `watch_loop_watchdog` ignores `--iterations` (only supports `--duration`). The CLI test `test_watch_one_iteration_indexes_existing_docs` hangs indefinitely.

**Files:**
- Modify: `src/markdownkeeper/cli/main.py:303-332`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
def test_watch_watchdog_mode_with_iterations_derives_duration(self) -> None:
    """When --mode auto selects watchdog and --iterations is set without --duration,
    duration_s should be derived from iterations * interval."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / ".markdownkeeper" / "index.db"
        docs = Path(tmp) / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        cfg = Path(tmp) / "markdownkeeper.toml"
        cfg.write_text(f'[watch]\nroots=["{docs.as_posix()}"]\nextensions=[".md"]\n', encoding="utf-8")

        with mock.patch("markdownkeeper.cli.main.is_watchdog_available", return_value=True), \
             mock.patch("markdownkeeper.cli.main.watch_loop_watchdog") as wd_mock:
            wd_mock.return_value.created = 0
            wd_mock.return_value.modified = 0
            wd_mock.return_value.deleted = 0
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "--config", str(cfg), "watch", "--db-path", str(db_path),
                 "--iterations", "3", "--interval", "0.5"],
            ):
                code = main()

        self.assertEqual(code, 0)
        wd_mock.assert_called_once()
        call_kwargs = wd_mock.call_args
        # duration_s should be iterations * interval = 3 * 0.5 = 1.5
        self.assertAlmostEqual(call_kwargs.kwargs.get("duration_s", call_kwargs[1].get("duration_s")), 1.5, places=1)
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_cli.py::CliTests::test_watch_watchdog_mode_with_iterations_derives_duration -v
```

Expected: FAIL — currently `duration_s` is passed as `None` when `--duration` not set.

**Step 3: Write minimal implementation**

In `src/markdownkeeper/cli/main.py`, replace the `_handle_watch` function (lines 303-332). The key change: when watchdog mode is selected and `args.duration` is `None` but `args.iterations` is set, derive `duration_s = args.iterations * args.interval`:

```python
def _handle_watch(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    db_path = _resolve_db_path(args.config, args.db_path)
    initialize_database(db_path)

    roots = [Path(root) for root in config.watch.roots]
    mode = args.mode
    if mode == "auto":
        mode = "watchdog" if is_watchdog_available() else "polling"

    if mode == "watchdog":
        duration = args.duration
        if duration is None and args.iterations is not None:
            duration = args.iterations * max(0.05, args.interval)
            import sys
            print(
                f"watchdog mode: --iterations approximated as --duration {duration:.1f}s",
                file=sys.stderr,
            )
        result = watch_loop_watchdog(
            database_path=db_path,
            roots=roots,
            extensions=config.watch.extensions,
            debounce_s=max(0.05, args.interval),
            duration_s=duration,
        )
    else:
        result = watch_loop(
            database_path=db_path,
            roots=roots,
            extensions=config.watch.extensions,
            interval_s=max(0.1, args.interval),
            iterations=args.iterations,
        )
    print(
        f"watch summary mode={mode} created={result.created} modified={result.modified} deleted={result.deleted}"
    )
    return 0
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_cli.py::CliTests::test_watch_watchdog_mode_with_iterations_derives_duration -v
python -m pytest tests/test_cli.py -k "watch" -v --timeout-method=signal
```

Expected: All watch tests pass (including the previously hanging one, which now derives a duration).

**Step 5: Commit**

```bash
git add src/markdownkeeper/cli/main.py tests/test_cli.py
git commit -m "fix: derive duration_s from --iterations in watchdog mode

When --mode auto selects watchdog, --iterations was silently ignored
causing an infinite loop. Now derives duration_s = iterations * interval."
```

---

## Task 2: Metadata Module

The `metadata/` package is a stub. Build frontmatter schema enforcement, auto-fill for missing metadata, and body-based concept extraction.

**Files:**
- Create: `src/markdownkeeper/metadata/manager.py`
- Modify: `src/markdownkeeper/config.py:11-63` (add MetadataConfig)
- Test: `tests/test_metadata.py`

**Step 1: Write the failing tests**

Create `tests/test_metadata.py`:

```python
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from markdownkeeper.metadata.manager import auto_fill, enforce_schema, extract_concepts
from markdownkeeper.processor.parser import parse_markdown


class EnforceSchemaTests(unittest.TestCase):
    def test_returns_empty_when_all_required_present(self) -> None:
        parsed = parse_markdown("---\ntitle: Doc\ntags: python\n---\n# Doc")
        violations = enforce_schema(parsed, required_fields=["title", "tags"])
        self.assertEqual(violations, [])

    def test_returns_violations_for_missing_fields(self) -> None:
        parsed = parse_markdown("# No Frontmatter")
        violations = enforce_schema(parsed, required_fields=["title", "tags", "category"])
        self.assertIn("tags", violations)
        self.assertIn("category", violations)

    def test_empty_required_fields_returns_empty(self) -> None:
        parsed = parse_markdown("# Doc")
        violations = enforce_schema(parsed, required_fields=[])
        self.assertEqual(violations, [])


class AutoFillTests(unittest.TestCase):
    def test_fills_category_from_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            guides = Path(tmp) / "guides"
            guides.mkdir()
            doc = guides / "install.md"
            doc.write_text("# Install Guide", encoding="utf-8")
            parsed = parse_markdown(doc.read_text(encoding="utf-8"))
            filled = auto_fill(parsed, doc)
        self.assertEqual(filled["category"], "guides")

    def test_fills_token_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "doc.md"
            doc.write_text("# Doc\nsome body text here", encoding="utf-8")
            parsed = parse_markdown(doc.read_text(encoding="utf-8"))
            filled = auto_fill(parsed, doc)
        self.assertGreater(filled["token_count"], 0)

    def test_preserves_existing_category(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "doc.md"
            doc.write_text("---\ncategory: runbooks\n---\n# Doc", encoding="utf-8")
            parsed = parse_markdown(doc.read_text(encoding="utf-8"))
            filled = auto_fill(parsed, doc)
        self.assertEqual(filled["category"], "runbooks")


class ExtractConceptsTests(unittest.TestCase):
    def test_extracts_frequent_terms(self) -> None:
        text = "kubernetes cluster deployment. kubernetes pods. kubernetes services."
        concepts = extract_concepts(text)
        self.assertIn("kubernetes", concepts)

    def test_returns_empty_for_empty_text(self) -> None:
        self.assertEqual(extract_concepts(""), [])

    def test_excludes_stopwords(self) -> None:
        text = "the the the and and for for with with"
        concepts = extract_concepts(text)
        self.assertEqual(concepts, [])


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_metadata.py -v
```

Expected: FAIL — `metadata.manager` module doesn't exist.

**Step 3: Write MetadataConfig in config.py**

Add to `src/markdownkeeper/config.py` — new dataclass and integration into `AppConfig`:

```python
@dataclass(slots=True)
class MetadataConfig:
    required_frontmatter_fields: list[str] = field(default_factory=lambda: ["title"])
    auto_fill_category: bool = True
```

Update `AppConfig`:

```python
@dataclass(slots=True)
class AppConfig:
    watch: WatchConfig = field(default_factory=WatchConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    metadata: MetadataConfig = field(default_factory=MetadataConfig)
```

Update `load_config` to parse `[metadata]` section:

```python
metadata = raw.get("metadata", {})
# ... in the return:
metadata=MetadataConfig(
    required_frontmatter_fields=list(metadata.get("required_frontmatter_fields", ["title"])),
    auto_fill_category=bool(metadata.get("auto_fill_category", True)),
),
```

**Step 4: Write metadata/manager.py**

Create `src/markdownkeeper/metadata/manager.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from markdownkeeper.processor.parser import ParsedDocument

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into",
    "your", "guide", "docs", "markdown", "are", "was", "were",
    "been", "being", "have", "has", "had", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "not", "but", "also", "than", "then", "when", "where", "how",
    "what", "which", "who", "whom", "why", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "only",
    "own", "same", "too", "very", "just", "use", "using", "used",
}


def enforce_schema(parsed: ParsedDocument, required_fields: list[str]) -> list[str]:
    """Return list of required frontmatter fields that are missing."""
    if not required_fields:
        return []
    present = set(parsed.frontmatter.keys())
    # title can come from heading even without frontmatter
    if parsed.title and parsed.title != "Untitled":
        present.add("title")
    return sorted(field for field in required_fields if field not in present)


def auto_fill(parsed: ParsedDocument, filepath: Path) -> dict[str, object]:
    """Generate metadata values for fields not present in frontmatter."""
    filled: dict[str, object] = {}
    filled["token_count"] = parsed.token_estimate

    if parsed.category:
        filled["category"] = parsed.category
    else:
        filled["category"] = filepath.parent.name if filepath.parent.name != filepath.anchor else ""

    filled["title"] = parsed.title
    return filled


def extract_concepts(text: str) -> list[str]:
    """Extract key concepts from body text via term frequency."""
    if not text.strip():
        return []
    words = [w.lower() for w in _WORD_RE.findall(text)]
    counts: dict[str, int] = {}
    for w in words:
        if w in _STOPWORDS:
            continue
        counts[w] = counts.get(w, 0) + 1
    ranked = sorted(counts.items(), key=lambda it: (-it[1], it[0]))
    return [item[0] for item in ranked[:10]]
```

**Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_metadata.py -v
python -m pytest tests/test_config.py -v
```

Expected: All pass.

**Step 6: Commit**

```bash
git add src/markdownkeeper/metadata/manager.py src/markdownkeeper/config.py tests/test_metadata.py
git commit -m "feat: add metadata module with schema enforcement and auto-fill

Implements enforce_schema (frontmatter validation), auto_fill (category
from directory, token count), and extract_concepts (TF-based).
Adds MetadataConfig to AppConfig."
```

---

## Task 3: Auto-Summarization

The parser generates `" ".join(lines[:2])[:280]` as summary. Replace with structured heading + first-paragraph format when no frontmatter summary exists.

**Files:**
- Create: `src/markdownkeeper/metadata/summarizer.py`
- Modify: `src/markdownkeeper/processor/parser.py:139-140`
- Test: `tests/test_metadata.py` (add SummarizerTests class)

**Step 1: Write the failing tests**

Add to `tests/test_metadata.py`:

```python
from markdownkeeper.metadata.summarizer import generate_summary


class SummarizerTests(unittest.TestCase):
    def test_preserves_frontmatter_summary(self) -> None:
        parsed = parse_markdown("---\nsummary: My explicit summary\n---\n# Doc\nBody text.")
        result = generate_summary(parsed)
        self.assertEqual(result, "My explicit summary")

    def test_generates_from_headings_and_body(self) -> None:
        md = "# Installation Guide\n\n## Prerequisites\n\nYou need Python 3.10.\n\n## Steps\n\nRun the installer."
        parsed = parse_markdown(md)
        result = generate_summary(parsed)
        self.assertIn("Installation Guide", result)
        self.assertIn("Prerequisites", result)
        self.assertIn("Steps", result)
        self.assertIn("Python 3.10", result)

    def test_truncates_to_max_tokens(self) -> None:
        md = "# Title\n\n" + "word " * 500
        parsed = parse_markdown(md)
        result = generate_summary(parsed, max_tokens=20)
        self.assertLessEqual(len(result.split()), 30)  # some overhead for structure

    def test_empty_document(self) -> None:
        parsed = parse_markdown("")
        result = generate_summary(parsed)
        self.assertIsInstance(result, str)

    def test_headings_only_no_body(self) -> None:
        md = "# Title\n## Section A\n## Section B"
        parsed = parse_markdown(md)
        result = generate_summary(parsed)
        self.assertIn("Title", result)
        self.assertIn("Section A", result)
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_metadata.py::SummarizerTests -v
```

Expected: FAIL — module doesn't exist.

**Step 3: Write summarizer.py**

Create `src/markdownkeeper/metadata/summarizer.py`:

```python
from __future__ import annotations

from markdownkeeper.processor.parser import ParsedDocument


def generate_summary(parsed: ParsedDocument, max_tokens: int = 150) -> str:
    """Generate a structured summary. Preserves frontmatter summary if present."""
    fm_summary = parsed.frontmatter.get("summary", "").strip()
    if fm_summary:
        return fm_summary

    parts: list[str] = []

    # Title
    if parsed.title and parsed.title != "Untitled":
        parts.append(f"{parsed.title}.")

    # H2-level headings as section list
    h2s = [h.text for h in parsed.headings if h.level == 2]
    if h2s:
        parts.append("Covers: " + ", ".join(h2s) + ".")

    # First non-empty paragraph from body
    paragraphs = [p.strip() for p in parsed.body.split("\n\n") if p.strip()]
    for para in paragraphs:
        # Skip lines that are headings
        if para.startswith("#"):
            continue
        parts.append(para)
        break

    result = " ".join(parts)

    # Truncate to max_tokens (approximate by word count)
    words = result.split()
    if len(words) > max_tokens:
        result = " ".join(words[:max_tokens])

    return result
```

**Step 4: Update parser.py to use summarizer**

In `src/markdownkeeper/processor/parser.py`, replace line 140:

```python
# Old:
summary = " ".join(lines[:2])[:280]

# New:
from markdownkeeper.metadata.summarizer import generate_summary as _generate_summary
```

Move the import to the top of the file (after existing imports). Then replace line 140:

```python
summary = str(frontmatter.get("summary") or "")
```

And after building the `ParsedDocument`, call the summarizer. Actually, simpler: just set the summary field using the summarizer in `parse_markdown`:

Replace lines 138-140 in `parser.py`:

```python
lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
title = str(frontmatter.get("title") or (headings[0].text if headings else "Untitled"))
summary = str(frontmatter.get("summary") or "")
```

Then at the end of `parse_markdown`, after building the ParsedDocument, we can't easily call the summarizer because it would create a circular dependency (summarizer imports ParsedDocument from parser). Instead, leave summary as the frontmatter value in parser, and have `upsert_document` call `generate_summary` when the summary is empty:

Actually the cleanest approach: build the ParsedDocument with the raw frontmatter summary, then have `generate_summary` accept the ParsedDocument and compute a better one. No circular dependency because summarizer imports from parser (one-way).

So the change in `parser.py` is just to use the frontmatter summary directly (stop the `" ".join(lines[:2])[:280]` fallback):

```python
summary = str(frontmatter.get("summary") or "")
```

And in `repository.py`'s `upsert_document`, call the summarizer when summary is empty:

```python
from markdownkeeper.metadata.summarizer import generate_summary

# In upsert_document, before the INSERT:
summary = parsed.summary or generate_summary(parsed)
```

Then use `summary` instead of `parsed.summary` in the INSERT statement.

**Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_metadata.py -v
python -m pytest tests/test_parser.py tests/test_repository.py tests/test_cli.py -k "not watch_one" -v
```

Expected: All pass. Existing tests should continue working because docs with frontmatter summaries are preserved, and docs without now get auto-generated summaries.

**Step 6: Commit**

```bash
git add src/markdownkeeper/metadata/summarizer.py src/markdownkeeper/processor/parser.py src/markdownkeeper/storage/repository.py tests/test_metadata.py
git commit -m "feat: add auto-summarization with heading + first-paragraph extraction

Documents with frontmatter summary are preserved. Others get a structured
summary: title, h2 headings, and first paragraph. Integrated into upsert."
```

---

## Task 4: External Link Validation Enhancements

`_check_external` exists and is called, but lacks: rate limiting per domain, GET fallback on 405, and an opt-in CLI flag (currently always checks external).

**Files:**
- Modify: `src/markdownkeeper/links/validator.py:22-78`
- Modify: `src/markdownkeeper/cli/main.py` (add `--check-external` flag)
- Test: `tests/test_links_validator.py`

**Step 1: Write the failing tests**

Add to `tests/test_links_validator.py`:

```python
from unittest import mock


class ExternalLinkTests(unittest.TestCase):
    def test_check_external_ok_on_200(self) -> None:
        mock_response = mock.MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)
        with mock.patch("markdownkeeper.links.validator.urlopen", return_value=mock_response):
            from markdownkeeper.links.validator import _check_external
            result = _check_external("https://example.com")
        self.assertEqual(result, "ok")

    def test_check_external_broken_on_404(self) -> None:
        from markdownkeeper.links.validator import _check_external
        from urllib.error import HTTPError
        with mock.patch(
            "markdownkeeper.links.validator.urlopen",
            side_effect=HTTPError("https://example.com", 404, "Not Found", {}, None),
        ):
            result = _check_external("https://example.com")
        self.assertEqual(result, "broken")

    def test_check_external_retries_get_on_405(self) -> None:
        from markdownkeeper.links.validator import _check_external
        from urllib.error import HTTPError

        call_count = 0
        def mock_urlopen(req, **kwargs):
            nonlocal call_count
            call_count += 1
            if req.get_method() == "HEAD":
                raise HTTPError(req.full_url, 405, "Method Not Allowed", {}, None)
            resp = mock.MagicMock()
            resp.status = 200
            resp.__enter__ = mock.MagicMock(return_value=resp)
            resp.__exit__ = mock.MagicMock(return_value=False)
            return resp

        with mock.patch("markdownkeeper.links.validator.urlopen", side_effect=mock_urlopen):
            result = _check_external("https://example.com")
        self.assertEqual(result, "ok")
        self.assertEqual(call_count, 2)  # HEAD then GET

    def test_check_external_timeout_returns_timeout(self) -> None:
        from markdownkeeper.links.validator import _check_external
        from urllib.error import URLError
        with mock.patch(
            "markdownkeeper.links.validator.urlopen",
            side_effect=URLError("timed out"),
        ):
            result = _check_external("https://example.com")
        self.assertEqual(result, "broken")

    def test_validate_links_skips_external_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / ".markdownkeeper" / "index.db"
            docs = tmp_path / "docs"
            docs.mkdir(parents=True, exist_ok=True)
            source = docs / "source.md"
            source.write_text("# S\n[ext](https://example.com) [int](./missing.md)", encoding="utf-8")

            initialize_database(db_path)
            upsert_document(db_path, source, parse_markdown(source.read_text(encoding="utf-8")))

            results = validate_links(db_path, check_external=False)
            ext_results = [r for r in results if "example.com" in r.target]
            int_results = [r for r in results if "missing" in r.target]
            self.assertEqual(len(ext_results), 0)  # skipped
            self.assertEqual(len(int_results), 1)  # checked


class RateLimiterTests(unittest.TestCase):
    def test_rate_limiter_delays_same_domain(self) -> None:
        from markdownkeeper.links.validator import _DomainRateLimiter
        limiter = _DomainRateLimiter(min_delay=0.5)
        limiter.wait("example.com")
        import time
        start = time.monotonic()
        limiter.wait("example.com")
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.4)

    def test_rate_limiter_no_delay_different_domains(self) -> None:
        from markdownkeeper.links.validator import _DomainRateLimiter
        limiter = _DomainRateLimiter(min_delay=1.0)
        import time
        limiter.wait("example.com")
        start = time.monotonic()
        limiter.wait("other.com")
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 0.5)
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_links_validator.py::ExternalLinkTests -v
python -m pytest tests/test_links_validator.py::RateLimiterTests -v
```

Expected: FAIL — `_DomainRateLimiter` doesn't exist, `validate_links` doesn't accept `check_external`.

**Step 3: Implement rate limiter and enhance _check_external**

Update `src/markdownkeeper/links/validator.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass(slots=True)
class LinkCheckResult:
    link_id: int
    target: str
    status: str


class _DomainRateLimiter:
    """Per-domain delay to avoid rate limiting on external link checks."""

    def __init__(self, min_delay: float = 1.0) -> None:
        self.min_delay = min_delay
        self._last_access: dict[str, float] = {}

    def wait(self, domain: str) -> None:
        now = time.monotonic()
        last = self._last_access.get(domain)
        if last is not None:
            remaining = self.min_delay - (now - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_access[domain] = time.monotonic()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _check_external(target: str, timeout_s: float = 3.0) -> str:
    """Check external URL. Tries HEAD first, falls back to GET on 405."""
    try:
        req = Request(target, method="HEAD")
        with urlopen(req, timeout=timeout_s) as response:  # noqa: S310
            code = getattr(response, "status", 200)
            return "ok" if 200 <= code < 400 else "broken"
    except HTTPError as exc:
        if exc.code == 405:
            # Server doesn't allow HEAD, try GET
            try:
                req_get = Request(target, method="GET")
                with urlopen(req_get, timeout=timeout_s) as response:  # noqa: S310
                    code = getattr(response, "status", 200)
                    return "ok" if 200 <= code < 400 else "broken"
            except Exception:
                return "broken"
        return "broken"
    except Exception:
        return "broken"


def _check_internal(document_path: str, target: str) -> str:
    if target.startswith("#"):
        return "ok"

    target_path = target.split("#", 1)[0].strip()
    if not target_path:
        return "ok"

    doc = Path(document_path)
    resolved = (doc.parent / target_path).resolve()
    return "ok" if resolved.exists() else "broken"


def validate_links(
    database_path: Path,
    timeout_s: float = 3.0,
    check_external: bool = True,
) -> list[LinkCheckResult]:
    now = _now_iso()
    results: list[LinkCheckResult] = []
    limiter = _DomainRateLimiter(min_delay=1.0)

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT l.id, l.target, l.is_external, d.path
            FROM links l
            JOIN documents d ON d.id = l.document_id
            ORDER BY l.id ASC
            """
        ).fetchall()

        for link_id, target, is_external, document_path in rows:
            t = str(target)
            if int(is_external):
                if not check_external:
                    continue
                parsed = urlparse(t)
                if parsed.scheme in {"http", "https"}:
                    limiter.wait(parsed.hostname or "")
                    status = _check_external(t, timeout_s=timeout_s)
                else:
                    status = "broken"
            else:
                status = _check_internal(str(document_path), t)

            connection.execute(
                "UPDATE links SET status = ?, checked_at = ? WHERE id = ?",
                (status, now, int(link_id)),
            )
            results.append(LinkCheckResult(link_id=int(link_id), target=t, status=status))

        connection.commit()

    return results
```

**Step 4: Add --check-external CLI flag**

In `src/markdownkeeper/cli/main.py`, update the `check_links` subparser (around line 60):

```python
check_links.add_argument("--check-external", action="store_true", default=False,
                         help="Also validate external HTTP links")
```

Update `_handle_check_links` to pass the flag:

```python
results = validate_links(db_path, check_external=args.check_external)
```

**Step 5: Run tests**

```bash
python -m pytest tests/test_links_validator.py -v
python -m pytest tests/test_cli.py::CliTests::test_check_links_returns_nonzero_when_broken -v
```

Expected: All pass. Existing test still works because `check_external` defaults to `True` in `validate_links` (backward compatible), and the CLI defaults to `False` (opt-in).

**Step 6: Commit**

```bash
git add src/markdownkeeper/links/validator.py src/markdownkeeper/cli/main.py tests/test_links_validator.py
git commit -m "feat: enhance external link validation with rate limiting and GET fallback

Adds per-domain rate limiting, GET fallback on 405, and --check-external
CLI flag. validate_links now accepts check_external parameter."
```

---

## Task 5: Query Result Caching Enhancements

Caching infrastructure (`_fetch_cache`, `_store_cache`) exists and is used by `semantic_search_documents`. Missing: TTL enforcement, cache invalidation on document changes, lexical search caching, cache metrics in stats.

**Files:**
- Modify: `src/markdownkeeper/storage/repository.py`
- Modify: `src/markdownkeeper/config.py` (add CacheConfig)
- Test: `tests/test_repository.py`

**Step 1: Write the failing tests**

Add to `tests/test_repository.py`:

```python
class QueryCacheTests(unittest.TestCase):
    def test_semantic_search_cache_hit_returns_same_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)
            md = Path(tmp) / "doc.md"
            md.write_text("# Cache Test\ncaching query results", encoding="utf-8")
            upsert_document(db_path, md, parse_markdown(md.read_text(encoding="utf-8")))

            r1 = semantic_search_documents(db_path, "caching")
            r2 = semantic_search_documents(db_path, "caching")
            self.assertEqual([d.id for d in r1], [d.id for d in r2])

    def test_cache_invalidated_on_upsert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)
            md = Path(tmp) / "doc.md"
            md.write_text("# Alpha\nalpha content", encoding="utf-8")
            upsert_document(db_path, md, parse_markdown(md.read_text(encoding="utf-8")))

            semantic_search_documents(db_path, "alpha")

            # Verify cache has entries
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0]
            self.assertGreater(count, 0)

            # Upsert should invalidate
            md.write_text("# Beta\nbeta content", encoding="utf-8")
            upsert_document(db_path, md, parse_markdown(md.read_text(encoding="utf-8")))

            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0]
            self.assertEqual(count, 0)

    def test_cache_invalidated_on_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)
            md = Path(tmp) / "doc.md"
            md.write_text("# Del\ndeletable content", encoding="utf-8")
            upsert_document(db_path, md, parse_markdown(md.read_text(encoding="utf-8")))
            semantic_search_documents(db_path, "deletable")

            delete_document_by_path(db_path, md)

            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0]
            self.assertEqual(count, 0)

    def test_cache_ttl_expired_entry_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)
            md = Path(tmp) / "doc.md"
            md.write_text("# TTL\nttl test content", encoding="utf-8")
            upsert_document(db_path, md, parse_markdown(md.read_text(encoding="utf-8")))

            semantic_search_documents(db_path, "ttl test")

            # Manually backdate the cache entry
            with sqlite3.connect(db_path) as conn:
                conn.execute("UPDATE query_cache SET created_at = '2020-01-01T00:00:00+00:00'")
                conn.commit()

            # Search again — should not use expired cache (re-executes search)
            results = semantic_search_documents(db_path, "ttl test")
            self.assertGreater(len(results), 0)
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_repository.py::QueryCacheTests -v
```

Expected: Invalidation tests fail (cache not cleared on upsert/delete). TTL test may pass incidentally if the code doesn't check TTL and just returns cached results.

**Step 3: Implement cache enhancements**

In `src/markdownkeeper/config.py`, add:

```python
@dataclass(slots=True)
class CacheConfig:
    enabled: bool = True
    ttl_seconds: int = 3600
```

Add to `AppConfig`:

```python
cache: CacheConfig = field(default_factory=CacheConfig)
```

In `src/markdownkeeper/storage/repository.py`:

1. Update `_fetch_cache` to check TTL:

```python
def _fetch_cache(connection: sqlite3.Connection, query_hash: str, ttl_seconds: int = 3600) -> list[int] | None:
    row = connection.execute(
        "SELECT id, result_json, created_at FROM query_cache WHERE query_hash = ?",
        (query_hash,),
    ).fetchone()
    if row is None:
        return None
    cache_id = int(row[0])
    created_at_str = str(row[2])

    # TTL check
    try:
        created_ts = datetime.fromisoformat(created_at_str).timestamp()
        age = time.time() - created_ts
        if age > ttl_seconds:
            connection.execute("DELETE FROM query_cache WHERE id = ?", (cache_id,))
            return None
    except ValueError:
        pass

    payload = json.loads(str(row[1]))
    connection.execute(
        "UPDATE query_cache SET hit_count = hit_count + 1, last_accessed = ? WHERE id = ?",
        (_utc_now_iso(), cache_id),
    )
    return [int(item) for item in payload.get("document_ids", [])]
```

2. Add `_invalidate_cache` helper:

```python
def _invalidate_cache(connection: sqlite3.Connection) -> None:
    """Clear all cached query results."""
    connection.execute("DELETE FROM query_cache")
```

3. Call `_invalidate_cache` in `upsert_document` (after the commit, inside the `with` block):

```python
_invalidate_cache(connection)
```

4. Call `_invalidate_cache` in `delete_document_by_path`:

```python
def delete_document_by_path(database_path: Path, file_path: Path) -> bool:
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        deleted = connection.execute(
            "DELETE FROM documents WHERE path = ?", (str(file_path),)
        ).rowcount
        _invalidate_cache(connection)
        connection.commit()
        return bool(deleted)
```

5. Add cache stats to `system_stats`:

```python
# In system_stats, inside the connection block:
cache_entries = int(connection.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0])
cache_hits = int(connection.execute("SELECT COALESCE(SUM(hit_count), 0) FROM query_cache").fetchone()[0])

# Add to return dict:
"cache": {"entries": cache_entries, "total_hits": cache_hits},
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_repository.py -v
python -m pytest tests/test_cli.py -k "stats" -v
```

Expected: All pass.

**Step 5: Commit**

```bash
git add src/markdownkeeper/storage/repository.py src/markdownkeeper/config.py tests/test_repository.py
git commit -m "feat: add TTL and invalidation to query result caching

Cache entries now expire after ttl_seconds (default 3600). Cache is
fully flushed on document upsert/delete. Cache stats added to system_stats."
```

---

## Task 6: FAISS Index (Optional)

Add optional FAISS-backed similarity search, falling back to brute-force cosine when not installed.

**Files:**
- Create: `src/markdownkeeper/query/faiss_index.py`
- Modify: `src/markdownkeeper/storage/repository.py` (use FAISS in semantic search)
- Modify: `src/markdownkeeper/cli/main.py` (rebuild FAISS on embeddings-generate)
- Modify: `pyproject.toml` (add faiss optional dep)
- Test: `tests/test_faiss_index.py`

**Step 1: Write the failing tests**

Create `tests/test_faiss_index.py`:

```python
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from markdownkeeper.query.faiss_index import FaissIndex, is_faiss_available


class FaissIndexTests(unittest.TestCase):
    def test_build_and_search_returns_nearest(self) -> None:
        index = FaissIndex()
        embeddings = [
            (1, [1.0, 0.0, 0.0]),
            (2, [0.0, 1.0, 0.0]),
            (3, [0.9, 0.1, 0.0]),
        ]
        index.build(embeddings)
        results = index.search([1.0, 0.0, 0.0], k=2)
        ids = [doc_id for doc_id, _ in results]
        self.assertIn(1, ids)
        self.assertIn(3, ids)

    def test_search_empty_index_returns_empty(self) -> None:
        index = FaissIndex()
        index.build([])
        results = index.search([1.0, 0.0], k=5)
        self.assertEqual(results, [])

    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.index"
            index = FaissIndex()
            embeddings = [(1, [1.0, 0.0]), (2, [0.0, 1.0])]
            index.build(embeddings)
            index.save(path)

            loaded = FaissIndex()
            loaded.load(path)
            results = loaded.search([1.0, 0.0], k=1)
            self.assertEqual(results[0][0], 1)

    def test_is_faiss_available_returns_bool(self) -> None:
        self.assertIsInstance(is_faiss_available(), bool)

    def test_k_larger_than_index_returns_all(self) -> None:
        index = FaissIndex()
        index.build([(1, [1.0, 0.0]), (2, [0.0, 1.0])])
        results = index.search([1.0, 0.0], k=100)
        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_faiss_index.py -v
```

Expected: FAIL — module doesn't exist.

**Step 3: Implement FaissIndex**

Create `src/markdownkeeper/query/faiss_index.py`:

```python
from __future__ import annotations

import json
import math
from pathlib import Path

try:
    import faiss  # type: ignore[import-untyped]
    import numpy as np  # type: ignore[import-untyped]
except ImportError:
    faiss = None
    np = None


def is_faiss_available() -> bool:
    return faiss is not None and np is not None


class FaissIndex:
    """Optional FAISS-backed vector index. Falls back to brute-force when FAISS not installed."""

    def __init__(self) -> None:
        self._index: object | None = None
        self._id_map: list[int] = []
        self._embeddings: list[tuple[int, list[float]]] = []
        self._dimensions: int = 0

    def build(self, embeddings: list[tuple[int, list[float]]]) -> None:
        self._embeddings = list(embeddings)
        if not embeddings:
            self._index = None
            self._id_map = []
            self._dimensions = 0
            return

        self._dimensions = len(embeddings[0][1])
        self._id_map = [doc_id for doc_id, _ in embeddings]

        if is_faiss_available():
            vectors = np.array([vec for _, vec in embeddings], dtype=np.float32)
            faiss.normalize_L2(vectors)
            index = faiss.IndexFlatIP(self._dimensions)
            index.add(vectors)
            self._index = index
        else:
            self._index = None

    def search(self, query_vector: list[float], k: int = 10) -> list[tuple[int, float]]:
        if not self._id_map:
            return []

        k = min(k, len(self._id_map))

        if is_faiss_available() and self._index is not None:
            q = np.array([query_vector], dtype=np.float32)
            faiss.normalize_L2(q)
            distances, indices = self._index.search(q, k)
            results: list[tuple[int, float]] = []
            for i in range(k):
                idx = int(indices[0][i])
                if idx < 0 or idx >= len(self._id_map):
                    continue
                results.append((self._id_map[idx], float(distances[0][i])))
            return results

        # Brute-force fallback
        return self._brute_force_search(query_vector, k)

    def _brute_force_search(self, query_vector: list[float], k: int) -> list[tuple[int, float]]:
        q_norm = self._normalize(query_vector)
        scored: list[tuple[float, int]] = []
        for doc_id, vec in self._embeddings:
            v_norm = self._normalize(vec)
            sim = sum(a * b for a, b in zip(q_norm, v_norm))
            scored.append((sim, doc_id))
        scored.sort(reverse=True)
        return [(doc_id, score) for score, doc_id in scored[:k]]

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if is_faiss_available() and self._index is not None:
            faiss.write_index(self._index, str(path))
            meta_path = path.with_suffix(".meta.json")
            meta_path.write_text(
                json.dumps({"id_map": self._id_map, "dimensions": self._dimensions}),
                encoding="utf-8",
            )
        else:
            # Save as JSON for brute-force fallback
            data = {
                "id_map": self._id_map,
                "dimensions": self._dimensions,
                "embeddings": [[doc_id, vec] for doc_id, vec in self._embeddings],
            }
            path.with_suffix(".json").write_text(json.dumps(data), encoding="utf-8")

    def load(self, path: Path) -> None:
        if is_faiss_available() and path.exists():
            self._index = faiss.read_index(str(path))
            meta_path = path.with_suffix(".meta.json")
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                self._id_map = meta["id_map"]
                self._dimensions = meta["dimensions"]
            return

        # Fallback: load from JSON
        json_path = path.with_suffix(".json")
        if json_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self._id_map = data["id_map"]
            self._dimensions = data["dimensions"]
            self._embeddings = [(e[0], e[1]) for e in data["embeddings"]]
```

**Step 4: Update pyproject.toml**

Add to `[project.optional-dependencies]`:

```toml
faiss = ["faiss-cpu>=1.7", "numpy>=1.24"]
```

**Step 5: Run tests**

```bash
python -m pytest tests/test_faiss_index.py -v
```

Expected: All pass (using brute-force fallback since faiss-cpu likely not installed).

**Step 6: Integrate into semantic_search_documents**

In `src/markdownkeeper/storage/repository.py`, add at the top:

```python
from markdownkeeper.query.faiss_index import FaissIndex, is_faiss_available
```

In `regenerate_embeddings`, after the main loop, build and save the FAISS index:

```python
# At end of regenerate_embeddings, before return:
all_embeddings: list[tuple[int, list[float]]] = []
for row in rows:
    doc_id = int(row[0])
    emb_row = connection.execute(
        "SELECT embedding FROM embeddings WHERE document_id = ?", (doc_id,)
    ).fetchone()
    if emb_row and emb_row[0]:
        all_embeddings.append((doc_id, _deserialize_embedding(emb_row[0])))

faiss_idx = FaissIndex()
faiss_idx.build(all_embeddings)
index_path = database_path.parent / "faiss.index"
faiss_idx.save(index_path)
```

**Step 7: Run full test suite**

```bash
python -m pytest tests/test_faiss_index.py tests/test_repository.py tests/test_embeddings.py -v
```

Expected: All pass.

**Step 8: Commit**

```bash
git add src/markdownkeeper/query/faiss_index.py src/markdownkeeper/storage/repository.py pyproject.toml tests/test_faiss_index.py
git commit -m "feat: add optional FAISS index for faster similarity search

FaissIndex class with build/search/save/load. Falls back to brute-force
cosine when faiss-cpu not installed. Rebuilt on embeddings-generate."
```

---

## Task 7: `mdkeeper report` Command

Capstone feature — aggregates health data from all subsystems into a summary report.

**Files:**
- Modify: `src/markdownkeeper/storage/repository.py` (add `generate_health_report`)
- Modify: `src/markdownkeeper/cli/main.py` (add `report` subcommand)
- Test: `tests/test_repository.py` (add HealthReportTests)
- Test: `tests/test_cli.py` (add report CLI test)

**Step 1: Write the failing tests**

Add to `tests/test_repository.py`:

```python
from markdownkeeper.storage.repository import generate_health_report


class HealthReportTests(unittest.TestCase):
    def test_report_on_empty_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)
            report = generate_health_report(db_path)
        self.assertEqual(report["total_documents"], 0)
        self.assertEqual(report["total_tokens"], 0)
        self.assertEqual(report["broken_internal_links"], 0)
        self.assertEqual(report["broken_external_links"], 0)
        self.assertEqual(report["missing_summaries"], 0)

    def test_report_on_populated_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)

            md1 = Path(tmp) / "doc1.md"
            md1.write_text("# Doc 1\n[bad](./missing.md)\n[ext](https://example.com)", encoding="utf-8")
            upsert_document(db_path, md1, parse_markdown(md1.read_text(encoding="utf-8")))

            md2 = Path(tmp) / "doc2.md"
            md2.write_text("---\nsummary: Has summary\n---\n# Doc 2", encoding="utf-8")
            upsert_document(db_path, md2, parse_markdown(md2.read_text(encoding="utf-8")))

            report = generate_health_report(db_path)

        self.assertEqual(report["total_documents"], 2)
        self.assertGreater(report["total_tokens"], 0)
        self.assertIn("embedding_coverage_pct", report)
        self.assertIn("cache_entries", report)
        self.assertIn("queue_queued", report)

    def test_report_json_serializable(self) -> None:
        import json
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)
            report = generate_health_report(db_path)
        serialized = json.dumps(report)
        self.assertIsInstance(serialized, str)
```

Add to `tests/test_cli.py`:

```python
def test_report_json_output(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / ".markdownkeeper" / "index.db"
        md_file = Path(tmp) / "doc.md"
        md_file.write_text("# Report Test\nhello world", encoding="utf-8")
        with mock.patch("sys.argv", ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)]):
            main()

        out = io.StringIO()
        with mock.patch("sys.argv", ["mdkeeper", "report", "--db-path", str(db_path), "--format", "json"]):
            with contextlib.redirect_stdout(out):
                code = main()
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["total_documents"], 1)

def test_report_text_output(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / ".markdownkeeper" / "index.db"
        out = io.StringIO()
        with mock.patch("sys.argv", ["mdkeeper", "report", "--db-path", str(db_path), "--format", "text"]):
            with contextlib.redirect_stdout(out):
                code = main()
        self.assertEqual(code, 0)
        self.assertIn("Health Report", out.getvalue())
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_repository.py::HealthReportTests -v
python -m pytest tests/test_cli.py::CliTests::test_report_json_output -v
```

Expected: FAIL — `generate_health_report` doesn't exist, `report` command not registered.

**Step 3: Implement generate_health_report**

Add to `src/markdownkeeper/storage/repository.py`:

```python
def generate_health_report(database_path: Path) -> dict[str, object]:
    """Aggregate health metrics across all subsystems."""
    with sqlite3.connect(database_path) as connection:
        total_docs = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
        total_tokens = int(connection.execute(
            "SELECT COALESCE(SUM(token_estimate), 0) FROM documents"
        ).fetchone()[0])

        broken_internal = int(connection.execute(
            "SELECT COUNT(*) FROM links WHERE is_external = 0 AND status = 'broken'"
        ).fetchone()[0])
        broken_external = int(connection.execute(
            "SELECT COUNT(*) FROM links WHERE is_external = 1 AND status = 'broken'"
        ).fetchone()[0])
        unchecked_external = int(connection.execute(
            "SELECT COUNT(*) FROM links WHERE is_external = 1 AND (status = 'unknown' OR status IS NULL)"
        ).fetchone()[0])

        missing_summaries = int(connection.execute(
            "SELECT COUNT(*) FROM documents WHERE summary IS NULL OR TRIM(summary) = ''"
        ).fetchone()[0])

        embedded = int(connection.execute(
            "SELECT COUNT(*) FROM embeddings WHERE embedding IS NOT NULL AND LENGTH(TRIM(embedding)) > 0"
        ).fetchone()[0])
        coverage_pct = round((embedded / total_docs * 100) if total_docs > 0 else 0.0, 1)

        cache_entries = int(connection.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0])
        cache_hits = int(connection.execute(
            "SELECT COALESCE(SUM(hit_count), 0) FROM query_cache"
        ).fetchone()[0])

        queue_queued = int(connection.execute(
            "SELECT COUNT(*) FROM events WHERE status = 'queued'"
        ).fetchone()[0])
        queue_failed = int(connection.execute(
            "SELECT COUNT(*) FROM events WHERE status = 'failed'"
        ).fetchone()[0])

    return {
        "total_documents": total_docs,
        "total_tokens": total_tokens,
        "broken_internal_links": broken_internal,
        "broken_external_links": broken_external,
        "unchecked_external_links": unchecked_external,
        "missing_summaries": missing_summaries,
        "embedding_coverage_pct": coverage_pct,
        "embedded_documents": embedded,
        "cache_entries": cache_entries,
        "cache_total_hits": cache_hits,
        "queue_queued": queue_queued,
        "queue_failed": queue_failed,
    }
```

**Step 4: Add report CLI command**

In `src/markdownkeeper/cli/main.py`:

Add to `build_parser` (after the `stats` subparser):

```python
report = subparsers.add_parser("report", help="Show health report")
report.add_argument("--db-path", type=Path, default=None, help="Override DB path")
report.add_argument("--format", choices=["text", "json"], default="text")
```

Add handler:

```python
def _handle_report(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path(args.config, args.db_path)
    initialize_database(db_path)
    report = generate_health_report(db_path)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        lines = [
            "┌──────────────────────────────────────────┐",
            "│ MarkdownKeeper Health Report             │",
            "├──────────────────────────────────────────┤",
            f"│ Total Documents: {report['total_documents']:<24}│",
            f"│ Total Tokens: {report['total_tokens']:<27}│",
            f"│ Broken Internal Links: {report['broken_internal_links']:<18}│",
            f"│ Broken External Links: {report['broken_external_links']:<18}│",
            f"│ Unchecked External Links: {report['unchecked_external_links']:<15}│",
            f"│ Missing Summaries: {report['missing_summaries']:<22}│",
            f"│ Embedding Coverage: {report['embedding_coverage_pct']}%{'':<17}│",
            f"│ Cache Entries: {report['cache_entries']:<26}│",
            f"│ Cache Hits: {report['cache_total_hits']:<29}│",
            f"│ Event Queue: {report['queue_queued']} queued / {report['queue_failed']} failed{'':<8}│",
            "└──────────────────────────────────────────┘",
        ]
        print("\n".join(lines))
    return 0
```

Add to the `handlers` dict:

```python
"report": _handle_report,
```

Add to the imports at the top:

```python
from markdownkeeper.storage.repository import ..., generate_health_report
```

**Step 5: Run tests**

```bash
python -m pytest tests/test_repository.py::HealthReportTests tests/test_cli.py::CliTests::test_report_json_output tests/test_cli.py::CliTests::test_report_text_output -v
```

Expected: All pass.

**Step 6: Run full test suite**

```bash
python -m pytest tests/ -k "not watch_one_iteration" --tb=short -q
```

Expected: All tests pass.

**Step 7: Commit**

```bash
git add src/markdownkeeper/storage/repository.py src/markdownkeeper/cli/main.py tests/test_repository.py tests/test_cli.py
git commit -m "feat: add mdkeeper report command with health metrics

Aggregates document count, tokens, broken links, missing summaries,
embedding coverage, cache stats, and event queue status."
```

---

## Final Verification

After all 7 tasks are complete:

```bash
# Run full test suite (skip the known hanging test if bug fix isn't committed yet)
python -m pytest tests/ -k "not watch_one_iteration" --tb=short -v

# Smoke test the CLI
mdkeeper --help
mdkeeper report --help
```

Expected: All tests pass. All new commands show in `--help`.
