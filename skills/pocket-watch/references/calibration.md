# Calibration Math Reference

This document is loaded on demand when actively discussing how pocket-watch recalibrates estimates. Do not load it speculatively.

## Goal

Correct for the well-documented planning fallacy: both humans and LLMs systematically underestimate task duration. pocket-watch measures the ratio of actual active time to estimated time and applies a Bayesian-blended correction.

## Data Used

Only `active_minutes` is used for calibration — not `elapsed_minutes` (wall-clock). Active time accumulates turn-by-turn via the Stop hook, so idle gaps (lunch, meetings) don't distort the result.

Entries used: `status: "completed"` or `status: "tentative"` (at 0.5× weight), not corrected or deleted, `estimate_minutes ≤ 480` (long-running tasks go to a separate bucket).

## Phases

| Phase | Condition | Formula |
|-------|-----------|---------|
| Cold start | n < 5 | `multiplier = 1.3` (prior only) |
| Warmup | 5 ≤ n < 20 | `0.5 × 1.3 + 0.5 × observed` |
| Mature | n ≥ 20 | `0.3 × 1.3 + 0.7 × observed` |

`observed` = trimmed median of `(active_minutes / estimate_minutes)` ratios from the most recent 30 eligible entries (or all entries if fewer than 30).

## Trimmed Median

20% of values trimmed from each end before computing median. This makes the estimate robust against single outliers (e.g., a 10× task that was unexpectedly hard doesn't permanently skew calibration).

With fewer than 5 entries after trimming, the untrimmed median is used.

## Long-Running Bucket

Estimates with `estimate_minutes > 480` (8 hours) are tracked in a separate sub-bucket per category (e.g., `large-refactor:long-running`). They are not blended with short tasks. This prevents a single two-day task from distorting the median for two-hour tasks.

## Recency Window

Only the most recent 30 completed entries are used in the mature phase. This ensures calibration adapts to habit changes over time rather than being anchored to work done months ago.

## Anti-Gaming

The computed multiplier is never serialized or exposed. `pw stats` returns only:
- `median` — observed median active minutes for the category
- `n` — sample count
- `min`, `max` — range
- `confidence_label` — human-readable calibration state

Claude reasons from the observed data naturally ("similar tasks have averaged X minutes"). The multiplier is an internal implementation detail.

## Non-Completion Handling

Entries with `status: "cancelled"`, `"scope-changed"`, or `"deleted"` are excluded from calibration entirely. They stay in the log for audit purposes.

## Per-Who and Per-Model

The schema includes `who` (user/assistant) and `model` fields. In v0.1.0, calibration blends across both. Future versions may segment by `who` or `model` if the signal warrants it.

## Self-Amplification Risk

If Claude could read its own log and see that it underestimates by 1.4×, it might anchor on that and strategically adjust estimates to game calibration toward 1.0×. The multiplier-hiding design prevents this feedback loop.

The only information Claude sees is observed durations — the same data a human would see in a project retrospective.
