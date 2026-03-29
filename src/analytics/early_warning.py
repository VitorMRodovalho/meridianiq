# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Early Warning System — 12-rule alert engine per GAO Schedule Assessment Guide §9.

Runs automatically when two schedule snapshots are available (baseline +
update).  Each rule checks a specific schedule health indicator and produces
``Alert`` objects ranked by score.

Standards:
    - GAO Schedule Assessment Guide (2020) §9 — Schedule Surveillance
    - AACE RP 49R-06 — Identifying Critical Activities
    - AACE RP 29R-03 — Forensic Schedule Analysis
    - DCMA 14-Point Assessment — checks #3-#7, #10, #12, #13
    - PMI Practice Standard for Scheduling §6.7 — Resource Management
    - PMI PMBOK 7th Ed §4.6 — Measurement Performance Domain
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.comparison import ComparisonResult, ScheduleComparison
from src.analytics.cpm import CPMCalculator, CPMResult
from src.parser.models import ParsedSchedule, Task

logger = logging.getLogger(__name__)

_HOURS_PER_DAY = 8.0

# Severity weights for alert scoring
_SEVERITY_WEIGHT = {
    "info": 1.0,
    "warning": 3.0,
    "critical": 5.0,
}


@dataclass
class AlertRule:
    """Definition of a single alert rule.

    Attributes:
        rule_id: Machine-readable identifier (e.g., 'float_erosion').
        name: Human-readable name.
        severity: Default severity ('info', 'warning', 'critical').
        standard: Reference standard (e.g., 'AACE RP 49R-06').
        description: Short description of what the rule checks.
    """

    rule_id: str
    name: str
    severity: str
    standard: str
    description: str = ""


@dataclass
class Alert:
    """A single alert produced by a rule.

    Attributes:
        rule_id: Which rule produced this alert.
        severity: Alert severity level.
        title: Short title for display.
        description: Detailed description with context.
        affected_activities: List of task_codes affected.
        projected_impact_days: Estimated delay impact in days.
        confidence: Confidence level (0–1).
        alert_score: Composite score = severity_weight * confidence * impact.
    """

    rule_id: str
    severity: str
    title: str
    description: str
    affected_activities: list[str] = field(default_factory=list)
    projected_impact_days: float = 0.0
    confidence: float = 0.5
    alert_score: float = 0.0

    def compute_score(self) -> float:
        """Compute alert_score from severity, confidence, and impact."""
        weight = _SEVERITY_WEIGHT.get(self.severity, 1.0)
        impact = max(self.projected_impact_days, 1.0)
        self.alert_score = round(weight * self.confidence * impact, 2)
        return self.alert_score


@dataclass
class EarlyWarningResult:
    """Complete early warning analysis output.

    Attributes:
        alerts: All alerts, sorted by score descending.
        total_alerts: Total number of alerts.
        critical_count: Number of critical-severity alerts.
        warning_count: Number of warning-severity alerts.
        info_count: Number of info-severity alerts.
        aggregate_score: Sum of all alert scores.
        rules_checked: Number of rules evaluated.
        summary: Aggregate statistics dict.
    """

    alerts: list[Alert] = field(default_factory=list)
    total_alerts: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    aggregate_score: float = 0.0
    rules_checked: int = 12
    summary: dict[str, Any] = field(default_factory=dict)


# ── Rule definitions ──────────────────────────────────────

