from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any


@dataclass(slots=True)
class ParsedHeading:
    level: int
    text: str
    anchor: str
    position: int


@dataclass(slots=True)
class ParsedLink:
    target: str
    is_external: bool


@dataclass(slots=True)
class ParsedDocument:
    title: str
    summary: str
    token_estimate: int
    content_hash: str
    headings: list[ParsedHeading]
    links: list[ParsedLink]
    frontmatter: dict[str, Any]


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9\s-]", "", value.lower())
    return re.sub(r"\s+", "-", slug).strip("-")


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text

    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text

    raw_fm = text[4:end]
    body = text[end + 5 :]
    frontmatter: dict[str, Any] = {}
    for line in raw_fm.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip('"')
    return frontmatter, body


def parse_markdown(text: str) -> ParsedDocument:
    frontmatter, body = _parse_frontmatter(text)

    headings: list[ParsedHeading] = []
    for idx, match in enumerate(_HEADING_RE.finditer(body), start=1):
        heading_text = match.group(2).strip()
        headings.append(
            ParsedHeading(
                level=len(match.group(1)),
                text=heading_text,
                anchor=_slugify(heading_text),
                position=idx,
            )
        )

    links: list[ParsedLink] = []
    for match in _LINK_RE.finditer(body):
        target = match.group(1).strip()
        links.append(
            ParsedLink(
                target=target,
                is_external=target.startswith("http://") or target.startswith("https://"),
            )
        )

    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    title = str(frontmatter.get("title") or (headings[0].text if headings else "Untitled"))
    summary = " ".join(lines[:2])[:280]
    token_estimate = max(1, len(body.split()))
    content_hash = sha256(text.encode("utf-8")).hexdigest()

    return ParsedDocument(
        title=title,
        summary=summary,
        token_estimate=token_estimate,
        content_hash=content_hash,
        headings=headings,
        links=links,
        frontmatter=frontmatter,
    )
