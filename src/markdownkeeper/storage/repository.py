from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
import statistics
import time

from markdownkeeper.processor.parser import ParsedDocument
from markdownkeeper.query.embeddings import compute_embedding, cosine_similarity, is_model_embedding_available


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


def _deserialize_embedding(raw: object) -> list[float]:
    if raw is None:
        return []
    try:
        payload = json.loads(str(raw))
    except (ValueError, TypeError, json.JSONDecodeError):
        return []
    try:
        return [float(item) for item in payload]
    except (ValueError, TypeError):
        return []


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
        chunk_rows: list[tuple[int, int, str, str, int, str]] = []
        for idx, heading_path, content, token_count in chunks:
            chunk_embedding, _ = compute_embedding(content)
            chunk_rows.append(
                (document_id, idx, heading_path, content, token_count, json.dumps(chunk_embedding))
            )

        connection.executemany(
            """
            INSERT INTO document_chunks(document_id, chunk_index, heading_path, content, token_count, embedding)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            chunk_rows,
        )

        embedding_source = " ".join(
            [
                str(parsed.title or ""),
                str(parsed.summary or ""),
                str(parsed.body or ""),
                " ".join(parsed.tags),
                " ".join(parsed.concepts),
                str(parsed.category or ""),
            ]
        )
        embedding, model_name = compute_embedding(embedding_source)
        connection.execute(
            """
            INSERT INTO embeddings(document_id, embedding, model_name, generated_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
              embedding=excluded.embedding,
              model_name=excluded.model_name,
              generated_at=excluded.generated_at
            """,
            (document_id, json.dumps(embedding), model_name, now),
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


def _tokenize(text: str) -> set[str]:
    import re

    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1}


def _compute_text_embedding(text: str, dimensions: int = 64) -> list[float]:
    # Compatibility shim for tests and transitional callers.
    # dimensions is ignored when sentence-transformers is available.
    vector, _ = compute_embedding(text)
    if len(vector) == dimensions:
        return vector
    if not vector:
        return [0.0] * dimensions
    if len(vector) > dimensions:
        return vector[:dimensions]
    return vector + ([0.0] * (dimensions - len(vector)))


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    return cosine_similarity(left, right)


def _fetch_cache(connection: sqlite3.Connection, query_hash: str) -> list[int] | None:
    row = connection.execute(
        "SELECT id, result_json FROM query_cache WHERE query_hash = ?",
        (query_hash,),
    ).fetchone()
    if row is None:
        return None
    cache_id = int(row[0])
    payload = json.loads(str(row[1]))
    connection.execute(
        "UPDATE query_cache SET hit_count = hit_count + 1, last_accessed = ? WHERE id = ?",
        (_utc_now_iso(), cache_id),
    )
    return [int(item) for item in payload.get("document_ids", [])]


def _store_cache(connection: sqlite3.Connection, query_hash: str, query_text: str, document_ids: list[int]) -> None:
    now = _utc_now_iso()
    connection.execute(
        """
        INSERT INTO query_cache(query_hash, query_text, result_json, created_at, hit_count, last_accessed)
        VALUES(?, ?, ?, ?, 0, ?)
        ON CONFLICT(query_hash) DO UPDATE SET
          query_text=excluded.query_text,
          result_json=excluded.result_json,
          created_at=excluded.created_at,
          last_accessed=excluded.last_accessed
        """,
        (query_hash, query_text, json.dumps({"document_ids": document_ids}), now, now),
    )


def semantic_search_documents(database_path: Path, query: str, limit: int = 10) -> list[DocumentRecord]:
    cleaned = query.strip().lower()
    if not cleaned:
        return []

    query_hash = hashlib.sha256(f"semantic:{cleaned}:{limit}".encode("utf-8")).hexdigest()

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        cached_ids = _fetch_cache(connection, query_hash)
        if cached_ids:
            placeholders = ",".join("?" for _ in cached_ids)
            rows = connection.execute(
                f"""
                SELECT id, path, title, summary, category, token_estimate, updated_at
                FROM documents
                WHERE id IN ({placeholders})
                """,
                tuple(cached_ids),
            ).fetchall()
            by_id = {int(row[0]): row for row in rows}
            ordered_rows = [by_id[item] for item in cached_ids if item in by_id]
            connection.commit()
            return _rows_to_records(ordered_rows)

        query_tokens = _tokenize(cleaned)
        rows = connection.execute(
            """
            SELECT d.id, d.path, d.title, d.summary, d.category, d.token_estimate, d.updated_at, d.content, e.embedding
            FROM documents d
            LEFT JOIN embeddings e ON e.document_id = d.id
            """
        ).fetchall()

        query_embedding, _ = compute_embedding(cleaned)
        scored: list[tuple[float, tuple[object, ...]]] = []
        for row in rows:
            document_id = int(row[0])
            haystack = " ".join(
                [
                    str(row[1] or ""),
                    str(row[2] or ""),
                    str(row[3] or ""),
                    str(row[7] or ""),
                ]
            )
            tokens = _tokenize(haystack)
            overlap = len(query_tokens & tokens)
            lexical_score = overlap / max(1, len(query_tokens)) if overlap > 0 else 0.0

            vector_score = cosine_similarity(query_embedding, _deserialize_embedding(row[8]))

            chunk_rows = connection.execute(
                """
                SELECT embedding
                FROM document_chunks
                WHERE document_id = ?
                ORDER BY chunk_index ASC
                """,
                (document_id,),
            ).fetchall()
            chunk_scores = [
                cosine_similarity(query_embedding, _deserialize_embedding(chunk_row[0]))
                for chunk_row in chunk_rows
                if chunk_row[0] is not None
            ]
            chunk_score = max(chunk_scores) if chunk_scores else 0.0

            concept_rows = connection.execute(
                """
                SELECT c.name
                FROM concepts c
                JOIN document_concepts dc ON dc.concept_id = c.id
                WHERE dc.document_id = ?
                """,
                (document_id,),
            ).fetchall()
            concepts = {str(item[0]) for item in concept_rows}
            concept_score = 1.0 if query_tokens & concepts else 0.0

            freshness_bonus = 0.05 if str(row[6]).startswith(str(datetime.now(tz=timezone.utc).year)) else 0.0

            score = (
                (0.45 * vector_score)
                + (0.30 * chunk_score)
                + (0.20 * lexical_score)
                + (0.05 * concept_score)
                + freshness_bonus
            )
            if score <= 0.0:
                continue
            scored.append((score, row[:7]))

        scored.sort(key=lambda item: (item[0], str(item[1][6])), reverse=True)
        top_rows = [row for _, row in scored[: max(1, limit)]]
        top_ids = [int(row[0]) for row in top_rows]

        if not top_rows:
            fallback = search_documents(database_path, query, limit=limit)
            _store_cache(connection, query_hash, cleaned, [item.id for item in fallback])
            connection.commit()
            return fallback

        _store_cache(connection, query_hash, cleaned, top_ids)
        connection.commit()
        return _rows_to_records(top_rows)




def regenerate_embeddings(database_path: Path, model_name: str = "all-MiniLM-L6-v2") -> int:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, title, summary, category, content
            FROM documents
            """
        ).fetchall()
        now = _utc_now_iso()
        updated = 0
        for row in rows:
            document_id = int(row[0])
            source = " ".join([str(row[1] or ""), str(row[2] or ""), str(row[3] or ""), str(row[4] or "")])
            embedding, resolved_model = compute_embedding(source, model_name=model_name)
            connection.execute(
                """
                INSERT INTO embeddings(document_id, embedding, model_name, generated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                  embedding=excluded.embedding,
                  model_name=excluded.model_name,
                  generated_at=excluded.generated_at
                """,
                (document_id, json.dumps(embedding), resolved_model, now),
            )
            updated += 1
        connection.commit()
        return updated


def embedding_coverage(database_path: Path, model_name: str = "all-MiniLM-L6-v2") -> dict[str, int | bool]:
    with sqlite3.connect(database_path) as connection:
        total = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
        embedded = int(
            connection.execute(
                "SELECT COUNT(*) FROM embeddings WHERE embedding IS NOT NULL AND LENGTH(TRIM(embedding)) > 0"
            ).fetchone()[0]
        )
        chunk_total = int(connection.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0])
        chunk_embedded = int(
            connection.execute(
                "SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL AND LENGTH(TRIM(embedding)) > 0"
            ).fetchone()[0]
        )
    return {
        "documents": total,
        "embedded": embedded,
        "missing": max(0, total - embedded),
        "chunks": chunk_total,
        "chunk_embedded": chunk_embedded,
        "chunk_missing": max(0, chunk_total - chunk_embedded),
        "model_available": is_model_embedding_available(model_name),
    }


