# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the schedule comparison engine."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.analytics.comparison import ComparisonResult, ScheduleComparison
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
def comparison_result(baseline: ParsedSchedule, update: ParsedSchedule) -> ComparisonResult:
    """Run the full comparison."""
    return ScheduleComparison(baseline, update).compare()


class TestActivityDetection:
    """Tests for activity-level change detection."""

    def test_detect_added_activities(self, comparison_result: ComparisonResult) -> None:
        """Two new activities (T-031, T-032) should be detected."""
        added_ids = {c.task_id for c in comparison_result.activities_added}
        assert "T-031" in added_ids
        assert "T-032" in added_ids
        assert len(comparison_result.activities_added) == 2

    def test_detect_deleted_activities(self, comparison_result: ComparisonResult) -> None:
        """One activity (T-029) should be detected as deleted."""
        deleted_ids = {c.task_id for c in comparison_result.activities_deleted}
        assert "T-029" in deleted_ids
        assert len(comparison_result.activities_deleted) == 1

    def test_detect_duration_changes(self, comparison_result: ComparisonResult) -> None:
        """Three activities should have duration changes."""
        dur_ids = {c.task_id for c in comparison_result.duration_changes}
        # T-021: 40 -> 56, T-024: 80 -> 60, T-025: 80 -> 64
        assert "T-021" in dur_ids
        assert "T-024" in dur_ids
        assert "T-025" in dur_ids
        assert len(comparison_result.duration_changes) == 3


class TestRelationshipDetection:
    """Tests for relationship-level change detection."""

    def test_detect_relationship_additions(self, comparison_result: ComparisonResult) -> None:
        """Five new relationships should be detected."""
        assert len(comparison_result.relationships_added) == 5

    def test_detect_relationship_deletions(self, comparison_result: ComparisonResult) -> None:
        """Two deleted relationships should be detected."""
        assert len(comparison_result.relationships_deleted) == 2


class TestFloatDetection:
    """Tests for float change detection."""

    def test_detect_float_changes(self, comparison_result: ComparisonResult) -> None:
        """Significant float changes should be detected."""
        assert len(comparison_result.significant_float_changes) > 0


class TestConstraintDetection:
    """Tests for constraint change detection."""

    def test_detect_constraint_addition(self, comparison_result: ComparisonResult) -> None:
        """At least one new constraint should be detected."""
        # T-026 gets a new cstr_type2 (CS_MSOA)
        assert len(comparison_result.constraint_changes) >= 1
        constraint_task_ids = {c.task_id for c in comparison_result.constraint_changes}
        assert "T-026" in constraint_task_ids


class TestManipulationFlags:
    """Tests for schedule manipulation indicators."""

    def test_detect_retroactive_date(self, comparison_result: ComparisonResult) -> None:
        """Retroactive date change on T-002 should be flagged."""
        retro_flags = [
            f for f in comparison_result.manipulation_flags
            if f.indicator == "retroactive_date"
        ]
        retro_task_ids = {f.task_id for f in retro_flags}
        assert "T-002" in retro_task_ids

    def test_detect_oos_progress(self, comparison_result: ComparisonResult) -> None:
        """Out-of-sequence progress should be detected."""
        oos_flags = [
            f for f in comparison_result.manipulation_flags
            if f.indicator == "oos_progress"
        ]
        assert len(oos_flags) > 0

    def test_manipulation_flags_populated(self, comparison_result: ComparisonResult) -> None:
        """At least some manipulation flags should be raised."""
        assert len(comparison_result.manipulation_flags) > 0


class TestSummaryMetrics:
    """Tests for summary metrics calculation."""

    def test_changed_percentage(self, comparison_result: ComparisonResult) -> None:
        """Changed percentage should be > 0 and reasonable."""
        assert comparison_result.changed_percentage > 0.0
        assert comparison_result.changed_percentage <= 100.0

    def test_critical_path_stability(self, comparison_result: ComparisonResult) -> None:
        """Critical path should show changes due to new activities/rels."""
        # With new activities T-031/T-032 and new relationships changing
        # the end of the schedule, the CP should change
        assert comparison_result.critical_path_changed is True

    def test_summary_dict_populated(self, comparison_result: ComparisonResult) -> None:
        """Summary dictionary should contain expected keys."""
        summary = comparison_result.summary
        assert "baseline_activity_count" in summary
        assert "update_activity_count" in summary
        assert "changed_percentage" in summary
        assert summary["baseline_activity_count"] == 30
        assert summary["update_activity_count"] == 31  # 30 - 1 deleted + 2 added
