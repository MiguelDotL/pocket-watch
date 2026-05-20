#!/usr/bin/env python3
"""Generate synthetic test fixtures for pocket-watch tests.

All data is deterministic (seeded RNG). No real user data.
Run from the repo root: python tests/fixtures/gen_fixtures.py
"""

from __future__ import annotations

import json
import random
import datetime
import uuid
import sys
from pathlib import Path

SEED = 42
OUT_DIR = Path(__file__).parent

CATEGORIES = [
    "small-fix", "medium-feature", "large-refactor",
    "deployment", "testing", "research",
]

ESTIMATE_RANGES = {
    "small-fix": (10, 60),
    "medium-feature": (60, 180),
    "large-refactor": (120, 360),
    "deployment": (30, 120),
    "testing": (20, 90),
    "research": (30, 150),
}

# Multiplier: actual/estimated ratio — simulates planning fallacy
RATIOS = {
    "small-fix": (0.8, 2.5),
    "medium-feature": (0.9, 3.0),
    "large-refactor": (1.0, 4.0),
    "deployment": (0.5, 2.0),
    "testing": (0.7, 2.5),
    "research": (1.0, 5.0),
}


def generate_entry(
    rng: random.Random,
    session_id: str,
    base_time: datetime.datetime,
    category: str,
) -> dict:
    est_min, est_max = ESTIMATE_RANGES[category]
    estimate_minutes = round(rng.uniform(est_min, est_max), 1)

    ratio_min, ratio_max = RATIOS[category]
    ratio = rng.uniform(ratio_min, ratio_max)
    active_minutes = round(estimate_minutes * ratio, 1)
    elapsed_minutes = round(active_minutes * rng.uniform(1.0, 1.8), 1)

    started_at = base_time
    completed_at = started_at + datetime.timedelta(minutes=elapsed_minutes)

    notes_pool = [
        "refactor auth module", "add endpoint validation", "fix null pointer",
        "update config parser", "write unit tests", "investigate memory leak",
        "deploy to staging", "create migration script", "rename interface",
        "format code", "implement feature flag", "root cause analysis",
    ]
    note = rng.choice(notes_pool)

    return {
        "id": str(uuid.UUID(int=rng.getrandbits(128))),
        "_schema": 1,
        "session_id": session_id,
        "who": rng.choice(["assistant", "assistant", "user"]),  # 2/3 assistant
        "model": rng.choice(["model-a", "model-b"]),
        "project": rng.choice(["example-project", "my-app", "myrepo"]),
        "category": category,
        "source": "auto",
        "confidence": round(rng.uniform(0.7, 0.95), 2),
        "estimated_at": started_at.isoformat(),
        "estimate_minutes": estimate_minutes,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "active_minutes": active_minutes,
        "elapsed_minutes": elapsed_minutes,
        "completion_signal": rng.choice(["explicit_done", "pr_create", "test_pass", "manual"]),
        "completion_confidence": round(rng.uniform(0.65, 0.95), 2),
        "status": rng.choice(["completed", "completed", "completed", "tentative"]),
        "notes": note,
        "audited_at": None,
        "audit_result": None,
        "corrected_by": None,
        "corrects": None,
    }


def generate_fixtures() -> None:
    rng = random.Random(SEED)

    # Base time: 90 days ago in UTC
    base = datetime.datetime(2024, 3, 17, 14, 0, 0, tzinfo=datetime.timezone.utc)
    current_time = base

    entries = []
    session_counter = 0

    for day_offset in range(90):
        # 60% chance of work on any given day
        if rng.random() < 0.4:
            continue

        current_time = base + datetime.timedelta(days=day_offset, hours=rng.uniform(8, 22))
        session_id = f"fixture-session-{session_counter:04d}"
        session_counter += 1

        # 1-4 tasks per day
        num_tasks = rng.randint(1, 4)
        for _ in range(num_tasks):
            category = rng.choice(CATEGORIES)
            entry = generate_entry(rng, session_id, current_time, category)
            entries.append(entry)
            # Advance time by elapsed + short break
            current_time += datetime.timedelta(
                minutes=entry["elapsed_minutes"] + rng.uniform(5, 30)
            )

    # Write to fixture file
    out_path = OUT_DIR / "sample_estimates.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, default=str) + "\n")

    print(f"Generated {len(entries)} entries → {out_path}")

    # Write summary (static metadata — no machine-generated timestamps)
    summary = {
        "seed": SEED,
        "entry_count": len(entries),
        "categories": list(CATEGORIES),
        "date_range": "2024-03-17 to 2024-06-14",
    }
    summary_path = OUT_DIR / "fixture_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Summary → {summary_path}")


if __name__ == "__main__":
    generate_fixtures()
