# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""DCMA 14-Point Schedule Assessment.

Implements the Defence Contract Management Agency 14-point check used
to assess the health of a project schedule.  Each metric is compared
against industry-standard thresholds and the overall result is reported
as a composite score.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


@dataclass
class MetricResult:
    """Result of a single DCMA metric check."""

    number: int
    name: str
    description: str
    value: float
    threshold: float
    unit: str = "%"
    passed: bool = True
    direction: str = "max"  # "max" means higher is better; "min" means lower
    details: str = ""


@dataclass
class DCMA14Result:
    """Full DCMA 14-point assessment output."""

    metrics: list[MetricResult] = field(default_factory=list)
    overall_score: float = 0.0
    passed_count: int = 0
    failed_count: int = 0
    data_date: datetime | None = None
    activity_count: int = 0


class DCMA14Analyzer:
    """Run the DCMA 14-point assessment on a parsed P6 schedule.

    Usage::

        analyzer = DCMA14Analyzer(schedule)
        result = analyzer.analyze()
        for m in result.metrics:
            status = "PASS" if m.passed else "FAIL"
            print(f"  {m.number}. {m.name}: {m.value:.1f}{m.unit} [{status}]")
    """

    # Threshold constants for standard DCMA checks
    LOGIC_THRESHOLD = 90.0  # >= 90% with both pred and succ
    LEADS_THRESHOLD = 0.0  # 0% with negative lag
    LAGS_THRESHOLD = 5.0  # <= 5% with positive lag
    FS_THRESHOLD = 90.0  # >= 90% FS relationships
    CONSTRAINTS_THRESHOLD = 5.0  # <= 5% with constraints
    HIGH_FLOAT_THRESHOLD = 5.0  # <= 5% with TF > 44 days
    NEGATIVE_FLOAT_THRESHOLD = 0.0  # 0% with negative TF
    HIGH_DURATION_THRESHOLD = 5.0  # <= 5% with dur > 44 working days
    INVALID_DATES_THRESHOLD = 0.0  # 0% with future actual dates
    RESOURCES_THRESHOLD = 90.0  # >= 90% with resources
    MISSED_TASKS_THRESHOLD = 5.0  # <= 5% missed tasks

    # 44 working days threshold in hours (assuming 8h/day)
    HIGH_FLOAT_HOURS = 44.0 * 8.0
    HIGH_DURATION_HOURS = 44.0 * 8.0

    def __init__(
        self,
        schedule: ParsedSchedule,
        data_date: datetime | None = None,
        hours_per_day: float = 8.0,
    ) -> None:
        """Initialise the analyser.

        Args:
            schedule: Parsed XER schedule.
            data_date: The schedule data date. If not provided, the first
                project's ``last_recalc_date`` or ``sum_data_date`` is used.
            hours_per_day: Hours per working day for conversions.
        """
        self.schedule = schedule
        self.hours_per_day = hours_per_day

        # Cycle 5 W4 hygiene: explicit attribute type so mypy --strict does
        # not infer ``datetime`` from the first branch and reject the
        # nullable assignments in the elif/else branches.
        self.data_date: datetime | None
        if data_date:
            self.data_date = data_date
        elif schedule.projects:
            proj = schedule.projects[0]
            self.data_date = proj.last_recalc_date or proj.sum_data_date
        else:
            self.data_date = None

        # Pre-compute lookup sets
        self._task_ids_with_pred: set[str] = set()
        self._task_ids_with_succ: set[str] = set()
        for rel in schedule.relationships:
            self._task_ids_with_pred.add(rel.task_id)  # successor has a pred
            self._task_ids_with_succ.add(rel.pred_task_id)  # predecessor has a succ

        self._task_ids_with_resources: set[str] = {tr.task_id for tr in schedule.task_resources}

        # Filter to incomplete activities only (non-LOE, non-WBS summary)
        # Use case-insensitive comparison — P6 versions vary in case
        self._incomplete: list[Any] = [
            t
            for t in schedule.activities
            if t.status_code.lower() != "tk_complete"
            and t.task_type.lower() not in ("tt_loe", "tt_wbs")
        ]

        # All non-LOE/WBS activities
        self._all_countable: list[Any] = [
            t for t in schedule.activities if t.task_type.lower() not in ("tt_loe", "tt_wbs")
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self) -> DCMA14Result:
        """Run all 14 checks and return the assessment.

        Returns:
            ``DCMA14Result`` with per-metric details and overall score.
        """
        result = DCMA14Result(
            data_date=self.data_date,
            activity_count=len(self._all_countable),
        )

        result.metrics.append(self._check_logic())
        result.metrics.append(self._check_leads())
        result.metrics.append(self._check_lags())
        result.metrics.append(self._check_relationship_types())
        result.metrics.append(self._check_hard_constraints())
        result.metrics.append(self._check_high_float())
        result.metrics.append(self._check_negative_float())
        result.metrics.append(self._check_high_duration())
        result.metrics.append(self._check_invalid_dates())
        result.metrics.append(self._check_resources())
        result.metrics.append(self._check_missed_tasks())
        result.metrics.append(self._check_critical_path_test())
        result.metrics.append(self._check_cpli())
        result.metrics.append(self._check_bei())

        result.passed_count = sum(1 for m in result.metrics if m.passed)
        result.failed_count = sum(1 for m in result.metrics if not m.passed)

        # Overall score: each of the 14 checks is worth equal weight
        if result.metrics:
            result.overall_score = round((result.passed_count / len(result.metrics)) * 100, 1)

        return result

    # ------------------------------------------------------------------
    # Individual metric checks
    # ------------------------------------------------------------------

    def _safe_pct(self, numerator: int, denominator: int) -> float:
        """Calculate a percentage safely, returning 0 if denominator is zero."""
        if denominator == 0:
            return 0.0
        return round((numerator / denominator) * 100, 2)

    def _check_logic(self) -> MetricResult:
        """Check 1: Logic -- % of activities with both pred and succ.

        Target: >= 90%.
        """
        total = len(self._all_countable)
        with_both = sum(
            1
            for t in self._all_countable
            if t.task_id in self._task_ids_with_pred and t.task_id in self._task_ids_with_succ
        )
        pct = self._safe_pct(with_both, total)
        return MetricResult(
            number=1,
            name="Logic",
            description="Activities with both predecessor and successor",
            value=pct,
            threshold=self.LOGIC_THRESHOLD,
            direction="max",
            passed=pct >= self.LOGIC_THRESHOLD,
            details=f"{with_both}/{total} activities have complete logic",
        )

    def _check_leads(self) -> MetricResult:
        """Check 2: Leads -- % of relationships with negative lag.

        Target: 0%.
        """
        total = len(self.schedule.relationships)
        with_leads = sum(1 for r in self.schedule.relationships if r.lag_hr_cnt < 0)
        pct = self._safe_pct(with_leads, total)
        return MetricResult(
            number=2,
            name="Leads",
            description="Relationships with negative lag (leads)",
            value=pct,
            threshold=self.LEADS_THRESHOLD,
            direction="min",
            passed=pct <= self.LEADS_THRESHOLD,
            details=f"{with_leads}/{total} relationships have leads",
        )

    def _check_lags(self) -> MetricResult:
        """Check 3: Lags -- % of relationships with positive lag.

        Target: <= 5%.
        """
        total = len(self.schedule.relationships)
        with_lags = sum(1 for r in self.schedule.relationships if r.lag_hr_cnt > 0)
        pct = self._safe_pct(with_lags, total)
        return MetricResult(
            number=3,
            name="Lags",
            description="Relationships with positive lag",
            value=pct,
            threshold=self.LAGS_THRESHOLD,
            direction="min",
            passed=pct <= self.LAGS_THRESHOLD,
            details=f"{with_lags}/{total} relationships have lags",
        )

    def _check_relationship_types(self) -> MetricResult:
        """Check 4: Relationship Types -- % that are Finish-to-Start.

        Target: >= 90%.
        """
        total = len(self.schedule.relationships)
        fs_count = sum(1 for r in self.schedule.relationships if r.pred_type in ("PR_FS", "FS"))
        pct = self._safe_pct(fs_count, total)
        return MetricResult(
            number=4,
            name="Relationship Types",
            description="Finish-to-Start relationships",
            value=pct,
            threshold=self.FS_THRESHOLD,
            direction="max",
            passed=pct >= self.FS_THRESHOLD,
            details=f"{fs_count}/{total} relationships are FS",
        )

    def _check_hard_constraints(self) -> MetricResult:
        """Check 5: Hard Constraints -- % of activities with constraints.

        Target: <= 5%.
        """
        total = len(self._all_countable)
        constrained = sum(1 for t in self._all_countable if t.cstr_type and t.cstr_type.strip())
        pct = self._safe_pct(constrained, total)
        return MetricResult(
            number=5,
            name="Hard Constraints",
            description="Activities with date constraints",
            value=pct,
            threshold=self.CONSTRAINTS_THRESHOLD,
            direction="min",
            passed=pct <= self.CONSTRAINTS_THRESHOLD,
            details=f"{constrained}/{total} activities have constraints",
        )

    def _check_high_float(self) -> MetricResult:
        """Check 6: High Float -- % with TF > 44 working days.

        Target: <= 5%.
        """
        total = len(self._incomplete)
        high = sum(
            1
            for t in self._incomplete
            if t.total_float_hr_cnt is not None and t.total_float_hr_cnt > self.HIGH_FLOAT_HOURS
        )
        pct = self._safe_pct(high, total)
        return MetricResult(
            number=6,
            name="High Float",
            description="Incomplete activities with total float > 44 days",
            value=pct,
            threshold=self.HIGH_FLOAT_THRESHOLD,
            direction="min",
            passed=pct <= self.HIGH_FLOAT_THRESHOLD,
            details=f"{high}/{total} incomplete activities have high float",
        )

    def _check_negative_float(self) -> MetricResult:
        """Check 7: Negative Float -- % with negative TF.

        Target: 0%.
        """
        total = len(self._incomplete)
        negative = sum(
            1
            for t in self._incomplete
            if t.total_float_hr_cnt is not None and t.total_float_hr_cnt < 0
        )
        pct = self._safe_pct(negative, total)
        return MetricResult(
            number=7,
            name="Negative Float",
            description="Incomplete activities with negative total float",
            value=pct,
            threshold=self.NEGATIVE_FLOAT_THRESHOLD,
            direction="min",
            passed=pct <= self.NEGATIVE_FLOAT_THRESHOLD,
            details=f"{negative}/{total} incomplete activities have negative float",
        )

    def _check_high_duration(self) -> MetricResult:
        """Check 8: High Duration -- % with duration > 44 working days.

        Target: <= 5%.
        """
        total = len(self._incomplete)
        high = sum(1 for t in self._incomplete if t.remain_drtn_hr_cnt > self.HIGH_DURATION_HOURS)
        pct = self._safe_pct(high, total)
        return MetricResult(
            number=8,
            name="High Duration",
            description="Incomplete activities with duration > 44 working days",
            value=pct,
            threshold=self.HIGH_DURATION_THRESHOLD,
            direction="min",
            passed=pct <= self.HIGH_DURATION_THRESHOLD,
            details=f"{high}/{total} incomplete activities have high duration",
        )

    def _check_invalid_dates(self) -> MetricResult:
        """Check 9: Invalid Dates -- actual dates in the future of data date.

        Target: 0%.
        """
        if not self.data_date:
            return MetricResult(
                number=9,
                name="Invalid Dates",
                description="Actual dates in the future of the data date",
                value=0.0,
                threshold=self.INVALID_DATES_THRESHOLD,
                direction="min",
                passed=True,
                details="No data date available -- check skipped",
            )

        total = len(self._all_countable)
        invalid = 0
        for t in self._all_countable:
            if t.act_start_date and t.act_start_date > self.data_date:
                invalid += 1
            elif t.act_end_date and t.act_end_date > self.data_date:
                invalid += 1
        pct = self._safe_pct(invalid, total)
        return MetricResult(
            number=9,
            name="Invalid Dates",
            description="Activities with actual dates after data date",
            value=pct,
            threshold=self.INVALID_DATES_THRESHOLD,
            direction="min",
            passed=pct <= self.INVALID_DATES_THRESHOLD,
            details=f"{invalid}/{total} activities have future actual dates",
        )

    def _check_resources(self) -> MetricResult:
        """Check 10: Resources -- % of activities with resource assignments.

        Target: >= 90%.
        """
        # Exclude milestones from resource check as they typically have none
        non_milestone = [
            t for t in self._all_countable if t.task_type.lower() not in ("tt_mile", "tt_finmile")
        ]
        total_nm = len(non_milestone)
        with_res = sum(1 for t in non_milestone if t.task_id in self._task_ids_with_resources)
        pct = self._safe_pct(with_res, total_nm)
        return MetricResult(
            number=10,
            name="Resources",
            description="Non-milestone activities with resource assignments",
            value=pct,
            threshold=self.RESOURCES_THRESHOLD,
            direction="max",
            passed=pct >= self.RESOURCES_THRESHOLD,
            details=f"{with_res}/{total_nm} non-milestone activities have resources",
        )

    def _check_missed_tasks(self) -> MetricResult:
        """Check 11: Missed Tasks -- tasks that should be done but are not.

        A task is *missed* if it has baseline (target) finish before the
        data date but is not yet complete.

        Target: <= 5%.
        """
        if not self.data_date:
            return MetricResult(
                number=11,
                name="Missed Tasks",
                description="Tasks past baseline finish that are not complete",
                value=0.0,
                threshold=self.MISSED_TASKS_THRESHOLD,
                direction="min",
                passed=True,
                details="No data date available -- check skipped",
            )

        total = len(self._all_countable)
        missed = 0
        for t in self._all_countable:
            if t.status_code.lower() == "tk_complete":
                continue
            if t.target_end_date and t.target_end_date < self.data_date:
                missed += 1
        pct = self._safe_pct(missed, total)
        return MetricResult(
            number=11,
            name="Missed Tasks",
            description="Incomplete tasks past their baseline finish",
            value=pct,
            threshold=self.MISSED_TASKS_THRESHOLD,
            direction="min",
            passed=pct <= self.MISSED_TASKS_THRESHOLD,
            details=f"{missed}/{total} activities are missed",
        )

    def _check_critical_path_test(self) -> MetricResult:
        """Check 12: Critical Path Test.

        A simplified check: verify that there is at least one path of
        activities with zero (or near-zero) total float from the schedule.
        In a full implementation, this would involve delaying a CP activity
        and confirming the project end date changes.

        For v0.1, we verify that at least one incomplete activity has TF
        close to zero.

        Target: PASS if critical path exists.
        """
        has_cp = any(
            t.total_float_hr_cnt is not None and abs(t.total_float_hr_cnt) < 1.0
            for t in self._incomplete
        )
        return MetricResult(
            number=12,
            name="Critical Path Test",
            description="Critical path is valid and identifiable",
            value=1.0 if has_cp else 0.0,
            threshold=1.0,
            unit="",
            direction="max",
            passed=has_cp,
            details="Critical path identified" if has_cp else "No critical path found",
        )

    def _check_cpli(self) -> MetricResult:
        """Check 13: Critical Path Length Index (CPLI).

        CPLI = (critical path length + total float) / critical path length

        For a healthy schedule, CPLI >= 1.0.  We approximate using the
        project finish and data date if available.

        CPLI = remaining_cp_duration / (project_finish - data_date)

        For v0.1, we use a simplified calculation based on available float
        data.
        """
        if not self.data_date or not self.schedule.projects:
            return MetricResult(
                number=13,
                name="CPLI",
                description="Critical Path Length Index",
                value=0.0,
                threshold=1.0,
                unit="",
                direction="max",
                passed=False,
                details="Insufficient data for CPLI calculation",
            )

        # Find project end date
        proj = self.schedule.projects[0]
        project_end = proj.scd_end_date or proj.plan_end_date
        if not project_end:
            # Try to find from activity dates
            end_dates = [t.early_end_date for t in self.schedule.activities if t.early_end_date]
            project_end = max(end_dates) if end_dates else None

        if not project_end:
            return MetricResult(
                number=13,
                name="CPLI",
                description="Critical Path Length Index",
                value=0.0,
                threshold=1.0,
                unit="",
                direction="max",
                passed=False,
                details="Cannot determine project end date",
            )

        # Total remaining duration of incomplete critical activities
        remaining_days = (project_end - self.data_date).days
        if remaining_days <= 0:
            return MetricResult(
                number=13,
                name="CPLI",
                description="Critical Path Length Index",
                value=1.0,
                threshold=1.0,
                unit="",
                direction="max",
                passed=True,
                details="Project is past its end date",
            )

        # Sum of total float on critical path in days
        cp_activities = [
            t
            for t in self._incomplete
            if t.total_float_hr_cnt is not None and abs(t.total_float_hr_cnt) < 1.0
        ]
        if cp_activities:
            # CP length in working days (simplified)
            cp_duration_hrs = sum(t.remain_drtn_hr_cnt for t in cp_activities)
            cp_length_days = cp_duration_hrs / self.hours_per_day
            cpli = (cp_length_days + remaining_days) / remaining_days if remaining_days > 0 else 1.0
            # Normalise: a well-scheduled project has CPLI ~= 1.0
            cpli = min(cpli, 2.0)  # cap at 2.0 for display
        else:
            cpli = 1.0  # no CP activities, assume OK

        passed = cpli >= 0.95
        return MetricResult(
            number=13,
            name="CPLI",
            description="Critical Path Length Index",
            value=round(cpli, 3),
            threshold=1.0,
            unit="",
            direction="max",
            passed=passed,
            details=f"CPLI = {cpli:.3f}",
        )

    def _check_bei(self) -> MetricResult:
        """Check 14: Baseline Execution Index (BEI).

        BEI = (number of tasks completed on time) / (number of tasks that
        should be complete by data date per baseline).

        A BEI >= 0.95 is considered healthy.
        """
        if not self.data_date:
            return MetricResult(
                number=14,
                name="BEI",
                description="Baseline Execution Index",
                value=0.0,
                threshold=0.95,
                unit="",
                direction="max",
                passed=False,
                details="No data date available -- check skipped",
            )

        # Tasks that should be complete (baseline end <= data date)
        should_be_complete = [
            t
            for t in self._all_countable
            if t.target_end_date and t.target_end_date <= self.data_date
        ]
        total_should = len(should_be_complete)
        if total_should == 0:
            return MetricResult(
                number=14,
                name="BEI",
                description="Baseline Execution Index",
                value=1.0,
                threshold=0.95,
                unit="",
                direction="max",
                passed=True,
                details="No tasks expected to be complete by data date",
            )

        actually_complete = sum(
            1 for t in should_be_complete if t.status_code.lower() == "tk_complete"
        )
        bei = round(actually_complete / total_should, 3)
        return MetricResult(
            number=14,
            name="BEI",
            description="Baseline Execution Index",
            value=bei,
            threshold=0.95,
            unit="",
            direction="max",
            passed=bei >= 0.95,
            details=f"{actually_complete}/{total_should} tasks completed on time (BEI = {bei:.3f})",
        )
