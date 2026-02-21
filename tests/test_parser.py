from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import unittest

from markdownkeeper.processor.parser import _slugify, _split_list, _extract_concepts, ParsedHeading, parse_markdown


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

    def test_parse_markdown_frontmatter_at_eof_without_trailing_newline(self) -> None:
        parsed = parse_markdown("---\ntitle: EOF Test\ntags: alpha\n---")
        self.assertEqual(parsed.title, "EOF Test")
        self.assertEqual(parsed.tags, ["alpha"])

    def test_parse_markdown_empty_body(self) -> None:
        parsed = parse_markdown("")
        self.assertEqual(parsed.title, "Untitled")
        self.assertEqual(parsed.headings, [])
        self.assertEqual(parsed.links, [])
        self.assertEqual(parsed.token_estimate, 1)

    def test_parse_markdown_content_hash_is_deterministic(self) -> None:
        text = "# Title\nbody content"
        p1 = parse_markdown(text)
        p2 = parse_markdown(text)
        self.assertEqual(p1.content_hash, p2.content_hash)

    def test_parse_markdown_content_hash_changes_with_content(self) -> None:
        p1 = parse_markdown("# A")
        p2 = parse_markdown("# B")
        self.assertNotEqual(p1.content_hash, p2.content_hash)

    def test_parse_markdown_extracts_multiple_heading_levels(self) -> None:
        parsed = parse_markdown("# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6")
        self.assertEqual(len(parsed.headings), 6)
        for i, heading in enumerate(parsed.headings):
            self.assertEqual(heading.level, i + 1)

    def test_parse_markdown_http_and_https_both_external(self) -> None:
        parsed = parse_markdown("[a](http://a.com) [b](https://b.com) [c](./local.md)")
        externals = [link for link in parsed.links if link.is_external]
        internals = [link for link in parsed.links if not link.is_external]
        self.assertEqual(len(externals), 2)
        self.assertEqual(len(internals), 1)

    def test_parse_markdown_summary_empty_without_frontmatter(self) -> None:
        long_line = "word " * 200
        parsed = parse_markdown(f"# Title\n{long_line}")
        self.assertEqual(parsed.summary, "")

    def test_slugify_handles_special_characters(self) -> None:
        self.assertEqual(_slugify("Hello World!"), "hello-world")
        self.assertEqual(_slugify("API v2.0 Guide"), "api-v20-guide")
        self.assertEqual(_slugify("   spaces   "), "spaces")

    def test_split_list_empty_and_whitespace(self) -> None:
        self.assertEqual(_split_list(None), [])
        self.assertEqual(_split_list(""), [])
        self.assertEqual(_split_list("  ,  ,  "), [])

    def test_split_list_normal_values(self) -> None:
        self.assertEqual(_split_list("a, b, c"), ["a", "b", "c"])

    def test_extract_concepts_prefers_heading_words(self) -> None:
        headings = [ParsedHeading(level=1, text="Kubernetes", anchor="kubernetes", position=1)]
        concepts = _extract_concepts("some random body text", headings)
        self.assertIn("kubernetes", concepts)

    def test_extract_concepts_filters_stopwords(self) -> None:
        headings: list[ParsedHeading] = []
        concepts = _extract_concepts("the and for with this that from into your guide docs markdown", headings)
        for stopword in ["the", "and", "for", "with"]:
            self.assertNotIn(stopword, concepts)

    def test_parse_markdown_category_none_when_missing(self) -> None:
        parsed = parse_markdown("# No Category\nbody")
        self.assertIsNone(parsed.category)

    def test_parse_markdown_frontmatter_strips_quotes_from_values(self) -> None:
        parsed = parse_markdown('---\ntitle: "Quoted Title"\n---\n# Body')
        self.assertEqual(parsed.title, "Quoted Title")


if __name__ == "__main__":
    unittest.main()
