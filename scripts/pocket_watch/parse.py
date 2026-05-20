"""Estimate-phrase normalizer, pivot detection, and category inference.

parse.py handles:
  - Detecting estimate phrases in text (positive-context regex)
  - Normalizing durations to minutes ("1-2 hours" → 90, "30-45 min" → 37)
  - Detecting pivot/cancel signals ("nevermind", "scrap that", etc.)
  - Inferring task category from keywords
  - Skipping false positives (fenced code, URLs, past-tense, pw invocations)
"""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Positive-context regex: future-intent estimate phrases
# ---------------------------------------------------------------------------
# Compound: "2h30m", "1h 30min" — extract hours + minutes together
_COMPOUND_DURATION = re.compile(
    r"(?P<context>will take|should take|estimate[sd]?|about|around|roughly|approximately|~|let me give|I[''']d say|maybe|probably|in about|could take)\s*"
    r"(?P<hours>\d+(?:\.\d+)?)\s*(?:h|hrs?|hours?)\s*(?P<mins>\d+(?:\.\d+)?)\s*(?:m|mins?|minutes?)",
    re.IGNORECASE,
)

_ESTIMATE_POSITIVE = re.compile(
    r"(?P<context>will take|should take|estimate[sd]?|about|around|roughly|approximately|let me give|I[''']d say|maybe|probably|in about|could take)\s+"
    r"(?P<dur>(?P<qty1>\d+(?:\.\d+)?)\s*(?:-\s*(?P<qty2>\d+(?:\.\d+)?)\s*)?(?P<unit>min(?:ute)?s?|hours?|hrs?|h|days?))",
    re.IGNORECASE,
)

# Tilde patterns: "~30m", "~1 hour" — no space required after ~
_TILDE_ESTIMATE = re.compile(
    r"~\s*(?P<qty1>\d+(?:\.\d+)?)\s*(?:-\s*(?P<qty2>\d+(?:\.\d+)?)\s*)?(?P<unit>min(?:ute)?s?|hours?|hrs?|h|days?)",
    re.IGNORECASE,
)

# Also catch "an hour", "a couple hours"
_WORD_DURATION = re.compile(
    r"(?:will take|should take|estimate[sd]?|about|around|roughly|approximately|~|maybe|probably)\s+"
    r"(?P<word>an hour(?:\s+or\s+so)?|a\s+couple\s+(?:of\s+)?hours?|half\s+an?\s+hour)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Negative-context skip patterns (false-positive prevention)
# ---------------------------------------------------------------------------
_NEGATIVE_PATTERNS = [
    re.compile(r"\d+\s*(?:min|hr|hour|day)s?\s+ago", re.IGNORECASE),
    re.compile(r"after\s+\d+\s*(?:min|hr|hour|day)", re.IGNORECASE),
    re.compile(r"(?:timeout|threshold|interval|delay|wait)\s+(?:\w+\s+)?\d+\s*(?:min|hr)", re.IGNORECASE),
    re.compile(r"set.*?to\s+\d+\s*(?:min|hr|ms|s)\b", re.IGNORECASE),
    re.compile(r"expires?\s+in\s+\d+", re.IGNORECASE),
    # Past-tense reporting ("took N min", "spent N min", "lasted N min")
    re.compile(r"\b(?:took|spent|lasted|consumed)\b.*?\d+\s*(?:min|hr|hour|day)", re.IGNORECASE),
]

# Self-output guard: lines mentioning pw commands or pocket-watch
_SELF_OUTPUT_PATTERN = re.compile(r"\bpw\s+\w|\bpocket[-_]watch\b", re.IGNORECASE)

# Fenced code block detection
_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)

# URL detection
_URL_RE = re.compile(r"https?://\S+")

