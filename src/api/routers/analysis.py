# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Schedule Analysis router — DCMA, CPM, float, calendar, delay attribution."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from ..auth import optional_auth
from ..deps import get_store, get_tia_store
from ..schemas import (
    ComplianceCheckSchema,
    ContractCheckRequest,
    ContractCheckResponse,
    ContractProvisionSchema,
    ContractProvisionsResponse,
    CriticalPathActivity,
    CriticalPathResponse,
    FloatBucket,
    FloatDistributionResponse,
    MetricSchema,
    MilestoneSchema,
    MilestonesResponse,
    ValidationResponse,
)

from src.analytics.calendar_validation import validate_calendars
from src.analytics.contract import ContractComplianceChecker
from src.analytics.cpm import CPMCalculator
from src.analytics.dcma14 import DCMA14Analyzer
from src.analytics.delay_attribution import compute_delay_attribution
from src.analytics.schedule_view import build_schedule_view

router = APIRouter()


# ------------------------------------------------------------------
# DCMA 14-Point Validation
# ------------------------------------------------------------------


@router.get("/api/v1/projects/{project_id}/validation", response_model=ValidationResponse)
def get_validation(project_id: str, _user: object = Depends(optional_auth)) -> ValidationResponse:
    """Run DCMA 14-Point assessment for a project.

    Args:
        project_id: The stored project identifier.

    Raises:
        HTTPException: If the project is not found.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    analyzer = DCMA14Analyzer(schedule)
    dcma = analyzer.analyze()

    metrics = [
        MetricSchema(
            number=m.number,
            name=m.name,
            description=m.description,
            value=m.value,
            threshold=m.threshold,
            unit=m.unit,
            passed=m.passed,
            direction=m.direction,
            details=m.details,
        )
        for m in dcma.metrics
    ]

    return ValidationResponse(
        overall_score=dcma.overall_score,
        passed_count=dcma.passed_count,
        failed_count=dcma.failed_count,
        activity_count=dcma.activity_count,
        metrics=metrics,
    )


# ------------------------------------------------------------------
# Critical Path
# ------------------------------------------------------------------


@router.get(
    "/api/v1/projects/{project_id}/critical-path",
    response_model=CriticalPathResponse,
)
def get_critical_path(
    project_id: str, _user: object = Depends(optional_auth)
) -> CriticalPathResponse:
    """Compute and return the critical path for a project.

    Args:
        project_id: The stored project identifier.

    Raises:
        HTTPException: If the project is not found.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    cpm = CPMCalculator(schedule).calculate()

    cp_activities = [
        CriticalPathActivity(
            task_id=tid,
            task_code=cpm.activity_results[tid].task_code,
            task_name=cpm.activity_results[tid].task_name,
            duration=cpm.activity_results[tid].duration,
            early_start=cpm.activity_results[tid].early_start,
            early_finish=cpm.activity_results[tid].early_finish,
            total_float=cpm.activity_results[tid].total_float,
        )
        for tid in cpm.critical_path
        if tid in cpm.activity_results
    ]

    return CriticalPathResponse(
        project_duration=cpm.project_duration,
        critical_path=cp_activities,
        has_cycles=cpm.has_cycles,
    )


# ------------------------------------------------------------------
# Float Distribution
# ------------------------------------------------------------------


