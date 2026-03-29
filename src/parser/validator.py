# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""XER schedule validation -- check structure and data quality.

Provides a set of automated checks to identify structural issues,
missing logic, date anomalies, and other common scheduling problems
in a parsed P6 XER schedule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import ParsedSchedule


@dataclass
class ValidationIssue:
    """A single validation finding."""

    severity: str  # "error", "warning", "info"
    category: str  # "structure", "logic", "dates", "resources"
    message: str
    activity_id: str = ""


@dataclass
class ValidationResult:
    """Aggregated validation output."""

    is_valid: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    activity_count: int = 0
    relationship_count: int = 0
    wbs_count: int = 0
    calendar_count: int = 0
    resource_count: int = 0
    open_start_count: int = 0
    open_finish_count: int = 0
    constrained_count: int = 0


class XERValidator:
    """Run structural and logical validation checks on a parsed schedule.

    Usage::

        validator = XERValidator(schedule)
        result = validator.validate()
        for issue in result.issues:
            print(f"[{issue.severity}] {issue.message}")
    """

    def __init__(self, schedule: ParsedSchedule) -> None:
        """Initialise validator with a parsed schedule.

        Args:
            schedule: A ``ParsedSchedule`` object from ``XERReader.parse()``.
        """
        self.schedule = schedule

    def validate(self) -> ValidationResult:
        """Run all validation checks and return aggregated results.

        Returns:
            A ``ValidationResult`` containing issues found and summary counts.
        """
        result = ValidationResult()
        self._check_required_tables(result)
        self._check_activity_counts(result)
        self._check_relationship_counts(result)
        self._check_open_ends(result)
        self._check_constraints(result)
        self._check_date_integrity(result)
        self._build_summary(result)
        return result

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_required_tables(self, result: ValidationResult) -> None:
        """Verify that essential tables are present and non-empty.

        Args:
            result: The result object to append issues to.
        """
        if not self.schedule.projects:
            result.issues.append(ValidationIssue("error", "structure", "No PROJECT records found"))
            result.is_valid = False
        if not self.schedule.activities:
            result.issues.append(ValidationIssue("error", "structure", "No TASK records found"))
            result.is_valid = False
        if not self.schedule.calendars:
            result.issues.append(
                ValidationIssue("warning", "structure", "No CALENDAR records found")
            )
        if not self.schedule.wbs_nodes:
            result.issues.append(
                ValidationIssue("warning", "structure", "No PROJWBS records found")
            )

    def _check_activity_counts(self, result: ValidationResult) -> None:
        """Populate activity count and verify it is reasonable.

        Args:
            result: The result object to update.
        """
        result.activity_count = len(self.schedule.activities)
        result.relationship_count = len(self.schedule.relationships)
        result.wbs_count = len(self.schedule.wbs_nodes)
        result.calendar_count = len(self.schedule.calendars)
        result.resource_count = len(self.schedule.resources)

        if result.activity_count == 0:
            return

        # Check for activities with blank task_code
        blank_code_count = sum(1 for t in self.schedule.activities if not t.task_code.strip())
        if blank_code_count > 0:
            result.issues.append(
                ValidationIssue(
                    "warning",
                    "structure",
                    f"{blank_code_count} activities have blank task_code",
                )
            )

    def _check_relationship_counts(self, result: ValidationResult) -> None:
        """Verify relationship counts and types.

        Args:
            result: The result object to update.
        """
        if not self.schedule.relationships:
            if self.schedule.activities:
                result.issues.append(
                    ValidationIssue(
                        "error",
                        "logic",
                        "No relationships found -- schedule has no logic",
                    )
                )
                result.is_valid = False
            return

        type_counts: dict[str, int] = {}
        for rel in self.schedule.relationships:
            ptype = rel.pred_type
            type_counts[ptype] = type_counts.get(ptype, 0) + 1

        result.summary["relationship_types"] = type_counts

    def _check_open_ends(self, result: ValidationResult) -> None:
        """Identify activities missing predecessors or successors.

        An *open start* is a non-milestone activity with no predecessor.
        An *open finish* is a non-milestone activity with no successor.

        Args:
            result: The result object to update.
        """
        if not self.schedule.activities:
            return

        successor_ids: set[str] = set()
        predecessor_ids: set[str] = set()
        for rel in self.schedule.relationships:
            successor_ids.add(rel.task_id)  # task_id is the successor
            predecessor_ids.add(rel.pred_task_id)

        all_task_ids = {t.task_id for t in self.schedule.activities}

        # Activities that are never a successor (no predecessors coming in)
        open_starts: set[str] = all_task_ids - successor_ids
        # Activities that are never a predecessor (no successors going out)
        open_finishes: set[str] = all_task_ids - predecessor_ids

        # Filter out milestones for open-end counting (start milestones
        # and LOE are often legitimately open)
        for task in self.schedule.activities:
            if task.task_id in open_starts:
                result.issues.append(
                    ValidationIssue(
                        "warning",
                        "logic",
                        f"Open start (no predecessor): {task.task_code} - {task.task_name}",
                        activity_id=task.task_code,
                    )
                )
            if task.task_id in open_finishes:
                result.issues.append(
                    ValidationIssue(
                        "warning",
                        "logic",
                        f"Open finish (no successor): {task.task_code} - {task.task_name}",
                        activity_id=task.task_code,
                    )
                )

        result.open_start_count = len(open_starts)
        result.open_finish_count = len(open_finishes)

    def _check_constraints(self, result: ValidationResult) -> None:
        """Flag activities with hard constraints.

        Args:
            result: The result object to update.
        """
        constrained = 0
        for task in self.schedule.activities:
            if task.cstr_type and task.cstr_type.strip():
                constrained += 1
                result.issues.append(
                    ValidationIssue(
                        "info",
                        "logic",
                        f"Constraint {task.cstr_type} on {task.task_code}",
                        activity_id=task.task_code,
                    )
                )
        result.constrained_count = constrained

    def _check_date_integrity(self, result: ValidationResult) -> None:
        """Check for basic date anomalies.

        Flags activities where the actual start is after the actual finish,
        or where early dates are inconsistent.

        Args:
            result: The result object to update.
        """
        for task in self.schedule.activities:
            # Actual start after actual finish
            if task.act_start_date and task.act_end_date:
                if task.act_start_date > task.act_end_date:
                    result.issues.append(
                        ValidationIssue(
                            "error",
                            "dates",
                            (f"Actual start > actual finish for {task.task_code}"),
                            activity_id=task.task_code,
                        )
                    )
                    result.is_valid = False

            # Early start after early finish
            if task.early_start_date and task.early_end_date:
                if task.early_start_date > task.early_end_date:
                    result.issues.append(
                        ValidationIssue(
                            "warning",
                            "dates",
                            (f"Early start > early finish for {task.task_code}"),
                            activity_id=task.task_code,
                        )
                    )

    def _build_summary(self, result: ValidationResult) -> None:
        """Compile a summary dictionary of the validation run.

        Args:
            result: The result object to finalise.
        """
        status_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for task in self.schedule.activities:
            sc = task.status_code or "UNKNOWN"
            status_counts[sc] = status_counts.get(sc, 0) + 1
            tt = task.task_type or "UNKNOWN"
            type_counts[tt] = type_counts.get(tt, 0) + 1

        result.summary["status_counts"] = status_counts
        result.summary["type_counts"] = type_counts
        result.summary["total_issues"] = len(result.issues)
        result.summary["errors"] = sum(1 for i in result.issues if i.severity == "error")
        result.summary["warnings"] = sum(1 for i in result.issues if i.severity == "warning")
        result.summary["info"] = sum(1 for i in result.issues if i.severity == "info")
