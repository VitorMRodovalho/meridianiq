# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the time-cost Pareto analysis engine."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.analytics.pareto import (
    CostScenario,
    ParetoResult,
    analyze_pareto,
)
from src.analytics.whatif import DurationAdjustment
from src.parser.models import Calendar, ParsedSchedule, Project, Relationship, Task
from src.parser.xer_reader import XERReader

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def real_schedule() -> ParsedSchedule:
    return XERReader(FIXTURES / "sample.xer").parse()


def _make_project() -> Project:
    return Project(
        proj_id="P1",
        proj_short_name="Test",
        last_recalc_date=datetime(2025, 3, 1),
        plan_start_date=datetime(2025, 1, 1),
        sum_data_date=datetime(2025, 3, 1),
    )


def _make_schedule() -> ParsedSchedule:
    return ParsedSchedule(
        projects=[_make_project()],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        activities=[
            Task(
                task_id="1",
                task_code="A",
                task_name="Foundation",
                status_code="TK_Active",
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=80.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Structure",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=160.0,
                target_drtn_hr_cnt=160.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="3",
                task_code="C",
                task_name="Finishes",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=80.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="3", pred_task_id="2", pred_type="PR_FS"),
        ],
    )


@pytest.fixture
def schedule() -> ParsedSchedule:
    return _make_schedule()


class TestParetoBasic:
    def test_returns_result(self, schedule: ParsedSchedule) -> None:
        result = analyze_pareto(schedule, [], base_cost=1_000_000)
        assert isinstance(result, ParetoResult)

    def test_baseline_only(self, schedule: ParsedSchedule) -> None:
        result = analyze_pareto(schedule, [], base_cost=1_000_000)
        assert result.scenarios_evaluated == 1
        assert result.frontier_size == 1
        assert result.frontier[0].scenario_name == "Baseline"

    def test_multiple_scenarios(self, schedule: ParsedSchedule) -> None:
        scenarios = [
            CostScenario(
                name="Crash B",
                adjustments=[DurationAdjustment(target="B", pct_change=-0.30)],
                cost_delta=200_000,
            ),
            CostScenario(
                name="Crash All",
                adjustments=[DurationAdjustment(target="*", pct_change=-0.20)],
                cost_delta=500_000,
            ),
            CostScenario(
                name="Extend All",
                adjustments=[DurationAdjustment(target="*", pct_change=0.20)],
                cost_delta=-100_000,
            ),
        ]
        result = analyze_pareto(schedule, scenarios, base_cost=1_000_000)
        assert result.scenarios_evaluated == 4  # 3 + baseline
        assert len(result.all_points) == 4

    def test_frontier_is_subset(self, schedule: ParsedSchedule) -> None:
        scenarios = [
            CostScenario(
                name="Crash",
                adjustments=[DurationAdjustment(target="B", pct_change=-0.50)],
                cost_delta=300_000,
            ),
            CostScenario(
                name="Save",
                adjustments=[DurationAdjustment(target="*", pct_change=0.30)],
                cost_delta=-200_000,
            ),
        ]
        result = analyze_pareto(schedule, scenarios, base_cost=1_000_000)
        assert result.frontier_size <= result.scenarios_evaluated
        for p in result.frontier:
            assert p.is_pareto_optimal is True

    def test_frontier_sorted_by_duration(self, schedule: ParsedSchedule) -> None:
        scenarios = [
            CostScenario(
                name="A",
                adjustments=[DurationAdjustment(target="B", pct_change=-0.50)],
                cost_delta=500_000,
            ),
            CostScenario(
                name="B",
                adjustments=[DurationAdjustment(target="*", pct_change=0.50)],
                cost_delta=-300_000,
            ),
        ]
        result = analyze_pareto(schedule, scenarios, base_cost=1_000_000)
        durations = [p.duration_days for p in result.frontier]
        assert durations == sorted(durations)

    def test_methodology_set(self, schedule: ParsedSchedule) -> None:
        result = analyze_pareto(schedule, [], base_cost=0)
        assert "pareto" in result.methodology.lower()

    def test_summary_keys(self, schedule: ParsedSchedule) -> None:
        result = analyze_pareto(schedule, [], base_cost=0)
        s = result.summary
        assert "base_duration_days" in s
        assert "frontier" in s
        assert "references" in s


class TestParetoFrontier:
    def test_dominated_point_excluded(self, schedule: ParsedSchedule) -> None:
        """A point that is worse in both time and cost should not be on frontier."""
        scenarios = [
            CostScenario(
                name="Better",
                adjustments=[DurationAdjustment(target="B", pct_change=-0.30)],
                cost_delta=-50_000,  # Faster AND cheaper
            ),
            CostScenario(
                name="Worse",
                adjustments=[DurationAdjustment(target="B", pct_change=0.30)],
                cost_delta=50_000,  # Slower AND more expensive
            ),
        ]
        result = analyze_pareto(schedule, scenarios, base_cost=1_000_000)
        frontier_names = {p.scenario_name for p in result.frontier}
        assert "Better" in frontier_names
        # "Worse" is dominated by Baseline (same duration, lower cost) or Better


class TestRealXER:
    def test_pareto_real(self, real_schedule: ParsedSchedule) -> None:
        scenarios = [
            CostScenario(
                name="Crash 20%",
                adjustments=[DurationAdjustment(target="*", pct_change=-0.20)],
                cost_delta=500_000,
            ),
            CostScenario(
                name="Extend 20%",
                adjustments=[DurationAdjustment(target="*", pct_change=0.20)],
                cost_delta=-200_000,
            ),
        ]
        result = analyze_pareto(real_schedule, scenarios, base_cost=5_000_000)
        assert result.scenarios_evaluated == 3
        assert result.frontier_size >= 1
