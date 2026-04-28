# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Projects router — list, detail, and sandbox toggle."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from src.parser.models import ParsedSchedule

from ..auth import optional_auth
from ..deps import RATE_LIMIT_MODERATE, RATE_LIMIT_READ, _sandbox_projects, get_store, limiter
from ..schemas import (
    ActivitySchema,
    ActivityStatusSummary,
    PendingStatusesResponse,
    PendingStatusItem,
    ProjectDetailResponse,
    ProjectListItem,
    ProjectListResponse,
    RelationshipSchema,
    RelationshipTypeSummary,
    WBSLevelCount,
    WBSStats,
)

router = APIRouter()


@router.get("/api/v1/projects", response_model=ProjectListResponse)
def list_projects(
    include_sandbox: bool = False,
    _user: object = Depends(optional_auth),
) -> ProjectListResponse:
    """List all uploaded projects.

    By default, sandbox projects are hidden. Pass ``include_sandbox=true``
    to include them (only visible to the owner regardless).
    """
    store = get_store()
    user_id = _user["id"] if _user else None
    all_projects = store.list_all(user_id=user_id)
    if not include_sandbox:
        all_projects = [p for p in all_projects if p["project_id"] not in _sandbox_projects]

    from src.analytics.schedule_metadata import extract_metadata

    items = []
    for p in all_projects:
        meta = extract_metadata(filename="", project_name=p.get("name", ""))
        items.append(
            ProjectListItem(
                **p,
                tags=meta.tags,
            )
        )
    return ProjectListResponse(projects=items)


@router.get("/api/v1/projects/pending-statuses", response_model=PendingStatusesResponse)
@limiter.limit(RATE_LIMIT_READ)
def list_pending_statuses(
    request: Request,
    _user: object = Depends(optional_auth),
) -> PendingStatusesResponse:
    """Aggregate banner poll — returns the caller's pending / failed projects.

    Introduced in W3 (ADR-0016) per frontend-ux-reviewer's P1 on poll-storm
    avoidance: one aggregate endpoint per logged-in user instead of N
    per-project pollers. The ``ComputingBanner.svelte`` component polls
    this endpoint every 3s and derives the ``computingProjects`` store
    from the result.

    Terminal rows (``status='ready'``) are excluded. A user with zero
    pending / failed rows receives an empty ``items`` list — that is the
    signal to the banner to render as hidden.

    Council P1 (backend-reviewer P1-4): when ``user_id`` is ``None``
    (dev path where ``optional_auth`` returns None — production raises
    401 at the auth layer), short-circuit with an empty list. A
    ``None`` user_id without short-circuit fans out to a global
    ``get_projects`` that would leak every tenant's pending rows.
    """
    from datetime import UTC, datetime

    user_id: str | None = _user["id"] if isinstance(_user, dict) else None
    if user_id is None:
        return PendingStatusesResponse(items=[], polled_at=datetime.now(UTC).isoformat())

    store = get_store()
    rows = store.get_projects(user_id=user_id, include_all_statuses=True)
    items: list[PendingStatusItem] = []
    for row in rows:
        status = str(row.get("status") or "ready")
        if status == "ready":
            continue
        items.append(
            PendingStatusItem(
                project_id=row["project_id"],
                name=row.get("name") or "",
                status=status,
            )
        )
    return PendingStatusesResponse(
        items=items,
        polled_at=datetime.now(UTC).isoformat(),
    )


