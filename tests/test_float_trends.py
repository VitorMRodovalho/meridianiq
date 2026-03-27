# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the float trend analysis engine."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.analytics.float_trends import FloatTrendAnalyzer, FloatTrendResult
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
def float_trend_result(baseline: ParsedSchedule, update: ParsedSchedule) -> FloatTrendResult:
    """Run the full float trend analysis."""
    return FloatTrendAnalyzer(baseline, update).analyze()


class TestFloatTrendBasic:
    """Basic float trend analysis tests."""

    def test_result_type(self, float_trend_result: FloatTrendResult) -> None:
        """Result should be a FloatTrendResult dataclass."""
        assert isinstance(float_trend_result, FloatTrendResult)

    def test_matched_activities(self, float_trend_result: FloatTrendResult) -> None:
        """Matched activity count should be positive."""
        assert float_trend_result.total_matched > 0

    def test_activity_trends_populated(self, float_trend_result: FloatTrendResult) -> None:
        """Activity trends should be populated for matched activities with float data."""
        assert len(float_trend_result.activity_trends) > 0


class TestFloatErosionIndex:
    """Tests for the Float Erosion Index metric."""

    def test_fei_is_percentage(self, float_trend_result: FloatTrendResult) -> None:
        """FEI should be between 0 and 100."""
        assert 0.0 <= float_trend_result.fei <= 100.0

    def test_fei_in_thresholds(self, float_trend_result: FloatTrendResult) -> None:
        """FEI should have a threshold status."""
        assert "fei" in float_trend_result.thresholds
        assert float_trend_result.thresholds["fei"]["status"] in ("green", "yellow", "red")


class TestNearCriticalDrift:
    """Tests for the Near-Critical Drift metric."""

    def test_near_critical_drift_non_negative(self, float_trend_result: FloatTrendResult) -> None:
        """Near-critical drift should be non-negative."""
        assert float_trend_result.near_critical_drift >= 0

    def test_near_critical_drift_in_thresholds(self, float_trend_result: FloatTrendResult) -> None:
        """Near-critical drift should have a threshold status."""
        assert "near_critical_drift" in float_trend_result.thresholds


class TestCriticalPathStability:
    """Tests for the Critical Path Stability metric."""

    def test_cp_stability_is_percentage(self, float_trend_result: FloatTrendResult) -> None:
        """CP stability should be between 0 and 100."""
        assert 0.0 <= float_trend_result.cp_stability <= 100.0

    def test_cp_stability_in_thresholds(self, float_trend_result: FloatTrendResult) -> None:
        """CP stability should have a threshold status."""
        assert "cp_stability" in float_trend_result.thresholds
        assert float_trend_result.thresholds["cp_stability"]["status"] in (
            "green",
            "yellow",
            "red",
        )


class TestActivityTrends:
    """Tests for per-activity float trend data."""

    def test_activity_direction_valid(self, float_trend_result: FloatTrendResult) -> None:
        """Each activity trend should have a valid direction."""
        for trend in float_trend_result.activity_trends:
            assert trend.direction in ("improving", "deteriorating", "stable")

    def test_activity_delta_consistent(self, float_trend_result: FloatTrendResult) -> None:
        """Delta should equal new_float - old_float."""
        for trend in float_trend_result.activity_trends:
            expected_delta = round(trend.new_float_days - trend.old_float_days, 2)
            assert abs(trend.delta_days - expected_delta) < 0.1


class TestSummary:
    """Tests for the summary output."""

    def test_summary_has_required_keys(self, float_trend_result: FloatTrendResult) -> None:
        """Summary should include all expected keys."""
        required_keys = {
            "total_matched",
            "total_with_float_data",
            "improving",
            "deteriorating",
            "stable",
            "fei",
            "near_critical_drift",
            "cp_stability",
        }
        assert required_keys.issubset(float_trend_result.summary.keys())

    def test_direction_counts_sum(self, float_trend_result: FloatTrendResult) -> None:
        """Direction counts should sum to total_with_float_data."""
        s = float_trend_result.summary
        assert s["improving"] + s["deteriorating"] + s["stable"] == s["total_with_float_data"]
