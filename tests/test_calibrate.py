"""Tests for calibrate.py: cold/warmup/mature phases, outliers, categories."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from pocket_watch.calibrate import (
    PRIOR,
    _trimmed_median,
    calibrated_multiplier,
    calibrated_estimate,
    stats_for_category,
    all_stats,
)


def _make_entry(estimate_minutes: float, active_minutes: float,
                category: str = "small-fix", status: str = "completed",
                entry_id: str = None) -> dict:
    """Create a minimal log entry dict."""
    import uuid
    return {
        "id": str(uuid.uuid4()) if entry_id is None else entry_id,
        "_schema": 1,
        "category": category,
        "status": status,
        "estimate_minutes": estimate_minutes,
        "active_minutes": active_minutes,
        "corrected_by": None,
    }


# ---------------------------------------------------------------------------
# Trimmed median
# ---------------------------------------------------------------------------

def test_trimmed_median_simple() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    # 20% trim → trim=1 from each end → [2, 3, 4] → median = 3
    assert _trimmed_median(values) == pytest.approx(3.0)


def test_trimmed_median_empty() -> None:
    assert _trimmed_median([]) == 0.0


def test_trimmed_median_single() -> None:
    assert _trimmed_median([5.0]) == 5.0


def test_trimmed_median_outlier_resistant() -> None:
    """A 10× outlier should not dominate the trimmed median."""
    values = [1.0, 1.1, 1.0, 1.2, 1.0, 1.1, 10.0]  # outlier at end
    result = _trimmed_median(values)
    assert result < 2.0, f"Outlier not trimmed: {result}"


# ---------------------------------------------------------------------------
# Cold start (n < 5)
# ---------------------------------------------------------------------------

def test_cold_start_empty() -> None:
    multiplier = calibrated_multiplier("small-fix", [])
    assert multiplier == PRIOR


def test_cold_start_few_entries() -> None:
    history = [_make_entry(30, 40) for _ in range(4)]
    multiplier = calibrated_multiplier("small-fix", history)
    assert multiplier == PRIOR


def test_cold_start_different_category() -> None:
    """Entries in a different category don't count."""
    history = [_make_entry(30, 40, category="deployment") for _ in range(20)]
    multiplier = calibrated_multiplier("small-fix", history)
    assert multiplier == PRIOR  # no history for small-fix


# ---------------------------------------------------------------------------
# Warmup phase (5 ≤ n < 20)
# ---------------------------------------------------------------------------

def test_warmup_blends_prior_and_observed() -> None:
    """With n=10 entries each taking 2× estimated, result should blend prior and 2.0."""
    history = [_make_entry(30, 60) for _ in range(10)]  # ratio = 2.0
    multiplier = calibrated_multiplier("small-fix", history)
    expected = 0.5 * PRIOR + 0.5 * 2.0
    assert multiplier == pytest.approx(expected, rel=0.05)


def test_warmup_accurate_estimator() -> None:
    """User who estimates perfectly (ratio=1.0) should get blend toward 1.0."""
    history = [_make_entry(30, 30) for _ in range(10)]  # ratio = 1.0
    multiplier = calibrated_multiplier("small-fix", history)
    expected = 0.5 * PRIOR + 0.5 * 1.0
    assert multiplier == pytest.approx(expected, rel=0.05)


# ---------------------------------------------------------------------------
# Mature phase (n ≥ 20)
# ---------------------------------------------------------------------------

def test_mature_trusts_data_more() -> None:
    """With n=30 entries at ratio=1.5, mature phase weights data 70%."""
    history = [_make_entry(30, 45) for _ in range(30)]  # ratio = 1.5
    multiplier = calibrated_multiplier("small-fix", history)
    expected = 0.3 * PRIOR + 0.7 * 1.5
    assert multiplier == pytest.approx(expected, rel=0.05)


def test_mature_with_outlier() -> None:
    """Single 10× outlier should not dominate mature-phase calibration."""
    history = [_make_entry(30, 45) for _ in range(29)]  # ratio = 1.5
    history.append(_make_entry(30, 300))  # ratio = 10.0 (outlier)
    multiplier = calibrated_multiplier("small-fix", history)
    # Should be close to mature with 1.5 ratio, not wildly off
    assert multiplier < 3.0, f"Outlier dominated: {multiplier}"


