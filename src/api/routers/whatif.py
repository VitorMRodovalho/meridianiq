# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""What-if router — scenario analysis, Pareto, leveling, prediction, scorecard."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from ..auth import optional_auth
from ..deps import get_store, limiter
from ..schemas import (
    ActivityImpactSchema,
    ActivityShiftSchema,
    DurationPredictionResponse,
    LevelingRequest,
    LevelingResponse,
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
def run_what_if(
    project_id: str,
    request: WhatIfRequest,
    _user: object = Depends(optional_auth),
) -> WhatIfResponse:
    """Run a what-if scenario on a project schedule.

    Applies duration adjustments and re-runs CPM to determine impact on
    project duration, critical path, and per-activity dates.  Supports
    deterministic (single run) and probabilistic (N iterations with ranges).

    Args:
        project_id: The stored project identifier.
        request: Scenario definition with adjustments and iteration count.

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
        name=request.name,
        adjustments=[
            DurationAdjustment(
                target=a.target,
                pct_change=a.pct_change,
                min_pct=a.min_pct,
                max_pct=a.max_pct,
            )
            for a in request.adjustments
        ],
        iterations=request.iterations,
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
def run_pareto_analysis(
    project_id: str,
    request: ParetoRequest,
    _user: object = Depends(optional_auth),
) -> ParetoResponse:
    """Run time-cost Pareto analysis across multiple scenarios.

    Identifies the Pareto-optimal frontier of non-dominated solutions
    on the time-vs-cost plane.

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
        for cs in request.scenarios
    ]

    result = analyze_pareto(schedule, scenarios, base_cost=request.base_cost)

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
def run_resource_leveling(
    project_id: str,
    request: LevelingRequest,
    _user: object = Depends(optional_auth),
) -> LevelingResponse:
    """Run resource-constrained scheduling using Serial SGS.

    Levels resources by scheduling activities at their earliest feasible
    start, respecting both precedence and resource capacity constraints.

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
            for rl in request.resource_limits
        ],
        priority_rule=request.priority_rule,
        max_project_extension_pct=request.max_project_extension_pct,
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
@limiter.limit("5/minute")
def optimize_schedule_endpoint(
    project_id: str,
    request: dict,
    _user: object = Depends(optional_auth),
) -> dict:
    """Optimize a resource-constrained schedule using Evolution Strategies.

    Evolves priority rules and resource allocation to minimize makespan.

    References:
        Loncar (2023), Beyer & Schwefel (2002), Kolisch (1996).
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")


    from src.analytics.evolution_optimizer import EvolutionConfig, optimize_schedule
    from src.analytics.resource_leveling import ResourceLimit

    limits = []
    for rl in request.get("resource_limits", []):
        limits.append(
            ResourceLimit(
                rsrc_id=rl.get("rsrc_id", ""),
                max_units=rl.get("max_units", 1.0),
            )
        )

    config = EvolutionConfig(
        population_size=request.get("population_size", 20),
        parent_size=request.get("parent_size", 5),
        generations=request.get("generations", 30),
        resource_limits=limits,
    )
    result = optimize_schedule(schedule, config)
    data = asdict(result)
    data.pop("best_leveling", None)
    return data


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
