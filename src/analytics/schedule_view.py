# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Schedule View — pre-computed layout data for interactive Gantt viewer.

Builds a WBS tree hierarchy, flattens activities with indent levels,
and computes layout data optimized for the frontend ScheduleViewer
component.  All date math and sorting happens server-side so the
frontend only needs to render.

References:
    - AACE RP 49R-06 — Identifying Critical Activities
    - DCMA 14-Point Assessment — Schedule structure metrics
    - GAO Schedule Assessment Guide — Activity hierarchy
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.analytics.cpm import CPMCalculator
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


@dataclass
class WBSNode:
    """A node in the WBS tree."""

    wbs_id: str
    name: str
    short_name: str = ""
    depth: int = 0
    parent_id: str = ""
    activity_count: int = 0
    children: list[WBSNode] = field(default_factory=list)


@dataclass
class ActivityView:
    """A single activity formatted for the Gantt viewer."""

    task_id: str
    task_code: str = ""
    task_name: str = ""
    wbs_id: str = ""
    wbs_path: str = ""
    indent_level: int = 0
    task_type: str = "task"  # task, milestone, loe
    status: str = "not_started"
    early_start: str = ""  # ISO date
    early_finish: str = ""
    late_start: str = ""
    late_finish: str = ""
    actual_start: str | None = None
    actual_finish: str | None = None
    baseline_start: str | None = None
    baseline_finish: str | None = None
    duration_days: float = 0.0
    remaining_days: float = 0.0
    total_float_days: float = 0.0
    free_float_days: float = 0.0
    progress_pct: float = 0.0
    is_critical: bool = False
    is_driving: bool = False
    calendar_id: str = ""
    constraint_type: str = ""
    constraint_date: str | None = None
    start_variance_days: float | None = None
    finish_variance_days: float | None = None
    alerts: list[str] = field(default_factory=list)


@dataclass
class RelationshipView:
    """A dependency formatted for the Gantt viewer."""

    from_id: str
    to_id: str
    type: str = "FS"  # FS, FF, SS, SF
    lag_days: float = 0.0
    is_driving: bool = False


@dataclass
class ScheduleViewResult:
    """Complete layout data for the Gantt viewer."""

    project_name: str = ""
    data_date: str = ""
    project_start: str = ""
    project_finish: str = ""
    wbs_tree: list[WBSNode] = field(default_factory=list)
    activities: list[ActivityView] = field(default_factory=list)
    relationships: list[RelationshipView] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


def _fmt_date(dt: datetime | None) -> str:
    """Format a datetime as ISO date string."""
    return dt.isoformat()[:10] if dt else ""


def _task_type_label(task_type: str) -> str:
    """Convert P6 task type to display label."""
    tt = task_type.upper()
    if tt in ("TT_MILE", "TT_FINMILE"):
        return "milestone"
    if tt == "TT_LOE":
        return "loe"
    return "task"


def _status_label(status_code: str) -> str:
    """Convert P6 status code to display label."""
    sc = status_code.upper()
    if sc == "TK_COMPLETE":
        return "complete"
    if sc == "TK_ACTIVE":
        return "active"
    return "not_started"