def test_mature_uses_recent_window() -> None:
    """Mature phase uses last 30 entries — old data with high ratios shouldn't dominate."""
    # 50 old entries with ratio=3.0
    old_history = [_make_entry(30, 90) for _ in range(50)]
    # 30 recent entries with ratio=1.0
    recent_history = [_make_entry(30, 30) for _ in range(30)]
    history = old_history + recent_history

    multiplier = calibrated_multiplier("small-fix", history)
    # Should be closer to 1.0 (recent) than 3.0 (old)
    expected_mature = 0.3 * PRIOR + 0.7 * 1.0
    assert multiplier == pytest.approx(expected_mature, rel=0.1)


# ---------------------------------------------------------------------------
# Calibrated estimate
# ---------------------------------------------------------------------------

def test_calibrated_estimate_cold_start() -> None:
    estimate = calibrated_estimate(30.0, "small-fix", [])
    assert estimate == pytest.approx(30.0 * PRIOR)


def test_calibrated_estimate_mature() -> None:
    history = [_make_entry(30, 30) for _ in range(30)]  # ratio=1.0
    estimate = calibrated_estimate(30.0, "small-fix", history)
    # Should be close to 30 minutes (accurate estimator)
    assert 25 < estimate < 50  # reasonable range


# ---------------------------------------------------------------------------
# Long-running exclusion
# ---------------------------------------------------------------------------

def test_long_running_excluded_from_short() -> None:
    """Entries with estimate_minutes > 480 are excluded from short-task calibration."""
    short = [_make_entry(30, 45) for _ in range(10)]
    long_running = [_make_entry(600, 1200) for _ in range(10)]  # ratio=2.0, but excluded
    history = short + long_running
    multiplier = calibrated_multiplier("small-fix", history)
    # Should only reflect the 10 short entries (warmup blend with ratio=1.5)
    expected = 0.5 * PRIOR + 0.5 * 1.5
    assert multiplier == pytest.approx(expected, rel=0.1)


# ---------------------------------------------------------------------------
# Stats output (no multiplier exposed)
# ---------------------------------------------------------------------------

def test_stats_no_history() -> None:
    result = stats_for_category("small-fix", [])
    assert result["n"] == 0
    assert result["median"] is None
    assert "no history" in result["confidence_label"]


def test_stats_cold_start() -> None:
    history = [_make_entry(30, 40) for _ in range(3)]
    result = stats_for_category("small-fix", history)
    assert result["n"] == 3
    assert result["median"] is not None
    assert "prior" in result["confidence_label"]


def test_stats_warmup() -> None:
    history = [_make_entry(30, 40) for _ in range(12)]
    result = stats_for_category("small-fix", history)
    assert result["n"] == 12
    assert "warming" in result["confidence_label"]


def test_stats_calibrated() -> None:
    history = [_make_entry(30, 40) for _ in range(25)]
    result = stats_for_category("small-fix", history)
    assert result["n"] == 25
    assert "calibrated" in result["confidence_label"]


def test_stats_no_multiplier_in_output() -> None:
    """Verify stats output does NOT contain a 'multiplier' field."""
    history = [_make_entry(30, 40) for _ in range(25)]
    result = stats_for_category("small-fix", history)
    assert "multiplier" not in result


def test_all_stats_multiple_categories() -> None:
    history = (
        [_make_entry(30, 40, category="small-fix") for _ in range(5)] +
        [_make_entry(120, 180, category="medium-feature") for _ in range(3)]
    )
    results = all_stats(history)
    categories = [r["category"] for r in results]
    assert "small-fix" in categories
    assert "medium-feature" in categories


# ---------------------------------------------------------------------------
# Exclusion of non-eligible entries
# ---------------------------------------------------------------------------

def test_cancelled_excluded() -> None:
    history = [_make_entry(30, 40, status="cancelled") for _ in range(25)]
    result = stats_for_category("small-fix", history)
    assert result["n"] == 0


def test_corrected_excluded() -> None:
    """Entries with corrected_by set are excluded."""
    history = [
        {**_make_entry(30, 40), "corrected_by": "manual-correct:2024-01-01"}
        for _ in range(25)
    ]
    result = stats_for_category("small-fix", history)
    assert result["n"] == 0
