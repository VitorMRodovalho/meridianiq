# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for calendar validation engine."""

from __future__ import annotations

from src.analytics.calendar_validation import (
    validate_calendars,
)
from src.parser.models import Calendar, ParsedSchedule, Task


def _make_schedule(
    calendars: list[Calendar] | None = None,
    tasks: list[Task] | None = None,
) -> ParsedSchedule:
    return ParsedSchedule(
        calendars=calendars or [],
        activities=tasks or [],
    )


def _cal(
    clndr_id: str = "CAL1",
    name: str = "Standard",
    day_hr: float = 8.0,
    week_hr: float = 40.0,
    default: str = "N",
) -> Calendar:
    return Calendar(
        clndr_id=clndr_id,
        clndr_name=name,
        day_hr_cnt=day_hr,
        week_hr_cnt=week_hr,
        default_flag=default,
    )


def _task(task_id: str = "A100", clndr_id: str = "CAL1") -> Task:
    return Task(
        task_id=task_id,
        clndr_id=clndr_id,
        task_type="TT_Task",
        status_code="TK_Active",
    )


class TestHealthySchedule:
    """A well-configured schedule should score high."""

    def test_healthy_score(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(default="Y")],
            tasks=[_task(f"A{i}") for i in range(10)],
        )
        result = validate_calendars(schedule)
        assert result.score >= 90
        assert result.grade in ("A", "B")
        assert result.has_default is True
        assert result.tasks_without_calendar == 0

    def test_calendar_details_populated(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(default="Y")],
            tasks=[_task(f"A{i}") for i in range(5)],
        )
        result = validate_calendars(schedule)
        assert len(result.calendars) == 1
        assert result.calendars[0].task_count == 5
        assert result.calendars[0].pct_of_tasks == 100.0
        assert result.calendars[0].is_default is True
        assert result.calendars[0].working_days_per_week == 5.0

    def test_dominant_calendar(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(default="Y"), _cal("CAL2", "7-Day", 8, 56)],
            tasks=[_task(f"A{i}") for i in range(8)]
            + [_task(f"B{i}", "CAL2") for i in range(2)],
        )
        result = validate_calendars(schedule)
        assert result.dominant_calendar == "Standard"
        assert result.dominant_pct == 80.0


class TestNoCalendars:
    """Missing calendar definitions should be critical."""

    def test_no_calendars_critical(self) -> None:
        schedule = _make_schedule(tasks=[_task()])
        result = validate_calendars(schedule)
        assert result.score == 0
        assert result.grade == "F"
        assert any(i.check == "no_calendars" for i in result.issues)


class TestDefaultCalendar:
    """Default calendar checks."""

    def test_no_default_penalized(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(default="N")],
            tasks=[_task()],
        )
        result = validate_calendars(schedule)
        assert result.has_default is False
        assert any(i.check == "default_calendar" for i in result.issues)
        assert result.score < 100

    def test_multiple_defaults_warning(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(default="Y"), _cal("CAL2", default="Y")],
            tasks=[_task()],
        )
        result = validate_calendars(schedule)
        assert any(i.check == "multiple_defaults" for i in result.issues)


class TestTaskCalendarAssignment:
    """Tasks should reference valid calendars."""

    def test_tasks_without_calendar(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(default="Y")],
            tasks=[_task(clndr_id=""), _task("A2", clndr_id="")],
        )
        result = validate_calendars(schedule)
        assert result.tasks_without_calendar == 2
        assert any(i.check == "no_calendar_assigned" for i in result.issues)

    def test_invalid_calendar_reference(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(default="Y")],
            tasks=[_task(clndr_id="NONEXISTENT")],
        )
        result = validate_calendars(schedule)
        assert any(i.check == "invalid_calendar_ref" for i in result.issues)
        assert result.score < 90


class TestHourConsistency:
    """Calendar hours should be physically possible."""

    def test_zero_daily_hours_critical(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(day_hr=0, default="Y")],
            tasks=[_task()],
        )
        result = validate_calendars(schedule)
        assert any(i.check == "zero_daily_hours" for i in result.issues)

    def test_excessive_daily_hours(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(day_hr=25, week_hr=125, default="Y")],
            tasks=[_task()],
        )
        result = validate_calendars(schedule)
        assert any(i.check == "excessive_daily_hours" for i in result.issues)

    def test_excessive_weekly_hours(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(day_hr=24, week_hr=200, default="Y")],
            tasks=[_task()],
        )
        result = validate_calendars(schedule)
        assert any(i.check == "excessive_weekly_hours" for i in result.issues)

    def test_daily_weekly_mismatch(self) -> None:
        # 80h/week / 10h/day = 8 days → should flag
        schedule2 = _make_schedule(
            calendars=[_cal(day_hr=10, week_hr=80, default="Y")],
            tasks=[_task()],
        )
        result2 = validate_calendars(schedule2)
        assert any(i.check == "hour_mismatch" for i in result2.issues)


class TestNonStandardCalendars:
    """Non-standard calendars should be flagged."""

    def test_reduced_work_week(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(day_hr=8, week_hr=32, default="Y")],
            tasks=[_task()],
        )
        result = validate_calendars(schedule)
        assert any(i.check == "non_standard_hours" for i in result.issues)

    def test_extended_calendar_info(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(day_hr=8, week_hr=56, default="Y")],
            tasks=[_task()],
        )
        result = validate_calendars(schedule)
        assert any(i.check == "extended_calendar" for i in result.issues)


class TestOrphanedCalendars:
    """Unused calendars should be noted."""

    def test_orphaned_calendar_flagged(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(default="Y"), _cal("CAL2", "Unused")],
            tasks=[_task()],  # only references CAL1
        )
        result = validate_calendars(schedule)
        assert any(i.check == "orphaned_calendars" for i in result.issues)
        orphan = next(c for c in result.calendars if c.calendar_id == "CAL2")
        assert orphan.task_count == 0
        assert len(orphan.issues) > 0


class TestIssueSorting:
    """Issues should be sorted critical → warning → info."""

    def test_severity_order(self) -> None:
        schedule = _make_schedule(
            calendars=[_cal(day_hr=25, week_hr=125)],  # no default + excessive
            tasks=[_task(clndr_id="")],  # no calendar
        )
        result = validate_calendars(schedule)
        severities = [i.severity for i in result.issues]
        order = {"critical": 0, "warning": 1, "info": 2}
        for i in range(len(severities) - 1):
            assert order[severities[i]] <= order[severities[i + 1]]


class TestMethodology:
    """Result includes methodology string."""

    def test_methodology_present(self) -> None:
        result = validate_calendars(_make_schedule())
        assert "DCMA" in result.methodology
        assert "AACE" in result.methodology
