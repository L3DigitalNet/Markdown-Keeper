from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL UNIQUE,
        title TEXT,
        summary TEXT,
        category TEXT,
        content TEXT,
        content_hash TEXT,
        token_estimate INTEGER DEFAULT 0,
        updated_at TEXT NOT NULL,
        processed_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS headings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        level INTEGER NOT NULL,
        heading_text TEXT NOT NULL,
        anchor TEXT,
        position INTEGER NOT NULL,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        source_anchor TEXT,
        target TEXT NOT NULL,
        is_external INTEGER NOT NULL,
        status TEXT DEFAULT 'unknown',
        checked_at TEXT,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS document_tags (
        document_id INTEGER NOT NULL,
        tag_id INTEGER NOT NULL,
        PRIMARY KEY(document_id, tag_id),
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
        FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS concepts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS document_concepts (
        document_id INTEGER NOT NULL,
        concept_id INTEGER NOT NULL,
        score REAL DEFAULT 1.0,
        PRIMARY KEY(document_id, concept_id),
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
        FOREIGN KEY(concept_id) REFERENCES concepts(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS document_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL,
        heading_path TEXT,
        content TEXT NOT NULL,
        token_count INTEGER NOT NULL,
        embedding TEXT,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS embeddings (
        document_id INTEGER PRIMARY KEY,
        embedding TEXT,
        model_name TEXT,
        generated_at TEXT,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS query_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_hash TEXT NOT NULL UNIQUE,
        query_text TEXT NOT NULL,
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        hit_count INTEGER DEFAULT 0,
        last_accessed TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        status TEXT DEFAULT 'queued',
        attempts INTEGER DEFAULT 0,
        last_error TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_headings_document_id ON headings(document_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_links_document_id ON links(document_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_query_cache_hash ON query_cache(query_hash)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_events_status_created ON events(status, created_at)
    """,
]


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)

        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(documents)").fetchall()
        }
        if "category" not in columns:
            connection.execute("ALTER TABLE documents ADD COLUMN category TEXT")
        if "content" not in columns:
            connection.execute("ALTER TABLE documents ADD COLUMN content TEXT")

        chunk_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(document_chunks)").fetchall()
        }
        if "embedding" not in chunk_columns:
            connection.execute("ALTER TABLE document_chunks ADD COLUMN embedding TEXT")

        event_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(events)").fetchall()
        }
        if "updated_at" not in event_columns:
            connection.execute("ALTER TABLE events ADD COLUMN updated_at TEXT")
        if "attempts" not in event_columns:
            connection.execute("ALTER TABLE events ADD COLUMN attempts INTEGER DEFAULT 0")
        if "last_error" not in event_columns:
            connection.execute("ALTER TABLE events ADD COLUMN last_error TEXT")

        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_status_created ON events(status, created_at)"
        )

        connection.commit()
