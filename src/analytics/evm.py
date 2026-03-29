# MIT License
# Copyright (c) 2025 Vitor Maia Rodovalho
"""Earned Value Management analysis per ANSI/EIA-748.

Calculates standard EVM metrics (SPI, CPI, SV, CV, EAC, ETC, VAC, TCPI)
from XER resource assignment data and activity progress. Supports
project-level and WBS-level analysis with S-curve generation.

References:
    - ANSI/EIA-748: Earned Value Management Systems
    - AACE RP 10S-90: Cost Engineering Terminology
    - PMI Practice Standard for Earned Value Management
    - GAO-16-89G: Schedule Assessment Guide (Chapter 10: EVM Integration)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from src.parser.models import ParsedSchedule, Task, WBS

logger = logging.getLogger(__name__)


@dataclass
class EVMMetrics:
    """Earned Value Management metrics for a scope element.

    All monetary values are in the project's base currency.
    Index values are dimensionless ratios.

    Attributes:
        scope_name: Name of the scope element (project name or WBS name).
        scope_id: Identifier of the scope element.
        bac: Budget at Completion -- total planned budget.
        pv: Planned Value -- budgeted cost of work scheduled (BCWS).
        ev: Earned Value -- budgeted cost of work performed (BCWP).
        ac: Actual Cost -- actual cost of work performed (ACWP).
    """

    scope_name: str = ""
    scope_id: str = ""
    bac: float = 0.0
    pv: float = 0.0
    ev: float = 0.0
    ac: float = 0.0

    @property
    def sv(self) -> float:
        """Schedule Variance = EV - PV.

        Positive means ahead of schedule, negative means behind.
        Per ANSI/EIA-748 and AACE RP 10S-90.
        """
        return self.ev - self.pv

    @property
    def cv(self) -> float:
        """Cost Variance = EV - AC.

        Positive means under budget, negative means over budget.
        Per ANSI/EIA-748 and AACE RP 10S-90.
        """
        return self.ev - self.ac

    @property
    def spi(self) -> float:
        """Schedule Performance Index = EV / PV.

        > 1.0 means ahead of schedule, < 1.0 means behind.
        Returns 0.0 if PV is zero (no work scheduled yet).
        """
        return self.ev / self.pv if self.pv != 0 else 0.0

    @property
    def cpi(self) -> float:
        """Cost Performance Index = EV / AC.

        > 1.0 means under budget, < 1.0 means over budget.
        Returns 0.0 if AC is zero (no costs incurred yet).
        """
        return self.ev / self.ac if self.ac != 0 else 0.0

    @property
    def eac_cpi(self) -> float:
        """Estimate at Completion based on CPI = BAC / CPI.

        Assumes future work will be performed at the same cost efficiency.
        Per PMI Practice Standard for EVM.
        """
        return self.bac / self.cpi if self.cpi != 0 else 0.0

    @property
    def eac_combined(self) -> float:
        """Estimate at Completion based on combined SPI*CPI.

        EAC = AC + (BAC - EV) / (CPI * SPI)
        Accounts for both schedule and cost performance trends.
        """
        combined = self.cpi * self.spi
        if combined == 0:
            return 0.0
        return self.ac + (self.bac - self.ev) / combined

    @property
    def eac_etc_new(self) -> float:
        """Estimate at Completion with new ETC estimate.

        EAC = AC + (BAC - EV)
        Assumes remaining work will be completed at budgeted rates.
        """
        return self.ac + (self.bac - self.ev)

    @property
    def etc(self) -> float:
        """Estimate to Complete based on CPI = (BAC - EV) / CPI.

        Cost required to finish remaining work at current efficiency.
        """
        return (self.bac - self.ev) / self.cpi if self.cpi != 0 else 0.0

    @property
    def vac(self) -> float:
        """Variance at Completion = BAC - EAC (CPI-based).

        Positive means expected under budget, negative means over budget.
        """
        return self.bac - self.eac_cpi

    @property
    def tcpi(self) -> float:
        """To-Complete Performance Index = (BAC - EV) / (BAC - AC).

        The CPI required on remaining work to finish within budget.
        > 1.0 means must improve efficiency, < 1.0 means can relax.
        """
        denominator = self.bac - self.ac
        if denominator == 0:
            return 0.0
        return (self.bac - self.ev) / denominator

    @property
    def percent_complete_ev(self) -> float:
        """Percent complete by earned value = EV / BAC * 100."""
        return (self.ev / self.bac * 100) if self.bac != 0 else 0.0

    @property
    def percent_spent(self) -> float:
        """Percent spent = AC / BAC * 100."""
        return (self.ac / self.bac * 100) if self.bac != 0 else 0.0


@dataclass
class SCurvePoint:
    """A single data point on the S-curve.

    Attributes:
        date: The date for this data point.
        cumulative_pv: Cumulative Planned Value up to this date.
        cumulative_ev: Cumulative Earned Value up to this date.
        cumulative_ac: Cumulative Actual Cost up to this date.
    """

    date: str
    cumulative_pv: float = 0.0
    cumulative_ev: float = 0.0
    cumulative_ac: float = 0.0


@dataclass
class HealthClassification:
    """Health classification for a performance index.

    Attributes:
        index_name: Name of the index (e.g., "SPI", "CPI").
        value: The index value.
        status: One of "good", "watch", "critical".
        label: Human-readable label.
    """

    index_name: str
    value: float
    status: str
    label: str


@dataclass
class WBSMetrics:
    """EVM metrics for a single WBS element.

    Attributes:
        wbs_id: WBS identifier.
        wbs_name: WBS display name.
        metrics: The computed EVM metrics for this WBS.
        activity_count: Number of activities in this WBS.
    """

    wbs_id: str
    wbs_name: str
    metrics: EVMMetrics
    activity_count: int = 0


@dataclass
class EVMAnalysisResult:
    """Complete result of an EVM analysis.

    Attributes:
        analysis_id: Unique identifier for this analysis.
        project_name: Name of the analyzed project.
        project_id: Internal project store identifier.
        data_date: The project data date (schedule status date).
        metrics: Project-level EVM metrics.
        wbs_breakdown: EVM metrics per WBS element.
        s_curve: Time-phased S-curve data points.
        schedule_health: Schedule performance health classification.
        cost_health: Cost performance health classification.
        forecast: EAC scenario forecasts.
        summary: Additional summary information.
    """

    analysis_id: str = ""
    project_name: str = ""
    project_id: str = ""
    data_date: str | None = None
    metrics: EVMMetrics = field(default_factory=EVMMetrics)
    wbs_breakdown: list[WBSMetrics] = field(default_factory=list)
    s_curve: list[SCurvePoint] = field(default_factory=list)
    schedule_health: HealthClassification = field(
        default_factory=lambda: HealthClassification("SPI", 0.0, "critical", "No data")
    )
    cost_health: HealthClassification = field(
        default_factory=lambda: HealthClassification("CPI", 0.0, "critical", "No data")
    )
    forecast: dict[str, float] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)


class EVMAnalyzer:
    """Earned Value Management analyzer per ANSI/EIA-748.

    Takes a ParsedSchedule containing activities with resource assignments
    (TASKRSRC) and computes project-level and WBS-level EVM metrics.

    The analyzer extracts cost data from task_resources:
    - target_cost = budget (BAC component per assignment)
    - act_reg_cost = actual cost incurred
    - EV is computed from physical percent complete * budget per activity

    Planned Value (PV) is computed based on which activities should be
    complete or in-progress as of the data date, using their scheduled
    dates and budget allocation.

    Usage::

        analyzer = EVMAnalyzer(schedule)
        result = analyzer.analyze()
        print(f"SPI: {result.metrics.spi:.2f}")
        print(f"CPI: {result.metrics.cpi:.2f}")
    """

    def __init__(self, schedule: ParsedSchedule) -> None:
        """Initialize the EVM analyzer.

        Args:
            schedule: A parsed P6 schedule with activities and task_resources.
        """
        self._schedule = schedule
        self._data_date: datetime | None = None
        self._task_budgets: dict[str, float] = {}
        self._task_actuals: dict[str, float] = {}
        self._task_by_id: dict[str, Task] = {}
        self._wbs_by_id: dict[str, WBS] = {}
        self._tasks_by_wbs: dict[str, list[Task]] = {}

    def analyze(self) -> EVMAnalysisResult:
        """Run the full EVM analysis.

        Returns:
            An ``EVMAnalysisResult`` with project-level metrics, WBS
            breakdown, S-curve data, health classifications, and forecasts.
        """
        self._prepare_lookups()
        self._extract_cost_data()

        project_metrics = self._compute_project_metrics()
        wbs_breakdown = self._compute_wbs_breakdown()
        s_curve = self._generate_s_curve()
        schedule_health = self._classify_health("SPI", project_metrics.spi)
        cost_health = self._classify_health("CPI", project_metrics.cpi)
        forecast = self._build_forecast(project_metrics)

        project_name = ""
        data_date_str: str | None = None
        if self._schedule.projects:
            project_name = self._schedule.projects[0].proj_short_name
            if self._data_date:
                data_date_str = self._data_date.isoformat()

        result = EVMAnalysisResult(
            project_name=project_name,
            data_date=data_date_str,
            metrics=project_metrics,
            wbs_breakdown=wbs_breakdown,
            s_curve=s_curve,
            schedule_health=schedule_health,
            cost_health=cost_health,
            forecast=forecast,
            summary={
                "total_activities": len(self._schedule.activities),
                "activities_with_cost": len(self._task_budgets),
                "total_resource_assignments": len(self._schedule.task_resources),
                "wbs_elements_analyzed": len(wbs_breakdown),
            },
        )

        return result

    def _prepare_lookups(self) -> None:
        """Build internal lookup dictionaries for tasks, WBS, and data date."""
        # Data date
        if self._schedule.projects:
            proj = self._schedule.projects[0]
            self._data_date = proj.last_recalc_date or proj.sum_data_date

        # Task lookup
        for task in self._schedule.activities:
            self._task_by_id[task.task_id] = task

        # WBS lookup
        for wbs in self._schedule.wbs_nodes:
            self._wbs_by_id[wbs.wbs_id] = wbs

        # Group tasks by WBS
        for task in self._schedule.activities:
            if task.wbs_id not in self._tasks_by_wbs:
                self._tasks_by_wbs[task.wbs_id] = []
            self._tasks_by_wbs[task.wbs_id].append(task)

    def _extract_cost_data(self) -> None:
        """Extract budget and actual cost from TASKRSRC assignments.

        Aggregates target_cost and act_reg_cost per task_id across all
        resource assignments. Activities with no resource assignments
        will not appear in the cost dictionaries.
        """
        for tr in self._schedule.task_resources:
            tid = tr.task_id
            self._task_budgets[tid] = self._task_budgets.get(tid, 0.0) + tr.target_cost
            self._task_actuals[tid] = self._task_actuals.get(tid, 0.0) + tr.act_reg_cost

    def _compute_activity_pv(self, task: Task, budget: float) -> float:
        """Compute Planned Value for a single activity as of the data date.

        PV represents the budgeted cost of work that should have been
        accomplished by the data date based on the baseline schedule.

        Logic:
        - If the activity's target end date is on or before the data date,
          PV = 100% of budget (should be fully complete).
        - If the activity's target start date is after the data date,
          PV = 0 (work hasn't started in the plan yet).
        - If the data date falls within the activity's planned duration,
          PV is prorated linearly based on the fraction of planned
          duration that has elapsed.

        Args:
            task: The activity to compute PV for.
            budget: The total budget for this activity.

        Returns:
            The planned value for this activity as of the data date.
        """
        if self._data_date is None or budget == 0:
            return 0.0

        # Use target dates for PV (baseline schedule)
        start = task.target_start_date or task.early_start_date
        end = task.target_end_date or task.early_end_date

        if start is None or end is None:
            return 0.0

        if self._data_date >= end:
            return budget
        if self._data_date < start:
            return 0.0

        # Prorate: fraction of planned duration elapsed
        total_duration = (end - start).total_seconds()
        if total_duration <= 0:
            return budget  # Zero-duration activity (milestone)

        elapsed = (self._data_date - start).total_seconds()
        fraction = elapsed / total_duration
        return budget * min(fraction, 1.0)

    def _compute_activity_ev(self, task: Task, budget: float) -> float:
        """Compute Earned Value for a single activity.

        EV = physical percent complete * budget.

        Uses phys_complete_pct from the task (0-100 scale in P6).

        Args:
            task: The activity to compute EV for.
            budget: The total budget for this activity.

        Returns:
            The earned value for this activity.
        """
        pct = task.phys_complete_pct / 100.0 if task.phys_complete_pct else 0.0
        return budget * pct

    def _compute_project_metrics(self) -> EVMMetrics:
        """Compute project-level EVM metrics.

        Aggregates BAC, PV, EV, and AC across all activities that have
        resource cost assignments.

        Returns:
            Project-level ``EVMMetrics``.
        """
        bac = 0.0
        pv = 0.0
        ev = 0.0
        ac = 0.0

        for tid, budget in self._task_budgets.items():
            task = self._task_by_id.get(tid)
            if task is None:
                continue

            bac += budget
            pv += self._compute_activity_pv(task, budget)
            ev += self._compute_activity_ev(task, budget)
            ac += self._task_actuals.get(tid, 0.0)

        project_name = ""
        if self._schedule.projects:
            project_name = self._schedule.projects[0].proj_short_name

        return EVMMetrics(
            scope_name=project_name,
            scope_id="project",
            bac=round(bac, 2),
            pv=round(pv, 2),
            ev=round(ev, 2),
            ac=round(ac, 2),
        )

    def _compute_wbs_breakdown(self) -> list[WBSMetrics]:
        """Compute EVM metrics for each WBS element.

        Only WBS elements that have at least one activity with cost data
        are included in the breakdown.

        Returns:
            List of ``WBSMetrics``, one per WBS with cost data.
        """
        wbs_results: list[WBSMetrics] = []

        for wbs_id, tasks in self._tasks_by_wbs.items():
            bac = 0.0
            pv = 0.0
            ev = 0.0
            ac = 0.0
            cost_task_count = 0

            for task in tasks:
                budget = self._task_budgets.get(task.task_id, 0.0)
                if budget == 0 and self._task_actuals.get(task.task_id, 0.0) == 0:
                    continue

                cost_task_count += 1
                bac += budget
                pv += self._compute_activity_pv(task, budget)
                ev += self._compute_activity_ev(task, budget)
                ac += self._task_actuals.get(task.task_id, 0.0)

            if cost_task_count == 0:
                continue

            wbs = self._wbs_by_id.get(wbs_id)
            wbs_name = wbs.wbs_name if wbs else wbs_id

            metrics = EVMMetrics(
                scope_name=wbs_name,
                scope_id=wbs_id,
                bac=round(bac, 2),
                pv=round(pv, 2),
                ev=round(ev, 2),
                ac=round(ac, 2),
            )

            wbs_results.append(
                WBSMetrics(
                    wbs_id=wbs_id,
                    wbs_name=wbs_name,
                    metrics=metrics,
                    activity_count=cost_task_count,
                )
            )

        return wbs_results

    def _generate_s_curve(self) -> list[SCurvePoint]:
        """Generate time-phased S-curve data.

        Creates data points at regular intervals from the earliest activity
        start to the latest activity end (or data date, whichever is later),
        computing cumulative PV, EV, and AC at each point.

        The S-curve uses weekly intervals for schedules spanning more than
        30 days, otherwise daily intervals.

        Returns:
            List of ``SCurvePoint`` instances ordered by date.
        """
        if not self._task_budgets:
            return []

        # Find date range from activities with cost data
        min_date: datetime | None = None
        max_date: datetime | None = None

        for tid in self._task_budgets:
            task = self._task_by_id.get(tid)
            if task is None:
                continue

            start = task.target_start_date or task.early_start_date
            end = task.target_end_date or task.early_end_date

            if start:
                if min_date is None or start < min_date:
                    min_date = start
            if end:
                if max_date is None or end > max_date:
                    max_date = end

        if min_date is None or max_date is None:
            return []

        # Extend to data date if it's later
        if self._data_date and self._data_date > max_date:
            max_date = self._data_date

        # Determine interval
        total_days = (max_date - min_date).days
        if total_days <= 0:
            return []

        interval_days = 7 if total_days > 30 else 1
        points: list[SCurvePoint] = []
        current = min_date

        while current <= max_date:
            cum_pv = 0.0
            cum_ev = 0.0
            cum_ac = 0.0

            for tid, budget in self._task_budgets.items():
                task = self._task_by_id.get(tid)
                if task is None:
                    continue

                # PV at this point in time
                start = task.target_start_date or task.early_start_date
                end = task.target_end_date or task.early_end_date

                if start and end:
                    if current >= end:
                        cum_pv += budget
                    elif current >= start:
                        total_dur = (end - start).total_seconds()
                        if total_dur > 0:
                            elapsed = (current - start).total_seconds()
                            cum_pv += budget * min(elapsed / total_dur, 1.0)
                        else:
                            cum_pv += budget

                # EV and AC are cumulative up to data date, not time-phased
                # For S-curve, we approximate: EV/AC accrue proportionally
                # to actual progress, which we model as linear up to data date
                if self._data_date and current <= self._data_date:
                    actual_cost = self._task_actuals.get(tid, 0.0)
                    earned = self._compute_activity_ev(task, budget)

                    act_start = task.act_start_date or start
                    act_end = task.act_end_date

                    if act_start:
                        if act_end and current >= act_end:
                            cum_ev += earned
                            cum_ac += actual_cost
                        elif current >= act_start:
                            if act_end:
                                total_act_dur = (act_end - act_start).total_seconds()
                            elif self._data_date:
                                total_act_dur = (self._data_date - act_start).total_seconds()
                            else:
                                total_act_dur = 0

                            if total_act_dur > 0:
                                act_elapsed = (current - act_start).total_seconds()
                                frac = min(act_elapsed / total_act_dur, 1.0)
                                cum_ev += earned * frac
                                cum_ac += actual_cost * frac

            points.append(
                SCurvePoint(
                    date=current.strftime("%Y-%m-%d"),
                    cumulative_pv=round(cum_pv, 2),
                    cumulative_ev=round(cum_ev, 2),
                    cumulative_ac=round(cum_ac, 2),
                )
            )

            current += timedelta(days=interval_days)

        return points

    @staticmethod
    def _classify_health(index_name: str, value: float) -> HealthClassification:
        """Classify a performance index as good, watch, or critical.

        Thresholds per AACE RP 10S-90 and common industry practice:
        - >= 1.0: Good (on track or better)
        - 0.9 to 1.0: Watch (minor variance, needs attention)
        - < 0.9: Critical (significant adverse trend)
        - 0.0: No data available

        Args:
            index_name: "SPI" or "CPI".
            value: The performance index value.

        Returns:
            A ``HealthClassification`` with status and label.
        """
        if value == 0.0:
            return HealthClassification(
                index_name=index_name,
                value=value,
                status="critical",
                label="No data",
            )
        if value >= 1.0:
            return HealthClassification(
                index_name=index_name,
                value=round(value, 3),
                status="good",
                label="On track" if value < 1.05 else "Ahead",
            )
        if value >= 0.9:
            return HealthClassification(
                index_name=index_name,
                value=round(value, 3),
                status="watch",
                label="Minor variance",
            )
        return HealthClassification(
            index_name=index_name,
            value=round(value, 3),
            status="critical",
            label="Significant adverse trend",
        )

    @staticmethod
    def _build_forecast(metrics: EVMMetrics) -> dict[str, float]:
        """Build a forecast dictionary with multiple EAC scenarios.

        Args:
            metrics: The project-level EVM metrics.

        Returns:
            Dictionary with forecast scenario names and values.
        """
        return {
            "bac": round(metrics.bac, 2),
            "eac_cpi": round(metrics.eac_cpi, 2),
            "eac_combined": round(metrics.eac_combined, 2),
            "eac_etc_new": round(metrics.eac_etc_new, 2),
            "etc": round(metrics.etc, 2),
            "vac": round(metrics.vac, 2),
            "tcpi": round(metrics.tcpi, 3),
        }
