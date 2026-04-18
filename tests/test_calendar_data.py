# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the structured P6 ``clndr_data`` parser."""

from __future__ import annotations

from src.parser.calendar_data import (
    P6_EPOCH,
    CalendarException,
    parse_calendar_data,
)


def test_empty_blob_returns_empty_schedule() -> None:
    sched = parse_calendar_data("")
    assert sched.weekly_hours == {}
    assert sched.exceptions == []


def test_weekly_hours_extracted() -> None:
    """A standard 8h/day Mon-Fri week gets parsed into per-day hours.

    P6 day numbers: 1=Sunday ... 7=Saturday. So Mon=2, Fri=6.
    """
    blob = (
        "(0||CalendarData("
        "(0||DaysOfWeek("
        "(0||1())"
        "(0||2()(s|07:00|f|11:00)(s|12:00|f|16:00))"
        "(0||3()(s|07:00|f|11:00)(s|12:00|f|16:00))"
        "(0||4()(s|07:00|f|11:00)(s|12:00|f|16:00))"
        "(0||5()(s|07:00|f|11:00)(s|12:00|f|16:00))"
        "(0||6()(s|07:00|f|11:00)(s|12:00|f|16:00))"
        "(0||7())"
        ")))"
    )
    sched = parse_calendar_data(blob)
    assert sched.weekly_hours[1] == 0.0  # Sunday: no windows
    assert sched.weekly_hours[2] == 8.0  # Monday: 4h + 4h
    assert sched.weekly_hours[6] == 8.0  # Friday
    assert sched.weekly_hours[7] == 0.0  # Saturday


def test_full_holiday_exception() -> None:
    """``(d|N)`` with no time window after it = full non-working day."""
    blob = "(0||Exceptions((0||(d|45050)())))"
    sched = parse_calendar_data(blob)
    assert len(sched.exceptions) == 1
    exc = sched.exceptions[0]
    assert exc.is_working is False
    assert exc.hours == 0.0
    assert exc.exception_date == "2023-05-05"  # day 45050 since 1899-12-31


def test_partial_working_exception() -> None:
    """``(d|N)(...working windows...)`` = working day with custom hours."""
    blob = "(0||Exceptions((0||(d|45100)(s|08:00|f|12:00))))"
    sched = parse_calendar_data(blob)
    assert len(sched.exceptions) == 1
    exc = sched.exceptions[0]
    assert exc.is_working is True
    assert exc.hours == 4.0


def test_mixed_exceptions_sorted_and_counted() -> None:
    blob = (
        "(0||Exceptions("
        "(0||(d|45200)(s|09:00|f|11:00))"  # 2h working
        "(0||(d|45100)())"  # holiday
        "(0||(d|45150)())"  # holiday
        "))"
    )
    sched = parse_calendar_data(blob)
    assert [e.exception_date for e in sched.exceptions] == sorted(
        e.exception_date for e in sched.exceptions
    )
    assert sched.working_exception_count == 1
    assert sched.holiday_exception_count == 2


def test_malformed_blob_is_tolerated() -> None:
    """Garbage input should not raise — return empty schedule."""
    sched = parse_calendar_data("not a calendar blob (((( malformed")
    assert sched.weekly_hours == {}
    assert sched.exceptions == []


def test_invalid_date_silently_skipped() -> None:
    """``(d|99999999)`` would overflow datetime; skip without raising."""
    blob = "(0||Exceptions((0||(d|99999999)())))"
    sched = parse_calendar_data(blob)
    assert sched.exceptions == []


def test_p6_epoch_constant() -> None:
    """Day 0 should be the P6 epoch itself (1899-12-31)."""
    assert P6_EPOCH.isoformat() == "1899-12-31"


def test_calendar_exception_dataclass_defaults() -> None:
    exc = CalendarException(exception_date="2026-01-01", is_working=False)
    assert exc.hours == 0.0
