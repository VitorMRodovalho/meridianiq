# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""BI connector router — flat, paginated data surfaces for Power BI / Tableau / Looker.

All endpoints return ``{items: [...], pagination: {...}}`` with limit/offset
pagination so BI tools can issue repeatable windowed queries. Rows are flat
(no nested objects) to minimise BI-side flattening logic.

Reference: PMI PMBOK 7 §4.6 (Measurement); GAO Schedule Assessment Guide.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import optional_auth
from ..deps import get_store
from ..kpi_helpers import schedule_kpi_bundle

router = APIRouter()


_MAX_LIMIT = 500
_DEFAULT_LIMIT = 100


def _paginate(
    items: list[dict],
    limit: int,
    offset: int,
) -> dict:
    total = len(items)
    window = items[offset : offset + limit]
    return {
        "items": window,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
            "returned": len(window),
            "has_next": offset + limit < total,
        },
    }


def _clamp_limit(limit: int) -> int:
    return max(1, min(_MAX_LIMIT, limit))


@router.get("/api/v1/bi/projects")
def bi_projects(
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    _user: object = Depends(optional_auth),
) -> dict:
    """Flat project list with top-level KPIs — one row per project.

    Computed fields (activity_count, relationship_count, dcma_score,
    health_score) are derived on-the-fly from the stored schedule so
    there is no staleness window. Designed as the entry-point dataset
    for BI dashboards — pivot other BI endpoints by ``project_id``.
    """
    store = get_store()
    user_id = _user["id"] if _user else None  # type: ignore[index]

    projects = store.get_projects(user_id=user_id) if hasattr(store, "get_projects") else []

    limit = _clamp_limit(limit)
    rows: list[dict] = []
    for p in projects:
        pid = p.get("project_id") or p.get("id") or ""
        row: dict = {
            "project_id": pid,
            "name": p.get("name", ""),
            "activity_count": p.get("activity_count"),
            "relationship_count": p.get("relationship_count"),
            "data_date": p.get("data_date"),
            "dcma_score": None,
            "dcma_passed_count": None,
            "dcma_failed_count": None,
            "health_score": None,
            "health_rating": None,
            "critical_path_length_days": None,
            "negative_float_count": None,
        }

        if pid:
            bundle = schedule_kpi_bundle(pid, user_id)
            for k in (
                "activity_count",
                "relationship_count",
                "dcma_score",
                "dcma_passed_count",
                "dcma_failed_count",
                "health_score",
                "health_rating",
                "critical_path_length_days",
                "negative_float_count",
            ):
                if k in bundle:
                    row[k] = bundle[k]

        rows.append(row)

    return _paginate(rows, limit, offset)


@router.get("/api/v1/bi/dcma-metrics")
def bi_dcma_metrics(
    project_id: str | None = None,
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    _user: object = Depends(optional_auth),
) -> dict:
    """One row per (project, DCMA metric) — flat pivot-ready surface.

    When ``project_id`` is passed, only that project's 14 DCMA rows are
    returned. Without it, all accessible projects are expanded (useful
    for cross-project DCMA benchmarking dashboards).

    Each row contains: project_id, project_name, metric number/name,
    value, threshold, unit, passed, direction.
    """
    store = get_store()
    user_id = _user["id"] if _user else None  # type: ignore[index]

    if project_id:
        project_list = [{"project_id": project_id, "name": ""}]
    else:
        project_list = store.get_projects(user_id=user_id) if hasattr(store, "get_projects") else []

    limit = _clamp_limit(limit)
    rows: list[dict] = []
    for p in project_list:
        pid = p.get("project_id") or p.get("id") or ""
        schedule = store.get(pid, user_id=user_id) if pid else None
        if schedule is None:
            continue
        try:
            from src.analytics.dcma14 import DCMA14Analyzer

            result = DCMA14Analyzer(schedule).analyze()
        except Exception:
            continue

        for m in result.metrics:
            rows.append(
                {
                    "project_id": pid,
                    "project_name": p.get("name", ""),
                    "metric_number": m.number,
                    "metric_name": m.name,
                    "value": m.value,
                    "threshold": m.threshold,
                    "unit": m.unit,
                    "passed": m.passed,
                    "direction": m.direction,
                    "description": m.description,
                }
            )

    if project_id and not rows:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    return _paginate(rows, limit, offset)


@router.get("/api/v1/bi/activities")
def bi_activities(
    project_id: str,
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    _user: object = Depends(optional_auth),
) -> dict:
    """Flat activity list — one row per activity with CPM-derived metrics.

    Surfaces fields BI tools commonly need: code, name, type, status,
    durations, dates, total/free float, criticality, WBS code.
    """
    store = get_store()
    user_id = _user["id"] if _user else None  # type: ignore[index]

    schedule = store.get(project_id, user_id=user_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    limit = _clamp_limit(limit)

    cpm_results: dict = {}
    project_duration = 0.0
    try:
        from src.analytics.cpm import CPMCalculator

        cpm = CPMCalculator(schedule).calculate()
        cpm_results = cpm.activity_results
        project_duration = cpm.project_duration
    except Exception:
        pass

    rows: list[dict] = []
    for a in schedule.activities:
        ar = cpm_results.get(a.task_id)
        rows.append(
            {
                "project_id": project_id,
                "task_id": a.task_id,
                "task_code": a.task_code,
                "task_name": a.task_name,
                "task_type": a.task_type,
                "status_code": a.status_code,
                "wbs_id": a.wbs_id,
                "target_duration_hours": a.target_drtn_hr_cnt,
                "remaining_duration_hours": a.remain_drtn_hr_cnt,
                "total_float_hours": a.total_float_hr_cnt,
                "act_start_date": a.act_start_date.isoformat() if a.act_start_date else None,
                "act_end_date": a.act_end_date.isoformat() if a.act_end_date else None,
                "early_start_date": (
                    a.early_start_date.isoformat() if a.early_start_date else None
                ),
                "early_end_date": a.early_end_date.isoformat() if a.early_end_date else None,
                "late_start_date": (a.late_start_date.isoformat() if a.late_start_date else None),
                "late_end_date": a.late_end_date.isoformat() if a.late_end_date else None,
                "cpm_total_float": ar.total_float if ar else None,
                "cpm_free_float": ar.free_float if ar else None,
                "is_critical": ar.is_critical if ar else None,
            }
        )

    paginated = _paginate(rows, limit, offset)
    paginated["project_id"] = project_id
    paginated["project_duration_days"] = round(project_duration, 2)
    return paginated
