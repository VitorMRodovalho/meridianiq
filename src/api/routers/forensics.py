# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Forensic Analysis (CPA / Window Analysis) router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from src.analytics.forensics import ForensicAnalyzer, ForensicTimeline
from src.analytics.half_step import analyze_half_step
from src.analytics.mip_observational import analyze_mip_3_1, analyze_mip_3_2
from src.analytics.mip_additive import analyze_mip_3_5
from src.analytics.mip_subtractive import (
    DelayEvent,
    WindowDelayEvents,
    analyze_mip_3_6,
    analyze_mip_3_7,
)
from src.parser.models import ParsedSchedule

from ..access import AccessContext, get_access
from ..deps import RATE_LIMIT_MODERATE, get_store, get_timeline_store, limiter
from ..schemas import (
    AppliedAdditiveEventSchema,
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
    Mip35Request,
    Mip35Response,
    Mip35WindowSchema,
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

_TIMELINE_NOT_FOUND = "Timeline not found"


def _owned_timeline(timeline_id: str, ctx: AccessContext) -> ForensicTimeline:
    """Return the caller's timeline, or 404 (same answer as a missing one)."""
    timeline = get_timeline_store().get(timeline_id, owner_id=ctx.principal.user_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail=_TIMELINE_NOT_FOUND)
    return timeline


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
@limiter.limit(RATE_LIMIT_MODERATE)
def create_timeline(
    request: Request,
    body: CreateTimelineRequest,
    bifurcated: bool = False,
    ctx: AccessContext = Depends(get_access),
) -> TimelineDetailSchema:
    """Create a forensic CPA timeline from multiple schedule updates.

    Fetches each referenced project from the store, sorts by data date,
    runs the ``ForensicAnalyzer``, stores the result, and returns the
    full timeline.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: Contains a list of project_ids (minimum 2).
        bifurcated: If True, run MIP 3.4 half-step analysis per window.

    Raises:
        HTTPException: 404 if any project is missing or not the caller's
            (one hidden id fails the whole request); 400/500 if analysis fails.
    """
    project_ids = ctx.projects(list(body.project_ids))
    store = get_store()
    tl_store = get_timeline_store()

    schedules: list[ParsedSchedule] = []
    for pid in project_ids:
        schedule = store.get(pid)
        if schedule is None:
            raise HTTPException(status_code=404, detail="Project not found")
        schedules.append(schedule)

    try:
        analyzer = ForensicAnalyzer(schedules, list(project_ids), bifurcated=bifurcated)
        timeline = analyzer.analyze()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Forensic analysis failed: {exc}")

    tid = tl_store.add(timeline, owner_id=ctx.principal.user_id, project_ids=project_ids)

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
def list_timelines(ctx: AccessContext = Depends(get_access)) -> TimelineListResponse:
    """List the caller's forensic timelines."""
    tl_store = get_timeline_store()
    items = [TimelineSummarySchema(**t) for t in tl_store.summaries(ctx.principal.user_id)]
    return TimelineListResponse(timelines=items)


@router.get(
    "/api/v1/forensic/timelines/{timeline_id}",
    response_model=TimelineDetailSchema,
)
def get_timeline(
    timeline_id: str, ctx: AccessContext = Depends(get_access)
) -> TimelineDetailSchema:
    """Get full forensic timeline with all window results.

    Args:
        timeline_id: The stored timeline identifier.

    Raises:
        HTTPException: If the timeline is not found.
    """
    timeline = _owned_timeline(timeline_id, ctx)

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
@limiter.limit(RATE_LIMIT_MODERATE)
def run_half_step(
    request: Request,
    body: HalfStepRequest,
    ctx: AccessContext = Depends(get_access),
) -> HalfStepResponse:
    """Run a half-step (bifurcation) analysis between two schedule updates.

    Per AACE RP 29R-03 MIP 3.4, separates delay into progress effect
    (actual work performance) and revision effect (logic/plan changes).
    Both ids are authorized before either schedule is read.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: Contains baseline_id and update_id.

    Raises:
        HTTPException: 404 if either project is missing or not the caller's;
            500 if the analysis fails.
    """
    baseline_id, update_id = ctx.projects([body.baseline_id, body.update_id])
    store = get_store()

    baseline = store.get(baseline_id)
    update = store.get(update_id)
    if baseline is None or update is None:
        raise HTTPException(status_code=404, detail="Project not found")

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
@limiter.limit(RATE_LIMIT_MODERATE)
def run_mip_3_1(
    request: Request,
    body: Mip31Request,
    ctx: AccessContext = Depends(get_access),
) -> Mip31Response:
    """Run MIP 3.1 — Observational Static Logic / Gross comparison.

    Compares only the earliest (baseline) and latest (as-built) schedules
    per AACE RP 29R-03 §3.1. No intermediate updates are examined. Both
    ids are authorized before either schedule is read.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: Contains baseline_id and final_id.

    Raises:
        HTTPException: 404 if either project is missing or not the caller's.
    """
    baseline_id, final_id = ctx.projects([body.baseline_id, body.final_id])
    store = get_store()

    baseline = store.get(baseline_id)
    final = store.get(final_id)
    if baseline is None or final is None:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        result = analyze_mip_3_1(baseline, final, baseline_id=baseline_id, final_id=final_id)
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
@limiter.limit(RATE_LIMIT_MODERATE)
def run_mip_3_2(
    request: Request,
    body: Mip32Request,
    ctx: AccessContext = Depends(get_access),
) -> Mip32Response:
    """Run MIP 3.2 — Observational Dynamic Logic / Contemporaneous As-Is.

    Walks every supplied schedule chronologically, producing one event per
    update (no window splitting). Per AACE RP 29R-03 §3.2.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: Contains project_ids (minimum 2).

    Raises:
        HTTPException: 404 if any project is missing or not the caller's
            (one hidden id fails the whole request); 400 on invalid input.
    """
    project_ids = ctx.projects(list(body.project_ids))
    store = get_store()

    schedules: list[ParsedSchedule] = []
    for pid in project_ids:
        schedule = store.get(pid)
        if schedule is None:
            raise HTTPException(status_code=404, detail="Project not found")
        schedules.append(schedule)

    try:
        result = analyze_mip_3_2(schedules, project_ids=project_ids)
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
@limiter.limit(RATE_LIMIT_MODERATE)
def run_mip_3_6(
    request: Request,
    body: Mip36Request,
    ctx: AccessContext = Depends(get_access),
) -> Mip36Response:
    """Run MIP 3.6 — Modified / Subtractive Single Simulation (Collapsed As-Built).

    Per AACE RP 29R-03 §3.6.  Caller names activities with per-activity
    delay attributions; the engine shortens those activities and re-runs
    CPM to compute the "but-for" completion date — what the project
    duration would have been without those delays.

    Unmatched ``task_id`` values are returned in ``unmatched_events``
    rather than raising, so the caller can show partial results.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: ``Mip36Request`` with project_id + list of delay events.

    Raises:
        HTTPException: 404 if the project is missing or not the caller's,
            400 on negative days.
    """
    project_id = ctx.project(body.project_id)
    store = get_store()

    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    events = [
        DelayEvent(
            task_id=e.task_id,
            days=e.days,
            description=e.description,
        )
        for e in body.delay_events
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
@limiter.limit(RATE_LIMIT_MODERATE)
def run_mip_3_7(
    request: Request,
    body: Mip37Request,
    ctx: AccessContext = Depends(get_access),
) -> Mip37Response:
    """Run MIP 3.7 — Modified / Subtractive Multiple Simulation (Windowed Collapsed).

    Per AACE RP 29R-03 §3.7.  Applies the MIP 3.6 collapsed-as-built
    pattern to each analysis window in a schedule-update series.  Delay
    events are attributed to specific windows; windows without events
    report zero attributable delay.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: project_ids (minimum 2) + optional per-window delay
            event bundles.

    Raises:
        HTTPException: 404 if any project is missing or not the caller's
            (one hidden id fails the whole request), 400 on invalid
            window_number or negative days.
    """
    project_ids = ctx.projects(list(body.project_ids))
    store = get_store()

    schedules: list[ParsedSchedule] = []
    for pid in project_ids:
        schedule = store.get(pid)
        if schedule is None:
            raise HTTPException(status_code=404, detail="Project not found")
        schedules.append(schedule)

    bundles = [
        WindowDelayEvents(
            window_number=b.window_number,
            events=[
                DelayEvent(task_id=e.task_id, days=e.days, description=e.description)
                for e in b.events
            ],
        )
        for b in body.window_delay_events
    ]

    try:
        result = analyze_mip_3_7(
            schedules,
            window_delay_events=bundles,
            project_ids=project_ids,
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


@router.post(
    "/api/v1/forensic/mip-3-5",
    response_model=Mip35Response,
)
@limiter.limit(RATE_LIMIT_MODERATE)
def run_mip_3_5(
    request: Request,
    body: Mip35Request,
    ctx: AccessContext = Depends(get_access),
) -> Mip35Response:
    """Run MIP 3.5 — Modified / Additive Multiple Base (Impacted As-Planned).

    Per AACE RP 29R-03 §3.5.  For each analysis window (schedule pair),
    the window's baseline (first schedule) is impacted with caller-
    attributed delay events — each event extends the named activity's
    duration by the given days.  The impact is measured as impacted
    completion minus baseline completion for that window.

    Mirrors MIP 3.7 structurally but applies additive (impact)
    semantics rather than subtractive (but-for) semantics.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: project_ids (minimum 2) + optional per-window delay
            event bundles.

    Raises:
        HTTPException: 404 if any project is missing or not the caller's
            (one hidden id fails the whole request), 400 on invalid
            window_number or negative days.
    """
    project_ids = ctx.projects(list(body.project_ids))
    store = get_store()

    schedules: list[ParsedSchedule] = []
    for pid in project_ids:
        schedule = store.get(pid)
        if schedule is None:
            raise HTTPException(status_code=404, detail="Project not found")
        schedules.append(schedule)

    bundles = [
        WindowDelayEvents(
            window_number=b.window_number,
            events=[
                DelayEvent(task_id=e.task_id, days=e.days, description=e.description)
                for e in b.events
            ],
        )
        for b in body.window_delay_events
    ]

    try:
        result = analyze_mip_3_5(
            schedules,
            window_delay_events=bundles,
            project_ids=project_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MIP 3.5 analysis failed: {exc}")

    windows = [
        Mip35WindowSchema(
            window_number=w.window_number,
            window_id=w.window_id,
            baseline_project_id=w.baseline_project_id,
            update_project_id=w.update_project_id,
            baseline_completion_days=w.baseline_completion_days,
            impacted_completion_days=w.impacted_completion_days,
            impact_delay_days=w.impact_delay_days,
            delay_events_applied=[
                AppliedAdditiveEventSchema(
                    task_id=a.task_id,
                    task_code=a.task_code,
                    task_name=a.task_name,
                    days_requested=a.days_requested,
                    days_applied=a.days_applied,
                    original_duration_days=a.original_duration_days,
                    impacted_duration_days=a.impacted_duration_days,
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

    return Mip35Response(
        project_ids=result.project_ids,
        schedule_count=result.schedule_count,
        window_count=result.window_count,
        total_impact_delay_days=result.total_impact_delay_days,
        windows=windows,
        methodology=result.methodology,
    )


@router.get(
    "/api/v1/forensic/timelines/{timeline_id}/delay-trend",
    response_model=DelayTrendResponse,
)
def get_delay_trend(
    timeline_id: str, ctx: AccessContext = Depends(get_access)
) -> DelayTrendResponse:
    """Return delay trend data for charting.

    Each point represents one analysis window's data date and the
    forecasted completion date at that point.

    Args:
        timeline_id: The stored timeline identifier.

    Raises:
        HTTPException: If the timeline is not found.
    """
    timeline = _owned_timeline(timeline_id, ctx)

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
