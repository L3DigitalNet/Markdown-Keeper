from __future__ import annotations

from pathlib import Path

from markdownkeeper.storage.repository import list_documents


def generate_master_index(database_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
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

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
