#!/usr/bin/env python3
"""PostToolUse hook: capture tool-pattern completion signals.

Detects: gh pr create, git push, test pass, deploy success.
These signals contribute to completion-confidence scoring in stop.py.
Does NOT detect estimates (that's stop.py's job).
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
if _PLUGIN_ROOT:
    sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "scripts"))
else:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

# Tool output patterns for completion signals
_SIGNALS: list[tuple[str, re.Pattern, str]] = [
    ("pr_create", re.compile(r"pull request.*created|https://github\.com/.*/pull/\d+", re.IGNORECASE), "high"),
    ("test_pass", re.compile(r"\d+\s+passed[,\s]|\bAll\s+tests\s+pass(?:ed)?\b|✓\s+\d+\s+tests?", re.IGNORECASE), "medium"),
    ("git_push", re.compile(r"Branch .+ set up to track|Everything up-to-date|->.*master|->.*main", re.IGNORECASE), "medium"),
    ("deploy_success", re.compile(r"Deployment\s+(?:complete|successful|finished)|deployed\s+to\s+(?:production|prod|staging)", re.IGNORECASE), "high"),
    ("release_create", re.compile(r"Release.*created|https://github\.com/.*/releases/tag/", re.IGNORECASE), "high"),
]

# Tools that are worth inspecting
_RELEVANT_TOOLS = {"Bash", "mcp__github__create_pull_request", "mcp__github__push_files"}


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
        event = json.loads(sys.stdin.read())
    except Exception:
        event = {}

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    tool_output = str(event.get("tool_output", ""))
    session_id = os.environ.get("POCKET_WATCH_SESSION_ID", "default")

    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    # Only inspect relevant tools
    if tool_name not in _RELEVANT_TOOLS and not tool_name.startswith("mcp__"):
        # For Bash, check input for gh/git patterns
        if tool_name == "Bash":
            cmd = str(tool_input.get("command", ""))
            if not any(kw in cmd for kw in ("gh pr create", "git push", "pytest", "jest", "npm test", "deploy")):
                print(json.dumps({}))
                return
        else:
            print(json.dumps({}))
            return

    # Match signals
    detected_signal = None
    for signal_name, pattern, strength in _SIGNALS:
        if pattern.search(tool_output):
            detected_signal = {"signal": signal_name, "strength": strength, "ts": now_iso}
            break

    if detected_signal is None:
        print(json.dumps({}))
        return

    # Load session state and append signal
    sp = session_state_path(session_id)
    state: dict = {}
    if sp.exists():
        try:
            state = json.loads(sp.read_text())
        except Exception:
            pass

    signals = state.get("tool_signals", [])
    signals.append(detected_signal)
    state["tool_signals"] = signals[-20:]  # Keep last 20

    try:
        sp.write_text(json.dumps(state, indent=2))
        sp.chmod(0o600)
    except Exception:
        pass

    print(json.dumps({}))


if __name__ == "__main__":
    main()
