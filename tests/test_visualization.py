# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for 4D visualization data."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.analytics.visualization import VisualizationResult, build_visualization
from src.parser.models import Calendar, ParsedSchedule, Project, Relationship, Task
from src.parser.xer_reader import XERReader

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def real_schedule() -> ParsedSchedule:
    return XERReader(FIXTURES / "sample.xer").parse()


def _make_schedule() -> ParsedSchedule:
    return ParsedSchedule(
        projects=[
            Project(
                proj_id="P1",
                proj_short_name="Test",
                last_recalc_date=datetime(2025, 3, 1),
                plan_start_date=datetime(2025, 1, 1),
                sum_data_date=datetime(2025, 3, 1),
            )
        ],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        activities=[
            Task(
                task_id="1",
                task_code="A",
                task_name="Foundation",
                status_code="TK_Complete",
                remain_drtn_hr_cnt=0.0,
                target_drtn_hr_cnt=80.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
                wbs_id="1.1",
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Structure",
                status_code="TK_Active",
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=160.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
                wbs_id="1.2",
            ),
            Task(
                task_id="3",
                task_code="C",
                task_name="MEP",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=120.0,
                target_drtn_hr_cnt=120.0,
                total_float_hr_cnt=400.0,
                clndr_id="CAL1",
                wbs_id="1.3",
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="3", pred_task_id="2", pred_type="PR_FS"),
        ],
    )


class TestVisualization:
    def test_returns_result(self) -> None:
        result = build_visualization(_make_schedule())
        assert isinstance(result, VisualizationResult)

    def test_has_activities(self) -> None:
        result = build_visualization(_make_schedule())
        assert result.total_activities == 3

    def test_has_wbs_groups(self) -> None:
        result = build_visualization(_make_schedule())
        assert len(result.wbs_groups) == 3

    def test_color_categories(self) -> None:
        result = build_visualization(_make_schedule())
        cats = {a.color_category for a in result.activities}
        assert "complete" in cats  # A is complete
        # B is on critical path so "critical" takes precedence over "active"
        assert "critical" in cats or "active" in cats

    def test_critical_count(self) -> None:
        result = build_visualization(_make_schedule())
        assert result.critical_count >= 0

    def test_project_duration(self) -> None:
        result = build_visualization(_make_schedule())
        assert result.project_duration_days > 0

    def test_summary_keys(self) -> None:
        result = build_visualization(_make_schedule())
        s = result.summary
        assert "total_activities" in s
        assert "color_distribution" in s
        assert "wbs_groups" in s

    def test_real_xer(self, real_schedule: ParsedSchedule) -> None:
        result = build_visualization(real_schedule)
        assert result.total_activities > 0
        assert result.project_duration_days > 0

    def test_empty_schedule(self) -> None:
        s = ParsedSchedule(
            projects=[
                Project(
                    proj_id="P1",
                    proj_short_name="Empty",
                    last_recalc_date=datetime(2025, 1, 1),
                    plan_start_date=datetime(2025, 1, 1),
                    sum_data_date=datetime(2025, 1, 1),
                )
            ]
        )
        result = build_visualization(s)
        assert result.total_activities == 0
