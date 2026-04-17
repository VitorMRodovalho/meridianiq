# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""AACE RP 29R-03 MIP 3.5 — Modified / Additive Multiple Base.

Implements the "Impacted As-Planned, Multiple Base" method per AACE
Recommended Practice 29R-03 §3.5.  For each analysis window (pair of
consecutive schedule updates), the caller attributes delay events
(activity + days) to that window.  The engine clones the window's
baseline (first schedule of the pair), *extends* each affected
activity's duration by the event days, re-runs CPM, and reports the
impact as the difference between the impacted completion and the
original (as-planned) baseline completion.

This mirrors ``mip_subtractive`` in structure but applies additive
rather than subtractive edits — i.e. "add these delay events to the
schedule and measure the resulting slippage" vs. MIP 3.6/3.7's "remove
these delay events and measure the but-for completion".

The method is **subjective** in that the caller identifies the delay
events; the computation of the impacted completion is deterministic
once the events are fixed.

References:
    AACE RP 29R-03 §3.5 (Modified / Additive Multiple Base).
    SCL Delay and Disruption Protocol 2nd ed. §22.2 (Impacted
    As-Planned Analysis).
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.cpm import CPMCalculator
from src.analytics.mip_subtractive import DelayEvent, WindowDelayEvents
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


_HOURS_PER_DAY = 8.0


@dataclass
class AppliedAdditiveEvent:
    """Record of an additive delay event's application to a specific activity."""

    task_id: str
    task_code: str
    task_name: str
    days_requested: float
    days_applied: float
    original_duration_days: float
    impacted_duration_days: float
    description: str = ""
    note: str = ""


@dataclass
class Mip35WindowResult:
    """Per-window output of MIP 3.5."""

    window_number: int
    window_id: str
    baseline_project_id: str = ""
    update_project_id: str = ""
    baseline_completion_days: float = 0.0
    impacted_completion_days: float = 0.0
    impact_delay_days: float = 0.0
    delay_events_applied: list[AppliedAdditiveEvent] = field(default_factory=list)
    unmatched_events: list[DelayEvent] = field(default_factory=list)


@dataclass
class Mip35Result:
    """Output of MIP 3.5 — Additive Multiple Base analysis."""

    project_ids: list[str] = field(default_factory=list)
    schedule_count: int = 0
    window_count: int = 0
    total_impact_delay_days: float = 0.0
    windows: list[Mip35WindowResult] = field(default_factory=list)
    methodology: str = "AACE RP 29R-03 MIP 3.5 — Modified / Additive Multiple Base"


def _critical_codes(cpm_result: Any) -> list[str]:
    codes: list[str] = []
    for tid in cpm_result.critical_path:
        ar = cpm_result.activity_results.get(tid)
        if ar:
            codes.append(ar.task_code or tid)
    return codes


