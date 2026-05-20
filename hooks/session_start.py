#!/usr/bin/env python3
"""SessionStart hook: context priming, habit refresh, first-run welcome,
stale-open warnings, monthly audit invitation, hook health alerts.

Outputs hookSpecificOutput.additionalContext to stdout (JSON).
Fails silently on any error.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import uuid

# Ensure scripts/ is on sys.path
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
if _PLUGIN_ROOT:
    sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "scripts"))
else:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def _emit(output: dict) -> None:
    """Write hook output to stdout."""
    print(json.dumps(output))


def _log_health(hook_name: str, success: bool, error: str = "") -> None:
    """Update hook-health.json with result."""
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

        entry = health.get(hook_name, {"consecutive_failures": 0, "disabled": False})
        if success:
            entry["consecutive_failures"] = 0
            entry["last_success"] = datetime.datetime.utcnow().isoformat() + "Z"
            entry.pop("disabled_reason", None)
        else:
            entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
            entry["last_error"] = error
            if entry["consecutive_failures"] >= 3:
                entry["disabled"] = True
                entry["disabled_reason"] = f"Auto-disabled after 3 consecutive failures. Last: {error}"

        health[hook_name] = entry
        hp.write_text(_json.dumps(health, indent=2))
    except Exception:
        pass


def main() -> None:
    # Kill switch
    if os.environ.get("POCKET_WATCH_DISABLE", "").strip() == "1":
        _emit({})
        return

    try:
        _run()
        _log_health("SessionStart", True)
    except Exception as exc:
        _log_health("SessionStart", False, str(exc))
        _emit({})


def _run() -> None:
    from pocket_watch import learn
    from pocket_watch.paths import (
        config_path, data_dir, estimates_path, first_run_flag_path,
        hook_health_path, session_state_path,
    )
    from pocket_watch.log import read_all, append_entry

    import json as _json

    # Read hook event from stdin
    try:
        event = _json.loads(sys.stdin.read())
    except Exception:
        event = {}

    source = event.get("source", "startup")  # startup|clear|resume|compact

    # Determine session_id
    if source in ("startup", "clear"):
        session_id = str(uuid.uuid4())
    else:
        # Try to preserve from previous session-state
        # Look for most recent session-state file
        dd = data_dir()
        existing_states = sorted(dd.glob("session-state-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if existing_states:
            try:
                prev = _json.loads(existing_states[0].read_text())
                session_id = prev.get("session_id", str(uuid.uuid4()))
            except Exception:
                session_id = str(uuid.uuid4())
        else:
            session_id = str(uuid.uuid4())

    # Persist session_id in env and state
    os.environ["POCKET_WATCH_SESSION_ID"] = session_id
    state_path = session_state_path(session_id)
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    state: dict = {
        "session_id": session_id,
        "started_at": now_iso,
        "source": source,
        "pw_invocation_in_flight": False,
        "tool_signals": [],
        "conversational_hints": {},
        "open_estimate_id": None,
        "active_minutes_accumulator": 0.0,
        "turn_start_ts": now_iso,
    }

    # Load existing state if resuming
    if source in ("resume", "compact") and state_path.exists():
        try:
            prev_state = _json.loads(state_path.read_text())
            state.update({
                "open_estimate_id": prev_state.get("open_estimate_id"),
                "active_minutes_accumulator": prev_state.get("active_minutes_accumulator", 0.0),
                "conversational_hints": prev_state.get("conversational_hints", {}),
            })
        except Exception:
            pass

    state_path.write_text(_json.dumps(state, indent=2))
    state_path.chmod(0o600)

    # Refresh habits if stale
    learn.refresh_if_stale()

    # Load config
    config: dict = {
        "capture_estimates": True,
        "capture_completions": True,
        "infer_habits": True,
        "surface_habits_in_pw_now": True,
        "monthly_audit_enabled": True,
        "first_monthly_audit_shown": False,
        "auto_cancel_after_days": 14,
    }
    if config_path().exists():
        try:
            config.update(_json.loads(config_path().read_text()))
        except Exception:
            pass

    context_parts: list[str] = []

    # First-run welcome
    flag_path = first_run_flag_path()
    if not flag_path.exists():
        context_parts.append(
            "pocket-watch is now active. It silently observes time estimates and completions "
            "in this session to calibrate future predictions. All data is stored locally at "
            "~/.claude/data/pocket-watch/ (chmod 0600). Disable any time: set POCKET_WATCH_DISABLE=1. "
            "Run /pw-doctor for diagnostic. Full privacy + config docs: README."
        )
        flag_path.touch()
        flag_path.chmod(0o600)

    # Stale-open estimate warnings + auto-cancel
    if estimates_path().exists():
        entries = read_all()
        auto_cancel_days = config.get("auto_cancel_after_days", 14)
        now_dt = datetime.datetime.now(tz=datetime.timezone.utc)

        for entry in entries:
            if entry.get("status") != "open":
                continue
            eid = entry.get("id", "?")
            estimated_at_str = entry.get("estimated_at", "")
            try:
                estimated_at = datetime.datetime.fromisoformat(estimated_at_str)
            except Exception:
                continue

            if estimated_at.tzinfo is None:
                estimated_at = estimated_at.replace(tzinfo=datetime.timezone.utc)

            age = now_dt - estimated_at
            age_days = age.total_seconds() / 86400

            if age_days > auto_cancel_days:
                # Auto-cancel stale estimate
                cancel_entry = dict(entry)
                cancel_entry["status"] = "cancelled"
                cancel_entry["completion_signal"] = "stale"
                cancel_entry["corrected_by"] = "auto-cancel"
                cancel_entry["notes"] = f"Auto-cancelled after {auto_cancel_days}d"
                append_entry(cancel_entry)
            elif age.total_seconds() > 8 * 3600:
                # Warn about stale open estimate
                age_desc = f"{int(age_days)}d" if age_days >= 1 else f"{int(age.total_seconds() / 3600)}h"
                notes = entry.get("notes", entry.get("category", "estimate"))
                est = entry.get("estimate_minutes", "?")
                context_parts.append(
                    f"Open estimate from {age_desc} ago: '{notes}' ({est}m est, {age_desc} old). "
                    f"Still relevant? /pw-correct {eid} status completed  or  /pw-done"
                )

    # CompACT resume: surface open estimate context
    if source in ("resume", "compact") and state.get("open_estimate_id"):
        eid = state["open_estimate_id"]
        accum = state.get("active_minutes_accumulator", 0.0)
        context_parts.append(
            f"Continuing open estimate (session resumed). "
            f"Elapsed active time so far: ~{int(accum)}m. "
            f"Run /pw-done when finished."
        )

    # Monthly audit invitation
    if config.get("monthly_audit_enabled", True):
        entries_for_audit = []
        if estimates_path().exists():
            entries_for_audit = read_all()
        unaudited = [e for e in entries_for_audit if not e.get("audited_at") and e.get("status") in ("completed", "tentative")]

        should_prompt = False
        if not config.get("first_monthly_audit_shown") and len(unaudited) >= 20:
            should_prompt = True
        elif config.get("first_monthly_audit_shown"):
            last_prompt_str = config.get("last_audit_prompt_at", "")
            if last_prompt_str:
                try:
                    last_prompt = datetime.datetime.fromisoformat(last_prompt_str)
                    if last_prompt.tzinfo is None:
                        last_prompt = last_prompt.replace(tzinfo=datetime.timezone.utc)
                    days_since = (now_dt - last_prompt).total_seconds() / 86400
                    if days_since >= 30 and len(unaudited) >= 5:
                        should_prompt = True
                except Exception:
                    pass
            else:
                if len(unaudited) >= 20:
                    should_prompt = True

        if should_prompt:
            context_parts.append(
                f"Monthly audit ready — {len(unaudited)} auto-captured estimates to review "
                f"for accuracy. Run /pw-audit to start."
            )
            # Update config
            config["last_audit_prompt_at"] = now_iso
            if not config.get("first_monthly_audit_shown"):
                config["first_monthly_audit_shown"] = True
            try:
                config_path().write_text(_json.dumps(config, indent=2))
            except Exception:
                pass

    # Hook health warnings
    hp = hook_health_path()
    if hp.exists():
        try:
            health = _json.loads(hp.read_text())
            for hook_name, hdata in health.items():
                if hdata.get("disabled"):
                    context_parts.append(
                        f"Hook '{hook_name}' is auto-disabled (3 consecutive failures). "
                        f"Run: pw doctor --enable-hooks  to re-enable."
                    )
        except Exception:
            pass

    if context_parts:
        additional_context = "\n\n".join(context_parts)
        _emit({"hookSpecificOutput": {"additionalContext": additional_context}})
    else:
        _emit({})


if __name__ == "__main__":
    main()
