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


# ---------------------------------------------------------------------------
# MIP 3.7 — Modified / Subtractive Multiple Simulation (Windowed Collapsed)
# ---------------------------------------------------------------------------


@dataclass
class WindowDelayEvents:
    """Delay events attributed to a single analysis window.

    ``window_number`` is 1-based.  Window N spans between
    ``schedules[N-1]`` (start) and ``schedules[N]`` (end).  Delay events
    are applied to the end schedule, per the MIP 3.6 pattern.
    """

    window_number: int
    events: list[DelayEvent] = field(default_factory=list)


@dataclass
class Mip37WindowResult:
    """Per-window output of MIP 3.7."""

    window_number: int
    window_id: str
    baseline_project_id: str = ""
    update_project_id: str = ""
    as_built_completion_days: float = 0.0
    but_for_completion_days: float = 0.0
    attributable_delay_days: float = 0.0
    delay_events_applied: list[AppliedDelayEvent] = field(default_factory=list)
    unmatched_events: list[DelayEvent] = field(default_factory=list)


@dataclass
class Mip37Result:
    """Output of MIP 3.7 — Windowed Collapsed As-Built analysis."""

    project_ids: list[str] = field(default_factory=list)
    schedule_count: int = 0
    window_count: int = 0
    total_attributable_delay_days: float = 0.0
    windows: list[Mip37WindowResult] = field(default_factory=list)
    methodology: str = "AACE RP 29R-03 MIP 3.7 — Modified / Subtractive Multiple Simulation"


def analyze_mip_3_7(
    schedules: list[ParsedSchedule],
    window_delay_events: list[WindowDelayEvents] | None = None,
    project_ids: list[str] | None = None,
    hours_per_day: float = _HOURS_PER_DAY,
) -> Mip37Result:
    """Run MIP 3.7 — Windowed Collapsed As-Built analysis.

    Applies the MIP 3.6 pattern to each analysis window: one collapsed
    simulation per schedule pair.  The window spans schedule[N-1] →
    schedule[N]; delay events attributed to window N are removed from
    schedule[N] and the resulting but-for completion measured.

    Args:
        schedules: Parsed schedules in chronological order, minimum 2.
        window_delay_events: Optional delay-event bundles keyed by window
            number (1-based).  Windows without an entry collapse with
            zero events (as-built == but-for).
        project_ids: Optional IDs parallel to ``schedules``.
        hours_per_day: Hours per working day (matches CPM default).

    Returns:
        A populated ``Mip37Result`` — per-window breakdown plus total.

    Raises:
        ValueError: If fewer than 2 schedules or a window_number is
            outside the valid range.

    Reference: AACE RP 29R-03 §3.7.
    """
    if len(schedules) < 2:
        raise ValueError("MIP 3.7 requires at least 2 schedule updates")

    ids = list(project_ids or [""] * len(schedules))
    if len(ids) < len(schedules):
        ids.extend([""] * (len(schedules) - len(ids)))

    window_count = len(schedules) - 1
    bundles = {w.window_number: w for w in (window_delay_events or [])}

    for bundle in bundles.values():
        if bundle.window_number < 1 or bundle.window_number > window_count:
            raise ValueError(f"window_number {bundle.window_number} out of range 1..{window_count}")

    result = Mip37Result(
        project_ids=ids[: len(schedules)],
        schedule_count=len(schedules),
        window_count=window_count,
    )

    total = 0.0
    for n in range(1, window_count + 1):
        baseline_schedule = schedules[n - 1]
        end_schedule = schedules[n]
        events = bundles[n].events if n in bundles else []

        per_window = analyze_mip_3_6(end_schedule, events, hours_per_day=hours_per_day)

        result.windows.append(
            Mip37WindowResult(
                window_number=n,
                window_id=f"W{n:02d}",
                baseline_project_id=ids[n - 1],
                update_project_id=ids[n],
                as_built_completion_days=per_window.as_built_completion_days,
                but_for_completion_days=per_window.but_for_completion_days,
                attributable_delay_days=per_window.attributable_delay_days,
                delay_events_applied=per_window.delay_events_applied,
                unmatched_events=per_window.unmatched_events,
            )
        )
        total += per_window.attributable_delay_days

    # Silence lint: we discard the baseline_schedule reference intentionally.
    del baseline_schedule

    result.total_attributable_delay_days = round(total, 2)
    return result
