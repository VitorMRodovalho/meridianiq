# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""4D visualization data — timeline + WBS spatial layout.

Produces a structured dataset that maps activities to a 2D spatial grid
(WBS hierarchy × time) suitable for rendering as a 4D-style chart.
Activities are positioned by their WBS path (Y-axis) and CPM dates
(X-axis), with color coding by status, float level, or risk score.

References:
    - PMI Practice Standard for Scheduling — Gantt Chart Extensions
    - AACE RP 49R-06 — Float Trend Visualization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.cpm import CPMCalculator, CPMResult
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)

_HOURS_PER_DAY = 8.0


@dataclass
class VisualizationActivity:
    """An activity positioned in the 4D visualization grid."""

    task_id: str = ""
    task_code: str = ""
    task_name: str = ""
    wbs_id: str = ""
    wbs_path: str = ""  # Full WBS hierarchy label
    # Temporal position (days from project start)
    early_start: float = 0.0
    early_finish: float = 0.0
    duration_days: float = 0.0
    # Status and metrics
    status: str = ""
    progress_pct: float = 0.0
    total_float_days: float = 0.0
    is_critical: bool = False
    # Color coding
    color_category: str = "not_started"  # critical, active, complete, not_started, high_float


@dataclass
class WBSGroup:
    """A WBS group containing activities at the same level."""

    wbs_id: str = ""
    wbs_name: str = ""
    depth: int = 0
    activity_count: int = 0
    row_index: int = 0  # Y-axis position


@dataclass
class VisualizationResult:
    """Complete 4D visualization data."""

    activities: list[VisualizationActivity] = field(default_factory=list)
    wbs_groups: list[WBSGroup] = field(default_factory=list)
    project_duration_days: float = 0.0
    total_activities: int = 0
    critical_count: int = 0
    max_wbs_depth: int = 0
    methodology: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


def _categorize_activity(
    status: str,
    is_critical: bool,
    total_float_hrs: float,
) -> str:
    """Assign color category based on status and float."""
    if status.lower() == "tk_complete":
        return "complete"
    if is_critical:
        return "critical"
    if status.lower() == "tk_active":
        return "active"
    if total_float_hrs > 44 * _HOURS_PER_DAY:
        return "high_float"
    return "not_started"


def build_visualization(
    schedule: ParsedSchedule,
) -> VisualizationResult:
    """Build 4D visualization data from a schedule.

    Maps activities to a WBS × time grid with color-coded status.

    Args:
        schedule: The schedule to visualize.

    Returns:
        A ``VisualizationResult`` with positioned activities and WBS groups.

    References:
        - PMI Practice Standard for Scheduling — Gantt Extensions
        - AACE RP 49R-06 — Float Visualization
    """
    result = VisualizationResult()

    # Run CPM
    try:
        cpm = CPMCalculator(schedule, hours_per_day=_HOURS_PER_DAY).calculate()
    except Exception:
        logger.warning("CPM failed for visualization")
        cpm = CPMResult()

    result.project_duration_days = round(cpm.project_duration, 1)
    cp_set = set(cpm.critical_path)

    # Build WBS name map from wbs_nodes
    wbs_name_map: dict[str, str] = {}
    for wbs in schedule.wbs_nodes:
        wbs_name_map[wbs.wbs_id] = wbs.wbs_name or wbs.wbs_short_name or wbs.wbs_id

    # Collect unique WBS IDs and assign row indices
    wbs_ids: list[str] = []
    seen_wbs: set[str] = set()
    for task in schedule.activities:
        wbs = task.wbs_id or "Unassigned"
        if wbs not in seen_wbs:
            wbs_ids.append(wbs)
            seen_wbs.add(wbs)

    wbs_groups = []
    for i, wbs_id in enumerate(wbs_ids):
        depth = wbs_id.count(".") if wbs_id != "Unassigned" else 0
        wbs_groups.append(
            WBSGroup(
                wbs_id=wbs_id,
                wbs_name=wbs_name_map.get(wbs_id, wbs_id),
                depth=depth,
                row_index=i,
                activity_count=sum(
                    1 for t in schedule.activities if (t.wbs_id or "Unassigned") == wbs_id
                ),
            )
        )
    result.wbs_groups = wbs_groups
    result.max_wbs_depth = max((g.depth for g in wbs_groups), default=0)

    # Build activity visualization entries
    {t.task_id: t for t in schedule.activities}
    vis_activities = []

    for task in schedule.activities:
        ar = cpm.activity_results.get(task.task_id)
        is_crit = task.task_id in cp_set
        tf_hrs = task.total_float_hr_cnt if task.total_float_hr_cnt is not None else 0

        vis_activities.append(
            VisualizationActivity(
                task_id=task.task_id,
                task_code=task.task_code,
                task_name=task.task_name,
                wbs_id=task.wbs_id or "Unassigned",
                wbs_path=wbs_name_map.get(task.wbs_id or "", task.wbs_id or ""),
                early_start=round(ar.early_start, 1) if ar else 0,
                early_finish=round(ar.early_finish, 1) if ar else 0,
                duration_days=round(ar.duration, 1) if ar else 0,
                status=task.status_code,
                progress_pct=task.phys_complete_pct,
                total_float_days=round(tf_hrs / _HOURS_PER_DAY, 1),
                is_critical=is_crit,
                color_category=_categorize_activity(task.status_code, is_crit, tf_hrs),
            )
        )

    result.activities = vis_activities
    result.total_activities = len(vis_activities)
    result.critical_count = sum(1 for a in vis_activities if a.is_critical)

    result.methodology = "4D visualization: WBS spatial grouping × CPM temporal positioning"

    result.summary = {
        "total_activities": result.total_activities,
        "critical_count": result.critical_count,
        "wbs_groups": len(result.wbs_groups),
        "max_wbs_depth": result.max_wbs_depth,
        "project_duration_days": result.project_duration_days,
        "color_distribution": {
            cat: sum(1 for a in vis_activities if a.color_category == cat)
            for cat in ["critical", "active", "complete", "not_started", "high_float"]
        },
    }

    return result
