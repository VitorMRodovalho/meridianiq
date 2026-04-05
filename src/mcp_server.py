# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""MeridianIQ MCP Server — Model Context Protocol integration.

Exposes schedule analysis capabilities as MCP tools that AI assistants
(Claude, etc.) can invoke to query and analyze uploaded P6 XER schedules.

Available tools:
- list_projects: List all uploaded schedules
- get_project_summary: Get project metadata and activity counts
- run_dcma: Run DCMA 14-point schedule assessment
- get_critical_path: Compute and return critical path activities
- get_float_distribution: Get float distribution across activities
- get_health_score: Compute composite health score
- get_float_entropy: Compute Shannon entropy of float distribution
- analyze_root_cause: Trace backwards to find delay root cause
- compare_schedules: Compare two schedule versions

Usage:
    python -m src.mcp_server

Or configure in Claude Code settings:
    {
        "mcpServers": {
            "meridianiq": {
                "command": "python",
                "args": ["-m", "src.mcp_server"],
                "cwd": "/path/to/p6-xer-analytics"
            }
        }
    }
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP(
    "MeridianIQ",
    instructions="Schedule intelligence platform — P6 XER analysis, DCMA validation, "
    "critical path, forensic delay analysis, and more. "
    "Upload XER files, then use tools to analyze schedule quality, "
    "find critical path, compute health scores, and detect manipulation.",
)

# ── Lazy store access ──

_store = None


def _get_store():
    """Lazy-initialise the in-memory project store."""
    global _store
    if _store is None:
        from src.database.store import InMemoryStore

        _store = InMemoryStore()
    return _store


def _serialize(obj: Any) -> Any:
    """Recursively convert dataclasses / datetimes for JSON output."""
    from dataclasses import asdict
    from datetime import date, datetime

    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(i) for i in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    return str(obj)


# ── Tools ──


@mcp.tool()
def upload_xer(file_path: str) -> str:
    """Upload and parse a P6 XER file from the local filesystem.

    Args:
        file_path: Absolute path to the .xer file.

    Returns:
        Project summary with ID, name, activity/relationship counts.
    """
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    from src.parser.xer_reader import XERReader

    reader = XERReader(path)
    schedule = reader.parse()

    store = _get_store()
    xer_bytes = path.read_bytes()
    project_id = store.add(schedule, xer_bytes)

    name = schedule.projects[0].proj_short_name if schedule.projects else ""
    return json.dumps(
        {
            "project_id": project_id,
            "name": name,
            "activity_count": len(schedule.activities),
            "relationship_count": len(schedule.relationships),
            "calendar_count": len(schedule.calendars),
            "wbs_count": len(schedule.wbs_nodes),
        }
    )


@mcp.tool()
def list_projects() -> str:
    """List all uploaded schedules with summary info.

    Returns:
        JSON array of projects with name, activity count, relationship count.
    """
    store = _get_store()
    projects = store.list_all()
    return json.dumps(projects, default=str)


@mcp.tool()
def get_project_summary(project_id: str) -> str:
    """Get detailed summary of a project including activity status breakdown.

    Args:
        project_id: The project identifier from list_projects.

    Returns:
        Project metadata, activity counts by status, relationship types.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    complete = sum(1 for a in schedule.activities if a.status_code.upper() == "TK_COMPLETE")
    active = sum(1 for a in schedule.activities if a.status_code.upper() == "TK_ACTIVE")
    not_started = len(schedule.activities) - complete - active

    name = schedule.projects[0].proj_short_name if schedule.projects else ""
    data_date = None
    if schedule.projects:
        dd = schedule.projects[0].last_recalc_date or schedule.projects[0].sum_data_date
        if dd:
            data_date = dd.isoformat()

    return json.dumps(
        {
            "project_id": project_id,
            "name": name,
            "data_date": data_date,
            "activities": {
                "total": len(schedule.activities),
                "complete": complete,
                "in_progress": active,
                "not_started": not_started,
            },
            "relationships": len(schedule.relationships),
            "calendars": len(schedule.calendars),
            "wbs_elements": len(schedule.wbs_nodes),
        }
    )


@mcp.tool()
def run_dcma(project_id: str) -> str:
    """Run DCMA 14-Point schedule assessment.

    Evaluates schedule quality across 14 standardized checks including
    logic density, leads/lags, float distribution, constraints, and more.

    Args:
        project_id: The project identifier.

    Returns:
        Overall score (0-100), pass/fail count, and each metric's result.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from src.analytics.dcma14 import DCMA14Analyzer

    analyzer = DCMA14Analyzer(schedule)
    result = analyzer.analyze()
    return json.dumps(_serialize(result))