# ---------------------------------------------------------------------------
# Pivot markers (conservative list — miss rather than false-cancel)
# ---------------------------------------------------------------------------
_PIVOT_PATTERNS = [
    re.compile(r"\bnever[\s-]?mind\b", re.IGNORECASE),
    re.compile(r"\bscra(?:p|tch)\s+that\b", re.IGNORECASE),
    re.compile(r"\blet[''']?s\s+abandon\b", re.IGNORECASE),
    re.compile(r"\babandon\s+this\b", re.IGNORECASE),
    re.compile(r"\bstart\s+over\b", re.IGNORECASE),
    re.compile(r"\bfrom\s+scratch\b", re.IGNORECASE),
    re.compile(r"\bcompletely\s+different\s+approach\b", re.IGNORECASE),
    re.compile(r"\blet[''']?s\s+do\s+\w+\s+instead\b", re.IGNORECASE),
    re.compile(r"\bactually[,\s]+new\s+plan\b", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Completion signal patterns (verbal closure)
# ---------------------------------------------------------------------------
_COMPLETION_PATTERNS = [
    re.compile(r"\b(?:done|finished|complete[d]?|wrapped\s+up|all\s+set)\b", re.IGNORECASE),
    re.compile(r"\bmerged\b", re.IGNORECASE),
    re.compile(r"\bdeployed\b", re.IGNORECASE),
    re.compile(r"\bships?\b", re.IGNORECASE),
    re.compile(r"✅"),
    re.compile(r"\bPR\s+(?:is\s+)?(?:open|created|merged)\b", re.IGNORECASE),
    re.compile(r"\btests?\s+pass(?:ing|ed)?\b", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Category keyword mapping
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("small-fix", ["typo", "rename", "lint", "format", "tweak", "small", "quick", "config", "fix"]),
    ("medium-feature", ["add", "implement", "create", "build", "feature", "new endpoint", "endpoint", "api"]),
    ("large-refactor", ["refactor", "restructure", "redesign", "migrate", "port", "big change", "overhaul"]),
    ("deployment", ["deploy", "release", "ship", "push", "prod", "rollout", "launch"]),
    ("testing", ["test", "fixture", "mock", "e2e", "integration", "spec", "coverage"]),
    ("research", ["investigate", "explore", "look into", "debug", "root cause", "research", "spike"]),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def strip_noise(text: str) -> str:
    """Remove fenced code blocks and URLs before pattern matching."""
    text = _FENCED_CODE_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    return text


def is_self_output(text: str) -> bool:
    """Return True if text contains pocket-watch self-referential content."""
    return bool(_SELF_OUTPUT_PATTERN.search(text))


def is_pivot(text: str) -> bool:
    """Return True if text contains a pivot/cancel signal."""
    clean = strip_noise(text)
    return any(p.search(clean) for p in _PIVOT_PATTERNS)


def has_completion_signal(text: str) -> bool:
    """Return True if text contains a verbal completion signal."""
    clean = strip_noise(text)
    return any(p.search(clean) for p in _COMPLETION_PATTERNS)


def _to_minutes(qty: float, unit: str) -> float:
    """Convert a quantity + unit to minutes."""
    unit = unit.lower()
    if unit.startswith("day"):
        return qty * 8 * 60  # 8-hour workday
    if unit in ("h", "hr", "hrs", "hour", "hours"):
        return qty * 60
    # minutes
    return qty


def extract_estimate(text: str) -> Optional[dict]:
    """Extract the first estimate phrase from text.

    Returns dict with keys: minutes (float), phrase (str), sentence (str)
    or None if no estimate found.
    """
    clean = strip_noise(text)

    # Check negative context first
    for neg in _NEGATIVE_PATTERNS:
        if neg.search(clean):
            return None

    # Compound duration: "2h30m", "1h 30min" — try before single-unit regex
    compound_m = _COMPOUND_DURATION.search(clean)
    if compound_m:
        minutes = float(compound_m.group("hours")) * 60 + float(compound_m.group("mins"))
        sentence = _extract_sentence(text, compound_m.start())
        return {
            "minutes": minutes,
            "phrase": compound_m.group(0),
            "sentence": sentence[:200],
        }

    # Word-duration patterns ("an hour", "a couple hours")
    word_m = _WORD_DURATION.search(clean)
    if word_m:
        word = word_m.group("word").lower()
        if "couple" in word:
            minutes = 120.0
        elif "half" in word:
            minutes = 30.0
        else:
            minutes = 60.0
        sentence = _extract_sentence(text, word_m.start())
        return {
            "minutes": minutes,
            "phrase": word_m.group(0),
            "sentence": sentence[:200],
        }

    # Tilde pattern: "~30m", "~1 hour" (no space-after-context required)
    tilde_m = _TILDE_ESTIMATE.search(clean)
    if tilde_m:
        qty1 = float(tilde_m.group("qty1"))
        qty2_str = tilde_m.group("qty2")
        unit = tilde_m.group("unit")
        if qty2_str is not None:
            qty2 = float(qty2_str)
            minutes = (_to_minutes(qty1, unit) + _to_minutes(qty2, unit)) / 2.0
        else:
            minutes = _to_minutes(qty1, unit)
        sentence = _extract_sentence(text, tilde_m.start())
        return {
            "minutes": minutes,
            "phrase": tilde_m.group(0),
            "sentence": sentence[:200],
        }

    # Numeric patterns
    m = _ESTIMATE_POSITIVE.search(clean)
    if m is None:
        return None

    qty1 = float(m.group("qty1"))
    qty2_str = m.group("qty2")
    unit = m.group("unit")

    if qty2_str is not None:
        # Range: use midpoint
        qty2 = float(qty2_str)
        minutes = (_to_minutes(qty1, unit) + _to_minutes(qty2, unit)) / 2.0
    else:
        minutes = _to_minutes(qty1, unit)

    sentence = _extract_sentence(text, m.start())
    return {
        "minutes": minutes,
        "phrase": m.group(0),
        "sentence": sentence[:200],
    }


def infer_category(text: str) -> str:
    """Infer task category from text keywords.

    Uses keyword-count scoring (not first-match) so a phrase like
    "Write integration tests for the API" picks 'testing' (2 matches:
    integration, test) over 'medium-feature' (1 match: api).
    Ties resolved by _CATEGORY_KEYWORDS order (small-fix wins over feature, etc.).
    """
    lower = text.lower()
    best_category = "uncategorized"
    best_score = 0
    for category, keywords in _CATEGORY_KEYWORDS:
        score = sum(1 for kw in keywords if kw in lower)
        if score > best_score:
            best_score = score
            best_category = category
    return best_category


def _extract_sentence(text: str, pos: int) -> str:
    """Extract the sentence containing character position pos."""
    # Find sentence boundaries (. ! ? or newline)
    sentence_end = re.search(r"[.!?\n]", text[pos:])
    end = pos + (sentence_end.start() if sentence_end else len(text) - pos)

    sentence_start = text.rfind("\n", 0, pos)
    for delim in ".!?":
        candidate = text.rfind(delim, 0, pos)
        if candidate > sentence_start:
            sentence_start = candidate

    start = max(0, sentence_start + 1)
    return text[start:end].strip()


def parse_duration(duration_str: str) -> Optional[float]:
    """Parse a duration string like '30m', '1h', '2h30m', '1.5h' into minutes.

    Returns minutes as float, or None if not parseable.
    """
    duration_str = duration_str.strip().lower()

    # "2h30m" style
    m = re.fullmatch(r"(\d+(?:\.\d+)?)h(\d+)m?", duration_str)
    if m:
        return float(m.group(1)) * 60 + float(m.group(2))

    # "30m" or "30min"
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:m(?:in)?s?)", duration_str)
    if m:
        return float(m.group(1))

    # "1h" or "1hr" or "1hour"
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:h(?:rs?|ours?)?)", duration_str)
    if m:
        return float(m.group(1)) * 60

    # "1d"
    m = re.fullmatch(r"(\d+(?:\.\d+)?)d(?:ays?)?", duration_str)
    if m:
        return float(m.group(1)) * 8 * 60

    # Plain number = minutes
    m = re.fullmatch(r"(\d+(?:\.\d+)?)", duration_str)
    if m:
        return float(m.group(1))

    return None
