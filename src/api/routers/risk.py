# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Risk Analysis (Monte Carlo QSRA) router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import optional_auth
from ..deps import RATE_LIMIT_EXPENSIVE, get_risk_store, get_store, limiter
from ..schemas import (
    CriticalityEntrySchema,
    CriticalityResponse,
    HistogramBinSchema,
    HistogramResponse,
    PValueSchema,
    RiskSCurvePointSchema,
    RiskSCurveResponse,
    RiskSimulationByJobResponse,
    RunSimulationRequest,
    SensitivityEntrySchema,
    SimulationListResponse,
    SimulationResultSchema,
    SimulationSummarySchema,
    TornadoResponse,
)

from src.analytics.risk import (
    DistributionType,
    DurationRisk,
    MonteCarloSimulator,
    RiskEvent,
    SimulationConfig,
)

router = APIRouter()


def _simulation_to_schema(result: Any) -> SimulationResultSchema:
    """Convert a SimulationResult dataclass to its Pydantic schema.

    Args:
        result: A ``SimulationResult`` instance.

    Returns:
        A ``SimulationResultSchema`` for JSON serialisation.
    """
    return SimulationResultSchema(
        simulation_id=result.simulation_id,
        project_name=result.project_name,
        project_id=result.project_id,
        iterations=result.iterations,
        deterministic_days=result.deterministic_days,
        mean_days=result.mean_days,
        std_days=result.std_days,
        p_values=[
            PValueSchema(
                percentile=pv.percentile,
                duration_days=pv.duration_days,
                delta_days=pv.delta_days,
            )
            for pv in result.p_values
        ],
        histogram=[
            HistogramBinSchema(
                bin_start=b.bin_start,
                bin_end=b.bin_end,
                count=b.count,
                frequency=b.frequency,
            )
            for b in result.histogram
        ],
        criticality=[
            CriticalityEntrySchema(
                activity_id=c.activity_id,
                activity_name=c.activity_name,
                criticality_pct=c.criticality_pct,
            )
            for c in result.criticality
        ],
        sensitivity=[
            SensitivityEntrySchema(
                activity_id=s.activity_id,
                activity_name=s.activity_name,
                correlation=s.correlation,
            )
            for s in result.sensitivity
        ],
        s_curve=[
            RiskSCurvePointSchema(
                duration_days=p.duration_days,
                cumulative_probability=p.cumulative_probability,
            )
            for p in result.s_curve
        ],
    )


