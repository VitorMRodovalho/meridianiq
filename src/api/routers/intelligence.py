# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Intelligence router — health score, float trends, root cause, NLP, anomalies, delay prediction, alerts, dashboard."""

from __future__ import annotations

import os
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from ..auth import optional_auth
from ..deps import get_store
from ..schemas import (
    ActivityFloatTrendSchema,
    ActivityRiskSchema,
    AlertSchema,
    AlertsResponse,
    DashboardKPIs,
    DelayPredictionResponse,
    FloatTrendResponse,
    RiskFactorSchema,
    ScheduleHealthResponse,
)

router = APIRouter()


# ══════════════════════════════════════════════════════════
# Intelligence v0.8 — Health Score, Float Trends, Alerts, Dashboard
# ══════════════════════════════════════════════════════════


@router.get(
    "/api/v1/projects/{project_id}/health",
    response_model=ScheduleHealthResponse,
)
def get_project_health(
    project_id: str,
    baseline_id: str | None = None,
    _user: object = Depends(optional_auth),
) -> ScheduleHealthResponse:
    """Get the composite schedule health score for a project.

    Computes a 0-100 score combining DCMA structural quality, float
    health, logic integrity, and trend direction.  If ``baseline_id``
    is provided, the trend component uses the baseline for comparison.

    Args:
        project_id: The stored project identifier.
        baseline_id: Optional baseline project for trend analysis.

    Raises:
        HTTPException: If the project is not found.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    baseline = None
    if baseline_id:
        baseline = store.get(baseline_id)
        if baseline is None:
            raise HTTPException(status_code=404, detail="Baseline project not found")

    from src.analytics.health_score import HealthScoreCalculator

    calc = HealthScoreCalculator(schedule, baseline=baseline)
    score = calc.calculate()

    return ScheduleHealthResponse(
        overall=score.overall,
        dcma_component=score.dcma_component,
        float_component=score.float_component,
        logic_component=score.logic_component,
        trend_component=score.trend_component,
        dcma_raw=score.dcma_raw,
        float_raw=score.float_raw,
        logic_raw=score.logic_raw,
        trend_raw=score.trend_raw,
        rating=score.rating,
        trend_arrow=score.trend_arrow,
        details=score.details,
    )


@router.get(
    "/api/v1/projects/{project_id}/float-trends",
    response_model=FloatTrendResponse,
)
def get_float_trends(
    project_id: str,
    baseline_id: str | None = None,
    _user: object = Depends(optional_auth),
) -> FloatTrendResponse:
    """Get float trend data between a baseline and update schedule.

    Computes Float Erosion Index, Near-Critical Drift, CP Stability,
    and per-activity float deltas.

    Args:
        project_id: The update project identifier.
        baseline_id: The baseline project identifier.

    Raises:
        HTTPException: If projects are not found.
    """
    store = get_store()
    update = store.get(project_id)
    if update is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if not baseline_id:
        raise HTTPException(
            status_code=400,
            detail="baseline_id query parameter is required for float trend analysis",
        )

    baseline = store.get(baseline_id)
    if baseline is None:
        raise HTTPException(status_code=404, detail="Baseline project not found")

    from src.analytics.float_trends import FloatTrendAnalyzer

    analyzer = FloatTrendAnalyzer(baseline, update)
    result = analyzer.analyze()

    return FloatTrendResponse(
        fei=result.fei,
        near_critical_drift=result.near_critical_drift,
        cp_stability=result.cp_stability,
        activity_trends=[
            ActivityFloatTrendSchema(
                task_code=t.task_code,
                task_name=t.task_name,
                wbs_id=t.wbs_id,
                old_float_days=t.old_float_days,
                new_float_days=t.new_float_days,
                delta_days=t.delta_days,
                direction=t.direction,
                is_critical_baseline=t.is_critical_baseline,
                is_critical_update=t.is_critical_update,
                progress_pct=t.progress_pct,
            )
            for t in result.activity_trends
        ],
        wbs_velocity=result.wbs_velocity,
        thresholds=result.thresholds,
        days_between_updates=result.days_between_updates,
        total_matched=result.total_matched,
        summary=result.summary,
    )


@router.get("/api/v1/projects/{project_id}/root-cause")
def get_root_cause(
    project_id: str,
    activity_id: str | None = None,
    _user: object = Depends(optional_auth),
) -> dict:
    """Trace backwards through the dependency network to find the root cause.

    Starting from a target activity (or the project completion driver if
    not specified), walks backwards through driving predecessors to
    identify the originating delay event.

    Args:
        project_id: The stored project identifier.
        activity_id: Optional target activity ID. If omitted, uses the
            activity with the latest early finish.

    Returns:
        RootCauseResult as dict with the driving chain.

    Raises:
        HTTPException: If the project is not found.

    References:
        AACE RP 49R-06 — Identifying Critical Activities.
        AACE RP 29R-03 — Forensic Schedule Analysis.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from src.analytics.root_cause import analyze_root_cause

    result = analyze_root_cause(schedule, target_task_id=activity_id)
    return asdict(result)


