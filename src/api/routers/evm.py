# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""EVM (Earned Value Management) router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from src.analytics.evm import EVMAnalyzer

from ..auth import optional_auth
from ..deps import get_evm_store, get_store, limiter
from ..schemas import (
    EVMAnalysisSchema,
    EVMAnalysisSummarySchema,
    EVMListResponse,
    EVMMetricsSchema,
    ForecastResponse,
    HealthClassificationSchema,
    SCurvePointSchema,
    SCurveResponse,
    WBSDrillResponse,
    WBSMetricsSchema,
)

router = APIRouter()


def _evm_metrics_to_schema(m: Any) -> EVMMetricsSchema:
    """Convert an EVMMetrics dataclass to its Pydantic schema.

    Args:
        m: An ``EVMMetrics`` instance.

    Returns:
        An ``EVMMetricsSchema`` for JSON serialisation.
    """
    return EVMMetricsSchema(
        scope_name=m.scope_name,
        scope_id=m.scope_id,
        bac=round(m.bac, 2),
        pv=round(m.pv, 2),
        ev=round(m.ev, 2),
        ac=round(m.ac, 2),
        sv=round(m.sv, 2),
        cv=round(m.cv, 2),
        spi=round(m.spi, 3),
        cpi=round(m.cpi, 3),
        eac_cpi=round(m.eac_cpi, 2),
        eac_combined=round(m.eac_combined, 2),
        etc=round(m.etc, 2),
        vac=round(m.vac, 2),
        tcpi=round(m.tcpi, 3),
        percent_complete_ev=round(m.percent_complete_ev, 1),
        percent_spent=round(m.percent_spent, 1),
    )


def _evm_result_to_schema(result: Any, project_id: str = "") -> EVMAnalysisSchema:
    """Convert an EVMAnalysisResult to its Pydantic schema.

    Args:
        result: An ``EVMAnalysisResult`` instance.
        project_id: The project store identifier.

    Returns:
        An ``EVMAnalysisSchema`` for JSON serialisation.
    """
    wbs_schemas = [
        WBSMetricsSchema(
            wbs_id=w.wbs_id,
            wbs_name=w.wbs_name,
            metrics=_evm_metrics_to_schema(w.metrics),
            activity_count=w.activity_count,
        )
        for w in result.wbs_breakdown
    ]

    s_curve_schemas = [
        SCurvePointSchema(
            date=p.date,
            cumulative_pv=p.cumulative_pv,
            cumulative_ev=p.cumulative_ev,
            cumulative_ac=p.cumulative_ac,
        )
        for p in result.s_curve
    ]

    return EVMAnalysisSchema(
        analysis_id=result.analysis_id,
        project_name=result.project_name,
        project_id=project_id,
        data_date=result.data_date,
        metrics=_evm_metrics_to_schema(result.metrics),
        wbs_breakdown=wbs_schemas,
        s_curve=s_curve_schemas,
        schedule_health=HealthClassificationSchema(
            index_name=result.schedule_health.index_name,
            value=result.schedule_health.value,
            status=result.schedule_health.status,
            label=result.schedule_health.label,
        ),
        cost_health=HealthClassificationSchema(
            index_name=result.cost_health.index_name,
            value=result.cost_health.value,
            status=result.cost_health.status,
            label=result.cost_health.label,
        ),
        forecast=result.forecast,
        summary=result.summary,
    )


@router.post("/api/v1/evm/analyze/{project_id}", response_model=EVMAnalysisSchema)
@limiter.limit("10/minute")
def run_evm_analysis(
    request: Request, project_id: str, _user: object = Depends(optional_auth)
) -> EVMAnalysisSchema:
    """Run Earned Value Management analysis on a project.

    Computes SPI, CPI, SV, CV, EAC, ETC, VAC, TCPI from resource
    assignment cost data and activity physical percent complete.
    Per ANSI/EIA-748 and AACE RP 10S-90.

    Args:
        project_id: The stored project identifier.

    Raises:
        HTTPException: If the project is not found or analysis fails.
    """
    store = get_store()
    evm_store = get_evm_store()

    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    try:
        analyzer = EVMAnalyzer(schedule)
        result = analyzer.analyze()
        result.project_id = project_id
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"EVM analysis failed: {exc}")

    evm_store.add(result)
    return _evm_result_to_schema(result, project_id)


