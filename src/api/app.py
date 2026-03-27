# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""FastAPI application for MeridianIQ.

Provides REST endpoints for uploading XER files, querying parsed
schedule data, running DCMA assessments, CPM analysis, comparing
schedule versions, and forensic (CPA/window) analysis.
"""
from __future__ import annotations

import io
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.analytics.comparison import ScheduleComparison
from src.analytics.contract import ContractComplianceChecker
from src.analytics.cpm import CPMCalculator
from src.analytics.dcma14 import DCMA14Analyzer
from src.analytics.evm import EVMAnalyzer
from src.analytics.forensics import ForensicAnalyzer
from src.analytics.risk import (
    DistributionType,
    DurationRisk,
    MonteCarloSimulator,
    RiskEvent,
    SimulationConfig,
)
from src.analytics.tia import (
    DelayFragment,
    FragmentActivity,
    ResponsibleParty,
    TimeImpactAnalyzer,
)
from src.parser.models import ParsedSchedule
from src.parser.xer_reader import XERReader

from .schemas import (
    ActivityChangeSchema,
    ActivitySchema,
    CodeRestructuringSchema,
    CompareRequest,
    CompareResponse,
    ComplianceCheckSchema,
    ContractCheckRequest,
    ContractCheckResponse,
    ContractProvisionSchema,
    ContractProvisionsResponse,
    CreateTimelineRequest,
    CriticalPathActivity,
    CriticalPathResponse,
    DelayFragmentSchema,
    DelayTrendPoint,
    DelayTrendResponse,
    EVMAnalysisSchema,
    EVMAnalysisSummarySchema,
    EVMListResponse,
    EVMMetricsSchema,
    ForecastResponse,
    FloatBucket,
    FloatChangeSchema,
    FloatDistributionResponse,
    FragmentActivitySchema,
    HealthClassificationSchema,
    HealthResponse,
    ManipulationFlagSchema,
    MatchStatsSchema,
    MetricSchema,
    MilestoneSchema,
    MilestonesResponse,
    ProjectDetailResponse,
    ProjectListItem,
    ProjectListResponse,
    ProjectSummary,
    RelationshipChangeSchema,
    RelationshipSchema,
    SCurvePointSchema,
    SCurveResponse,
    TIAAnalysisSchema,
    TIAAnalysisSummarySchema,
    TIAAnalyzeRequest,
    TIAListResponse,
    TIAResultSchema,
    TIASummaryResponse,
    TimelineDetailSchema,
    TimelineListResponse,
    TimelineSummarySchema,
    ValidationResponse,
    WBSDrillResponse,
    WBSLevelCount,
    WBSMetricsSchema,
    WBSStats,
    WindowSchema,
    # Risk schemas
    CriticalityEntrySchema,
    CriticalityResponse,
    DurationRiskSchema,
    HistogramBinSchema,
    HistogramResponse,
    PValueSchema,
    RiskEventSchema,
    RiskSCurvePointSchema,
    RiskSCurveResponse,
    RunSimulationRequest,
    SensitivityEntrySchema,
    SimulationConfigSchema,
    SimulationListResponse,
    SimulationResultSchema,
    SimulationSummarySchema,
    TornadoResponse,
)
from .storage import EVMStore, ProjectStore, RiskStore, TIAStore, TimelineStore

app = FastAPI(
    title="MeridianIQ",
    description="The intelligence standard for project schedules",
    version="0.6.0-dev",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory stores (singletons for the app lifetime)
_store = ProjectStore()
_timeline_store = TimelineStore()
_tia_store = TIAStore()
_evm_store = EVMStore()
_risk_store = RiskStore()


def get_store() -> ProjectStore:
    """Return the global project store.

    Exposed as a function so tests can replace it via monkeypatching.
    """
    return _store


def get_timeline_store() -> TimelineStore:
    """Return the global timeline store.

    Exposed as a function so tests can replace it via monkeypatching.
    """
    return _timeline_store


def get_tia_store() -> TIAStore:
    """Return the global TIA store.

    Exposed as a function so tests can replace it via monkeypatching.
    """
    return _tia_store


def get_evm_store() -> EVMStore:
    """Return the global EVM store.

    Exposed as a function so tests can replace it via monkeypatching.
    """
    return _evm_store


def get_risk_store() -> RiskStore:
    """Return the global risk simulation store.

    Exposed as a function so tests can replace it via monkeypatching.
    """
    return _risk_store


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------


@app.get("/api/v1/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()


# ------------------------------------------------------------------
# Upload
# ------------------------------------------------------------------


@app.post("/api/v1/upload", response_model=ProjectSummary)
async def upload_xer(file: UploadFile = File(...)) -> ProjectSummary:
    """Upload an XER file, parse it, and store the result.

    Args:
        file: The uploaded .xer file.

    Returns:
        A summary of the parsed project.

    Raises:
        HTTPException: If the file is not a valid XER file.
    """
    if file.filename and not file.filename.lower().endswith(".xer"):
        raise HTTPException(status_code=400, detail="File must have .xer extension")

    xer_bytes = await file.read()
    if not xer_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    # Write to a temporary file for the parser (it expects a file path)
    try:
        with tempfile.NamedTemporaryFile(suffix=".xer", delete=False) as tmp:
            tmp.write(xer_bytes)
            tmp_path = Path(tmp.name)

        reader = XERReader(tmp_path)
        schedule = reader.parse()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse XER file: {exc}")
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass

    if not schedule.activities:
        raise HTTPException(status_code=400, detail="XER file contains no activities")

    store = get_store()
    project_id = store.add(schedule, xer_bytes)

    data_date = None
    name = ""
    if schedule.projects:
        proj = schedule.projects[0]
        name = proj.proj_short_name
        dd = proj.last_recalc_date or proj.sum_data_date
        if dd:
            data_date = dd.isoformat()

    return ProjectSummary(
        project_id=project_id,
        name=name,
        activity_count=len(schedule.activities),
        relationship_count=len(schedule.relationships),
        calendar_count=len(schedule.calendars),
        wbs_count=len(schedule.wbs_nodes),
        data_date=data_date,
    )


# ------------------------------------------------------------------
# Project listing
# ------------------------------------------------------------------


@app.get("/api/v1/projects", response_model=ProjectListResponse)
def list_projects() -> ProjectListResponse:
    """List all uploaded projects."""
    store = get_store()
    items = [ProjectListItem(**p) for p in store.list_all()]
    return ProjectListResponse(projects=items)


# ------------------------------------------------------------------
# Project detail
# ------------------------------------------------------------------


@app.get("/api/v1/projects/{project_id}", response_model=ProjectDetailResponse)
def get_project(project_id: str) -> ProjectDetailResponse:
    """Get full project data for a given project_id.

    Args:
        project_id: The stored project identifier.

    Raises:
        HTTPException: If the project is not found.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    data_date = None
    name = ""
    if schedule.projects:
        proj = schedule.projects[0]
        name = proj.proj_short_name
        dd = proj.last_recalc_date or proj.sum_data_date
        if dd:
            data_date = dd.isoformat()

    activities = [
        ActivitySchema(
            task_id=t.task_id,
            task_code=t.task_code,
            task_name=t.task_name,
            task_type=t.task_type,
            status_code=t.status_code,
            total_float_hr_cnt=t.total_float_hr_cnt,
            remain_drtn_hr_cnt=t.remain_drtn_hr_cnt,
            target_drtn_hr_cnt=t.target_drtn_hr_cnt,
            act_start_date=t.act_start_date,
            act_end_date=t.act_end_date,
            early_start_date=t.early_start_date,
            early_end_date=t.early_end_date,
            late_start_date=t.late_start_date,
            late_end_date=t.late_end_date,
        )
        for t in schedule.activities
    ]

    relationships = [
        RelationshipSchema(
            task_id=r.task_id,
            pred_task_id=r.pred_task_id,
            pred_type=r.pred_type,
            lag_hr_cnt=r.lag_hr_cnt,
        )
        for r in schedule.relationships
    ]

    # Compute WBS hierarchy statistics
    wbs_stats = _compute_wbs_stats(schedule)

    return ProjectDetailResponse(
        project_id=project_id,
        name=name,
        data_date=data_date,
        activities=activities,
        relationships=relationships,
        wbs_stats=wbs_stats,
    )


