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

from markdownkeeper.storage.schema import initialize_database


class SchemaTests(unittest.TestCase):
    def test_initialize_database_creates_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)

            with sqlite3.connect(db_path) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }

        self.assertTrue(
            {
                "documents",
                "headings",
                "links",
                "events",
                "tags",
                "document_tags",
                "concepts",
                "document_concepts",
                "document_chunks",
                "embeddings",
                "query_cache",
            }.issubset(tables)
        )
        self.assertTrue({"documents", "headings", "links", "events"}.issubset(tables))

    def test_initialize_database_creates_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)

            with sqlite3.connect(db_path) as connection:
                indexes = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='index'"
                    )
                }

        self.assertTrue(
            {
                "idx_documents_path",
                "idx_documents_category",
                "idx_headings_document_id",
                "idx_links_document_id",
                "idx_chunks_document_id",
                "idx_query_cache_hash",
                "idx_headings_document_id",
                "idx_links_document_id",
            }.issubset(indexes)
        )


if __name__ == "__main__":
    unittest.main()
