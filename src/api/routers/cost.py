# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Cost router — CBS upload, trends, narrative, float entropy, constraint accumulation."""

from __future__ import annotations

import tempfile
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from ..auth import optional_auth
from ..deps import RATE_LIMIT_MODERATE, RATE_LIMIT_WRITE, get_store, limiter

router = APIRouter()


@router.post("/api/v1/cost/upload")
@limiter.limit(RATE_LIMIT_WRITE)
async def upload_cost_data(
    request: Request,
    file: UploadFile = File(...),
    project_id: str | None = None,
    _user: object = Depends(optional_auth),
) -> dict:
    """Upload a CBS Excel file, parse, and persist as a cost snapshot.

    Returns CBS hierarchy, WBS budgets, CBS-WBS mappings, and (when
    ``project_id`` is provided) a ``snapshot_id`` that can be used to
    list prior uploads via ``GET /projects/{id}/cost/snapshots``.

    Reference: AACE RP 10S-90 — Cost Engineering Terminology.
    """
    filename = (file.filename or "").lower()
    if not filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Upload an Excel file (.xlsx)")

    file_bytes = await file.read()
    if not file_bytes or len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File empty or too large (max 50MB)")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        from src.analytics.cost_integration import parse_cbs_excel

        result = parse_cbs_excel(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)

    snapshot_id = ""
    if project_id:
        store = get_store()
        user_id = _user["id"] if _user else None  # type: ignore[index]
        snapshot_id = store.save_cost_upload(
            project_id=project_id,
            result=result,
            user_id=user_id,
            source_name=file.filename or "CBS Upload",
        )

    return {
        "filename": file.filename,
        "snapshot_id": snapshot_id,
        "project_id": project_id,
        "budget_date": result.budget_date,
        "total_budget": result.total_budget,
        "total_contingency": result.total_contingency,
        "total_escalation": result.total_escalation,
        "program_total": result.program_total,
        "cbs_element_count": len(result.cbs_elements),
        "wbs_budget_count": len(result.wbs_budgets),
        "mapping_count": len(result.cbs_wbs_mappings),
        "insights": result.insights,
        "cbs_elements": [
            {
                "cbs_code": e.cbs_code,
                "cbs_level1": e.cbs_level1,
                "cbs_level2": e.cbs_level2,
                "scope": e.scope,
                "wbs_code": e.wbs_code,
                "estimate": e.estimate,
                "contingency": e.contingency,
                "budget": e.budget,
            }
            for e in result.cbs_elements
        ],
        "wbs_budgets": [
            {"wbs_code": w.wbs_code, "total_budget": w.total_budget} for w in result.wbs_budgets
        ],
        "cbs_wbs_mappings": [
            {
                "cost_category": m.cost_category,
                "cbs_code": m.cbs_code,
                "wbs_level1": m.wbs_level1,
                "notes": m.notes,
            }
            for m in result.cbs_wbs_mappings
        ],
    }


