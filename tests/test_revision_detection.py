# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Cycle 4 W2 PR-A — unit tests for src/api/revision_detection.py.

Pins the heuristic v1 contract:
- match by ``project_name`` (case-insensitive) + same ``program_id`` + different ``data_date``
- defensive: never raises (returns no-candidate shape on any failure)
- ``compute_xer_content_hash`` returns lowercase 64-char hex
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.api.revision_detection import (
    _HEURISTIC_CONFIDENCE_HIGH,
    compute_xer_content_hash,
    detect_candidate_parent,
)
from src.database.store import InMemoryStore
from src.parser.models import ParsedSchedule, Project


def _schedule(name: str, last_recalc: datetime | None) -> ParsedSchedule:
    sched = ParsedSchedule()
    sched.projects.append(Project(proj_id="1", proj_short_name=name, last_recalc_date=last_recalc))
    return sched


def test_compute_xer_content_hash_is_lowercase_hex_64() -> None:
    h = compute_xer_content_hash(b"hello world")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h), h
    # Stable shape — sha256("hello world") is well-known
    assert h == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_compute_xer_content_hash_empty_bytes() -> None:
    h = compute_xer_content_hash(b"")
    # sha256("") is well-known
    assert h == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_detect_no_candidate_when_project_missing() -> None:
    store = InMemoryStore()
    result = detect_candidate_parent(store, user_id="user-x", project_id="nonexistent")
    assert result["candidate_project_id"] is None
    assert result["confidence"] == 0.0
    assert "not found" in result["reasoning"]


def test_detect_no_candidate_when_no_program_id() -> None:
    """Anonymous uploads (no user_id) get no program_id; detect returns nothing."""
    store = InMemoryStore()
    pid = store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id=None,  # anonymous → no program_id
    )
    result = detect_candidate_parent(store, user_id="user-x", project_id=pid)
    assert result["candidate_project_id"] is None
    # Either "not owned" or "no program_id" depending on owner_check ordering.
    assert "program_id" in result["reasoning"] or "not owned" in result["reasoning"]


def test_detect_no_candidate_when_only_one_in_program() -> None:
    store = InMemoryStore()
    pid = store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-x",
    )
    result = detect_candidate_parent(store, user_id="user-x", project_id=pid)
    assert result["candidate_project_id"] is None
    assert "no sibling" in result["reasoning"]


def test_detect_returns_sibling_with_different_data_date() -> None:
    store = InMemoryStore()
    p1 = store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-x",
    )
    p2 = store.save_project(
        upload_id="u2",
        schedule=_schedule("PROJ-A", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        user_id="user-x",
    )
    # Detect from p2's perspective — p1 should be the candidate
    result = detect_candidate_parent(store, user_id="user-x", project_id=p2)
    assert result["candidate_project_id"] == p1
    assert result["confidence"] == _HEURISTIC_CONFIDENCE_HIGH
    assert "matched on project_name" in result["reasoning"]


def test_detect_skips_sibling_with_same_data_date() -> None:
    """Same data_date = duplicate re-upload, NOT a revision — heuristic skips."""
    store = InMemoryStore()
    same_dd = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", same_dd),
        user_id="user-x",
    )
    p2 = store.save_project(
        upload_id="u2",
        schedule=_schedule("PROJ-A", same_dd),  # same data_date
        user_id="user-x",
    )
    result = detect_candidate_parent(store, user_id="user-x", project_id=p2)
    assert result["candidate_project_id"] is None
    assert "no sibling with different data_date" in result["reasoning"]


def test_detect_returns_most_recent_sibling_when_multiple() -> None:
    store = InMemoryStore()
    p1 = store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-x",
    )
    p2 = store.save_project(
        upload_id="u2",
        schedule=_schedule("PROJ-A", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        user_id="user-x",
    )
    p3 = store.save_project(
        upload_id="u3",
        schedule=_schedule("PROJ-A", datetime(2026, 3, 1, tzinfo=timezone.utc)),
        user_id="user-x",
    )
    # Detect from p3 — p2 (most recent of p1/p2) should be candidate
    result = detect_candidate_parent(store, user_id="user-x", project_id=p3)
    assert result["candidate_project_id"] in (p1, p2)
    # The most recent sibling (highest data_date excluding self) wins
    # The dict comprehension in detect sorts data_date DESC NULLS LAST
    # so p2 (2026-02) ranks above p1 (2026-01). Only p3 (2026-03) is excluded as self.
    assert result["candidate_project_id"] == p2


def test_detect_rls_scoped_returns_nothing_for_other_user() -> None:
    store = InMemoryStore()
    pid = store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-x",
    )
    result = detect_candidate_parent(store, user_id="user-DIFFERENT", project_id=pid)
    assert result["candidate_project_id"] is None
    assert "not owned" in result["reasoning"] or "not found" in result["reasoning"]
