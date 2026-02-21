from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass(slots=True)
class LinkCheckResult:
    link_id: int
    target: str
    status: str


class _DomainRateLimiter:
    """Per-domain delay to avoid rate limiting on external link checks."""

    def __init__(self, min_delay: float = 1.0) -> None:
        self.min_delay = min_delay
        self._last_access: dict[str, float] = {}

    def wait(self, domain: str) -> None:
        now = time.monotonic()
        last = self._last_access.get(domain)
        if last is not None:
            remaining = self.min_delay - (now - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_access[domain] = time.monotonic()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _check_external(target: str, timeout_s: float = 3.0) -> str:
    """Check external URL. Tries HEAD first, falls back to GET on 405."""
    try:
        req = Request(target, method="HEAD")
        with urlopen(req, timeout=timeout_s) as response:  # noqa: S310
            code = getattr(response, "status", 200)
            return "ok" if 200 <= code < 400 else "broken"
    except HTTPError as exc:
        if exc.code == 405:
            # Server doesn't allow HEAD, try GET
            try:
                req_get = Request(target, method="GET")
                with urlopen(req_get, timeout=timeout_s) as response:  # noqa: S310
                    code = getattr(response, "status", 200)
                    return "ok" if 200 <= code < 400 else "broken"
            except Exception:
                return "broken"
        return "broken"
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


def validate_links(
    database_path: Path,
    timeout_s: float = 3.0,
    check_external: bool = False,
) -> list[LinkCheckResult]:
    now = _now_iso()
    results: list[LinkCheckResult] = []
    limiter = _DomainRateLimiter(min_delay=1.0)

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
                if not check_external:
                    continue
                parsed = urlparse(t)
                if parsed.scheme in {"http", "https"}:
                    limiter.wait(parsed.hostname or "")
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
