# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""AACE RP 29R-03 observational MIPs — 3.1 (Gross) and 3.2 (As-Is).

Implements the two observational Methods of Implementation per AACE
Recommended Practice 29R-03 (Forensic Schedule Analysis):

- **MIP 3.1 — Observational / Static Logic / Gross**.  The most abridged
  forensic method.  Pairs the earliest as-planned schedule with the
  latest as-built schedule and reports gross delay, critical-path shift,
  and activity inventory deltas.  No intermediate updates are examined.

- **MIP 3.2 — Observational / Dynamic Logic / Contemporaneous As-Is**.
  Walks every schedule update chronologically, observing completion
  date movement and critical-path evolution at each data date without
  splitting the project into discrete windows.  Output is a narrative
  event stream rather than a window-by-window decomposition (that is
  MIP 3.3's job).

Both methods are *observational* — neither alters the schedules.  They
rely on the existing CPM calculator and schedule comparison engine.

References:
    AACE RP 29R-03 §3.1 (Static Logic Gross), §3.2 (Dynamic Logic As-Is).
    SCL Delay and Disruption Protocol, 2nd ed. (2017) — time-slice
    methodology alignment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from src.analytics.comparison import ScheduleComparison
from src.analytics.cpm import CPMCalculator
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers — deliberately duplicated from forensics.py for module isolation.
# Both modules accept a ParsedSchedule and derive the same fields; keeping
# them standalone means mip_observational stays independent from
# ForensicAnalyzer's lifecycle.
# ---------------------------------------------------------------------------


def _data_date(schedule: ParsedSchedule) -> datetime | None:
    if schedule.projects:
        proj = schedule.projects[0]
        return proj.last_recalc_date or proj.sum_data_date
    return None


def _completion_date(schedule: ParsedSchedule) -> datetime | None:
    """Forecasted completion date. Falls back to latest early_end_date."""
    fallback: datetime | None = None
    for task in schedule.activities:
        if task.early_end_date and (fallback is None or task.early_end_date > fallback):
            fallback = task.early_end_date

    try:
        cpm = CPMCalculator(schedule).calculate()
        if cpm.has_cycles or not cpm.critical_path:
            return fallback
        max_ef = max(
            (cpm.activity_results[tid].early_finish for tid in cpm.critical_path),
            default=0.0,
        )
        if max_ef > 0 and schedule.projects and schedule.projects[0].plan_start_date:
            return schedule.projects[0].plan_start_date + timedelta(days=max_ef * 7.0 / 5.0)
    except Exception:
        logger.warning("CPM failed during completion-date extraction")
    return fallback


def _critical_path_codes(schedule: ParsedSchedule) -> list[str]:
    try:
        cpm = CPMCalculator(schedule).calculate()
        if cpm.has_cycles:
            return []
        out: list[str] = []
        for tid in cpm.critical_path:
            ar = cpm.activity_results.get(tid)
            if ar:
                out.append(ar.task_code or tid)
        return out
    except Exception:
        logger.warning("CPM failed during critical-path extraction")
        return []


def _driving_activity(schedule: ParsedSchedule) -> str:
    try:
        cpm = CPMCalculator(schedule).calculate()
        if cpm.has_cycles or not cpm.critical_path:
            return ""
        max_ef = -1.0
        driver = ""
        for tid in cpm.critical_path:
            ar = cpm.activity_results.get(tid)
            if ar and ar.early_finish >= max_ef:
                max_ef = ar.early_finish
                driver = ar.task_code or tid
        return driver
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# MIP 3.1 — Static Logic / Gross
# ---------------------------------------------------------------------------


@dataclass
class Mip31Result:
    """Output of MIP 3.1 — Static Logic Gross comparison.

    Captures the two endpoints of the project: the as-planned baseline
    and the final as-built.  Intermediate schedule history is ignored.
    """

    baseline_project_id: str = ""
    final_project_id: str = ""
    baseline_data_date: datetime | None = None
    final_data_date: datetime | None = None
    baseline_completion_date: datetime | None = None
    final_completion_date: datetime | None = None
    gross_delay_days: float = 0.0
    baseline_critical_path: list[str] = field(default_factory=list)
    final_critical_path: list[str] = field(default_factory=list)
    cp_activities_joined: list[str] = field(default_factory=list)
    cp_activities_left: list[str] = field(default_factory=list)
    driving_activity: str = ""
    activities_added: int = 0
    activities_deleted: int = 0
    activities_changed: int = 0
    comparison_summary: dict[str, Any] = field(default_factory=dict)
    methodology: str = "AACE RP 29R-03 MIP 3.1 — Static Logic / Gross"


def analyze_mip_3_1(
    baseline: ParsedSchedule,
    final: ParsedSchedule,
    baseline_id: str = "",
    final_id: str = "",
) -> Mip31Result:
    """Run MIP 3.1 — Observational Static Logic / Gross.

    Compares only the first and last schedules; reports gross delay and
    critical-path shift.  Intended for quick high-level assessments when
    a full CPA (MIP 3.3) is not warranted.

    Args:
        baseline: The earliest (as-planned) schedule.
        final: The latest (as-built) schedule.
        baseline_id: Project identifier for the baseline (optional).
        final_id: Project identifier for the final schedule (optional).

    Returns:
        A populated ``Mip31Result``.

    Reference: AACE RP 29R-03 §3.1.
    """
    result = Mip31Result(baseline_project_id=baseline_id, final_project_id=final_id)

    result.baseline_data_date = _data_date(baseline)
    result.final_data_date = _data_date(final)
    result.baseline_completion_date = _completion_date(baseline)
    result.final_completion_date = _completion_date(final)

    if result.baseline_completion_date and result.final_completion_date:
        result.gross_delay_days = float(
            (result.final_completion_date - result.baseline_completion_date).days
        )

    base_cp = _critical_path_codes(baseline)
    final_cp = _critical_path_codes(final)
    result.baseline_critical_path = base_cp
    result.final_critical_path = final_cp
    result.cp_activities_joined = sorted(set(final_cp) - set(base_cp))
    result.cp_activities_left = sorted(set(base_cp) - set(final_cp))
    result.driving_activity = _driving_activity(final)

    try:
        comparison = ScheduleComparison(baseline, final).compare()
        result.comparison_summary = comparison.summary or {}
        result.activities_added = len(getattr(comparison, "added_activities", []) or [])
        result.activities_deleted = len(getattr(comparison, "deleted_activities", []) or [])
        result.activities_changed = len(getattr(comparison, "changed_activities", []) or [])
    except Exception:
        logger.warning("ScheduleComparison failed in MIP 3.1")

    return result


# ---------------------------------------------------------------------------
# MIP 3.2 — Dynamic Logic / Contemporaneous As-Is
# ---------------------------------------------------------------------------


@dataclass
class Mip32Event:
    """One observational event — the state of the project at a single update."""

    index: int
    project_id: str
    data_date: datetime | None = None
    completion_date: datetime | None = None
    delay_since_baseline_days: float = 0.0
    delay_since_previous_days: float = 0.0
    critical_path: list[str] = field(default_factory=list)
    cp_activities_joined_since_previous: list[str] = field(default_factory=list)
    cp_activities_left_since_previous: list[str] = field(default_factory=list)
    driving_activity: str = ""


@dataclass
class Mip32Result:
    """Output of MIP 3.2 — Dynamic Logic Contemporaneous As-Is observation.

    Narrative of the project: one event per update.  No simulation, no
    window accounting; cumulative delay is measured against the first
    schedule's completion forecast.
    """

    project_ids: list[str] = field(default_factory=list)
    schedule_count: int = 0
    baseline_completion_date: datetime | None = None
    final_completion_date: datetime | None = None
    total_delay_days: float = 0.0
    events: list[Mip32Event] = field(default_factory=list)
    cp_activities_ever_critical: list[str] = field(default_factory=list)
    methodology: str = "AACE RP 29R-03 MIP 3.2 — Dynamic Logic / Contemporaneous As-Is"


def analyze_mip_3_2(
    schedules: list[ParsedSchedule],
    project_ids: list[str] | None = None,
) -> Mip32Result:
    """Run MIP 3.2 — Observational Dynamic Logic / Contemporaneous As-Is.

    Walks every supplied schedule in chronological order (as given),
    observing completion-date movement and CP evolution at each step.
    Does not split the project into discrete windows.

    Args:
        schedules: List of parsed schedules in chronological order.
            At least 2 required.
        project_ids: Optional project identifiers parallel to ``schedules``.

    Returns:
        A populated ``Mip32Result`` with one event per schedule.

    Raises:
        ValueError: If fewer than 2 schedules are supplied.

    Reference: AACE RP 29R-03 §3.2.
    """
    if len(schedules) < 2:
        raise ValueError("MIP 3.2 requires at least 2 schedule updates")

    ids = list(project_ids or [""] * len(schedules))
    if len(ids) < len(schedules):
        ids.extend([""] * (len(schedules) - len(ids)))

    result = Mip32Result(
        project_ids=ids[: len(schedules)],
        schedule_count=len(schedules),
    )

    baseline_completion = _completion_date(schedules[0])
    result.baseline_completion_date = baseline_completion

    previous_completion = baseline_completion
    previous_cp: list[str] = []
    ever_critical: set[str] = set()

    for idx, schedule in enumerate(schedules):
        completion = _completion_date(schedule)
        cp = _critical_path_codes(schedule)

        ever_critical.update(cp)

        delay_vs_base = 0.0
        if baseline_completion and completion:
            delay_vs_base = float((completion - baseline_completion).days)

        delay_vs_prev = 0.0
        if previous_completion and completion and idx > 0:
            delay_vs_prev = float((completion - previous_completion).days)

        joined = sorted(set(cp) - set(previous_cp)) if idx > 0 else []
        left = sorted(set(previous_cp) - set(cp)) if idx > 0 else []

        result.events.append(
            Mip32Event(
                index=idx,
                project_id=ids[idx] if idx < len(ids) else "",
                data_date=_data_date(schedule),
                completion_date=completion,
                delay_since_baseline_days=delay_vs_base,
                delay_since_previous_days=delay_vs_prev,
                critical_path=cp,
                cp_activities_joined_since_previous=joined,
                cp_activities_left_since_previous=left,
                driving_activity=_driving_activity(schedule),
            )
        )

        previous_completion = completion
        previous_cp = cp

    result.final_completion_date = previous_completion
    if baseline_completion and previous_completion:
        result.total_delay_days = float((previous_completion - baseline_completion).days)
    result.cp_activities_ever_critical = sorted(ever_critical)

    return result
