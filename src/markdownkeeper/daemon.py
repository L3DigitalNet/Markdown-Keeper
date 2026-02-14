from __future__ import annotations

from pathlib import Path
import os
import signal
import subprocess
import time


def _read_pid(pid_file: Path) -> int | None:
    if not pid_file.exists():
        return None
    raw = pid_file.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def start_background(command: list[str], pid_file: Path) -> int:
    existing = _read_pid(pid_file)
    if existing is not None and _is_pid_running(existing):
        return existing

    pid_file.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(  # noqa: S603
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    pid_file.write_text(str(process.pid), encoding="utf-8")
    return int(process.pid)


def stop_background(pid_file: Path, timeout_s: float = 5.0) -> bool:
    pid = _read_pid(pid_file)
    if pid is None:
        return False

    if not _is_pid_running(pid):
        pid_file.unlink(missing_ok=True)
        return False

    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _is_pid_running(pid):
            pid_file.unlink(missing_ok=True)
            return True
        time.sleep(0.05)

    os.kill(pid, signal.SIGKILL)
    pid_file.unlink(missing_ok=True)
    return True


def status_background(pid_file: Path) -> tuple[bool, int | None]:
    pid = _read_pid(pid_file)
    if pid is None:
        return False, None
    return _is_pid_running(pid), pid


def restart_background(command: list[str], pid_file: Path, timeout_s: float = 5.0) -> int:
    stop_background(pid_file, timeout_s=timeout_s)
    return start_background(command, pid_file)


def reload_background(pid_file: Path) -> bool:
    pid = _read_pid(pid_file)
    if pid is None or not _is_pid_running(pid):
        return False
    os.kill(pid, signal.SIGHUP)
    return True