@router.post(
    "/api/v1/risk/simulate/{project_id}",
    response_model=SimulationResultSchema,
)
@limiter.limit(RATE_LIMIT_EXPENSIVE)
async def run_risk_simulation(
    request: Request,
    project_id: str,
    payload: RunSimulationRequest,
    job_id: str | None = None,
    _user: object = Depends(optional_auth),
) -> SimulationResultSchema:
    """Run Monte Carlo schedule risk simulation (QSRA) on a project.

    Performs *N* iterations sampling activity durations from probability
    distributions, running CPM each time, and computing completion date
    probability distributions, criticality indices, and sensitivity.
    Per AACE RP 57R-09.

    Args:
        project_id: The stored project identifier.
        request: Simulation configuration, duration risks, and risk events.
        job_id: Optional progress channel id. When set, the client should
            connect to ``GET /api/v1/ws/progress/{job_id}`` (WebSocket)
            BEFORE issuing this request to receive ``{"type": "progress",
            "done", "total", "pct"}`` events plus a final ``{"type": "done"}``.

    Raises:
        HTTPException: If the project is not found or simulation fails.
    """
    import asyncio

    from ..progress import get_channel, get_channel_owner, publish, thread_safe_publisher

    store = get_store()
    risk_store = get_risk_store()

    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    # Convert payload schemas to domain models
    config = None
    if payload.config:
        config = SimulationConfig(
            iterations=payload.config.iterations,
            default_distribution=DistributionType(payload.config.default_distribution),
            default_uncertainty=payload.config.default_uncertainty,
            seed=payload.config.seed,
            confidence_levels=payload.config.confidence_levels,
        )

    duration_risks = (
        [
            DurationRisk(
                activity_id=r.activity_id,
                distribution=DistributionType(r.distribution),
                min_duration=r.min_duration,
                most_likely=r.most_likely,
                max_duration=r.max_duration,
            )
            for r in payload.duration_risks
        ]
        if payload.duration_risks
        else None
    )

    risk_events = (
        [
            RiskEvent(
                risk_id=e.risk_id,
                name=e.name,
                probability=e.probability,
                impact_hours=e.impact_hours,
                affected_activities=e.affected_activities,
            )
            for e in payload.risk_events
        ]
        if payload.risk_events
        else None
    )

    progress_callback = None
    if job_id:
        # Wave 0 #7 hardening: the caller may only use a job_id they own
        # (the channel was bound on POST /api/v1/jobs/progress/start). If
        # the channel is bound AND the authenticated user differs, reject.
        owner = get_channel_owner(job_id)
        caller_id = _user["id"] if isinstance(_user, dict) else None
        if owner is not None and caller_id is not None and owner != caller_id:
            raise HTTPException(
                status_code=403,
                detail="job_id is bound to another user",
            )
    if job_id and get_channel(job_id) is not None:
        publish_event = thread_safe_publisher(job_id)

        def progress_callback(done: int, total: int) -> None:
            publish_event(
                {
                    "type": "progress",
                    "done": done,
                    "total": total,
                    "pct": round(done * 100 / total, 1) if total else 0.0,
                }
            )

    try:
        simulator = MonteCarloSimulator(schedule, config)
        result = await asyncio.to_thread(
            simulator.simulate, duration_risks, risk_events, progress_callback
        )
        result.project_id = project_id
    except Exception as exc:
        if job_id:
            publish(job_id, {"type": "error", "message": str(exc)})
        raise HTTPException(status_code=500, detail=f"Risk simulation failed: {exc}")

    risk_store.add(result)

    if job_id:
        # ADR-0019 §"W1 — D4" — bind job_id → simulation_id so the
        # WS-recovery poller can recover the result if the WS dropped
        # before the terminal `done` frame arrived.
        risk_store.bind_job(job_id, result.simulation_id)
        publish(job_id, {"type": "done", "simulation_id": result.simulation_id})

    return _simulation_to_schema(result)


@router.get("/api/v1/risk/simulations", response_model=SimulationListResponse)
def list_risk_simulations(
    _user: object = Depends(optional_auth),
) -> SimulationListResponse:
    """List all risk simulations."""
    risk_store = get_risk_store()
    items = [SimulationSummarySchema(**s) for s in risk_store.list_all()]
    return SimulationListResponse(simulations=items)


@router.get(
    "/api/v1/risk/simulations/by-job/{job_id}",
    response_model=RiskSimulationByJobResponse,
)
def get_risk_simulation_by_job(
    job_id: str,
    _user: object = Depends(optional_auth),
) -> RiskSimulationByJobResponse:
    """Look up a risk simulation by its progress channel job_id.

    Per ADR-0019 §"W1 — D4". Used by the WebSocket-progress recovery
    poller (frontend ``recoveryPoller``) to determine whether a
    Monte Carlo simulation completed after a transient WS disconnect.

    Returns 200 in both states — the poller's contract distinguishes
    completion via the ``simulation_id`` value (string → done, null →
    still running or never bound).

    Args:
        job_id: Progress channel id allocated by
            ``POST /api/v1/jobs/progress/start``.

    Raises:
        HTTPException: 403 when the channel is bound to a different
            user (matches ``run_risk_simulation`` ownership check).
    """
    from ..progress import get_channel_owner

    owner = get_channel_owner(job_id)
    caller_id = _user["id"] if isinstance(_user, dict) else None
    if owner is not None and caller_id is not None and owner != caller_id:
        raise HTTPException(
            status_code=403,
            detail="job_id is bound to another user",
        )

    risk_store = get_risk_store()
    sid = risk_store.get_simulation_id_by_job(job_id)
    return RiskSimulationByJobResponse(simulation_id=sid)


