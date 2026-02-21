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
