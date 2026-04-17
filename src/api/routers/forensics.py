# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Forensic Analysis (CPA / Window Analysis) router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.analytics.forensics import ForensicAnalyzer
from src.analytics.half_step import analyze_half_step
from src.analytics.mip_observational import analyze_mip_3_1, analyze_mip_3_2
from src.analytics.mip_subtractive import (
    DelayEvent,
    WindowDelayEvents,
    analyze_mip_3_6,
    analyze_mip_3_7,
)
from src.parser.models import ParsedSchedule

from ..auth import optional_auth
from ..deps import get_store, get_timeline_store
from ..schemas import (
    AppliedDelayEventSchema,
    CreateTimelineRequest,
    DelayEventSchema,
    DelayTrendPoint,
    DelayTrendResponse,
    HalfStepRequest,
    HalfStepResponse,
    Mip31Request,
    Mip31Response,
    Mip32EventSchema,
    Mip32Request,
    Mip32Response,
    Mip36Request,
    Mip36Response,
    Mip37Request,
    Mip37Response,
    Mip37WindowSchema,
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
def get_timeline(timeline_id: str, _user: object = Depends(optional_auth)) -> TimelineDetailSchema:
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


@router.post(
    "/api/v1/forensic/mip-3-1",
    response_model=Mip31Response,
)
def run_mip_3_1(
    request: Mip31Request,
    _user: object = Depends(optional_auth),
) -> Mip31Response:
    """Run MIP 3.1 — Observational Static Logic / Gross comparison.

    Compares only the earliest (baseline) and latest (as-built) schedules
    per AACE RP 29R-03 §3.1. No intermediate updates are examined.

    Args:
        request: Contains baseline_id and final_id.

    Raises:
        HTTPException: If either project is not found.
    """
    store = get_store()

    baseline = store.get(request.baseline_id)
    if baseline is None:
        raise HTTPException(
            status_code=404, detail=f"Baseline project not found: {request.baseline_id}"
        )

    final = store.get(request.final_id)
    if final is None:
        raise HTTPException(status_code=404, detail=f"Final project not found: {request.final_id}")

    try:
        result = analyze_mip_3_1(
            baseline, final, baseline_id=request.baseline_id, final_id=request.final_id
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MIP 3.1 analysis failed: {exc}")

    return Mip31Response(
        baseline_project_id=result.baseline_project_id,
        final_project_id=result.final_project_id,
        baseline_data_date=(
            result.baseline_data_date.isoformat() if result.baseline_data_date else None
        ),
        final_data_date=(result.final_data_date.isoformat() if result.final_data_date else None),
        baseline_completion_date=(
            result.baseline_completion_date.isoformat() if result.baseline_completion_date else None
        ),
        final_completion_date=(
            result.final_completion_date.isoformat() if result.final_completion_date else None
        ),
        gross_delay_days=result.gross_delay_days,
        baseline_critical_path=result.baseline_critical_path,
        final_critical_path=result.final_critical_path,
        cp_activities_joined=result.cp_activities_joined,
        cp_activities_left=result.cp_activities_left,
        driving_activity=result.driving_activity,
        activities_added=result.activities_added,
        activities_deleted=result.activities_deleted,
        activities_changed=result.activities_changed,
        comparison_summary=result.comparison_summary,
        methodology=result.methodology,
    )


@router.post(
    "/api/v1/forensic/mip-3-2",
    response_model=Mip32Response,
)
def run_mip_3_2(
    request: Mip32Request,
    _user: object = Depends(optional_auth),
) -> Mip32Response:
    """Run MIP 3.2 — Observational Dynamic Logic / Contemporaneous As-Is.

    Walks every supplied schedule chronologically, producing one event per
    update (no window splitting). Per AACE RP 29R-03 §3.2.

    Args:
        request: Contains project_ids (minimum 2).

    Raises:
        HTTPException: 404 if any project is missing, 400 on invalid input.
    """
    store = get_store()

    schedules: list[ParsedSchedule] = []
    for pid in request.project_ids:
        schedule = store.get(pid)
        if schedule is None:
            raise HTTPException(status_code=404, detail=f"Project not found: {pid}")
        schedules.append(schedule)

    try:
        result = analyze_mip_3_2(schedules, project_ids=list(request.project_ids))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MIP 3.2 analysis failed: {exc}")

    events = [
        Mip32EventSchema(
            index=e.index,
            project_id=e.project_id,
            data_date=e.data_date.isoformat() if e.data_date else None,
            completion_date=e.completion_date.isoformat() if e.completion_date else None,
            delay_since_baseline_days=e.delay_since_baseline_days,
            delay_since_previous_days=e.delay_since_previous_days,
            critical_path=e.critical_path,
            cp_activities_joined_since_previous=e.cp_activities_joined_since_previous,
            cp_activities_left_since_previous=e.cp_activities_left_since_previous,
            driving_activity=e.driving_activity,
        )
        for e in result.events
    ]

    return Mip32Response(
        project_ids=result.project_ids,
        schedule_count=result.schedule_count,
        baseline_completion_date=(
            result.baseline_completion_date.isoformat() if result.baseline_completion_date else None
        ),
        final_completion_date=(
            result.final_completion_date.isoformat() if result.final_completion_date else None
        ),
        total_delay_days=result.total_delay_days,
        events=events,
        cp_activities_ever_critical=result.cp_activities_ever_critical,
        methodology=result.methodology,
    )


@router.post(
    "/api/v1/forensic/mip-3-6",
    response_model=Mip36Response,
)
def run_mip_3_6(
    request: Mip36Request,
    _user: object = Depends(optional_auth),
) -> Mip36Response:
    """Run MIP 3.6 — Modified / Subtractive Single Simulation (Collapsed As-Built).

    Per AACE RP 29R-03 §3.6.  Caller names activities with per-activity
    delay attributions; the engine shortens those activities and re-runs
    CPM to compute the "but-for" completion date — what the project
    duration would have been without those delays.

    Unmatched ``task_id`` values are returned in ``unmatched_events``
    rather than raising, so the caller can show partial results.

    Args:
        request: ``Mip36Request`` with project_id + list of delay events.

    Raises:
        HTTPException: 404 if project missing, 400 on negative days.
    """
    store = get_store()

    schedule = store.get(request.project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {request.project_id}")

    events = [
        DelayEvent(
            task_id=e.task_id,
            days=e.days,
            description=e.description,
        )
        for e in request.delay_events
    ]

    try:
        result = analyze_mip_3_6(schedule, events)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MIP 3.6 analysis failed: {exc}")

    return Mip36Response(
        as_built_completion_days=result.as_built_completion_days,
        but_for_completion_days=result.but_for_completion_days,
        attributable_delay_days=result.attributable_delay_days,
        delay_events_applied=[
            AppliedDelayEventSchema(
                task_id=a.task_id,
                task_code=a.task_code,
                task_name=a.task_name,
                days_requested=a.days_requested,
                days_applied=a.days_applied,
                original_duration_days=a.original_duration_days,
                collapsed_duration_days=a.collapsed_duration_days,
                description=a.description,
                note=a.note,
            )
            for a in result.delay_events_applied
        ],
        unmatched_events=[
            DelayEventSchema(task_id=u.task_id, days=u.days, description=u.description)
            for u in result.unmatched_events
        ],
        as_built_critical_path=result.as_built_critical_path,
        but_for_critical_path=result.but_for_critical_path,
        methodology=result.methodology,
    )


@router.post(
    "/api/v1/forensic/mip-3-7",
    response_model=Mip37Response,
)
def run_mip_3_7(
    request: Mip37Request,
    _user: object = Depends(optional_auth),
) -> Mip37Response:
    """Run MIP 3.7 — Modified / Subtractive Multiple Simulation (Windowed Collapsed).

    Per AACE RP 29R-03 §3.7.  Applies the MIP 3.6 collapsed-as-built
    pattern to each analysis window in a schedule-update series.  Delay
    events are attributed to specific windows; windows without events
    report zero attributable delay.

    Args:
        request: project_ids (minimum 2) + optional per-window delay
            event bundles.

    Raises:
        HTTPException: 404 if any project is missing, 400 on invalid
            window_number or negative days.
    """
    store = get_store()

    schedules: list[ParsedSchedule] = []
    for pid in request.project_ids:
        schedule = store.get(pid)
        if schedule is None:
            raise HTTPException(status_code=404, detail=f"Project not found: {pid}")
        schedules.append(schedule)

    bundles = [
        WindowDelayEvents(
            window_number=b.window_number,
            events=[
                DelayEvent(task_id=e.task_id, days=e.days, description=e.description)
                for e in b.events
            ],
        )
        for b in request.window_delay_events
    ]

    try:
        result = analyze_mip_3_7(
            schedules,
            window_delay_events=bundles,
            project_ids=list(request.project_ids),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MIP 3.7 analysis failed: {exc}")

    windows = [
        Mip37WindowSchema(
            window_number=w.window_number,
            window_id=w.window_id,
            baseline_project_id=w.baseline_project_id,
            update_project_id=w.update_project_id,
            as_built_completion_days=w.as_built_completion_days,
            but_for_completion_days=w.but_for_completion_days,
            attributable_delay_days=w.attributable_delay_days,
            delay_events_applied=[
                AppliedDelayEventSchema(
                    task_id=a.task_id,
                    task_code=a.task_code,
                    task_name=a.task_name,
                    days_requested=a.days_requested,
                    days_applied=a.days_applied,
                    original_duration_days=a.original_duration_days,
                    collapsed_duration_days=a.collapsed_duration_days,
                    description=a.description,
                    note=a.note,
                )
                for a in w.delay_events_applied
            ],
            unmatched_events=[
                DelayEventSchema(task_id=u.task_id, days=u.days, description=u.description)
                for u in w.unmatched_events
            ],
        )
        for w in result.windows
    ]

    return Mip37Response(
        project_ids=result.project_ids,
        schedule_count=result.schedule_count,
        window_count=result.window_count,
        total_attributable_delay_days=result.total_attributable_delay_days,
        windows=windows,
        methodology=result.methodology,
    )


@router.get(
    "/api/v1/forensic/timelines/{timeline_id}/delay-trend",
    response_model=DelayTrendResponse,
)
def get_delay_trend(timeline_id: str, _user: object = Depends(optional_auth)) -> DelayTrendResponse:
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
