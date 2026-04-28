# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""What-if router — scenario analysis, Pareto, leveling, prediction, scorecard."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import optional_auth
from ..deps import RATE_LIMIT_EXPENSIVE, RATE_LIMIT_WRITE, get_store, limiter
from ..schemas import (
    ActivityImpactSchema,
    ActivityShiftSchema,
    ConvergencePointSchema,
    DurationPredictionResponse,
    LevelingRequest,
    LevelingResponse,
    OptimizeResponse,
    ParetoPointSchema,
    ParetoRequest,
    ParetoResponse,
    ResourceProfileSchema,
    ScorecardDimensionSchema,
    ScorecardResponse,
    WhatIfRequest,
    WhatIfResponse,
)

router = APIRouter()


@router.post("/api/v1/projects/{project_id}/what-if")
@limiter.limit(RATE_LIMIT_EXPENSIVE)
def run_what_if(
    request: Request,
    project_id: str,
    body: WhatIfRequest,
    _user: object = Depends(optional_auth),
) -> WhatIfResponse:
    """Run a what-if scenario on a project schedule.

    Applies duration adjustments and re-runs CPM to determine impact on
    project duration, critical path, and per-activity dates.  Supports
    deterministic (single run) and probabilistic (N iterations with ranges).

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        project_id: The stored project identifier.
        body: Scenario definition with adjustments and iteration count.

    References:
        AACE RP 57R-09 — Scenario Analysis,
        PMI PMBOK 7 S4.6 — Measurement Performance Domain.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from src.analytics.whatif import (
        DurationAdjustment,
        WhatIfScenario,
        simulate_whatif,
    )

    scenario = WhatIfScenario(
        name=body.name,
        adjustments=[
            DurationAdjustment(
                target=a.target,
                pct_change=a.pct_change,
                min_pct=a.min_pct,
                max_pct=a.max_pct,
            )
            for a in body.adjustments
        ],
        iterations=body.iterations,
    )

    result = simulate_whatif(schedule, scenario)

    return WhatIfResponse(
        scenario_name=result.scenario_name,
        base_duration_days=result.base_duration_days,
        adjusted_duration_days=result.adjusted_duration_days,
        delta_days=result.delta_days,
        delta_pct=result.delta_pct,
        critical_path_changed=result.critical_path_changed,
        new_critical_path=result.new_critical_path,
        activity_impacts=[
            ActivityImpactSchema(
                task_id=i.task_id,
                task_code=i.task_code,
                task_name=i.task_name,
                original_duration_days=i.original_duration_days,
                adjusted_duration_days=i.adjusted_duration_days,
                delta_days=i.delta_days,
                original_total_float=i.original_total_float,
                adjusted_total_float=i.adjusted_total_float,
                was_critical=i.was_critical,
                is_critical=i.is_critical,
            )
            for i in result.activity_impacts
        ],
        iterations=result.iterations,
        distribution=result.distribution,
        p_values=result.p_values,
        std_days=result.std_days,
        methodology=result.methodology,
        summary=result.summary,
    )


@router.post("/api/v1/projects/{project_id}/pareto")
@limiter.limit(RATE_LIMIT_EXPENSIVE)
def run_pareto_analysis(
    request: Request,
    project_id: str,
    body: ParetoRequest,
    _user: object = Depends(optional_auth),
) -> ParetoResponse:
    """Run time-cost Pareto analysis across multiple scenarios.

    Identifies the Pareto-optimal frontier of non-dominated solutions
    on the time-vs-cost plane.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        project_id: The stored project identifier.
        body: List of cost scenarios + base cost for the Pareto frontier.

    References:
        AACE RP 36R-06, Kelley & Walker (1959).
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from src.analytics.pareto import CostScenario, analyze_pareto
    from src.analytics.whatif import DurationAdjustment

    scenarios = [
        CostScenario(
            name=cs.name,
            adjustments=[
                DurationAdjustment(
                    target=a.target,
                    pct_change=a.pct_change,
                    min_pct=a.min_pct,
                    max_pct=a.max_pct,
                )
                for a in cs.adjustments
            ],
            cost_delta=cs.cost_delta,
        )
        for cs in body.scenarios
    ]

    result = analyze_pareto(schedule, scenarios, base_cost=body.base_cost)

    def _map_point(p):  # noqa: ANN001, ANN202
        return ParetoPointSchema(
            scenario_name=p.scenario_name,
            duration_days=p.duration_days,
            total_cost=p.total_cost,
            is_pareto_optimal=p.is_pareto_optimal,
            delta_days=p.delta_days,
            delta_cost=p.delta_cost,
        )

    return ParetoResponse(
        base_duration_days=result.base_duration_days,
        base_cost=result.base_cost,
        all_points=[_map_point(p) for p in result.all_points],
        frontier=[_map_point(p) for p in result.frontier],
        scenarios_evaluated=result.scenarios_evaluated,
        frontier_size=result.frontier_size,
        methodology=result.methodology,
        summary=result.summary,
    )


