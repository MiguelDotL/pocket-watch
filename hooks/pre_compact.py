#!/usr/bin/env python3
"""PreCompact hook: preserve open-estimate state across compaction.

Saves current session state to session-state-{session_id}.json so that
SessionStart (with source=compact) can restore context afterward.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
if _PLUGIN_ROOT:
    sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "scripts"))
else:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def main() -> None:
    if os.environ.get("POCKET_WATCH_DISABLE", "").strip() == "1":
        print(json.dumps({}))
        return

    try:
        _run()
    except Exception:
        print(json.dumps({}))


def _run() -> None:
    from pocket_watch.paths import session_state_path

    try:
        json.loads(sys.stdin.read())
    except Exception:
        pass

    session_id = os.environ.get("POCKET_WATCH_SESSION_ID", "default")
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    sp = session_state_path(session_id)
    state: dict = {}
    if sp.exists():
        try:
            state = json.loads(sp.read_text())
        except Exception:
            pass

    # Mark compaction checkpoint
    state["compacted_at"] = now_iso
    state["session_id"] = session_id

    try:
        sp.write_text(json.dumps(state, indent=2))
        sp.chmod(0o600)
    except Exception:
        pass

    context_parts: list[str] = []
    open_id = state.get("open_estimate_id")
    if open_id:
        accum = state.get("active_minutes_accumulator", 0.0)
        context_parts.append(
            f"[pocket-watch] Compaction occurred with an open estimate in progress. "
            f"Active time accumulated so far: ~{int(accum)}m. "
            f"The estimate log has been preserved. Run /pw-done when you complete the task."
        )

    if context_parts:
        print(json.dumps({"hookSpecificOutput": {"additionalContext": "\n".join(context_parts)}}))
    else:
        print(json.dumps({}))


if __name__ == "__main__":
    main()