def _compute_wbs_stats(schedule: ParsedSchedule) -> WBSStats:
    """Compute WBS hierarchy depth and activity distribution."""
    wbs_nodes = schedule.wbs_nodes
    if not wbs_nodes:
        return WBSStats()

    # Build parent→children map and find root(s)
    wbs_by_id: dict[str, Any] = {w.wbs_id: w for w in wbs_nodes}
    child_ids: set[str] = set()
    for w in wbs_nodes:
        if w.parent_wbs_id and w.parent_wbs_id != w.wbs_id:
            child_ids.add(w.wbs_id)

    # Calculate depth for each WBS node via BFS from roots
    roots = [w for w in wbs_nodes if w.wbs_id not in child_ids
             or w.proj_node_flag.upper() == "Y"]
    levels: dict[str, int] = {}
    queue = [(r.wbs_id, 1) for r in roots]
    for wbs_id, level in queue:
        if wbs_id in levels:
            continue
        levels[wbs_id] = level
        # Find children
        for w in wbs_nodes:
            if w.parent_wbs_id == wbs_id and w.wbs_id != wbs_id:
                queue.append((w.wbs_id, level + 1))

    # Assign level 1 to any unvisited nodes (orphans)
    for w in wbs_nodes:
        if w.wbs_id not in levels:
            levels[w.wbs_id] = 1

    max_depth = max(levels.values()) if levels else 0

    # Count by level
    level_counts: dict[int, int] = {}
    for lvl in levels.values():
        level_counts[lvl] = level_counts.get(lvl, 0) + 1
    by_level = [
        WBSLevelCount(level=lvl, count=cnt)
        for lvl, cnt in sorted(level_counts.items())
    ]

    # Activities per WBS node
    act_per_wbs: dict[str, int] = {w.wbs_id: 0 for w in wbs_nodes}
    for t in schedule.activities:
        if t.wbs_id in act_per_wbs:
            act_per_wbs[t.wbs_id] += 1

    counts = list(act_per_wbs.values())
    no_activities = sum(1 for c in counts if c == 0)
    non_zero = [c for c in counts if c > 0]

    return WBSStats(
        total_elements=len(wbs_nodes),
        max_depth=max_depth,
        by_level=by_level,
        avg_activities_per_wbs=round(sum(counts) / len(counts), 1) if counts else 0.0,
        min_activities_per_wbs=min(non_zero) if non_zero else 0,
        max_activities_per_wbs=max(non_zero) if non_zero else 0,
        wbs_with_no_activities=no_activities,
    )


