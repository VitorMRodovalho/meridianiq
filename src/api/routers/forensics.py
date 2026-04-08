# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Forensic Analysis (CPA / Window Analysis) router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.analytics.forensics import ForensicAnalyzer
from src.analytics.half_step import analyze_half_step
from src.parser.models import ParsedSchedule

from ..auth import optional_auth
from ..deps import get_store, get_timeline_store
from ..schemas import (
    CreateTimelineRequest,
    DelayTrendPoint,
    DelayTrendResponse,
    HalfStepRequest,
    HalfStepResponse,
    TimelineDetailSchema,
    TimelineListResponse,
    TimelineSummarySchema,
    WindowSchema,
)

router = APIRouter()


def _window_to_schema(wr: Any) -> WindowSchema:
    """Convert a WindowResult dataclass to a WindowSchema.

    Args:
        wr: A ``WindowResult`` instance.

    Returns:
        A ``WindowSchema`` suitable for JSON serialisation.
    """
    return WindowSchema(
        window_number=wr.window.window_number,
        window_id=wr.window.window_id,
        baseline_project_id=wr.window.baseline_project_id,
        update_project_id=wr.window.update_project_id,
        start_date=wr.window.start_date.isoformat() if wr.window.start_date else None,
        end_date=wr.window.end_date.isoformat() if wr.window.end_date else None,
        completion_date_start=(
            wr.completion_date_start.isoformat() if wr.completion_date_start else None
        ),
        completion_date_end=(
            wr.completion_date_end.isoformat() if wr.completion_date_end else None
        ),
        delay_days=wr.delay_days,
        cumulative_delay=wr.cumulative_delay,
        critical_path_start=wr.critical_path_start,
        critical_path_end=wr.critical_path_end,
        cp_activities_joined=wr.cp_activities_joined,
        cp_activities_left=wr.cp_activities_left,
        driving_activity=wr.driving_activity,
        comparison_summary=wr.comparison.summary if wr.comparison else {},
        progress_delay_days=wr.progress_delay_days,
        revision_delay_days=wr.revision_delay_days,
        half_step_summary=wr.half_step_result.summary if wr.half_step_result else None,
    )


@router.post(
    "/api/v1/forensic/create-timeline",
    response_model=TimelineDetailSchema,
)
def create_timeline(
    request: CreateTimelineRequest,
    bifurcated: bool = False,
    _user: object = Depends(optional_auth),
) -> TimelineDetailSchema:
    """Create a forensic CPA timeline from multiple schedule updates.

    Fetches each referenced project from the store, sorts by data date,
    runs the ``ForensicAnalyzer``, stores the result, and returns the
    full timeline.

    Args:
        request: Contains a list of project_ids (minimum 2).
        bifurcated: If True, run MIP 3.4 half-step analysis per window.

    Raises:
        HTTPException: If any project is not found or analysis fails.
    """
    store = get_store()
    tl_store = get_timeline_store()

    schedules: list[ParsedSchedule] = []
    for pid in request.project_ids:
        schedule = store.get(pid)
        if schedule is None:
            raise HTTPException(status_code=404, detail=f"Project not found: {pid}")
        schedules.append(schedule)

    try:
        analyzer = ForensicAnalyzer(schedules, list(request.project_ids), bifurcated=bifurcated)
        timeline = analyzer.analyze()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Forensic analysis failed: {exc}")

    tid = tl_store.add(timeline)

    return TimelineDetailSchema(
        timeline_id=tid,
        project_name=timeline.project_name,
        schedule_count=timeline.schedule_count,
        total_delay_days=timeline.total_delay_days,
        contract_completion=(
            timeline.contract_completion.isoformat() if timeline.contract_completion else None
        ),
        current_completion=(
            timeline.current_completion.isoformat() if timeline.current_completion else None
        ),
        windows=[_window_to_schema(w) for w in timeline.windows],
        summary=timeline.summary,
    )


@router.get(
    "/api/v1/forensic/timelines",
    response_model=TimelineListResponse,
)
def list_timelines(_user: object = Depends(optional_auth)) -> TimelineListResponse:
    """List all forensic timelines."""
    tl_store = get_timeline_store()
    items = [TimelineSummarySchema(**t) for t in tl_store.list_all()]
    return TimelineListResponse(timelines=items)


