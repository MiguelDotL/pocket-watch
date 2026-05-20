# /pw-doctor

Run pocket-watch self-diagnostic to identify configuration or environment issues.

## Usage

```
/pw-doctor
/pw-doctor --enable-hooks
```

## What it does

Runs `${CLAUDE_PLUGIN_ROOT}/scripts/pw doctor [--enable-hooks]` and reports:

- Python version (≥ 3.9 required)
- `zoneinfo` module availability and tzdata freshness
- IANA timezone detection result (which fallback step succeeded)
- Data directory writability and path
- `estimates.jsonl` presence and schema version
- Hook health (consecutive failures, auto-disabled status)
- `pw` binary namespace collision check

Each check prints ✓ (pass) or ✗ (fail) with a remediation hint.

## `--enable-hooks`

Resets any auto-disabled hooks. Use this after fixing the underlying issue that caused the hook failures.

## When to use

- First thing when something seems off ("why isn't Claude mentioning time?")
- When a hook has auto-disabled (you'll see a warning in the session context)
- When filing a bug report — include the `pw doctor` output
- Issue templates require `pw doctor` output

## Example output

```
pocket-watch doctor

  ✓ Python ≥ 3.9: 3.12.3
  ✓ zoneinfo available: available
  ✓ IANA timezone detected: Europe/London
  ✓ Data dir writable: ~/.claude/data/pocket-watch/
  ✓ estimates.jsonl exists: Will be created on first estimate
  ✓ Hook Stop: ok (failures: 0)
  ✓ pw namespace: No collision found

All checks passed.
```
