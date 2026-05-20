# /pw-estimate

Manually log a time estimate.

## Usage

```
/pw-estimate <duration> [--category <cat>] [--note <text>]
```

## What it does

Runs `${CLAUDE_PLUGIN_ROOT}/scripts/pw estimate <duration> [--category <cat>] [--note <text>]`.

Logs an estimate with `who: "user"` and `source: "manual"`. The Stop hook normally auto-captures estimates from Claude's responses — use this command to preemptively log an estimate before starting work, or to record one the hook missed.

## Duration formats

| Input | Minutes |
|-------|---------|
| `30m` | 30 |
| `1h` | 60 |
| `1h30m` | 90 |
| `2.5h` | 150 |
| `1d` | 480 (8h workday) |

## Categories

`small-fix`, `medium-feature`, `large-refactor`, `deployment`, `testing`, `research`

Free-form categories are also accepted and tracked separately.

## Example

```
/pw-estimate 45m --category medium-feature --note "add OAuth login"
/pw-estimate 2h large-refactor
```

## When to use

- You're starting a task and want to log your prediction before asking Claude
- The auto-capture missed an estimate (e.g., it was in a code block)
- You want to force a category that the auto-infer got wrong
