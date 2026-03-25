# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Forensic schedule analysis -- Contemporaneous Period Analysis (CPA).

Implements window analysis methodology per AACE RP 29R-03 (Forensic Schedule
Analysis) and the SCL Delay and Disruption Protocol.  Divides a project's
schedule update history into analysis windows and quantifies delay per window.

References:
    - AACE RP 29R-03 Forensic Schedule Analysis, MIP 3.3
    - SCL Delay and Disruption Protocol, 2nd ed., Core Principle 2
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from src.analytics.comparison import ComparisonResult, ScheduleComparison
from src.analytics.cpm import CPMCalculator, CPMResult
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


@dataclass
class AnalysisWindow:
    """One analysis period between two consecutive schedule updates."""

    window_number: int
    window_id: str  # e.g., "W01"
    baseline_project_id: str
    update_project_id: str
    start_date: datetime | None = None  # data date of baseline
    end_date: datetime | None = None  # data date of update


@dataclass
class WindowResult:
    """Results of analyzing one window.

    Per AACE RP 29R-03 MIP 3.3, each window captures the change in
    forecasted completion date between two consecutive data dates and
    tracks critical path evolution.
    """

    window: AnalysisWindow
    completion_date_start: datetime | None = None  # CP end date at start of window
    completion_date_end: datetime | None = None  # CP end date at end of window
    delay_days: float = 0.0  # positive = delay, negative = acceleration
    cumulative_delay: float = 0.0  # running total
    critical_path_start: list[str] = field(default_factory=list)  # CP activity codes at start
    critical_path_end: list[str] = field(default_factory=list)  # CP activity codes at end
    cp_activities_joined: list[str] = field(default_factory=list)
    cp_activities_left: list[str] = field(default_factory=list)
    driving_activity: str = ""  # activity driving completion at end of window
    comparison: ComparisonResult | None = None  # full comparison details


@dataclass
class ForensicTimeline:
    """Complete CPA across all schedule updates.

    Aggregates all ``WindowResult`` objects into a single timeline that
    shows delay accumulation across the project lifecycle.
    """

    timeline_id: str
    project_name: str = ""
    windows: list[WindowResult] = field(default_factory=list)
    total_delay_days: float = 0.0
    contract_completion: datetime | None = None  # original contractual end
    current_completion: datetime | None = None  # latest forecasted end
    schedule_count: int = 0
    summary: dict[str, Any] = field(default_factory=dict)


