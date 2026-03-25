# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the CPM calculator module."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.parser import XERReader, ParsedSchedule
from src.analytics.cpm import CPMCalculator, CPMResult

SAMPLE_XER = Path(__file__).parent / "fixtures" / "sample.xer"


@pytest.fixture
def schedule() -> ParsedSchedule:
    reader = XERReader(SAMPLE_XER)
    return reader.parse()


@pytest.fixture
def cpm_result(schedule: ParsedSchedule) -> CPMResult:
    calc = CPMCalculator(schedule)
    return calc.calculate()


class TestCriticalPath:
    """Tests for critical path identification."""

    def test_no_cycles(self, cpm_result: CPMResult) -> None:
        assert cpm_result.has_cycles is False

    def test_critical_path_not_empty(self, cpm_result: CPMResult) -> None:
        assert len(cpm_result.critical_path) > 0

    def test_critical_path_contains_expected(self, cpm_result: CPMResult) -> None:
        """The critical path should include key activities."""
        # At minimum, the project start and finish should be on it
        # (both are milestones with 0 duration on the longest path)
        cp_set = set(cpm_result.critical_path)
        # T-030 (Project Completion) should be on the critical path
        assert "T-030" in cp_set

    def test_project_duration_positive(self, cpm_result: CPMResult) -> None:
        assert cpm_result.project_duration > 0


class TestForwardPass:
    """Tests for Early Start / Early Finish calculation."""

    def test_first_activity_es_zero(self, cpm_result: CPMResult) -> None:
        """The first activity (T-001, milestone) should start at 0."""
        ar = cpm_result.activity_results["T-001"]
        assert ar.early_start == 0.0

    def test_first_activity_ef_zero(self, cpm_result: CPMResult) -> None:
        """T-001 is a completed milestone, duration 0 -> EF = 0."""
        ar = cpm_result.activity_results["T-001"]
        assert ar.early_finish == 0.0

    def test_successor_es_after_predecessor_ef(self, cpm_result: CPMResult) -> None:
        """T-002 (successor of T-001 via FS) should start at or after T-001 EF."""
        ar_001 = cpm_result.activity_results["T-001"]
        ar_002 = cpm_result.activity_results["T-002"]
        assert ar_002.early_start >= ar_001.early_finish

    def test_ef_equals_es_plus_duration(self, cpm_result: CPMResult) -> None:
        """For any activity, EF = ES + duration."""
        for ar in cpm_result.activity_results.values():
            assert abs(ar.early_finish - (ar.early_start + ar.duration)) < 1e-6


class TestBackwardPass:
    """Tests for Late Start / Late Finish calculation."""

    def test_last_activity_lf_equals_project_duration(
        self, cpm_result: CPMResult
    ) -> None:
        """Activities with no successor should have LF = project duration."""
        # T-030 is the project end milestone
        ar = cpm_result.activity_results["T-030"]
        assert abs(ar.late_finish - cpm_result.project_duration) < 1e-6

    def test_ls_equals_lf_minus_duration(self, cpm_result: CPMResult) -> None:
        for ar in cpm_result.activity_results.values():
            assert abs(ar.late_start - (ar.late_finish - ar.duration)) < 1e-6


class TestTotalFloat:
    """Tests for Total Float calculation."""

    def test_critical_activities_have_zero_float(self, cpm_result: CPMResult) -> None:
        for task_id in cpm_result.critical_path:
            ar = cpm_result.activity_results[task_id]
            assert abs(ar.total_float) < 1e-6

    def test_noncritical_have_positive_float(self, cpm_result: CPMResult) -> None:
        """At least some non-critical activities should have positive float."""
        non_critical = [
            ar
            for tid, ar in cpm_result.activity_results.items()
            if tid not in set(cpm_result.critical_path)
        ]
        has_positive = any(ar.total_float > 0 for ar in non_critical)
        assert has_positive

    def test_total_float_is_ls_minus_es(self, cpm_result: CPMResult) -> None:
        for ar in cpm_result.activity_results.values():
            expected = ar.late_start - ar.early_start
            assert abs(ar.total_float - expected) < 1e-6


class TestFreeFloat:
    """Tests for Free Float calculation."""

    def test_free_float_non_negative(self, cpm_result: CPMResult) -> None:
        for ar in cpm_result.activity_results.values():
            assert ar.free_float >= -1e-6

    def test_free_float_lte_total_float(self, cpm_result: CPMResult) -> None:
        """Free float should never exceed total float."""
        for ar in cpm_result.activity_results.values():
            assert ar.free_float <= ar.total_float + 1e-6


class TestCPMWithCycle:
    """Test CPM behaviour when the schedule graph has a cycle."""

    def test_cycle_detected(self) -> None:
        """Build a minimal schedule with a cycle and verify detection."""
        from src.parser.models import ParsedSchedule, Task, Relationship

        schedule = ParsedSchedule(
            activities=[
                Task(task_id="A", remain_drtn_hr_cnt=8, task_code="A"),
                Task(task_id="B", remain_drtn_hr_cnt=8, task_code="B"),
            ],
            relationships=[
                Relationship(task_id="B", pred_task_id="A", pred_type="PR_FS"),
                Relationship(task_id="A", pred_task_id="B", pred_type="PR_FS"),
            ],
        )
        calc = CPMCalculator(schedule)
        result = calc.calculate()
        assert result.has_cycles is True
