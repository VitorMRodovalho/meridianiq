# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Schedule ops router — generation, build, cashflow, lookahead, risk register."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import optional_auth
from ..deps import RATE_LIMIT_EXPENSIVE, RATE_LIMIT_MODERATE, RATE_LIMIT_WRITE, get_store, limiter

router = APIRouter()


@router.post("/api/v1/schedule/generate")
@limiter.limit(RATE_LIMIT_WRITE)
def generate_schedule_endpoint(
    request: Request,
    body: dict,
    _user: object = Depends(optional_auth),
) -> dict:
    """Generate a complete schedule from project parameters.

    Accepts project_type, size_category, project_name, and target_duration_days.
    Returns generated activities, relationships, and predicted duration.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: Free-form dict with project_type, size_category, project_name,
            target_duration_days, complexity_factor.
    """
    from dataclasses import asdict

    from src.analytics.schedule_generation import GenerationInput, generate_schedule

    params = GenerationInput(
        project_type=body.get("project_type", "commercial"),
        project_name=body.get("project_name", "Generated Project"),
        target_duration_days=body.get("target_duration_days", 0),
        size_category=body.get("size_category", "medium"),
        complexity_factor=body.get("complexity_factor", 1.0),
    )
    result = generate_schedule(params)
    # Exclude parsed_schedule from response (too large)
    data = asdict(result)
    data.pop("parsed_schedule", None)
    return data


@router.post("/api/v1/schedule/build")
@limiter.limit(RATE_LIMIT_EXPENSIVE)
async def build_schedule_endpoint(
    request: Request,
    body: dict,
    _user: object = Depends(optional_auth),
) -> dict:
    """Build a schedule from natural language description.

    Uses Claude API to extract parameters, falls back to keyword matching.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: Free-form dict with a ``description`` key (natural language).
    """
    from src.analytics.schedule_builder import _fallback_build

    description = body.get("description", "")
    if not description:
        raise HTTPException(status_code=400, detail="Description required")

    result = _fallback_build(description)
    return result.summary


@router.get("/api/v1/projects/{project_id}/cashflow")
def get_cashflow(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Get cash flow analysis with S-Curve data.

    Distributes costs across timeline using CPM dates and TaskResource costs.

    References:
        AACE RP 10S-90, PMI Practice Standard for EVM.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from dataclasses import asdict

    from src.analytics.cashflow import analyze_cashflow

    result = analyze_cashflow(schedule)
    return asdict(result)


@router.get("/api/v1/projects/{project_id}/lookahead")
def get_lookahead(
    project_id: str,
    weeks: int = 2,
    _user: object = Depends(optional_auth),
) -> dict:
    """Get look-ahead schedule for the next N weeks.

    Filters activities starting, finishing, or active within the window.

    References:
        PMI Practice Standard for Scheduling, Lean Construction LPS.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from dataclasses import asdict

    from src.analytics.lookahead import generate_lookahead

    result = generate_lookahead(schedule, weeks=weeks)
    return asdict(result)


@router.get("/api/v1/projects/{project_id}/risk-register")
def get_risk_register(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """List risk register entries plus summary statistics for a project.

    Returns both the persisted entries and an aggregated
    ``RiskRegisterSummary`` (counts, expected values, risk score).

    References:
        AACE RP 57R-09, PMI Risk Management, ISO 31000.
    """
    from dataclasses import asdict

    from src.analytics.risk_register import RiskEntry, summarize_register

    store = get_store()
    user_id = _user["id"] if _user else None  # type: ignore[index]

    raw_entries = (
        store.list_risk_entries(project_id, user_id=user_id)
        if hasattr(store, "list_risk_entries")
        else []
    )

    register_entries = [
        RiskEntry(
            risk_id=e.get("risk_id", ""),
            name=e.get("name", ""),
            description=e.get("description", ""),
            category=e.get("category", "schedule"),
            probability=float(e.get("probability", 0.0) or 0.0),
            impact_days=float(e.get("impact_days", 0.0) or 0.0),
            impact_cost=float(e.get("impact_cost", 0.0) or 0.0),
            status=e.get("status", "open"),
            responsible_party=e.get("responsible_party", ""),
            mitigation=e.get("mitigation", ""),
            affected_activities=list(e.get("affected_activities") or []),
        )
        for e in raw_entries
    ]

    summary = summarize_register(register_entries)
    return {
        "project_id": project_id,
        "entries": raw_entries,
        "summary": asdict(summary),
    }


@router.post("/api/v1/projects/{project_id}/risk-register")
@limiter.limit(RATE_LIMIT_MODERATE)
def add_risk_register_entry(
    request: Request,
    project_id: str,
    body: dict,
    _user: object = Depends(optional_auth),
) -> dict:
    """Create or upsert a risk register entry for a project.

    If ``risk_id`` is missing it is auto-assigned (``R001``, ``R002``, …).
    Re-posting an existing ``risk_id`` replaces that record.
    """
    store = get_store()
    user_id = _user["id"] if _user else None  # type: ignore[index]

    if not hasattr(store, "save_risk_entry"):
        raise HTTPException(
            status_code=501,
            detail="Risk register persistence not supported by this backend",
        )

    stored = store.save_risk_entry(project_id, body, user_id=user_id)
    return {"project_id": project_id, "entry": stored}


@router.delete("/api/v1/projects/{project_id}/risk-register/{risk_id}")
@limiter.limit(RATE_LIMIT_MODERATE)
def delete_risk_register_entry(
    request: Request,
    project_id: str,
    risk_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Remove a risk register entry."""
    store = get_store()
    user_id = _user["id"] if _user else None  # type: ignore[index]

    if not hasattr(store, "delete_risk_entry"):
        raise HTTPException(
            status_code=501,
            detail="Risk register persistence not supported by this backend",
        )

    ok = store.delete_risk_entry(project_id, risk_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Risk {risk_id} not found")
    return {"project_id": project_id, "risk_id": risk_id, "deleted": True}