@router.post("/api/v1/projects/{project_id}/resource-leveling")
@limiter.limit(RATE_LIMIT_EXPENSIVE)
def run_resource_leveling(
    request: Request,
    project_id: str,
    body: LevelingRequest,
    _user: object = Depends(optional_auth),
) -> LevelingResponse:
    """Run resource-constrained scheduling using Serial SGS.

    Levels resources by scheduling activities at their earliest feasible
    start, respecting both precedence and resource capacity constraints.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        project_id: The stored project identifier.
        body: Resource limits + priority rule + max extension config.

    References:
        AACE RP 46R-11, Kolisch (1996), Kelley & Walker (1959).
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from src.analytics.resource_leveling import LevelingConfig, ResourceLimit, level_resources

    config = LevelingConfig(
        resource_limits=[
            ResourceLimit(
                rsrc_id=rl.rsrc_id,
                max_units=rl.max_units,
                cost_per_unit_day=rl.cost_per_unit_day,
            )
            for rl in body.resource_limits
        ],
        priority_rule=body.priority_rule,
        max_project_extension_pct=body.max_project_extension_pct,
    )

    result = level_resources(schedule, config)

    return LevelingResponse(
        original_duration_days=result.original_duration_days,
        leveled_duration_days=result.leveled_duration_days,
        extension_days=result.extension_days,
        extension_pct=result.extension_pct,
        activity_shifts=[
            ActivityShiftSchema(
                task_id=s.task_id,
                task_code=s.task_code,
                task_name=s.task_name,
                original_start=s.original_start,
                leveled_start=s.leveled_start,
                shift_days=s.shift_days,
                duration_days=s.duration_days,
                resources=s.resources,
            )
            for s in result.activity_shifts
        ],
        resource_profiles=[
            ResourceProfileSchema(
                rsrc_id=rp.rsrc_id,
                rsrc_name=rp.rsrc_name,
                max_units=rp.max_units,
                peak_demand=rp.peak_demand,
                demand_by_day=rp.demand_by_day,
            )
            for rp in result.resource_profiles
        ],
        overloaded_periods=result.overloaded_periods,
        leveling_iterations=result.leveling_iterations,
        priority_rule=result.priority_rule,
        methodology=result.methodology,
        summary=result.summary,
    )


@router.get("/api/v1/projects/{project_id}/duration-prediction")
def get_duration_prediction(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> DurationPredictionResponse:
    """Predict project duration using ML trained on benchmark data.

    Uses Random Forest + Gradient Boosting ensemble trained on the
    benchmark database to predict expected project duration based on
    schedule structural features.

    References:
        AbdElMottaleb (2025), Breiman (2001), Friedman (2001).
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from src.analytics.benchmarks import BenchmarkMetrics
    from src.analytics.duration_prediction import predict_duration

    # Load benchmarks from DB or use empty list (model handles gracefully)
    benchmarks: list[BenchmarkMetrics] = []
    try:
        db_store = get_store()
        if hasattr(db_store, "get_benchmarks"):
            benchmarks = db_store.get_benchmarks()
    except Exception:
        pass

    result = predict_duration(schedule, benchmarks)

    return DurationPredictionResponse(
        predicted_duration_days=result.predicted_duration_days,
        confidence_low=result.confidence_low,
        confidence_high=result.confidence_high,
        actual_duration_days=result.actual_duration_days,
        delta_days=result.delta_days,
        model_r_squared=result.model_r_squared,
        training_samples=result.training_samples,
        feature_importances=result.feature_importances,
        methodology=result.methodology,
        summary=result.summary,
    )


