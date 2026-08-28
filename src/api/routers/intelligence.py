# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Intelligence router — health score, float trends, root cause, NLP, anomalies, delay prediction, alerts, dashboard."""

from __future__ import annotations

import logging
import os
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import optional_auth
from ..deps import RATE_LIMIT_READ, RATE_LIMIT_WRITE, get_store, limiter
from ..kpi_helpers import schedule_kpi_bundle
from ..schemas import (
    ActivityFloatTrendSchema,
    ActivityRiskSchema,
    AlertSchema,
    AlertsResponse,
    DashboardKPIs,
    DelayPredictionResponse,
    FloatTrendResponse,
    NLPQueryRequest,
    NLPQueryResponse,
    RiskFactorSchema,
    ScheduleHealthResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Hard cap on how many projects one dashboard request will score. Each project
# costs a full schedule reconstruction (tens of sequential PostgREST
# round-trips, ~100MB transient RSS at production scale), and the endpoint runs
# on the anyio threadpool with no cancellation when the client disconnects — an
# uncapped loop over a large portfolio is an OOM vector on a 2GB machine.
# The response reports `truncated` so a capped aggregate is never mistaken for
# a complete one.
_DASHBOARD_MAX_PROJECTS = 50


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


@router.post(
    "/api/v1/projects/{project_id}/ask",
    response_model=NLPQueryResponse,
)
@limiter.limit(RATE_LIMIT_WRITE)
async def ask_schedule(
    request: Request,
    project_id: str,
    body: NLPQueryRequest,
    _user: object = Depends(optional_auth),
) -> NLPQueryResponse:
    """Ask a natural language question about a schedule.

    Uses Claude API to interpret the question and generate an answer
    grounded in the schedule's actual data. Does NOT send raw schedule
    data to the API — only a compact statistical summary.

    Args:
        project_id: The stored project identifier.
        body: ``question`` (required) and optional ``api_key``.

    Returns:
        NLPQueryResponse with ``answer``, ``question``, ``tokens_used``, ``model``.

    Raises:
        HTTPException: If project not found, API key missing, or upstream call fails.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    api_key = body.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Anthropic API key required. Pass api_key in body or set ANTHROPIC_API_KEY env var.",
        )

    from src.analytics.nlp_query import query_schedule

    try:
        result = await query_schedule(schedule, question, api_key=api_key)
    except Exception as exc:
        is_dev = os.getenv("ENVIRONMENT", "development") == "development"
        detail = f"NLP query failed: {exc}" if is_dev else "NLP query failed"
        raise HTTPException(status_code=502, detail=detail) from exc

    return NLPQueryResponse(
        question=result.question,
        answer=result.answer,
        model=result.model,
        tokens_used=result.tokens_used,
    )


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
@limiter.limit(RATE_LIMIT_READ)
def get_dashboard(request: Request, _user: object = Depends(optional_auth)) -> DashboardKPIs:
    """Get portfolio-level dashboard KPIs.

    Aggregates the per-project Health Score (``src/analytics/health_score.py``,
    thresholds aligned with the GAO Schedule Assessment Guide's 4
    characteristics) across the caller's portfolio:

    - ``avg_health_score``  — mean composite health over the SCORED projects.
      Read it together with ``scored_projects``: an average of 0.0 over 0
      scored projects means "nothing could be scored", not "the portfolio is
      failing".
    - ``scored_projects``   — how many projects contributed to the average.
      ``total_projects`` counts every row the caller owns, including
      ``pending`` / ``failed`` uploads that have no schedule to score.
    - ``active_alerts``     — projects rated ``poor`` (health < 50, i.e. GAO
      "significant gaps in 2+ characteristics").

      NOTE: this counts PROJECTS, and is a different unit and criterion from
      the ``total_alerts`` on ``GET /api/v1/projects/{id}/alerts``, which
      counts individual rule hits from the 12-rule EarlyWarning engine
      (GAO Schedule Assessment Guide §9). The two numbers are not
      reconcilable and are not meant to be. The EarlyWarning engine requires
      a (baseline, update) pair, which a portfolio rollup does not have.
    - ``most_critical_project`` — project_id of the lowest-scoring project,
      with its score. Ties break on project_id so the choice is stable across
      requests. The frontend resolves the id to a display name.

    ``projects_trending_up`` / ``_down`` are always ``None``: the trend arrow
    comes from ``HealthScoreCalculator``, which needs a baseline to compute it
    (``health_score.py::_compute_trend_score`` returns a neutral 50.0 without
    one, which ``_classify_trend_arrow`` always maps to "→"). ``schedule_kpi_bundle``
    deliberately runs baseline-free, so the portfolio rollup cannot produce a
    direction. Returning ``None`` rather than ``0`` keeps that honest — an
    earlier revision of this endpoint reported computed zeros that no input
    could ever move.

    Per-project compute is delegated to ``schedule_kpi_bundle``, which is
    memoised for 120s per ``(project_id, user_id)`` and is the same path used
    by ``/api/v1/programs/{id}/rollup`` and ``/api/v1/bi/projects``.

    COST: this is O(projects) and the dominant term is I/O — reconstructing one
    production-scale schedule (~8k activities) costs tens of sequential
    PostgREST round-trips and ~100MB of transient RSS. Hence the read rate
    limit, the ``ready``-only filter, and the ``_DASHBOARD_MAX_PROJECTS`` cap.
    Serving this from ``schedule_derived_artifacts`` (migration 023) instead of
    re-running the engines is the real fix; see issue tracker.
    """
    store = get_store()
    user_id = _user["id"] if _user else None
    all_projects = store.list_all(user_id=user_id)

    if not all_projects:
        return DashboardKPIs()

    # Only `ready` projects have a schedule to score. Including `pending` /
    # `failed` rows would inflate `total_projects` relative to the scored set
    # AND pay a full `store.get()` for a project that cannot contribute.
    scorable = [p for p in all_projects if p.get("status") in (None, "ready")]
    truncated = len(scorable) > _DASHBOARD_MAX_PROJECTS
    if truncated:
        logger.warning(
            "Dashboard aggregation capped at %d of %d scorable projects",
            _DASHBOARD_MAX_PROJECTS,
            len(scorable),
        )
        scorable = scorable[:_DASHBOARD_MAX_PROJECTS]

    scores: list[float] = []
    active_alerts = 0
    most_critical_project: str | None = None
    most_critical_score: float | None = None

    for project in scorable:
        project_id = project.get("project_id") or project.get("id") or ""
        if not project_id:
            continue

        # The bundle guards each analytics engine, but the store call inside it
        # (ownership check + row fetch) is not guarded. A single transient
        # PostgREST error must not discard every project already aggregated.
        try:
            bundle = schedule_kpi_bundle(project_id, user_id)
        except Exception:
            logger.warning("Dashboard KPI bundle failed for project %s", project_id)
            continue

        score = bundle.get("health_score")
        if score is None:
            continue

        score = float(score)
        scores.append(score)

        if bundle.get("health_rating") == "poor":
            active_alerts += 1

        # Strict `<` alone is order-dependent, and neither store applies an
        # ORDER BY — tie-break on project_id so repeated requests agree.
        if (
            most_critical_score is None
            or score < most_critical_score
            or (score == most_critical_score and project_id < (most_critical_project or ""))
        ):
            most_critical_score = score
            most_critical_project = project_id

    return DashboardKPIs(
        total_projects=len(all_projects),
        scored_projects=len(scores),
        truncated=truncated,
        active_alerts=active_alerts,
        avg_health_score=round(sum(scores) / len(scores), 1) if scores else 0.0,
        projects_trending_up=None,
        projects_trending_down=None,
        most_critical_project=most_critical_project,
        most_critical_score=most_critical_score,
    )
