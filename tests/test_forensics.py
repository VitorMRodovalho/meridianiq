# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the forensic schedule analysis engine (CPA / window analysis).

Verifies window creation, delay calculation, cumulative delay tracking,
completion date extraction, driving activity identification, critical path
evolution, and edge-case validation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.analytics.forensics import ForensicAnalyzer, ForensicTimeline
from src.parser.xer_reader import XERReader

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


def _parse(filename: str):
    """Parse a fixture XER file."""
    reader = XERReader(FIXTURES / filename)
    return reader.parse()


@pytest.fixture
def sample():
    return _parse("sample.xer")


@pytest.fixture
def update1():
    return _parse("sample_update.xer")


@pytest.fixture
def update2():
    return _parse("sample_update2.xer")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWindowCreation:
    """Verify that windows are created correctly from schedule lists."""

    def test_two_schedules_one_window(self, sample, update1):
        """Two schedules should produce one window."""
        analyzer = ForensicAnalyzer([sample, update1], ["p1", "p2"])
        timeline = analyzer.analyze()
        assert len(timeline.windows) == 1
        assert timeline.schedule_count == 2
        assert timeline.windows[0].window.window_id == "W01"

    def test_three_schedules_two_windows(self, sample, update1, update2):
        """Three schedules should produce two windows."""
        analyzer = ForensicAnalyzer(
            [sample, update1, update2], ["p1", "p2", "p3"]
        )
        timeline = analyzer.analyze()
        assert len(timeline.windows) == 2
        assert timeline.windows[0].window.window_id == "W01"
        assert timeline.windows[1].window.window_id == "W02"
        assert timeline.schedule_count == 3


class TestDelayCalculation:
    """Verify delay_days is computed per window."""

    def test_delay_days_is_numeric(self, sample, update1):
        """delay_days should be a number (positive or negative)."""
        analyzer = ForensicAnalyzer([sample, update1], ["p1", "p2"])
        timeline = analyzer.analyze()
        w = timeline.windows[0]
        assert isinstance(w.delay_days, (int, float))

    def test_delay_calculated_between_windows(self, sample, update1, update2):
        """Each window should have its own delay_days."""
        analyzer = ForensicAnalyzer(
            [sample, update1, update2], ["p1", "p2", "p3"]
        )
        timeline = analyzer.analyze()
        for w in timeline.windows:
            assert w.completion_date_start is not None
            assert w.completion_date_end is not None


class TestCumulativeDelay:
    """Verify running total of delay across windows."""

    def test_cumulative_equals_sum(self, sample, update1, update2):
        """cumulative_delay of last window should equal total_delay_days."""
        analyzer = ForensicAnalyzer(
            [sample, update1, update2], ["p1", "p2", "p3"]
        )
        timeline = analyzer.analyze()
        last = timeline.windows[-1]
        assert abs(last.cumulative_delay - timeline.total_delay_days) < 0.01

    def test_cumulative_is_running_total(self, sample, update1, update2):
        """Each window's cumulative should be sum of all prior delays."""
        analyzer = ForensicAnalyzer(
            [sample, update1, update2], ["p1", "p2", "p3"]
        )
        timeline = analyzer.analyze()
        running = 0.0
        for w in timeline.windows:
            running += w.delay_days
            assert abs(w.cumulative_delay - running) < 0.01


class TestCompletionDateExtraction:
    """Verify CP-based completion date extraction."""

    def test_completion_date_is_datetime(self, sample):
        """Completion date should be a datetime object."""
        analyzer = ForensicAnalyzer([sample, sample], ["p1", "p2"])
        cd = analyzer._get_completion_date(sample)
        assert cd is not None
        from datetime import datetime
        assert isinstance(cd, datetime)

    def test_completion_dates_differ_between_updates(self, sample, update2):
        """Completion dates should differ between baseline and later updates."""
        analyzer = ForensicAnalyzer([sample, update2], ["p1", "p2"])
        cd1 = analyzer._get_completion_date(sample)
        cd2 = analyzer._get_completion_date(update2)
        assert cd1 is not None
        assert cd2 is not None
        # The dates should not be identical (schedule has changed)
        assert cd1 != cd2


