# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the DCMA 14-point assessment module."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.parser import XERReader, ParsedSchedule
from src.analytics.dcma14 import DCMA14Analyzer, DCMA14Result

SAMPLE_XER = Path(__file__).parent / "fixtures" / "sample.xer"


@pytest.fixture
def schedule() -> ParsedSchedule:
    reader = XERReader(SAMPLE_XER)
    return reader.parse()


@pytest.fixture
def dcma_result(schedule: ParsedSchedule) -> DCMA14Result:
    analyzer = DCMA14Analyzer(schedule)
    return analyzer.analyze()


class TestLogicCheck:
    """Check 1: Logic -- % with both pred and succ."""

    def test_logic_metric_exists(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[0]
        assert m.number == 1
        assert m.name == "Logic"

    def test_logic_value_is_percentage(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[0]
        assert 0.0 <= m.value <= 100.0

    def test_logic_threshold(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[0]
        assert m.threshold == 90.0


class TestRelationshipTypes:
    """Check 4: Relationship Types -- % FS."""

    def test_fs_metric(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[3]
        assert m.number == 4
        assert m.name == "Relationship Types"
        # 35/40 = 87.5% FS -- just under threshold
        assert 85.0 <= m.value <= 90.0

    def test_fs_threshold(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[3]
        assert m.threshold == 90.0


class TestHighFloat:
    """Check 6: High Float -- % with TF > 44 days."""

    def test_high_float_metric(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[5]
        assert m.number == 6
        assert m.name == "High Float"

    def test_high_float_value(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[5]
        assert 0.0 <= m.value <= 100.0


class TestConstraints:
    """Check 5: Hard Constraints."""

    def test_constraints_metric(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[4]
        assert m.number == 5
        assert m.name == "Hard Constraints"
        # 2 constrained out of 29 countable = ~6.9%
        assert m.value > 0.0

    def test_constraints_threshold(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[4]
        assert m.threshold == 5.0


class TestOverallScore:
    """Test the composite overall score."""

    def test_score_range(self, dcma_result: DCMA14Result) -> None:
        assert 0.0 <= dcma_result.overall_score <= 100.0

    def test_metric_count(self, dcma_result: DCMA14Result) -> None:
        assert len(dcma_result.metrics) == 14

    def test_passed_plus_failed_equals_14(self, dcma_result: DCMA14Result) -> None:
        assert dcma_result.passed_count + dcma_result.failed_count == 14


class TestLeadsAndLags:
    """Checks 2 and 3: Leads and Lags."""

    def test_no_leads(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[1]
        assert m.number == 2
        assert m.value == 0.0
        assert m.passed is True

    def test_no_lags(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[2]
        assert m.number == 3
        # No lags in our sample
        assert m.value == 0.0


class TestNegativeFloat:
    """Check 7: Negative Float."""

    def test_no_negative_float(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[6]
        assert m.number == 7
        assert m.value == 0.0
        assert m.passed is True


class TestHighDuration:
    """Check 8: High Duration."""

    def test_high_duration_metric(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[7]
        assert m.number == 8
        assert 0.0 <= m.value <= 100.0


class TestBEI:
    """Check 14: Baseline Execution Index."""

    def test_bei_metric(self, dcma_result: DCMA14Result) -> None:
        m = dcma_result.metrics[13]
        assert m.number == 14
        assert m.name == "BEI"
        # BEI should be calculable since we have baseline dates and data date
        assert m.value >= 0.0


class TestDCMAWithDataDate:
    """Test DCMA with explicit data date."""

    def test_explicit_data_date(self, schedule: ParsedSchedule) -> None:
        data_date = datetime(2024, 6, 1, 8, 0)
        analyzer = DCMA14Analyzer(schedule, data_date=data_date)
        result = analyzer.analyze()
        assert result.data_date == data_date
        assert len(result.metrics) == 14
