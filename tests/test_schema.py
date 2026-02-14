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
                "idx_events_status_created",
            }.issubset(indexes)
        )


    def test_initialize_database_migrates_event_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        path TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT DEFAULT 'queued'
                    )
                    """
                )
                connection.commit()

            initialize_database(db_path)

            with sqlite3.connect(db_path) as connection:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(events)").fetchall()
                }

        self.assertTrue({"updated_at", "attempts", "last_error"}.issubset(columns))


    def test_initialize_database_migrates_chunk_embedding_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE document_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id INTEGER NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        heading_path TEXT,
                        content TEXT NOT NULL,
                        token_count INTEGER NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        path TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT DEFAULT 'queued'
                    )
                    """
                )
                connection.commit()

            initialize_database(db_path)

            with sqlite3.connect(db_path) as connection:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(document_chunks)").fetchall()
                }

        self.assertIn("embedding", columns)


if __name__ == "__main__":
    unittest.main()
