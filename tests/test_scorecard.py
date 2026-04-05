# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the schedule scorecard engine."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.analytics.scorecard import ScorecardResult, calculate_scorecard
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


def _make_healthy_schedule() -> ParsedSchedule:
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
                phys_complete_pct=50.0,
                total_float_hr_cnt=40.0,
                clndr_id="CAL1",
                wbs_id="1.1",
                early_start_date=datetime(2025, 1, 1),
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Structure",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=160.0,
                target_drtn_hr_cnt=160.0,
                total_float_hr_cnt=80.0,
                clndr_id="CAL1",
                wbs_id="1.2",
                early_start_date=datetime(2025, 2, 1),
            ),
            Task(
                task_id="3",
                task_code="C",
                task_name="MEP",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=120.0,
                target_drtn_hr_cnt=120.0,
                total_float_hr_cnt=120.0,
                clndr_id="CAL1",
                wbs_id="1.3",
                early_start_date=datetime(2025, 3, 1),
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="3", pred_task_id="2", pred_type="PR_FS"),
        ],
    )


@pytest.fixture
def healthy() -> ParsedSchedule:
    return _make_healthy_schedule()


# ===========================================================================
# Tests: Basic Structure
# ===========================================================================


class TestBasicStructure:
    def test_returns_result(self, healthy: ParsedSchedule) -> None:
        result = calculate_scorecard(healthy)
        assert isinstance(result, ScorecardResult)

    def test_has_five_dimensions(self, healthy: ParsedSchedule) -> None:
        result = calculate_scorecard(healthy)
        assert len(result.dimensions) == 5
        names = {d.name for d in result.dimensions}
        assert names == {"Validation", "Health", "Risk", "Logic", "Completeness"}

    def test_overall_score_bounded(self, healthy: ParsedSchedule) -> None:
        result = calculate_scorecard(healthy)
        assert 0 <= result.overall_score <= 100

    def test_overall_grade_valid(self, healthy: ParsedSchedule) -> None:
        result = calculate_scorecard(healthy)
        assert result.overall_grade in {"A", "B", "C", "D", "F"}

    def test_dimension_scores_bounded(self, healthy: ParsedSchedule) -> None:
        result = calculate_scorecard(healthy)
        for d in result.dimensions:
            assert 0 <= d.score <= 100
            assert d.grade in {"A", "B", "C", "D", "F"}

    def test_methodology_set(self, healthy: ParsedSchedule) -> None:
        result = calculate_scorecard(healthy)
        assert "weighted" in result.methodology.lower()


# ===========================================================================
# Tests: Grade Boundaries
# ===========================================================================


class TestGradeBoundaries:
    def test_grade_a(self) -> None:
        from src.analytics.scorecard import _score_to_grade

        assert _score_to_grade(95) == "A"
        assert _score_to_grade(90) == "A"

    def test_grade_b(self) -> None:
        from src.analytics.scorecard import _score_to_grade

        assert _score_to_grade(85) == "B"
        assert _score_to_grade(80) == "B"

    def test_grade_c(self) -> None:
        from src.analytics.scorecard import _score_to_grade

        assert _score_to_grade(75) == "C"

    def test_grade_d(self) -> None:
        from src.analytics.scorecard import _score_to_grade

        assert _score_to_grade(65) == "D"

    def test_grade_f(self) -> None:
        from src.analytics.scorecard import _score_to_grade

        assert _score_to_grade(55) == "F"
        assert _score_to_grade(0) == "F"


# ===========================================================================
# Tests: Recommendations
# ===========================================================================


class TestRecommendations:
    def test_has_recommendations(self, healthy: ParsedSchedule) -> None:
        result = calculate_scorecard(healthy)
        assert len(result.recommendations) > 0

    def test_perfect_schedule_gets_positive_rec(self) -> None:
        """A schedule that scores well should get positive feedback."""
        from src.analytics.scorecard import ScorecardDimension, _generate_recommendations

        dims = [
            ScorecardDimension(name="Validation", score=95, grade="A"),
            ScorecardDimension(name="Health", score=92, grade="A"),
            ScorecardDimension(name="Risk", score=88, grade="B"),
            ScorecardDimension(name="Logic", score=91, grade="A"),
            ScorecardDimension(name="Completeness", score=95, grade="A"),
        ]
        recs = _generate_recommendations(dims)
        assert any("maintain" in r.lower() for r in recs)


# ===========================================================================
# Tests: Summary
# ===========================================================================


class TestSummary:
    def test_summary_keys(self, healthy: ParsedSchedule) -> None:
        result = calculate_scorecard(healthy)
        s = result.summary
        assert "overall_score" in s
        assert "overall_grade" in s
        assert "dimensions" in s
        assert "methodology" in s
        assert "references" in s

    def test_summary_dimensions_match(self, healthy: ParsedSchedule) -> None:
        result = calculate_scorecard(healthy)
        assert len(result.summary["dimensions"]) == 5


# ===========================================================================
# Tests: Real XER
# ===========================================================================


class TestRealXER:
    def test_scorecard_real(self, real_schedule: ParsedSchedule) -> None:
        result = calculate_scorecard(real_schedule)
        assert result.overall_score > 0
        assert len(result.dimensions) == 5
        assert result.overall_grade in {"A", "B", "C", "D", "F"}

    def test_real_has_recommendations(self, real_schedule: ParsedSchedule) -> None:
        result = calculate_scorecard(real_schedule)
        assert len(result.recommendations) > 0


# ===========================================================================
# Tests: Edge Cases
# ===========================================================================


class TestEdgeCases:
    def test_empty_schedule(self) -> None:
        s = ParsedSchedule(projects=[_make_project()])
        result = calculate_scorecard(s)
        assert result.overall_score >= 0
        assert len(result.dimensions) == 5

    def test_single_activity(self) -> None:
        s = ParsedSchedule(
            projects=[_make_project()],
            activities=[
                Task(
                    task_id="1",
                    task_code="X",
                    task_name="Solo",
                    status_code="TK_Active",
                    remain_drtn_hr_cnt=80.0,
                    target_drtn_hr_cnt=80.0,
                    total_float_hr_cnt=0.0,
                    clndr_id="CAL1",
                )
            ],
        )
        result = calculate_scorecard(s)
        assert isinstance(result, ScorecardResult)
