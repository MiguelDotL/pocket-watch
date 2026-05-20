#!/usr/bin/env python3
"""Stop hook: the workhorse.

Reads assistant_response from stdin and:
1. Detects estimate phrases (with positive-context regex + self-output guard)
2. Handles revision vs new estimate logic
3. Detects pivot/cancel signals
4. Runs completion-confidence fusion (verbal + tool signals)
5. Accumulates active_minutes per turn
6. Updates session state and JSONL log

Hard limits: 5s wallclock budget, 1 file-append max per fire.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import uuid

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
if _PLUGIN_ROOT:
    sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "scripts"))
else:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def _log_health(success: bool, error: str = "") -> None:
    try:
        from pocket_watch.paths import hook_health_path
        import json as _json

        hp = hook_health_path()
        health: dict = {}
        if hp.exists():
            try:
                health = _json.loads(hp.read_text())
            except Exception:
                health = {}

        entry = health.get("Stop", {"consecutive_failures": 0, "disabled": False})
        if success:
            entry["consecutive_failures"] = 0
            entry["last_success"] = datetime.datetime.utcnow().isoformat() + "Z"
            entry.pop("disabled_reason", None)
        else:
            entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
            entry["last_error"] = error
            if entry["consecutive_failures"] >= 3:
                entry["disabled"] = True
                entry["disabled_reason"] = f"Auto-disabled after 3 failures. Last: {error}"
        health["Stop"] = entry
        hp.write_text(_json.dumps(health, indent=2))
    except Exception:
        pass


def main() -> None:
    if os.environ.get("POCKET_WATCH_DISABLE", "").strip() == "1":
        print(json.dumps({}))
        return

    # Check auto-disable
    try:
        from pocket_watch.paths import hook_health_path
        hp = hook_health_path()
        if hp.exists():
            health = json.loads(hp.read_text())
            if health.get("Stop", {}).get("disabled"):
                print(json.dumps({}))
                return
    except Exception:
        pass

    try:
        _run()
        _log_health(True)
    except Exception as exc:
        _log_health(False, str(exc))
        print(json.dumps({}))


def _project_from_env() -> str:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=2,
        )
        url = result.stdout.strip()
        if url:
            name = url.rstrip("/").split("/")[-1]
            return name.removesuffix(".git") if hasattr(name, "removesuffix") else name.replace(".git", "")
    except Exception:
        pass
    return os.path.basename(os.getcwd()) or "unknown"


def _run() -> None:
    from pocket_watch.parse import (
        extract_estimate, infer_category, is_pivot, has_completion_signal,
        is_self_output,
    )
    from pocket_watch.log import append_entry, read_tail
    from pocket_watch.paths import session_state_path, config_path

    try:
        event = json.loads(sys.stdin.read())
    except Exception:
        event = {}

    assistant_response = event.get("assistant_response", "")
    session_id = os.environ.get("POCKET_WATCH_SESSION_ID", "default")
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    now_dt = datetime.datetime.now(tz=datetime.timezone.utc)

    # Load session state
    sp = session_state_path(session_id)
    state: dict = {
        "session_id": session_id,
        "pw_invocation_in_flight": False,
        "tool_signals": [],
        "open_estimate_id": None,
        "active_minutes_accumulator": 0.0,
        "turn_start_ts": now_iso,
    }
    if sp.exists():
        try:
            state = json.loads(sp.read_text())
        except Exception:
            pass

    # --- Active-time accumulation ---
    turn_start_str = state.get("turn_start_ts", now_iso)
    try:
        turn_start = datetime.datetime.fromisoformat(turn_start_str)
        if turn_start.tzinfo is None:
            turn_start = turn_start.replace(tzinfo=datetime.timezone.utc)
        turn_duration = (now_dt - turn_start).total_seconds() / 60.0
        # Cap at 60 min per turn (sanity bound)
        turn_duration = min(turn_duration, 60.0)
    except Exception:
        turn_duration = 0.0

    accum = state.get("active_minutes_accumulator", 0.0) + max(0.0, turn_duration)
    state["active_minutes_accumulator"] = accum
    state["turn_start_ts"] = now_iso  # reset for next turn

    # --- Self-output guard ---
    if state.get("pw_invocation_in_flight"):
        state["pw_invocation_in_flight"] = False
        # Save state and exit — skip estimate detection this turn
        try:
            sp.write_text(json.dumps(state, indent=2))
            sp.chmod(0o600)
        except Exception:
            pass
        print(json.dumps({}))
        return

    if is_self_output(assistant_response):
        try:
            sp.write_text(json.dumps(state, indent=2))
            sp.chmod(0o600)
        except Exception:
            pass
        print(json.dumps({}))
        return

    # Load config
    config: dict = {"capture_estimates": True, "capture_completions": True}
    if config_path().exists():
        try:
            config.update(json.loads(config_path().read_text()))
        except Exception:
            pass

    # --- Pivot detection (auto-cancel open estimate) ---
    if is_pivot(assistant_response) and state.get("open_estimate_id"):
        eid = state["open_estimate_id"]
        # Read the open entry and write a cancellation
        entries = read_tail(200)
        for entry in reversed(entries):
            if entry.get("id") == eid and entry.get("status") == "open":
                cancel_entry = dict(entry)
                cancel_entry["status"] = "cancelled"
                cancel_entry["completion_signal"] = "pivot"
                cancel_entry["completion_confidence"] = 0.0
                cancel_entry["completed_at"] = now_iso
                cancel_entry["corrected_by"] = "pivot-auto-cancel"
                append_entry(cancel_entry)
                state["open_estimate_id"] = None
                state["active_minutes_accumulator"] = 0.0
                break

        try:
            sp.write_text(json.dumps(state, indent=2))
            sp.chmod(0o600)
        except Exception:
            pass
        print(json.dumps({}))
        return

    # --- Completion fusion (if there's an open estimate) ---
    if config.get("capture_completions", True) and state.get("open_estimate_id"):
        eid = state["open_estimate_id"]
        verbal_done = has_completion_signal(assistant_response)

        # Tool signals: only count those after the estimate was created
        entries_tail = read_tail(200)
        open_entry = None
        for entry in reversed(entries_tail):
            if entry.get("id") == eid and entry.get("status") == "open":
                open_entry = entry
                break

        if open_entry:
            estimated_at_str = open_entry.get("estimated_at", "")
            try:
                estimated_at = datetime.datetime.fromisoformat(estimated_at_str)
                if estimated_at.tzinfo is None:
                    estimated_at = estimated_at.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                estimated_at = None

            # Filter tool signals by timestamp (must be AFTER estimate was created)
            tool_signals = state.get("tool_signals", [])
            valid_tool_signals = []
            if estimated_at:
                for sig in tool_signals:
                    try:
                        sig_ts = datetime.datetime.fromisoformat(sig["ts"])
                        if sig_ts.tzinfo is None:
                            sig_ts = sig_ts.replace(tzinfo=datetime.timezone.utc)
                        if sig_ts > estimated_at:
                            valid_tool_signals.append(sig)
                    except Exception:
                        pass
            has_tool_signal = bool(valid_tool_signals)
            high_tool = any(s.get("strength") == "high" for s in valid_tool_signals)

            # Confidence fusion
            if verbal_done and (has_tool_signal and high_tool):
                confidence = 0.92
                signal_type = "explicit_done"
                new_status = "completed"
            elif verbal_done and has_tool_signal:
                confidence = 0.75
                signal_type = "explicit_done"
                new_status = "tentative"
            elif verbal_done:
                confidence = 0.65
                signal_type = "explicit_done"
                new_status = "tentative"
            elif has_tool_signal and high_tool:
                confidence = 0.70
                signal_type = valid_tool_signals[0]["signal"]
                new_status = "tentative"
            else:
                confidence = None

            if confidence is not None:
                elapsed = None
                started_str = open_entry.get("started_at")
                if started_str:
                    try:
                        started = datetime.datetime.fromisoformat(started_str)
                        if started.tzinfo is None:
                            started = started.replace(tzinfo=datetime.timezone.utc)
                        elapsed = (now_dt - started).total_seconds() / 60.0
                    except Exception:
                        pass

                closed_entry = dict(open_entry)
                closed_entry["status"] = new_status
                closed_entry["completed_at"] = now_iso
                closed_entry["active_minutes"] = round(accum, 1)
                closed_entry["elapsed_minutes"] = round(elapsed, 1) if elapsed else None
                closed_entry["completion_signal"] = signal_type
                closed_entry["completion_confidence"] = round(confidence, 3)
                closed_entry["corrected_by"] = "stop-hook-closure"

                append_entry(closed_entry)
                state["open_estimate_id"] = None
                state["active_minutes_accumulator"] = 0.0
                state["tool_signals"] = []  # Clear used signals

                try:
                    sp.write_text(json.dumps(state, indent=2))
                    sp.chmod(0o600)
                except Exception:
                    pass
                print(json.dumps({}))
                return

    # --- Estimate detection (Claude's response) ---
    if config.get("capture_estimates", True):
        estimate = extract_estimate(assistant_response)
        if estimate:
            category = infer_category(assistant_response)
            project = _project_from_env()
            model = os.environ.get("CLAUDE_MODEL", "unknown")
            entry_id = str(uuid.uuid4())

            corrects_id = state.get("open_estimate_id")

            entry = {
                "id": entry_id,
                "_schema": 1,
                "session_id": session_id,
                "who": "assistant",
                "model": model,
                "project": project,
                "category": category,
                "source": "auto",
                "confidence": 0.85,
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
                "corrects": corrects_id,
            }

            append_entry(entry)
            state["open_estimate_id"] = entry_id
            state["active_minutes_accumulator"] = 0.0

    # Save state
    try:
        sp.write_text(json.dumps(state, indent=2))
        sp.chmod(0o600)
    except Exception:
        pass

    print(json.dumps({}))


if __name__ == "__main__":
    main()
