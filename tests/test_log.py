"""Tests for log.py: append, read, corruption recovery, flock."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from pocket_watch.log import append_entry, iter_entries, read_all, read_tail


def _sample_entry(entry_id: str = "test-id") -> dict:
    return {
        "id": entry_id,
        "_schema": 1,
        "session_id": "s1",
        "who": "assistant",
        "model": "test-model",
        "project": "example-project",
        "category": "small-fix",
        "source": "auto",
        "confidence": 0.85,
        "estimated_at": "2024-06-15T14:32:00+00:00",
        "estimate_minutes": 30.0,
        "started_at": "2024-06-15T14:32:00+00:00",
        "completed_at": None,
        "active_minutes": None,
        "elapsed_minutes": None,
        "completion_signal": None,
        "completion_confidence": 0.0,
        "status": "open",
        "notes": "refactor auth module",
        "audited_at": None,
        "audit_result": None,
        "corrected_by": None,
        "corrects": None,
    }


# ---------------------------------------------------------------------------
# Append and read
# ---------------------------------------------------------------------------

def test_append_and_read(tmp_path: Path) -> None:
    log = tmp_path / "test.jsonl"
    entry = _sample_entry()
    append_entry(entry, log_path=log)
    entries = read_all(log_path=log)
    assert len(entries) == 1
    assert entries[0]["id"] == "test-id"


def test_append_multiple(tmp_path: Path) -> None:
    log = tmp_path / "test.jsonl"
    for i in range(5):
        append_entry(_sample_entry(f"id-{i}"), log_path=log)
    entries = read_all(log_path=log)
    assert len(entries) == 5
    assert [e["id"] for e in entries] == [f"id-{i}" for i in range(5)]


def test_read_empty_file(tmp_path: Path) -> None:
    log = tmp_path / "empty.jsonl"
    log.write_text("")
    entries = read_all(log_path=log)
    assert entries == []


def test_read_missing_file(tmp_path: Path) -> None:
    log = tmp_path / "nonexistent.jsonl"
    entries = read_all(log_path=log)
    assert entries == []


# ---------------------------------------------------------------------------
# Corruption recovery
# ---------------------------------------------------------------------------

def test_skips_corrupt_lines(tmp_path: Path) -> None:
    log = tmp_path / "corrupt.jsonl"
    log.write_text(
        '{"id": "good-1", "_schema": 1}\n'
        'NOT VALID JSON {{{ }}\n'
        '{"id": "good-2", "_schema": 1}\n'
    )
    entries = read_all(log_path=log)
    assert len(entries) == 2
    assert entries[0]["id"] == "good-1"
    assert entries[1]["id"] == "good-2"


def test_skips_empty_lines(tmp_path: Path) -> None:
    log = tmp_path / "spaced.jsonl"
    log.write_text(
        '{"id": "a"}\n'
        '\n'
        '   \n'
        '{"id": "b"}\n'
    )
    entries = read_all(log_path=log)
    assert len(entries) == 2


def test_skips_partial_line(tmp_path: Path) -> None:
    """Simulate a crash that left a partial JSON line."""
    log = tmp_path / "partial.jsonl"
    log.write_text(
        '{"id": "complete"}\n'
        '{"id": "incomplete", "status": \n'  # truncated
    )
    entries = read_all(log_path=log)
    assert len(entries) == 1
    assert entries[0]["id"] == "complete"


# ---------------------------------------------------------------------------
# Tail reading
# ---------------------------------------------------------------------------

def test_read_tail(tmp_path: Path) -> None:
    log = tmp_path / "test.jsonl"
    for i in range(10):
        append_entry(_sample_entry(f"id-{i}"), log_path=log)
    tail = read_tail(3, log_path=log)
    assert len(tail) == 3
    assert [e["id"] for e in tail] == ["id-7", "id-8", "id-9"]


def test_read_tail_fewer_than_n(tmp_path: Path) -> None:
    log = tmp_path / "test.jsonl"
    for i in range(3):
        append_entry(_sample_entry(f"id-{i}"), log_path=log)
    tail = read_tail(10, log_path=log)
    assert len(tail) == 3


# ---------------------------------------------------------------------------
# File permissions
# ---------------------------------------------------------------------------

def test_file_perms_after_append(tmp_path: Path) -> None:
    """File should be 0o600 after first append."""
    import os
    log = tmp_path / "perms.jsonl"
    append_entry(_sample_entry(), log_path=log)
    mode = oct(log.stat().st_mode & 0o777)
    assert mode == oct(0o600), f"Expected 0o600, got {mode}"


# ---------------------------------------------------------------------------
# iter_entries generator
# ---------------------------------------------------------------------------

def test_iter_entries_yields_dicts(tmp_path: Path) -> None:
    log = tmp_path / "test.jsonl"
    append_entry(_sample_entry("x"), log_path=log)
    results = list(iter_entries(log_path=log))
    assert isinstance(results[0], dict)
    assert results[0]["id"] == "x"
