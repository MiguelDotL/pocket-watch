"""State-path resolution for pocket-watch.

Priority:
  1. $CLAUDE_PLUGIN_DATA  (set by Claude Code for all hooks)
  2. ~/.claude/data/pocket-watch/  (fallback)
"""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """Return the data directory, creating it if needed (mode 0700)."""
    env_val = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    if env_val:
        base = Path(env_val)
    else:
        base = Path.home() / ".claude" / "data" / "pocket-watch"

    # Resolve symlinks; validate target is writable.
    try:
        resolved = base.resolve()
    except OSError:
        resolved = base

    if not resolved.exists():
        resolved.mkdir(parents=True, exist_ok=True)
        resolved.chmod(0o700)

    return resolved


def estimates_path() -> Path:
    return data_dir() / "estimates.jsonl"


def config_path() -> Path:
    return data_dir() / "config.json"


def habits_path() -> Path:
    return data_dir() / "habits.json"


def hook_health_path() -> Path:
    return data_dir() / "hook-health.json"


def session_state_path(session_id: str) -> Path:
    return data_dir() / f"session-state-{session_id}.json"


def errors_log_path() -> Path:
    return data_dir() / "errors.log"


def first_run_flag_path() -> Path:
    return data_dir() / "first_run.flag"


def audit_log_path() -> Path:
    return data_dir() / "audit-log.jsonl"


def ensure_file_perms(path: Path, mode: int = 0o600) -> None:
    """Ensure a file exists with the given permissions."""
    if path.exists():
        path.chmod(mode)