def build_schedule_view(
    schedule: ParsedSchedule,
    baseline: ParsedSchedule | None = None,
) -> ScheduleViewResult:
    """Build pre-computed layout data for the Gantt viewer.

    Args:
        schedule: The current/update schedule.
        baseline: Optional baseline schedule for comparison bars.

    Returns:
        ScheduleViewResult with WBS tree, flattened activities, and relationships.
    """
    result = ScheduleViewResult()

    # Project metadata
    if schedule.projects:
        proj = schedule.projects[0]
        result.project_name = proj.proj_short_name or ""
        result.data_date = _fmt_date(proj.last_recalc_date or proj.sum_data_date)

    # Run CPM to get critical path
    cpm = CPMCalculator(schedule)
    cpm_result = cpm.calculate()

    # Determine critical path set
    critical_ids: set[str] = set()
    if cpm_result.critical_path:
        critical_ids = set(cpm_result.critical_path)

    # Build WBS hierarchy
    wbs_map: dict[str, WBSNode] = {}
    wbs_children: dict[str, list[str]] = {}  # parent_id -> [child_ids]

    for w in schedule.wbs_nodes:
        node = WBSNode(
            wbs_id=w.wbs_id,
            name=w.wbs_name or w.wbs_short_name or w.wbs_id,
            short_name=w.wbs_short_name,
            parent_id=w.parent_wbs_id,
        )
        wbs_map[w.wbs_id] = node
        if w.parent_wbs_id:
            wbs_children.setdefault(w.parent_wbs_id, []).append(w.wbs_id)

    # Count activities per WBS
    for t in schedule.activities:
        if t.wbs_id in wbs_map:
            wbs_map[t.wbs_id].activity_count += 1

    # Compute depth
    def _set_depth(wbs_id: str, depth: int) -> None:
        if wbs_id in wbs_map:
            wbs_map[wbs_id].depth = depth
            for child_id in wbs_children.get(wbs_id, []):
                _set_depth(child_id, depth + 1)

    # Find root nodes (no parent or parent not in map)
    root_ids = [
        wid for wid, node in wbs_map.items() if not node.parent_id or node.parent_id not in wbs_map
    ]
    for rid in root_ids:
        _set_depth(rid, 0)

    # Build tree structure
    def _build_tree(parent_id: str) -> list[WBSNode]:
        children = []
        for child_id in wbs_children.get(parent_id, []):
            node = wbs_map[child_id]
            node.children = _build_tree(child_id)
            children.append(node)
        return sorted(children, key=lambda n: n.short_name or n.name)

    for rid in sorted(root_ids):
        if rid in wbs_map:
            root = wbs_map[rid]
            root.children = _build_tree(rid)
            result.wbs_tree.append(root)

    # Build WBS path lookup
    wbs_path: dict[str, str] = {}

    def _build_path(node: WBSNode, prefix: str) -> None:
        path = (
            f"{prefix}/{node.short_name or node.name}" if prefix else (node.short_name or node.name)
        )
        wbs_path[node.wbs_id] = path
        for child in node.children:
            _build_path(child, path)

    for root in result.wbs_tree:
        _build_path(root, "")

    # Build baseline lookup
    baseline_dates: dict[str, tuple[str, str]] = {}
    if baseline:
        for t in baseline.activities:
            es = _fmt_date(t.early_start_date or t.target_start_date)
            ef = _fmt_date(t.early_end_date or t.target_end_date)
            baseline_dates[t.task_code or t.task_id] = (es, ef)
            baseline_dates[t.task_id] = (es, ef)

    # Calendar hours/day for float conversion
    day_hours = 8.0
    if schedule.calendars:
        day_hours = schedule.calendars[0].day_hr_cnt or 8.0

    # Flatten activities sorted by WBS path + early start
    sorted_tasks = sorted(
        schedule.activities,
        key=lambda t: (
            wbs_path.get(t.wbs_id, ""),
            t.early_start_date or t.target_start_date or datetime.max,
        ),
    )

    earliest_date: datetime | None = None
    latest_date: datetime | None = None

    for t in sorted_tasks:
        es = t.early_start_date or t.target_start_date
        ef = t.early_end_date or t.target_end_date
        ls = t.late_start_date
        lf = t.late_end_date

        if es and (earliest_date is None or es < earliest_date):
            earliest_date = es
        if ef and (latest_date is None or ef > latest_date):
            latest_date = ef

        # Float in days
        tf_days = (t.total_float_hr_cnt or 0) / day_hours
        ff_days = (t.free_float_hr_cnt or 0) / day_hours

        # Duration in days
        dur_days = (
            t.remain_drtn_hr_cnt + (t.target_drtn_hr_cnt - t.remain_drtn_hr_cnt)
        ) / day_hours
        if dur_days <= 0:
            dur_days = t.target_drtn_hr_cnt / day_hours

        # WBS depth for indent
        indent = wbs_map[t.wbs_id].depth + 1 if t.wbs_id in wbs_map else 0

        # Baseline dates
        bl_start = None
        bl_finish = None
        key = t.task_code or t.task_id
        if key in baseline_dates:
            bl_start, bl_finish = baseline_dates[key]
        elif t.task_id in baseline_dates:
            bl_start, bl_finish = baseline_dates[t.task_id]

        # Variance calculations (vs baseline)
        start_var: float | None = None
        finish_var: float | None = None
        if bl_start and es:
            try:
                from datetime import datetime as _dt

                bs = _dt.fromisoformat(bl_start)
                start_var = round((es - bs).days, 1)
            except (ValueError, TypeError):
                pass
        if bl_finish and ef:
            try:
                from datetime import datetime as _dt

                bf = _dt.fromisoformat(bl_finish)
                finish_var = round((ef - bf).days, 1)
            except (ValueError, TypeError):
                pass

        # Alerts
        alerts: list[str] = []
        if tf_days < 0:
            alerts.append("negative_float")
        if t.cstr_type and t.cstr_type not in ("", "CS_MEO"):
            alerts.append("hard_constraint")
        if (
            t.status_code.upper() == "TK_ACTIVE"
            and t.act_start_date
            and es
            and t.act_start_date < es
        ):
            alerts.append("out_of_sequence")

        av = ActivityView(
            task_id=t.task_id,
            task_code=t.task_code,
            task_name=t.task_name,
            wbs_id=t.wbs_id,
            wbs_path=wbs_path.get(t.wbs_id, ""),
            indent_level=indent,
            task_type=_task_type_label(t.task_type),
            status=_status_label(t.status_code),
            early_start=_fmt_date(es),
            early_finish=_fmt_date(ef),
            late_start=_fmt_date(ls),
            late_finish=_fmt_date(lf),
            actual_start=_fmt_date(t.act_start_date) if t.act_start_date else None,
            actual_finish=_fmt_date(t.act_end_date) if t.act_end_date else None,
            baseline_start=bl_start if bl_start else None,
            baseline_finish=bl_finish if bl_finish else None,
            duration_days=round(dur_days, 1),
            remaining_days=round(t.remain_drtn_hr_cnt / day_hours, 1),
            total_float_days=round(tf_days, 1),
            free_float_days=round(ff_days, 1),
            progress_pct=round(t.phys_complete_pct, 1),
            is_critical=t.task_id in critical_ids,
            is_driving=t.driving_path_flag.upper() == "Y" if t.driving_path_flag else False,
            calendar_id=t.clndr_id,
            constraint_type=t.cstr_type,
            constraint_date=_fmt_date(t.cstr_date) if t.cstr_date else None,
            start_variance_days=start_var,
            finish_variance_days=finish_var,
            alerts=alerts,
        )
        result.activities.append(av)

    # Relationships
    for r in schedule.relationships:
        pred_type = r.pred_type.replace("PR_", "") if r.pred_type.startswith("PR_") else r.pred_type
        lag_days = r.lag_hr_cnt / day_hours
        result.relationships.append(
            RelationshipView(
                from_id=r.pred_task_id,
                to_id=r.task_id,
                type=pred_type,
                lag_days=round(lag_days, 1),
            )
        )

    # Project date range
    result.project_start = _fmt_date(earliest_date)
    result.project_finish = _fmt_date(latest_date)

    # Summary
    complete_count = sum(1 for a in result.activities if a.status == "complete")
    near_critical = sum(
        1
        for a in result.activities
        if 0 < a.total_float_days <= 10 and a.status != "complete"
    )
    result.summary = {
        "total_activities": len(result.activities),
        "critical_count": len(critical_ids),
        "near_critical_count": near_critical,
        "complete_pct": round(complete_count / len(result.activities) * 100, 1)
        if result.activities
        else 0.0,
        "negative_float_count": sum(1 for a in result.activities if a.total_float_days < 0),
        "milestones_count": sum(1 for a in result.activities if a.task_type == "milestone"),
        "relationship_count": len(result.relationships),
        "calendar_count": len(schedule.calendars),
    }

    return result
