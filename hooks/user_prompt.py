#!/usr/bin/env python3
"""UserPromptSubmit hook: scan user's message for estimates and conversational cues.

- Logs estimates with who="user"
- Detects greetings/farewells and updates conversational_hints in session-state
- Sets pw_invocation_in_flight flag if user typed a /pw-* command
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
import uuid

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
if _PLUGIN_ROOT:
    sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "scripts"))
else:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

# Conversational cue patterns
_GREETING_RE = re.compile(r"\b(?:good\s+morning|morning|good\s+evening|good\s+night|goodnight|hey|hello|hi)\b", re.IGNORECASE)
_FAREWELL_RE = re.compile(r"\b(?:good\s+night|goodnight|signing\s+off|bye|goodbye|later|logging\s+off|wrapping\s+up)\b", re.IGNORECASE)
_BACK_RE = re.compile(r"\b(?:i[''']?m\s+back|back\s+again|returned|resuming)\b", re.IGNORECASE)
_PW_INVOCATION_RE = re.compile(r"/pw-\w+")

# Project detection from git remote or cwd
def _detect_project() -> str:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=2
        )
        url = result.stdout.strip()
        if url:
            name = url.rstrip("/").split("/")[-1]
            return name.removesuffix(".git") if hasattr(name, "removesuffix") else name.replace(".git", "")
    except Exception:
        pass
    return os.path.basename(os.getcwd()) or "unknown"


def main() -> None:
    if os.environ.get("POCKET_WATCH_DISABLE", "").strip() == "1":
        print(json.dumps({}))
        return

    try:
        _run()
    except Exception:
        print(json.dumps({}))


def _run() -> None:
    from pocket_watch.parse import extract_estimate, infer_category, is_self_output
    from pocket_watch.log import append_entry
    from pocket_watch.paths import session_state_path, config_path

    try:
        event = json.loads(sys.stdin.read())
    except Exception:
        event = {}

    user_text = event.get("prompt", "")
    session_id = os.environ.get("POCKET_WATCH_SESSION_ID", "default")

    # Load session state
    sp = session_state_path(session_id)
    state: dict = {}
    if sp.exists():
        try:
            state = json.loads(sp.read_text())
        except Exception:
            pass

    # Update turn_start_ts for active-time accumulation
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    state["turn_start_ts"] = now_iso

    # Check for /pw-* invocation (self-output guard)
    if _PW_INVOCATION_RE.search(user_text):
        state["pw_invocation_in_flight"] = True

    # Conversational cues
    hints = state.get("conversational_hints", {})
    if _GREETING_RE.search(user_text):
        hints["last_greeting"] = now_iso
    if _FAREWELL_RE.search(user_text):
        hints["last_farewell"] = now_iso
    if _BACK_RE.search(user_text):
        hints["returned_at"] = now_iso
    hints["last_message_ts"] = now_iso
    state["conversational_hints"] = hints

    # Load config
    config: dict = {"capture_estimates": True}
    if config_path().exists():
        try:
            config.update(json.loads(config_path().read_text()))
        except Exception:
            pass

    # Estimate detection (user side)
    if config.get("capture_estimates", True) and not is_self_output(user_text):
        estimate = extract_estimate(user_text)
        if estimate:
            category = infer_category(user_text)
            project = _detect_project()
            model = os.environ.get("CLAUDE_MODEL", "unknown")
            entry_id = str(uuid.uuid4())

            entry = {
                "id": entry_id,
                "_schema": 1,
                "session_id": session_id,
                "who": "user",
                "model": model,
                "project": project,
                "category": category,
                "source": "auto",
                "confidence": 0.7,  # users hedge; lower default
                "estimated_at": now_iso,
                "estimate_minutes": round(estimate["minutes"], 1),
                "started_at": now_iso,
                "completed_at": None,
                "active_minutes": None,
                "elapsed_minutes": None,
                "completion_signal": None,
                "completion_confidence": 0.0,
                "status": "open",
                "notes": estimate.get("sentence", "")[:200],
                "audited_at": None,
                "audit_result": None,
                "corrected_by": None,
                "corrects": state.get("open_estimate_id"),
            }

            if state.get("open_estimate_id"):
                # This is a revision
                entry["corrects"] = state["open_estimate_id"]

            append_entry(entry)
            state["open_estimate_id"] = entry_id
            state["active_minutes_accumulator"] = 0.0

    # Save updated state
    try:
        sp.write_text(json.dumps(state, indent=2))
        sp.chmod(0o600)
    except Exception:
        pass

    print(json.dumps({}))


if __name__ == "__main__":
    main()
