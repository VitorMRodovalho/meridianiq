# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Structured parser for Oracle P6 ``clndr_data`` blob.

P6 packs the weekly schedule + exception dates + per-exception hours into a
single string field on the ``CALENDAR`` table. The format uses parenthesised
tagged lists::

    (0||CalendarData(
        (0||DaysOfWeek(
            (0||1()(0||0(s|07:00|f|11:00)(s|12:00|f|16:00)))
            (0||2()(0||0(s|07:00|f|11:00)(s|12:00|f|16:00)))
            ...))
        (0||Exceptions(
            (0||(d|45050)())                          # full holiday
            (0||(d|45100)(0||0(s|08:00|f|12:00)))     # half-day work
            ...)))

Numeric encodings:
    - Day numbers (``DaysOfWeek``) are 1=Sunday, 2=Monday, ..., 7=Saturday
      per the P6 SDK.
    - Exception dates (``d|NNNNN``) are days since the P6 epoch
      ``1899-12-31``.
    - Each ``(s|HH:MM|f|HH:MM)`` block is one working window for that day.

This module returns a structured dict instead of poking the blob directly
from feature code. The existing ``parse_calendar_holidays()`` in
``schedule_view.py`` uses a regex and treats every exception date as a full
holiday — kept for backwards compat. The new parser distinguishes
``is_working`` exceptions and reports their hours.

Reference: Oracle Primavera P6 Professional Reference Manual, Calendar
Data Format appendix.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

P6_EPOCH = date(1899, 12, 31)


@dataclass
class CalendarException:
    """One exception day from a P6 calendar.

    Attributes:
        exception_date: ISO date string (YYYY-MM-DD).
        is_working: ``False`` for full-day non-working (holiday); ``True``
            when the day has at least one ``(s|f|)`` working window. P6
            allows both directions: a normally-non-working day flagged as
            working, and a normally-working day flagged as a holiday.
        hours: Sum of working-window hours on this day. ``0.0`` for holidays.
    """

    exception_date: str
    is_working: bool
    hours: float = 0.0


@dataclass
class CalendarSchedule:
    """Parsed structure of a single calendar's clndr_data blob.

    Attributes:
        weekly_hours: Map ``{1..7 → daily working hours}`` where 1=Sunday
            and 7=Saturday per the P6 SDK convention.
        exceptions: All exception days found, sorted by date.
        working_exception_count: Convenience counter for QA reports.
        holiday_exception_count: Convenience counter.
    """

    weekly_hours: dict[int, float] = field(default_factory=dict)
    exceptions: list[CalendarException] = field(default_factory=list)
    working_exception_count: int = 0
    holiday_exception_count: int = 0


_TIME_WINDOW = re.compile(r"\(s\|(\d{1,2}):(\d{2})\|f\|(\d{1,2}):(\d{2})\)")
_DAY_BLOCK = re.compile(
    r"\(0\|\|([1-7])\(\)((?:\(s\|\d{1,2}:\d{2}\|f\|\d{1,2}:\d{2}\))*|\(0\|\|0[^()]*(?:\([^()]*\))*\))",
)
_EXCEPTION_BLOCK = re.compile(
    r"\(0\|\|\(d\|(\d+)\)((?:\([^()]*\))*)\)",
)


def _sum_window_hours(text: str) -> float:
    """Sum hours from all ``(s|HH:MM|f|HH:MM)`` windows in ``text``."""
    total = 0.0
    for sh, sm, fh, fm in _TIME_WINDOW.findall(text):
        start = int(sh) * 60 + int(sm)
        finish = int(fh) * 60 + int(fm)
        if finish > start:
            total += (finish - start) / 60.0
    return total


def parse_calendar_data(blob: str) -> CalendarSchedule:
    """Parse a P6 ``clndr_data`` string into a :class:`CalendarSchedule`.

    Tolerant of malformed blobs: returns whatever it could extract and
    silently skips entries it can't decode. Empty / missing input returns
    an empty schedule.
    """
    schedule = CalendarSchedule()
    if not blob:
        return schedule

    for match in _DAY_BLOCK.finditer(blob):
        day_num = int(match.group(1))
        windows_text = match.group(2)
        schedule.weekly_hours[day_num] = _sum_window_hours(windows_text)

    for match in _EXCEPTION_BLOCK.finditer(blob):
        day_num = int(match.group(1))
        body = match.group(2)
        try:
            iso = (P6_EPOCH + timedelta(days=day_num)).isoformat()
        except (ValueError, OverflowError):
            continue
        hours = _sum_window_hours(body)
        is_working = hours > 0
        schedule.exceptions.append(
            CalendarException(
                exception_date=iso,
                is_working=is_working,
                hours=hours,
            )
        )

    schedule.exceptions.sort(key=lambda e: e.exception_date)
    schedule.working_exception_count = sum(1 for e in schedule.exceptions if e.is_working)
    schedule.holiday_exception_count = sum(1 for e in schedule.exceptions if not e.is_working)

    return schedule
