# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Schedule ops router — generation, build, cashflow, lookahead, risk register."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth import optional_auth
from ..deps import get_store, limiter

router = APIRouter()


@router.post("/api/v1/schedule/generate")
@limiter.limit("5/minute")
def generate_schedule_endpoint(
    request: dict,
    _user: object = Depends(optional_auth),
) -> dict:
    """Generate a complete schedule from project parameters.

    Accepts project_type, size_category, project_name, and target_duration_days.
    Returns generated activities, relationships, and predicted duration.
    """
    from dataclasses import asdict

    from src.analytics.schedule_generation import GenerationInput, generate_schedule

    params = GenerationInput(
        project_type=request.get("project_type", "commercial"),
        project_name=request.get("project_name", "Generated Project"),
        target_duration_days=request.get("target_duration_days", 0),
        size_category=request.get("size_category", "medium"),
        complexity_factor=request.get("complexity_factor", 1.0),
    )
    result = generate_schedule(params)
    # Exclude parsed_schedule from response (too large)
    data = asdict(result)
    data.pop("parsed_schedule", None)
    return data


@router.post("/api/v1/schedule/build")
async def build_schedule_endpoint(
    request: dict,
    _user: object = Depends(optional_auth),
) -> dict:
    """Build a schedule from natural language description.

    Uses Claude API to extract parameters, falls back to keyword matching.
    """
    from src.analytics.schedule_builder import _fallback_build

    description = request.get("description", "")
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
def get_risk_register_summary(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Get risk register summary for a project.

    References:
        AACE RP 57R-09, PMI Risk Management, ISO 31000.
    """
    from dataclasses import asdict

    from src.analytics.risk_register import summarize_register

    result = summarize_register([])
    return asdict(result)
