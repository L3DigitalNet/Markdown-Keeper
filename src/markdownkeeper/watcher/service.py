from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from markdownkeeper.processor.parser import parse_markdown
from markdownkeeper.storage.repository import delete_document_by_path, upsert_document


@dataclass(slots=True)
class WatchRunResult:
    created: int = 0
    modified: int = 0
    deleted: int = 0


def _snapshot(roots: list[Path], extensions: set[str]) -> dict[Path, float]:
    snap: dict[Path, float] = {}
    for root in roots:
        if not root.exists():
            continue
        for file in root.rglob("*"):
            if file.is_file() and file.suffix.lower() in extensions:
                snap[file.resolve()] = file.stat().st_mtime
    return snap


def watch_once(
    database_path: Path,
    roots: list[Path],
    extensions: list[str],
    previous_snapshot: dict[Path, float] | None = None,
) -> tuple[dict[Path, float], WatchRunResult]:
    ext_set = {ext.lower() for ext in extensions}
    old = previous_snapshot or {}
    new = _snapshot(roots, ext_set)

    result = WatchRunResult()

    created = [path for path in new if path not in old]
    deleted = [path for path in old if path not in new]
    modified = [path for path in new if path in old and new[path] != old[path]]

    for path in created + modified:
        parsed = parse_markdown(path.read_text(encoding="utf-8"))
        upsert_document(database_path, path, parsed)

    for path in deleted:
        delete_document_by_path(database_path, path)

    result.created = len(created)
    result.modified = len(modified)
    result.deleted = len(deleted)
    return new, result


def watch_loop(
    database_path: Path,
    roots: list[Path],
    extensions: list[str],
    interval_s: float = 1.0,
    iterations: int | None = None,
) -> WatchRunResult:
    total = WatchRunResult()
    snapshot: dict[Path, float] | None = None
    runs = 0

    while True:
        snapshot, result = watch_once(
            database_path=database_path,
            roots=roots,
            extensions=extensions,
            previous_snapshot=snapshot,
        )
        total.created += result.created
        total.modified += result.modified
        total.deleted += result.deleted

        runs += 1
        if iterations is not None and runs >= iterations:
            return total

        time.sleep(interval_s)
