# Alpha tester setup

Thanks for trying pocket-watch. This guide walks you through install, a quick smoke test, and what to report back.

## Install

```
/plugin install github.com/MiguelDotL/pocket-watch
```

Start a new Claude Code session after install. The skill loads automatically.

## Smoke test (5 steps, ~10 minutes)

### 1. Confirm time detection
Ask Claude: **"what time is it?"**

Expected: Claude returns the current local time, timezone (IANA name), and day-part. No errors, no clock-skew warnings.

### 2. Confirm estimate capture
Ask Claude to do a small task and watch how it responds: **"add a TODO comment to any file in this repo"** (or similar trivial change).

If Claude says something like "this'll take ~2 minutes," that estimate should silently log to `~/.claude/data/pocket-watch/estimates.jsonl`.

### 3. Confirm completion capture
Let Claude finish the small task. When it says "done" or similar, the estimate entry should auto-close with `active_minutes` populated.

Check with: `/pw-stats`

Expected: a summary line showing the entry was logged.

### 4. Run the doctor
Run: `/pw-doctor`

Expected: a checklist with mostly ✓ marks. Any ✗ marks are useful to report.

### 5. Verify hook health
Look at `~/.claude/data/pocket-watch/hook-health.json` (may not exist if no hooks have failed). If it exists with `disabled_reason` for any hook, that's a bug worth reporting.

## What to report

Use the GitHub issue templates:
- **Bug** — include the output of `/pw-doctor`
- **Platform report** — your OS, Python version, what worked, what didn't
- **Feature** — anything you wished worked differently

## Disable any time

Set `POCKET_WATCH_DISABLE=1` in your environment. All hooks stop firing immediately.

## Known limitations

- Sub-agent work attribution is best-effort
- Multi-task / parallel work is not auto-attributed
- Remote SSH sessions use remote-local time unless `POCKET_WATCH_TZ` is set
- NFS-mounted home directories: file locking unreliable; data may not be safe with concurrent Claude Code instances

## Feedback

If you have suggestions for the README, the install flow, or the smoke test steps, mention them in your bug or feature report.
