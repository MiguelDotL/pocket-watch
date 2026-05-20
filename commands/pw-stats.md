# /pw-stats

Show observed calibration data per task category.

## Usage

```
/pw-stats
/pw-stats [category]
```

## What it does

Runs `${CLAUDE_PLUGIN_ROOT}/scripts/pw stats [--category <cat>] --json` and presents a summary of completed task durations.

For each category with data, shows:

- **median** active minutes across completed tasks
- **range** (min–max) of actual durations
- **n** (sample count) and calibration confidence label

Confidence labels:
- `n=0, prior only` — no history; pocket-watch uses a conservative prior
- `n=N, warming up` — small sample; blends prior with observed data
- `n=N, calibrated` — sufficient history; dominated by observed data

## When to use

- Before stating a time estimate, to ground the estimate in your actual task history
- After completing several tasks, to see if your estimates are improving
- To understand how accurate Claude's estimates have been for a given category

## Note

The calibration multiplier is internal — it is never shown directly. This avoids self-referential anchoring. Claude reasons from the observed data naturally.

## Categories

`small-fix`, `medium-feature`, `large-refactor`, `deployment`, `testing`, `research`, `uncategorized`

User-corrected categories are also tracked separately.
