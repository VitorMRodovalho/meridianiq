# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the delay prediction engine.

Verifies feature extraction, risk scoring, risk factor explanations,
project-level aggregation, and baseline trend enhancement.
"""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

import pytest

from src.analytics.delay_prediction import (
    DelayPredictionResult,
    MLDelayModel,
    _HAS_SKLEARN,
    predict_delays,
)
from src.parser.models import (
    Calendar,
    ParsedSchedule,
    Project,
    Relationship,
    Task,
)
from src.parser.xer_reader import XERReader

# ---------------------------------------------------------------------------
# Fixtures — real XER files
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def baseline() -> ParsedSchedule:
    return XERReader(FIXTURES / "sample.xer").parse()


@pytest.fixture(scope="module")
def update1() -> ParsedSchedule:
    return XERReader(FIXTURES / "sample_update.xer").parse()


# ---------------------------------------------------------------------------
# Fixtures — synthetic schedules
# ---------------------------------------------------------------------------


def _make_project() -> Project:
    return Project(
        proj_id="P1",
        proj_short_name="Test Project",
        last_recalc_date=datetime(2025, 3, 1),
        plan_start_date=datetime(2025, 1, 1),
        sum_data_date=datetime(2025, 3, 1),
    )


def _make_healthy_schedule() -> ParsedSchedule:
    """Schedule with good health indicators — low risk expected."""
    return ParsedSchedule(
        projects=[_make_project()],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        activities=[
            Task(
                task_id="1",
                task_code="A",
                task_name="Foundation",
                status_code="TK_Complete",
                act_start_date=datetime(2025, 1, 1),
                act_end_date=datetime(2025, 1, 20),
                remain_drtn_hr_cnt=0.0,
                target_drtn_hr_cnt=120.0,
                phys_complete_pct=100.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Structure",
                status_code="TK_Active",
                act_start_date=datetime(2025, 1, 21),
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=160.0,
                phys_complete_pct=50.0,
                total_float_hr_cnt=80.0,  # 10 days — moderate float
                clndr_id="CAL1",
            ),
            Task(
                task_id="3",
                task_code="C",
                task_name="MEP",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=120.0,
                target_drtn_hr_cnt=120.0,
                phys_complete_pct=0.0,
                total_float_hr_cnt=160.0,  # 20 days — good float
                clndr_id="CAL1",
            ),
            Task(
                task_id="4",
                task_code="D",
                task_name="Finishes",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=80.0,
                phys_complete_pct=0.0,
                total_float_hr_cnt=240.0,  # 30 days — high float
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="3", pred_task_id="2", pred_type="PR_FS"),
            Relationship(task_id="4", pred_task_id="3", pred_type="PR_FS"),
        ],
    )


def _make_risky_schedule() -> ParsedSchedule:
    """Schedule with poor health — high risk expected."""
    return ParsedSchedule(
        projects=[_make_project()],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        activities=[
            Task(
                task_id="1",
                task_code="A",
                task_name="Foundation",
                status_code="TK_Active",
                act_start_date=datetime(2025, 1, 1),
                remain_drtn_hr_cnt=200.0,  # Way over original
                target_drtn_hr_cnt=120.0,
                phys_complete_pct=10.0,  # Very little progress
                total_float_hr_cnt=-40.0,  # Negative float!
                clndr_id="CAL1",
                cstr_type="CS_MSOA",  # Hard constraint
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Structure",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=800.0,  # Very long duration
                target_drtn_hr_cnt=800.0,
                phys_complete_pct=0.0,
                total_float_hr_cnt=-16.0,  # Negative float
                clndr_id="CAL1",
            ),
            Task(
                task_id="3",
                task_code="C",
                task_name="MEP (dangling)",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=120.0,
                target_drtn_hr_cnt=120.0,
                phys_complete_pct=0.0,
                total_float_hr_cnt=0.0,  # Zero float
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            # C has no relationships — dangling activity
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
        ],
    )


@pytest.fixture
def healthy_schedule() -> ParsedSchedule:
    return _make_healthy_schedule()


@pytest.fixture
def risky_schedule() -> ParsedSchedule:
    return _make_risky_schedule()


# ===========================================================================
# Tests: Basic Prediction
# ===========================================================================


class TestBasicPrediction:
    """Verify basic prediction works and returns correct structure."""

    def test_returns_result(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule)
        assert isinstance(result, DelayPredictionResult)

    def test_skips_complete_activities(self, healthy_schedule: ParsedSchedule) -> None:
        """Complete activities should not appear in risk results."""
        result = predict_delays(healthy_schedule)
        codes = {r.task_code for r in result.activity_risks}
        assert "A" not in codes  # A is TK_Complete
        assert "B" in codes
        assert "C" in codes
        assert "D" in codes

    def test_risk_scores_are_bounded(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule)
        for r in result.activity_risks:
            assert 0 <= r.risk_score <= 100

    def test_risk_levels_valid(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule)
        valid_levels = {"low", "medium", "high", "critical"}
        for r in result.activity_risks:
            assert r.risk_level in valid_levels

    def test_sorted_by_risk_descending(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule)
        scores = [r.risk_score for r in result.activity_risks]
        assert scores == sorted(scores, reverse=True)

    def test_project_level_score(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule)
        assert 0 <= result.project_risk_score <= 100
        assert result.project_risk_level in {"low", "medium", "high", "critical"}

    def test_risk_distribution(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule)
        total = sum(result.risk_distribution.values())
        assert total == len(result.activity_risks)

    def test_methodology_set(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule)
        assert "single schedule" in result.methodology.lower()
        assert result.has_baseline is False


# ===========================================================================
# Tests: Risk Scoring Quality
# ===========================================================================


class TestRiskScoringQuality:
    """Verify risk scores reflect schedule health correctly."""

    def test_risky_schedule_scores_higher(
        self, healthy_schedule: ParsedSchedule, risky_schedule: ParsedSchedule
    ) -> None:
        """Risky schedule should have higher project risk than healthy one."""
        healthy = predict_delays(healthy_schedule)
        risky = predict_delays(risky_schedule)
        assert risky.project_risk_score > healthy.project_risk_score

    def test_negative_float_high_risk(self, risky_schedule: ParsedSchedule) -> None:
        """Activities with negative float should be high/critical risk."""
        result = predict_delays(risky_schedule)
        risk_a = next(r for r in result.activity_risks if r.task_code == "A")
        assert risk_a.risk_level in ("high", "critical")
        assert risk_a.float_risk > 50

    def test_dangling_activity_flagged(self, risky_schedule: ParsedSchedule) -> None:
        """Activity with no relationships should have logic risk."""
        result = predict_delays(risky_schedule)
        risk_c = next(r for r in result.activity_risks if r.task_code == "C")
        assert risk_c.logic_risk > 30
        logic_factors = [f for f in risk_c.top_risk_factors if "open_ended" in f.name]
        assert len(logic_factors) > 0

    def test_very_long_duration_flagged(self, risky_schedule: ParsedSchedule) -> None:
        """Activity with very long duration should have duration risk."""
        result = predict_delays(risky_schedule)
        risk_b = next(r for r in result.activity_risks if r.task_code == "B")
        assert risk_b.duration_risk > 30

    def test_duration_overrun_flagged(self, risky_schedule: ParsedSchedule) -> None:
        """Activity with remaining > original should flag overrun."""
        result = predict_delays(risky_schedule)
        risk_a = next(r for r in result.activity_risks if r.task_code == "A")
        dur_factors = [f for f in risk_a.top_risk_factors if "duration_overrun" in f.name]
        assert len(dur_factors) > 0

    def test_predicted_delay_for_negative_float(self, risky_schedule: ParsedSchedule) -> None:
        """Activities with negative float should predict delay."""
        result = predict_delays(risky_schedule)
        risk_a = next(r for r in result.activity_risks if r.task_code == "A")
        assert risk_a.predicted_delay_days > 0


# ===========================================================================
# Tests: Risk Factors (Explainability)
# ===========================================================================


class TestRiskFactors:
    """Verify risk factor explanations are present and useful."""

    def test_factors_have_required_fields(self, risky_schedule: ParsedSchedule) -> None:
        result = predict_delays(risky_schedule)
        for risk in result.activity_risks:
            for factor in risk.top_risk_factors:
                assert factor.name
                assert 0 <= factor.contribution <= 1
                assert factor.description
                assert factor.value

    def test_factors_sorted_by_contribution(self, risky_schedule: ParsedSchedule) -> None:
        result = predict_delays(risky_schedule)
        for risk in result.activity_risks:
            contribs = [f.contribution for f in risk.top_risk_factors]
            assert contribs == sorted(contribs, reverse=True)

    def test_max_five_factors(self, risky_schedule: ParsedSchedule) -> None:
        result = predict_delays(risky_schedule)
        for risk in result.activity_risks:
            assert len(risk.top_risk_factors) <= 5


# ===========================================================================
# Tests: Baseline Enhancement
# ===========================================================================


class TestBaselineEnhancement:
    """Verify trend features improve prediction when baseline provided."""

    def test_has_baseline_flag(self, healthy_schedule: ParsedSchedule) -> None:
        baseline = copy.deepcopy(healthy_schedule)
        result = predict_delays(healthy_schedule, baseline=baseline)
        assert result.has_baseline is True
        assert "trend" in result.methodology.lower()

    def test_float_erosion_detected(self, healthy_schedule: ParsedSchedule) -> None:
        """Float erosion between baseline and update should increase risk."""
        baseline = copy.deepcopy(healthy_schedule)
        update = copy.deepcopy(healthy_schedule)
        # Erode float on activity B
        for t in update.activities:
            if t.task_code == "B":
                t.total_float_hr_cnt = 0.0  # Was 80h (10 days)

        result_no_base = predict_delays(update)
        result_with_base = predict_delays(update, baseline=baseline)

        risk_no = next(r for r in result_no_base.activity_risks if r.task_code == "B")
        risk_with = next(r for r in result_with_base.activity_risks if r.task_code == "B")
        assert risk_with.trend_risk > risk_no.trend_risk

    def test_constraint_addition_detected(self, healthy_schedule: ParsedSchedule) -> None:
        """New constraint should be flagged as trend risk."""
        baseline = copy.deepcopy(healthy_schedule)
        update = copy.deepcopy(healthy_schedule)
        for t in update.activities:
            if t.task_code == "C":
                t.cstr_type = "CS_MSOA"  # Add constraint

        result = predict_delays(update, baseline=baseline)
        risk_c = next(r for r in result.activity_risks if r.task_code == "C")
        constraint_factors = [f for f in risk_c.top_risk_factors if "constraint_added" in f.name]
        assert len(constraint_factors) > 0


# ===========================================================================
# Tests: Summary
# ===========================================================================


class TestSummary:
    """Verify summary contains expected keys."""

    def test_summary_keys(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule)
        s = result.summary
        assert "activities_analyzed" in s
        assert "project_risk_score" in s
        assert "risk_distribution" in s
        assert "methodology" in s
        assert "top_risk_activities" in s
        assert "references" in s
        assert s["activities_analyzed"] == 3  # 4 total minus 1 complete

    def test_top_risk_activities_limited(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule)
        assert len(result.summary["top_risk_activities"]) <= 10


# ===========================================================================
# Tests: Real XER Files
# ===========================================================================


class TestWithRealXER:
    """Integration tests with actual XER fixture files."""

    def test_predict_single_schedule(self, baseline: ParsedSchedule) -> None:
        result = predict_delays(baseline)
        assert len(result.activity_risks) > 0
        assert result.project_risk_score > 0
        assert result.summary["activities_analyzed"] > 0

    def test_predict_with_baseline(self, baseline: ParsedSchedule, update1: ParsedSchedule) -> None:
        result = predict_delays(update1, baseline=baseline)
        assert result.has_baseline is True
        assert len(result.activity_risks) > 0
        assert result.features_used == 35  # Trend features included

    def test_critical_path_activities_flagged(self, baseline: ParsedSchedule) -> None:
        result = predict_delays(baseline)
        cp_activities = [r for r in result.activity_risks if r.is_critical_path]
        assert len(cp_activities) > 0


# ===========================================================================
# Tests: Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Verify robustness for edge cases."""

    def test_empty_schedule(self) -> None:
        schedule = ParsedSchedule(projects=[_make_project()])
        result = predict_delays(schedule)
        assert len(result.activity_risks) == 0
        assert result.project_risk_score == 0

    def test_all_complete(self, healthy_schedule: ParsedSchedule) -> None:
        """All-complete schedule should produce no risks."""
        s = copy.deepcopy(healthy_schedule)
        for t in s.activities:
            t.status_code = "TK_Complete"
            t.remain_drtn_hr_cnt = 0.0
            t.phys_complete_pct = 100.0
        result = predict_delays(s)
        assert len(result.activity_risks) == 0

    def test_single_activity(self) -> None:
        schedule = ParsedSchedule(
            projects=[_make_project()],
            activities=[
                Task(
                    task_id="1",
                    task_code="X",
                    task_name="Solo",
                    status_code="TK_Active",
                    remain_drtn_hr_cnt=80.0,
                    target_drtn_hr_cnt=80.0,
                    phys_complete_pct=50.0,
                    total_float_hr_cnt=0.0,
                    clndr_id="CAL1",
                )
            ],
        )
        result = predict_delays(schedule)
        assert len(result.activity_risks) == 1
        assert result.activity_risks[0].task_code == "X"

    def test_no_relationships(self) -> None:
        """Schedule with no relationships — all activities dangling."""
        schedule = ParsedSchedule(
            projects=[_make_project()],
            activities=[
                Task(
                    task_id="1",
                    task_code="A",
                    task_name="First",
                    status_code="TK_NotStart",
                    remain_drtn_hr_cnt=40.0,
                    target_drtn_hr_cnt=40.0,
                    total_float_hr_cnt=80.0,
                    clndr_id="CAL1",
                ),
                Task(
                    task_id="2",
                    task_code="B",
                    task_name="Second",
                    status_code="TK_NotStart",
                    remain_drtn_hr_cnt=40.0,
                    target_drtn_hr_cnt=40.0,
                    total_float_hr_cnt=80.0,
                    clndr_id="CAL1",
                ),
            ],
        )
        result = predict_delays(schedule)
        # Both should have logic risk for being open-ended
        for r in result.activity_risks:
            assert r.logic_risk > 0

    def test_confidence_higher_with_baseline(self, healthy_schedule: ParsedSchedule) -> None:
        """Confidence should be higher when baseline is provided."""
        no_base = predict_delays(healthy_schedule)
        with_base = predict_delays(healthy_schedule, baseline=healthy_schedule)
        # Average confidence should be higher with baseline
        avg_no = sum(r.confidence for r in no_base.activity_risks) / max(
            len(no_base.activity_risks), 1
        )
        avg_with = sum(r.confidence for r in with_base.activity_risks) / max(
            len(with_base.activity_risks), 1
        )
        assert avg_with >= avg_no