@router.get("/api/v1/projects/{project_id}/cost/snapshots")
def list_cost_snapshots(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """List all persisted CBS cost snapshots for a project (newest first).

    Each snapshot corresponds to one CBS upload and contains summary
    totals (budget, contingency, element count). Returns an empty list
    if no uploads exist or the backend does not support persistence.
    """
    store = get_store()
    user_id = _user["id"] if _user else None  # type: ignore[index]
    snapshots = store.list_cost_snapshots(project_id, user_id=user_id)
    return {"project_id": project_id, "count": len(snapshots), "snapshots": snapshots}


@router.get("/api/v1/projects/{project_id}/cost/compare")
def compare_cost_snapshots_endpoint(
    project_id: str,
    a: str,
    b: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Compare two persisted CBS cost snapshots element-by-element.

    Requires both snapshot ids to resolve via ``get_cost_snapshot``.
    Returns totals delta, per-CBS variance, and interpretation insights.

    Reference: AACE RP 10S-90 — Cost Engineering Terminology;
               AACE RP 29R-03 §5.3 — variance documentation.
    """
    if a == b:
        raise HTTPException(status_code=400, detail="Snapshot ids a and b must differ")

    store = get_store()
    user_id = _user["id"] if _user else None  # type: ignore[index]

    snap_a = store.get_cost_snapshot(project_id, a, user_id=user_id)
    snap_b = store.get_cost_snapshot(project_id, b, user_id=user_id)

    if snap_a is None or snap_b is None:
        missing = []
        if snap_a is None:
            missing.append(a)
        if snap_b is None:
            missing.append(b)
        raise HTTPException(
            status_code=404,
            detail=f"Snapshot(s) not found for this project: {', '.join(missing)}",
        )

    from src.analytics.cost_integration import compare_cost_snapshots

    result = compare_cost_snapshots(snap_a, snap_b, snapshot_a_id=a, snapshot_b_id=b)
    return {"project_id": project_id, **asdict(result)}


@router.post("/api/v1/trends")
@limiter.limit(RATE_LIMIT_MODERATE)
def get_schedule_trends(
    request: Request,
    body: dict,
    _user: object = Depends(optional_auth),
) -> dict:
    """Compute schedule trends across multiple project updates.

    Accepts a list of project IDs representing sequential schedule updates.
    Returns trend data points and insights.

    Reference: AACE RP 29R-03 — Forensic Schedule Analysis.
    """
    project_ids: list[str] = body.get("project_ids", [])
    if not project_ids:
        raise HTTPException(status_code=400, detail="project_ids required")
    if len(project_ids) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 projects per trend")

    include_scorecard: bool = body.get("include_scorecard", False)

    from src.analytics.schedule_metadata import extract_metadata
    from src.analytics.schedule_trends import analyze_trends, compute_trend_point

    store = get_store()
    user_id = _user["id"] if _user else None

    points = []
    for pid in project_ids:
        schedule = store.get(pid, user_id=user_id)
        if schedule is None:
            continue
        meta = extract_metadata(
            filename="",
            project_name=schedule.projects[0].proj_short_name if schedule.projects else "",
        )
        point = compute_trend_point(schedule, pid, update_number=meta.update_number)

        if include_scorecard:
            try:
                from src.analytics.scorecard import calculate_scorecard

                sc = calculate_scorecard(schedule)
                point.quality_score = sc.overall_score
                point.quality_grade = sc.overall_grade
            except Exception:
                pass  # Skip if scorecard fails

        points.append(point)

    result = analyze_trends(points)
    return {
        "series_name": result.series_name,
        "point_count": len(result.points),
        "insights": result.insights,
        "points": [
            {
                "project_id": p.project_id,
                "project_name": p.project_name,
                "data_date": p.data_date,
                "update_number": p.update_number,
                "activity_count": p.activity_count,
                "relationship_count": p.relationship_count,
                "wbs_count": p.wbs_count,
                "milestone_count": p.milestone_count,
                "complete_count": p.complete_count,
                "active_count": p.active_count,
                "not_started_count": p.not_started_count,
                "complete_pct": p.complete_pct,
                "avg_total_float": p.avg_total_float,
                "negative_float_count": p.negative_float_count,
                "zero_float_count": p.zero_float_count,
                "critical_count": p.critical_count,
                "near_critical_count": p.near_critical_count,
                "logic_density": p.logic_density,
                "constraint_count": p.constraint_count,
                "loe_count": p.loe_count,
                "project_duration_days": p.project_duration_days,
                "quality_score": p.quality_score,
                "quality_grade": p.quality_grade or None,
            }
            for p in result.points
        ],
    }


@router.get("/api/v1/projects/{project_id}/narrative")
def get_narrative_report(
    project_id: str,
    baseline_id: str | None = None,
    _user: object = Depends(optional_auth),
) -> dict:
    """Generate a narrative schedule status report.

    Combines schedule metrics, scorecard, and optional comparison into
    structured text sections for claims documentation or status reports.

    Reference: AACE RP 29R-03 — Forensic Schedule Analysis.
    """
    from dataclasses import asdict as _asdict

    from src.analytics.comparison import ScheduleComparison
    from src.analytics.narrative_report import generate_schedule_narrative
    from src.analytics.schedule_view import build_schedule_view
    from src.analytics.scorecard import calculate_scorecard

    store = get_store()
    user_id = _user["id"] if _user else None
    schedule = store.get(project_id, user_id=user_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build schedule view for summary
    view = build_schedule_view(schedule)

    # Scorecard
    scorecard_data = None
    try:
        sc = calculate_scorecard(schedule)
        scorecard_data = _asdict(sc)
    except Exception:
        pass

    # Comparison (if baseline provided)
    comparison_data = None
    if baseline_id:
        baseline = store.get(baseline_id, user_id=user_id)
        if baseline:
            try:
                comp = ScheduleComparison(baseline, schedule)
                comparison_data = comp.compare()
            except Exception:
                pass

    report = generate_schedule_narrative(
        project_name=view.project_name,
        data_date=view.data_date,
        summary=view.summary,
        scorecard=scorecard_data,
        comparison=comparison_data,
    )

    return {
        "title": report.title,
        "project_name": report.project_name,
        "data_date": report.data_date,
        "generated_at": report.generated_at,
        "executive_summary": report.executive_summary,
        "sections": [
            {
                "title": s.title,
                "content": s.content,
                "severity": s.severity,
            }
            for s in report.sections
        ],
    }


@router.get("/api/v1/projects/{project_id}/float-entropy")
def get_float_entropy(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Compute Shannon entropy of float distribution.

    Measures how uniformly total float is spread across predefined
    buckets.  Low entropy indicates float concentrated in few categories
    (potentially unreliable); high entropy indicates even distribution.

    No baseline required — operates on a single schedule snapshot.

    Args:
        project_id: The stored project identifier.

    Returns:
        FloatEntropyResult as dict with entropy, normalised_entropy,
        distribution, and interpretation.

    Raises:
        HTTPException: If the project is not found.

    References:
        Shannon (1948) — A Mathematical Theory of Communication.
        AACE RP 49R-06 — Identifying Critical Activities.
    """
    from src.analytics.float_trends import compute_float_entropy

    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = compute_float_entropy(schedule)
    return asdict(result)


@router.get("/api/v1/projects/{project_id}/constraint-accumulation")
def get_constraint_accumulation(
    project_id: str,
    baseline_id: str | None = None,
    _user: object = Depends(optional_auth),
) -> dict:
    """Compute constraint accumulation rate between two schedule versions.

    Measures the rate at which hard constraints are being added.
    Excessive constraint growth is a schedule manipulation indicator
    per DCMA check #10 and AACE RP 29R-03.

    Args:
        project_id: The update project identifier.
        baseline_id: The baseline project identifier (required).

    Returns:
        ConstraintAccumulationResult as dict.

    Raises:
        HTTPException: If projects are not found or baseline_id missing.

    References:
        DCMA 14-Point Assessment — Check #10 (Hard Constraints).
        AACE RP 29R-03 — Schedule manipulation detection.
    """
    from src.analytics.float_trends import compute_constraint_accumulation

    store = get_store()
    update = store.get(project_id)
    if update is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if not baseline_id:
        raise HTTPException(
            status_code=400,
            detail="baseline_id query parameter is required for constraint accumulation",
        )

    baseline = store.get(baseline_id)
    if baseline is None:
        raise HTTPException(status_code=404, detail="Baseline project not found")

    result = compute_constraint_accumulation(baseline, update)
    return asdict(result)