def evaluate_semantic_precision(
    database_path: Path,
    cases: list[dict[str, object]],
    k: int = 5,
) -> dict[str, object]:
    if not cases:
        return {"cases": 0, "k": k, "precision_at_k": 0.0, "details": []}

    details: list[dict[str, object]] = []
    total_hits = 0.0
    for case in cases:
        query = str(case.get("query", "")).strip()
        expected = {int(item) for item in case.get("expected_ids", []) if str(item).isdigit()}
        results = semantic_search_documents(database_path, query, limit=max(1, k))
        got_ids = [item.id for item in results[:k]]
        hits = len(expected & set(got_ids))
        precision = hits / max(1, k)
        total_hits += precision
        details.append(
            {
                "query": query,
                "expected_ids": sorted(expected),
                "result_ids": got_ids,
                "precision_at_k": precision,
            }
        )

    return {
        "cases": len(cases),
        "k": k,
        "precision_at_k": total_hits / len(cases),
        "details": details,
    }


def system_stats(database_path: Path, model_name: str = "all-MiniLM-L6-v2") -> dict[str, object]:
    coverage = embedding_coverage(database_path, model_name=model_name)
    with sqlite3.connect(database_path) as connection:
        queued = int(connection.execute("SELECT COUNT(*) FROM events WHERE status='queued'").fetchone()[0])
        failed = int(connection.execute("SELECT COUNT(*) FROM events WHERE status='failed'").fetchone()[0])
        oldest = connection.execute(
            "SELECT created_at FROM events WHERE status='queued' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        docs = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
        links = int(connection.execute("SELECT COUNT(*) FROM links").fetchone()[0])

    queue_lag_seconds = 0.0
    if oldest and oldest[0]:
        try:
            created_ts = datetime.fromisoformat(str(oldest[0])).timestamp()
            queue_lag_seconds = max(0.0, time.time() - created_ts)
        except ValueError:
            queue_lag_seconds = 0.0

    return {
        "documents": docs,
        "links": links,
        "queue": {"queued": queued, "failed": failed, "lag_seconds": round(queue_lag_seconds, 3)},
        "embeddings": coverage,
    }


def benchmark_semantic_queries(
    database_path: Path,
    cases: list[dict[str, object]],
    k: int = 5,
    iterations: int = 1,
) -> dict[str, object]:
    if not cases:
        return {
            "cases": 0,
            "iterations": max(1, iterations),
            "k": max(1, k),
            "precision_at_k": 0.0,
            "latency_ms": {"avg": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0},
        }

    k = max(1, int(k))
    iterations = max(1, int(iterations))
    latencies_ms: list[float] = []

    for _ in range(iterations):
        for case in cases:
            query = str(case.get("query", "")).strip()
            start = time.perf_counter()
            semantic_search_documents(database_path, query, limit=k)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            latencies_ms.append(elapsed_ms)

    precision_report = evaluate_semantic_precision(database_path, cases, k=k)

    sorted_lat = sorted(latencies_ms)
    p50 = statistics.median(sorted_lat)
    p95_index = min(len(sorted_lat) - 1, int(round(0.95 * (len(sorted_lat) - 1))))
    p95 = sorted_lat[p95_index]

    return {
        "cases": len(cases),
        "iterations": iterations,
        "k": k,
        "precision_at_k": float(precision_report["precision_at_k"]),
        "latency_ms": {
            "avg": round(sum(sorted_lat) / len(sorted_lat), 3),
            "p50": round(p50, 3),
            "p95": round(p95, 3),
            "max": round(max(sorted_lat), 3),
        },
    }


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