@router.put("/api/v1/projects/{project_id}/sandbox")
@limiter.limit(RATE_LIMIT_MODERATE)
def toggle_sandbox(
    request: Request,
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Toggle sandbox mode for a project.

    Sandbox projects are hidden from project listings and org views.
    Only the owner can see and toggle sandbox status.
    """
    store = get_store()
    user_id = _user["id"] if _user else None
    schedule = store.get(project_id, user_id=user_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if project_id in _sandbox_projects:
        _sandbox_projects.discard(project_id)
        is_sandbox = False
    else:
        _sandbox_projects.add(project_id)
        is_sandbox = True

    return {"project_id": project_id, "is_sandbox": is_sandbox}


@router.get("/api/v1/projects/{project_id}", response_model=ProjectDetailResponse)
def get_project(project_id: str, _user: object = Depends(optional_auth)) -> ProjectDetailResponse:
    """Get full project data for a given project_id.

    Args:
        project_id: The stored project identifier.

    Raises:
        HTTPException: If the project is not found.
    """
    store = get_store()
    user_id = _user["id"] if _user else None
    schedule = store.get(project_id, user_id=user_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    data_date = None
    name = ""
    if schedule.projects:
        proj = schedule.projects[0]
        name = proj.proj_short_name
        dd = proj.last_recalc_date or proj.sum_data_date
        if dd:
            data_date = dd.isoformat()

    activities = [
        ActivitySchema(
            task_id=t.task_id,
            task_code=t.task_code,
            task_name=t.task_name,
            task_type=t.task_type,
            status_code=t.status_code,
            total_float_hr_cnt=t.total_float_hr_cnt,
            remain_drtn_hr_cnt=t.remain_drtn_hr_cnt,
            target_drtn_hr_cnt=t.target_drtn_hr_cnt,
            act_start_date=t.act_start_date,
            act_end_date=t.act_end_date,
            early_start_date=t.early_start_date,
            early_end_date=t.early_end_date,
            late_start_date=t.late_start_date,
            late_end_date=t.late_end_date,
        )
        for t in schedule.activities
    ]

    relationships = [
        RelationshipSchema(
            task_id=r.task_id,
            pred_task_id=r.pred_task_id,
            pred_type=r.pred_type,
            lag_hr_cnt=r.lag_hr_cnt,
        )
        for r in schedule.relationships
    ]

    # Compute WBS hierarchy statistics
    wbs_stats = _compute_wbs_stats(schedule)

    # Compute summary counts server-side (avoids client iterating full arrays)
    complete = sum(1 for t in schedule.activities if t.status_code.upper() == "TK_COMPLETE")
    active = sum(1 for t in schedule.activities if t.status_code.upper() == "TK_ACTIVE")
    activity_summary = ActivityStatusSummary(
        total=len(schedule.activities),
        complete=complete,
        in_progress=active,
        not_started=len(schedule.activities) - complete - active,
    )

    fs = ff = ss = sf = 0
    for r in schedule.relationships:
        pt = r.pred_type.upper() if r.pred_type else ""
        if pt == "PR_FS":
            fs += 1
        elif pt == "PR_FF":
            ff += 1
        elif pt == "PR_SS":
            ss += 1
        elif pt == "PR_SF":
            sf += 1
    relationship_summary = RelationshipTypeSummary(
        total=len(schedule.relationships),
        fs=fs,
        ff=ff,
        ss=ss,
        sf=sf,
    )

    return ProjectDetailResponse(
        project_id=project_id,
        name=name,
        data_date=data_date,
        activities=activities,
        relationships=relationships,
        wbs_stats=wbs_stats,
        activity_summary=activity_summary,
        relationship_summary=relationship_summary,
    )


def _compute_wbs_stats(schedule: ParsedSchedule) -> WBSStats:
    """Compute WBS hierarchy depth and activity distribution."""
    wbs_nodes = schedule.wbs_nodes
    if not wbs_nodes:
        return WBSStats()

    # Build parent->children map and find root(s)
    child_ids: set[str] = set()
    for w in wbs_nodes:
        if w.parent_wbs_id and w.parent_wbs_id != w.wbs_id:
            child_ids.add(w.wbs_id)

    # Calculate depth for each WBS node via BFS from roots
    roots = [w for w in wbs_nodes if w.wbs_id not in child_ids or w.proj_node_flag.upper() == "Y"]
    levels: dict[str, int] = {}
    queue = [(r.wbs_id, 1) for r in roots]
    for wbs_id, level in queue:
        if wbs_id in levels:
            continue
        levels[wbs_id] = level
        # Find children
        for w in wbs_nodes:
            if w.parent_wbs_id == wbs_id and w.wbs_id != wbs_id:
                queue.append((w.wbs_id, level + 1))

    # Assign level 1 to any unvisited nodes (orphans)
    for w in wbs_nodes:
        if w.wbs_id not in levels:
            levels[w.wbs_id] = 1

    max_depth = max(levels.values()) if levels else 0

    # Count by level
    level_counts: dict[int, int] = {}
    for lvl in levels.values():
        level_counts[lvl] = level_counts.get(lvl, 0) + 1
    by_level = [WBSLevelCount(level=lvl, count=cnt) for lvl, cnt in sorted(level_counts.items())]

    # Activities per WBS node
    act_per_wbs: dict[str, int] = {w.wbs_id: 0 for w in wbs_nodes}
    for t in schedule.activities:
        if t.wbs_id in act_per_wbs:
            act_per_wbs[t.wbs_id] += 1

    counts = list(act_per_wbs.values())
    no_activities = sum(1 for c in counts if c == 0)
    non_zero = [c for c in counts if c > 0]

    return WBSStats(
        total_elements=len(wbs_nodes),
        max_depth=max_depth,
        by_level=by_level,
        avg_activities_per_wbs=round(sum(counts) / len(counts), 1) if counts else 0.0,
        min_activities_per_wbs=min(non_zero) if non_zero else 0,
        max_activities_per_wbs=max(non_zero) if non_zero else 0,
        wbs_with_no_activities=no_activities,
    )