# ===========================================================================
# Tests: ML Prediction (scikit-learn)
# ===========================================================================


@pytest.mark.skipif(not _HAS_SKLEARN, reason="scikit-learn not installed")
class TestMLPrediction:
    """Verify ML ensemble prediction mode."""

    def test_ml_returns_result(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule, model="ml")
        assert isinstance(result, DelayPredictionResult)
        assert len(result.activity_risks) > 0

    def test_ml_scores_bounded(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule, model="ml")
        for r in result.activity_risks:
            assert 0 <= r.risk_score <= 100

    def test_ml_risk_levels_valid(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule, model="ml")
        valid_levels = {"low", "medium", "high", "critical"}
        for r in result.activity_risks:
            assert r.risk_level in valid_levels

    def test_ml_methodology_set(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule, model="ml")
        assert "ml" in result.methodology.lower() or "ensemble" in result.methodology.lower()

    def test_ml_has_feature_importances(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule, model="ml")
        assert "feature_importances" in result.summary
        importances = result.summary["feature_importances"]
        assert len(importances) > 0
        assert all(v >= 0 for v in importances.values())

    def test_ml_sorted_descending(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule, model="ml")
        scores = [r.risk_score for r in result.activity_risks]
        assert scores == sorted(scores, reverse=True)

    def test_ml_risky_higher_than_healthy(
        self, healthy_schedule: ParsedSchedule, risky_schedule: ParsedSchedule
    ) -> None:
        """ML model should also rank risky schedule higher."""
        healthy = predict_delays(healthy_schedule, model="ml")
        risky = predict_delays(risky_schedule, model="ml")
        assert risky.project_risk_score > healthy.project_risk_score

    def test_ml_with_baseline(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule, baseline=healthy_schedule, model="ml")
        assert result.has_baseline is True
        assert result.features_used == 35

    def test_ml_confidence_higher_than_rules(
        self, healthy_schedule: ParsedSchedule
    ) -> None:
        """ML confidence base (0.7) should be >= rule-based (0.6)."""
        rules = predict_delays(healthy_schedule, model="rules")
        ml = predict_delays(healthy_schedule, model="ml")
        avg_rules = sum(r.confidence for r in rules.activity_risks) / max(
            len(rules.activity_risks), 1
        )
        avg_ml = sum(r.confidence for r in ml.activity_risks) / max(
            len(ml.activity_risks), 1
        )
        assert avg_ml >= avg_rules

    def test_ml_skips_complete(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule, model="ml")
        codes = {r.task_code for r in result.activity_risks}
        assert "A" not in codes

    def test_ml_real_xer(self, baseline: ParsedSchedule) -> None:
        """ML prediction works with real XER files."""
        result = predict_delays(baseline, model="ml")
        assert len(result.activity_risks) > 0
        assert result.project_risk_score > 0

    def test_ml_real_xer_with_baseline(
        self, baseline: ParsedSchedule, update1: ParsedSchedule
    ) -> None:
        result = predict_delays(update1, baseline=baseline, model="ml")
        assert result.has_baseline is True
        assert "ml" in result.methodology.lower() or "ensemble" in result.methodology.lower()


