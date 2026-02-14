from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from markdownkeeper.processor.parser import parse_markdown
from markdownkeeper.storage.repository import delete_document_by_path, upsert_document

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except Exception:  # pragma: no cover - optional dependency
    FileSystemEventHandler = object  # type: ignore[assignment]
    Observer = None  # type: ignore[assignment]


@dataclass(slots=True)
class WatchRunResult:
    created: int = 0
    modified: int = 0
    deleted: int = 0


def is_watchdog_available() -> bool:
    return Observer is not None


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


class _MarkdownWatchEventHandler(FileSystemEventHandler):
    def __init__(self, extensions: set[str]) -> None:
        super().__init__()
        self.extensions = extensions
        self.changed: set[Path] = set()
        self.deleted: set[Path] = set()

    def _is_markdown_file(self, path: str) -> bool:
        candidate = Path(path)
        return candidate.suffix.lower() in self.extensions

    def _record_change(self, path: str) -> None:
        candidate = Path(path).resolve()
        if self._is_markdown_file(path):
            self.changed.add(candidate)
            self.deleted.discard(candidate)

    def _record_delete(self, path: str) -> None:
        candidate = Path(path).resolve()
        if self._is_markdown_file(path):
            self.deleted.add(candidate)
            self.changed.discard(candidate)

    def on_created(self, event) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._record_change(event.src_path)

    def on_modified(self, event) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._record_change(event.src_path)

    def on_moved(self, event) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._record_delete(event.src_path)
            self._record_change(event.dest_path)

    def on_deleted(self, event) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._record_delete(event.src_path)


def _flush_pending_events(
    database_path: Path,
    handler: _MarkdownWatchEventHandler,
) -> WatchRunResult:
    result = WatchRunResult()

    pending_delete = sorted(handler.deleted)
    pending_change = sorted(handler.changed)
    handler.deleted.clear()
    handler.changed.clear()

    for path in pending_delete:
        delete_document_by_path(database_path, path)
        result.deleted += 1

    for path in pending_change:
        if not path.exists():
            continue
        parsed = parse_markdown(path.read_text(encoding="utf-8"))
        upsert_document(database_path, path, parsed)
        result.modified += 1

    return result


def watch_loop_watchdog(
    database_path: Path,
    roots: list[Path],
    extensions: list[str],
    debounce_s: float = 0.25,
    duration_s: float | None = None,
) -> WatchRunResult:
    if not is_watchdog_available():
        raise RuntimeError("watchdog is not installed; use polling mode")

    ext_set = {ext.lower() for ext in extensions}
    handler = _MarkdownWatchEventHandler(ext_set)
    observer = Observer()

    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
        observer.schedule(handler, str(root), recursive=True)

    total = WatchRunResult()
    started = time.monotonic()
    observer.start()

    try:
        while True:
            step = _flush_pending_events(database_path, handler)
            total.modified += step.modified
            total.deleted += step.deleted

            if duration_s is not None and (time.monotonic() - started) >= duration_s:
                break
            time.sleep(max(0.05, debounce_s))
    finally:
        observer.stop()
        observer.join(timeout=2)

    return total
