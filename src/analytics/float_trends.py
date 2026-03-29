# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Float Trend Analysis engine per AACE RP 49R-06.

Tracks how total float for each activity changes across schedule updates.
Float consumption without proportional progress indicates schedule
deterioration.  Produces Float Erosion Index, Near-Critical Drift,
Critical Path Stability, Float Consumption Velocity per WBS, and
per-activity float deltas.

Standards:
    - AACE RP 49R-06 — Identifying Critical Activities
    - PMI Practice Standard for Scheduling §6.6 — Float Management
    - DCMA 14-Point checks #3 (High Float), #4 (Negative Float)
    - Kim & de la Garza (2005) — Phantom float detection

References:
    - GAO Schedule Assessment Guide §7.3 — Critical Path Stability
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.analytics.cpm import CPMCalculator
from src.parser.models import ParsedSchedule, Task

logger = logging.getLogger(__name__)

# Hours per working day (P6 default)
_HOURS_PER_DAY = 8.0

# Near-critical threshold in hours (10 days * 8 h/day = 80 hours)
_NEAR_CRITICAL_THRESHOLD_HOURS = 10 * _HOURS_PER_DAY

# Float erosion: activity must have lost more than this many hours of float
_EROSION_THRESHOLD_HOURS = 5 * _HOURS_PER_DAY

# Progress threshold: activity must have less than this % progress to count as eroded
_EROSION_PROGRESS_THRESHOLD = 50.0


@dataclass
class ActivityFloatTrend:
    """Float change for a single matched activity between baseline and update.

    Attributes:
        task_code: The P6 user-visible activity code.
        task_name: The activity description.
        wbs_id: The WBS element the activity belongs to.
        old_float_days: Total float in the baseline (days).
        new_float_days: Total float in the update (days).
        delta_days: Change in total float (days, negative = lost float).
        direction: 'improving', 'stable', or 'deteriorating'.
        is_critical_baseline: Whether the activity was critical in baseline.
        is_critical_update: Whether the activity is critical in update.
        progress_pct: Physical percent complete in the update schedule.
    """

    task_code: str
    task_name: str = ""
    wbs_id: str = ""
    old_float_days: float = 0.0
    new_float_days: float = 0.0
    delta_days: float = 0.0
    direction: str = "stable"
    is_critical_baseline: bool = False
    is_critical_update: bool = False
    progress_pct: float = 0.0


@dataclass
class FloatTrendResult:
    """Complete float trend analysis output.

    Attributes:
        fei: Float Erosion Index — % of activities that lost float without
            proportional progress (0–100).  Per AACE RP 49R-06.
        near_critical_drift: Count of activities that crossed from above to
            at-or-below the 10-day TF threshold (per DCMA #3).
        cp_stability: % of critical-path activities that remain on the CP
            between baseline and update (0–100).  Per GAO §7.3.
        activity_trends: Per-activity float trend data.
        wbs_velocity: Average float days lost per calendar day, keyed by WBS
            ID.  Positive = losing float.
        thresholds: Green/yellow/red status for each aggregate metric.
        days_between_updates: Calendar days between baseline and update data
            dates (used for velocity calculations).
        total_matched: Number of activities matched between schedules.
        summary: Aggregate statistics dict.
    """

    fei: float = 0.0
    near_critical_drift: int = 0
    cp_stability: float = 100.0
    activity_trends: list[ActivityFloatTrend] = field(default_factory=list)
    wbs_velocity: dict[str, float] = field(default_factory=dict)
    thresholds: dict[str, dict[str, Any]] = field(default_factory=dict)
    days_between_updates: float = 0.0
    total_matched: int = 0
    summary: dict[str, Any] = field(default_factory=dict)