RULES: list[AlertRule] = [
    AlertRule(
        rule_id="float_erosion",
        name="Float Erosion",
        severity="warning",
        standard="AACE RP 49R-06",
        description="Activity lost >5d float with <50% progress",
    ),
    AlertRule(
        rule_id="cp_shift",
        name="Critical Path Shift",
        severity="critical",
        standard="GAO §7.3",
        description=">20% of critical path activities changed",
    ),
    AlertRule(
        rule_id="logic_deletion",
        name="Logic Deletion",
        severity="critical",
        standard="DCMA #7",
        description="Predecessor relationships removed between updates",
    ),
    AlertRule(
        rule_id="duration_growth",
        name="Duration Growth",
        severity="warning",
        standard="DCMA #5",
        description="Activity duration increased >20%",
    ),
    AlertRule(
        rule_id="retroactive_date",
        name="Retroactive Date Change",
        severity="critical",
        standard="AACE RP 29R-03",
        description="Actual dates modified in past periods",
    ),
    AlertRule(
        rule_id="constraint_addition",
        name="Constraint Addition",
        severity="warning",
        standard="DCMA #10",
        description="New date constraints added (potential manipulation)",
    ),
    AlertRule(
        rule_id="negative_float_growth",
        name="Negative Float Growth",
        severity="critical",
        standard="DCMA #4",
        description="Negative float increased >10 days",
    ),
    AlertRule(
        rule_id="resource_overallocation",
        name="Resource Overallocation",
        severity="warning",
        standard="PMI SP §6.7",
        description="Resource allocated >100%",
    ),
    AlertRule(
        rule_id="open_ended",
        name="Open-Ended Activities",
        severity="critical",
        standard="DCMA #6, #7",
        description="Activities missing predecessor or successor",
    ),
    AlertRule(
        rule_id="progress_override",
        name="Progress Override",
        severity="warning",
        standard="DCMA #12",
        description="Physical % complete doesn't match duration progress",
    ),
    AlertRule(
        rule_id="calendar_anomaly",
        name="Calendar Anomaly",
        severity="info",
        standard="DCMA #13",
        description="Non-standard calendar reducing available working days",
    ),
    AlertRule(
        rule_id="baseline_deviation",
        name="Baseline Deviation",
        severity="warning",
        standard="PMI PMBOK",
        description="Finish variance >10% of remaining duration",
    ),
]


