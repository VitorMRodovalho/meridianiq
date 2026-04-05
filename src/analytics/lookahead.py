# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Look-ahead schedule — short-term activity window view.

Filters activities to a configurable time window (typically 2-4 weeks)
relative to the data date, providing construction managers and field teams
with a focused view of near-term work.

References:
    - PMI Practice Standard for Scheduling — Look-Ahead Planning
    - Lean Construction Institute — Last Planner System (LPS)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.cpm import CPMCalculator
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)

_HOURS_PER_DAY = 8.0


@dataclass
class LookaheadActivity:
    """An activity within the look-ahead window."""

    task_id: str = ""
    task_code: str = ""
    task_name: str = ""
    wbs_id: str = ""
    status: str = ""
    start_day: float = 0.0
    finish_day: float = 0.0
    duration_days: float = 0.0
    total_float_days: float = 0.0
    progress_pct: float = 0.0
    is_critical: bool = False
    responsible: str = ""


@dataclass
class LookaheadResult:
    """Result of a look-ahead schedule analysis."""

    window_weeks: int = 2
    window_days: int = 14
    activities: list[LookaheadActivity] = field(default_factory=list)
    total_in_window: int = 0
    active_count: int = 0
    starting_count: int = 0
    finishing_count: int = 0
    critical_count: int = 0
    methodology: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


def generate_lookahead(
    schedule: ParsedSchedule,
    weeks: int = 2,
) -> LookaheadResult:
    """Generate a look-ahead schedule for the next N weeks.

    Filters activities that start, finish, or are active within
    the look-ahead window relative to the project data date.

    Args:
        schedule: The schedule to analyze.
        weeks: Number of weeks for the look-ahead window (default 2).

    Returns:
        A ``LookaheadResult`` with filtered activities and counts.

    References:
        - PMI Practice Standard for Scheduling — Look-Ahead Planning
        - Lean Construction Institute — Last Planner System
    """
    result = LookaheadResult(window_weeks=weeks, window_days=weeks * 5)
    window_days = weeks * 5  # Working days

    # Run CPM
    try:
        cpm = CPMCalculator(schedule, hours_per_day=_HOURS_PER_DAY).calculate()
    except Exception:
        logger.warning("CPM failed for look-ahead")
        result.methodology = "CPM failed"
        return result

    cp_set = set(cpm.critical_path)
    activities: list[LookaheadActivity] = []

    for task in schedule.activities:
        if task.status_code.lower() == "tk_complete":
            continue

        ar = cpm.activity_results.get(task.task_id)
        if ar is None:
            continue

        # Filter: activity overlaps with window [0, window_days]
        if ar.early_start > window_days:
            continue  # Starts after window
        if ar.early_finish < 0:
            continue  # Already finished (shouldn't happen for non-complete)

        tf_hrs = task.total_float_hr_cnt if task.total_float_hr_cnt is not None else 0

        activities.append(
            LookaheadActivity(
                task_id=task.task_id,
                task_code=task.task_code,
                task_name=task.task_name,
                wbs_id=task.wbs_id or "",
                status=task.status_code,
                start_day=round(ar.early_start, 1),
                finish_day=round(ar.early_finish, 1),
                duration_days=round(ar.duration, 1),
                total_float_days=round(tf_hrs / _HOURS_PER_DAY, 1),
                progress_pct=task.phys_complete_pct,
                is_critical=task.task_id in cp_set,
            )
        )

    # Sort by start day
    activities.sort(key=lambda a: a.start_day)

    result.activities = activities
    result.total_in_window = len(activities)
    result.active_count = sum(1 for a in activities if a.status.lower() == "tk_active")
    result.starting_count = sum(
        1 for a in activities if a.status.lower() == "tk_notstart" and a.start_day <= window_days
    )
    result.finishing_count = sum(1 for a in activities if a.finish_day <= window_days)
    result.critical_count = sum(1 for a in activities if a.is_critical)

    result.methodology = (
        f"{weeks}-week look-ahead schedule (PMI Practice Standard, Lean Construction LPS)"
    )

    result.summary = {
        "window_weeks": weeks,
        "window_days": window_days,
        "total_in_window": result.total_in_window,
        "active": result.active_count,
        "starting": result.starting_count,
        "finishing": result.finishing_count,
        "critical": result.critical_count,
        "methodology": result.methodology,
    }

    return result
