from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import tempfile
import unittest

from markdownkeeper.indexer.generator import generate_master_index
from markdownkeeper.processor.parser import parse_markdown
from markdownkeeper.storage.repository import upsert_document
from markdownkeeper.storage.schema import initialize_database


class IndexerTests(unittest.TestCase):
    def test_generate_master_index_writes_document_listing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / ".markdownkeeper" / "index.db"
            initialize_database(db)
            doc = root / "docs" / "a.md"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text("# Alpha\nbody", encoding="utf-8")
            upsert_document(db, doc, parse_markdown(doc.read_text(encoding="utf-8")))

            out = generate_master_index(db, root / "_index")
            content = out.read_text(encoding="utf-8")
            self.assertIn("MarkdownKeeper Master Index", content)
            self.assertIn("Alpha", content)


if __name__ == "__main__":
    unittest.main()
