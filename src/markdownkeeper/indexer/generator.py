from __future__ import annotations

from pathlib import Path
import sqlite3

from markdownkeeper.storage.repository import list_documents


def _write(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def generate_master_index(database_path: Path, output_dir: Path) -> Path:
    out = output_dir / "master.md"
    docs = list_documents(database_path)

    lines = ["# MarkdownKeeper Master Index", ""]
    if not docs:
        lines.append("_No indexed documents found._")
    else:
        for doc in docs:
            summary = doc.summary.replace("\n", " ").strip()
            lines.append(f"- [{doc.id}] **{doc.title or 'Untitled'}** (`{doc.path}`)")
            if summary:
                lines.append(f"  - {summary[:180]}")

    return _write(out, lines)


def generate_category_index(database_path: Path, output_dir: Path) -> Path:
    out = output_dir / "by-category.md"
    lines = ["# Documents by Category", ""]
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT COALESCE(category, 'uncategorized') AS category, id, title, path
            FROM documents
            ORDER BY category, title
            """
        ).fetchall()

    current = None
    for category, doc_id, title, path in rows:
        if category != current:
            lines.extend([f"## {category}", ""])
            current = category
        lines.append(f"- [{int(doc_id)}] **{title or 'Untitled'}** (`{path}`)")
    if len(rows) == 0:
        lines.append("_No indexed documents found._")
    return _write(out, lines)


def generate_tag_index(database_path: Path, output_dir: Path) -> Path:
    out = output_dir / "by-tag.md"
    lines = ["# Documents by Tag", ""]
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT t.name, d.id, d.title, d.path
            FROM tags t
            JOIN document_tags dt ON dt.tag_id = t.id
            JOIN documents d ON d.id = dt.document_id
            ORDER BY t.name, d.title
            """
        ).fetchall()

    current = None
    for tag, doc_id, title, path in rows:
        if tag != current:
            lines.extend([f"## {tag}", ""])
            current = tag
        lines.append(f"- [{int(doc_id)}] **{title or 'Untitled'}** (`{path}`)")
    if len(rows) == 0:
        lines.append("_No tagged documents found._")
    return _write(out, lines)


def generate_concept_index(database_path: Path, output_dir: Path) -> Path:
    out = output_dir / "by-concept.md"
    lines = ["# Documents by Concept", ""]
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT c.name, d.id, d.title, d.path
            FROM concepts c
            JOIN document_concepts dc ON dc.concept_id = c.id
            JOIN documents d ON d.id = dc.document_id
            ORDER BY c.name, d.title
            """
        ).fetchall()

    current = None
    for concept, doc_id, title, path in rows:
        if concept != current:
            lines.extend([f"## {concept}", ""])
            current = concept
        lines.append(f"- [{int(doc_id)}] **{title or 'Untitled'}** (`{path}`)")
    if len(rows) == 0:
        lines.append("_No concept mappings found._")
    return _write(out, lines)


def generate_all_indexes(database_path: Path, output_dir: Path) -> list[Path]:
    return [
        generate_master_index(database_path, output_dir),
        generate_category_index(database_path, output_dir),
        generate_tag_index(database_path, output_dir),
        generate_concept_index(database_path, output_dir),
    ]
