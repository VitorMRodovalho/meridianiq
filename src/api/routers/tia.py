# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""TIA (Time Impact Analysis) router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from src.analytics.tia import (
    DelayFragment,
    FragmentActivity,
    ResponsibleParty,
    TimeImpactAnalyzer,
)

from ..auth import optional_auth
from ..deps import RATE_LIMIT_MODERATE, get_store, get_tia_store, limiter
from ..schemas import (
    DelayFragmentSchema,
    FragmentActivitySchema,
    TIAAnalysisSchema,
    TIAAnalysisSummarySchema,
    TIAAnalyzeRequest,
    TIAListResponse,
    TIAResultSchema,
    TIASummaryResponse,
)

router = APIRouter()


def _fragment_schema_to_model(schema: DelayFragmentSchema) -> DelayFragment:
    """Convert a DelayFragmentSchema to a DelayFragment dataclass.

    Args:
        schema: The Pydantic schema from the request body.

    Returns:
        A ``DelayFragment`` dataclass instance.
    """
    activities = [
        FragmentActivity(
            fragment_activity_id=a.fragment_activity_id,
            name=a.name,
            duration_hours=a.duration_hours,
            predecessors=a.predecessors,
            successors=a.successors,
        )
        for a in schema.activities
    ]

    return DelayFragment(
        fragment_id=schema.fragment_id,
        name=schema.name,
        description=schema.description,
        responsible_party=ResponsibleParty(schema.responsible_party),
        activities=activities,
    )


def _analysis_to_schema(analysis: Any) -> TIAAnalysisSchema:
    """Convert a TIAAnalysis dataclass to its Pydantic schema.

    Args:
        analysis: A ``TIAAnalysis`` instance.

    Returns:
        A ``TIAAnalysisSchema`` for JSON serialisation.
    """
    fragment_schemas = [
        DelayFragmentSchema(
            fragment_id=f.fragment_id,
            name=f.name,
            description=f.description,
            responsible_party=f.responsible_party.value,
            activities=[
                FragmentActivitySchema(
                    fragment_activity_id=a.fragment_activity_id,
                    name=a.name,
                    duration_hours=a.duration_hours,
                    predecessors=a.predecessors,
                    successors=a.successors,
                )
                for a in f.activities
            ],
        )
        for f in analysis.fragments
    ]

    result_schemas = [
        TIAResultSchema(
            fragment_id=r.fragment.fragment_id,
            fragment_name=r.fragment.name,
            responsible_party=r.fragment.responsible_party.value,
            unimpacted_completion_days=r.unimpacted_completion_days,
            impacted_completion_days=r.impacted_completion_days,
            delay_days=r.delay_days,
            critical_path_affected=r.critical_path_affected,
            float_consumed_hours=r.float_consumed_hours,
            delay_type=r.delay_type.value,
            concurrent_with=r.concurrent_with,
            impacted_driving_path=r.impacted_driving_path,
        )
        for r in analysis.results
    ]

    return TIAAnalysisSchema(
        analysis_id=analysis.analysis_id,
        project_name=analysis.project_name,
        base_project_id=analysis.base_project_id,
        fragments=fragment_schemas,
        results=result_schemas,
        total_owner_delay=analysis.total_owner_delay,
        total_contractor_delay=analysis.total_contractor_delay,
        total_shared_delay=analysis.total_shared_delay,
        net_delay=analysis.net_delay,
        summary=analysis.summary,
    )


@router.post("/api/v1/tia/analyze", response_model=TIAAnalysisSchema)
@limiter.limit(RATE_LIMIT_MODERATE)
def tia_analyze(
    request: Request,
    body: TIAAnalyzeRequest,
    _user: object = Depends(optional_auth),
) -> TIAAnalysisSchema:
    """Run Time Impact Analysis on a project with delay fragments.

    Per AACE RP 52R-06, inserts each fragment into the schedule network,
    runs CPM, and measures the impact on the project completion date.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: Contains project_id and fragment definitions.

    Raises:
        HTTPException: If the project is not found or analysis fails.
    """
    store = get_store()
    tia_store = get_tia_store()

    schedule = store.get(body.project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {body.project_id}")

    # Convert schemas to domain models
    fragments = [_fragment_schema_to_model(f) for f in body.fragments]

    try:
        analyzer = TimeImpactAnalyzer(schedule)
        analysis = analyzer.analyze_all(fragments)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TIA analysis failed: {exc}")

    tia_store.add(analysis)
    return _analysis_to_schema(analysis)


@router.get("/api/v1/tia/analyses", response_model=TIAListResponse)
def list_tia_analyses(_user: object = Depends(optional_auth)) -> TIAListResponse:
    """List all TIA analyses."""
    tia_store = get_tia_store()
    items = [TIAAnalysisSummarySchema(**a) for a in tia_store.list_all()]
    return TIAListResponse(analyses=items)


@router.get(
    "/api/v1/tia/analyses/{analysis_id}",
    response_model=TIAAnalysisSchema,
)
def get_tia_analysis(analysis_id: str, _user: object = Depends(optional_auth)) -> TIAAnalysisSchema:
    """Get full TIA analysis with all fragment results.

    Args:
        analysis_id: The stored analysis identifier.

    Raises:
        HTTPException: If the analysis is not found.
    """
    tia_store = get_tia_store()
    analysis = tia_store.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="TIA analysis not found")

    return _analysis_to_schema(analysis)


@router.get(
    "/api/v1/tia/analyses/{analysis_id}/summary",
    response_model=TIASummaryResponse,
)
def get_tia_summary(analysis_id: str, _user: object = Depends(optional_auth)) -> TIASummaryResponse:
    """Get delay-by-responsibility summary for a TIA analysis.

    Args:
        analysis_id: The stored analysis identifier.

    Raises:
        HTTPException: If the analysis is not found.
    """
    tia_store = get_tia_store()
    analysis = tia_store.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="TIA analysis not found")

    return TIASummaryResponse(
        analysis_id=analysis.analysis_id,
        total_owner_delay=analysis.total_owner_delay,
        total_contractor_delay=analysis.total_contractor_delay,
        total_shared_delay=analysis.total_shared_delay,
        net_delay=analysis.net_delay,
        summary=analysis.summary,
    )
