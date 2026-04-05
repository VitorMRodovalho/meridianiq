# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the benchmark analytics engine.

Verifies metric extraction, anonymization, percentile ranking,
and comparison against benchmark datasets.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.analytics.benchmarks import (
    BenchmarkMetrics,
    compare_to_benchmarks,
    extract_benchmark_metrics,
)
from src.parser.models import ParsedSchedule
from src.parser.xer_reader import XERReader

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def sample() -> ParsedSchedule:
    return XERReader(FIXTURES / "sample.xer").parse()


@pytest.fixture(scope="module")
def update1() -> ParsedSchedule:
    return XERReader(FIXTURES / "sample_update.xer").parse()


# ===========================================================================
# Tests: Metric Extraction
# ===========================================================================


class TestMetricExtraction:
    """Verify anonymized metrics are correctly extracted."""

    def test_returns_benchmark_metrics(self, sample: ParsedSchedule) -> None:
        m = extract_benchmark_metrics(sample)
        assert isinstance(m, BenchmarkMetrics)

    def test_activity_count(self, sample: ParsedSchedule) -> None:
        m = extract_benchmark_metrics(sample)
        assert m.activity_count > 0
        assert m.activity_count == len(sample.activities)

    def test_relationship_count(self, sample: ParsedSchedule) -> None:
        m = extract_benchmark_metrics(sample)
        assert m.relationship_count > 0

    def test_size_category_assigned(self, sample: ParsedSchedule) -> None:
        m = extract_benchmark_metrics(sample)
        assert m.size_category in ("small", "medium", "large", "mega")

    def test_dcma_score_populated(self, sample: ParsedSchedule) -> None:
        m = extract_benchmark_metrics(sample)
        assert 0 <= m.dcma_score <= 100

    def test_float_stats_populated(self, sample: ParsedSchedule) -> None:
        m = extract_benchmark_metrics(sample)
        assert isinstance(m.float_mean_days, float)
        assert isinstance(m.float_median_days, float)

    def test_network_metrics(self, sample: ParsedSchedule) -> None:
        m = extract_benchmark_metrics(sample)
        assert m.relationship_density > 0
        assert m.project_duration_days > 0

    def test_progress_percentages(self, sample: ParsedSchedule) -> None:
        m = extract_benchmark_metrics(sample)
        total = m.complete_pct + m.active_pct + m.not_started_pct
        assert abs(total - 100.0) < 5.0  # Allow for rounding + other statuses

    def test_no_identifying_info(self, sample: ParsedSchedule) -> None:
        """Metrics should contain NO activity names, WBS text, or codes."""
        m = extract_benchmark_metrics(sample)
        # BenchmarkMetrics has no string fields for names/codes
        fields = vars(m)
        for key, value in fields.items():
            if isinstance(value, str):
                # Only allowed string fields are size_category
                assert key == "size_category", f"Unexpected string field: {key}={value}"

    def test_empty_schedule(self) -> None:
        s = ParsedSchedule()
        m = extract_benchmark_metrics(s)
        assert m.activity_count == 0
        assert m.dcma_score == 0


# ===========================================================================
# Tests: Benchmark Comparison
# ===========================================================================


class TestBenchmarkComparison:
    """Verify comparison against benchmark dataset."""

    def _make_dataset(self) -> list[BenchmarkMetrics]:
        """Create a synthetic benchmark dataset."""
        return [
            BenchmarkMetrics(
                activity_count=50,
                size_category="small",
                dcma_score=65,
                logic_pct=85,
                constraint_pct=8,
                negative_float_pct=5,
                relationship_density=1.2,
                bei=0.9,
            ),
            BenchmarkMetrics(
                activity_count=80,
                size_category="small",
                dcma_score=72,
                logic_pct=90,
                constraint_pct=3,
                negative_float_pct=2,
                relationship_density=1.5,
                bei=0.95,
            ),
            BenchmarkMetrics(
                activity_count=30,
                size_category="small",
                dcma_score=50,
                logic_pct=70,
                constraint_pct=15,
                negative_float_pct=10,
                relationship_density=0.8,
                bei=0.7,
            ),
        ]

    def test_comparison_returns_result(self, sample: ParsedSchedule) -> None:
        dataset = self._make_dataset()
        result = compare_to_benchmarks(sample, dataset, filter_size=False)
        assert result.benchmark_count > 0
        assert len(result.rankings) > 0

    def test_percentiles_bounded(self, sample: ParsedSchedule) -> None:
        dataset = self._make_dataset()
        result = compare_to_benchmarks(sample, dataset, filter_size=False)
        for r in result.rankings:
            assert 0 <= r.percentile <= 100

    def test_interpretations_valid(self, sample: ParsedSchedule) -> None:
        dataset = self._make_dataset()
        result = compare_to_benchmarks(sample, dataset, filter_size=False)
        valid = {"above_average", "average", "below_average"}
        for r in result.rankings:
            assert r.interpretation in valid

    def test_summary_populated(self, sample: ParsedSchedule) -> None:
        dataset = self._make_dataset()
        result = compare_to_benchmarks(sample, dataset, filter_size=False)
        s = result.summary
        assert "benchmark_count" in s
        assert "overall_percentile" in s
        assert "dcma_score" in s

    def test_empty_dataset(self, sample: ParsedSchedule) -> None:
        result = compare_to_benchmarks(sample, [], filter_size=False)
        assert result.benchmark_count == 0
        assert "error" in result.summary

    def test_size_filtering(self, sample: ParsedSchedule) -> None:
        """When filtering by size, only same-size benchmarks should be used."""
        m = extract_benchmark_metrics(sample)
        dataset = self._make_dataset()
        # Add a large project that shouldn't match small
        dataset.append(BenchmarkMetrics(activity_count=1000, size_category="large", dcma_score=90))
        result = compare_to_benchmarks(sample, dataset, filter_size=True)
        # Should filter to only matching size
        if m.size_category == "small":
            assert result.benchmark_count == 3  # Only the 3 small ones


# ===========================================================================
# Tests: Multiple Real XERs
# ===========================================================================


class TestMultipleXERs:
    """Test benchmark extraction across multiple real schedule versions."""

    def test_metrics_differ_between_updates(
        self, sample: ParsedSchedule, update1: ParsedSchedule
    ) -> None:
        """Different schedule versions should produce different metrics."""
        m1 = extract_benchmark_metrics(sample)
        m2 = extract_benchmark_metrics(update1)
        # At least some metrics should differ
        differs = (
            m1.dcma_score != m2.dcma_score
            or m1.complete_pct != m2.complete_pct
            or m1.float_mean_days != m2.float_mean_days
        )
        assert differs

    def test_compare_against_self(self, sample: ParsedSchedule) -> None:
        """Comparing a schedule to itself should give ~50th percentile."""
        m = extract_benchmark_metrics(sample)
        result = compare_to_benchmarks(sample, [m], filter_size=False)
        # With 1 benchmark equal to self, percentile should be ~50
        for r in result.rankings:
            assert 40 <= r.percentile <= 60
