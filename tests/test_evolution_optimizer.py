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


class TestProgressCallback:
    """Contract tests for the ``progress_callback`` hook added in W5/W6 of
    Cycle 1 v4.0 (pre-committed fallback branch per ADR-0009 Amendment 2).
    """

    def _small_config(self, **overrides: int) -> EvolutionConfig:
        defaults = {
            "population_size": 3,
            "parent_size": 2,
            "generations": 2,
            "resource_limits": [ResourceLimit(rsrc_id="R1", max_units=1.0)],
            "priority_rules": ["late_start", "early_start", "float", "duration"],
        }
        defaults.update(overrides)
        return EvolutionConfig(**defaults)  # type: ignore[arg-type]

    def test_callback_not_invoked_when_none(self, schedule: ParsedSchedule) -> None:
        """Default omission path MUST NOT raise or change behaviour."""
        config = self._small_config()
        result = optimize_schedule(schedule, config, progress_callback=None)
        assert result.best_duration_days > 0

    def test_callback_total_matches_formula(self, schedule: ParsedSchedule) -> None:
        """``total`` field equals ``len(priority_rules) + generations * population_size``."""
        config = self._small_config(generations=2, population_size=3)
        expected_total = len(config.priority_rules) + config.generations * config.population_size

        events: list[tuple[int, int]] = []

        def cb(done: int, total: int) -> None:
            events.append((done, total))

        optimize_schedule(schedule, config, progress_callback=cb)

        assert events, "callback never fired"
        for _, total in events:
            assert total == expected_total

    def test_callback_monotonic_and_bounded(self, schedule: ParsedSchedule) -> None:
        """``done`` is non-decreasing and never exceeds ``total``."""
        config = self._small_config(generations=3, population_size=4)
        events: list[tuple[int, int]] = []

        def cb(done: int, total: int) -> None:
            events.append((done, total))

        optimize_schedule(schedule, config, progress_callback=cb)

        assert events
        last_done = 0
        for done, total in events:
            assert done >= last_done, f"progress regressed: {last_done} -> {done}"
            assert done <= total, f"done {done} exceeded total {total}"
            last_done = done

    def test_callback_final_call_reaches_total(self, schedule: ParsedSchedule) -> None:
        """Last emission is exactly ``(total, total)``, even when the per-step
        cadence would otherwise skip the last frame."""
        config = self._small_config(generations=2, population_size=3)
        events: list[tuple[int, int]] = []

        def cb(done: int, total: int) -> None:
            events.append((done, total))

        optimize_schedule(schedule, config, progress_callback=cb)

        last_done, last_total = events[-1]
        assert last_done == last_total
        assert last_total == len(config.priority_rules) + (
            config.generations * config.population_size
        )

    def test_callback_no_emission_on_unconstrained_path(self, schedule: ParsedSchedule) -> None:
        """The early-return branch (no resource_limits) performs no heavy
        work units, so it MUST NOT fire the callback."""
        config = EvolutionConfig(population_size=5, parent_size=2, generations=3)
        events: list[tuple[int, int]] = []

        def cb(done: int, total: int) -> None:
            events.append((done, total))

        result = optimize_schedule(schedule, config, progress_callback=cb)

        assert events == []
        assert "unconstrained" in result.methodology.lower()

    def test_callback_result_identical_with_and_without(self, schedule: ParsedSchedule) -> None:
        """Observing progress MUST NOT alter the optimisation outcome — same
        seed, same config, same best_duration with or without callback."""
        config = self._small_config(generations=3, population_size=4)

        r_no_cb = optimize_schedule(schedule, config)

        def cb(_done: int, _total: int) -> None:  # noqa: ARG001
            pass

        r_cb = optimize_schedule(schedule, config, progress_callback=cb)

        assert r_cb.best_duration_days == r_no_cb.best_duration_days
        assert r_cb.generations_run == r_no_cb.generations_run

    def test_callback_emits_intermediate_frames(self, schedule: ParsedSchedule) -> None:
        """The in-loop cadence path MUST fire at least one frame with
        ``done < total``. Proves the `% progress_step` branch is live code
        — a regression that silently strips intermediate emissions and
        only leaves the final `(total, total)` frame would be invisible
        to the other tests (end-of-wave backend-review P1).
        """
        # n=4+3*4=16 → progress_step = max(1, 16//100) = 1 → every eval
        # emits in the loop AND the final guarantee fires.
        config = self._small_config(generations=3, population_size=4)
        events: list[tuple[int, int]] = []

        def cb(done: int, total: int) -> None:
            events.append((done, total))

        optimize_schedule(schedule, config, progress_callback=cb)

        mid_frames = [e for e in events if e[0] < e[1]]
        assert mid_frames, "no intermediate cadence frames emitted — in-loop emission is dead"
        # Bounded: at most one frame per work unit + one final guarantee.
        expected_total = len(config.priority_rules) + (config.generations * config.population_size)
        assert len(events) <= expected_total + 1
