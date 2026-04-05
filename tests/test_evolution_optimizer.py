# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the Evolution Strategies optimizer."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.analytics.evolution_optimizer import (
    EvolutionConfig,
    OptimizationResult,
    optimize_schedule,
)
from src.analytics.resource_leveling import ResourceLimit
from src.parser.models import (
    Calendar,
    ParsedSchedule,
    Project,
    Relationship,
    Resource,
    Task,
    TaskResource,
)


def _make_project() -> Project:
    return Project(
        proj_id="P1",
        proj_short_name="Test",
        last_recalc_date=datetime(2025, 3, 1),
        plan_start_date=datetime(2025, 1, 1),
        sum_data_date=datetime(2025, 3, 1),
    )


def _make_resource_schedule() -> ParsedSchedule:
    """Schedule with resource conflicts for optimization."""
    return ParsedSchedule(
        projects=[_make_project()],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        resources=[Resource(rsrc_id="R1", rsrc_name="Crane")],
        activities=[
            Task(
                task_id="1",
                task_code="A",
                task_name="Task A",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=80.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Task B",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=80.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="3",
                task_code="C",
                task_name="Task C",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=40.0,
                target_drtn_hr_cnt=40.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="4",
                task_code="D",
                task_name="Task D",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=40.0,
                target_drtn_hr_cnt=40.0,
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="3", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="4", pred_task_id="2", pred_type="PR_FS"),
            Relationship(task_id="4", pred_task_id="3", pred_type="PR_FS"),
        ],
        task_resources=[
            TaskResource(task_id="1", rsrc_id="R1", target_qty=1.0, remain_qty=1.0),
            TaskResource(task_id="2", rsrc_id="R1", target_qty=1.0, remain_qty=1.0),
            TaskResource(task_id="3", rsrc_id="R1", target_qty=1.0, remain_qty=1.0),
        ],
    )


@pytest.fixture
def schedule() -> ParsedSchedule:
    return _make_resource_schedule()


class TestEvolutionOptimizer:
    def test_returns_result(self, schedule: ParsedSchedule) -> None:
        config = EvolutionConfig(
            population_size=5,
            parent_size=2,
            generations=3,
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
        )
        result = optimize_schedule(schedule, config)
        assert isinstance(result, OptimizationResult)

    def test_finds_duration(self, schedule: ParsedSchedule) -> None:
        config = EvolutionConfig(
            population_size=5,
            parent_size=2,
            generations=3,
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
        )
        result = optimize_schedule(schedule, config)
        assert result.best_duration_days > 0
        assert result.greedy_duration_days > 0

    def test_improvement_non_negative(self, schedule: ParsedSchedule) -> None:
        config = EvolutionConfig(
            population_size=10,
            parent_size=3,
            generations=10,
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
        )
        result = optimize_schedule(schedule, config)
        assert result.improvement_days >= 0
        assert result.best_duration_days <= result.greedy_duration_days

    def test_convergence_history(self, schedule: ParsedSchedule) -> None:
        config = EvolutionConfig(
            population_size=5,
            parent_size=2,
            generations=5,
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
        )
        result = optimize_schedule(schedule, config)
        assert len(result.convergence_history) == 6  # initial + 5 generations

    def test_convergence_monotonic(self, schedule: ParsedSchedule) -> None:
        """Best fitness should never worsen across generations."""
        config = EvolutionConfig(
            population_size=10,
            parent_size=3,
            generations=10,
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
        )
        result = optimize_schedule(schedule, config)
        for i in range(1, len(result.convergence_history)):
            assert result.convergence_history[i] <= result.convergence_history[i - 1]

    def test_no_limits_returns_cpm(self, schedule: ParsedSchedule) -> None:
        config = EvolutionConfig(population_size=5, parent_size=2, generations=3)
        result = optimize_schedule(schedule, config)
        assert "unconstrained" in result.methodology.lower()

    def test_has_best_leveling(self, schedule: ParsedSchedule) -> None:
        config = EvolutionConfig(
            population_size=5,
            parent_size=2,
            generations=3,
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
        )
        result = optimize_schedule(schedule, config)
        assert result.best_leveling is not None

    def test_methodology_set(self, schedule: ParsedSchedule) -> None:
        config = EvolutionConfig(
            population_size=5,
            parent_size=2,
            generations=3,
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
        )
        result = optimize_schedule(schedule, config)
        assert "evolution" in result.methodology.lower()

    def test_summary_keys(self, schedule: ParsedSchedule) -> None:
        config = EvolutionConfig(
            population_size=5,
            parent_size=2,
            generations=3,
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
        )
        result = optimize_schedule(schedule, config)
        s = result.summary
        assert "best_duration_days" in s
        assert "improvement_pct" in s
        assert "references" in s

    def test_reproducible_with_seed(self, schedule: ParsedSchedule) -> None:
        config = EvolutionConfig(
            population_size=5,
            parent_size=2,
            generations=5,
            seed=42,
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
        )
        r1 = optimize_schedule(schedule, config)
        r2 = optimize_schedule(schedule, config)
        assert r1.best_duration_days == r2.best_duration_days