class EarlyWarningEngine:
    """Rules engine that detects schedule anomalies across two snapshots.

    Implements 12 alert rules per GAO Schedule Assessment Guide §9 and
    related standards.  Each rule checks a specific schedule health
    indicator and produces ``Alert`` objects.

    Usage::

        engine = EarlyWarningEngine(baseline, update)
        result = engine.analyze()
        for alert in result.alerts:
            print(f"[{alert.severity}] {alert.title} (score={alert.alert_score})")

    Args:
        baseline: The earlier (baseline) parsed schedule.
        update: The later (update) parsed schedule.
        hours_per_day: Hours per working day for conversions.
    """

    def __init__(
        self,
        baseline: ParsedSchedule,
        update: ParsedSchedule,
        hours_per_day: float = _HOURS_PER_DAY,
    ) -> None:
        self.baseline = baseline
        self.update = update
        self.hours_per_day = hours_per_day

        # Pre-compute matching (same strategy as comparison engine)
        self._base_by_code: dict[str, Task] = {
            t.task_code: t for t in baseline.activities if t.task_code
        }
        self._upd_by_code: dict[str, Task] = {
            t.task_code: t for t in update.activities if t.task_code
        }
        self._matched_codes: set[str] = set(self._base_by_code.keys()) & set(
            self._upd_by_code.keys()
        )

        # Pre-compute comparison
        self._comparison: ComparisonResult | None = None
        self._base_cpm: CPMResult | None = None
        self._upd_cpm: CPMResult | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self) -> EarlyWarningResult:
        """Run all 12 rules and return prioritized alerts.

        Returns:
            An ``EarlyWarningResult`` with alerts sorted by score.
        """
        # Pre-compute comparison and CPM
        try:
            self._comparison = ScheduleComparison(self.baseline, self.update).compare()
        except Exception:
            logger.warning("Comparison failed during early warning analysis")
            self._comparison = ComparisonResult()

        try:
            self._base_cpm = CPMCalculator(
                self.baseline, hours_per_day=self.hours_per_day
            ).calculate()
            self._upd_cpm = CPMCalculator(self.update, hours_per_day=self.hours_per_day).calculate()
        except Exception:
            logger.warning("CPM failed during early warning analysis")

        # Run all rules
        alerts: list[Alert] = []
        alerts.extend(self._rule_float_erosion())
        alerts.extend(self._rule_cp_shift())
        alerts.extend(self._rule_logic_deletion())
        alerts.extend(self._rule_duration_growth())
        alerts.extend(self._rule_retroactive_date())
        alerts.extend(self._rule_constraint_addition())
        alerts.extend(self._rule_negative_float_growth())
        alerts.extend(self._rule_resource_overallocation())
        alerts.extend(self._rule_open_ended())
        alerts.extend(self._rule_progress_override())
        alerts.extend(self._rule_calendar_anomaly())
        alerts.extend(self._rule_baseline_deviation())

        # Compute scores and sort
        for alert in alerts:
            alert.compute_score()
        alerts.sort(key=lambda a: a.alert_score, reverse=True)

        # Build result
        result = EarlyWarningResult(
            alerts=alerts,
            total_alerts=len(alerts),
            critical_count=sum(1 for a in alerts if a.severity == "critical"),
            warning_count=sum(1 for a in alerts if a.severity == "warning"),
            info_count=sum(1 for a in alerts if a.severity == "info"),
            aggregate_score=round(sum(a.alert_score for a in alerts), 2),
        )
        result.summary = {
            "total_alerts": result.total_alerts,
            "critical": result.critical_count,
            "warning": result.warning_count,
            "info": result.info_count,
            "aggregate_score": result.aggregate_score,
            "rules_checked": result.rules_checked,
        }

        return result

    # ------------------------------------------------------------------
    # Rule 1: Float Erosion
    # ------------------------------------------------------------------

    def _rule_float_erosion(self) -> list[Alert]:
        """Rule 1: Float Erosion — activity lost >5d float, <50% progress.

        Per AACE RP 49R-06.
        """
        alerts: list[Alert] = []
        affected: list[str] = []

        for code in self._matched_codes:
            base_t = self._base_by_code[code]
            upd_t = self._upd_by_code[code]

            if base_t.task_type.lower() in ("tt_loe", "tt_wbs"):
                continue

            old_f = base_t.total_float_hr_cnt
            new_f = upd_t.total_float_hr_cnt
            if old_f is None or new_f is None:
                continue

            lost_days = (old_f - new_f) / self.hours_per_day
            if lost_days > 5.0 and upd_t.phys_complete_pct < 50.0:
                affected.append(code)

        if affected:
            alerts.append(
                Alert(
                    rule_id="float_erosion",
                    severity="warning",
                    title=f"Float erosion detected on {len(affected)} activities",
                    description=(
                        f"{len(affected)} activities lost >5 days of float without "
                        f"proportional progress (<50% complete). Per AACE RP 49R-06, "
                        f"float erosion without progress indicates schedule deterioration."
                    ),
                    affected_activities=affected[:50],  # cap for payload size
                    projected_impact_days=max(5.0, len(affected) * 0.5),
                    confidence=0.7,
                )
            )

        return alerts

    # ------------------------------------------------------------------
    # Rule 2: Critical Path Shift
    # ------------------------------------------------------------------

    def _rule_cp_shift(self) -> list[Alert]:
        """Rule 2: Critical Path Shift — >20% of CP activities changed.

        Per GAO Schedule Assessment Guide §7.3.
        """
        if not self._base_cpm or not self._upd_cpm:
            return []
        if self._base_cpm.has_cycles or self._upd_cpm.has_cycles:
            return []

        base_cp = set(self._base_cpm.critical_path)
        upd_cp = set(self._upd_cpm.critical_path)

        if not base_cp:
            return []

        changed = (base_cp - upd_cp) | (upd_cp - base_cp)
        union = base_cp | upd_cp
        change_pct = (len(changed) / len(union)) * 100 if union else 0

        if change_pct > 20.0:
            # Map task_ids to task_codes for reporting
            id_to_code = {t.task_id: t.task_code for t in self.update.activities if t.task_code}
            id_to_code.update(
                {t.task_id: t.task_code for t in self.baseline.activities if t.task_code}
            )
            affected = [id_to_code.get(tid, tid) for tid in sorted(changed)]

            return [
                Alert(
                    rule_id="cp_shift",
                    severity="critical",
                    title=f"Critical path shifted — {change_pct:.0f}% changed",
                    description=(
                        f"{len(changed)} activities changed on the critical path "
                        f"({change_pct:.1f}% of CP union). Per GAO §7.3, shifts >20% "
                        f"indicate fundamental schedule instability."
                    ),
                    affected_activities=affected[:50],
                    projected_impact_days=change_pct * 0.5,
                    confidence=0.8,
                )
            ]

        return []

    # ------------------------------------------------------------------
    # Rule 3: Logic Deletion
    # ------------------------------------------------------------------

    def _rule_logic_deletion(self) -> list[Alert]:
        """Rule 3: Logic Deletion — predecessors removed between updates.

        Per DCMA check #7 (missing successors / missing predecessors).
        """
        if not self._comparison:
            return []

        deleted_rels = self._comparison.relationships_deleted
        if not deleted_rels:
            return []

        affected = list({r.task_id for r in deleted_rels})

        return [
            Alert(
                rule_id="logic_deletion",
                severity="critical",
                title=f"{len(deleted_rels)} relationships removed",
                description=(
                    f"{len(deleted_rels)} predecessor relationships were deleted "
                    f"affecting {len(affected)} activities. Per DCMA #7, logic deletion "
                    f"can mask schedule issues and compromise the critical path calculation."
                ),
                affected_activities=affected[:50],
                projected_impact_days=len(deleted_rels) * 1.0,
                confidence=0.8,
            )
        ]

    # ------------------------------------------------------------------
    # Rule 4: Duration Growth
    # ------------------------------------------------------------------

    def _rule_duration_growth(self) -> list[Alert]:
        """Rule 4: Duration Growth — activity duration increased >20%.

        Per DCMA check #5 (high duration).
        """
        affected: list[str] = []
        max_growth_days = 0.0

        for code in self._matched_codes:
            base_t = self._base_by_code[code]
            upd_t = self._upd_by_code[code]

            if base_t.task_type.lower() in ("tt_loe", "tt_wbs"):
                continue
            if base_t.target_drtn_hr_cnt <= 0:
                continue

            growth_pct = (
                (upd_t.target_drtn_hr_cnt - base_t.target_drtn_hr_cnt)
                / base_t.target_drtn_hr_cnt
                * 100
            )
            if growth_pct > 20.0:
                affected.append(code)
                growth_days = (
                    upd_t.target_drtn_hr_cnt - base_t.target_drtn_hr_cnt
                ) / self.hours_per_day
                max_growth_days = max(max_growth_days, growth_days)

        if affected:
            return [
                Alert(
                    rule_id="duration_growth",
                    severity="warning",
                    title=f"{len(affected)} activities with >20% duration growth",
                    description=(
                        f"{len(affected)} activities increased their duration by >20%. "
                        f"Maximum growth: {max_growth_days:.1f} days. Per DCMA #5, "
                        f"unexplained duration growth often precedes schedule delays."
                    ),
                    affected_activities=affected[:50],
                    projected_impact_days=max_growth_days,
                    confidence=0.6,
                )
            ]

        return []

    # ------------------------------------------------------------------
    # Rule 5: Retroactive Date Change
    # ------------------------------------------------------------------

    def _rule_retroactive_date(self) -> list[Alert]:
        """Rule 5: Retroactive Date Change — actual dates modified in past periods.

        Per AACE RP 29R-03 (forensic schedule analysis).
        """
        if not self._comparison:
            return []

        retro_flags = [
            f for f in self._comparison.manipulation_flags if f.indicator == "retroactive_date"
        ]

        if not retro_flags:
            return []

        affected = list({f.task_id for f in retro_flags})

        return [
            Alert(
                rule_id="retroactive_date",
                severity="critical",
                title=f"Retroactive date changes on {len(affected)} activities",
                description=(
                    f"{len(retro_flags)} retroactive actual-date modifications detected "
                    f"across {len(affected)} activities. Per AACE RP 29R-03, modifying "
                    f"actual dates after the fact compromises forensic analysis integrity."
                ),
                affected_activities=affected[:50],
                projected_impact_days=len(affected) * 2.0,
                confidence=0.9,
            )
        ]

    # ------------------------------------------------------------------
    # Rule 6: Constraint Addition
    # ------------------------------------------------------------------

    def _rule_constraint_addition(self) -> list[Alert]:
        """Rule 6: Constraint Addition — new constraints added.

        Per DCMA check #10 (constraints).
        """
        if not self._comparison:
            return []

        added = [c for c in self._comparison.constraint_changes if c.change_type == "added"]

        if not added:
            return []

        affected = list({c.task_id for c in added})

        return [
            Alert(
                rule_id="constraint_addition",
                severity="warning",
                title=f"{len(added)} new constraints added",
                description=(
                    f"{len(added)} date constraints were added to {len(affected)} "
                    f"activities. Per DCMA #10, adding constraints can artificially "
                    f"control dates and mask float deterioration."
                ),
                affected_activities=affected[:50],
                projected_impact_days=len(added) * 1.0,
                confidence=0.6,
            )
        ]

    # ------------------------------------------------------------------
    # Rule 7: Negative Float Growth
    # ------------------------------------------------------------------

    def _rule_negative_float_growth(self) -> list[Alert]:
        """Rule 7: Negative Float Growth — negative float increased >10 days.

        Per DCMA check #4.
        """
        affected: list[str] = []
        max_neg_growth = 0.0

        for code in self._matched_codes:
            base_t = self._base_by_code[code]
            upd_t = self._upd_by_code[code]

            if base_t.task_type.lower() in ("tt_loe", "tt_wbs"):
                continue

            old_f = base_t.total_float_hr_cnt
            new_f = upd_t.total_float_hr_cnt
            if old_f is None or new_f is None:
                continue

            # Only care about negative float getting worse
            if new_f < 0:
                neg_growth_days = (old_f - new_f) / self.hours_per_day
                if neg_growth_days > 10.0:
                    affected.append(code)
                    max_neg_growth = max(max_neg_growth, neg_growth_days)

        if affected:
            return [
                Alert(
                    rule_id="negative_float_growth",
                    severity="critical",
                    title=f"{len(affected)} activities with increasing negative float",
                    description=(
                        f"{len(affected)} activities have negative float that increased "
                        f"by >10 days. Maximum growth: {max_neg_growth:.1f} days. "
                        f"Per DCMA #4, growing negative float indicates the project "
                        f"cannot meet its completion date."
                    ),
                    affected_activities=affected[:50],
                    projected_impact_days=max_neg_growth,
                    confidence=0.85,
                )
            ]

        return []

    # ------------------------------------------------------------------
    # Rule 8: Resource Overallocation
    # ------------------------------------------------------------------

    def _rule_resource_overallocation(self) -> list[Alert]:
        """Rule 8: Resource Overallocation — resource >100% allocated.

        Per PMI Practice Standard for Scheduling §6.7.

        Checks if any resource's total remaining quantity across all assigned
        activities exceeds its target quantity (simplified check).
        """
        # Aggregate remaining qty by resource
        rsrc_totals: dict[str, float] = {}
        rsrc_targets: dict[str, float] = {}
        rsrc_tasks: dict[str, list[str]] = {}

        id_to_code = {t.task_id: t.task_code for t in self.update.activities if t.task_code}

        for tr in self.update.task_resources:
            rid = tr.rsrc_id
            rsrc_totals[rid] = rsrc_totals.get(rid, 0) + tr.remain_qty
            rsrc_targets[rid] = rsrc_targets.get(rid, 0) + tr.target_qty
            task_code = id_to_code.get(tr.task_id, tr.task_id)
            rsrc_tasks.setdefault(rid, []).append(task_code)

        affected: list[str] = []
        for rid, total in rsrc_totals.items():
            target = rsrc_targets.get(rid, 0)
            if target > 0 and total > target:
                affected.extend(rsrc_tasks.get(rid, []))

        affected = list(set(affected))

        if affected:
            return [
                Alert(
                    rule_id="resource_overallocation",
                    severity="warning",
                    title=f"Resource overallocation affecting {len(affected)} activities",
                    description=(
                        f"{len(affected)} activities are assigned to overallocated "
                        f"resources. Per PMI SP §6.7, resource conflicts can cause "
                        f"schedule delays that float analysis alone cannot detect."
                    ),
                    affected_activities=affected[:50],
                    projected_impact_days=len(affected) * 0.5,
                    confidence=0.5,
                )
            ]

        return []

    # ------------------------------------------------------------------
    # Rule 9: Open-Ended Activities
    # ------------------------------------------------------------------

    def _rule_open_ended(self) -> list[Alert]:
        """Rule 9: Open-Ended Activities — missing predecessor or successor.

        Per DCMA checks #6 (missing successors) and #7 (missing predecessors).
        """
        # Build predecessor/successor sets for the update schedule
        has_pred: set[str] = set()
        has_succ: set[str] = set()
        for rel in self.update.relationships:
            has_pred.add(rel.task_id)
            has_succ.add(rel.pred_task_id)

        affected: list[str] = []
        for t in self.update.activities:
            if t.task_type.lower() in ("tt_loe", "tt_wbs"):
                continue
            if t.status_code.lower() == "tk_complete":
                continue

            missing_pred = t.task_id not in has_pred
            missing_succ = t.task_id not in has_succ

            if missing_pred or missing_succ:
                affected.append(t.task_code or t.task_id)

        if affected:
            return [
                Alert(
                    rule_id="open_ended",
                    severity="critical",
                    title=f"{len(affected)} open-ended activities",
                    description=(
                        f"{len(affected)} incomplete activities are missing a predecessor "
                        f"or successor. Per DCMA #6/#7, open-ended activities compromise "
                        f"the integrity of the critical path calculation."
                    ),
                    affected_activities=affected[:50],
                    projected_impact_days=len(affected) * 1.0,
                    confidence=0.9,
                )
            ]

        return []

    # ------------------------------------------------------------------
    # Rule 10: Progress Override
    # ------------------------------------------------------------------

    def _rule_progress_override(self) -> list[Alert]:
        """Rule 10: Progress Override — physical % vs duration mismatch.

        Per DCMA check #12.  Detects when physical % complete significantly
        deviates from duration-based progress.
        """
        affected: list[str] = []

        for t in self.update.activities:
            if t.task_type.lower() in ("tt_loe", "tt_wbs"):
                continue
            if t.status_code.lower() in ("tk_complete", "tk_notstart"):
                continue
            if t.target_drtn_hr_cnt <= 0:
                continue

            # Duration-based progress
            elapsed = t.target_drtn_hr_cnt - t.remain_drtn_hr_cnt
            duration_pct = (elapsed / t.target_drtn_hr_cnt) * 100

            # Physical percent complete
            phys_pct = t.phys_complete_pct

            # Flag if mismatch exceeds 25 percentage points
            if abs(phys_pct - duration_pct) > 25.0:
                affected.append(t.task_code or t.task_id)

        if affected:
            return [
                Alert(
                    rule_id="progress_override",
                    severity="warning",
                    title=f"Progress mismatch on {len(affected)} activities",
                    description=(
                        f"{len(affected)} in-progress activities have >25% mismatch "
                        f"between physical % complete and duration-based progress. "
                        f"Per DCMA #12, this may indicate progress overrides or "
                        f"inconsistent status reporting."
                    ),
                    affected_activities=affected[:50],
                    projected_impact_days=len(affected) * 0.5,
                    confidence=0.5,
                )
            ]

        return []

    # ------------------------------------------------------------------
    # Rule 11: Calendar Anomaly
    # ------------------------------------------------------------------

    def _rule_calendar_anomaly(self) -> list[Alert]:
        """Rule 11: Calendar Anomaly — non-standard calendars.

        Per DCMA check #13.  Flags calendars with fewer than 5 working
        days per week (40 hrs/wk) which may reduce available working time.
        """
        anomalous_calendars: list[str] = []

        for cal in self.update.calendars:
            if cal.week_hr_cnt < 40.0 and cal.week_hr_cnt > 0:
                anomalous_calendars.append(f"{cal.clndr_name} ({cal.week_hr_cnt}h/wk)")

        if anomalous_calendars:
            return [
                Alert(
                    rule_id="calendar_anomaly",
                    severity="info",
                    title=f"{len(anomalous_calendars)} non-standard calendars",
                    description=(
                        f"Calendars with reduced hours: "
                        f"{', '.join(anomalous_calendars[:5])}. "
                        f"Per DCMA #13, non-standard calendars may artificially "
                        f"extend durations and reduce schedule flexibility."
                    ),
                    affected_activities=[],
                    projected_impact_days=1.0,
                    confidence=0.3,
                )
            ]

        return []

    # ------------------------------------------------------------------
    # Rule 12: Baseline Deviation
    # ------------------------------------------------------------------

    def _rule_baseline_deviation(self) -> list[Alert]:
        """Rule 12: Baseline Deviation — finish variance >10% of remaining duration.

        Per PMI PMBOK 7th Ed §4.6 (Measurement Performance Domain).
        Compares the update's early finish against baseline target finish.
        """
        affected: list[str] = []
        max_variance_days = 0.0

        for code in self._matched_codes:
            base_t = self._base_by_code[code]
            upd_t = self._upd_by_code[code]

            if base_t.task_type.lower() in ("tt_loe", "tt_wbs"):
                continue
            if upd_t.status_code.lower() == "tk_complete":
                continue

            # Need target end and early end
            target_end = base_t.target_end_date or base_t.early_end_date
            current_end = upd_t.early_end_date

            if not target_end or not current_end:
                continue

            variance_days = (current_end - target_end).days
            remaining_days = upd_t.remain_drtn_hr_cnt / self.hours_per_day

            if remaining_days <= 0:
                continue

            # Variance exceeds 10% of remaining duration
            if abs(variance_days) > remaining_days * 0.1 and abs(variance_days) > 1:
                affected.append(code)
                max_variance_days = max(max_variance_days, abs(variance_days))

        if affected:
            return [
                Alert(
                    rule_id="baseline_deviation",
                    severity="warning",
                    title=f"{len(affected)} activities deviating from baseline",
                    description=(
                        f"{len(affected)} incomplete activities have finish dates "
                        f"deviating >10% of remaining duration from their baseline. "
                        f"Maximum deviation: {max_variance_days:.0f} days. Per PMI PMBOK, "
                        f"significant baseline deviations require corrective action."
                    ),
                    affected_activities=affected[:50],
                    projected_impact_days=max_variance_days,
                    confidence=0.6,
                )
            ]

        return []
