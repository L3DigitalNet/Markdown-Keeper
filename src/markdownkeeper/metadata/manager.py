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