@pytest.mark.skipif(not _HAS_SKLEARN, reason="scikit-learn not installed")
class TestMLModel:
    """Test MLDelayModel class directly."""

    def test_model_init(self) -> None:
        model = MLDelayModel()
        assert not model.is_trained
        assert len(model.feature_names) == 30

    def test_model_train_requires_min_samples(self) -> None:
        model = MLDelayModel()
        with pytest.raises(ValueError, match="at least 10"):
            model.train([[]])

    def test_model_predict_before_train_fails(self) -> None:
        model = MLDelayModel()
        with pytest.raises(RuntimeError, match="not trained"):
            model.predict_batch([])

    def test_model_train_and_predict(self, risky_schedule: ParsedSchedule) -> None:
        """Train on risky schedule, predict on same."""
        from src.analytics.cpm import CPMCalculator
        from src.analytics.delay_prediction import _extract_features

        cpm = CPMCalculator(risky_schedule).calculate()
        features = _extract_features(risky_schedule, cpm)

        # Need enough samples — duplicate features
        big_features = features * 5  # 15 samples
        model = MLDelayModel()
        info = model.train([big_features])

        assert model.is_trained
        assert info["samples"] == 15
        assert info["features"] == 30
        assert "feature_importances" in info

        scores = model.predict_batch(features)
        assert len(scores) == len(features)
        for s in scores:
            assert 0 <= s <= 100

    def test_feature_importances(self, risky_schedule: ParsedSchedule) -> None:
        from src.analytics.cpm import CPMCalculator
        from src.analytics.delay_prediction import _extract_features

        cpm = CPMCalculator(risky_schedule).calculate()
        features = _extract_features(risky_schedule, cpm) * 5

        model = MLDelayModel()
        model.train([features])
        importances = model.get_feature_importances()

        assert len(importances) == 30
        assert all(isinstance(v, float) for v in importances.values())
        # Most important feature should have > 0 importance
        top_value = list(importances.values())[0]
        assert top_value > 0

    def test_pretrained_model_in_predict(
        self, healthy_schedule: ParsedSchedule, risky_schedule: ParsedSchedule
    ) -> None:
        """Pass pre-trained model to predict_delays."""
        from src.analytics.cpm import CPMCalculator
        from src.analytics.delay_prediction import _extract_features

        # Train on risky
        cpm = CPMCalculator(risky_schedule).calculate()
        features = _extract_features(risky_schedule, cpm) * 5
        model = MLDelayModel()
        model.train([features])

        # Predict on healthy with pre-trained model
        result = predict_delays(healthy_schedule, model="ml", ml_model=model)
        assert len(result.activity_risks) > 0
        assert "ml" in result.methodology.lower() or "ensemble" in result.methodology.lower()


class TestModelFallback:
    """Verify graceful fallback behavior."""

    def test_rules_is_default(self, healthy_schedule: ParsedSchedule) -> None:
        result = predict_delays(healthy_schedule)
        assert "rule-based" in result.methodology.lower()

    def test_invalid_model_uses_rules(self, healthy_schedule: ParsedSchedule) -> None:
        """Unknown model name falls back to rules."""
        result = predict_delays(healthy_schedule, model="unknown")
        assert "rule-based" in result.methodology.lower()
