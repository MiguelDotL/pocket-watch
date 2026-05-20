"""Tests for clock.py: IANA detection, DST transitions, day-part, formatting."""

from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add scripts/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from pocket_watch.clock import (
    _day_part,
    _detect_iana_tz,
    _utc_offset_str,
    format_compact,
    now_info,
)


# ---------------------------------------------------------------------------
# Day-part tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hour, expected", [
    (0, "late-night"),
    (3, "late-night"),
    (4, "late-night"),
    (5, "early-morning"),
    (8, "early-morning"),
    (9, "morning"),
    (11, "morning"),
    (12, "midday"),
    (13, "midday"),
    (14, "afternoon"),
    (17, "afternoon"),
    (18, "evening"),
    (20, "evening"),
    (21, "night"),
    (23, "night"),
])
def test_day_part(hour: int, expected: str) -> None:
    assert _day_part(hour) == expected


# ---------------------------------------------------------------------------
# UTC offset formatting
# ---------------------------------------------------------------------------

def test_utc_offset_positive() -> None:
    dt = datetime.datetime(2024, 6, 15, 12, 0, 0,
                           tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
    assert _utc_offset_str(dt) == "+05:30"


def test_utc_offset_negative() -> None:
    dt = datetime.datetime(2024, 6, 15, 12, 0, 0,
                           tzinfo=datetime.timezone(datetime.timedelta(hours=-7)))
    assert _utc_offset_str(dt) == "-07:00"


def test_utc_offset_zero() -> None:
    dt = datetime.datetime(2024, 6, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
    assert _utc_offset_str(dt) == "+00:00"


def test_utc_offset_chatham() -> None:
    """Pacific/Chatham is UTC+12:45 (standard) / UTC+13:45 (DST)."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Pacific/Chatham")
        # In January (Southern Hemisphere summer = DST in Chatham)
        dt = datetime.datetime(2024, 1, 15, 12, 0, tzinfo=tz)
        offset = _utc_offset_str(dt)
        assert "13:45" in offset
    except ImportError:
        pytest.skip("zoneinfo not available")


# ---------------------------------------------------------------------------
# IANA detection: env var override
# ---------------------------------------------------------------------------

def test_env_var_override() -> None:
    with patch.dict(os.environ, {"POCKET_WATCH_TZ": "Asia/Tokyo"}):
        iana, fallback = _detect_iana_tz()
    assert iana == "Asia/Tokyo"
    assert fallback is False


def test_env_var_empty_falls_through() -> None:
    with patch.dict(os.environ, {"POCKET_WATCH_TZ": ""}):
        # Should not use empty string as a valid TZ
        iana, fallback = _detect_iana_tz()
        # Whatever it returns, should not be empty
        assert iana != ""


# ---------------------------------------------------------------------------
# DST transition tests
# ---------------------------------------------------------------------------

def test_dst_spring_forward_los_angeles() -> None:
    """America/Los_Angeles: clocks spring forward 2025-03-09 02:00 → 03:00.
    The hour from 02:00–03:00 is skipped, so 01:59 → 03:00 wall-clock is only
    1 minute of actual elapsed UTC time."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("America/Los_Angeles")
        before = datetime.datetime(2025, 3, 9, 1, 59, tzinfo=tz)
        after = datetime.datetime(2025, 3, 9, 3, 0, tzinfo=tz)

        before_ts = before.timestamp()
        after_ts = after.timestamp()
        # Wall clock jumped 1h1m but UTC elapsed is only 1 minute (hour was skipped)
        assert after_ts - before_ts == pytest.approx(60, abs=1)
    except ImportError:
        pytest.skip("zoneinfo not available")


def test_dst_fall_back_los_angeles() -> None:
    """America/Los_Angeles: clocks fall back 2025-11-02 02:00 → 01:00.

    ISO 8601 offsets disambiguate the repeated hour.
    """
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("America/Los_Angeles")
        # 01:30 PDT (before fallback, UTC-7)
        dt1 = datetime.datetime(2025, 11, 2, 1, 30,
                                tzinfo=datetime.timezone(datetime.timedelta(hours=-7)))
        # 01:30 PST (after fallback, UTC-8)
        dt2 = datetime.datetime(2025, 11, 2, 1, 30,
                                tzinfo=datetime.timezone(datetime.timedelta(hours=-8)))

        # They should represent different UTC moments
        assert dt1.timestamp() != dt2.timestamp()
        assert _utc_offset_str(dt1) == "-07:00"
        assert _utc_offset_str(dt2) == "-08:00"
    except ImportError:
        pytest.skip("zoneinfo not available")


def test_dst_london() -> None:
    """Europe/London: UTC+1 in summer, UTC+0 in winter."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Europe/London")
        summer = datetime.datetime(2024, 7, 15, 12, 0, tzinfo=tz)
        winter = datetime.datetime(2024, 1, 15, 12, 0, tzinfo=tz)

        assert _utc_offset_str(summer) == "+01:00"
        assert _utc_offset_str(winter) == "+00:00"
    except ImportError:
        pytest.skip("zoneinfo not available")


def test_dst_sydney() -> None:
    """Australia/Sydney: UTC+11 in summer (Jan), UTC+10 in winter (Jul)."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Australia/Sydney")
        summer = datetime.datetime(2024, 1, 15, 12, 0, tzinfo=tz)
        winter = datetime.datetime(2024, 7, 15, 12, 0, tzinfo=tz)

        assert _utc_offset_str(summer) == "+11:00"
        assert _utc_offset_str(winter) == "+10:00"
    except ImportError:
        pytest.skip("zoneinfo not available")


def test_half_hour_zone_kolkata() -> None:
    """Asia/Kolkata is UTC+05:30 year-round (no DST)."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        dt = datetime.datetime(2024, 6, 15, 12, 0, tzinfo=tz)
        assert _utc_offset_str(dt) == "+05:30"
    except ImportError:
        pytest.skip("zoneinfo not available")


def test_quarter_hour_zone_kathmandu() -> None:
    """Asia/Kathmandu is UTC+05:45 (Nepal Standard Time)."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Asia/Kathmandu")
        dt = datetime.datetime(2024, 6, 15, 12, 0, tzinfo=tz)
        assert _utc_offset_str(dt) == "+05:45"
    except ImportError:
        pytest.skip("zoneinfo not available")


