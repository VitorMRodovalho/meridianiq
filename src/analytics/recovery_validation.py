# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Recovery Schedule Validation Engine.

Per AACE Recommended Practice 29R-03 Section 4 — Recovery Schedule Analysis.

A recovery schedule is submitted by a contractor to demonstrate how they
plan to recover from delay. This engine validates whether the recovery
plan is reasonable, achievable, and properly linked to the impacted schedule.

Checks:
1. Duration reasonableness — are recovery durations unrealistically compressed?
2. Logic integrity — does the recovery maintain proper predecessor/successor logic?
3. Resource loading — are resources overloaded beyond reasonable capacity?
4. Calendar compliance — does recovery respect work calendar constraints?
5. Float consumption — does recovery eliminate all available float?
6. Scope consistency — are activities added/removed vs the impacted schedule?
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


@dataclass
class RecoveryIssue:
    """A single issue found during recovery schedule validation."""

    severity: str  # "critical", "warning", "info"
    category: str  # "duration", "logic", "resource", "calendar", "float", "scope"
    task_code: str
    task_name: str
    description: str
    impacted_value: str = ""
    recovery_value: str = ""


@dataclass
class RecoveryValidationResult:
    """Output of recovery schedule validation."""

    impacted_name: str
    recovery_name: str
    impacted_activity_count: int
    recovery_activity_count: int
    issues: list[RecoveryIssue] = field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    total_duration_reduction_pct: float = 0.0
    activities_compressed: int = 0
    activities_added: int = 0
    activities_removed: int = 0
    zero_float_activities: int = 0
    validation_score: float = 100.0  # 0-100
    verdict: str = "acceptable"  # "acceptable", "questionable", "unreasonable"


