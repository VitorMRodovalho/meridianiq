# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for schedule view layout engine."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.analytics.schedule_view import build_schedule_view
from src.parser.models import (
    Calendar,
    ParsedSchedule,
    Project,
    Relationship,
    Task,
    WBS,
)


def _date(offset: int = 0) -> datetime:
    base = datetime(2026, 1, 1)
    return base + timedelta(days=offset)


def _make_schedule() -> ParsedSchedule:
    """Create a small schedule with WBS hierarchy and relationships."""
    return ParsedSchedule(
        projects=[
            Project(
                proj_id="P1",
                proj_short_name="Test Project",
                last_recalc_date=_date(10),
                plan_start_date=_date(0),
            )
        ],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8, week_hr_cnt=40, default_flag="Y")],
        wbs_nodes=[
            WBS(
                wbs_id="W1",
                proj_id="P1",
                wbs_short_name="Root",
                wbs_name="Root",
                proj_node_flag="Y",
            ),
            WBS(
                wbs_id="W2",
                proj_id="P1",
                parent_wbs_id="W1",
                wbs_short_name="Phase1",
                wbs_name="Phase 1",
            ),
            WBS(
                wbs_id="W3",
                proj_id="P1",
                parent_wbs_id="W1",
                wbs_short_name="Phase2",
                wbs_name="Phase 2",
            ),
        ],
        activities=[
            Task(
                task_id="A100",
                proj_id="P1",
                wbs_id="W2",
                task_code="A100",
                task_name="Foundation",
                task_type="TT_Task",
                status_code="TK_Complete",
                early_start_date=_date(0),
                early_end_date=_date(10),
                target_drtn_hr_cnt=80,
                phys_complete_pct=100,
                total_float_hr_cnt=0,
            ),
            Task(
                task_id="A200",
                proj_id="P1",
                wbs_id="W2",
                task_code="A200",
                task_name="Framing",
                task_type="TT_Task",
                status_code="TK_Active",
                early_start_date=_date(10),
                early_end_date=_date(25),
                target_drtn_hr_cnt=120,
                remain_drtn_hr_cnt=60,
                phys_complete_pct=50,
                total_float_hr_cnt=0,
            ),
            Task(
                task_id="A300",
                proj_id="P1",
                wbs_id="W3",
                task_code="A300",
                task_name="Electrical",
                task_type="TT_Task",
                status_code="TK_NotStart",
                early_start_date=_date(20),
                early_end_date=_date(35),
                target_drtn_hr_cnt=120,
                remain_drtn_hr_cnt=120,
                phys_complete_pct=0,
                total_float_hr_cnt=40,
            ),
            Task(
                task_id="M100",
                proj_id="P1",
                wbs_id="W3",
                task_code="M100",
                task_name="Substantial Completion",
                task_type="TT_FinMile",
                status_code="TK_NotStart",
                early_start_date=_date(35),
                early_end_date=_date(35),
                target_drtn_hr_cnt=0,
                total_float_hr_cnt=0,
            ),
        ],
        relationships=[
            Relationship(task_id="A200", pred_task_id="A100", pred_type="PR_FS"),
            Relationship(task_id="A300", pred_task_id="A200", pred_type="PR_FS", lag_hr_cnt=16),
            Relationship(task_id="M100", pred_task_id="A300", pred_type="PR_FS"),
        ],
    )


class TestScheduleView:
    def test_basic_output_structure(self) -> None:
        result = build_schedule_view(_make_schedule())
        assert result.project_name == "Test Project"
        assert result.data_date != ""
        assert result.project_start != ""
        assert result.project_finish != ""
        assert len(result.activities) == 4
        assert len(result.relationships) == 3
        assert len(result.wbs_tree) >= 1

    def test_wbs_tree_hierarchy(self) -> None:
        result = build_schedule_view(_make_schedule())
        root = result.wbs_tree[0]
        assert root.name in ("Root", "Root")
        assert len(root.children) == 2

    def test_activity_sorting_by_wbs(self) -> None:
        result = build_schedule_view(_make_schedule())
        wbs_ids = [a.wbs_id for a in result.activities]
        # Phase1 (W2) activities should come before Phase2 (W3)
        w2_indices = [i for i, w in enumerate(wbs_ids) if w == "W2"]
        w3_indices = [i for i, w in enumerate(wbs_ids) if w == "W3"]
        assert max(w2_indices) < min(w3_indices)

    def test_activity_types(self) -> None:
        result = build_schedule_view(_make_schedule())
        types = {a.task_id: a.task_type for a in result.activities}
        assert types["A100"] == "task"
        assert types["M100"] == "milestone"

    def test_status_labels(self) -> None:
        result = build_schedule_view(_make_schedule())
        statuses = {a.task_id: a.status for a in result.activities}
        assert statuses["A100"] == "complete"
        assert statuses["A200"] == "active"
        assert statuses["A300"] == "not_started"

    def test_float_conversion(self) -> None:
        result = build_schedule_view(_make_schedule())
        a300 = next(a for a in result.activities if a.task_id == "A300")
        assert a300.total_float_days == 5.0  # 40h / 8h = 5 days

    def test_relationship_type_normalization(self) -> None:
        result = build_schedule_view(_make_schedule())
        types = [r.type for r in result.relationships]
        assert all(t in ("FS", "FF", "SS", "SF") for t in types)
        assert "PR_FS" not in types  # PR_ prefix stripped

    def test_relationship_lag(self) -> None:
        result = build_schedule_view(_make_schedule())
        lag_rel = next(r for r in result.relationships if r.from_id == "A200" and r.to_id == "A300")
        assert lag_rel.lag_days == 2.0  # 16h / 8h = 2 days

    def test_summary_counts(self) -> None:
        result = build_schedule_view(_make_schedule())
        assert result.summary["total_activities"] == 4
        assert result.summary["milestones_count"] == 1
        assert result.summary["complete_pct"] == 25.0  # 1 of 4

    def test_indent_levels(self) -> None:
        result = build_schedule_view(_make_schedule())
        for a in result.activities:
            assert a.indent_level >= 0

    def test_baseline_comparison(self) -> None:
        schedule = _make_schedule()
        baseline = _make_schedule()
        # Shift baseline earlier
        for t in baseline.activities:
            if t.early_start_date:
                t.early_start_date = t.early_start_date - timedelta(days=5)
            if t.early_end_date:
                t.early_end_date = t.early_end_date - timedelta(days=5)

        result = build_schedule_view(schedule, baseline=baseline)
        # At least some activities should have baseline dates
        with_baseline = [a for a in result.activities if a.baseline_start is not None]
        assert len(with_baseline) > 0

    def test_alerts_generated(self) -> None:
        schedule = _make_schedule()
        # Add negative float to trigger alert
        for t in schedule.activities:
            if t.task_id == "A200":
                t.total_float_hr_cnt = -16.0  # -2 days
        result = build_schedule_view(schedule)
        a200 = next(a for a in result.activities if a.task_id == "A200")
        assert "negative_float" in a200.alerts

    def test_empty_schedule(self) -> None:
        schedule = ParsedSchedule()
        result = build_schedule_view(schedule)
        assert len(result.activities) == 0
        assert result.summary["total_activities"] == 0