class ForensicAnalyzer:
    """Perform Contemporaneous Period Analysis on a series of schedule updates.

    Per AACE RP 29R-03 MIP 3.3, this analysis:
    1. Divides the project into analysis windows (one per update period)
    2. Identifies the critical path at each data date
    3. Measures completion date movement per window
    4. Quantifies delay per window
    5. Tracks critical path evolution across windows

    Usage::

        analyzer = ForensicAnalyzer(schedules, project_ids)
        timeline = analyzer.analyze()
    """

    def __init__(
        self,
        schedules: list[ParsedSchedule],
        project_ids: list[str],
    ) -> None:
        """Initialize with a list of schedule updates sorted by data date.

        Args:
            schedules: List of parsed schedules (must contain at least 2).
            project_ids: Corresponding project IDs for reference.

        Raises:
            ValueError: If fewer than 2 schedules are provided or the lists
                differ in length.
        """
        if len(schedules) < 2:
            raise ValueError(
                f"Forensic analysis requires at least 2 schedules, got {len(schedules)}"
            )
        if len(schedules) != len(project_ids):
            raise ValueError(
                f"schedules ({len(schedules)}) and project_ids ({len(project_ids)}) "
                f"must have the same length"
            )

        # Pair and sort by data date
        paired: list[tuple[ParsedSchedule, str, datetime | None]] = []
        for sched, pid in zip(schedules, project_ids):
            dd = self._get_data_date(sched)
            paired.append((sched, pid, dd))

        # Sort by data date (None sorts first -- treat as epoch)
        paired.sort(key=lambda t: t[2] or datetime.min)

        self._schedules = [p[0] for p in paired]
        self._project_ids = [p[1] for p in paired]
        self._data_dates = [p[2] for p in paired]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self) -> ForensicTimeline:
        """Run the full CPA analysis.

        Returns:
            A ``ForensicTimeline`` with per-window delay data and
            cumulative totals.
        """
        timeline = ForensicTimeline(
            timeline_id=f"tl-{uuid.uuid4().hex[:8]}",
            schedule_count=len(self._schedules),
        )

        # Extract project name from the first schedule
        if self._schedules[0].projects:
            timeline.project_name = self._schedules[0].projects[0].proj_short_name

        # Contract completion = completion date of the first (baseline) schedule
        timeline.contract_completion = self._get_completion_date(self._schedules[0])

        cumulative_delay = 0.0

        for i in range(len(self._schedules) - 1):
            baseline = self._schedules[i]
            update = self._schedules[i + 1]
            base_id = self._project_ids[i]
            upd_id = self._project_ids[i + 1]
            window_num = i + 1

            window_result = self._analyze_window(
                baseline, update, base_id, upd_id, window_num, cumulative_delay
            )
            cumulative_delay = window_result.cumulative_delay
            timeline.windows.append(window_result)

        # Totals
        timeline.total_delay_days = cumulative_delay
        timeline.current_completion = self._get_completion_date(self._schedules[-1])

        # Build summary
        timeline.summary = self._build_summary(timeline)

        return timeline

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_data_date(self, schedule: ParsedSchedule) -> datetime | None:
        """Extract data date from a schedule.

        Looks at the project's ``last_recalc_date`` first, falling back
        to ``sum_data_date``.

        Args:
            schedule: A parsed schedule.

        Returns:
            The data date, or ``None`` if not available.
        """
        if schedule.projects:
            proj = schedule.projects[0]
            return proj.last_recalc_date or proj.sum_data_date
        return None

    def _get_completion_date(self, schedule: ParsedSchedule) -> datetime | None:
        """Get the forecasted completion date.

        Strategy:
        1. Run CPM and find the latest early_finish on the critical path.
           Convert from float (days from project start) to a datetime using
           the project's plan_start_date.
        2. Fallback: use the latest ``early_end_date`` from any activity in
           the schedule.

        Args:
            schedule: A parsed schedule.

        Returns:
            The forecasted completion datetime, or ``None``.
        """
        # Fallback: latest early_end_date from raw data
        fallback_date: datetime | None = None
        for task in schedule.activities:
            if task.early_end_date and (
                fallback_date is None or task.early_end_date > fallback_date
            ):
                fallback_date = task.early_end_date

        # Try CPM-based completion
        try:
            cpm_result = CPMCalculator(schedule).calculate()
            if cpm_result.has_cycles or not cpm_result.critical_path:
                return fallback_date

            # Get latest early_finish on the CP
            max_ef = 0.0
            for tid in cpm_result.critical_path:
                ar = cpm_result.activity_results.get(tid)
                if ar and ar.early_finish > max_ef:
                    max_ef = ar.early_finish

            if max_ef > 0 and schedule.projects:
                plan_start = schedule.projects[0].plan_start_date
                if plan_start:
                    # CPM durations are in working days (8h/day)
                    # Convert to calendar days approx (5 working days = 7 calendar days)
                    calendar_days = max_ef * 7.0 / 5.0
                    return plan_start + timedelta(days=calendar_days)
        except Exception:
            logger.warning("CPM calculation failed for completion date extraction")

        return fallback_date

    def _get_critical_path_codes(self, schedule: ParsedSchedule) -> tuple[list[str], CPMResult | None]:
        """Get the critical path activity codes for a schedule.

        Args:
            schedule: A parsed schedule.

        Returns:
            Tuple of (list of task_codes on the CP, CPMResult or None).
        """
        try:
            cpm_result = CPMCalculator(schedule).calculate()
            if cpm_result.has_cycles:
                return [], None

            codes: list[str] = []
            for tid in cpm_result.critical_path:
                ar = cpm_result.activity_results.get(tid)
                if ar:
                    codes.append(ar.task_code or tid)
            return codes, cpm_result
        except Exception:
            logger.warning("CPM calculation failed for critical path extraction")
            return [], None

    def _get_driving_activity(self, schedule: ParsedSchedule) -> str:
        """Get the activity driving the completion date.

        The driving activity is the one with the latest early_finish on
        the critical path.

        Args:
            schedule: A parsed schedule.

        Returns:
            The task_code of the driving activity, or empty string.
        """
        try:
            cpm_result = CPMCalculator(schedule).calculate()
            if cpm_result.has_cycles or not cpm_result.critical_path:
                # Fallback: activity with latest early_end_date
                latest_task = None
                for task in schedule.activities:
                    if task.early_end_date and (
                        latest_task is None
                        or task.early_end_date > latest_task.early_end_date
                    ):
                        latest_task = task
                return latest_task.task_code if latest_task else ""

            max_ef = 0.0
            driving_code = ""
            for tid in cpm_result.critical_path:
                ar = cpm_result.activity_results.get(tid)
                if ar and ar.early_finish >= max_ef:
                    max_ef = ar.early_finish
                    driving_code = ar.task_code or tid
            return driving_code
        except Exception:
            logger.warning("CPM calculation failed for driving activity extraction")
            return ""

    def _analyze_window(
        self,
        baseline: ParsedSchedule,
        update: ParsedSchedule,
        base_id: str,
        upd_id: str,
        window_num: int,
        cumulative_delay: float,
    ) -> WindowResult:
        """Analyze a single window between two consecutive schedule updates.

        Per AACE RP 29R-03 MIP 3.3:
        - Get completion date at start and end of window
        - Calculate delay = completion_end - completion_start
        - Compare schedules for changes
        - Track critical path evolution

        Args:
            baseline: The earlier schedule.
            update: The later schedule.
            base_id: Project ID of baseline.
            upd_id: Project ID of update.
            window_num: Sequential window number.
            cumulative_delay: Running total of delay from prior windows.

        Returns:
            A ``WindowResult`` for this window.
        """
        window = AnalysisWindow(
            window_number=window_num,
            window_id=f"W{window_num:02d}",
            baseline_project_id=base_id,
            update_project_id=upd_id,
            start_date=self._get_data_date(baseline),
            end_date=self._get_data_date(update),
        )

        result = WindowResult(window=window)

        # Completion dates
        result.completion_date_start = self._get_completion_date(baseline)
        result.completion_date_end = self._get_completion_date(update)

        # Delay calculation
        if result.completion_date_start and result.completion_date_end:
            delta = result.completion_date_end - result.completion_date_start
            result.delay_days = delta.days
        else:
            result.delay_days = 0.0

        result.cumulative_delay = cumulative_delay + result.delay_days

        # Critical path analysis
        cp_start_codes, _ = self._get_critical_path_codes(baseline)
        cp_end_codes, _ = self._get_critical_path_codes(update)
        result.critical_path_start = cp_start_codes
        result.critical_path_end = cp_end_codes

        # CP evolution
        start_set = set(cp_start_codes)
        end_set = set(cp_end_codes)
        result.cp_activities_joined = sorted(end_set - start_set)
        result.cp_activities_left = sorted(start_set - end_set)

        # Driving activity
        result.driving_activity = self._get_driving_activity(update)

        # Full schedule comparison
        try:
            comparison = ScheduleComparison(baseline, update)
            result.comparison = comparison.compare()
        except Exception:
            logger.warning("Schedule comparison failed for window %d", window_num)

        return result

    def _build_summary(self, timeline: ForensicTimeline) -> dict[str, Any]:
        """Build a summary dictionary for the timeline.

        Args:
            timeline: The completed timeline.

        Returns:
            Dictionary with summary metrics.
        """
        windows_with_delay = sum(1 for w in timeline.windows if w.delay_days > 0)
        windows_with_acceleration = sum(1 for w in timeline.windows if w.delay_days < 0)
        max_delay_window = max(
            (w for w in timeline.windows),
            key=lambda w: w.delay_days,
            default=None,
        )
        max_accel_window = min(
            (w for w in timeline.windows),
            key=lambda w: w.delay_days,
            default=None,
        )
        cp_changed_count = sum(
            1 for w in timeline.windows
            if w.cp_activities_joined or w.cp_activities_left
        )

        return {
            "schedule_count": timeline.schedule_count,
            "window_count": len(timeline.windows),
            "total_delay_days": timeline.total_delay_days,
            "windows_with_delay": windows_with_delay,
            "windows_with_acceleration": windows_with_acceleration,
            "max_single_window_delay": max_delay_window.delay_days if max_delay_window else 0.0,
            "max_single_window_delay_id": max_delay_window.window.window_id if max_delay_window else "",
            "max_single_window_acceleration": max_accel_window.delay_days if max_accel_window else 0.0,
            "max_single_window_acceleration_id": max_accel_window.window.window_id if max_accel_window else "",
            "cp_changed_windows": cp_changed_count,
            "contract_completion": (
                timeline.contract_completion.isoformat()
                if timeline.contract_completion
                else None
            ),
            "current_completion": (
                timeline.current_completion.isoformat()
                if timeline.current_completion
                else None
            ),
        }
