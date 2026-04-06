# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""MeridianIQ MCP Server — Model Context Protocol integration.

Exposes schedule analysis capabilities as MCP tools that AI assistants
(Claude, etc.) can invoke to query and analyze uploaded P6 XER schedules.

Available tools (21):
- upload_xer: Parse and store an XER file
- list_projects: List all uploaded schedules
- get_project_summary: Get project metadata and activity counts
- run_dcma: Run DCMA 14-point schedule assessment
- get_critical_path: Compute and return critical path activities
- get_health_score: Compute composite health score
- get_float_entropy: Compute Shannon entropy of float distribution
- analyze_root_cause: Trace backwards to find delay root cause
- compare_schedules: Compare two schedule versions
- predict_delays: ML delay risk prediction (RF+GB ensemble)
- extract_benchmarks: Extract anonymized benchmark metrics
- run_half_step: MIP 3.4 half-step bifurcation analysis
- run_what_if: Deterministic/probabilistic scenario simulation
- get_scorecard: Schedule scorecard with letter grades A-F
- level_resources: Resource-constrained scheduling (Serial SGS)
- generate_schedule: Generate schedule from project type/size
- build_schedule_from_description: NLP-driven schedule generation
- export_xer: Export schedule to XER format for P6 import
- optimize_schedule_es: Evolution Strategies RCPSP optimizer
- validate_calendars_tool: Calendar integrity validation (DCMA #13)
- compute_delay_attribution_tool: Delay breakdown by responsible party

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
    """Lazy-initialise the project store (Supabase if configured, else in-memory)."""
    global _store
    if _store is None:
        try:
            import os

            if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
                from src.database.store import SupabaseStore

                _store = SupabaseStore()
                logger.info("MCP server using SupabaseStore")
            else:
                raise ValueError("No Supabase env vars")
        except Exception:
            from src.database.store import InMemoryStore

            _store = InMemoryStore()
            logger.info("MCP server using InMemoryStore")
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


@mcp.tool()
def run_what_if(
    project_id: str,
    adjustments: str = "",
    iterations: int = 1,
) -> str:
    """Run a what-if scenario on a schedule.

    Applies percentage-based duration adjustments and re-runs CPM to show
    impact on project duration and critical path.  Supports deterministic
    (iterations=1) and probabilistic (iterations>1) modes.

    Args:
        project_id: The project identifier.
        adjustments: JSON array of adjustments, e.g.
            '[{"target": "B", "pct_change": 0.20}]' or
            '[{"target": "*", "min_pct": -0.10, "max_pct": 0.30}]'.
        iterations: Number of iterations (1=deterministic, >1=probabilistic).

    Returns:
        JSON with base/adjusted duration, delta, P-values (if probabilistic),
        and per-activity impacts.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from src.analytics.whatif import DurationAdjustment, WhatIfScenario, simulate_whatif

    adj_list = []
    if adjustments:
        raw = json.loads(adjustments)
        for a in raw:
            adj_list.append(
                DurationAdjustment(
                    target=a.get("target", "*"),
                    pct_change=a.get("pct_change", 0.0),
                    min_pct=a.get("min_pct"),
                    max_pct=a.get("max_pct"),
                )
            )

    scenario = WhatIfScenario(name="MCP Scenario", adjustments=adj_list, iterations=iterations)
    result = simulate_whatif(schedule, scenario)
    return json.dumps(_serialize(result))


@mcp.tool()
def get_scorecard(project_id: str) -> str:
    """Get a comprehensive schedule scorecard with letter grades.

    Aggregates DCMA 14-Point, Health Score, Risk Assessment, Logic
    Integrity, and Data Completeness into a weighted overall grade (A-F).

    Args:
        project_id: The project identifier.

    Returns:
        JSON with overall_grade, overall_score, dimension scores/grades,
        and actionable recommendations.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from src.analytics.scorecard import calculate_scorecard

    result = calculate_scorecard(schedule)
    return json.dumps(_serialize(result))


@mcp.tool()
def level_resources(
    project_id: str,
    resource_limits: str = "",
    priority_rule: str = "late_start",
) -> str:
    """Run resource-constrained scheduling via Serial SGS.

    Levels resources by scheduling activities at their earliest feasible
    start, respecting both precedence and resource capacity constraints.

    Args:
        project_id: The project identifier.
        resource_limits: JSON array of limits, e.g.
            '[{"rsrc_id": "R1", "max_units": 2.0}]'.
        priority_rule: Priority rule (late_start, early_start, float, duration).

    Returns:
        JSON with original/leveled duration, extension, activity shifts,
        and resource profiles.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from src.analytics.resource_leveling import LevelingConfig, ResourceLimit, level_resources

    limits = []
    if resource_limits:
        raw = json.loads(resource_limits)
        for rl in raw:
            limits.append(
                ResourceLimit(
                    rsrc_id=rl.get("rsrc_id", ""),
                    max_units=rl.get("max_units", 1.0),
                )
            )

    config = LevelingConfig(resource_limits=limits, priority_rule=priority_rule)
    result = level_resources(schedule, config)
    return json.dumps(_serialize(result))


@mcp.tool()
def generate_schedule(
    project_type: str = "commercial",
    size_category: str = "medium",
    project_name: str = "Generated Project",
    target_duration_days: float = 0,
) -> str:
    """Generate a complete schedule from project parameters.

    Creates activities, durations, and logical relationships based on
    project type, size category, and optional target duration.

    Args:
        project_type: commercial, industrial, infrastructure, or residential.
        size_category: small, medium, large, or mega.
        project_name: Name for the generated project.
        target_duration_days: Target duration (0 = auto).

    Returns:
        JSON with generated activities, relationships, predicted duration,
        and full schedule summary.
    """
    from src.analytics.schedule_generation import GenerationInput
    from src.analytics.schedule_generation import generate_schedule as _generate

    params = GenerationInput(
        project_type=project_type,
        project_name=project_name,
        target_duration_days=target_duration_days,
        size_category=size_category,
    )
    result = _generate(params)
    # Don't serialize parsed_schedule (too large for MCP response)
    summary = result.summary.copy()
    summary["activities"] = [
        {"code": a.task_code, "name": a.task_name, "duration_days": a.duration_days}
        for a in result.activities[:50]  # Limit to first 50
    ]
    return json.dumps(summary)


@mcp.tool()
def build_schedule_from_description(description: str) -> str:
    """Build a schedule from a natural language project description.

    Interprets the description to extract project type, size, and
    complexity, then generates a complete schedule.

    Args:
        description: Natural language project description, e.g.
            "3-story office building, 18 months, steel frame".

    Returns:
        JSON with interpreted parameters, generated activity count,
        and predicted duration.
    """
    from src.analytics.schedule_builder import _fallback_build

    result = _fallback_build(description)
    return json.dumps(_serialize(result.summary))


@mcp.tool()
def export_xer(project_id: str) -> str:
    """Export a project schedule to XER format.

    Writes the schedule back to Oracle P6 XER format for import into
    Primavera P6. Supports round-trip fidelity.

    Args:
        project_id: The project identifier.

    Returns:
        XER file content as a string (first 5000 chars for preview).
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from src.export.xer_writer import XERWriter

    content = XERWriter(schedule).write()
    preview = content[:5000]
    return json.dumps(
        {
            "preview": preview,
            "total_length": len(content),
            "tables_written": content.count("%T\t"),
            "rows_written": content.count("%R\t"),
        }
    )


@mcp.tool()
def optimize_schedule_es(
    project_id: str,
    resource_limits: str = "",
    generations: int = 20,
) -> str:
    """Optimize a resource-constrained schedule using Evolution Strategies.

    Uses (mu, lambda) ES to find better priority orderings for the
    Serial SGS, minimizing project makespan.

    Args:
        project_id: The project identifier.
        resource_limits: JSON array of limits, e.g.
            '[{"rsrc_id": "R1", "max_units": 2.0}]'.
        generations: Number of ES generations to run.

    Returns:
        JSON with best/greedy duration, improvement, convergence history.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from src.analytics.evolution_optimizer import EvolutionConfig, optimize_schedule
    from src.analytics.resource_leveling import ResourceLimit

    limits = []
    if resource_limits:
        raw = json.loads(resource_limits)
        for rl in raw:
            limits.append(
                ResourceLimit(
                    rsrc_id=rl.get("rsrc_id", ""),
                    max_units=rl.get("max_units", 1.0),
                )
            )

    config = EvolutionConfig(
        population_size=20,
        parent_size=5,
        generations=generations,
        resource_limits=limits,
    )
    result = optimize_schedule(schedule, config)
    return json.dumps(_serialize(result.summary))


@mcp.tool()
def validate_calendars_tool(project_id: str) -> str:
    """Validate work calendar definitions for integrity and best practices.

    Checks default calendar existence, task coverage, hour consistency,
    non-standard calendars, and orphaned definitions. Returns a score
    (0-100) with letter grade (A-F) and detailed findings.

    Args:
        project_id: The project identifier.

    Returns:
        JSON with score, grade, calendar details, and validation issues.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from dataclasses import asdict

    from src.analytics.calendar_validation import validate_calendars

    result = validate_calendars(schedule)
    return json.dumps(_serialize(asdict(result)))


@mcp.tool()
def compute_delay_attribution_tool(
    project_id: str,
    baseline_id: str = "",
) -> str:
    """Compute delay attribution breakdown by responsible party.

    Aggregates delay by Owner, Contractor, Shared, Third Party, and
    Force Majeure.  Returns excusable vs non-excusable totals and
    per-party driving activities.

    Args:
        project_id: The current/update schedule identifier.
        baseline_id: Optional baseline schedule for comparison.

    Returns:
        JSON with per-party breakdown and excusable/non-excusable totals.
    """
    store = _get_store()
    schedule = store.get(project_id)
    if schedule is None:
        return json.dumps({"error": "Project not found"})

    from dataclasses import asdict

    from src.analytics.delay_attribution import compute_delay_attribution

    baseline = store.get(baseline_id) if baseline_id else None
    result = compute_delay_attribution(schedule, baseline=baseline)
    return json.dumps(_serialize(asdict(result)))


# ── Entry point ──

if __name__ == "__main__":
    mcp.run()
