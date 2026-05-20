---
name: pocket-watch
description: Use for current time, dates, scheduling, time estimates for tasks, day/night context, or resuming work after a gap. Triggers on "today/tomorrow/yesterday", "this will take N minutes/hours", "good morning/night", "I'm back", or any task ETA. Also before time-of-day greetings to avoid mismatched replies.
version: 0.1.0
allowed-tools: [Read, Bash]
---

# pocket-watch

## First step on any trigger

Run `${CLAUDE_PLUGIN_ROOT}/scripts/pw now --json` (Bash) to get current time context.

**Cache the result for the current turn** — do not re-run within a single response. Never guess time from prior context or training data; always call `pw now`.

If `pw now` fails entirely, fall back to `date -u +%FT%TZ` and warn the user that timezone detection failed.

The JSON response includes:
- `iso` — current datetime with UTC offset
- `utc_offset` — e.g. `+01:00`
- `iana` — IANA timezone name (e.g. `Europe/London`)
- `day_part` — `early-morning`, `morning`, `midday`, `afternoon`, `evening`, `night`, `late-night`
- `weekday` — short name (Mon–Sun)
- `date` — `YYYY-MM-DD`
- `time_24h`, `time_12h` — formatted local time
- `holiday` — holiday name if today is a recognized holiday, else null
- `streak_minutes` — continuous work time today (from completed estimates)
- `conversational_hints` — `last_greeting`, `last_farewell`, `returned_at`, `last_message_ts`
- `habits_summary` — aggregated work patterns from history
- `tz_warning` (optional) — present if timezone detection fell back to UTC

## Display rule

Never use bare TZ abbreviations (CST, IST, PDT). Always use `Region/City (UTC±HH:MM)`.

Example: `Europe/London (UTC+01:00)` — not `BST`.

## Day-part is descriptive only

Do NOT apply clock-based rules like "it's night, suggest rest." The day-part label is for context only.

**Mirror user cues.** If the user says "good night" at 14:00, respond in kind — they're stepping away. If they say "morning!" at 03:00, match their framing. The user's words take precedence over the clock.

## Conversational inference

Read `conversational_hints` from `pw now` output:

- `last_farewell` set → user stepped away; they're back now; acknowledge the gap naturally
- `returned_at` set → frame the session as a resume; reference how much time has passed if relevant
- `last_greeting` set → they just started; match their energy
- `gap_since_last_message` > 6 hours (compute from `last_message_ts`) → frame as session resume

For relative time expressions:
- "tomorrow" → compute from `date` field (+1 day in the user's local date)
- "yesterday" → `date` field (-1 day)
- "this morning" / "tonight" → anchor to the user's local date from `pw now`

Do not anchor to UTC or training-data time.

## Estimate flow

Before stating a time estimate for a task:

1. Run `${CLAUDE_PLUGIN_ROOT}/scripts/pw stats --category <inferred_category> --json` to get observed data.
2. The response includes: `median`, `n`, `min`, `max`, `confidence_label`.
3. State your estimate informed by this data, in natural language.

Examples:
- `"I estimate ~35 minutes — similar tasks have averaged 28m over the last 12 (warming up)."`
- `"~2 hours. I have 47 similar tasks on record with a median of 105m."`
- `"~30 minutes, though I have no prior history for this category."`

**Do NOT say "I'm multiplying by 1.4x"** — the multiplier is internal to calibration and exposing it undermines the system's integrity. Reference only observed durations.

**Do NOT call `pw estimate` automatically** — the Stop hook logs estimates from your natural-language responses. Only call `pw estimate` when explicitly correcting an entry or preemptively logging before starting.

## Work streak and break suggestions

Use `streak_minutes` from `pw now` for evidence-based suggestions.

Example: `"You've been at this 95 minutes. Want to take a short break, or push through?"`

Do NOT apply clock-based break rules. Do NOT say "it's 10 PM, you should rest" — you don't know when the user typically works. Habits are in `habits_summary.typical_work_hours`.

## Confidence labels

When stating an estimate, include calibration state naturally:
- `"~30 minutes (low confidence — only 3 prior samples)"`
- `"~45 minutes (calibrated from 52 tasks)"`
- `"~1 hour (no history for this category; conservative estimate)"`

The user deserves honesty about how grounded the estimate is.

## Platform fallbacks

If `${CLAUDE_PLUGIN_ROOT}/scripts/pw now --json` fails:
1. Try `date -u +%FT%TZ` for UTC time (warn that local TZ is unknown)
2. Tell the user to set `POCKET_WATCH_TZ=<IANA>` and restart the session
3. Suggest running `/pw-doctor` to diagnose

## Reference docs

- See [references/calibration.md] — only when actively discussing recalibration or the math behind estimates
- See [references/platform-notes.md] — only when debugging a platform-specific timezone issue

Do not load these files speculatively. They are for deep-dive use only.

## Slash commands

Users rarely need these — hooks handle the common path. But if asked:

| Command | Purpose |
|---------|---------|
| `/pw-now` | Inspect current time context |
| `/pw-stats [cat]` | See observed calibration data |
| `/pw-doctor` | Self-diagnostic |
| `/pw-audit` | Review auto-captured estimates |
| `/pw-correct <id> <field> <value>` | Fix an auto-captured entry |
| `/pw-done [minutes] [--status ...]` | Manually close an estimate |
| `/pw-estimate <dur> [--category cat]` | Manually log an estimate |

## Anti-gaming

If the user asks "why did you estimate 30 minutes?": explain you're applying calibration from past tasks, and they can see the underlying data with `/pw-stats`. Do not quote the multiplier.
