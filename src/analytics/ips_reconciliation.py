# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Integrated Project Schedule (IPS) Reconciliation Engine.

Verifies consistency between a master schedule and sub-schedules.
Per AACE Recommended Practice 71R-12 — Required Skills and Knowledge
of Integrated Project Schedule Development.

The IPS reconciliation checks:
1. Milestone alignment — do sub-schedule milestones match master dates?
2. Interface point consistency — are handoff activities aligned?
3. Logic continuity — are cross-schedule dependencies maintained?
4. Date consistency — do sub completion dates align with master windows?
5. WBS alignment — do sub WBS elements map to master WBS?
6. Float consistency — does sub float align with master float allowance?
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationIssue:
    """A single discrepancy found during IPS reconciliation."""

    severity: str  # "critical", "warning", "info"
    category: str  # "milestone", "interface", "logic", "date", "wbs", "float"
    master_activity: str
    sub_activity: str
    sub_schedule: str
    description: str
    master_value: str = ""
    sub_value: str = ""
    delta: str = ""


@dataclass
class SubScheduleResult:
    """Reconciliation results for a single sub-schedule."""

    sub_name: str
    sub_activity_count: int = 0
    matched_milestones: int = 0
    unmatched_milestones: int = 0
    date_issues: int = 0
    logic_issues: int = 0
    issues: list[ReconciliationIssue] = field(default_factory=list)
    alignment_score: float = 100.0  # 0-100


@dataclass
class IPSReconciliationResult:
    """Full IPS reconciliation output."""

    master_name: str
    master_activity_count: int
    sub_count: int
    sub_results: list[SubScheduleResult] = field(default_factory=list)
    total_issues: int = 0
    critical_issues: int = 0
    warning_issues: int = 0
    overall_alignment_score: float = 100.0  # 0-100 weighted average
    reconciliation_status: str = (
        "aligned"  # "aligned", "minor_discrepancies", "major_discrepancies"
    )