@router.post("/api/v1/projects/{project_id}/ask")
async def ask_schedule(
    project_id: str,
    body: dict,
    _user: object = Depends(optional_auth),
) -> dict:
    """Ask a natural language question about a schedule.

    Uses Claude API to interpret the question and generate an answer
    grounded in the schedule's actual data. Does NOT send raw schedule
    data to the API — only a compact statistical summary.

    Args:
        project_id: The stored project identifier.
        body: JSON with ``question`` (required) and optional ``api_key``.

    Returns:
        Dict with ``answer``, ``question``, ``tokens_used``, ``model``.

    Raises:
        HTTPException: If project not found or API key missing.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    question = body.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    api_key = body.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Anthropic API key required. Pass api_key in body or set ANTHROPIC_API_KEY env var.",
        )

    from src.analytics.nlp_query import query_schedule

    try:
        result = await query_schedule(schedule, question, api_key=api_key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "question": result.question,
        "answer": result.answer,
        "model": result.model,
        "tokens_used": result.tokens_used,
    }


@router.get("/api/v1/projects/{project_id}/anomalies")
def get_anomalies(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Detect statistical anomalies in schedule data.

    Uses IQR and z-score methods to flag activities with unusual
    duration, float, progress, or relationship patterns.

    Args:
        project_id: The stored project identifier.

    Returns:
        AnomalyDetectionResult with anomalies sorted by severity.

    References:
        Tukey (1977) — Exploratory Data Analysis (IQR method).
        DCMA 14-Point Assessment — duration and float thresholds.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from src.analytics.anomaly_detection import detect_anomalies

    result = detect_anomalies(schedule)
    return asdict(result)


@router.get("/api/v1/projects/{project_id}/delay-prediction")
def get_delay_prediction(
    project_id: str,
    baseline_id: str | None = None,
    model: str = "rules",
    _user: object = Depends(optional_auth),
) -> DelayPredictionResponse:
    """Predict delay risk for all non-complete activities.

    Uses weighted multi-factor risk scoring with explainable risk factors.
    Optionally enhanced with trend features when a baseline is provided.

    Args:
        project_id: The stored project identifier.
        baseline_id: Optional earlier schedule for trend analysis.
        model: Prediction mode — ``"rules"`` (default) or ``"ml"``
            (Random Forest + Gradient Boosting ensemble).

    References:
        DCMA 14-Point Assessment, AACE RP 49R-06, GAO Schedule Guide,
        Gondia et al. (2021).
    """
    if model not in ("rules", "ml"):
        raise HTTPException(status_code=400, detail="model must be 'rules' or 'ml'")

    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    baseline = None
    if baseline_id:
        baseline = store.get(baseline_id)
        if baseline is None:
            raise HTTPException(status_code=404, detail="Baseline not found")

    from src.analytics.delay_prediction import predict_delays

    result = predict_delays(schedule, baseline=baseline, model=model)

    return DelayPredictionResponse(
        activity_risks=[
            ActivityRiskSchema(
                task_id=r.task_id,
                task_code=r.task_code,
                task_name=r.task_name,
                risk_score=r.risk_score,
                risk_level=r.risk_level,
                predicted_delay_days=r.predicted_delay_days,
                confidence=r.confidence,
                top_risk_factors=[
                    RiskFactorSchema(
                        name=f.name,
                        contribution=f.contribution,
                        description=f.description,
                        value=f.value,
                    )
                    for f in r.top_risk_factors
                ],
                is_critical_path=r.is_critical_path,
                wbs_id=r.wbs_id,
                float_risk=r.float_risk,
                progress_risk=r.progress_risk,
                logic_risk=r.logic_risk,
                duration_risk=r.duration_risk,
                network_risk=r.network_risk,
                trend_risk=r.trend_risk,
            )
            for r in result.activity_risks
        ],
        project_risk_score=result.project_risk_score,
        project_risk_level=result.project_risk_level,
        predicted_completion_delay=result.predicted_completion_delay,
        high_risk_count=result.high_risk_count,
        critical_risk_count=result.critical_risk_count,
        risk_distribution=result.risk_distribution,
        methodology=result.methodology,
        features_used=result.features_used,
        has_baseline=result.has_baseline,
        summary=result.summary,
    )


@router.get(
    "/api/v1/projects/{project_id}/alerts",
    response_model=AlertsResponse,
)
def get_project_alerts(
    project_id: str,
    baseline_id: str | None = None,
    _user: object = Depends(optional_auth),
) -> AlertsResponse:
    """Get early warning alerts for a project.

    Runs the 12-rule early warning engine comparing baseline and update
    schedules.  Produces prioritized alerts ranked by severity, confidence,
    and projected impact.

    Args:
        project_id: The update project identifier.
        baseline_id: The baseline project identifier.

    Raises:
        HTTPException: If projects are not found.
    """
    store = get_store()
    update = store.get(project_id)
    if update is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if not baseline_id:
        raise HTTPException(
            status_code=400,
            detail="baseline_id query parameter is required for early warning analysis",
        )

    baseline = store.get(baseline_id)
    if baseline is None:
        raise HTTPException(status_code=404, detail="Baseline project not found")

    from src.analytics.early_warning import EarlyWarningEngine

    engine = EarlyWarningEngine(baseline, update)
    result = engine.analyze()

    return AlertsResponse(
        alerts=[
            AlertSchema(
                rule_id=a.rule_id,
                severity=a.severity,
                title=a.title,
                description=a.description,
                affected_activities=a.affected_activities,
                projected_impact_days=a.projected_impact_days,
                confidence=a.confidence,
                alert_score=a.alert_score,
            )
            for a in result.alerts
        ],
        total_alerts=result.total_alerts,
        critical_count=result.critical_count,
        warning_count=result.warning_count,
        info_count=result.info_count,
        aggregate_score=result.aggregate_score,
        summary=result.summary,
    )


@router.get(
    "/api/v1/dashboard",
    response_model=DashboardKPIs,
)
def get_dashboard(_user: object = Depends(optional_auth)) -> DashboardKPIs:
    """Get portfolio-level dashboard KPIs.

    Returns total projects, average health score, active alerts count,
    and identifies the most critical project.  Computes health scores
    on-the-fly for all loaded projects.
    """
    from src.analytics.health_score import HealthScoreCalculator

    store = get_store()
    project_ids = store.list_ids()

    if not project_ids:
        return DashboardKPIs()

    health_scores: dict[str, float] = {}

    for pid in project_ids:
        schedule = store.get(pid)
        if schedule is None:
            continue

        try:
            calc = HealthScoreCalculator(schedule)
            score = calc.calculate()
            health_scores[pid] = score.overall
        except Exception:
            health_scores[pid] = 50.0

    most_critical_id = min(health_scores, key=health_scores.get) if health_scores else None
    most_critical_score = health_scores.get(most_critical_id, None) if most_critical_id else None

    avg_health = sum(health_scores.values()) / len(health_scores) if health_scores else 0.0

    return DashboardKPIs(
        total_projects=len(project_ids),
        active_alerts=0,
        avg_health_score=round(avg_health, 1),
        projects_trending_up=0,
        projects_trending_down=0,
        most_critical_project=most_critical_id,
        most_critical_score=most_critical_score,
    )
