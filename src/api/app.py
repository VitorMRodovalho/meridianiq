# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""FastAPI application for P6 XER Analytics.

Provides REST endpoints for uploading XER files, querying parsed
schedule data, running DCMA assessments, CPM analysis, and comparing
schedule versions.
"""
from __future__ import annotations

import io
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.analytics.comparison import ScheduleComparison
from src.analytics.cpm import CPMCalculator
from src.analytics.dcma14 import DCMA14Analyzer
from src.parser.models import ParsedSchedule
from src.parser.xer_reader import XERReader

from .schemas import (
    ActivityChangeSchema,
    ActivitySchema,
    CodeRestructuringSchema,
    CompareRequest,
    CompareResponse,
    CriticalPathActivity,
    CriticalPathResponse,
    FloatBucket,
    FloatChangeSchema,
    FloatDistributionResponse,
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
    ValidationResponse,
    WBSLevelCount,
    WBSStats,
)
from .storage import ProjectStore

app = FastAPI(
    title="P6 XER Analytics",
    description="Open-source Primavera P6 XER schedule analysis toolkit",
    version="0.1.0-dev",
)

# Global in-memory store (singleton for the app lifetime)
_store = ProjectStore()


def get_store() -> ProjectStore:
    """Return the global project store.

    Exposed as a function so tests can replace it via monkeypatching.
    """
    return _store


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