class FloatTrendAnalyzer:
    """Analyze float trends between two schedule snapshots.

    Implements float trend metrics per AACE RP 49R-06 and GAO Schedule
    Assessment Guide.  Matches activities by ``task_code`` (same strategy
    as ``ScheduleComparison``).

    Usage::

        analyzer = FloatTrendAnalyzer(baseline, update)
        result = analyzer.analyze()
        print(f"Float Erosion Index: {result.fei:.1f}%")
        print(f"Near-Critical Drift: {result.near_critical_drift}")
        print(f"CP Stability: {result.cp_stability:.1f}%")

    Args:
        baseline: The earlier (baseline) parsed schedule.
        update: The later (update) parsed schedule.
        hours_per_day: Hours per working day for float conversion.
    """

    # Threshold definitions per DCMA + industry consensus
    THRESHOLDS = {
        "fei": {"green": 10.0, "yellow": 25.0},  # < 10% green, 10-25% yellow, > 25% red
        "near_critical_drift_pct": {
            "green": 5.0,
            "yellow": 15.0,
        },  # < 5% green, 5-15% yellow, > 15% red
        "cp_stability": {"green": 80.0, "yellow": 60.0},  # > 80% green, 60-80% yellow, < 60% red
    }

    def __init__(
        self,
        baseline: ParsedSchedule,
        update: ParsedSchedule,
        hours_per_day: float = _HOURS_PER_DAY,
    ) -> None:
        self.baseline = baseline
        self.update = update
        self.hours_per_day = hours_per_day

        # Match activities by task_code (same as comparison engine)
        self._base_by_code: dict[str, Task] = {
            t.task_code: t for t in baseline.activities if t.task_code
        }
        self._upd_by_code: dict[str, Task] = {
            t.task_code: t for t in update.activities if t.task_code
        }
        self._matched_codes: set[str] = set(self._base_by_code.keys()) & set(
            self._upd_by_code.keys()
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self) -> FloatTrendResult:
        """Run the full float trend analysis.

        Returns:
            A ``FloatTrendResult`` populated with all metrics.
        """
        result = FloatTrendResult(total_matched=len(self._matched_codes))

        # Calculate days between data dates
        result.days_between_updates = self._calendar_days_between()

        # Run CPM on both to identify critical paths
        base_cp_codes = self._get_cp_task_codes(self.baseline)
        upd_cp_codes = self._get_cp_task_codes(self.update)

        # Build per-activity trends
        activity_trends = self._build_activity_trends(base_cp_codes, upd_cp_codes)
        result.activity_trends = activity_trends

        # Compute FEI
        result.fei = self._compute_fei(activity_trends)

        # Compute Near-Critical Drift
        result.near_critical_drift = self._compute_near_critical_drift(activity_trends)

        # Compute CP Stability
        result.cp_stability = self._compute_cp_stability(base_cp_codes, upd_cp_codes)

        # Compute WBS float velocity
        result.wbs_velocity = self._compute_wbs_velocity(
            activity_trends, result.days_between_updates
        )

        # Compute threshold statuses
        result.thresholds = self._evaluate_thresholds(result)

        # Summary
        result.summary = self._build_summary(result)

        return result

    # ------------------------------------------------------------------
    # Activity matching and trend building
    # ------------------------------------------------------------------

    def _build_activity_trends(
        self,
        base_cp_codes: set[str],
        upd_cp_codes: set[str],
    ) -> list[ActivityFloatTrend]:
        """Build per-activity float trends for all matched activities.

        Filters out LOE and WBS summary activities.
        """
        trends: list[ActivityFloatTrend] = []

        for code in sorted(self._matched_codes):
            base_t = self._base_by_code[code]
            upd_t = self._upd_by_code[code]

            # Skip LOE and WBS summary types
            if base_t.task_type.lower() in ("tt_loe", "tt_wbs"):
                continue

            old_float_hr = base_t.total_float_hr_cnt
            new_float_hr = upd_t.total_float_hr_cnt

            if old_float_hr is None or new_float_hr is None:
                continue

            old_float_days = old_float_hr / self.hours_per_day
            new_float_days = new_float_hr / self.hours_per_day
            delta_days = new_float_days - old_float_days

            if abs(delta_days) < 0.01:
                direction = "stable"
            elif delta_days > 0:
                direction = "improving"
            else:
                direction = "deteriorating"

            trends.append(
                ActivityFloatTrend(
                    task_code=code,
                    task_name=upd_t.task_name,
                    wbs_id=upd_t.wbs_id,
                    old_float_days=round(old_float_days, 2),
                    new_float_days=round(new_float_days, 2),
                    delta_days=round(delta_days, 2),
                    direction=direction,
                    is_critical_baseline=code in base_cp_codes,
                    is_critical_update=code in upd_cp_codes,
                    progress_pct=upd_t.phys_complete_pct,
                )
            )

        return trends

    # ------------------------------------------------------------------
    # FEI — Float Erosion Index
    # ------------------------------------------------------------------

    def _compute_fei(self, trends: list[ActivityFloatTrend]) -> float:
        """Compute Float Erosion Index.

        FEI = % of activities that lost > 5 days of float without
        proportional progress (< 50% complete).

        Per AACE RP 49R-06 definition of float erosion.

        Returns:
            FEI as a percentage (0–100).
        """
        if not trends:
            return 0.0

        eroded_count = 0
        for trend in trends:
            lost_days = -trend.delta_days  # positive when float decreased
            if (
                lost_days > _EROSION_THRESHOLD_HOURS / self.hours_per_day
                and trend.progress_pct < _EROSION_PROGRESS_THRESHOLD
            ):
                eroded_count += 1

        return round((eroded_count / len(trends)) * 100, 2)

    # ------------------------------------------------------------------
    # Near-Critical Drift
    # ------------------------------------------------------------------

    def _compute_near_critical_drift(self, trends: list[ActivityFloatTrend]) -> int:
        """Count activities that crossed from above to at-or-below 10-day TF.

        Per DCMA check #3 near-critical threshold.

        Returns:
            Count of activities that drifted into near-critical zone.
        """
        threshold_days = _NEAR_CRITICAL_THRESHOLD_HOURS / self.hours_per_day
        count = 0

        for trend in trends:
            if trend.old_float_days > threshold_days and trend.new_float_days <= threshold_days:
                count += 1

        return count

    # ------------------------------------------------------------------
    # Critical Path Stability
    # ------------------------------------------------------------------

    def _compute_cp_stability(self, base_cp_codes: set[str], upd_cp_codes: set[str]) -> float:
        """Compute Critical Path Stability metric.

        CP Stability = % of baseline CP activities that remain on the CP in
        the update.  Per GAO Schedule Assessment Guide §7.3.

        Returns:
            CP Stability as a percentage (0–100).
        """
        if not base_cp_codes:
            return 100.0

        unchanged = base_cp_codes & upd_cp_codes
        return round((len(unchanged) / len(base_cp_codes)) * 100, 2)

    # ------------------------------------------------------------------
    # WBS Float Consumption Velocity
    # ------------------------------------------------------------------

    def _compute_wbs_velocity(
        self,
        trends: list[ActivityFloatTrend],
        days_between: float,
    ) -> dict[str, float]:
        """Compute average float days lost per calendar day, per WBS.

        A positive value indicates float is being consumed.  The velocity
        is useful for identifying WBS areas with the fastest deterioration.

        Returns:
            Dict mapping WBS ID to float consumption velocity (days/day).
        """
        if days_between <= 0:
            return {}

        # Accumulate float loss by WBS
        wbs_loss: dict[str, list[float]] = {}
        for trend in trends:
            wbs_id = trend.wbs_id or "UNASSIGNED"
            wbs_loss.setdefault(wbs_id, []).append(-trend.delta_days)  # positive = loss

        # Average loss per calendar day
        velocity: dict[str, float] = {}
        for wbs_id, losses in wbs_loss.items():
            avg_loss = sum(losses) / len(losses) if losses else 0.0
            velocity[wbs_id] = round(avg_loss / days_between, 4)

        return velocity

    # ------------------------------------------------------------------
    # Threshold evaluation
    # ------------------------------------------------------------------

    def _evaluate_thresholds(self, result: FloatTrendResult) -> dict[str, dict[str, Any]]:
        """Evaluate green/yellow/red status for each metric.

        Thresholds per DCMA + industry consensus (from discovery doc):
            FEI:        < 10% green, 10-25% yellow, > 25% red
            NC Drift:   < 5% green, 5-15% yellow, > 15% red
            CP Stab:    > 80% green, 60-80% yellow, < 60% red
        """
        thresholds: dict[str, dict[str, Any]] = {}

        # FEI
        fei = result.fei
        if fei < self.THRESHOLDS["fei"]["green"]:
            fei_status = "green"
        elif fei <= self.THRESHOLDS["fei"]["yellow"]:
            fei_status = "yellow"
        else:
            fei_status = "red"
        thresholds["fei"] = {"value": fei, "status": fei_status, "unit": "%"}

        # Near-critical drift (as % of total)
        total = result.total_matched or 1
        nc_pct = (result.near_critical_drift / total) * 100
        if nc_pct < self.THRESHOLDS["near_critical_drift_pct"]["green"]:
            nc_status = "green"
        elif nc_pct <= self.THRESHOLDS["near_critical_drift_pct"]["yellow"]:
            nc_status = "yellow"
        else:
            nc_status = "red"
        thresholds["near_critical_drift"] = {
            "value": result.near_critical_drift,
            "percentage": round(nc_pct, 2),
            "status": nc_status,
        }

        # CP Stability
        cp = result.cp_stability
        if cp >= self.THRESHOLDS["cp_stability"]["green"]:
            cp_status = "green"
        elif cp >= self.THRESHOLDS["cp_stability"]["yellow"]:
            cp_status = "yellow"
        else:
            cp_status = "red"
        thresholds["cp_stability"] = {"value": cp, "status": cp_status, "unit": "%"}

        return thresholds

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_cp_task_codes(self, schedule: ParsedSchedule) -> set[str]:
        """Run CPM and return the set of task_codes on the critical path."""
        try:
            cpm = CPMCalculator(schedule, hours_per_day=self.hours_per_day)
            cpm_result = cpm.calculate()
        except Exception:
            logger.warning("CPM calculation failed during float trend analysis")
            return set()

        if cpm_result.has_cycles:
            logger.warning("Schedule has cycles — cannot determine critical path")
            return set()

        # Map task_id back to task_code
        id_to_code = {t.task_id: t.task_code for t in schedule.activities if t.task_code}
        return {id_to_code[tid] for tid in cpm_result.critical_path if tid in id_to_code}

    def _calendar_days_between(self) -> float:
        """Compute calendar days between baseline and update data dates.

        Uses the first project's last_recalc_date or sum_data_date.

        Returns:
            Calendar days between data dates, or 0.0 if unavailable.
        """
        base_date = self._get_data_date(self.baseline)
        upd_date = self._get_data_date(self.update)

        if base_date and upd_date:
            delta = (upd_date - base_date).days
            return float(max(delta, 0))

        return 0.0

    @staticmethod
    def _get_data_date(schedule: ParsedSchedule) -> datetime | None:
        """Extract the data date from a schedule."""
        if schedule.projects:
            proj = schedule.projects[0]
            return proj.last_recalc_date or proj.sum_data_date
        return None

    def _build_summary(self, result: FloatTrendResult) -> dict[str, Any]:
        """Build aggregate summary statistics."""
        improving = sum(1 for t in result.activity_trends if t.direction == "improving")
        deteriorating = sum(1 for t in result.activity_trends if t.direction == "deteriorating")
        stable = sum(1 for t in result.activity_trends if t.direction == "stable")

        return {
            "total_matched": result.total_matched,
            "total_with_float_data": len(result.activity_trends),
            "improving": improving,
            "deteriorating": deteriorating,
            "stable": stable,
            "fei": result.fei,
            "near_critical_drift": result.near_critical_drift,
            "cp_stability": result.cp_stability,
            "days_between_updates": result.days_between_updates,
        }