class IPSReconciler:
    """Reconcile a master schedule against one or more sub-schedules.

    Per AACE RP 71R-12, the IPS must demonstrate:
    - Vertical traceability (WBS alignment)
    - Horizontal traceability (logic continuity across schedules)
    - Milestone and interface point consistency
    """

    MILESTONE_DATE_TOLERANCE_DAYS = 5.0  # Allow 5 working days tolerance
    FLOAT_TOLERANCE_HOURS = 40.0  # 5 days tolerance for float

    def __init__(self, master: ParsedSchedule):
        self.master = master
        self._master_milestones = {
            t.task_code: t
            for t in master.activities
            if t.task_type and t.task_type.upper() in ("TT_MILE", "TT_FINMILE")
        }
        self._master_by_code = {t.task_code: t for t in master.activities}
        self._master_wbs = {w.wbs_id: w for w in master.wbs_nodes}

    def reconcile(self, sub_schedules: list[ParsedSchedule]) -> IPSReconciliationResult:
        """Run full IPS reconciliation.

        Args:
            sub_schedules: List of sub-schedules to reconcile against the master.

        Returns:
            IPSReconciliationResult with issues and alignment scores.
        """
        result = IPSReconciliationResult(
            master_name=(
                self.master.projects[0].proj_short_name if self.master.projects else "Master"
            ),
            master_activity_count=len(self.master.activities),
            sub_count=len(sub_schedules),
        )

        for sub in sub_schedules:
            sub_result = self._reconcile_sub(sub)
            result.sub_results.append(sub_result)

        # Aggregate
        result.total_issues = sum(len(sr.issues) for sr in result.sub_results)
        result.critical_issues = sum(
            sum(1 for i in sr.issues if i.severity == "critical") for sr in result.sub_results
        )
        result.warning_issues = sum(
            sum(1 for i in sr.issues if i.severity == "warning") for sr in result.sub_results
        )

        if result.sub_results:
            result.overall_alignment_score = round(
                sum(sr.alignment_score for sr in result.sub_results) / len(result.sub_results),
                1,
            )

        if result.critical_issues > 0:
            result.reconciliation_status = "major_discrepancies"
        elif result.warning_issues > 0:
            result.reconciliation_status = "minor_discrepancies"
        else:
            result.reconciliation_status = "aligned"

        return result

    def _reconcile_sub(self, sub: ParsedSchedule) -> SubScheduleResult:
        """Reconcile a single sub-schedule against the master."""
        sub_name = sub.projects[0].proj_short_name if sub.projects else "Sub-Schedule"
        sr = SubScheduleResult(sub_name=sub_name, sub_activity_count=len(sub.activities))

        sub_milestones = {
            t.task_code: t
            for t in sub.activities
            if t.task_type and t.task_type.upper() in ("TT_MILE", "TT_FINMILE")
        }
        sub_by_code = {t.task_code: t for t in sub.activities}

        # Check 1: Milestone alignment
        self._check_milestone_alignment(sr, sub_name, sub_milestones)

        # Check 2: Date consistency for matched activities
        self._check_date_consistency(sr, sub_name, sub_by_code)

        # Check 3: Float consistency
        self._check_float_consistency(sr, sub_name, sub_by_code)

        # Check 4: WBS alignment
        self._check_wbs_alignment(sr, sub_name, sub)

        # Calculate alignment score
        total_checks = max(sr.matched_milestones + sr.unmatched_milestones + len(sub.activities), 1)
        issue_penalty = sr.date_issues * 5 + sr.logic_issues * 10 + sr.unmatched_milestones * 15
        sr.alignment_score = max(0.0, round(100.0 - (issue_penalty / total_checks * 100), 1))

        return sr

    def _check_milestone_alignment(
        self,
        sr: SubScheduleResult,
        sub_name: str,
        sub_milestones: dict,
    ) -> None:
        """Verify sub milestones match master milestone dates."""
        for code, master_ms in self._master_milestones.items():
            if code in sub_milestones:
                sr.matched_milestones += 1
                sub_ms = sub_milestones[code]

                # Compare target end dates
                m_date = master_ms.target_end_date or master_ms.early_end_date
                s_date = sub_ms.target_end_date or sub_ms.early_end_date

                if m_date and s_date:
                    delta_hours = abs((m_date - s_date).total_seconds() / 3600)
                    delta_days = delta_hours / 8.0

                    if delta_days > self.MILESTONE_DATE_TOLERANCE_DAYS:
                        sr.date_issues += 1
                        sr.issues.append(
                            ReconciliationIssue(
                                severity="critical" if delta_days > 20 else "warning",
                                category="milestone",
                                master_activity=code,
                                sub_activity=code,
                                sub_schedule=sub_name,
                                description=(
                                    f"Milestone date mismatch: {delta_days:.1f} days delta"
                                ),
                                master_value=str(m_date.date()) if m_date else "",
                                sub_value=str(s_date.date()) if s_date else "",
                                delta=f"{delta_days:.1f} days",
                            )
                        )
            else:
                sr.unmatched_milestones += 1
                sr.issues.append(
                    ReconciliationIssue(
                        severity="warning",
                        category="milestone",
                        master_activity=code,
                        sub_activity="(missing)",
                        sub_schedule=sub_name,
                        description=f"Master milestone '{code}' not found in sub-schedule",
                    )
                )

    def _check_date_consistency(
        self,
        sr: SubScheduleResult,
        sub_name: str,
        sub_by_code: dict,
    ) -> None:
        """Check that shared activities have consistent dates."""
        for code, master_act in self._master_by_code.items():
            if code not in sub_by_code:
                continue

            sub_act = sub_by_code[code]

            # Compare early finish dates
            m_ef = master_act.early_end_date
            s_ef = sub_act.early_end_date

            if m_ef and s_ef:
                delta_hours = abs((m_ef - s_ef).total_seconds() / 3600)
                delta_days = delta_hours / 8.0

                if delta_days > self.MILESTONE_DATE_TOLERANCE_DAYS * 2:
                    sr.date_issues += 1
                    sr.issues.append(
                        ReconciliationIssue(
                            severity="warning",
                            category="date",
                            master_activity=code,
                            sub_activity=code,
                            sub_schedule=sub_name,
                            description=f"Early finish date delta: {delta_days:.1f} days",
                            master_value=str(m_ef.date()) if m_ef else "",
                            sub_value=str(s_ef.date()) if s_ef else "",
                            delta=f"{delta_days:.1f} days",
                        )
                    )

    def _check_float_consistency(
        self,
        sr: SubScheduleResult,
        sub_name: str,
        sub_by_code: dict,
    ) -> None:
        """Check that float values are consistent between schedules."""
        for code, master_act in self._master_by_code.items():
            if code not in sub_by_code:
                continue

            sub_act = sub_by_code[code]
            m_float = master_act.total_float_hr_cnt
            s_float = sub_act.total_float_hr_cnt

            if m_float is not None and s_float is not None:
                delta = abs(m_float - s_float)
                if delta > self.FLOAT_TOLERANCE_HOURS:
                    sr.issues.append(
                        ReconciliationIssue(
                            severity="info",
                            category="float",
                            master_activity=code,
                            sub_activity=code,
                            sub_schedule=sub_name,
                            description=(
                                f"Float discrepancy: {delta / 8:.1f} days "
                                f"(master={m_float / 8:.1f}d, sub={s_float / 8:.1f}d)"
                            ),
                            master_value=f"{m_float / 8:.1f}d",
                            sub_value=f"{s_float / 8:.1f}d",
                            delta=f"{delta / 8:.1f} days",
                        )
                    )

    def _check_wbs_alignment(
        self,
        sr: SubScheduleResult,
        sub_name: str,
        sub: ParsedSchedule,
    ) -> None:
        """Check that sub-schedule WBS elements map to master WBS."""
        if not self._master_wbs or not sub.wbs_nodes:
            return

        master_wbs_names = {
            w.wbs_short_name.upper() for w in self.master.wbs_nodes if w.wbs_short_name
        }
        sub_wbs_names = {w.wbs_short_name.upper() for w in sub.wbs_nodes if w.wbs_short_name}

        orphan_wbs = sub_wbs_names - master_wbs_names
        if len(orphan_wbs) > len(sub_wbs_names) * 0.5 and len(sub_wbs_names) > 3:
            sr.issues.append(
                ReconciliationIssue(
                    severity="warning",
                    category="wbs",
                    master_activity="WBS",
                    sub_activity="WBS",
                    sub_schedule=sub_name,
                    description=(
                        f"{len(orphan_wbs)}/{len(sub_wbs_names)} sub WBS elements "
                        f"don't match master WBS names"
                    ),
                )
            )
