"""Estimate calibration: Bayesian-blended trimmed-median multiplier.

Phases:
  cold    (n < 5):   return prior (1.3)
  warmup  (5 <= n < 20): 50/50 prior / observed trimmed median
  mature  (n >= 20): 30/70 prior / observed trimmed median

Long-running tasks (estimate > 480 min) are bucketed separately within
each category to avoid skewing short-task calibration.

Multiplier is computed internally and never serialized to the stats output;
Claude only sees observed duration data (median, n, min, max).
"""

from __future__ import annotations

import statistics

PRIOR = 1.3  # LLM/planning-fallacy bias prior
LONG_RUNNING_THRESHOLD = 480  # minutes — separate bucket above this


def _trimmed_median(values: list[float], trim_fraction: float = 0.2) -> float:
    """Compute median of sorted values after trimming trim_fraction from each end."""
    n = len(values)
    if n == 0:
        return 0.0
    trim = max(1, int(n * trim_fraction))
    if 2 * trim >= n:
        # Can't trim — just take the median of the full set
        return statistics.median(values)
    trimmed = sorted(values)[trim:-trim]
    return statistics.median(trimmed)


def _completion_weight(entry: dict) -> float:
    """Return a calibration weight for an entry based on completion confidence."""
    status = entry.get("status", "")
    if status == "completed":
        return entry.get("completion_confidence", 1.0) or 1.0
    if status == "tentative":
        return 0.5
    return 0.0


def _eligible_entries(history: list[dict], category: str) -> list[dict]:
    """Return completed/tentative entries for a category, excluding long-running."""
    return [
        e for e in history
        if e.get("category") == category
        and e.get("status") in ("completed", "tentative")
        and e.get("active_minutes") is not None
        and e.get("estimate_minutes") is not None
        and e.get("estimate_minutes", 0) > 0
        and e.get("estimate_minutes", 0) <= LONG_RUNNING_THRESHOLD
        # Exclude entries marked deleted or corrected
        and e.get("status") != "deleted"
        and not e.get("corrected_by")
    ]


def _eligible_long_running(history: list[dict], category: str) -> list[dict]:
    """Return entries with estimate_minutes > LONG_RUNNING_THRESHOLD."""
    return [
        e for e in history
        if e.get("category") == category
        and e.get("status") in ("completed", "tentative")
        and e.get("active_minutes") is not None
        and e.get("estimate_minutes") is not None
        and e.get("estimate_minutes", 0) > LONG_RUNNING_THRESHOLD
        and not e.get("corrected_by")
    ]


def calibrated_multiplier(category: str, history: list[dict]) -> float:
    """Return the calibrated multiplier for a category.

    This value is internal — never exposed to Claude's context.
    """
    entries = _eligible_entries(history, category)
    n = len(entries)

    if n < 5:
        return PRIOR

    # Use most recent 30 for mature phase
    recent = entries[-30:] if n >= 20 else entries

    ratios = sorted(
        e["active_minutes"] / e["estimate_minutes"]
        for e in recent
        if e["active_minutes"] > 0
    )

    if not ratios:
        return PRIOR

    observed = _trimmed_median(ratios)

    if n < 20:
        return 0.5 * PRIOR + 0.5 * observed
    else:
        return 0.3 * PRIOR + 0.7 * observed


def calibrated_estimate(base_minutes: float, category: str, history: list[dict]) -> float:
    """Return calibrated estimate in minutes (multiplier applied internally)."""
    multiplier = calibrated_multiplier(category, history)
    return base_minutes * multiplier


def stats_for_category(category: str, history: list[dict]) -> dict:
    """Return observed stats for a category (no multiplier — anti-gaming).

    Returns dict with: median, n, min, max, confidence_label
    """
    entries = _eligible_entries(history, category)
    n = len(entries)

    if n == 0:
        return {
            "category": category,
            "n": 0,
            "median": None,
            "min": None,
            "max": None,
            "confidence_label": "no history",
        }

    actuals = [e["active_minutes"] for e in entries if e["active_minutes"] > 0]

    if not actuals:
        return {
            "category": category,
            "n": n,
            "median": None,
            "min": None,
            "max": None,
            "confidence_label": "no completed data",
        }

    median_val = statistics.median(actuals)
    min_val = min(actuals)
    max_val = max(actuals)

    if n < 5:
        confidence = f"n={n}, prior only"
    elif n < 20:
        confidence = f"n={n}, warming up"
    else:
        confidence = f"n={n}, calibrated"

    return {
        "category": category,
        "n": n,
        "median": round(median_val, 1),
        "min": round(min_val, 1),
        "max": round(max_val, 1),
        "confidence_label": confidence,
    }


def all_stats(history: list[dict]) -> list[dict]:
    """Return stats for all categories that have data."""
    categories = set(
        e.get("category", "uncategorized")
        for e in history
        if e.get("status") in ("completed", "tentative")
    )
    return [stats_for_category(cat, history) for cat in sorted(categories)]
