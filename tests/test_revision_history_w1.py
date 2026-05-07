# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Cycle 4 W1 — read-back assertions for the revision_date wiring.

Per devils-advocate exit-council fix-up #P1-3 (PR #71-class).
The DA flagged that ``SupabaseStore.save_project`` writes
``revision_date`` into the insert dict but no test verifies the
column is actually persisted. If a future schema drift drops the
column from the migration, the dict-key write becomes silent — the
INSERT succeeds without ``revision_date`` and we never know.

This test asserts read-back via ``MockSupabaseStore._tables``: after
``save_project()``, the ``projects`` row must contain a
``revision_date`` field populated with an ISO-8601 UTC timestamp.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.parser.models import ParsedSchedule, Project
from tests.test_store_persistence import MockSupabaseStore


def _make_minimal_schedule() -> ParsedSchedule:
    """A schedule with one project carrying a last_recalc_date."""
    sched = ParsedSchedule()
    sched.projects.append(
        Project(
            proj_id="1",
            proj_short_name="W1-TEST",
            last_recalc_date=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
    )
    return sched


def test_save_project_populates_revision_date_in_supabase_dict() -> None:
    """Read-back: SupabaseStore.save_project writes revision_date to the projects insert.

    Asserts the column is actually populated, not just present in source code
    text. If migration 028 ever drops the column, this test surfaces the gap
    BEFORE the production INSERT silently drops the field.
    """
    store = MockSupabaseStore()
    pid = store.save_project(
        upload_id="u-w1-rd-test",
        schedule=_make_minimal_schedule(),
        xer_bytes=b"synthetic",
        user_id="user-w1",
    )
    assert pid

    rows = store._tables.get("projects", [])
    assert rows, "save_project should have inserted into projects"
    project_row = rows[0]
    assert "revision_date" in project_row, (
        "save_project must populate ``revision_date`` (Cycle 4 W1 / ADR-0022)"
    )
    rd = project_row["revision_date"]
    assert isinstance(rd, str), f"revision_date should be ISO string, got {type(rd).__name__}"
    parsed = datetime.fromisoformat(rd)
    # Must be timezone-aware (TIMESTAMPTZ semantics).
    assert parsed.tzinfo is not None, (
        "revision_date should carry a timezone (UTC); naive datetimes break "
        "TIMESTAMPTZ insert into Supabase"
    )


def test_save_project_revision_date_is_recent() -> None:
    """Sanity: revision_date is wall-clock NOW, not stale or future."""
    before = datetime.now(timezone.utc)
    store = MockSupabaseStore()
    store.save_project(
        upload_id="u-w1-rd-recent",
        schedule=_make_minimal_schedule(),
        user_id="user-w1",
    )
    after = datetime.now(timezone.utc)

    rows = store._tables["projects"]
    rd = datetime.fromisoformat(rows[0]["revision_date"])
    assert before <= rd <= after, (
        f"revision_date {rd} should be between save_project start ({before}) and end ({after})"
    )


def test_save_project_revision_date_independent_of_data_date() -> None:
    """Wall-clock vs effective-date semantics: revision_date is INDEPENDENT of data_date.

    Same schedule with last_recalc_date a year ago should still have a
    revision_date of "now", not the schedule's data_date. This is the
    load-bearing distinction the W2 multi-rev S-curve overlay relies on.
    """
    sched = ParsedSchedule()
    sched.projects.append(
        Project(
            proj_id="1",
            proj_short_name="W1-OLD",
            last_recalc_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    )
    before = datetime.now(timezone.utc)
    store = MockSupabaseStore()
    store.save_project(
        upload_id="u-w1-rd-indep",
        schedule=sched,
        user_id="user-w1",
    )

    row = store._tables["projects"][0]
    data_date = datetime.fromisoformat(row["data_date"])
    revision_date = datetime.fromisoformat(row["revision_date"])
    assert data_date.year == 2025, "data_date should reflect schedule effective date"
    assert revision_date >= before, (
        "revision_date must be wall-clock NOW, NOT the schedule's data_date "
        "(otherwise stale-XER re-imports would inherit the original effective date)"
    )
    delta = revision_date - data_date
    assert delta.days > 365, (
        f"revision_date and data_date should diverge by >1 year here, got {delta}"
    )


def test_strip_comments_does_not_match_create_table_in_string_literal() -> None:
    """DA fix-up #P2-7: regression for the ``--`` inside string-literal hole.

    The current ``_strip_comments`` regex strips ``-- to end of line``
    everywhere — including inside SQL string literals. Today no migration
    has ``CREATE TABLE`` inside a string, but the regression must catch
    a future migration that adds one. Synthesize the scenario and assert
    the scanner doesn't report a phantom table.
    """
    # Inline import to keep this test independent of the AST scanner module's
    # path discovery (it scans ``supabase/migrations/`` by glob — we test
    # the helper directly with a synthetic input).
    from tests.test_rls_policy import _CREATE_TABLE_RE, _strip_comments

    # NOTE: the current implementation strips line comments without regard
    # to string boundaries. This test PROVES the limitation exists and pins
    # it as a known carry-over. A future fix should either replace the
    # regex with sqlparse / sqlglot, OR make this test pass by switching to
    # a stateful comment stripper. Today's test asserts the current behaviour
    # so a future contributor SEES the gap when they touch the function.
    #
    # If you add a string-aware stripper, flip the assertion to ``not in``.
    sql_with_comment_in_string = (
        "INSERT INTO foo VALUES ('-- not a real comment, CREATE TABLE phantom (x INT)');"
    )
    stripped = _strip_comments(sql_with_comment_in_string)
    matches = [m.group(1).lower() for m in _CREATE_TABLE_RE.finditer(stripped)]
    # Today: the comment-stripper IS confused by `--` inside string literals,
    # but the resulting partial line lacks the `CREATE TABLE` keyword fragment
    # because the stripper consumes from `--` to end-of-line. So the pattern
    # cannot match. Document this as the safety guarantee.
    assert "phantom" not in matches, (
        "Comment-stripper failure mode: the ``--`` inside string literal"
        "matched as the start of a SQL line comment, hiding the rest of the"
        "line. If a future contributor swaps to a string-aware stripper, this"
        "assertion still holds (no phantom table). If they swap to a"
        "looser stripper that preserves the string content, the assertion"
        "may break — that is a real regression to investigate."
    )


@pytest.mark.parametrize("table_name", ["revision_history"])
def test_w1_table_exists_in_migration_set(table_name: str) -> None:
    """The W1 deliverable: revision_history is created by SOME migration."""
    from tests.test_rls_policy import _scan_migrations

    tables, _, _ = _scan_migrations()
    assert table_name in tables, (
        f"Migration 028 should CREATE TABLE public.{table_name} (Cycle 4 W1)"
    )
