# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Calendar Validation — work calendar quality and integrity checks.

Validates P6 work calendar definitions for structural integrity,
consistency, and scheduling best practices. A scheduler needs to
trust the calendars before trusting float and critical path.

Checks:
    1. Default calendar exists
    2. All tasks reference valid calendar IDs
    3. No orphaned calendars (defined but unused)
    4. Daily/weekly hour consistency (day_hr_cnt × working_days ≈ week_hr_cnt)
    5. Reasonable work hours (not >24h/day or >168h/week)
    6. Non-standard calendars flagged (compressed, extended, etc.)
    7. Calendar diversity (too many calendars can indicate manipulation)
    8. Tasks without calendar assignment

Standards:
    - DCMA 14-Point Assessment — Check #13 (calendar adequacy)
    - GAO Schedule Assessment Guide — Reasonable activity parameters
    - AACE RP 49R-06 — Schedule Health Assessment
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


@dataclass
class CalendarIssue:
    """A single calendar validation finding.

    Attributes:
        calendar_id: The calendar's ID (empty for task-level issues).
        calendar_name: Calendar display name.
        check: The validation rule that flagged this.
        severity: critical, warning, or info.
        description: Human-readable explanation.
        affected_tasks: Number of tasks impacted by this issue.
    """

    calendar_id: str = ""
    calendar_name: str = ""
    check: str = ""
    severity: str = "info"
    description: str = ""
    affected_tasks: int = 0


@dataclass
class CalendarDetail:
    """Summary of a single calendar with usage stats.

    Attributes:
        calendar_id: Calendar system ID.
        name: Calendar display name.
        day_hr_cnt: Hours per working day.
        week_hr_cnt: Hours per working week.
        calendar_type: Calendar type code.
        is_default: Whether this is the default calendar.
        task_count: Number of tasks assigned to this calendar.
        pct_of_tasks: Percentage of total tasks using this calendar.
        working_days_per_week: Inferred from week_hr_cnt / day_hr_cnt.
        issues: Validation issues for this specific calendar.
    """

    calendar_id: str = ""
    name: str = ""
    day_hr_cnt: float = 8.0
    week_hr_cnt: float = 40.0
    calendar_type: str = ""
    is_default: bool = False
    task_count: int = 0
    pct_of_tasks: float = 0.0
    working_days_per_week: float = 5.0
    issues: list[str] = field(default_factory=list)


@dataclass
class CalendarValidationResult:
    """Result of calendar validation analysis.

    Attributes:
        calendars: Detailed list of all calendars with usage stats.
        issues: All validation findings sorted by severity.
        score: Overall calendar health score (0-100).
        grade: Letter grade A-F.
        total_calendars: Count of defined calendars.
        total_tasks: Total activities in schedule.
        tasks_with_calendar: Tasks that reference a valid calendar.
        tasks_without_calendar: Tasks missing calendar assignment.
        has_default: Whether a default calendar exists.
        dominant_calendar: The most-used calendar name.
        dominant_pct: Percentage of tasks on the dominant calendar.
        methodology: Description of validation approach.
    """

    calendars: list[CalendarDetail] = field(default_factory=list)
    issues: list[CalendarIssue] = field(default_factory=list)
    score: float = 100.0
    grade: str = "A"
    total_calendars: int = 0
    total_tasks: int = 0
    tasks_with_calendar: int = 0
    tasks_without_calendar: int = 0
    has_default: bool = False
    dominant_calendar: str = ""
    dominant_pct: float = 0.0
    methodology: str = (
        "Calendar validation per DCMA 14-Point Check #13 (calendar adequacy), "
        "GAO Schedule Assessment Guide, and AACE RP 49R-06. "
        "Checks structural integrity, hour consistency, task coverage, "
        "and non-standard calendar patterns."
    )


_GRADE_THRESHOLDS = [(90, "A"), (80, "B"), (70, "C"), (60, "D")]


