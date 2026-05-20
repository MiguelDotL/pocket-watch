# /pw-done

Manually close an open estimate.

## Usage

```
/pw-done
/pw-done <active_minutes>
/pw-done --status cancelled|merged|scope-changed
```

## What it does

Runs `${CLAUDE_PLUGIN_ROOT}/scripts/pw done [<active_minutes>] [--status ...]`.

Closes the most recent open estimate entry. If `active_minutes` is omitted, pocket-watch computes the wall-clock elapsed time from `started_at` to now (which may include idle time — if you want precise active time, provide it explicitly).

## Status values

- `completed` (default) — work is done as scoped
- `cancelled` — abandoned; excluded from calibration
- `merged` — completed and merged to a branch
- `scope-changed` — task changed significantly mid-stream; excluded from calibration

## When to use

The Stop hook closes estimates automatically when it detects high-confidence completion signals ("done", "merged", ✅ + tool signals). Use `/pw-done` to:

- Manually close an estimate the hook missed
- Set a precise active time (e.g., you stepped away for an hour and want to exclude idle)
- Close with a non-completion status (`cancelled`, `scope-changed`)
- Override a tentative auto-close

## Example

```
/pw-done 45
/pw-done --status cancelled
/pw-done 90 --status merged
```