# ------------------------------------------------------------------
# DCMA Validation
# ------------------------------------------------------------------


@app.get("/api/v1/projects/{project_id}/validation", response_model=ValidationResponse)
def get_validation(project_id: str) -> ValidationResponse:
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


@app.get(
    "/api/v1/projects/{project_id}/critical-path",
    response_model=CriticalPathResponse,
)
def get_critical_path(project_id: str) -> CriticalPathResponse:
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


@app.get(
    "/api/v1/projects/{project_id}/float-distribution",
    response_model=FloatDistributionResponse,
)
def get_float_distribution(project_id: str) -> FloatDistributionResponse:
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
        t for t in schedule.activities
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


@app.get(
    "/api/v1/projects/{project_id}/milestones",
    response_model=MilestonesResponse,
)
def get_milestones(project_id: str) -> MilestonesResponse:
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
# Compare
# ------------------------------------------------------------------


@app.post("/api/v1/compare", response_model=CompareResponse)
def compare_schedules(request: CompareRequest) -> CompareResponse:
    """Compare two uploaded projects (baseline vs update).

    Args:
        request: Contains baseline_id and update_id.

    Raises:
        HTTPException: If either project is not found.
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

    comparison = ScheduleComparison(baseline, update)
    result = comparison.compare()

    return CompareResponse(
        activities_added=[
            ActivityChangeSchema(**asdict(c)) for c in result.activities_added
        ],
        activities_deleted=[
            ActivityChangeSchema(**asdict(c)) for c in result.activities_deleted
        ],
        activity_modifications=[
            ActivityChangeSchema(**asdict(c)) for c in result.activity_modifications
        ],
        duration_changes=[
            ActivityChangeSchema(**asdict(c)) for c in result.duration_changes
        ],
        relationships_added=[
            RelationshipChangeSchema(**asdict(c)) for c in result.relationships_added
        ],
        relationships_deleted=[
            RelationshipChangeSchema(**asdict(c)) for c in result.relationships_deleted
        ],
        relationships_modified=[
            RelationshipChangeSchema(**asdict(c)) for c in result.relationships_modified
        ],
        significant_float_changes=[
            FloatChangeSchema(**asdict(c)) for c in result.significant_float_changes
        ],
        constraint_changes=[
            ActivityChangeSchema(**asdict(c)) for c in result.constraint_changes
        ],
        manipulation_flags=[
            ManipulationFlagSchema(**asdict(c)) for c in result.manipulation_flags
        ],
        code_restructuring=[
            CodeRestructuringSchema(**asdict(c)) for c in result.code_restructuring
        ],
        match_stats=MatchStatsSchema(**asdict(result.match_stats)),
        changed_percentage=result.changed_percentage,
        critical_path_changed=result.critical_path_changed,
        activities_joined_cp=result.activities_joined_cp,
        activities_left_cp=result.activities_left_cp,
        summary=result.summary,
    )


# ------------------------------------------------------------------
# Forensic Analysis (CPA / Window Analysis)
# ------------------------------------------------------------------


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
    )


@app.post(
    "/api/v1/forensic/create-timeline",
    response_model=TimelineDetailSchema,
)
def create_timeline(request: CreateTimelineRequest) -> TimelineDetailSchema:
    """Create a forensic CPA timeline from multiple schedule updates.

    Fetches each referenced project from the store, sorts by data date,
    runs the ``ForensicAnalyzer``, stores the result, and returns the
    full timeline.

    Args:
        request: Contains a list of project_ids (minimum 2).

    Raises:
        HTTPException: If any project is not found or analysis fails.
    """
    store = get_store()
    tl_store = get_timeline_store()

    schedules: list[ParsedSchedule] = []
    for pid in request.project_ids:
        schedule = store.get(pid)
        if schedule is None:
            raise HTTPException(
                status_code=404, detail=f"Project not found: {pid}"
            )
        schedules.append(schedule)

    try:
        analyzer = ForensicAnalyzer(schedules, list(request.project_ids))
        timeline = analyzer.analyze()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Forensic analysis failed: {exc}"
        )

    tid = tl_store.add(timeline)

    return TimelineDetailSchema(
        timeline_id=tid,
        project_name=timeline.project_name,
        schedule_count=timeline.schedule_count,
        total_delay_days=timeline.total_delay_days,
        contract_completion=(
            timeline.contract_completion.isoformat()
            if timeline.contract_completion
            else None
        ),
        current_completion=(
            timeline.current_completion.isoformat()
            if timeline.current_completion
            else None
        ),
        windows=[_window_to_schema(w) for w in timeline.windows],
        summary=timeline.summary,
    )


@app.get(
    "/api/v1/forensic/timelines",
    response_model=TimelineListResponse,
)
def list_timelines() -> TimelineListResponse:
    """List all forensic timelines."""
    tl_store = get_timeline_store()
    items = [TimelineSummarySchema(**t) for t in tl_store.list_all()]
    return TimelineListResponse(timelines=items)


@app.get(
    "/api/v1/forensic/timelines/{timeline_id}",
    response_model=TimelineDetailSchema,
)
def get_timeline(timeline_id: str) -> TimelineDetailSchema:
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
            timeline.contract_completion.isoformat()
            if timeline.contract_completion
            else None
        ),
        current_completion=(
            timeline.current_completion.isoformat()
            if timeline.current_completion
            else None
        ),
        windows=[_window_to_schema(w) for w in timeline.windows],
        summary=timeline.summary,
    )


@app.get(
    "/api/v1/forensic/timelines/{timeline_id}/delay-trend",
    response_model=DelayTrendResponse,
)
def get_delay_trend(timeline_id: str) -> DelayTrendResponse:
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
                data_date=(
                    wr.window.end_date.isoformat() if wr.window.end_date else None
                ),
                completion_date=(
                    wr.completion_date_end.isoformat()
                    if wr.completion_date_end
                    else None
                ),
                delay_days=wr.delay_days,
                cumulative_delay=wr.cumulative_delay,
            )
        )

    return DelayTrendResponse(
        timeline_id=timeline.timeline_id,
        contract_completion=(
            timeline.contract_completion.isoformat()
            if timeline.contract_completion
            else None
        ),
        points=points,
    )


# ------------------------------------------------------------------
# TIA (Time Impact Analysis)
# ------------------------------------------------------------------


def _fragment_schema_to_model(schema: DelayFragmentSchema) -> DelayFragment:
    """Convert a DelayFragmentSchema to a DelayFragment dataclass.

    Args:
        schema: The Pydantic schema from the request body.

    Returns:
        A ``DelayFragment`` dataclass instance.
    """
    activities = [
        FragmentActivity(
            fragment_activity_id=a.fragment_activity_id,
            name=a.name,
            duration_hours=a.duration_hours,
            predecessors=a.predecessors,
            successors=a.successors,
        )
        for a in schema.activities
    ]

    return DelayFragment(
        fragment_id=schema.fragment_id,
        name=schema.name,
        description=schema.description,
        responsible_party=ResponsibleParty(schema.responsible_party),
        activities=activities,
    )


def _analysis_to_schema(analysis: Any) -> TIAAnalysisSchema:
    """Convert a TIAAnalysis dataclass to its Pydantic schema.

    Args:
        analysis: A ``TIAAnalysis`` instance.

    Returns:
        A ``TIAAnalysisSchema`` for JSON serialisation.
    """
    fragment_schemas = [
        DelayFragmentSchema(
            fragment_id=f.fragment_id,
            name=f.name,
            description=f.description,
            responsible_party=f.responsible_party.value,
            activities=[
                FragmentActivitySchema(
                    fragment_activity_id=a.fragment_activity_id,
                    name=a.name,
                    duration_hours=a.duration_hours,
                    predecessors=a.predecessors,
                    successors=a.successors,
                )
                for a in f.activities
            ],
        )
        for f in analysis.fragments
    ]

    result_schemas = [
        TIAResultSchema(
            fragment_id=r.fragment.fragment_id,
            fragment_name=r.fragment.name,
            responsible_party=r.fragment.responsible_party.value,
            unimpacted_completion_days=r.unimpacted_completion_days,
            impacted_completion_days=r.impacted_completion_days,
            delay_days=r.delay_days,
            critical_path_affected=r.critical_path_affected,
            float_consumed_hours=r.float_consumed_hours,
            delay_type=r.delay_type.value,
            concurrent_with=r.concurrent_with,
            impacted_driving_path=r.impacted_driving_path,
        )
        for r in analysis.results
    ]

    return TIAAnalysisSchema(
        analysis_id=analysis.analysis_id,
        project_name=analysis.project_name,
        base_project_id=analysis.base_project_id,
        fragments=fragment_schemas,
        results=result_schemas,
        total_owner_delay=analysis.total_owner_delay,
        total_contractor_delay=analysis.total_contractor_delay,
        total_shared_delay=analysis.total_shared_delay,
        net_delay=analysis.net_delay,
        summary=analysis.summary,
    )


@app.post("/api/v1/tia/analyze", response_model=TIAAnalysisSchema)
def tia_analyze(request: TIAAnalyzeRequest) -> TIAAnalysisSchema:
    """Run Time Impact Analysis on a project with delay fragments.

    Per AACE RP 52R-06, inserts each fragment into the schedule network,
    runs CPM, and measures the impact on the project completion date.

    Args:
        request: Contains project_id and fragment definitions.

    Raises:
        HTTPException: If the project is not found or analysis fails.
    """
    store = get_store()
    tia_store = get_tia_store()

    schedule = store.get(request.project_id)
    if schedule is None:
        raise HTTPException(
            status_code=404, detail=f"Project not found: {request.project_id}"
        )

    # Convert schemas to domain models
    fragments = [_fragment_schema_to_model(f) for f in request.fragments]

    try:
        analyzer = TimeImpactAnalyzer(schedule)
        analysis = analyzer.analyze_all(fragments)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"TIA analysis failed: {exc}"
        )

    aid = tia_store.add(analysis)
    return _analysis_to_schema(analysis)


@app.get("/api/v1/tia/analyses", response_model=TIAListResponse)
def list_tia_analyses() -> TIAListResponse:
    """List all TIA analyses."""
    tia_store = get_tia_store()
    items = [TIAAnalysisSummarySchema(**a) for a in tia_store.list_all()]
    return TIAListResponse(analyses=items)


@app.get(
    "/api/v1/tia/analyses/{analysis_id}",
    response_model=TIAAnalysisSchema,
)
def get_tia_analysis(analysis_id: str) -> TIAAnalysisSchema:
    """Get full TIA analysis with all fragment results.

    Args:
        analysis_id: The stored analysis identifier.

    Raises:
        HTTPException: If the analysis is not found.
    """
    tia_store = get_tia_store()
    analysis = tia_store.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="TIA analysis not found")

    return _analysis_to_schema(analysis)


@app.get(
    "/api/v1/tia/analyses/{analysis_id}/summary",
    response_model=TIASummaryResponse,
)
def get_tia_summary(analysis_id: str) -> TIASummaryResponse:
    """Get delay-by-responsibility summary for a TIA analysis.

    Args:
        analysis_id: The stored analysis identifier.

    Raises:
        HTTPException: If the analysis is not found.
    """
    tia_store = get_tia_store()
    analysis = tia_store.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="TIA analysis not found")

    return TIASummaryResponse(
        analysis_id=analysis.analysis_id,
        total_owner_delay=analysis.total_owner_delay,
        total_contractor_delay=analysis.total_contractor_delay,
        total_shared_delay=analysis.total_shared_delay,
        net_delay=analysis.net_delay,
        summary=analysis.summary,
    )


# ------------------------------------------------------------------
# Contract Compliance
# ------------------------------------------------------------------


@app.post("/api/v1/contract/check", response_model=ContractCheckResponse)
def contract_check(request: ContractCheckRequest) -> ContractCheckResponse:
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


@app.get(
    "/api/v1/contract/provisions",
    response_model=ContractProvisionsResponse,
)
def list_contract_provisions() -> ContractProvisionsResponse:
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
# EVM (Earned Value Management)
# ------------------------------------------------------------------


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


@app.post("/api/v1/evm/analyze/{project_id}", response_model=EVMAnalysisSchema)
def run_evm_analysis(project_id: str) -> EVMAnalysisSchema:
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
        raise HTTPException(
            status_code=500, detail=f"EVM analysis failed: {exc}"
        )

    evm_store.add(result)
    return _evm_result_to_schema(result, project_id)


@app.get("/api/v1/evm/analyses", response_model=EVMListResponse)
def list_evm_analyses() -> EVMListResponse:
    """List all EVM analyses."""
    evm_store = get_evm_store()
    items = [EVMAnalysisSummarySchema(**a) for a in evm_store.list_all()]
    return EVMListResponse(analyses=items)


@app.get("/api/v1/evm/analyses/{analysis_id}", response_model=EVMAnalysisSchema)
def get_evm_analysis(analysis_id: str) -> EVMAnalysisSchema:
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


@app.get("/api/v1/evm/analyses/{analysis_id}/s-curve", response_model=SCurveResponse)
def get_evm_s_curve(analysis_id: str) -> SCurveResponse:
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


@app.get(
    "/api/v1/evm/analyses/{analysis_id}/wbs-drill",
    response_model=WBSDrillResponse,
)
def get_evm_wbs_drill(analysis_id: str) -> WBSDrillResponse:
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


@app.get(
    "/api/v1/evm/analyses/{analysis_id}/forecast",
    response_model=ForecastResponse,
)
def get_evm_forecast(analysis_id: str) -> ForecastResponse:
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


# ------------------------------------------------------------------
# Risk (Monte Carlo QSRA)
# ------------------------------------------------------------------


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


@app.post(
    "/api/v1/risk/simulate/{project_id}",
    response_model=SimulationResultSchema,
)
def run_risk_simulation(
    project_id: str, request: RunSimulationRequest
) -> SimulationResultSchema:
    """Run Monte Carlo schedule risk simulation (QSRA) on a project.

    Performs *N* iterations sampling activity durations from probability
    distributions, running CPM each time, and computing completion date
    probability distributions, criticality indices, and sensitivity.
    Per AACE RP 57R-09.

    Args:
        project_id: The stored project identifier.
        request: Simulation configuration, duration risks, and risk events.

    Raises:
        HTTPException: If the project is not found or simulation fails.
    """
    store = get_store()
    risk_store = get_risk_store()

    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(
            status_code=404, detail=f"Project not found: {project_id}"
        )

    # Convert request schemas to domain models
    config = None
    if request.config:
        config = SimulationConfig(
            iterations=request.config.iterations,
            default_distribution=DistributionType(request.config.default_distribution),
            default_uncertainty=request.config.default_uncertainty,
            seed=request.config.seed,
            confidence_levels=request.config.confidence_levels,
        )

    duration_risks = [
        DurationRisk(
            activity_id=r.activity_id,
            distribution=DistributionType(r.distribution),
            min_duration=r.min_duration,
            most_likely=r.most_likely,
            max_duration=r.max_duration,
        )
        for r in request.duration_risks
    ] if request.duration_risks else None

    risk_events = [
        RiskEvent(
            risk_id=e.risk_id,
            name=e.name,
            probability=e.probability,
            impact_hours=e.impact_hours,
            affected_activities=e.affected_activities,
        )
        for e in request.risk_events
    ] if request.risk_events else None

    try:
        simulator = MonteCarloSimulator(schedule, config)
        result = simulator.simulate(duration_risks, risk_events)
        result.project_id = project_id
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Risk simulation failed: {exc}"
        )

    risk_store.add(result)
    return _simulation_to_schema(result)


@app.get("/api/v1/risk/simulations", response_model=SimulationListResponse)
def list_risk_simulations() -> SimulationListResponse:
    """List all risk simulations."""
    risk_store = get_risk_store()
    items = [SimulationSummarySchema(**s) for s in risk_store.list_all()]
    return SimulationListResponse(simulations=items)


@app.get(
    "/api/v1/risk/simulations/{simulation_id}",
    response_model=SimulationResultSchema,
)
def get_risk_simulation(simulation_id: str) -> SimulationResultSchema:
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


@app.get(
    "/api/v1/risk/simulations/{simulation_id}/histogram",
    response_model=HistogramResponse,
)
def get_risk_histogram(simulation_id: str) -> HistogramResponse:
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


@app.get(
    "/api/v1/risk/simulations/{simulation_id}/tornado",
    response_model=TornadoResponse,
)
def get_risk_tornado(simulation_id: str) -> TornadoResponse:
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


@app.get(
    "/api/v1/risk/simulations/{simulation_id}/criticality",
    response_model=CriticalityResponse,
)
def get_risk_criticality(simulation_id: str) -> CriticalityResponse:
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


@app.get(
    "/api/v1/risk/simulations/{simulation_id}/s-curve",
    response_model=RiskSCurveResponse,
)
def get_risk_s_curve(simulation_id: str) -> RiskSCurveResponse:
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
