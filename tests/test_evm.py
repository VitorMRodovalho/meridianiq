# MIT License
# Copyright (c) 2025 Vitor Maia Rodovalho
"""Tests for the EVM (Earned Value Management) engine.

Verifies EVM metric calculations per ANSI/EIA-748 and AACE RP 10S-90
using known inputs and expected outputs.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.analytics.evm import EVMAnalyzer, EVMMetrics, HealthClassification
from src.parser.models import (
    ParsedSchedule,
    Project,
    Task,
    TaskResource,
    WBS,
)


def _make_schedule(
    activities: list[Task],
    task_resources: list[TaskResource],
    wbs_nodes: list[WBS] | None = None,
    data_date: datetime | None = None,
) -> ParsedSchedule:
    """Build a minimal ParsedSchedule for testing."""
    proj = Project(
        proj_id="TEST",
        proj_short_name="Test Project",
        last_recalc_date=data_date or datetime(2024, 6, 1),
    )
    if wbs_nodes is None:
        wbs_nodes = [WBS(wbs_id="W1", proj_id="TEST", wbs_name="Main")]
    return ParsedSchedule(
        projects=[proj],
        activities=activities,
        task_resources=task_resources,
        wbs_nodes=wbs_nodes,
    )


class TestBasicEVMMetrics:
    """Test basic EVM metric calculations with known inputs."""

    def test_basic_evm_metrics(self) -> None:
        """Given known BAC, PV, EV, AC, verify SPI, CPI, SV, CV."""
        m = EVMMetrics(bac=100_000, pv=60_000, ev=50_000, ac=55_000)

        assert m.sv == -10_000  # EV - PV: behind schedule
        assert m.cv == -5_000  # EV - AC: over budget
        assert m.spi == pytest.approx(50_000 / 60_000, rel=1e-6)
        assert m.cpi == pytest.approx(50_000 / 55_000, rel=1e-6)

    def test_perfect_performance(self) -> None:
        """SPI=1.0 and CPI=1.0 when on track."""
        m = EVMMetrics(bac=100_000, pv=50_000, ev=50_000, ac=50_000)

        assert m.spi == 1.0
        assert m.cpi == 1.0
        assert m.sv == 0.0
        assert m.cv == 0.0

    def test_ahead_and_under_budget(self) -> None:
        """SPI > 1.0 and CPI > 1.0 when ahead and under budget."""
        m = EVMMetrics(bac=100_000, pv=40_000, ev=50_000, ac=35_000)

        assert m.spi > 1.0
        assert m.cpi > 1.0
        assert m.sv > 0
        assert m.cv > 0

    def test_zero_pv_spi(self) -> None:
        """SPI returns 0.0 when PV is zero."""
        m = EVMMetrics(bac=100_000, pv=0, ev=0, ac=0)
        assert m.spi == 0.0

    def test_zero_ac_cpi(self) -> None:
        """CPI returns 0.0 when AC is zero."""
        m = EVMMetrics(bac=100_000, pv=50_000, ev=50_000, ac=0)
        assert m.cpi == 0.0


class TestEACScenarios:
    """Test all EAC formula variants."""

    def test_eac_cpi(self) -> None:
        """EAC(CPI) = BAC / CPI."""
        m = EVMMetrics(bac=100_000, pv=60_000, ev=50_000, ac=55_000)
        expected_cpi = 50_000 / 55_000
        expected_eac = 100_000 / expected_cpi
        assert m.eac_cpi == pytest.approx(expected_eac, rel=1e-6)

    def test_eac_combined(self) -> None:
        """EAC(Combined) = AC + (BAC - EV) / (CPI * SPI)."""
        m = EVMMetrics(bac=100_000, pv=60_000, ev=50_000, ac=55_000)
        cpi = 50_000 / 55_000
        spi = 50_000 / 60_000
        expected = 55_000 + (100_000 - 50_000) / (cpi * spi)
        assert m.eac_combined == pytest.approx(expected, rel=1e-6)

    def test_eac_etc_new(self) -> None:
        """EAC(New ETC) = AC + (BAC - EV)."""
        m = EVMMetrics(bac=100_000, pv=60_000, ev=50_000, ac=55_000)
        assert m.eac_etc_new == 55_000 + 50_000  # 105_000


class TestTCPI:
    """Test TCPI calculation."""

    def test_tcpi_normal(self) -> None:
        """TCPI = (BAC - EV) / (BAC - AC)."""
        m = EVMMetrics(bac=100_000, pv=60_000, ev=50_000, ac=55_000)
        expected = (100_000 - 50_000) / (100_000 - 55_000)
        assert m.tcpi == pytest.approx(expected, rel=1e-6)

    def test_tcpi_zero_denominator(self) -> None:
        """TCPI returns 0.0 when BAC equals AC."""
        m = EVMMetrics(bac=100_000, pv=60_000, ev=50_000, ac=100_000)
        assert m.tcpi == 0.0

    def test_tcpi_overrun(self) -> None:
        """TCPI > 1.0 when project is over budget."""
        m = EVMMetrics(bac=100_000, pv=60_000, ev=40_000, ac=60_000)
        # (100k - 40k) / (100k - 60k) = 60k / 40k = 1.5
        assert m.tcpi == pytest.approx(1.5, rel=1e-6)


class TestHealthClassification:
    """Test health status classification thresholds."""

    def test_good_health(self) -> None:
        """SPI/CPI >= 1.0 classified as 'good'."""
        h = EVMAnalyzer._classify_health("SPI", 1.05)
        assert h.status == "good"

    def test_watch_health(self) -> None:
        """SPI/CPI between 0.9 and 1.0 classified as 'watch'."""
        h = EVMAnalyzer._classify_health("CPI", 0.95)
        assert h.status == "watch"

    def test_critical_health(self) -> None:
        """SPI/CPI < 0.9 classified as 'critical'."""
        h = EVMAnalyzer._classify_health("SPI", 0.85)
        assert h.status == "critical"

    def test_no_data_health(self) -> None:
        """Zero value classified as 'critical' with 'No data' label."""
        h = EVMAnalyzer._classify_health("SPI", 0.0)
        assert h.status == "critical"
        assert h.label == "No data"

    def test_exactly_one(self) -> None:
        """SPI/CPI = 1.0 classified as 'good'."""
        h = EVMAnalyzer._classify_health("CPI", 1.0)
        assert h.status == "good"

    def test_exactly_point_nine(self) -> None:
        """SPI/CPI = 0.9 classified as 'watch'."""
        h = EVMAnalyzer._classify_health("SPI", 0.9)
        assert h.status == "watch"


class TestWBSLevelEVM:
    """Test per-WBS breakdown analysis."""

    def test_wbs_level_evm(self) -> None:
        """Verify EVM metrics are computed per WBS element."""
        wbs_nodes = [
            WBS(wbs_id="W1", proj_id="TEST", wbs_name="Phase 1"),
            WBS(wbs_id="W2", proj_id="TEST", wbs_name="Phase 2"),
        ]
        activities = [
            Task(
                task_id="T1", proj_id="TEST", wbs_id="W1",
                task_type="TT_Task", status_code="TK_Complete",
                phys_complete_pct=100,
                target_start_date=datetime(2024, 1, 1),
                target_end_date=datetime(2024, 3, 1),
            ),
            Task(
                task_id="T2", proj_id="TEST", wbs_id="W2",
                task_type="TT_Task", status_code="TK_Active",
                phys_complete_pct=50,
                target_start_date=datetime(2024, 3, 1),
                target_end_date=datetime(2024, 6, 1),
            ),
        ]
        resources = [
            TaskResource(task_id="T1", rsrc_id="R1", target_cost=10_000, act_reg_cost=10_000),
            TaskResource(task_id="T2", rsrc_id="R1", target_cost=20_000, act_reg_cost=12_000),
        ]

        schedule = _make_schedule(activities, resources, wbs_nodes)
        result = EVMAnalyzer(schedule).analyze()

        assert len(result.wbs_breakdown) == 2

        w1 = next(w for w in result.wbs_breakdown if w.wbs_id == "W1")
        assert w1.metrics.bac == 10_000
        assert w1.metrics.ev == 10_000  # 100% complete

        w2 = next(w for w in result.wbs_breakdown if w.wbs_id == "W2")
        assert w2.metrics.bac == 20_000
        assert w2.metrics.ev == 10_000  # 50% of 20k


class TestSCurveGeneration:
    """Test S-curve time-phased data generation."""

    def test_s_curve_generation(self) -> None:
        """Verify S-curve produces ordered data points with cumulative values."""
        activities = [
            Task(
                task_id="T1", proj_id="TEST", wbs_id="W1",
                task_type="TT_Task", status_code="TK_Complete",
                phys_complete_pct=100,
                target_start_date=datetime(2024, 1, 1),
                target_end_date=datetime(2024, 3, 1),
                act_start_date=datetime(2024, 1, 1),
                act_end_date=datetime(2024, 3, 1),
            ),
        ]
        resources = [
            TaskResource(task_id="T1", rsrc_id="R1", target_cost=10_000, act_reg_cost=10_000),
        ]

        schedule = _make_schedule(activities, resources, data_date=datetime(2024, 6, 1))
        result = EVMAnalyzer(schedule).analyze()

        assert len(result.s_curve) > 0
        # Should be ordered by date
        dates = [p.date for p in result.s_curve]
        assert dates == sorted(dates)
        # Cumulative PV should increase monotonically
        pvs = [p.cumulative_pv for p in result.s_curve]
        for i in range(1, len(pvs)):
            assert pvs[i] >= pvs[i - 1]


class TestNoCostData:
    """Test handling of schedules without resource cost assignments."""

    def test_no_cost_data(self) -> None:
        """Schedule with no TASKRSRC records should produce zero metrics."""
        activities = [
            Task(
                task_id="T1", proj_id="TEST", wbs_id="W1",
                task_type="TT_Task", status_code="TK_Active",
                phys_complete_pct=50,
                target_start_date=datetime(2024, 1, 1),
                target_end_date=datetime(2024, 6, 1),
            ),
        ]
        schedule = _make_schedule(activities, task_resources=[])
        result = EVMAnalyzer(schedule).analyze()

        assert result.metrics.bac == 0.0
        assert result.metrics.ev == 0.0
        assert result.metrics.ac == 0.0
        assert result.metrics.pv == 0.0
        assert result.metrics.spi == 0.0
        assert result.metrics.cpi == 0.0
        assert len(result.s_curve) == 0


class TestHundredPercentComplete:
    """Test edge case: 100% complete project."""

    def test_100_percent_complete(self) -> None:
        """Fully complete project should have EV = BAC."""
        activities = [
            Task(
                task_id="T1", proj_id="TEST", wbs_id="W1",
                task_type="TT_Task", status_code="TK_Complete",
                phys_complete_pct=100,
                target_start_date=datetime(2024, 1, 1),
                target_end_date=datetime(2024, 3, 1),
                act_start_date=datetime(2024, 1, 1),
                act_end_date=datetime(2024, 3, 1),
            ),
            Task(
                task_id="T2", proj_id="TEST", wbs_id="W1",
                task_type="TT_Task", status_code="TK_Complete",
                phys_complete_pct=100,
                target_start_date=datetime(2024, 3, 1),
                target_end_date=datetime(2024, 6, 1),
                act_start_date=datetime(2024, 3, 1),
                act_end_date=datetime(2024, 5, 15),
            ),
        ]
        resources = [
            TaskResource(task_id="T1", rsrc_id="R1", target_cost=50_000, act_reg_cost=50_000),
            TaskResource(task_id="T2", rsrc_id="R1", target_cost=50_000, act_reg_cost=45_000),
        ]

        schedule = _make_schedule(activities, resources, data_date=datetime(2024, 7, 1))
        result = EVMAnalyzer(schedule).analyze()

        # EV should equal BAC (100% complete)
        assert result.metrics.ev == result.metrics.bac
        # AC should be sum of actuals
        assert result.metrics.ac == 95_000
        # CPI > 1.0 (under budget)
        assert result.metrics.cpi > 1.0
        # PV should also equal BAC (past all target end dates)
        assert result.metrics.pv == result.metrics.bac


class TestAnalyzerWithSampleFixture:
    """Test using the sample XER generator fixture."""

    def test_analyzer_with_sample(self) -> None:
        """Run EVM analysis on the sample fixture and verify structure."""
        from src.parser.xer_reader import XERReader
        from tests.fixtures.sample_xer_generator import generate_sample_xer

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            xer_path = generate_sample_xer(Path(tmpdir) / "sample.xer")
            reader = XERReader(xer_path)
            schedule = reader.parse()

        result = EVMAnalyzer(schedule).analyze()

        # Sample has 10 TASKRSRC records
        assert result.summary["total_resource_assignments"] == 10
        assert result.summary["activities_with_cost"] > 0
        assert result.metrics.bac > 0
        # Should have WBS breakdown
        assert len(result.wbs_breakdown) > 0
        # Should have S-curve data
        assert len(result.s_curve) > 0