@router.get(
    "/api/v1/risk/simulations/{simulation_id}",
    response_model=SimulationResultSchema,
)
def get_risk_simulation(
    simulation_id: str, _user: object = Depends(optional_auth)
) -> SimulationResultSchema:
    """Get full risk simulation result with all analysis data.

    Args:
        simulation_id: The stored simulation identifier.

    Raises:
        HTTPException: If the simulation is not found.
    """
    risk_store = get_risk_store()
    result = risk_store.get(simulation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Risk simulation not found")

    return _simulation_to_schema(result)


@router.get(
    "/api/v1/risk/simulations/{simulation_id}/histogram",
    response_model=HistogramResponse,
)
def get_risk_histogram(
    simulation_id: str, _user: object = Depends(optional_auth)
) -> HistogramResponse:
    """Get histogram data for a risk simulation.

    Returns bin counts and P-value overlay lines suitable for
    charting a probability distribution of project completion.

    Args:
        simulation_id: The stored simulation identifier.

    Raises:
        HTTPException: If the simulation is not found.
    """
    risk_store = get_risk_store()
    result = risk_store.get(simulation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Risk simulation not found")

    return HistogramResponse(
        simulation_id=simulation_id,
        deterministic_days=result.deterministic_days,
        bins=[
            HistogramBinSchema(
                bin_start=b.bin_start,
                bin_end=b.bin_end,
                count=b.count,
                frequency=b.frequency,
            )
            for b in result.histogram
        ],
        p_values=[
            PValueSchema(
                percentile=pv.percentile,
                duration_days=pv.duration_days,
                delta_days=pv.delta_days,
            )
            for pv in result.p_values
        ],
    )


@router.get(
    "/api/v1/risk/simulations/{simulation_id}/tornado",
    response_model=TornadoResponse,
)
def get_risk_tornado(simulation_id: str, _user: object = Depends(optional_auth)) -> TornadoResponse:
    """Get sensitivity / tornado data for a risk simulation.

    Returns Spearman rank correlations between each activity's
    sampled duration and the project completion date, sorted by
    absolute correlation (top 15).

    Args:
        simulation_id: The stored simulation identifier.

    Raises:
        HTTPException: If the simulation is not found.
    """
    risk_store = get_risk_store()
    result = risk_store.get(simulation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Risk simulation not found")

    # Return top 15 by absolute correlation
    top_entries = result.sensitivity[:15]

    return TornadoResponse(
        simulation_id=simulation_id,
        entries=[
            SensitivityEntrySchema(
                activity_id=s.activity_id,
                activity_name=s.activity_name,
                correlation=s.correlation,
            )
            for s in top_entries
        ],
    )


@router.get(
    "/api/v1/risk/simulations/{simulation_id}/criticality",
    response_model=CriticalityResponse,
)
def get_risk_criticality(
    simulation_id: str, _user: object = Depends(optional_auth)
) -> CriticalityResponse:
    """Get criticality index data for a risk simulation.

    Returns the percentage of iterations in which each activity
    appeared on the critical path.

    Args:
        simulation_id: The stored simulation identifier.

    Raises:
        HTTPException: If the simulation is not found.
    """
    risk_store = get_risk_store()
    result = risk_store.get(simulation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Risk simulation not found")

    return CriticalityResponse(
        simulation_id=simulation_id,
        entries=[
            CriticalityEntrySchema(
                activity_id=c.activity_id,
                activity_name=c.activity_name,
                criticality_pct=c.criticality_pct,
            )
            for c in result.criticality
        ],
    )


@router.get("/api/v1/risk/simulations/{simulation_id}/register-entries")
def get_simulation_register_entries(
    simulation_id: str,
    top_n: int = 15,
    _user: object = Depends(optional_auth),
) -> dict:
    """Return register entries that touch the simulation's most-sensitive activities.

    Links are **activity-based** (semantic): a register entry is
    considered linked when any of its ``affected_activities`` appears
    among the top-N activities by sensitivity correlation OR criticality
    index in the simulation. No foreign key is stored — the simulation
    id itself is in-memory and ephemeral.

    Returns the linked entries plus the set of activities that drove
    the match, so the UI can explain *why* each entry surfaced.

    Args:
        simulation_id: The stored simulation identifier.
        top_n: How many top activities to consider for matching (default 15).

    Reference: AACE RP 57R-09 — Schedule Risk Analysis.
    """
    risk_store = get_risk_store()
    store = get_store()

    result = risk_store.get(simulation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Risk simulation not found")

    if not hasattr(store, "list_risk_entries"):
        return {
            "simulation_id": simulation_id,
            "project_id": result.project_id,
            "driver_activities": [],
            "entries": [],
            "total": 0,
        }

    top_sensitivity = {s.activity_id for s in result.sensitivity[:top_n] if s.activity_id}
    top_criticality = {c.activity_id for c in result.criticality[:top_n] if c.activity_id}
    # Also match by activity_name / task_code since register entries may store
    # user-facing codes rather than internal task_ids.
    top_activity_names = {
        s.activity_name for s in result.sensitivity[:top_n] if s.activity_name
    } | {c.activity_name for c in result.criticality[:top_n] if c.activity_name}

    driver_ids = top_sensitivity | top_criticality | top_activity_names

    user_id = _user["id"] if _user else None  # type: ignore[index]
    entries = store.list_risk_entries(result.project_id, user_id=user_id)

    sensitivity_by_id = {s.activity_id: s.correlation for s in result.sensitivity}
    criticality_by_id = {c.activity_id: c.criticality_pct for c in result.criticality}

    linked = []
    for e in entries:
        affected = set(e.get("affected_activities") or [])
        matched = affected & driver_ids
        if not matched:
            continue
        # Collect metrics for matched activities
        matched_details = []
        for act in sorted(matched):
            matched_details.append(
                {
                    "activity": act,
                    "sensitivity": sensitivity_by_id.get(act),
                    "criticality_pct": criticality_by_id.get(act),
                }
            )
        linked.append({**e, "matched_activities": matched_details})

    return {
        "simulation_id": simulation_id,
        "project_id": result.project_id,
        "driver_activities": sorted(driver_ids),
        "entries": linked,
        "total": len(linked),
    }


@router.get(
    "/api/v1/risk/simulations/{simulation_id}/s-curve",
    response_model=RiskSCurveResponse,
)
def get_risk_s_curve(
    simulation_id: str, _user: object = Depends(optional_auth)
) -> RiskSCurveResponse:
    """Get cumulative probability S-curve data for a risk simulation.

    Returns sorted completion durations with their cumulative
    probability, suitable for charting a sigmoid/S-curve.

    Args:
        simulation_id: The stored simulation identifier.

    Raises:
        HTTPException: If the simulation is not found.
    """
    risk_store = get_risk_store()
    result = risk_store.get(simulation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Risk simulation not found")

    return RiskSCurveResponse(
        simulation_id=simulation_id,
        deterministic_days=result.deterministic_days,
        points=[
            RiskSCurvePointSchema(
                duration_days=p.duration_days,
                cumulative_probability=p.cumulative_probability,
            )
            for p in result.s_curve
        ],
        p_values=[
            PValueSchema(
                percentile=pv.percentile,
                duration_days=pv.duration_days,
                delta_days=pv.delta_days,
            )
            for pv in result.p_values
        ],
    )
