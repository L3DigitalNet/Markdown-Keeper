from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
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


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


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




def _document_exists(database_path: Path, path: Path) -> bool:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT 1 FROM documents WHERE path = ? LIMIT 1",
            (str(path),),
        ).fetchone()
    return row is not None

def _desired_event_type(path: Path, deleted_paths: set[Path]) -> str:
    return "delete" if path in deleted_paths else "upsert"


def _queue_events(
    database_path: Path,
    changed_paths: list[Path],
    deleted_paths: list[Path],
) -> None:
    deleted_set = set(deleted_paths)
    all_paths = sorted(set(changed_paths) | deleted_set)
    if not all_paths:
        return

    now = _utc_now_iso()
    with sqlite3.connect(database_path) as connection:
        for path in all_paths:
            event_type = _desired_event_type(path, deleted_set)
            existing = connection.execute(
                """
                SELECT id, event_type
                FROM events
                WHERE path = ? AND status = 'queued'
                ORDER BY id DESC
                LIMIT 1
                """,
                (str(path),),
            ).fetchone()
            if existing:
                event_id = int(existing[0])
                current_event_type = str(existing[1])
                if current_event_type == event_type:
                    continue
                connection.execute(
                    """
                    UPDATE events
                    SET event_type = ?, created_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (event_type, now, now, event_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO events(event_type, path, created_at, updated_at, status, attempts)
                    VALUES(?, ?, ?, ?, 'queued', 0)
                    """,
                    (event_type, str(path), now, now),
                )
        connection.commit()


def _drain_event_queue(database_path: Path, batch_size: int = 256) -> WatchRunResult:
    result = WatchRunResult()
    with sqlite3.connect(database_path) as connection:
        while True:
            queued = connection.execute(
                """
                SELECT id, event_type, path, attempts
                FROM events
                WHERE status = 'queued'
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                (batch_size,),
            ).fetchall()
            if not queued:
                connection.commit()
                return result

            for row in queued:
                event_id = int(row[0])
                event_type = str(row[1])
                path = Path(str(row[2]))
                attempts = int(row[3])
                now = _utc_now_iso()
                connection.execute(
                    "UPDATE events SET status = 'processing', updated_at = ? WHERE id = ?",
                    (now, event_id),
                )
                connection.commit()

                try:
                    if event_type == "delete":
                        delete_document_by_path(database_path, path)
                        result.deleted += 1
                    else:
                        if path.exists() and path.is_file():
                            existed = _document_exists(database_path, path)
                            parsed = parse_markdown(path.read_text(encoding="utf-8"))
                            upsert_document(database_path, path, parsed)
                            if existed:
                                result.modified += 1
                            else:
                                result.created += 1
                        else:
                            delete_document_by_path(database_path, path)
                            result.deleted += 1

                    connection.execute(
                        "UPDATE events SET status = 'done', updated_at = ? WHERE id = ?",
                        (_utc_now_iso(), event_id),
                    )
                except Exception as exc:  # pragma: no cover - defensive retry branch
                    next_attempt = attempts + 1
                    status = "failed" if next_attempt >= 5 else "queued"
                    connection.execute(
                        """
                        UPDATE events
                        SET status = ?, attempts = ?, last_error = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (status, next_attempt, str(exc), _utc_now_iso(), event_id),
                    )
                connection.commit()


def watch_once(
    database_path: Path,
    roots: list[Path],
    extensions: list[str],
    previous_snapshot: dict[Path, float] | None = None,
) -> tuple[dict[Path, float], WatchRunResult]:
    ext_set = {ext.lower() for ext in extensions}
    old = previous_snapshot or {}
    new = _snapshot(roots, ext_set)

    created = [path for path in new if path not in old]
    deleted = [path for path in old if path not in new]
    modified = [path for path in new if path in old and new[path] != old[path]]

    _queue_events(
        database_path=database_path,
        changed_paths=created + modified,
        deleted_paths=deleted,
    )
    result = _drain_event_queue(database_path)
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
    pending_delete = sorted(handler.deleted)
    pending_change = sorted(handler.changed)
    handler.deleted.clear()
    handler.changed.clear()

    _queue_events(
        database_path=database_path,
        changed_paths=pending_change,
        deleted_paths=pending_delete,
    )
    return _drain_event_queue(database_path)


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
            total.created += step.created
            total.modified += step.modified
            total.deleted += step.deleted

            if duration_s is not None and (time.monotonic() - started) >= duration_s:
                break
            time.sleep(max(0.05, debounce_s))
    finally:
        observer.stop()
        observer.join(timeout=2)

    final_step = _flush_pending_events(database_path, handler)
    total.created += final_step.created
    total.modified += final_step.modified
    total.deleted += final_step.deleted
    return total