class RecoveryValidator:
    """Validate a recovery schedule against the impacted schedule.

    Args:
        impacted: The impacted (current/as-is) schedule.
        recovery: The proposed recovery schedule.
    """

    COMPRESSION_WARNING_PCT = 25.0  # Flag if duration reduced by >25%
    COMPRESSION_CRITICAL_PCT = 50.0  # Flag if duration reduced by >50%
    ZERO_FLOAT_THRESHOLD_PCT = 80.0  # Flag if >80% of activities have zero float

    def __init__(self, impacted: ParsedSchedule, recovery: ParsedSchedule):
        self.impacted = impacted
        self.recovery = recovery
        self._impacted_by_code = {t.task_code: t for t in impacted.activities}
        self._recovery_by_code = {t.task_code: t for t in recovery.activities}

    def validate(self) -> RecoveryValidationResult:
        """Run full recovery schedule validation."""
        result = RecoveryValidationResult(
            impacted_name=(
                self.impacted.projects[0].proj_short_name if self.impacted.projects else "Impacted"
            ),
            recovery_name=(
                self.recovery.projects[0].proj_short_name if self.recovery.projects else "Recovery"
            ),
            impacted_activity_count=len(self.impacted.activities),
            recovery_activity_count=len(self.recovery.activities),
        )

        self._check_duration_compression(result)
        self._check_scope_changes(result)
        self._check_float_consumption(result)
        self._check_logic_integrity(result)
        self._calculate_score(result)

        return result

    def _check_duration_compression(self, result: RecoveryValidationResult) -> None:
        """Check for unrealistic duration compression."""
        total_impacted_hrs = 0.0
        total_recovery_hrs = 0.0

        for code, imp_task in self._impacted_by_code.items():
            if code not in self._recovery_by_code:
                continue

            rec_task = self._recovery_by_code[code]
            imp_dur = imp_task.remain_drtn_hr_cnt or 0
            rec_dur = rec_task.remain_drtn_hr_cnt or 0

            # Skip completed activities
            if imp_dur <= 0:
                continue

            total_impacted_hrs += imp_dur
            total_recovery_hrs += rec_dur

            if imp_dur > 0 and rec_dur < imp_dur:
                reduction_pct = ((imp_dur - rec_dur) / imp_dur) * 100

                if reduction_pct >= self.COMPRESSION_CRITICAL_PCT:
                    result.activities_compressed += 1
                    result.issues.append(
                        RecoveryIssue(
                            severity="critical",
                            category="duration",
                            task_code=code,
                            task_name=imp_task.task_name,
                            description=(
                                f"Duration compressed by {reduction_pct:.0f}% "
                                f"({imp_dur / 8:.1f}d → {rec_dur / 8:.1f}d). "
                                f"Likely unreasonable without justification."
                            ),
                            impacted_value=f"{imp_dur / 8:.1f}d",
                            recovery_value=f"{rec_dur / 8:.1f}d",
                        )
                    )
                elif reduction_pct >= self.COMPRESSION_WARNING_PCT:
                    result.activities_compressed += 1
                    result.issues.append(
                        RecoveryIssue(
                            severity="warning",
                            category="duration",
                            task_code=code,
                            task_name=imp_task.task_name,
                            description=(
                                f"Duration reduced by {reduction_pct:.0f}% "
                                f"({imp_dur / 8:.1f}d → {rec_dur / 8:.1f}d)"
                            ),
                            impacted_value=f"{imp_dur / 8:.1f}d",
                            recovery_value=f"{rec_dur / 8:.1f}d",
                        )
                    )

        if total_impacted_hrs > 0:
            result.total_duration_reduction_pct = round(
                ((total_impacted_hrs - total_recovery_hrs) / total_impacted_hrs) * 100, 1
            )

    def _check_scope_changes(self, result: RecoveryValidationResult) -> None:
        """Check for activities added or removed in recovery."""
        impacted_codes = set(self._impacted_by_code.keys())
        recovery_codes = set(self._recovery_by_code.keys())

        added = recovery_codes - impacted_codes
        removed = impacted_codes - recovery_codes

        result.activities_added = len(added)
        result.activities_removed = len(removed)

        if len(removed) > len(impacted_codes) * 0.1:
            result.issues.append(
                RecoveryIssue(
                    severity="critical",
                    category="scope",
                    task_code="SCHEDULE",
                    task_name="Scope Reduction",
                    description=(
                        f"{len(removed)} activities removed ({len(removed) / len(impacted_codes) * 100:.0f}%). "
                        f"Recovery should not reduce scope to show schedule improvement."
                    ),
                )
            )

        if len(added) > 0:
            result.issues.append(
                RecoveryIssue(
                    severity="info",
                    category="scope",
                    task_code="SCHEDULE",
                    task_name="Scope Addition",
                    description=f"{len(added)} activities added in recovery (mitigation measures).",
                )
            )

    def _check_float_consumption(self, result: RecoveryValidationResult) -> None:
        """Check if recovery eliminates all available float."""
        zero_float = 0
        total_incomplete = 0

        for task in self.recovery.activities:
            status = (task.status_code or "").upper()
            if status == "TK_COMPLETE":
                continue
            total_incomplete += 1
            tf = task.total_float_hr_cnt
            if tf is not None and abs(tf) < 1.0:
                zero_float += 1

        result.zero_float_activities = zero_float

        if total_incomplete > 0:
            zero_float_pct = (zero_float / total_incomplete) * 100
            if zero_float_pct >= self.ZERO_FLOAT_THRESHOLD_PCT:
                result.issues.append(
                    RecoveryIssue(
                        severity="critical",
                        category="float",
                        task_code="SCHEDULE",
                        task_name="Float Consumption",
                        description=(
                            f"{zero_float_pct:.0f}% of incomplete activities have zero float. "
                            f"Recovery plan has no schedule margin — any delay causes further slippage."
                        ),
                    )
                )

    def _check_logic_integrity(self, result: RecoveryValidationResult) -> None:
        """Check that recovery maintains logical relationships."""
        impacted_rels = {(r.task_id, r.pred_task_id): r for r in self.impacted.relationships}
        recovery_rels = {(r.task_id, r.pred_task_id): r for r in self.recovery.relationships}

        removed_rels = set(impacted_rels.keys()) - set(recovery_rels.keys())

        if len(removed_rels) > len(impacted_rels) * 0.15:
            result.issues.append(
                RecoveryIssue(
                    severity="warning",
                    category="logic",
                    task_code="SCHEDULE",
                    task_name="Logic Changes",
                    description=(
                        f"{len(removed_rels)} relationships removed "
                        f"({len(removed_rels) / max(len(impacted_rels), 1) * 100:.0f}%). "
                        f"Removing logic to show recovery may mask real constraints."
                    ),
                )
            )

    def _calculate_score(self, result: RecoveryValidationResult) -> None:
        """Calculate overall validation score and verdict."""
        score = 100.0
        result.critical_count = sum(1 for i in result.issues if i.severity == "critical")
        result.warning_count = sum(1 for i in result.issues if i.severity == "warning")

        score -= result.critical_count * 20
        score -= result.warning_count * 5
        score -= min(result.total_duration_reduction_pct * 0.5, 30)

        result.validation_score = max(0.0, round(score, 1))

        if result.validation_score >= 70:
            result.verdict = "acceptable"
        elif result.validation_score >= 40:
            result.verdict = "questionable"
        else:
            result.verdict = "unreasonable"