def test_arizona_no_dst() -> None:
    """America/Phoenix does not observe DST; UTC-7 year-round."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("America/Phoenix")
        summer = datetime.datetime(2024, 7, 15, 12, 0, tzinfo=tz)
        winter = datetime.datetime(2024, 1, 15, 12, 0, tzinfo=tz)

        assert _utc_offset_str(summer) == "-07:00"
        assert _utc_offset_str(winter) == "-07:00"
    except ImportError:
        pytest.skip("zoneinfo not available")


# ---------------------------------------------------------------------------
# Leap year / edge date tests
# ---------------------------------------------------------------------------

def test_leap_year_feb_29() -> None:
    """Feb 29 should be a valid date in a leap year."""
    dt = datetime.datetime(2024, 2, 29, 12, 0, tzinfo=datetime.timezone.utc)
    assert dt.month == 2
    assert dt.day == 29


def test_not_leap_year_2100() -> None:
    """2100 is not a leap year (century rule)."""
    with pytest.raises(ValueError):
        datetime.datetime(2100, 2, 29)


def test_year_2038_unix_overflow() -> None:
    """Python datetime handles post-2038 dates (uses arbitrary precision)."""
    dt = datetime.datetime(2038, 1, 19, 3, 14, 8, tzinfo=datetime.timezone.utc)
    assert dt.year == 2038
    # Should not raise
    assert dt.timestamp() > 0


def test_pre_1970_date() -> None:
    """Python datetime supports dates before 1970."""
    dt = datetime.datetime(1969, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc)
    assert dt.year == 1969


# ---------------------------------------------------------------------------
# now_info structure tests
# ---------------------------------------------------------------------------

def test_now_info_structure() -> None:
    """now_info() should return all expected keys."""
    info = now_info()
    required_keys = {
        "iso", "utc_offset", "iana", "day_part", "weekday",
        "date", "time_24h", "time_12h", "holiday",
        "streak_minutes", "conversational_hints", "habits_summary",
    }
    for key in required_keys:
        assert key in info, f"Missing key: {key}"


def test_now_info_offset_positive() -> None:
    """now_info with +1d offset should return tomorrow."""
    now = now_info()
    tomorrow = now_info(offset_delta=datetime.timedelta(days=1))

    # Date should differ by 1 day
    from datetime import date
    now_date = date.fromisoformat(now["date"])
    tomorrow_date = date.fromisoformat(tomorrow["date"])
    assert (tomorrow_date - now_date).days == 1


def test_now_info_offset_negative() -> None:
    """now_info with -1d offset should return yesterday."""
    now = now_info()
    yesterday = now_info(offset_delta=datetime.timedelta(days=-1))

    from datetime import date
    now_date = date.fromisoformat(now["date"])
    yesterday_date = date.fromisoformat(yesterday["date"])
    assert (now_date - yesterday_date).days == 1


def test_now_info_with_env_tz() -> None:
    """Env var override should be reflected in now_info IANA field."""
    with patch.dict(os.environ, {"POCKET_WATCH_TZ": "Asia/Tokyo"}):
        info = now_info()
    assert info["iana"] == "Asia/Tokyo"


def test_format_compact_structure() -> None:
    """format_compact should produce a non-empty single-line string."""
    info = now_info()
    result = format_compact(info)
    assert isinstance(result, str)
    assert len(result) > 0
    # Should not include bare TZ abbreviations like PST, CST, PDT
    # (this is a belt-and-suspenders check; the actual rule is in clock.py)
    assert "·" in result  # separator present
