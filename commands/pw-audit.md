# /pw-audit

Review auto-captured estimates interactively for accuracy.

## Usage

```
/pw-audit
/pw-audit --skip
/pw-audit --accept-all
```

## What it does

Runs `${CLAUDE_PLUGIN_ROOT}/scripts/pw audit` and presents each unaudited completed/tentative estimate for review.

For each entry, shows:
- Category, estimated minutes, actual active minutes
- Status (completed vs tentative)
- Notes (the sentence from which the estimate was captured)
- Entry ID (for use with `/pw-correct`)

Accepts `y` (accept), `n` (flag as inaccurate), or `q` (quit).

Accepted entries are marked `audit_result: "accepted"`.
Flagged entries are marked `audit_result: "rejected"` — excluded from calibration at reduced weight.

## Options

- `--skip` — skip this month's audit without reviewing
- `--accept-all` — bulk-accept all unaudited entries without reviewing individually

## When you're prompted

The monthly audit prompt appears in your session context when:
- ≥ 20 unaudited captures exist (first-ever audit), or
- ≥ 30 days since last audit with ≥ 5 new captures

You can always run `/pw-audit` manually regardless of the prompt schedule.

## Effect on calibration

Audited entries count at full weight. Tentative entries count at 0.5× until audited. Regular audits improve calibration accuracy over time.
