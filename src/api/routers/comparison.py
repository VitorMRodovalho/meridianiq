# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Comparison router — compare two uploaded schedules (baseline vs update)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request

from src.analytics.comparison import ScheduleComparison

from ..auth import optional_auth
from ..deps import RATE_LIMIT_ANALYSIS, get_store, limiter
from ..schemas import (
    ActivityChangeSchema,
    CodeRestructuringSchema,
    CompareRequest,
    CompareResponse,
    FloatChangeSchema,
    ManipulationFlagSchema,
    MatchStatsSchema,
    RelationshipChangeSchema,
)

router = APIRouter()


@router.post("/api/v1/compare", response_model=CompareResponse)
@limiter.limit(RATE_LIMIT_ANALYSIS)
def compare_schedules(
    request: Request,
    body: CompareRequest,
    _user: object = Depends(optional_auth),
) -> CompareResponse:
    """Compare two uploaded projects (baseline vs update).

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: Contains baseline_id and update_id.

    Raises:
        HTTPException: If either project is not found.
    """
    store = get_store()

    baseline = store.get(body.baseline_id)
    if baseline is None:
        raise HTTPException(
            status_code=404, detail=f"Baseline project not found: {body.baseline_id}"
        )

    update = store.get(body.update_id)
    if update is None:
        raise HTTPException(status_code=404, detail=f"Update project not found: {body.update_id}")

    comparison = ScheduleComparison(baseline, update)
    result = comparison.compare()

    return CompareResponse(
        activities_added=[ActivityChangeSchema(**asdict(c)) for c in result.activities_added],
        activities_deleted=[ActivityChangeSchema(**asdict(c)) for c in result.activities_deleted],
        activity_modifications=[
            ActivityChangeSchema(**asdict(c)) for c in result.activity_modifications
        ],
        duration_changes=[ActivityChangeSchema(**asdict(c)) for c in result.duration_changes],
        relationships_added=[
            RelationshipChangeSchema(**asdict(c)) for c in result.relationships_added
        ],
        relationships_deleted=[
            RelationshipChangeSchema(**asdict(c)) for c in result.relationships_deleted
        ],
        relationships_modified=[
            RelationshipChangeSchema(**asdict(c)) for c in result.relationships_modified
        ],
        significant_float_changes=[
            FloatChangeSchema(**asdict(c)) for c in result.significant_float_changes
        ],
        constraint_changes=[ActivityChangeSchema(**asdict(c)) for c in result.constraint_changes],
        manipulation_flags=[ManipulationFlagSchema(**asdict(c)) for c in result.manipulation_flags],
        code_restructuring=[
            CodeRestructuringSchema(**asdict(c)) for c in result.code_restructuring
        ],
        match_stats=MatchStatsSchema(**asdict(result.match_stats)),
        changed_percentage=result.changed_percentage,
        critical_path_changed=result.critical_path_changed,
        activities_joined_cp=result.activities_joined_cp,
        activities_left_cp=result.activities_left_cp,
        # The engine computes the aggregate verdict in
        # ScheduleComparator._score_manipulation; these three were never mapped,
        # so the response served the schema defaults (0 / "normal" / "") while
        # `manipulation_flags` carried critical retroactive_date findings. The UI
        # rendered "Risk Score 0 — no manipulation indicators" directly above
        # them, which is the worst possible screen for the forensic persona.
        manipulation_classification=result.manipulation_classification,
        manipulation_score=result.manipulation_score,
        manipulation_rationale=result.manipulation_rationale,
        summary=result.summary,
    )