@mcp.tool()
def get_critical_path(project_id: str) -> str:
    """Compute critical path using the CPM engine.

    Returns the ordered list of activities on the longest path through
    the schedule network, with duration and float for each activity.

    Args:
        project_id: The project identifier.

    Returns:
        Critical path activities with ES, EF, LS, LF, TF, FF.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from src.analytics.cpm import CPMCalculator

    calc = CPMCalculator(schedule)
    result = calc.calculate()
    return json.dumps(_serialize(result))


@mcp.tool()
def get_health_score(project_id: str) -> str:
    """Compute composite schedule health score (0-100).

    Combines DCMA quality (40%), float health (25%), logic integrity (20%),
    and trend direction (15%) per GAO Schedule Assessment Guide.

    Args:
        project_id: The project identifier.

    Returns:
        Overall score, rating (excellent/good/fair/poor), component breakdown.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from src.analytics.health_score import HealthScoreCalculator

    calc = HealthScoreCalculator(schedule)
    result = calc.calculate()
    return json.dumps(_serialize(result))


@mcp.tool()
def get_float_entropy(project_id: str) -> str:
    """Compute Shannon entropy of float distribution.

    Measures how uniformly total float is distributed across activities.
    Low entropy = concentrated, high entropy = spread evenly.

    Args:
        project_id: The project identifier.

    Returns:
        Entropy value, normalised entropy (0-1), distribution, interpretation.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from src.analytics.float_trends import compute_float_entropy
    from dataclasses import asdict

    result = compute_float_entropy(schedule)
    return json.dumps(asdict(result))


@mcp.tool()
def analyze_root_cause(project_id: str, activity_id: str = "") -> str:
    """Trace backwards through the dependency network to find delay root cause.

    Starting from a target activity (or project completion if not specified),
    walks backwards through driving predecessors to identify the originating
    delay event.

    Args:
        project_id: The project identifier.
        activity_id: Optional target activity. If empty, uses project completion.

    Returns:
        Ordered chain from target to root cause with driving reason at each step.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from src.analytics.root_cause import analyze_root_cause as _analyze

    target = activity_id if activity_id else None
    result = _analyze(schedule, target_task_id=target)
    return json.dumps(_serialize(result))


@mcp.tool()
def compare_schedules(baseline_id: str, update_id: str) -> str:
    """Compare two schedule versions to detect changes and manipulation.

    Identifies added/deleted/modified activities, relationship changes,
    float changes, and potential manipulation indicators.

    Args:
        baseline_id: The baseline project identifier.
        update_id: The update project identifier.

    Returns:
        Comparison results with change counts, manipulation flags, and details.
    """
    store = _get_store()
    baseline = store.get(baseline_id)
    update = store.get(update_id)

    if baseline is None:
        return json.dumps({"error": "Baseline project not found"})
    if update is None:
        return json.dumps({"error": "Update project not found"})

    from src.analytics.comparison import ScheduleComparison

    comparison = ScheduleComparison(baseline, update)
    result = comparison.compare()
    return json.dumps(_serialize(result))


@mcp.tool()
def predict_delays(project_id: str, baseline_id: str = "") -> str:
    """Predict delay risk for all non-complete activities in a schedule.

    Uses weighted multi-factor risk scoring with explainable risk factors
    per DCMA 14-Point and AACE RP 49R-06 criteria. Optionally enhanced
    with trend features when a baseline is provided.

    Args:
        project_id: The project identifier to analyze.
        baseline_id: Optional earlier project for trend-based enhancement.

    Returns:
        Per-activity risk scores, risk levels, predicted delay days,
        top risk factors, and project-level aggregates.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    baseline = None
    if baseline_id:
        baseline = store.get(baseline_id)
        if baseline is None:
            return json.dumps({"error": "Baseline project not found"})

    from src.analytics.delay_prediction import predict_delays as _predict

    result = _predict(schedule, baseline=baseline)
    return json.dumps(_serialize(result))


@mcp.tool()
def extract_benchmarks(project_id: str) -> str:
    """Extract anonymized benchmark metrics from a schedule.

    Produces aggregate metrics (DCMA scores, float distribution, network
    density) with no identifying information (no activity names, WBS text,
    or project identifiers).

    Args:
        project_id: The project identifier.

    Returns:
        Anonymized BenchmarkMetrics as JSON.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from src.analytics.benchmarks import extract_benchmark_metrics

    result = extract_benchmark_metrics(schedule)
    return json.dumps(_serialize(result))


@mcp.tool()
def run_half_step(baseline_id: str, update_id: str) -> str:
    """Run half-step bifurcation analysis per AACE RP 29R-03 MIP 3.4.

    Separates schedule delay into progress effect (actual work performance)
    and revision effect (logic/plan changes) by creating an intermediate
    half-step schedule with only progress applied.

    Args:
        baseline_id: The earlier (baseline) project identifier.
        update_id: The later (update) project identifier.

    Returns:
        JSON with progress_effect, revision_effect, total_delay, critical
        paths, change classification, and invariant check.
    """
    store = _get_store()
    baseline = store.get(baseline_id)
    update = store.get(update_id)

    if baseline is None:
        return json.dumps({"error": "Baseline project not found"})
    if update is None:
        return json.dumps({"error": "Update project not found"})

    from src.analytics.half_step import analyze_half_step as _analyze

    result = _analyze(baseline, update)
    return json.dumps(_serialize(result))


# ── Entry point ──

if __name__ == "__main__":
    mcp.run()
