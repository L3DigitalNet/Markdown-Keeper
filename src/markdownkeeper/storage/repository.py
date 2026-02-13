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
    category: str
    token_estimate: int
    updated_at: str


@dataclass(slots=True)
class DocumentDetail(DocumentRecord):
    headings: list[dict[str, object]]
    links: list[dict[str, object]]
    tags: list[str]
    concepts: list[str]
    content: str


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _get_or_create_id(connection: sqlite3.Connection, table: str, name: str) -> int:
    row = connection.execute(f"SELECT id FROM {table} WHERE name = ?", (name,)).fetchone()
    if row:
        return int(row[0])
    connection.execute(f"INSERT INTO {table}(name) VALUES(?)", (name,))
    row2 = connection.execute(f"SELECT id FROM {table} WHERE name = ?", (name,)).fetchone()
    return int(row2[0])


def _chunk_document(parsed: ParsedDocument, max_words: int = 120) -> list[tuple[int, str, str, int]]:
    paragraphs = [p.strip() for p in parsed.body.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[tuple[int, str, str, int]] = []
    heading_path = parsed.headings[0].text if parsed.headings else ""
    idx = 0
    for paragraph in paragraphs:
        words = paragraph.split()
        start = 0
        while start < len(words):
            subset = words[start : start + max_words]
            content = " ".join(subset)
            chunks.append((idx, heading_path, content, len(subset)))
            idx += 1
            start += max_words
    return chunks


def upsert_document(database_path: Path, file_path: Path, parsed: ParsedDocument) -> int:
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        now = _utc_now_iso()
        connection.execute(
            """
            INSERT INTO documents(path, title, summary, category, content, content_hash, token_estimate, updated_at, processed_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
              title=excluded.title,
              summary=excluded.summary,
              category=excluded.category,
              content=excluded.content,
              content_hash=excluded.content_hash,
              token_estimate=excluded.token_estimate,
              updated_at=excluded.updated_at,
              processed_at=excluded.processed_at
            """,
            (
                str(file_path),
                parsed.title,
                parsed.summary,
                parsed.category,
                parsed.body,
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
        connection.execute("DELETE FROM document_tags WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM document_concepts WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))

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

        for tag in parsed.tags:
            tag_id = _get_or_create_id(connection, "tags", tag.lower())
            connection.execute(
                "INSERT OR IGNORE INTO document_tags(document_id, tag_id) VALUES(?, ?)",
                (document_id, tag_id),
            )

        for concept in parsed.concepts:
            concept_id = _get_or_create_id(connection, "concepts", concept.lower())
            connection.execute(
                "INSERT OR IGNORE INTO document_concepts(document_id, concept_id, score) VALUES(?, ?, 1.0)",
                (document_id, concept_id),
            )

        chunks = _chunk_document(parsed)
        connection.executemany(
            """
            INSERT INTO document_chunks(document_id, chunk_index, heading_path, content, token_count)
            VALUES(?, ?, ?, ?, ?)
            """,
            [(document_id, idx, heading_path, content, token_count) for idx, heading_path, content, token_count in chunks],
        )

        connection.commit()

    return document_id


def delete_document_by_path(database_path: Path, file_path: Path) -> bool:
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        deleted = connection.execute(
            "DELETE FROM documents WHERE path = ?", (str(file_path),)
        ).rowcount
        connection.commit()
        return bool(deleted)


def _rows_to_records(rows: list[tuple[object, ...]]) -> list[DocumentRecord]:
    return [
        DocumentRecord(
            id=int(row[0]),
            path=str(row[1]),
            title=str(row[2] or ""),
            summary=str(row[3] or ""),
            category=str(row[4] or ""),
            token_estimate=int(row[5] or 0),
            updated_at=str(row[6] or ""),
        )
        for row in rows
    ]


def list_documents(database_path: Path) -> list[DocumentRecord]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, path, title, summary, category, token_estimate, updated_at
            FROM documents
            ORDER BY updated_at DESC
            """
        ).fetchall()

    return _rows_to_records(rows)


def search_documents(database_path: Path, query: str, limit: int = 10) -> list[DocumentRecord]:
    pattern = f"%{query.strip()}%"
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, path, title, summary, category, token_estimate, updated_at
            FROM documents
            WHERE title LIKE ? OR summary LIKE ? OR path LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, limit),
        ).fetchall()

    return _rows_to_records(rows)


def find_documents_by_concept(database_path: Path, concept: str, limit: int = 10) -> list[DocumentRecord]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT d.id, d.path, d.title, d.summary, d.category, d.token_estimate, d.updated_at
            FROM documents d
            JOIN document_concepts dc ON dc.document_id = d.id
            JOIN concepts c ON c.id = dc.concept_id
            WHERE c.name = ?
            ORDER BY d.updated_at DESC
            LIMIT ?
            """,
            (concept.lower().strip(), limit),
        ).fetchall()
    return _rows_to_records(rows)


def _select_content(
    connection: sqlite3.Connection,
    document_id: int,
    include_content: bool,
    max_tokens: int | None,
    section: str | None,
) -> str:
    if not include_content:
        return ""

    if section:
        rows = connection.execute(
            """
            SELECT content, token_count
            FROM document_chunks
            WHERE document_id = ? AND LOWER(heading_path) LIKE ?
            ORDER BY chunk_index ASC
            """,
            (document_id, f"%{section.lower()}%"),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT content, token_count
            FROM document_chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
            """,
            (document_id,),
        ).fetchall()

    budget = max_tokens if max_tokens is not None and max_tokens > 0 else None
    selected: list[str] = []
    used = 0
    for content, token_count in rows:
        tc = int(token_count)
        text = str(content)
        if budget is not None and used + tc > budget:
            remaining = budget - used
            if remaining <= 0:
                break
            selected.append(" ".join(text.split()[:remaining]))
            used += remaining
            break
        selected.append(text)
        used += tc

    return "\n\n".join(selected)


def get_document(
    database_path: Path,
    document_id: int,
    include_content: bool = False,
    max_tokens: int | None = None,
    section: str | None = None,
) -> DocumentDetail | None:
    with sqlite3.connect(database_path) as connection:
        doc = connection.execute(
            """
            SELECT id, path, title, summary, category, token_estimate, updated_at
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
        tag_rows = connection.execute(
            """
            SELECT t.name
            FROM tags t
            JOIN document_tags dt ON dt.tag_id = t.id
            WHERE dt.document_id = ?
            ORDER BY t.name ASC
            """,
            (document_id,),
        ).fetchall()
        concept_rows = connection.execute(
            """
            SELECT c.name
            FROM concepts c
            JOIN document_concepts dc ON dc.concept_id = c.id
            WHERE dc.document_id = ?
            ORDER BY c.name ASC
            """,
            (document_id,),
        ).fetchall()

        content = _select_content(connection, document_id, include_content, max_tokens, section)

    return DocumentDetail(
        id=int(doc[0]),
        path=str(doc[1]),
        title=str(doc[2] or ""),
        summary=str(doc[3] or ""),
        category=str(doc[4] or ""),
        token_estimate=int(doc[5] or 0),
        updated_at=str(doc[6] or ""),
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
        tags=[str(row[0]) for row in tag_rows],
        concepts=[str(row[0]) for row in concept_rows],
        content=content,
    )
