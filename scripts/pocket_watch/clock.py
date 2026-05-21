"""IANA timezone detection with 8-step fallback chain.

Detection priority:
  1. $POCKET_WATCH_TZ env var (user override)
  2. datetime.now().astimezone().tzinfo  (handles most platforms)
  3. readlink /etc/localtime             (macOS/Linux)
  4. /etc/timezone                       (Debian-family Linux)
  5. timedatectl show                    (systemd Linux)
  6. systemsetup -gettimezone            (macOS)
  7. tzutil /g + Windows→IANA mapping   (Windows)
  8. UTC + warning to stderr

Display rule: never bare abbreviations — always Region/City (UTC±HH:MM).
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Windows TZ abbreviation → IANA name mapping (subset; extend as needed)
# ---------------------------------------------------------------------------
_WINDOWS_TO_IANA: dict[str, str] = {
    "AUS Eastern Standard Time": "Australia/Sydney",
    "AUS Central Standard Time": "Australia/Darwin",
    "Canada Central Standard Time": "America/Regina",
    "Cape Verde Standard Time": "Atlantic/Cape_Verde",
    "Cen. Australia Standard Time": "Australia/Adelaide",
    "Central America Standard Time": "America/Guatemala",
    "Central Asia Standard Time": "Asia/Almaty",
    "Central Brazilian Standard Time": "America/Cuiaba",
    "Central Europe Standard Time": "Europe/Budapest",
    "Central European Standard Time": "Europe/Warsaw",
    "Central Pacific Standard Time": "Pacific/Guadalcanal",
    "Central Standard Time": "America/Chicago",
    "Central Standard Time (Mexico)": "America/Mexico_City",
    "China Standard Time": "Asia/Shanghai",
    "E. Africa Standard Time": "Africa/Nairobi",
    "E. Australia Standard Time": "Australia/Brisbane",
    "E. Europe Standard Time": "Asia/Nicosia",
    "E. South America Standard Time": "America/Sao_Paulo",
    "Eastern Standard Time": "America/New_York",
    "Eastern Standard Time (Mexico)": "America/Cancun",
    "Egypt Standard Time": "Africa/Cairo",
    "Ekaterinburg Standard Time": "Asia/Yekaterinburg",
    "FLE Standard Time": "Europe/Kiev",
    "GMT Standard Time": "Europe/London",
    "GTB Standard Time": "Europe/Bucharest",
    "Georgian Standard Time": "Asia/Tbilisi",
    "Greenland Standard Time": "America/Godthab",
    "Greenwich Standard Time": "Atlantic/Reykjavik",
    "Hawaii Standard Time": "Pacific/Honolulu",
    "India Standard Time": "Asia/Kolkata",
    "Iran Standard Time": "Asia/Tehran",
    "Israel Standard Time": "Asia/Jerusalem",
    "Jordan Standard Time": "Asia/Amman",
    "Korea Standard Time": "Asia/Seoul",
    "Mauritius Standard Time": "Indian/Mauritius",
    "Middle East Standard Time": "Asia/Beirut",
    "Montevideo Standard Time": "America/Montevideo",
    "Morocco Standard Time": "Africa/Casablanca",
    "Mountain Standard Time": "America/Denver",
    "Mountain Standard Time (Mexico)": "America/Chihuahua",
    "Myanmar Standard Time": "Asia/Rangoon",
    "N. Central Asia Standard Time": "Asia/Novosibirsk",
    "Namibia Standard Time": "Africa/Windhoek",
    "Nepal Standard Time": "Asia/Kathmandu",
    "New Zealand Standard Time": "Pacific/Auckland",
    "Newfoundland Standard Time": "America/St_Johns",
    "North Asia East Standard Time": "Asia/Irkutsk",
    "North Asia Standard Time": "Asia/Krasnoyarsk",
    "Pacific SA Standard Time": "America/Santiago",
    "Pacific Standard Time": "America/Los_Angeles",
    "Pacific Standard Time (Mexico)": "America/Santa_Isabel",
    "Romance Standard Time": "Europe/Paris",
    "Russia Time Zone 11": "Asia/Kamchatka",
    "Russia Time Zone 3": "Europe/Samara",
    "Russian Standard Time": "Europe/Moscow",
    "SA Eastern Standard Time": "America/Cayenne",
    "SA Pacific Standard Time": "America/Bogota",
    "SA Western Standard Time": "America/La_Paz",
    "SE Asia Standard Time": "Asia/Bangkok",
    "Samoa Standard Time": "Pacific/Apia",
    "Singapore Standard Time": "Asia/Singapore",
    "South Africa Standard Time": "Africa/Johannesburg",
    "Sri Lanka Standard Time": "Asia/Colombo",
    "Syria Standard Time": "Asia/Damascus",
    "Taipei Standard Time": "Asia/Taipei",
    "Tasmania Standard Time": "Australia/Hobart",
    "Tokyo Standard Time": "Asia/Tokyo",
    "Tonga Standard Time": "Pacific/Tongatapu",
    "Turkey Standard Time": "Europe/Istanbul",
    "US Eastern Standard Time": "America/Indiana/Indianapolis",
    "US Mountain Standard Time": "America/Phoenix",
    "UTC": "Etc/UTC",
    "UTC+12": "Etc/GMT-12",
    "UTC-02": "Etc/GMT+2",
    "UTC-11": "Etc/GMT+11",
    "Ulaanbaatar Standard Time": "Asia/Ulaanbaatar",
    "Venezuela Standard Time": "America/Caracas",
    "Vladivostok Standard Time": "Asia/Vladivostok",
    "W. Australia Standard Time": "Australia/Perth",
    "W. Central Africa Standard Time": "Africa/Lagos",
    "W. Europe Standard Time": "Europe/Berlin",
    "West Asia Standard Time": "Asia/Tashkent",
    "West Pacific Standard Time": "Pacific/Port_Moresby",
    "Yakutsk Standard Time": "Asia/Yakutsk",
}

# Day-part boundaries (hour, inclusive start). 0–4 handled separately as "late-night".
_DAY_PARTS = [
    (5, "early-morning"),
    (9, "morning"),
    (12, "midday"),
    (14, "afternoon"),
    (18, "evening"),
    (21, "night"),
]


def _day_part(hour: int) -> str:
    """Return descriptive day-part label for a local hour (0–23)."""
    if hour < 5:
        return "late-night"
    result = "late-night"
    for start, label in _DAY_PARTS:
        if hour >= start:
            result = label
    return result


_IANA_CACHE_TTL_SECONDS = 60 * 60  # 1 hour — long enough to skip repeated calls, short enough for travel


def _detect_iana_tz() -> tuple[str, bool]:
    """Return (iana_name, used_fallback).

    Tries each step in order; returns on first success.
    Result is cached to disk for 1 hour to avoid repeated subprocess calls
    (timedatectl, systemsetup) and filesystem walks on repeated invocations.
    """
    # Step 1: env var override — always wins, never cached
    env_tz = os.environ.get("POCKET_WATCH_TZ", "").strip()
    if env_tz:
        return env_tz, False

    # Cache check — only valid if no env var override is in effect
    try:
        from pocket_watch.paths import data_dir
        cache_path = data_dir() / ".iana_cache.json"
        try:
            cached = json.loads(cache_path.read_text())
            ts = float(cached.get("ts", 0))
            if time.time() - ts < _IANA_CACHE_TTL_SECONDS:
                iana = cached.get("iana")
                fallback = bool(cached.get("fallback", False))
                if iana:
                    return iana, fallback
        except (FileNotFoundError, ValueError, OSError):
            pass
    except Exception:
        cache_path = None  # type: ignore[assignment]

    iana, fallback = _detect_iana_tz_uncached()

    # Write cache (best-effort)
    try:
        if cache_path is not None:
            cache_path.write_text(json.dumps({"ts": time.time(), "iana": iana, "fallback": fallback}))
    except OSError:
        pass

    return iana, fallback


def _detect_iana_tz_uncached() -> tuple[str, bool]:
    """The actual detection chain. Slow — only called on cache miss."""

    # Step 2: Python datetime (works on Windows, macOS, Linux in most cases)
    try:
        now = datetime.datetime.now().astimezone()
        tzinfo = now.tzinfo
        if tzinfo is not None:
            # Try to get IANA name from tzinfo
            tz_name = str(tzinfo)
            # On macOS/Linux this may already be IANA form
            if "/" in tz_name and not tz_name.startswith("UTC"):
                return tz_name, False
    except Exception:
        pass

    # Step 3: readlink /etc/localtime (macOS/Linux)
    if sys.platform != "win32":
        try:
            link = Path("/etc/localtime")
            if link.is_symlink():
                target = str(link.resolve())
                # Extract "Region/City" from .../zoneinfo/Region/City
                m = re.search(r"zoneinfo/(.+)$", target)
                if m:
                    return m.group(1), False
        except Exception:
            pass

        # Step 4: /etc/timezone (Debian-family)
        try:
            tz_file = Path("/etc/timezone")
            if tz_file.exists():
                content = tz_file.read_text().strip()
                if content and "/" in content:
                    return content, False
        except Exception:
            pass

        # Step 5: timedatectl (systemd)
        try:
            result = subprocess.run(
                ["timedatectl", "show", "--property=Timezone", "--value"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            val = result.stdout.strip()
            if val and "/" in val:
                return val, False
        except Exception:
            pass

        # Step 6: systemsetup (macOS)
        if sys.platform == "darwin":
            try:
                result = subprocess.run(
                    ["systemsetup", "-gettimezone"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                # Output: "Time Zone: America/Los_Angeles"
                m = re.search(r"Time Zone:\s*(.+)", result.stdout)
                if m:
                    tz_val = m.group(1).strip()
                    if "/" in tz_val:
                        return tz_val, False
            except Exception:
                pass

    # Step 7: tzutil (Windows)
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["tzutil", "/g"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            win_tz = result.stdout.strip()
            if win_tz in _WINDOWS_TO_IANA:
                return _WINDOWS_TO_IANA[win_tz], False
        except Exception:
            pass

    # Step 8: fallback UTC
    return "UTC", True


def _utc_offset_str(dt: datetime.datetime) -> str:
    """Format UTC offset as ±HH:MM."""
    offset = dt.utcoffset()
    if offset is None:
        return "+00:00"
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f"{sign}{hours:02d}:{minutes:02d}"


_TZDATA_CACHE_TTL_SECONDS = 7 * 24 * 3600  # check at most once a week


def _check_tzdata_freshness() -> Optional[str]:
    """Return a warning string if tzdata appears stale, else None.

    Result is cached to disk for 7 days because `importlib.metadata.distribution()`
    is the slowest operation in the hot path (~21ms on a typical machine) and
    tzdata staleness rarely changes between calls.
    """
    try:
        from pocket_watch.paths import data_dir
        cache_path = data_dir() / ".tzdata_check.json"
        try:
            cached = json.loads(cache_path.read_text())
            ts = float(cached.get("ts", 0))
            if time.time() - ts < _TZDATA_CACHE_TTL_SECONDS:
                warn = cached.get("warn")
                return warn if warn else None
        except (FileNotFoundError, ValueError, OSError):
            pass

        # Cache miss or stale — run the real check
        warn = _compute_tzdata_freshness()
        try:
            cache_path.write_text(json.dumps({"ts": time.time(), "warn": warn}))
        except OSError:
            pass
        return warn
    except Exception:
        # Any unexpected failure — silently skip the warning, don't break now_info
        return None


def _compute_tzdata_freshness() -> Optional[str]:
    """Actual tzdata version check. Slow — only called on cache miss."""
    try:
        import importlib.metadata
        dist = importlib.metadata.distribution("tzdata")
        version_str = dist.version  # e.g. "2024.1"
        year_str = version_str.split(".")[0]
        if year_str.isdigit():
            year = int(year_str)
            current_year = datetime.date.today().year
            if current_year - year > 1:
                return (
                    f"tzdata package version {version_str} may be stale "
                    f"(>12 months old). Consider updating: pip install --upgrade tzdata"
                )
    except Exception:
        pass
    return None


def now_info(offset_delta: Optional[datetime.timedelta] = None) -> dict:
    """Return current time information as a dict.

    Args:
        offset_delta: optional timedelta to shift the result (e.g. +1 day for "tomorrow")

    Returns dict with keys:
        iso, utc_offset, iana, day_part, weekday, date, time_12h, time_24h,
        holiday, streak_minutes, conversational_hints, habits_summary,
        tzdata_warning (optional)
    """
    iana, used_fallback = _detect_iana_tz()

    # Build aware datetime in detected tz
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(iana)
        now = datetime.datetime.now(tz=tz)
    except Exception:
        # zoneinfo not available or bad IANA name — use system local
        now = datetime.datetime.now().astimezone()
        iana = "UTC"
        used_fallback = True

    if offset_delta is not None:
        now = now + offset_delta

    utc_offset = _utc_offset_str(now)
    iso = now.isoformat()
    day = now.weekday()  # 0=Mon
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday = weekday_names[day]
    date_str = now.strftime("%Y-%m-%d")
    time_24h = now.strftime("%H:%M")
    time_12h = now.strftime("%-I:%M %p") if sys.platform != "win32" else now.strftime("%I:%M %p").lstrip("0")
    dp = _day_part(now.hour)

    # Holiday lookup
    holiday = _check_holiday(now.date())

    # Habits from cached file
    habits_summary = _load_habits_summary()
    streak_minutes = habits_summary.get("current_streak_minutes", 0)

    # Conversational hints from session-state (passed via env var by hooks)
    conversational_hints = _load_conversational_hints()

    result: dict = {
        "iso": iso,
        "utc_offset": utc_offset,
        "iana": iana,
        "day_part": dp,
        "weekday": weekday,
        "date": date_str,
        "time_24h": time_24h,
        "time_12h": time_12h,
        "holiday": holiday,
        "streak_minutes": streak_minutes,
        "conversational_hints": conversational_hints,
        "habits_summary": habits_summary,
    }

    if used_fallback:
        result["tz_warning"] = "Could not detect timezone; using UTC. Set POCKET_WATCH_TZ=<IANA> to override."

    tzdata_warn = _check_tzdata_freshness()
    if tzdata_warn:
        result["tzdata_warning"] = tzdata_warn

    return result


def _check_holiday(date: datetime.date) -> Optional[str]:
    """Return holiday name if the given date is a known holiday, else None."""
    try:
        holidays_path = Path(__file__).parent.parent.parent / "holidays.json"
        if not holidays_path.exists():
            return None
        with open(holidays_path) as f:
            holidays = json.load(f)
        # Key format: "MM-DD" for recurring, "YYYY-MM-DD" for fixed
        mmdd = date.strftime("%m-%d")
        yyyymmdd = date.strftime("%Y-%m-%d")
        return holidays.get(yyyymmdd) or holidays.get(mmdd)
    except Exception:
        return None


def _load_habits_summary() -> dict:
    """Load habits from cached habits.json if available."""
    try:
        from pocket_watch.paths import habits_path
        hp = habits_path()
        if hp.exists():
            import json as _json
            with open(hp) as f:
                return _json.load(f)
    except Exception:
        pass
    return {}


def _load_conversational_hints() -> dict:
    """Load conversational hints from session-state env var."""
    session_id = os.environ.get("POCKET_WATCH_SESSION_ID", "")
    if not session_id:
        return {}
    try:
        from pocket_watch.paths import session_state_path
        sp = session_state_path(session_id)
        if sp.exists():
            import json as _json
            with open(sp) as f:
                state = _json.load(f)
            return state.get("conversational_hints", {})
    except Exception:
        pass
    return {}


def format_compact(info: dict) -> str:
    """Format time info as a compact single line."""
    iana = info.get("iana", "UTC")
    utc_offset = info.get("utc_offset", "+00:00")
    date = info.get("date", "")
    time_24h = info.get("time_24h", "")
    time_12h = info.get("time_12h", "")
    weekday = info.get("weekday", "")
    dp = info.get("day_part", "")
    streak = info.get("streak_minutes", 0)
    holiday = info.get("holiday")

    parts = [
        f"{date} {time_24h} ({time_12h}) {iana} ({utc_offset})",
        f"{weekday} {dp}",
        f"streak {streak}min",
    ]
    if holiday:
        parts.append(f"holiday: {holiday}")

    line = " · ".join(parts)

    warn = info.get("tz_warning")
    if warn:
        line += f"\n⚠ {warn}"
    return line
