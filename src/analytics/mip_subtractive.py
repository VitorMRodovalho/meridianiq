# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""AACE RP 29R-03 MIP 3.6 — Modified / Subtractive Single Simulation.

Implements the "Collapsed As-Built" method per AACE Recommended Practice
29R-03 §3.6.  Starting from the as-built schedule, the caller names the
activities (and delay amounts) they attribute to specific events.  The
engine shortens each affected activity's duration by the stated amount
and re-runs CPM, yielding a "but-for" completion date: *what the project
completion would have been had those delay events not occurred*.

The method is **subjective** in that the caller identifies the delay
events; the computation of the but-for completion is deterministic once
the events are fixed.  This matches how owner-side counsel typically
prepares a collapsed as-built: the analyst chooses which delays to
"remove" and the tool measures the impact.

References:
    AACE RP 29R-03 §3.6 (Modified / Subtractive Single Simulation).
    SCL Delay and Disruption Protocol 2nd ed. §22.4 (Collapsed As-Built
    Analysis).
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.cpm import CPMCalculator
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


_HOURS_PER_DAY = 8.0  # Matches CPMCalculator default


@dataclass
class DelayEvent:
    """Caller-supplied delay attribution.

    Attributes:
        task_id: The activity to shorten.  Matched against ``Task.task_id``.
        days: Number of working days to remove from the activity's
            target / remaining duration.  Must be ``>= 0``.
        description: Optional free-text label carried through to the
            result for audit trail.
    """

    task_id: str
    days: float
    description: str = ""


@dataclass
class AppliedDelayEvent:
    """Record of a delay event's application to a specific activity."""

    task_id: str
    task_code: str
    task_name: str
    days_requested: float
    days_applied: float
    original_duration_days: float
    collapsed_duration_days: float
    description: str = ""
    note: str = ""


@dataclass
class Mip36Result:
    """Output of MIP 3.6 — Collapsed As-Built single-simulation analysis."""

    as_built_completion_days: float = 0.0
    but_for_completion_days: float = 0.0
    attributable_delay_days: float = 0.0
    delay_events_applied: list[AppliedDelayEvent] = field(default_factory=list)
    unmatched_events: list[DelayEvent] = field(default_factory=list)
    as_built_critical_path: list[str] = field(default_factory=list)
    but_for_critical_path: list[str] = field(default_factory=list)
    methodology: str = "AACE RP 29R-03 MIP 3.6 — Modified / Subtractive Single Simulation"


def _critical_codes(cpm_result: Any) -> list[str]:
    codes: list[str] = []
    for tid in cpm_result.critical_path:
        ar = cpm_result.activity_results.get(tid)
        if ar:
            codes.append(ar.task_code or tid)
    return codes


def analyze_mip_3_6(
    schedule: ParsedSchedule,
    delay_events: list[DelayEvent],
    hours_per_day: float = _HOURS_PER_DAY,
) -> Mip36Result:
    """Run MIP 3.6 — Collapsed As-Built single-simulation analysis.

    Args:
        schedule: The as-built (or latest available) schedule.
        delay_events: Caller-attributed delays.  Each event names an
            activity and the days of delay to "remove" from it.
        hours_per_day: Hours per working day (must match the CPM
            calculator setting used on the original schedule).

    Returns:
        A populated ``Mip36Result``.  ``unmatched_events`` lists any
        ``DelayEvent`` whose ``task_id`` did not exist in the schedule —
        these are returned rather than raised so the caller can present a
        best-effort result plus a warning.

    Raises:
        ValueError: If any event has a negative ``days`` value.

    Reference: AACE RP 29R-03 §3.6.
    """
    for event in delay_events:
        if event.days < 0:
            raise ValueError(
                f"DelayEvent days must be non-negative; got {event.days} "
                f"for task_id={event.task_id!r}"
            )

    result = Mip36Result()

    # ---- Original (as-built) CPM ----
    as_built_cpm = CPMCalculator(schedule, hours_per_day=hours_per_day).calculate()
    result.as_built_completion_days = float(as_built_cpm.project_duration)
    result.as_built_critical_path = _critical_codes(as_built_cpm)

    # ---- Build the collapsed schedule ----
    collapsed = copy.deepcopy(schedule)
    task_by_id: dict[str, Any] = {t.task_id: t for t in collapsed.activities}

    for event in delay_events:
        task = task_by_id.get(event.task_id)
        if task is None:
            result.unmatched_events.append(event)
            continue

        original_days = float(task.target_drtn_hr_cnt or 0.0) / hours_per_day
        remove_hours = event.days * hours_per_day

        # Days_applied is clamped so we never produce a negative duration
        days_applied = min(event.days, original_days)
        new_target = max(0.0, float(task.target_drtn_hr_cnt or 0.0) - remove_hours)
        new_remain = max(0.0, float(task.remain_drtn_hr_cnt or 0.0) - remove_hours)

        task.target_drtn_hr_cnt = new_target
        task.remain_drtn_hr_cnt = new_remain

        collapsed_days = new_target / hours_per_day
        note = ""
        if days_applied < event.days:
            note = (
                f"requested {event.days}d but activity was only "
                f"{original_days:.1f}d — clamped to {days_applied:.1f}d"
            )

        result.delay_events_applied.append(
            AppliedDelayEvent(
                task_id=event.task_id,
                task_code=task.task_code or "",
                task_name=task.task_name or "",
                days_requested=event.days,
                days_applied=days_applied,
                original_duration_days=round(original_days, 2),
                collapsed_duration_days=round(collapsed_days, 2),
                description=event.description,
                note=note,
            )
        )

    # ---- But-for CPM on the collapsed schedule ----
    but_for_cpm = CPMCalculator(collapsed, hours_per_day=hours_per_day).calculate()
    result.but_for_completion_days = float(but_for_cpm.project_duration)
    result.but_for_critical_path = _critical_codes(but_for_cpm)

    result.attributable_delay_days = round(
        result.as_built_completion_days - result.but_for_completion_days, 2
    )

    return result