@router.get("/api/v1/evm/analyses", response_model=EVMListResponse)
def list_evm_analyses(_user: object = Depends(optional_auth)) -> EVMListResponse:
    """List all EVM analyses."""
    evm_store = get_evm_store()
    items = [EVMAnalysisSummarySchema(**a) for a in evm_store.list_all()]
    return EVMListResponse(analyses=items)


@router.get("/api/v1/evm/analyses/{analysis_id}", response_model=EVMAnalysisSchema)
def get_evm_analysis(analysis_id: str, _user: object = Depends(optional_auth)) -> EVMAnalysisSchema:
    """Get full EVM analysis with all metrics.

    Args:
        analysis_id: The stored analysis identifier.

    Raises:
        HTTPException: If the analysis is not found.
    """
    evm_store = get_evm_store()
    result = evm_store.get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="EVM analysis not found")

    return _evm_result_to_schema(result, result.project_id)


@router.get("/api/v1/evm/analyses/{analysis_id}/s-curve", response_model=SCurveResponse)
def get_evm_s_curve(analysis_id: str, _user: object = Depends(optional_auth)) -> SCurveResponse:
    """Get S-curve data for an EVM analysis.

    Returns time-phased cumulative PV, EV, and AC data points
    suitable for charting.

    Args:
        analysis_id: The stored analysis identifier.

    Raises:
        HTTPException: If the analysis is not found.
    """
    evm_store = get_evm_store()
    result = evm_store.get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="EVM analysis not found")

    points = [
        SCurvePointSchema(
            date=p.date,
            cumulative_pv=p.cumulative_pv,
            cumulative_ev=p.cumulative_ev,
            cumulative_ac=p.cumulative_ac,
        )
        for p in result.s_curve
    ]

    return SCurveResponse(analysis_id=analysis_id, points=points)


@router.get(
    "/api/v1/evm/analyses/{analysis_id}/wbs-drill",
    response_model=WBSDrillResponse,
)
def get_evm_wbs_drill(analysis_id: str, _user: object = Depends(optional_auth)) -> WBSDrillResponse:
    """Get WBS-level EVM breakdown for an analysis.

    Args:
        analysis_id: The stored analysis identifier.

    Raises:
        HTTPException: If the analysis is not found.
    """
    evm_store = get_evm_store()
    result = evm_store.get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="EVM analysis not found")

    wbs_schemas = [
        WBSMetricsSchema(
            wbs_id=w.wbs_id,
            wbs_name=w.wbs_name,
            metrics=_evm_metrics_to_schema(w.metrics),
            activity_count=w.activity_count,
        )
        for w in result.wbs_breakdown
    ]

    return WBSDrillResponse(analysis_id=analysis_id, wbs_breakdown=wbs_schemas)


@router.get(
    "/api/v1/evm/analyses/{analysis_id}/forecast",
    response_model=ForecastResponse,
)
def get_evm_forecast(analysis_id: str, _user: object = Depends(optional_auth)) -> ForecastResponse:
    """Get EAC scenario forecasts for an analysis.

    Returns multiple Estimate at Completion scenarios:
    - EAC (CPI): BAC / CPI
    - EAC (Combined): AC + (BAC - EV) / (CPI * SPI)
    - EAC (New ETC): AC + (BAC - EV)
    - ETC, VAC, TCPI

    Args:
        analysis_id: The stored analysis identifier.

    Raises:
        HTTPException: If the analysis is not found.
    """
    evm_store = get_evm_store()
    result = evm_store.get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="EVM analysis not found")

    return ForecastResponse(
        analysis_id=analysis_id,
        **result.forecast,
    )