def _to_grade(score: float) -> str:
    for threshold, grade in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def validate_calendars(schedule: ParsedSchedule) -> CalendarValidationResult:
    """Run all calendar validation checks on a parsed schedule.

    Args:
        schedule: A fully parsed XER schedule.

    Returns:
        CalendarValidationResult with calendars, issues, and score.
    """
    result = CalendarValidationResult()
    calendars = schedule.calendars
    all_tasks = schedule.activities

    result.total_calendars = len(calendars)
    result.total_tasks = len(all_tasks)

    # Build calendar lookup
    cal_map = {c.clndr_id: c for c in calendars}

    # Count tasks per calendar
    task_per_cal: dict[str, int] = {}
    tasks_no_cal = 0
    tasks_invalid_cal = 0
    for t in all_tasks:
        if not t.clndr_id:
            tasks_no_cal += 1
        elif t.clndr_id in cal_map:
            task_per_cal[t.clndr_id] = task_per_cal.get(t.clndr_id, 0) + 1
        else:
            tasks_invalid_cal += 1
            task_per_cal.setdefault(t.clndr_id, 0)

    result.tasks_without_calendar = tasks_no_cal + tasks_invalid_cal
    result.tasks_with_calendar = len(all_tasks) - result.tasks_without_calendar

    # Build calendar details
    for cal in calendars:
        count = task_per_cal.get(cal.clndr_id, 0)
        pct = (count / len(all_tasks) * 100) if all_tasks else 0.0
        working_days = cal.week_hr_cnt / cal.day_hr_cnt if cal.day_hr_cnt > 0 else 0.0
        detail = CalendarDetail(
            calendar_id=cal.clndr_id,
            name=cal.clndr_name or cal.clndr_id,
            day_hr_cnt=cal.day_hr_cnt,
            week_hr_cnt=cal.week_hr_cnt,
            calendar_type=cal.clndr_type,
            is_default=cal.default_flag.upper() == "Y",
            task_count=count,
            pct_of_tasks=round(pct, 1),
            working_days_per_week=round(working_days, 1),
        )
        result.calendars.append(detail)

    # Sort by task count descending
    result.calendars.sort(key=lambda c: c.task_count, reverse=True)
    if result.calendars:
        result.dominant_calendar = result.calendars[0].name
        result.dominant_pct = result.calendars[0].pct_of_tasks

    # --- Validation checks ---
    score = 100.0
    issues = result.issues

    # Check 1: Default calendar exists
    defaults = [c for c in calendars if c.default_flag.upper() == "Y"]
    result.has_default = len(defaults) > 0
    if not result.has_default:
        issues.append(
            CalendarIssue(
                check="default_calendar",
                severity="critical",
                description="No default calendar defined. P6 requires a default calendar for unassigned tasks.",
                affected_tasks=len(all_tasks),
            )
        )
        score -= 15
    elif len(defaults) > 1:
        issues.append(
            CalendarIssue(
                check="multiple_defaults",
                severity="warning",
                description=f"{len(defaults)} calendars marked as default. Only one should be the default.",
                affected_tasks=0,
            )
        )
        score -= 5

    # Check 2: Tasks without calendar
    if tasks_no_cal > 0:
        pct = tasks_no_cal / len(all_tasks) * 100 if all_tasks else 0
        sev = "critical" if pct > 10 else "warning" if pct > 2 else "info"
        issues.append(
            CalendarIssue(
                check="no_calendar_assigned",
                severity=sev,
                description=(
                    f"{tasks_no_cal} tasks ({pct:.1f}%) have no calendar assigned. "
                    "Float and duration calculations may be unreliable."
                ),
                affected_tasks=tasks_no_cal,
            )
        )
        if sev == "critical":
            score -= 20
        elif sev == "warning":
            score -= 10
        else:
            score -= 3

    # Check 3: Tasks referencing invalid calendars
    if tasks_invalid_cal > 0:
        issues.append(
            CalendarIssue(
                check="invalid_calendar_ref",
                severity="critical",
                description=(
                    f"{tasks_invalid_cal} tasks reference calendar IDs not defined "
                    "in CALENDAR table. Data integrity issue."
                ),
                affected_tasks=tasks_invalid_cal,
            )
        )
        score -= 15

    # Check 4: Orphaned calendars (defined but unused)
    orphaned = [c for c in result.calendars if c.task_count == 0]
    if orphaned:
        names = ", ".join(c.name for c in orphaned[:5])
        issues.append(
            CalendarIssue(
                check="orphaned_calendars",
                severity="info",
                description=(
                    f"{len(orphaned)} calendar(s) defined but not used by any task: {names}."
                    + (" (and more)" if len(orphaned) > 5 else "")
                ),
                affected_tasks=0,
            )
        )
        for c in orphaned:
            c.issues.append("Unused — no tasks assigned")

    # Check 5: Per-calendar hour consistency
    for detail in result.calendars:
        cal = cal_map.get(detail.calendar_id)
        if not cal:
            continue

        # 5a: Unreasonable daily hours
        if cal.day_hr_cnt <= 0:
            detail.issues.append("Zero or negative daily hours")
            issues.append(
                CalendarIssue(
                    calendar_id=cal.clndr_id,
                    calendar_name=detail.name,
                    check="zero_daily_hours",
                    severity="critical",
                    description=f"Calendar '{detail.name}' has {cal.day_hr_cnt} hours/day.",
                    affected_tasks=detail.task_count,
                )
            )
            score -= 10
        elif cal.day_hr_cnt > 24:
            detail.issues.append(f"Impossible: {cal.day_hr_cnt}h/day > 24")
            issues.append(
                CalendarIssue(
                    calendar_id=cal.clndr_id,
                    calendar_name=detail.name,
                    check="excessive_daily_hours",
                    severity="critical",
                    description=f"Calendar '{detail.name}' has {cal.day_hr_cnt} hours/day (exceeds 24).",
                    affected_tasks=detail.task_count,
                )
            )
            score -= 10

        # 5b: Unreasonable weekly hours
        if cal.week_hr_cnt > 168:
            detail.issues.append(f"Impossible: {cal.week_hr_cnt}h/week > 168")
            issues.append(
                CalendarIssue(
                    calendar_id=cal.clndr_id,
                    calendar_name=detail.name,
                    check="excessive_weekly_hours",
                    severity="critical",
                    description=f"Calendar '{detail.name}' has {cal.week_hr_cnt} hours/week (exceeds 168).",
                    affected_tasks=detail.task_count,
                )
            )
            score -= 10

        # 5c: Daily/weekly mismatch
        if cal.day_hr_cnt > 0:
            implied_days = cal.week_hr_cnt / cal.day_hr_cnt
            if implied_days < 1 or implied_days > 7:
                detail.issues.append(
                    f"Inconsistent: {cal.week_hr_cnt}h/wk ÷ {cal.day_hr_cnt}h/day = {implied_days:.1f} days"
                )
                issues.append(
                    CalendarIssue(
                        calendar_id=cal.clndr_id,
                        calendar_name=detail.name,
                        check="hour_mismatch",
                        severity="warning",
                        description=(
                            f"Calendar '{detail.name}': {cal.week_hr_cnt}h/week ÷ "
                            f"{cal.day_hr_cnt}h/day = {implied_days:.1f} implied working days "
                            "(should be 1-7)."
                        ),
                        affected_tasks=detail.task_count,
                    )
                )
                score -= 5

    # Check 6: Non-standard calendars (DCMA #13)
    non_standard = [c for c in result.calendars if c.week_hr_cnt < 40 and c.task_count > 0]
    if non_standard:
        total_affected = sum(c.task_count for c in non_standard)
        names = ", ".join(f"{c.name} ({c.week_hr_cnt}h)" for c in non_standard[:3])
        issues.append(
            CalendarIssue(
                check="non_standard_hours",
                severity="warning",
                description=(
                    f"{len(non_standard)} calendar(s) with <40h/week: {names}. "
                    f"Affects {total_affected} tasks. "
                    "Reduced work weeks inflate float and extend duration calculations."
                ),
                affected_tasks=total_affected,
            )
        )
        for c in non_standard:
            c.issues.append(f"Non-standard: {c.week_hr_cnt}h/week < 40h")
        score -= 5

    # Check 7: Extended calendars (7-day)
    extended = [c for c in result.calendars if c.working_days_per_week > 5.5 and c.task_count > 0]
    if extended:
        total_affected = sum(c.task_count for c in extended)
        names = ", ".join(f"{c.name} ({c.working_days_per_week}d)" for c in extended[:3])
        issues.append(
            CalendarIssue(
                check="extended_calendar",
                severity="info",
                description=(
                    f"{len(extended)} calendar(s) with >5.5 working days/week: {names}. "
                    f"Affects {total_affected} tasks. "
                    "Extended calendars compress durations and may not reflect reality."
                ),
                affected_tasks=total_affected,
            )
        )
        for c in extended:
            c.issues.append(f"Extended: {c.working_days_per_week} days/week")

    # Check 8: Too many calendars (potential manipulation)
    if len(calendars) > 10 and all_tasks:
        ratio = len(calendars) / len(all_tasks) * 100
        if ratio > 5:
            issues.append(
                CalendarIssue(
                    check="excessive_calendars",
                    severity="warning",
                    description=(
                        f"{len(calendars)} calendars for {len(all_tasks)} tasks "
                        f"(ratio {ratio:.1f}%). Excessive calendars can obscure float analysis."
                    ),
                    affected_tasks=0,
                )
            )
            score -= 5

    # Check 9: No calendars at all
    if not calendars:
        issues.append(
            CalendarIssue(
                check="no_calendars",
                severity="critical",
                description="No CALENDAR records in schedule. All duration and float calculations are unreliable.",
                affected_tasks=len(all_tasks),
            )
        )
        score = 0

    # Clamp and grade
    result.score = max(0.0, min(100.0, score))
    result.grade = _to_grade(result.score)

    # Sort issues: critical first, then warning, then info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    result.issues.sort(key=lambda i: severity_order.get(i.severity, 3))

    return result
