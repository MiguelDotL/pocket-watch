"""JSONL log management: append, read, skip corrupt lines, flock concurrency."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterator

from pocket_watch.paths import ensure_file_perms


def _flock_append(path: Path, line: str) -> None:
    """Append a JSON line with exclusive file lock (fcntl on Unix, msvcrt on Windows)."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        import msvcrt

        with open(path, "a", encoding="utf-8") as f:
            # Lock from current position to 1 byte forward
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                f.write(line + "\n")
                f.flush()
            finally:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
    else:
        import fcntl

        with open(path, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(line + "\n")
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    ensure_file_perms(path, 0o600)


def append_entry(entry: dict, log_path: Path | None = None) -> None:
    """Append a single entry dict as a JSONL line."""
    from pocket_watch.paths import estimates_path

    if log_path is None:
        log_path = estimates_path()

    line = json.dumps(entry, ensure_ascii=False, default=str)
    _flock_append(log_path, line)


def iter_entries(log_path: Path | None = None, tail: int | None = None) -> Iterator[dict]:
    """Yield valid JSONL entries, skipping corrupt lines.

    Args:
        log_path: path to .jsonl file; defaults to estimates.jsonl
        tail: if set, only read the last N entries (hot-path optimisation)
    """
    from pocket_watch.paths import estimates_path

    if log_path is None:
        log_path = estimates_path()

    if not log_path.exists():
        return

    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    if tail is not None:
        lines = lines[-tail:]

    for line_num, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                yield obj
        except json.JSONDecodeError:
            _log_error(f"Skipping corrupt JSONL line {line_num} in {log_path}")


def read_all(log_path: Path | None = None) -> list[dict]:
    """Return all valid entries as a list."""
    return list(iter_entries(log_path))


def read_tail(n: int, log_path: Path | None = None) -> list[dict]:
    """Return the last N valid entries."""
    return list(iter_entries(log_path, tail=n))


def _log_error(msg: str) -> None:
    """Write an error message to errors.log (best-effort)."""
    try:
        from pocket_watch.paths import errors_log_path
        import datetime

        err_path = errors_log_path()
        ts = datetime.datetime.utcnow().isoformat() + "Z"
        with open(err_path, "a", encoding="utf-8") as f:
            f.write(f"{ts} {msg}\n")
    except Exception:
        pass
