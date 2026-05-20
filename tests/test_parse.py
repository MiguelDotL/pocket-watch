"""Tests for parse.py: estimate extraction, pivot detection, category inference."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from pocket_watch.parse import (
    extract_estimate,
    has_completion_signal,
    infer_category,
    is_pivot,
    is_self_output,
    parse_duration,
    strip_noise,
)


# ---------------------------------------------------------------------------
# Duration parser
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("s, expected", [
    ("30m", 30.0),
    ("30min", 30.0),
    ("1h", 60.0),
    ("1hr", 60.0),
    ("1hour", 60.0),
    ("1.5h", 90.0),
    ("2h30m", 150.0),
    ("45", 45.0),
    ("1d", 480.0),
])
def test_parse_duration_valid(s: str, expected: float) -> None:
    result = parse_duration(s)
    assert result == pytest.approx(expected)


def test_parse_duration_invalid() -> None:
    assert parse_duration("not-a-duration") is None
    assert parse_duration("") is None
    assert parse_duration("abc") is None


# ---------------------------------------------------------------------------
# Estimate extraction: positive cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected_minutes", [
    ("This will take about 30 minutes.", 30.0),
    ("It should take roughly 2 hours.", 120.0),
    ("I estimate this will take 1h.", 60.0),
    ("That's approximately 45 minutes of work.", 45.0),
    ("~1 hour to complete.", 60.0),
    ("Probably 30-45 min.", 37.5),  # midpoint
    ("This will take 1-2 hours.", 90.0),  # midpoint
    ("This will take around 2h30m.", 150.0),
])
def test_extract_estimate_positive(text: str, expected_minutes: float) -> None:
    result = extract_estimate(text)
    assert result is not None, f"No estimate found in: {text}"
    assert result["minutes"] == pytest.approx(expected_minutes, rel=0.1)


def test_extract_estimate_an_hour() -> None:
    result = extract_estimate("This will take about an hour.")
    assert result is not None
    assert result["minutes"] == pytest.approx(60.0)


def test_extract_estimate_couple_hours() -> None:
    result = extract_estimate("Probably a couple of hours.")
    assert result is not None
    assert result["minutes"] == pytest.approx(120.0)


# ---------------------------------------------------------------------------
# Estimate extraction: negative cases (false-positive prevention)
# ---------------------------------------------------------------------------

def test_no_estimate_past_tense() -> None:
    """'30 minutes ago' should not be detected as an estimate."""
    result = extract_estimate("That happened 30 minutes ago.")
    assert result is None


def test_no_estimate_timeout_config() -> None:
    """timeout=60 min is not a task estimate."""
    result = extract_estimate("Set the timeout to 60 min in the config.")
    assert result is None


def test_no_estimate_inside_fenced_code() -> None:
    """Estimates inside code blocks should be skipped."""
    text = "Here's a snippet:\n```\nSLEEP_TIME = 30 * 60  # 30 minutes\n```"
    result = extract_estimate(text)
    assert result is None


def test_no_estimate_in_url() -> None:
    """Numbers in URLs should not trigger estimate detection."""
    result = extract_estimate("See https://example.com/docs/30min-quickstart for details.")
    assert result is None


def test_no_estimate_empty_text() -> None:
    assert extract_estimate("") is None
    assert extract_estimate("   ") is None


# ---------------------------------------------------------------------------
# Notes field
# ---------------------------------------------------------------------------

def test_extract_estimate_returns_sentence() -> None:
    text = "Let me think. This will take about 30 minutes for the auth refactor. Then we can ship."
    result = extract_estimate(text)
    assert result is not None
    # Sentence should be the one containing the estimate
    assert "30 minutes" in result["sentence"] or "30" in result["sentence"]


def test_extract_estimate_sentence_truncated() -> None:
    long_text = "This will take about 30 minutes " + ("x" * 300)
    result = extract_estimate(long_text)
    assert result is not None
    assert len(result["sentence"]) <= 200


# ---------------------------------------------------------------------------
# Pivot detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Never mind, let's do something else.",
    "Nevermind, scrap that.",
    "Let's abandon this approach.",
    "Start over from scratch.",
    "Completely different approach needed.",
    "Actually, new plan: we'll use a queue.",
    "Scrap that, let's do it differently.",
])
def test_is_pivot_true(text: str) -> None:
    assert is_pivot(text) is True, f"Expected pivot signal in: {text}"


@pytest.mark.parametrize("text", [
    "This will take about 30 minutes.",
    "We're done with the refactor.",
    "Good morning! Let's start.",
])
def test_is_pivot_false(text: str) -> None:
    assert is_pivot(text) is False, f"Unexpected pivot signal in: {text}"


# ---------------------------------------------------------------------------
# Completion signal detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Done!",
    "It's finished.",
    "The task is complete.",
    "Merged to main.",
    "Deployed to production.",
    "Tests pass.",
    "✅",
    "PR is open.",
])
def test_has_completion_signal_true(text: str) -> None:
    assert has_completion_signal(text) is True, f"Expected completion signal in: {text}"


@pytest.mark.parametrize("text", [
    "This will take about 30 minutes.",
    "Let me think about this.",
    "Good morning!",
])
def test_has_completion_signal_false(text: str) -> None:
    assert has_completion_signal(text) is False, f"Unexpected completion signal in: {text}"


# ---------------------------------------------------------------------------
# Self-output guard
# ---------------------------------------------------------------------------

def test_is_self_output_pw_command() -> None:
    assert is_self_output("I ran pw stats and here's the output:") is True


def test_is_self_output_pocket_watch_mention() -> None:
    assert is_self_output("pocket-watch detected this estimate.") is True


def test_is_self_output_clean() -> None:
    assert is_self_output("This will take about 30 minutes.") is False


# ---------------------------------------------------------------------------
# Category inference
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected_category", [
    ("Fix the typo in the header", "small-fix"),
    ("Implement the new feature for user auth", "medium-feature"),
    ("Refactor the entire database layer", "large-refactor"),
    ("Deploy the app to production", "deployment"),
    ("Write integration tests for the API", "testing"),
    ("Investigate the root cause of the memory leak", "research"),
    ("Some random task with no keywords", "uncategorized"),
])
def test_infer_category(text: str, expected_category: str) -> None:
    result = infer_category(text)
    assert result == expected_category, f"For '{text}': expected {expected_category}, got {result}"


# ---------------------------------------------------------------------------
# strip_noise
# ---------------------------------------------------------------------------

def test_strip_noise_removes_code_blocks() -> None:
    text = "Before ```code block with 30 min wait``` After"
    result = strip_noise(text)
    assert "30 min" not in result


def test_strip_noise_removes_urls() -> None:
    text = "See https://example.com/30min/guide for details"
    result = strip_noise(text)
    assert "example.com" not in result
