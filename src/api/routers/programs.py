# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Programs router — group uploads under programs with revision tracking."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth import optional_auth
from ..deps import get_store

router = APIRouter()


@router.get("/api/v1/programs")
def list_programs(_user: object = Depends(optional_auth)):
    """Return all programs with latest revision info."""
    store = get_store()
    user_id = _user["id"] if _user else None
    programs = store.get_programs(user_id=user_id)
    return {"programs": programs}


@router.get("/api/v1/programs/{program_id}")
def get_program_detail(program_id: str, _user: object = Depends(optional_auth)):
    """Return a program with all its revisions."""
    store = get_store()
    user_id = _user["id"] if _user else None
    revisions = store.get_program_revisions(program_id, user_id=user_id)
    # Also get the program metadata
    programs = store.get_programs(user_id=user_id)
    program = None
    for p in programs:
        if p["id"] == program_id:
            program = p
            break
    if program is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return {"program": program, "revisions": revisions}


@router.put("/api/v1/programs/{program_id}")
def update_program(program_id: str, body: dict, _user: object = Depends(optional_auth)):
    """Rename or update a program."""
    store = get_store()
    user_id = _user["id"] if _user else None
    updated = store.update_program(program_id, body, user_id=user_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return {"program": updated}


def _build_rollup(
    store, program_id: str, revisions: list[dict], user_id: str | None = None
) -> dict:
    """Build the program rollup payload from a revisions list.

    Extracted so both the HTTP endpoint and other callers (exec-summary
    PDF enrichment) can reuse the same computation path.
    """
    revisions.sort(key=lambda r: r.get("revision_number", 0), reverse=True)
    latest = revisions[0]
    prev = revisions[1] if len(revisions) > 1 else None

    latest_metrics: dict = {
        "activity_count": latest.get("activity_count"),
        "revision_number": latest.get("revision_number"),
        "data_date": latest.get("data_date"),
    }

    latest_schedule = store.get(latest["id"], user_id=user_id)
    if latest_schedule is not None:
        latest_metrics["activity_count"] = len(latest_schedule.activities)
        latest_metrics["relationship_count"] = len(latest_schedule.relationships)

        try:
            from src.analytics.cpm import CPMCalculator

            cpm = CPMCalculator(latest_schedule).calculate()
            latest_metrics["critical_path_length_days"] = round(cpm.project_duration, 2)
            latest_metrics["critical_activities_count"] = len(cpm.critical_path)
            latest_metrics["has_cycles"] = cpm.has_cycles
            latest_metrics["negative_float_count"] = sum(
                1 for ar in cpm.activity_results.values() if ar.total_float < 0
            )
        except Exception:
            pass

        try:
            from src.analytics.dcma14 import DCMA14Analyzer

            dcma = DCMA14Analyzer(latest_schedule).analyze()
            latest_metrics["dcma_score"] = round(dcma.overall_score, 1)
            latest_metrics["dcma_passed_count"] = dcma.passed_count
            latest_metrics["dcma_failed_count"] = dcma.failed_count
        except Exception:
            pass

        try:
            from src.analytics.health_score import HealthScoreCalculator

            health = HealthScoreCalculator(latest_schedule).calculate()
            latest_metrics["health_score"] = round(health.overall, 1)
            latest_metrics["health_rating"] = health.rating
            latest_metrics["health_trend_arrow"] = health.trend_arrow
        except Exception:
            pass

    trend_direction = "stable"
    trend_delta: float | None = None
    if prev and "health_score" in latest_metrics:
        prev_schedule = store.get(prev["id"], user_id=user_id)
        if prev_schedule is not None:
            try:
                from src.analytics.health_score import HealthScoreCalculator

                prev_health = HealthScoreCalculator(prev_schedule).calculate()
                trend_delta = round(latest_metrics["health_score"] - prev_health.overall, 1)
                if trend_delta > 2:
                    trend_direction = "improving"
                elif trend_delta < -2:
                    trend_direction = "degrading"
            except Exception:
                pass

    return {
        "program_id": program_id,
        "revision_count": len(revisions),
        "latest_revision_id": latest["id"],
        "latest_revision_number": latest.get("revision_number"),
        "latest_data_date": latest.get("data_date"),
        "latest_metrics": latest_metrics,
        "trend_direction": trend_direction,
        "trend_delta": trend_delta,
        "previous_revision_id": prev["id"] if prev else None,
        "previous_revision_number": prev.get("revision_number") if prev else None,
    }


def compute_program_rollup(program_id: str, user_id: str | None = None) -> dict | None:
    """Return a rollup dict for a program, or None when it has no revisions.

    Plain-callable version of the /rollup endpoint so other reports (e.g.
    executive summary PDF) can embed rollup context without going through
    ``Depends(optional_auth)``.
    """
    store = get_store()
    revisions = (
        store.get_program_revisions(program_id, user_id)
        if hasattr(store, "get_program_revisions")
        else []
    )
    if not revisions:
        return None
    return _build_rollup(store, program_id, revisions, user_id=user_id)


@router.get("/api/v1/programs/{program_id}/rollup")
def get_program_rollup(program_id: str, _user: object = Depends(optional_auth)):
    """Aggregated KPIs across a program's revisions.

    Computes CPM + DCMA + health on the latest revision and compares its
    health score against the previous revision for trend direction. Gives
    Program Directors a one-call summary (CP length, negative float,
    DCMA score, health + trend) without drilling into each revision.

    Reference: DCMA 14-Point Assessment; AACE RP 29R-03.
    """
    store = get_store()
    user_id = _user["id"] if _user else None  # type: ignore[index]

    revisions = (
        store.get_program_revisions(program_id, user_id)
        if hasattr(store, "get_program_revisions")
        else []
    )
    if not revisions:
        raise HTTPException(status_code=404, detail="Program not found or no revisions")

    return _build_rollup(store, program_id, revisions, user_id=user_id)


@router.get("/api/v1/programs/{program_id}/trends")
def get_program_trends(program_id: str, _user: object = Depends(optional_auth)):
    """Trend data across all revisions for charting."""
    store = get_store()
    user_id = _user["id"] if _user else None
    revisions = (
        store.get_program_revisions(program_id, user_id)
        if hasattr(store, "get_program_revisions")
        else []
    )
    if not revisions:
        raise HTTPException(status_code=404, detail="Program not found or no revisions")

    # Sort ascending by revision_number
    revisions.sort(key=lambda r: r.get("revision_number", 0))

    trends: dict = {
        "revision_count": len(revisions),
        "labels": [],
        "health_scores": [],
        "dcma_scores": [],
        "alert_counts": [],
        "activity_counts": [],
        "revisions": [],
    }

    for rev in revisions:
        results = rev.get("analysis_results") or {}
        health = results.get("health", {})
        dcma = results.get("dcma", {})
        alerts = results.get("alerts", {})

        label = rev.get("data_date") or f"Rev {rev.get('revision_number', '?')}"
        trends["labels"].append(str(label))
        trends["health_scores"].append(health.get("score") if health else None)
        dcma_score = dcma.get("score") if dcma else None
        if dcma_score is None and dcma:
            dcma_score = dcma.get("pass_rate")
        trends["dcma_scores"].append(dcma_score)
        if alerts and isinstance(alerts.get("alerts"), list):
            trends["alert_counts"].append(len(alerts["alerts"]))
        elif alerts:
            trends["alert_counts"].append(alerts.get("count", 0))
        else:
            trends["alert_counts"].append(None)
        trends["activity_counts"].append(rev.get("activity_count"))
        trends["revisions"].append(
            {
                "id": rev.get("id"),
                "revision_number": rev.get("revision_number"),
                "data_date": rev.get("data_date"),
                "filename": rev.get("filename"),
            }
        )

    return trends
