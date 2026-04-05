# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for benchmark-derived Monte Carlo priors."""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

import pytest

from src.analytics.benchmark_priors import (
    PriorConfig,
    PriorResult,
    generate_benchmark_priors,
)
from src.analytics.benchmarks import BenchmarkMetrics
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
                total_float_hr_cnt=40.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="3",
                task_code="C",
                task_name="Done",
                status_code="TK_Complete",
                remain_drtn_hr_cnt=0.0,
                target_drtn_hr_cnt=80.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
        ],
    )


def _make_benchmarks(n: int = 20) -> list[BenchmarkMetrics]:
    rng = random.Random(42)
    return [
        BenchmarkMetrics(
            activity_count=rng.randint(50, 500),
            relationship_count=rng.randint(40, 400),
            size_category="medium",
            project_duration_days=rng.uniform(100, 500),
            dcma_score=rng.uniform(40, 90),
        )
        for _ in range(n)
    ]


@pytest.fixture
def schedule() -> ParsedSchedule:
    return _make_schedule()


@pytest.fixture
def benchmarks() -> list[BenchmarkMetrics]:
    return _make_benchmarks()


class TestBenchmarkPriors:
    def test_returns_result(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        result = generate_benchmark_priors(schedule, benchmarks)
        assert isinstance(result, PriorResult)

    def test_generates_risks(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        result = generate_benchmark_priors(schedule, benchmarks)
        assert result.activities_covered == 2  # A and B (C is complete)
        assert len(result.duration_risks) == 2

    def test_skips_complete(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        result = generate_benchmark_priors(schedule, benchmarks)
        ids = {r.activity_id for r in result.duration_risks}
        assert "C" not in ids

    def test_pert_distribution(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        result = generate_benchmark_priors(schedule, benchmarks)
        for risk in result.duration_risks:
            assert risk.min_duration < risk.most_likely
            assert risk.most_likely < risk.max_duration

    def test_asymmetric_range(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        """Upside risk should be larger than downside."""
        result = generate_benchmark_priors(schedule, benchmarks)
        for risk in result.duration_risks:
            downside = risk.most_likely - risk.min_duration
            upside = risk.max_duration - risk.most_likely
            assert upside >= downside

    def test_methodology_set(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        result = generate_benchmark_priors(schedule, benchmarks)
        assert "benchmark" in result.methodology.lower()
        assert "aace" in result.methodology.lower()

    def test_no_benchmarks_uses_default(self, schedule: ParsedSchedule) -> None:
        result = generate_benchmark_priors(schedule, [])
        assert result.activities_covered == 2
        assert "default" in result.methodology.lower()

    def test_prior_weight_affects_uncertainty(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        low = generate_benchmark_priors(schedule, benchmarks, PriorConfig(prior_weight=0.1))
        high = generate_benchmark_priors(schedule, benchmarks, PriorConfig(prior_weight=0.9))
        # Different weights should produce different uncertainties
        assert low.avg_uncertainty != high.avg_uncertainty

    def test_integrates_with_monte_carlo(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        """Generated priors should work with the Monte Carlo simulator."""
        from src.analytics.risk import MonteCarloSimulator, SimulationConfig

        priors = generate_benchmark_priors(schedule, benchmarks)
        sim = MonteCarloSimulator(schedule, SimulationConfig(iterations=50, seed=42))
        result = sim.simulate(duration_risks=priors.duration_risks)
        assert result.iterations == 50
        assert result.mean_days > 0


class TestRealXER:
    def test_real_schedule_priors(self, real_schedule: ParsedSchedule) -> None:
        benchmarks = _make_benchmarks(30)
        result = generate_benchmark_priors(real_schedule, benchmarks)
        assert result.activities_covered > 0
        assert len(result.duration_risks) > 0
