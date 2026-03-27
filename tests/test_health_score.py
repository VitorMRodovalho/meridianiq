# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the composite schedule health score calculator."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.analytics.health_score import HealthScore, HealthScoreCalculator
from src.parser import ParsedSchedule, XERReader

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XER = FIXTURES / "sample.xer"
SAMPLE_UPDATE_XER = FIXTURES / "sample_update.xer"


@pytest.fixture(scope="module")
def baseline() -> ParsedSchedule:
    """Parse the baseline sample XER."""
    return XERReader(SAMPLE_XER).parse()


@pytest.fixture(scope="module")
def update() -> ParsedSchedule:
    """Parse the update sample XER."""
    return XERReader(SAMPLE_UPDATE_XER).parse()


@pytest.fixture(scope="module")
def health_single(baseline: ParsedSchedule) -> HealthScore:
    """Health score for a single schedule (no trend)."""
    return HealthScoreCalculator(baseline).calculate()


@pytest.fixture(scope="module")
def health_with_trend(baseline: ParsedSchedule, update: ParsedSchedule) -> HealthScore:
    """Health score with trend from baseline to update."""
    return HealthScoreCalculator(update, baseline=baseline).calculate()


class TestHealthScoreBasic:
    """Basic health score tests."""

    def test_result_type(self, health_single: HealthScore) -> None:
        """Result should be a HealthScore dataclass."""
        assert isinstance(health_single, HealthScore)

    def test_overall_in_range(self, health_single: HealthScore) -> None:
        """Overall score should be between 0 and 100."""
        assert 0.0 <= health_single.overall <= 100.0

    def test_components_sum_to_overall(self, health_single: HealthScore) -> None:
        """Weighted components should sum to the overall score."""
        component_sum = (
            health_single.dcma_component
            + health_single.float_component
            + health_single.logic_component
            + health_single.trend_component
        )
        assert abs(component_sum - health_single.overall) < 0.5


class TestHealthRating:
    """Tests for health score rating classification."""

    def test_rating_valid(self, health_single: HealthScore) -> None:
        """Rating should be one of the valid values."""
        assert health_single.rating in ("excellent", "good", "fair", "poor")

    def test_excellent_rating(self) -> None:
        """Score >= 85 should be excellent."""
        assert HealthScoreCalculator._classify_rating(90.0) == "excellent"

    def test_good_rating(self) -> None:
        """Score >= 70 should be good."""
        assert HealthScoreCalculator._classify_rating(75.0) == "good"

    def test_fair_rating(self) -> None:
        """Score >= 50 should be fair."""
        assert HealthScoreCalculator._classify_rating(55.0) == "fair"

    def test_poor_rating(self) -> None:
        """Score < 50 should be poor."""
        assert HealthScoreCalculator._classify_rating(30.0) == "poor"


class TestTrendArrow:
    """Tests for trend direction arrow."""

    def test_trend_arrow_valid(self, health_single: HealthScore) -> None:
        """Trend arrow should be a valid value."""
        assert health_single.trend_arrow in ("↑", "→", "↓")

    def test_single_schedule_neutral_trend(self, health_single: HealthScore) -> None:
        """Without baseline, trend should be neutral (arrow = right)."""
        assert health_single.trend_arrow == "→"


class TestWithTrend:
    """Tests for health score with trend analysis."""

    def test_has_baseline_flag(self, health_with_trend: HealthScore) -> None:
        """Details should indicate baseline was provided."""
        assert health_with_trend.details.get("has_baseline") is True

    def test_trend_component_non_neutral(self, health_with_trend: HealthScore) -> None:
        """With baseline, trend raw should not necessarily be 50."""
        # It *could* be 50 if perfectly balanced, but we test it's computed
        assert 0.0 <= health_with_trend.trend_raw <= 100.0


class TestComponentScores:
    """Tests for individual component scores."""

    def test_dcma_raw_in_range(self, health_single: HealthScore) -> None:
        """DCMA raw score should be between 0 and 100."""
        assert 0.0 <= health_single.dcma_raw <= 100.0

    def test_float_raw_in_range(self, health_single: HealthScore) -> None:
        """Float health raw score should be between 0 and 100."""
        assert 0.0 <= health_single.float_raw <= 100.0

    def test_logic_raw_in_range(self, health_single: HealthScore) -> None:
        """Logic integrity raw score should be between 0 and 100."""
        assert 0.0 <= health_single.logic_raw <= 100.0

    def test_trend_raw_in_range(self, health_single: HealthScore) -> None:
        """Trend direction raw score should be between 0 and 100."""
        assert 0.0 <= health_single.trend_raw <= 100.0


class TestDetails:
    """Tests for the details transparency dict."""

    def test_details_has_weights(self, health_single: HealthScore) -> None:
        """Details should include the component weights."""
        assert "weights" in health_single.details
        weights = health_single.details["weights"]
        assert weights["dcma"] == 0.40
        assert weights["float"] == 0.25
        assert weights["logic"] == 0.20
        assert weights["trend"] == 0.15

    def test_details_has_raw_scores(self, health_single: HealthScore) -> None:
        """Details should include raw scores."""
        assert "raw_scores" in health_single.details
