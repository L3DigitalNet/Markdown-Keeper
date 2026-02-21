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
from markdownkeeper.metadata.summarizer import generate_summary
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


if __name__ == "__main__":
    unittest.main()