@router.get("/api/v1/projects/{project_id}/scorecard")
def get_scorecard(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> ScorecardResponse:
    """Get a comprehensive schedule scorecard with letter grades.

    Aggregates DCMA 14-Point, Health Score, Risk Assessment, Logic
    Integrity, and Data Completeness into a weighted overall grade.

    References:
        DCMA 14-Point, GAO Schedule Guide, AACE RP 49R-06, AACE RP 57R-09.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from src.analytics.scorecard import calculate_scorecard

    result = calculate_scorecard(schedule)

    return ScorecardResponse(
        overall_score=result.overall_score,
        overall_grade=result.overall_grade,
        dimensions=[
            ScorecardDimensionSchema(
                name=d.name,
                score=d.score,
                grade=d.grade,
                description=d.description,
                details=d.details,
            )
            for d in result.dimensions
        ],
        recommendations=result.recommendations,
        methodology=result.methodology,
        summary=result.summary,
    )


@router.post("/api/v1/projects/{project_id}/optimize")
@limiter.limit(RATE_LIMIT_WRITE)
async def optimize_schedule_endpoint(
    request: Request,
    project_id: str,
    body: dict,
    job_id: str | None = None,
    _user: object = Depends(optional_auth),
) -> OptimizeResponse:
    """Optimize a resource-constrained schedule using Evolution Strategies.

    Evolves priority rules and resource allocation to minimize makespan.
    When ``job_id`` is supplied the caller receives live progress events on
    the WebSocket channel opened via ``POST /api/v1/jobs/progress/start``.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        project_id: The stored project identifier.
        body: Optimization config (population_size, parent_size, generations,
            resource_limits).
        job_id: Optional progress channel id. When set, the client should
            connect to ``GET /api/v1/ws/progress/{job_id}`` (WebSocket)
            BEFORE issuing this request to receive ``{"type": "progress",
            "done", "total", "pct"}`` events plus a final ``{"type": "done",
            "improvement_pct", "improvement_days"}``.

    References:
        Loncar (2023), Beyer & Schwefel (2002), Kolisch (1996).
    """
    import asyncio

    from ..progress import get_channel, get_channel_owner, publish, thread_safe_publisher

    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from src.analytics.evolution_optimizer import EvolutionConfig, optimize_schedule
    from src.analytics.resource_leveling import ResourceLimit

    limits = []
    for rl in body.get("resource_limits", []):
        limits.append(
            ResourceLimit(
                rsrc_id=rl.get("rsrc_id", ""),
                max_units=rl.get("max_units", 1.0),
            )
        )

    config = EvolutionConfig(
        population_size=body.get("population_size", 20),
        parent_size=body.get("parent_size", 5),
        generations=body.get("generations", 30),
        resource_limits=limits,
    )

    progress_callback = None
    if job_id:
        # ADR-0013 ownership check — mirror risk.py:180-191. The caller may
        # only use a job_id they own; the channel was bound on
        # POST /api/v1/jobs/progress/start.
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
        result = await asyncio.to_thread(optimize_schedule, schedule, config, progress_callback)
    except Exception as exc:
        if job_id:
            publish(job_id, {"type": "error", "message": str(exc)})
        raise HTTPException(status_code=500, detail=f"Optimization failed: {exc}")

    if job_id:
        publish(
            job_id,
            {
                "type": "done",
                "improvement_pct": result.improvement_pct,
                "improvement_days": result.improvement_days,
            },
        )

    # Issue #14: explicit mapping engine → public surface (Pydantic).
    # Engine emits best fitness only; mean is intentionally absent.
    convergence = [
        ConvergencePointSchema(generation=i + 1, best_fitness=float(f))
        for i, f in enumerate(result.convergence_history)
    ]
    shifted_activities: list[ActivityShiftSchema] = []
    if result.best_leveling is not None:
        shifted_activities = [
            ActivityShiftSchema(
                task_id=s.task_id,
                task_code=s.task_code,
                task_name=s.task_name,
                original_start=s.original_start,
                leveled_start=s.leveled_start,
                shift_days=s.shift_days,
                duration_days=s.duration_days,
                resources=s.resources,
            )
            for s in result.best_leveling.activity_shifts
        ]

    return OptimizeResponse(
        original_makespan=result.greedy_duration_days,
        optimized_makespan=result.best_duration_days,
        improvement_days=result.improvement_days,
        improvement_pct=result.improvement_pct,
        generations=result.generations_run,
        best_priority_rule=result.best_priority_rule,
        convergence=convergence,
        shifted_activities=shifted_activities,
        methodology=result.methodology,
        summary=result.summary,
    )


@router.get("/api/v1/projects/{project_id}/visualization")
def get_visualization(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Get 4D visualization data (WBS spatial x CPM temporal).

    Returns activities positioned by WBS group and CPM dates with
    color coding by status, float level, or critical path.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from src.analytics.visualization import build_visualization

    result = build_visualization(schedule)
    return asdict(result)
