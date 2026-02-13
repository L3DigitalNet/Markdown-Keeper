from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from markdownkeeper.processor.parser import ParsedDocument


@dataclass(slots=True)
class DocumentRecord:
    id: int
    path: str
    title: str
    summary: str
    token_estimate: int
    updated_at: str


@dataclass(slots=True)
class DocumentDetail(DocumentRecord):
    headings: list[dict[str, object]]
    links: list[dict[str, object]]


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def upsert_document(database_path: Path, file_path: Path, parsed: ParsedDocument) -> int:
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        now = _utc_now_iso()
        connection.execute(
            """
            INSERT INTO documents(path, title, summary, content_hash, token_estimate, updated_at, processed_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
              title=excluded.title,
              summary=excluded.summary,
              content_hash=excluded.content_hash,
              token_estimate=excluded.token_estimate,
              updated_at=excluded.updated_at,
              processed_at=excluded.processed_at
            """,
            (
                str(file_path),
                parsed.title,
                parsed.summary,
                parsed.content_hash,
                parsed.token_estimate,
                now,
                now,
            ),
        )

        row = connection.execute(
            "SELECT id FROM documents WHERE path = ?", (str(file_path),)
        ).fetchone()
        if row is None:
            raise RuntimeError("Document upsert failed unexpectedly")
        document_id = int(row[0])

        connection.execute("DELETE FROM headings WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM links WHERE document_id = ?", (document_id,))

        connection.executemany(
            """
            INSERT INTO headings(document_id, level, heading_text, anchor, position)
            VALUES(?, ?, ?, ?, ?)
            """,
            [
                (document_id, heading.level, heading.text, heading.anchor, heading.position)
                for heading in parsed.headings
            ],
        )

        connection.executemany(
            """
            INSERT INTO links(document_id, source_anchor, target, is_external)
            VALUES(?, NULL, ?, ?)
            """,
            [(document_id, link.target, int(link.is_external)) for link in parsed.links],
        )
        connection.commit()

    return document_id


def search_documents(database_path: Path, query: str, limit: int = 10) -> list[DocumentRecord]:
    pattern = f"%{query.strip()}%"
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, path, title, summary, token_estimate, updated_at
            FROM documents
            WHERE title LIKE ? OR summary LIKE ? OR path LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, limit),
        ).fetchall()

    return [
        DocumentRecord(
            id=int(row[0]),
            path=str(row[1]),
            title=str(row[2] or ""),
            summary=str(row[3] or ""),
            token_estimate=int(row[4] or 0),
            updated_at=str(row[5] or ""),
        )
        for row in rows
    ]


def get_document(database_path: Path, document_id: int) -> DocumentDetail | None:
    with sqlite3.connect(database_path) as connection:
        doc = connection.execute(
            """
            SELECT id, path, title, summary, token_estimate, updated_at
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
        if doc is None:
            return None

        heading_rows = connection.execute(
            """
            SELECT level, heading_text, anchor, position
            FROM headings
            WHERE document_id = ?
            ORDER BY position ASC
            """,
            (document_id,),
        ).fetchall()
        link_rows = connection.execute(
            """
            SELECT target, is_external, status
            FROM links
            WHERE document_id = ?
            ORDER BY id ASC
            """,
            (document_id,),
        ).fetchall()

    return DocumentDetail(
        id=int(doc[0]),
        path=str(doc[1]),
        title=str(doc[2] or ""),
        summary=str(doc[3] or ""),
        token_estimate=int(doc[4] or 0),
        updated_at=str(doc[5] or ""),
        headings=[
            {
                "level": int(row[0]),
                "text": str(row[1]),
                "anchor": str(row[2] or ""),
                "position": int(row[3]),
            }
            for row in heading_rows
        ],
        links=[
            {
                "target": str(row[0]),
                "is_external": bool(row[1]),
                "status": str(row[2] or "unknown"),
            }
            for row in link_rows
        ],
    )
