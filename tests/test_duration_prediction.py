# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for ML duration prediction engine."""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

import pytest

from src.analytics.benchmarks import BenchmarkMetrics
from src.analytics.duration_prediction import (
    DurationPrediction,
    DurationPredictor,
    _HAS_SKLEARN,
    predict_duration,
)
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
                total_float_hr_cnt=40.0,
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
        ],
    )


def _make_benchmark_dataset(n: int = 30) -> list[BenchmarkMetrics]:
    """Generate synthetic benchmark data for training."""
    rng = random.Random(42)
    dataset = []
    for i in range(n):
        act_count = rng.randint(20, 2000)
        size = (
            "small"
            if act_count < 100
            else "medium"
            if act_count < 500
            else "large"
            if act_count < 2000
            else "mega"
        )
        duration = act_count * rng.uniform(0.3, 1.5) + rng.uniform(30, 200)
        dataset.append(
            BenchmarkMetrics(
                activity_count=act_count,
                relationship_count=int(act_count * rng.uniform(0.8, 1.5)),
                wbs_depth=rng.randint(2, 8),
                milestone_count=rng.randint(1, act_count // 10 + 1),
                size_category=size,
                dcma_score=rng.uniform(30, 95),
                logic_pct=rng.uniform(50, 100),
                constraint_pct=rng.uniform(0, 30),
                high_float_pct=rng.uniform(0, 50),
                negative_float_pct=rng.uniform(0, 20),
                high_duration_pct=rng.uniform(0, 30),
                relationship_fs_pct=rng.uniform(60, 100),
                lead_pct=rng.uniform(0, 10),
                lag_pct=rng.uniform(0, 20),
                bei=rng.uniform(0.5, 1.5),
                cpli=rng.uniform(0.7, 1.3),
                float_mean_days=rng.uniform(5, 50),
                float_median_days=rng.uniform(3, 40),
                float_stdev_days=rng.uniform(5, 30),
                relationship_density=rng.uniform(0.8, 2.0),
                critical_path_length=rng.randint(5, act_count // 5 + 1),
                cp_percentage=rng.uniform(5, 30),
                project_duration_days=duration,
                complete_pct=rng.uniform(0, 100),
                active_pct=rng.uniform(0, 50),
                not_started_pct=rng.uniform(0, 80),
            )
        )
    return dataset


@pytest.fixture
def benchmarks() -> list[BenchmarkMetrics]:
    return _make_benchmark_dataset(30)


@pytest.fixture
def schedule() -> ParsedSchedule:
    return _make_schedule()


# ===========================================================================
# Tests: DurationPredictor
# ===========================================================================


@pytest.mark.skipif(not _HAS_SKLEARN, reason="scikit-learn not installed")
class TestDurationPredictor:
    def test_init(self) -> None:
        model = DurationPredictor()
        assert not model.is_trained

    def test_train(self, benchmarks: list[BenchmarkMetrics]) -> None:
        model = DurationPredictor()
        info = model.train(benchmarks)
        assert model.is_trained
        assert info["samples"] == 30
        assert info["features"] == 28
        assert "r_squared" in info
        assert "feature_importances" in info

    def test_train_insufficient_data(self) -> None:
        model = DurationPredictor()
        with pytest.raises(ValueError, match="at least 10"):
            model.train([])

    def test_predict(self, benchmarks: list[BenchmarkMetrics]) -> None:
        model = DurationPredictor()
        model.train(benchmarks)
        pred = model.predict(benchmarks[0])
        assert pred > 0

    def test_predict_with_confidence(self, benchmarks: list[BenchmarkMetrics]) -> None:
        model = DurationPredictor()
        model.train(benchmarks)
        mean, low, high = model.predict_with_confidence(benchmarks[0])
        assert mean > 0
        assert low <= mean
        assert high >= low

    def test_feature_importances(self, benchmarks: list[BenchmarkMetrics]) -> None:
        model = DurationPredictor()
        model.train(benchmarks)
        imp = model.get_feature_importances()
        assert len(imp) == 28
        # Top feature should have > 0 importance
        assert list(imp.values())[0] > 0

    def test_predict_before_train(self) -> None:
        model = DurationPredictor()
        with pytest.raises(RuntimeError, match="not trained"):
            model.predict(BenchmarkMetrics())


# ===========================================================================
# Tests: predict_duration function
# ===========================================================================


@pytest.mark.skipif(not _HAS_SKLEARN, reason="scikit-learn not installed")
class TestPredictDuration:
    def test_returns_prediction(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        result = predict_duration(schedule, benchmarks)
        assert isinstance(result, DurationPrediction)
        assert result.predicted_duration_days > 0

    def test_has_confidence_interval(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        result = predict_duration(schedule, benchmarks)
        assert result.confidence_low > 0
        assert result.confidence_high >= result.confidence_low

    def test_has_actual_duration(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        result = predict_duration(schedule, benchmarks)
        assert result.actual_duration_days > 0

    def test_methodology_set(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        result = predict_duration(schedule, benchmarks)
        assert "ml" in result.methodology.lower() or "ensemble" in result.methodology.lower()
        assert "30" in result.methodology  # training samples

    def test_summary_keys(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        result = predict_duration(schedule, benchmarks)
        s = result.summary
        assert "predicted_duration_days" in s
        assert "confidence_interval" in s
        assert "model_r_squared" in s
        assert "references" in s

    def test_pretrained_model(
        self, schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        predictor = DurationPredictor()
        predictor.train(benchmarks)
        result = predict_duration(schedule, benchmarks, predictor=predictor)
        assert result.predicted_duration_days > 0

    def test_real_xer(
        self, real_schedule: ParsedSchedule, benchmarks: list[BenchmarkMetrics]
    ) -> None:
        result = predict_duration(real_schedule, benchmarks)
        assert result.predicted_duration_days > 0
        assert result.actual_duration_days > 0

    def test_empty_benchmarks(self, schedule: ParsedSchedule) -> None:
        result = predict_duration(schedule, [])
        assert "failed" in result.methodology.lower() or result.predicted_duration_days == 0
