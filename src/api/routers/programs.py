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