@router.get(
    "/api/v1/projects/{project_id}/float-distribution",
    response_model=FloatDistributionResponse,
)
def get_float_distribution(
    project_id: str, _user: object = Depends(optional_auth)
) -> FloatDistributionResponse:
    """Return float distribution buckets for a project.

    Buckets: critical (TF=0), near-critical (0-10d), moderate (10-20d),
    high (20-44d), excessive (>44d), negative.

    Args:
        project_id: The stored project identifier.

    Raises:
        HTTPException: If the project is not found.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Filter to countable activities (case-insensitive)
    countable = [
        t
        for t in schedule.activities
        if t.task_type.lower() not in ("tt_loe", "tt_wbs")
        and t.status_code.lower() != "tk_complete"
    ]

    total = len(countable)
    if total == 0:
        return FloatDistributionResponse(total_activities=0, buckets=[])

    # Define buckets in hours (8h/day)
    bucket_defs: list[tuple[str, float, float]] = [
        ("Negative (< 0)", float("-inf"), 0.0),
        ("Critical (= 0)", 0.0, 0.001),
        ("Near-Critical (0-10d)", 0.001, 80.001),
        ("Moderate (10-20d)", 80.001, 160.001),
        ("High (20-44d)", 160.001, 352.001),
        ("Excessive (> 44d)", 352.001, float("inf")),
    ]

    counts: dict[str, int] = {label: 0 for label, _, _ in bucket_defs}

    for task in countable:
        tf = task.total_float_hr_cnt
        if tf is None:
            continue
        for label, low, high in bucket_defs:
            if low <= tf < high:
                counts[label] += 1
                break

    buckets = [
        FloatBucket(
            range_label=label,
            count=counts[label],
            percentage=round((counts[label] / total) * 100, 1) if total else 0.0,
        )
        for label, _, _ in bucket_defs
    ]

    return FloatDistributionResponse(total_activities=total, buckets=buckets)


# ------------------------------------------------------------------
# Milestones
# ------------------------------------------------------------------


@router.get(
    "/api/v1/projects/{project_id}/milestones",
    response_model=MilestonesResponse,
)
def get_milestones(project_id: str, _user: object = Depends(optional_auth)) -> MilestonesResponse:
    """Return all milestone activities for a project.

    Args:
        project_id: The stored project identifier.

    Raises:
        HTTPException: If the project is not found.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Match milestones case-insensitively — P6 versions vary in case
    MILESTONE_TYPES = {"tt_mile", "tt_finmile"}
    milestones = [
        MilestoneSchema(
            task_id=t.task_id,
            task_code=t.task_code,
            task_name=t.task_name,
            task_type=t.task_type,
            status_code=t.status_code,
            act_start_date=t.act_start_date,
            act_end_date=t.act_end_date,
            early_start_date=t.early_start_date,
            early_end_date=t.early_end_date,
            target_start_date=t.target_start_date,
            target_end_date=t.target_end_date,
        )
        for t in schedule.activities
        if t.task_type.lower() in MILESTONE_TYPES
    ]

    return MilestonesResponse(milestones=milestones)


# ------------------------------------------------------------------
# Contract Compliance
# ------------------------------------------------------------------


@router.post("/api/v1/contract/check", response_model=ContractCheckResponse)
def contract_check(
    request: ContractCheckRequest, _user: object = Depends(optional_auth)
) -> ContractCheckResponse:
    """Run contract compliance checks against a TIA analysis.

    Evaluates each fragment against standard construction contract
    provisions per AIA A201, ConsensusDocs 200, and FIDIC conditions.

    Args:
        request: Contains the analysis_id to check.

    Raises:
        HTTPException: If the analysis is not found.
    """
    tia_store = get_tia_store()
    analysis = tia_store.get(request.analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=404, detail=f"TIA analysis not found: {request.analysis_id}"
        )

    checker = ContractComplianceChecker()
    checks = checker.check_all(analysis.fragments, analysis.results)

    check_schemas = [
        ComplianceCheckSchema(
            fragment_id=c.fragment_id,
            fragment_name=c.fragment_name,
            provision_id=c.provision.provision_id,
            provision_name=c.provision.name,
            provision_category=c.provision.category.value,
            status=c.status.value,
            finding=c.finding,
            recommendation=c.recommendation,
            details=c.details,
        )
        for c in checks
    ]

    warnings = sum(1 for c in checks if c.status.value == "warning")
    failures = sum(1 for c in checks if c.status.value == "fail")

    return ContractCheckResponse(
        analysis_id=request.analysis_id,
        checks=check_schemas,
        total_checks=len(checks),
        warnings=warnings,
        failures=failures,
    )


@router.get(
    "/api/v1/contract/provisions",
    response_model=ContractProvisionsResponse,
)
def list_contract_provisions(
    _user: object = Depends(optional_auth),
) -> ContractProvisionsResponse:
    """List default contract provisions used for compliance checking."""
    checker = ContractComplianceChecker()
    provisions = [
        ContractProvisionSchema(
            provision_id=p.provision_id,
            name=p.name,
            description=p.description,
            category=p.category.value,
            reference=p.reference,
            threshold_days=p.threshold_days,
            details=p.details,
        )
        for p in checker.provisions
    ]
    return ContractProvisionsResponse(provisions=provisions)


# ------------------------------------------------------------------
# Schedule View (Gantt viewer data)
# ------------------------------------------------------------------