@router.get(
    "/api/v1/forensic/timelines/{timeline_id}",
    response_model=TimelineDetailSchema,
)
def get_timeline(
    timeline_id: str, _user: object = Depends(optional_auth)
) -> TimelineDetailSchema:
    """Get full forensic timeline with all window results.

    Args:
        timeline_id: The stored timeline identifier.

    Raises:
        HTTPException: If the timeline is not found.
    """
    tl_store = get_timeline_store()
    timeline = tl_store.get(timeline_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail="Timeline not found")

    return TimelineDetailSchema(
        timeline_id=timeline.timeline_id,
        project_name=timeline.project_name,
        schedule_count=timeline.schedule_count,
        total_delay_days=timeline.total_delay_days,
        contract_completion=(
            timeline.contract_completion.isoformat() if timeline.contract_completion else None
        ),
        current_completion=(
            timeline.current_completion.isoformat() if timeline.current_completion else None
        ),
        windows=[_window_to_schema(w) for w in timeline.windows],
        summary=timeline.summary,
    )


@router.post(
    "/api/v1/forensic/half-step",
    response_model=HalfStepResponse,
)
def run_half_step(
    request: HalfStepRequest, _user: object = Depends(optional_auth)
) -> HalfStepResponse:
    """Run a half-step (bifurcation) analysis between two schedule updates.

    Per AACE RP 29R-03 MIP 3.4, separates delay into progress effect
    (actual work performance) and revision effect (logic/plan changes).

    Args:
        request: Contains baseline_id and update_id.

    Raises:
        HTTPException: If either project is not found or analysis fails.
    """
    store = get_store()

    baseline = store.get(request.baseline_id)
    if baseline is None:
        raise HTTPException(
            status_code=404, detail=f"Baseline project not found: {request.baseline_id}"
        )

    update = store.get(request.update_id)
    if update is None:
        raise HTTPException(
            status_code=404, detail=f"Update project not found: {request.update_id}"
        )

    try:
        result = analyze_half_step(baseline, update)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Half-step analysis failed: {exc}")

    return HalfStepResponse(
        completion_a_days=result.completion_a,
        completion_half_step_days=result.completion_half_step,
        completion_b_days=result.completion_b,
        progress_effect_days=result.progress_effect,
        revision_effect_days=result.revision_effect,
        total_delay_days=result.total_delay,
        progress_direction=result.summary.get("progress_direction", ""),
        revision_direction=result.summary.get("revision_direction", ""),
        invariant_holds=result.invariant_check,
        activities_updated=result.activities_updated,
        critical_path_a=result.critical_path_a,
        critical_path_half_step=result.critical_path_half_step,
        critical_path_b=result.critical_path_b,
        classification_summary=result.classification.summary if result.classification else {},
        summary=result.summary,
    )


@router.get(
    "/api/v1/forensic/timelines/{timeline_id}/delay-trend",
    response_model=DelayTrendResponse,
)
def get_delay_trend(
    timeline_id: str, _user: object = Depends(optional_auth)
) -> DelayTrendResponse:
    """Return delay trend data for charting.

    Each point represents one analysis window's data date and the
    forecasted completion date at that point.

    Args:
        timeline_id: The stored timeline identifier.

    Raises:
        HTTPException: If the timeline is not found.
    """
    tl_store = get_timeline_store()
    timeline = tl_store.get(timeline_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail="Timeline not found")

    points: list[DelayTrendPoint] = []
    for wr in timeline.windows:
        points.append(
            DelayTrendPoint(
                window_id=wr.window.window_id,
                window_number=wr.window.window_number,
                data_date=(wr.window.end_date.isoformat() if wr.window.end_date else None),
                completion_date=(
                    wr.completion_date_end.isoformat() if wr.completion_date_end else None
                ),
                delay_days=wr.delay_days,
                cumulative_delay=wr.cumulative_delay,
            )
        )

    return DelayTrendResponse(
        timeline_id=timeline.timeline_id,
        contract_completion=(
            timeline.contract_completion.isoformat() if timeline.contract_completion else None
        ),
        points=points,
    )