class TestDrivingActivity:
    """Verify correct driving activity identification."""

    def test_driving_activity_is_string(self, sample):
        """Driving activity should be a non-empty string."""
        analyzer = ForensicAnalyzer([sample, sample], ["p1", "p2"])
        da = analyzer._get_driving_activity(sample)
        assert isinstance(da, str)
        assert len(da) > 0

    def test_driving_activity_per_window(self, sample, update1, update2):
        """Each window should identify a driving activity."""
        analyzer = ForensicAnalyzer(
            [sample, update1, update2], ["p1", "p2", "p3"]
        )
        timeline = analyzer.analyze()
        for w in timeline.windows:
            assert isinstance(w.driving_activity, str)
            assert len(w.driving_activity) > 0


class TestCriticalPathEvolution:
    """Verify CP changes are tracked between windows."""

    def test_cp_lists_are_populated(self, sample, update1):
        """Each window should have CP start and end lists."""
        analyzer = ForensicAnalyzer([sample, update1], ["p1", "p2"])
        timeline = analyzer.analyze()
        w = timeline.windows[0]
        assert isinstance(w.critical_path_start, list)
        assert isinstance(w.critical_path_end, list)
        assert len(w.critical_path_start) > 0
        assert len(w.critical_path_end) > 0

    def test_cp_changes_detected(self, sample, update1, update2):
        """CP joined/left lists should exist (may be empty if CP unchanged)."""
        analyzer = ForensicAnalyzer(
            [sample, update1, update2], ["p1", "p2", "p3"]
        )
        timeline = analyzer.analyze()
        for w in timeline.windows:
            assert isinstance(w.cp_activities_joined, list)
            assert isinstance(w.cp_activities_left, list)


class TestEdgeCases:
    """Verify error handling and edge cases."""

    def test_single_schedule_error(self, sample):
        """ForensicAnalyzer should reject a single schedule."""
        with pytest.raises(ValueError, match="at least 2"):
            ForensicAnalyzer([sample], ["p1"])

    def test_empty_list_error(self):
        """ForensicAnalyzer should reject an empty list."""
        with pytest.raises(ValueError, match="at least 2"):
            ForensicAnalyzer([], [])

    def test_mismatched_lists_error(self, sample, update1):
        """ForensicAnalyzer should reject mismatched list lengths."""
        with pytest.raises(ValueError, match="same length"):
            ForensicAnalyzer([sample, update1], ["p1"])


class TestWindowOrdering:
    """Verify windows are ordered by data date."""

    def test_windows_sorted_by_data_date(self, sample, update1, update2):
        """Windows should be in chronological order even if input is shuffled."""
        # Pass in reverse order -- analyzer should sort
        analyzer = ForensicAnalyzer(
            [update2, sample, update1], ["p3", "p1", "p2"]
        )
        timeline = analyzer.analyze()
        assert len(timeline.windows) == 2
        w1 = timeline.windows[0]
        w2 = timeline.windows[1]
        # Window 1 should have earlier dates than window 2
        assert w1.window.start_date is not None
        assert w2.window.start_date is not None
        assert w1.window.start_date < w2.window.start_date


class TestTimelineSummary:
    """Verify the timeline summary is populated."""

    def test_summary_has_expected_keys(self, sample, update1, update2):
        """Summary dict should contain expected metrics."""
        analyzer = ForensicAnalyzer(
            [sample, update1, update2], ["p1", "p2", "p3"]
        )
        timeline = analyzer.analyze()
        s = timeline.summary
        assert "schedule_count" in s
        assert "window_count" in s
        assert "total_delay_days" in s
        assert "windows_with_delay" in s
        assert "cp_changed_windows" in s
        assert s["schedule_count"] == 3
        assert s["window_count"] == 2

    def test_project_name_populated(self, sample, update1):
        """Timeline should have the project name from the first schedule."""
        analyzer = ForensicAnalyzer([sample, update1], ["p1", "p2"])
        timeline = analyzer.analyze()
        assert timeline.project_name == "Sample Construction"

    def test_comparison_included(self, sample, update1):
        """Each window should include a ComparisonResult."""
        analyzer = ForensicAnalyzer([sample, update1], ["p1", "p2"])
        timeline = analyzer.analyze()
        w = timeline.windows[0]
        assert w.comparison is not None
        assert hasattr(w.comparison, "summary")
