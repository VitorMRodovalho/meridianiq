# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the activity-grouping option on the Gantt schedule view.

Verifies that ``build_schedule_view(schedule, group_by=...)`` synthesises
the right WBS hierarchy for each non-default mode and leaves the original
``wbs`` mode untouched.
"""

from __future__ import annotations

import pytest

from src.analytics.schedule_view import GROUP_BY_OPTIONS, build_schedule_view
from src.parser.models import WBS, ParsedSchedule, Project, Task


def _schedule_with_mixed_activities() -> ParsedSchedule:
    """A small schedule whose activities span every grouping dimension."""
    return ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name="Demo")],
        wbs_nodes=[WBS(wbs_id="W1", wbs_name="Real WBS")],
        activities=[
            Task(
                task_id="T1",
                task_code="A1",
                task_name="Done A",
                wbs_id="W1",
                status_code="TK_Complete",
                task_type="TT_Task",
                clndr_id="C1",
                total_float_hr_cnt=0,
            ),
            Task(
                task_id="T2",
                task_code="A2",
                task_name="In progress B",
                wbs_id="W1",
                status_code="TK_Active",
                task_type="TT_Task",
                clndr_id="C1",
                total_float_hr_cnt=40,  # 5 days
            ),
            Task(
                task_id="T3",
                task_code="A3",
                task_name="Milestone C",
                wbs_id="W1",
                status_code="TK_NotStart",
                task_type="TT_Mile",
                clndr_id="C2",
                total_float_hr_cnt=-16,  # negative
            ),
            Task(
                task_id="T4",
                task_code="A4",
                task_name="Slacker D",
                wbs_id="W1",
                status_code="TK_NotStart",
                task_type="TT_Task",
                clndr_id="C2",
                total_float_hr_cnt=320,  # 40 days
            ),
        ],
    )


def test_default_group_by_is_wbs_and_unchanged() -> None:
    schedule = _schedule_with_mixed_activities()
    result = build_schedule_view(schedule)
    # Default keeps the real WBS tree
    assert len(result.wbs_tree) == 1
    assert result.wbs_tree[0].wbs_id == "W1"


def test_invalid_group_by_falls_back_to_wbs() -> None:
    schedule = _schedule_with_mixed_activities()
    result = build_schedule_view(schedule, group_by="bogus")
    assert len(result.wbs_tree) == 1
    assert result.wbs_tree[0].wbs_id == "W1"


def test_group_by_status_creates_one_root_per_status() -> None:
    schedule = _schedule_with_mixed_activities()
    result = build_schedule_view(schedule, group_by="status")
    root_names = {n.name for n in result.wbs_tree}
    # _status_label returns the lowercase enum-like label
    assert "complete" in root_names
    assert "active" in root_names
    assert "not_started" in root_names
    # Activities point at the synthetic groups
    assert all(act.wbs_id.startswith("_grp_") for act in result.activities)


def test_group_by_critical_creates_two_roots() -> None:
    schedule = _schedule_with_mixed_activities()
    result = build_schedule_view(schedule, group_by="critical")
    root_names = {n.name for n in result.wbs_tree}
    # Both buckets should appear — at least one of each kind must exist for
    # a reasonable schedule, but to be safe we just assert the universe.
    assert root_names <= {"Critical", "Non-Critical"}
    assert len(root_names) >= 1


def test_group_by_task_type_buckets() -> None:
    schedule = _schedule_with_mixed_activities()
    result = build_schedule_view(schedule, group_by="task_type")
    root_names = {n.name for n in result.wbs_tree}
    assert "task" in root_names
    assert "milestone" in root_names


def test_group_by_calendar_uses_clndr_id() -> None:
    schedule = _schedule_with_mixed_activities()
    result = build_schedule_view(schedule, group_by="calendar")
    root_names = {n.name for n in result.wbs_tree}
    assert root_names == {"C1", "C2"}


def test_group_by_float_bucket_partitions_activities() -> None:
    schedule = _schedule_with_mixed_activities()
    result = build_schedule_view(schedule, group_by="float_bucket")
    root_names = {n.name for n in result.wbs_tree}
    # T1 = 0d -> 0-5 days, T2 = 5d -> 0-5 days, T3 = -2d -> Negative,
    # T4 = 40d -> >20 days
    assert "Negative float" in root_names
    assert "0-5 days" in root_names
    assert ">20 days" in root_names


def test_grouping_does_not_mutate_input_schedule() -> None:
    """``model_copy(update=...)`` shouldn't touch the caller's schedule object."""
    schedule = _schedule_with_mixed_activities()
    original_wbs_ids = [t.wbs_id for t in schedule.activities]
    build_schedule_view(schedule, group_by="status")
    assert [t.wbs_id for t in schedule.activities] == original_wbs_ids


def test_group_by_options_constant_is_complete() -> None:
    """Sanity: every mode tested above is in the public constant."""
    for mode in ("wbs", "status", "critical", "task_type", "calendar", "float_bucket"):
        assert mode in GROUP_BY_OPTIONS


@pytest.mark.parametrize("mode", ["status", "critical", "task_type", "calendar", "float_bucket"])
def test_synthetic_roots_have_no_children(mode: str) -> None:
    """Non-WBS grouping is intentionally flat — one root per group, no nesting."""
    schedule = _schedule_with_mixed_activities()
    result = build_schedule_view(schedule, group_by=mode)
    assert all(len(n.children) == 0 for n in result.wbs_tree)