@router.get("/api/v1/projects/{project_id}/schedule-view")
def get_schedule_view(
    project_id: str,
    baseline_id: str | None = None,
    force: bool = False,
    _user: object = Depends(optional_auth),
) -> dict:
    """Get pre-computed layout data for the interactive Gantt viewer.

    Returns WBS tree hierarchy, flattened activities with dates and
    indent levels, relationships, and summary metrics — all optimized
    for the frontend ScheduleViewer component.

    Results are cached after first computation (CPM is expensive).
    Pass ``force=true`` to recompute.

    Args:
        project_id: The schedule identifier.
        baseline_id: Optional baseline schedule for comparison bars.
        force: Force recomputation (bypass cache).

    Returns:
        ScheduleViewResult with WBS tree, activities, relationships, summary.

    References:
        AACE RP 49R-06 — Identifying Critical Activities.
        GAO Schedule Assessment Guide.
    """
    store = get_store()
    cache_key = f"schedule_view:{baseline_id or 'none'}"

    # Check cache first (skip if force=True)
    if not force:
        cached = store.get_analysis(project_id, cache_key)
        if cached:
            return cached

    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    baseline = store.get(baseline_id) if baseline_id else None
    result = build_schedule_view(schedule, baseline=baseline)
    result_dict = asdict(result)

    # Cache for future requests
    store.save_analysis(project_id, cache_key, result_dict)

    return result_dict


@router.get("/api/v1/projects/{project_id}/schedule-view/resources")
def get_schedule_resources(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Per-resource daily demand for histogram rendering below the Gantt.

    Returns ``as-scheduled`` demand curves (no leveling). Each profile is
    a flat array of daily unit counts aligned to the schedule's day 0.

    Args:
        project_id: The schedule identifier.

    Returns:
        Object with ``project_id``, ``total_days``, and ``resources`` list
        (each with ``rsrc_id``, ``rsrc_name``, ``peak_demand``,
        ``demand_by_day``).

    References:
        PMI Practice Standard for Scheduling — Resource Loading.
    """
    from src.analytics.resource_leveling import compute_resource_profiles

    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    profiles = compute_resource_profiles(schedule)
    total_days = max((len(p.demand_by_day) for p in profiles), default=0)
    return {
        "project_id": project_id,
        "total_days": total_days,
        "resource_count": len(profiles),
        "resources": [
            {
                "rsrc_id": p.rsrc_id,
                "rsrc_name": p.rsrc_name,
                "peak_demand": round(p.peak_demand, 2),
                "demand_by_day": [round(v, 2) for v in p.demand_by_day],
            }
            for p in profiles
        ],
    }


# ------------------------------------------------------------------
# Delay Attribution
# ------------------------------------------------------------------


@router.get("/api/v1/projects/{project_id}/delay-attribution")
def get_delay_attribution(
    project_id: str,
    baseline_id: str | None = None,
    _user: object = Depends(optional_auth),
) -> dict:
    """Compute delay attribution breakdown by responsible party.

    Aggregates delay by Owner, Contractor, Shared, Third Party, and
    Force Majeure. Uses TIA results if available, otherwise estimates
    from schedule characteristics.

    Args:
        project_id: The current/update schedule identifier.
        baseline_id: Optional baseline schedule for comparison.

    Returns:
        AttributionResult with per-party breakdown, excusable/non-excusable totals.

    References:
        AACE RP 29R-03, AACE RP 52R-06, SCL Protocol.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    baseline = store.get(baseline_id) if baseline_id else None

    result = compute_delay_attribution(schedule, baseline=baseline)
    return asdict(result)


# ------------------------------------------------------------------
# Calendar Validation
# ------------------------------------------------------------------


@router.get("/api/v1/projects/{project_id}/calendar-validation")
def get_calendar_validation(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Validate work calendar definitions for integrity and best practices.

    Checks default calendar existence, task coverage, hour consistency,
    non-standard calendars, orphaned definitions, and excessive diversity.

    Args:
        project_id: The stored project identifier.

    Returns:
        CalendarValidationResult with calendars, issues, score, and grade.

    References:
        DCMA 14-Point Check #13 — Calendar adequacy.
        GAO Schedule Assessment Guide — Reasonable parameters.
        AACE RP 49R-06 — Schedule Health Assessment.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = validate_calendars(schedule)
    return asdict(result)
