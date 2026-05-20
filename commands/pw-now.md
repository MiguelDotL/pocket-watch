# /pw-now

Show current local time, timezone, day-part, and habit summary.

## Usage

```
/pw-now
```

## What it does

Runs `${CLAUDE_PLUGIN_ROOT}/scripts/pw now --json` and presents:

- Current local time (24h and 12h) with IANA timezone and UTC offset
- Day-part label (morning, afternoon, evening, etc.)
- Active work streak (minutes of continuous work today)
- Holiday if applicable
- Habit summary: typical work hours, session length
- Any active timezone detection warnings

## When to use

- Check what time pocket-watch thinks it is (debugging timezone detection)
- Verify IANA zone is correct before relying on time-aware Claude responses
- Confirm the system clock is reasonable

## Example output

```
2024-06-15 22:30 (10:30 PM) Europe/London (+01:00) · Sat night · streak 47min
```

With `--json`:

```json
{
  "iso": "2024-06-15T22:30:00+01:00",
  "utc_offset": "+01:00",
  "iana": "Europe/London",
  "day_part": "night",
  "weekday": "Sat",
  "date": "2024-06-15",
  "time_24h": "22:30",
  "time_12h": "10:30 PM",
  "holiday": null,
  "streak_minutes": 47
}
```

## Escape hatch

If timezone detection is wrong, set `POCKET_WATCH_TZ=America/Chicago` (or your IANA zone) in your environment before starting Claude Code.
