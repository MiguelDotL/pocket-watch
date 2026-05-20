# pocket-watch

**Temporal awareness and estimate calibration for Claude Code.**

> ⚠️ Pre-release — breaking changes possible. Stable API at v1.0.0.

Claude has no first-class sense of your local time. This causes:

- "Get some rest" suggestions in the middle of the afternoon
- "Good morning" greetings at midnight
- Time estimates that are half of what tasks actually take (planning fallacy + LLM optimism)
- Losing temporal context when resuming work after a gap

pocket-watch gives Claude:
1. **Temporal awareness** — your current local time, timezone, day-part, and calendar context
2. **Conversational time inference** — recognizes "good night," "I'm back," "tomorrow" to frame responses correctly
3. **Estimate calibration** — logs estimates and actual durations, recalibrates future predictions against your history

---

## Privacy

**pocket-watch transmits zero data off-device. It makes no network connections of any kind.**

All time and timezone data comes from your local system clock. All estimate history is stored on disk in `~/.claude/data/pocket-watch/` (permissions: `chmod 0600`). Nothing leaves your machine.

To disable: `export POCKET_WATCH_DISABLE=1` (disables all hooks immediately).

To delete all data: `rm -rf ~/.claude/data/pocket-watch/`

---

## Install

```
/plugin install github.com/MiguelDotL/pocket-watch
```

That's it. The skill activates automatically on the next session start.

---

## Quick Start

1. **Check time awareness:** Ask Claude "what time is it?" — Claude will consult pocket-watch and respond with your local time.

2. **Give an estimate:** Say "this refactor will take about 45 minutes." — pocket-watch's Stop hook auto-logs it silently.

3. **Finish a task:** When Claude says "done" or you complete work, the hook detects it and closes the estimate.

4. **See your history:** Run `/pw-stats` to see observed task durations by category.

5. **Diagnose issues:** Run `/pw-doctor` to verify everything is working.

---

## How It Works

### Skill (passive)

The `pocket-watch` skill activates when the conversation involves time, estimates, greetings, or resuming work. It calls `pw now` to get your current time context and `pw stats` to ground estimates in your history.

### Hooks (automatic)

Five hooks run silently in the background:

| Hook | Purpose |
|------|---------|
| SessionStart | Injects time context; surfaces stale estimates and health warnings |
| UserPromptSubmit | Detects estimates in your messages; captures "good night", "I'm back" |
| PostToolUse | Detects tool-pattern completion signals (PR created, tests passed) |
| Stop | Detects estimates in Claude's responses; auto-closes on completion |
| PreCompact | Preserves open estimate state across `/compact` |

Hooks fail silently. After 3 consecutive failures, a hook auto-disables; `/pw-doctor --enable-hooks` re-enables it.

### Slash Commands (power user)

| Command | Purpose |
|---------|---------|
| `/pw-now` | Inspect current time context |
| `/pw-stats [cat]` | Observed durations per category |
| `/pw-doctor` | Self-diagnostic |
| `/pw-audit` | Review auto-captured estimates |
| `/pw-correct <id> <field> <value>` | Fix an auto-captured entry |
| `/pw-done [minutes]` | Manually close an estimate |
| `/pw-estimate <dur> [--category cat]` | Manually log an estimate |

---

## Calibration

pocket-watch tracks the ratio of actual active time to estimated time across completed tasks. It applies a Bayesian-blended correction:

- **Cold start (n < 5):** uses a conservative 1.3× prior (the well-documented LLM optimism bias)
- **Warming up (5–19):** 50/50 blend of prior and observed data
- **Calibrated (≥ 20):** 70% observed data, 30% prior

The multiplier is **never shown to Claude** — only observed durations (median, range, n) are surfaced. This prevents the model from gaming its own calibration.

Active time only counts turns where Claude and the user are actively working — idle time between turns doesn't accumulate. Lunch breaks and meetings don't inflate your "actual" durations.

---

## Configuration

All config lives in `~/.claude/data/pocket-watch/config.json`:

```json
{
  "capture_estimates": true,
  "capture_completions": true,
  "infer_habits": true,
  "surface_habits_in_pw_now": true,
  "monthly_audit_enabled": true,
  "auto_cancel_after_days": 14
}
```

**Environment variables:**

| Variable | Effect |
|----------|--------|
| `POCKET_WATCH_DISABLE=1` | Disables all hooks immediately |
| `POCKET_WATCH_TZ=<IANA>` | Override timezone detection (e.g. `America/Chicago`) |

---

## Platform Support

| Platform | Status |
|----------|--------|
| macOS | Verified |
| Linux (Ubuntu, Fedora) | Alpha — contributors wanted |
| WSL | Alpha — contributors wanted |
| Windows | Alpha — contributors wanted |

If timezone detection fails, set `POCKET_WATCH_TZ=<your IANA name>` (e.g. `America/New_York`, `Europe/London`) and restart Claude Code.

---

## Troubleshooting

**Timezone shows as UTC when it shouldn't:**
Run `/pw-doctor` to see which detection step ran. Set `POCKET_WATCH_TZ=<IANA>` as a workaround.

**Hook auto-disabled:**
You'll see a warning in the session context. Run `/pw-doctor --enable-hooks` to re-enable after fixing the underlying issue.

**No estimates being captured:**
Verify `POCKET_WATCH_DISABLE` is not set. Check that estimates contain future-tense context ("will take", "should take", "about", "roughly"). Estimates inside code blocks are intentionally skipped.

**Clock seems wrong:**
pocket-watch trusts the OS system clock (NTP-synced on online machines). If your system clock is wrong, run `timedatectl set-ntp true` (Linux) or check Date & Time in System Settings (macOS).

---

## Uninstalling

Uninstalling pocket-watch does **not** delete your estimate history. Your data is preserved at `~/.claude/data/pocket-watch/` in case of reinstall.

To fully remove: `rm -rf ~/.claude/data/pocket-watch/`

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, testing, and PR process.

Issues: please include `/pw-doctor` output in bug reports. Issue templates pre-fill the required fields.

---

## License

MIT — see [LICENSE](LICENSE).
