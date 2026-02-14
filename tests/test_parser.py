from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import unittest

from markdownkeeper.processor.parser import parse_markdown


class ParserTests(unittest.TestCase):
    def test_parse_markdown_extracts_frontmatter_headings_and_links(self) -> None:
        doc = """---
title: Sample Doc
author: Test
tags: api,docker
category: guides
concepts: kubernetes,networking
---
# Intro
Paragraph with [internal](./guide.md) and [external](https://example.com).
## Setup
More content.
"""
        parsed = parse_markdown(doc)

        self.assertEqual(parsed.title, "Sample Doc")
        self.assertEqual(parsed.category, "guides")
        self.assertIn("Paragraph", parsed.body)
        self.assertEqual(parsed.tags, ["api", "docker"])
        self.assertEqual(parsed.concepts, ["kubernetes", "networking"])
        self.assertEqual(len(parsed.headings), 2)
        self.assertEqual(parsed.headings[0].anchor, "intro")
        self.assertEqual(len(parsed.links), 2)
        self.assertFalse(parsed.links[0].is_external)
        self.assertTrue(parsed.links[1].is_external)
        self.assertGreater(parsed.token_estimate, 0)
        self.assertEqual(parsed.frontmatter["author"], "Test")

    def test_parse_markdown_title_falls_back_to_first_heading(self) -> None:
        parsed = parse_markdown("# Heading One\nText")
        self.assertEqual(parsed.title, "Heading One")

    def test_parse_markdown_defaults_to_untitled_without_headings(self) -> None:
        parsed = parse_markdown("plain text without headings")
        self.assertEqual(parsed.title, "Untitled")

    def test_parse_markdown_ignores_invalid_frontmatter(self) -> None:
        parsed = parse_markdown("---\nnotkv\n---\n# Title")
        self.assertEqual(parsed.title, "Title")

    def test_parse_markdown_unclosed_frontmatter_treated_as_body(self) -> None:
        parsed = parse_markdown("---\ntitle: broken\n# Heading")
        self.assertEqual(parsed.title, "Heading")

    def test_parse_markdown_auto_extracts_concepts(self) -> None:
        parsed = parse_markdown("# Kubernetes Setup\nKubernetes cluster setup guide")
        self.assertIn("kubernetes", parsed.concepts)


if __name__ == "__main__":
    unittest.main()
