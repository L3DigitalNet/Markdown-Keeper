from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass(slots=True)
class LinkCheckResult:
    link_id: int
    target: str
    status: str


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _check_external(target: str, timeout_s: float = 3.0) -> str:
    try:
        req = Request(target, method="HEAD")
        with urlopen(req, timeout=timeout_s) as response:  # noqa: S310
            code = getattr(response, "status", 200)
            return "ok" if 200 <= code < 400 else "broken"
    except Exception:
        return "broken"


def _check_internal(document_path: str, target: str) -> str:
    if target.startswith("#"):
        return "ok"

    target_path = target.split("#", 1)[0].strip()
    if not target_path:
        return "ok"

    doc = Path(document_path)
    resolved = (doc.parent / target_path).resolve()
    return "ok" if resolved.exists() else "broken"


def validate_links(database_path: Path, timeout_s: float = 3.0) -> list[LinkCheckResult]:
    now = _now_iso()
    results: list[LinkCheckResult] = []

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT l.id, l.target, l.is_external, d.path
            FROM links l
            JOIN documents d ON d.id = l.document_id
            ORDER BY l.id ASC
            """
        ).fetchall()

        for link_id, target, is_external, document_path in rows:
            t = str(target)
            if int(is_external):
                parsed = urlparse(t)
                if parsed.scheme in {"http", "https"}:
                    status = _check_external(t, timeout_s=timeout_s)
                else:
                    status = "broken"
            else:
                status = _check_internal(str(document_path), t)

            connection.execute(
                "UPDATE links SET status = ?, checked_at = ? WHERE id = ?",
                (status, now, int(link_id)),
            )
            results.append(LinkCheckResult(link_id=int(link_id), target=t, status=status))

        connection.commit()

    return results
