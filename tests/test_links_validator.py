from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import sqlite3
import tempfile
import unittest
from unittest import mock

from markdownkeeper.links.validator import _check_internal, validate_links
from markdownkeeper.processor.parser import parse_markdown
from markdownkeeper.storage.repository import upsert_document
from markdownkeeper.storage.schema import initialize_database


class LinkValidatorTests(unittest.TestCase):
    def test_validate_links_marks_internal_ok_and_broken(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / ".markdownkeeper" / "index.db"
            docs = tmp_path / "docs"
            docs.mkdir(parents=True, exist_ok=True)
            target = docs / "exists.md"
            target.write_text("# Exists", encoding="utf-8")

            source = docs / "source.md"
            source.write_text("# S\n[good](./exists.md) [bad](./missing.md)", encoding="utf-8")

            initialize_database(db_path)
            upsert_document(db_path, source, parse_markdown(source.read_text(encoding="utf-8")))

            results = validate_links(db_path)
            statuses = {item.target: item.status for item in results}
            self.assertEqual(statuses["./exists.md"], "ok")
            self.assertEqual(statuses["./missing.md"], "broken")

            with sqlite3.connect(db_path) as connection:
                rows = connection.execute("SELECT target, status, checked_at FROM links").fetchall()
            self.assertTrue(all(row[2] for row in rows))

    def test_check_internal_hash_only_anchor_returns_ok(self) -> None:
        result = _check_internal("/some/doc.md", "#section")
        self.assertEqual(result, "ok")

    def test_check_internal_empty_target_returns_ok(self) -> None:
        result = _check_internal("/some/doc.md", "")
        self.assertEqual(result, "ok")

    def test_check_internal_with_anchor_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "doc.md"
            doc.write_text("# Doc", encoding="utf-8")
            target_file = Path(tmp) / "target.md"
            target_file.write_text("# Target", encoding="utf-8")
            result = _check_internal(str(doc), "target.md#section")
            self.assertEqual(result, "ok")

    def test_validate_links_empty_database_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            results = validate_links(db_path)
            self.assertEqual(results, [])


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

    def test_check_external_timeout_returns_broken(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