def _analyze_window_additive(
    baseline: ParsedSchedule,
    events: list[DelayEvent],
    window_number: int,
    baseline_project_id: str,
    update_project_id: str,
    hours_per_day: float,
) -> Mip35WindowResult:
    """Run one additive window: clone baseline, extend durations, CPM."""
    for event in events:
        if event.days < 0:
            raise ValueError(
                f"DelayEvent days must be non-negative; got {event.days} "
                f"for task_id={event.task_id!r}"
            )

    # Baseline CPM (as-planned, no additive impact)
    baseline_cpm = CPMCalculator(baseline, hours_per_day=hours_per_day).calculate()
    baseline_completion = float(baseline_cpm.project_duration)

    # Build the impacted schedule
    impacted = copy.deepcopy(baseline)
    task_by_id: dict[str, Any] = {t.task_id: t for t in impacted.activities}

    applied: list[AppliedAdditiveEvent] = []
    unmatched: list[DelayEvent] = []

    for event in events:
        task = task_by_id.get(event.task_id)
        if task is None:
            unmatched.append(event)
            continue

        original_days = float(task.target_drtn_hr_cnt or 0.0) / hours_per_day
        add_hours = event.days * hours_per_day

        # Additive events are not clamped — extending a zero-duration milestone by
        # N days is meaningful (it becomes an N-day activity under the impact model).
        new_target = float(task.target_drtn_hr_cnt or 0.0) + add_hours
        new_remain = float(task.remain_drtn_hr_cnt or 0.0) + add_hours

        task.target_drtn_hr_cnt = new_target
        task.remain_drtn_hr_cnt = new_remain

        applied.append(
            AppliedAdditiveEvent(
                task_id=event.task_id,
                task_code=task.task_code or "",
                task_name=task.task_name or "",
                days_requested=event.days,
                days_applied=event.days,
                original_duration_days=round(original_days, 2),
                impacted_duration_days=round(new_target / hours_per_day, 2),
                description=event.description,
                note=(
                    "activity was zero-duration (milestone / LOE); "
                    "impact extends it to a positive duration"
                    if original_days == 0 and event.days > 0
                    else ""
                ),
            )
        )

    # Impacted CPM
    impacted_cpm = CPMCalculator(impacted, hours_per_day=hours_per_day).calculate()
    impacted_completion = float(impacted_cpm.project_duration)

    impact_delay = round(impacted_completion - baseline_completion, 2)

    return Mip35WindowResult(
        window_number=window_number,
        window_id=f"W{window_number:02d}",
        baseline_project_id=baseline_project_id,
        update_project_id=update_project_id,
        baseline_completion_days=baseline_completion,
        impacted_completion_days=impacted_completion,
        impact_delay_days=impact_delay,
        delay_events_applied=applied,
        unmatched_events=unmatched,
    )


def analyze_mip_3_5(
    schedules: list[ParsedSchedule],
    window_delay_events: list[WindowDelayEvents] | None = None,
    project_ids: list[str] | None = None,
    hours_per_day: float = _HOURS_PER_DAY,
) -> Mip35Result:
    """Run MIP 3.5 — Additive Multiple Base impacted as-planned analysis.

    For each analysis window (schedule[N-1] → schedule[N]), the window's
    **baseline** (the earlier of the two) is impacted with the caller's
    delay events.  The difference between the impacted and original
    baseline completion is attributed as that window's impact delay.

    Args:
        schedules: Parsed schedules in chronological order, minimum 2.
        window_delay_events: Optional per-window delay-event bundles.
            Windows without an entry impact with zero events (no-op).
        project_ids: Optional IDs parallel to ``schedules``.
        hours_per_day: Hours per working day (matches CPM default).

    Returns:
        A populated ``Mip35Result`` — per-window breakdown plus total.

    Raises:
        ValueError: If fewer than 2 schedules, window_number is out of
            range, or any event has negative days.

    Reference: AACE RP 29R-03 §3.5.
    """
    if len(schedules) < 2:
        raise ValueError("MIP 3.5 requires at least 2 schedule updates")

    ids = list(project_ids or [""] * len(schedules))
    if len(ids) < len(schedules):
        ids.extend([""] * (len(schedules) - len(ids)))

    window_count = len(schedules) - 1
    bundles = {w.window_number: w for w in (window_delay_events or [])}

    for bundle in bundles.values():
        if bundle.window_number < 1 or bundle.window_number > window_count:
            raise ValueError(f"window_number {bundle.window_number} out of range 1..{window_count}")

    result = Mip35Result(
        project_ids=ids[: len(schedules)],
        schedule_count=len(schedules),
        window_count=window_count,
    )

    total = 0.0
    for n in range(1, window_count + 1):
        baseline = schedules[n - 1]
        events = bundles[n].events if n in bundles else []

        window_result = _analyze_window_additive(
            baseline=baseline,
            events=events,
            window_number=n,
            baseline_project_id=ids[n - 1],
            update_project_id=ids[n],
            hours_per_day=hours_per_day,
        )
        result.windows.append(window_result)
        total += window_result.impact_delay_days

    result.total_impact_delay_days = round(total, 2)
    return result
