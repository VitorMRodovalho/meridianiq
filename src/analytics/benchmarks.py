# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Benchmark analytics — anonymized cross-project comparison.

Extracts anonymized aggregate metrics from a schedule and compares them
against a benchmark dataset.  All identifying information (project names,
activity names, WBS descriptions) is stripped before storage.

The benchmark dataset enables percentile-based comparison:
"Your DCMA score is in the 75th percentile for projects of this size."

References:
    - DCMA 14-Point Assessment — standard metric thresholds
    - AACE RP 49R-06 — Float health criteria
    - GAO Schedule Assessment Guide — quality indicators
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from typing import Any

from src.analytics.cpm import CPMCalculator
from src.analytics.dcma14 import DCMA14Analyzer
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkMetrics:
    """Anonymized aggregate metrics extracted from a single schedule.

    No identifying information (names, codes, WBS descriptions) is stored.
    """

    # Schedule characteristics
    activity_count: int = 0
    relationship_count: int = 0
    wbs_depth: int = 0
    milestone_count: int = 0
    size_category: str = (
        ""  # "small" (<100), "medium" (100-500), "large" (500-2000), "mega" (>2000)
    )

    # DCMA metrics
    dcma_score: float = 0.0  # Overall 0-100
    logic_pct: float = 0.0  # % with pred+succ
    constraint_pct: float = 0.0  # % with hard constraints
    high_float_pct: float = 0.0  # % with TF >44d
    negative_float_pct: float = 0.0  # % with negative TF
    high_duration_pct: float = 0.0  # % with duration >44d
    relationship_fs_pct: float = 0.0  # % FS relationships
    lead_pct: float = 0.0  # % with negative lag
    lag_pct: float = 0.0  # % with positive lag
    bei: float = 0.0  # Baseline Execution Index
    cpli: float = 0.0  # Critical Path Length Index

    # Float distribution
    float_mean_days: float = 0.0
    float_median_days: float = 0.0
    float_stdev_days: float = 0.0

    # Network metrics
    relationship_density: float = 0.0  # rels / activities
    critical_path_length: int = 0  # Activities on CP
    cp_percentage: float = 0.0  # % activities on CP
    project_duration_days: float = 0.0

    # Progress (if update)
    complete_pct: float = 0.0
    active_pct: float = 0.0
    not_started_pct: float = 0.0


@dataclass
class PercentileRanking:
    """How a metric compares to the benchmark dataset."""

    metric_name: str
    value: float
    percentile: float  # 0-100
    benchmark_mean: float
    benchmark_median: float
    benchmark_count: int
    interpretation: str  # "above_average", "average", "below_average"


@dataclass
class BenchmarkComparison:
    """Result of comparing a schedule against the benchmark dataset."""

    project_metrics: BenchmarkMetrics = field(default_factory=BenchmarkMetrics)
    rankings: list[PercentileRanking] = field(default_factory=list)
    overall_percentile: float = 0.0
    benchmark_count: int = 0
    size_category: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------------

_HOURS_PER_DAY = 8.0


def extract_benchmark_metrics(schedule: ParsedSchedule) -> BenchmarkMetrics:
    """Extract anonymized aggregate metrics from a schedule.

    No activity names, WBS descriptions, or any identifying text is
    included in the output — only numeric aggregates.

    Args:
        schedule: A parsed schedule.

    Returns:
        Anonymized ``BenchmarkMetrics``.
    """
    m = BenchmarkMetrics()
    activities = schedule.activities
    relationships = schedule.relationships

    if not activities:
        return m

    # Schedule characteristics
    m.activity_count = len(activities)
    m.relationship_count = len(relationships)
    m.milestone_count = sum(
        1 for t in activities if t.task_type in ("TT_Mile", "TT_FinMile", "TT_StartMile")
    )

    # Size category
    if m.activity_count < 100:
        m.size_category = "small"
    elif m.activity_count < 500:
        m.size_category = "medium"
    elif m.activity_count < 2000:
        m.size_category = "large"
    else:
        m.size_category = "mega"

    # WBS depth
    wbs_depths = set()
    for w in schedule.wbs_nodes:
        depth = 0
        parent = w.parent_wbs_id
        seen: set[str] = {w.wbs_id}
        wbs_map = {n.wbs_id: n for n in schedule.wbs_nodes}
        while parent and parent not in seen:
            depth += 1
            seen.add(parent)
            p_node = wbs_map.get(parent)
            parent = p_node.parent_wbs_id if p_node else ""
        wbs_depths.add(depth)
    m.wbs_depth = max(wbs_depths, default=0)

    # DCMA metrics
    try:
        dcma = DCMA14Analyzer(schedule).analyze()
        m.dcma_score = dcma.overall_score

        for check in dcma.checks:
            name = check.name.lower()
            if "logic" in name and "type" not in name:
                m.logic_pct = check.value
            elif "constraint" in name or "hard" in name:
                m.constraint_pct = check.value
            elif "high float" in name:
                m.high_float_pct = check.value
            elif "negative float" in name:
                m.negative_float_pct = check.value
            elif "high duration" in name or "long duration" in name:
                m.high_duration_pct = check.value
            elif "relationship type" in name or "fs" in name.split():
                m.relationship_fs_pct = check.value
            elif "lead" in name:
                m.lead_pct = check.value
            elif "lag" in name and "lead" not in name:
                m.lag_pct = check.value
            elif "bei" in name or "baseline execution" in name:
                m.bei = check.value
            elif "cpli" in name or "critical path length" in name:
                m.cpli = check.value
    except Exception:
        logger.warning("DCMA analysis failed during benchmark extraction")

    # Float distribution
    floats = [
        (t.total_float_hr_cnt or 0.0) / _HOURS_PER_DAY
        for t in activities
        if t.total_float_hr_cnt is not None
    ]
    if floats:
        m.float_mean_days = round(statistics.mean(floats), 2)
        m.float_median_days = round(statistics.median(floats), 2)
        m.float_stdev_days = round(statistics.stdev(floats), 2) if len(floats) > 1 else 0.0

    # Network metrics
    m.relationship_density = round(m.relationship_count / m.activity_count, 2)

    try:
        cpm = CPMCalculator(schedule).calculate()
        m.critical_path_length = len(cpm.critical_path)
        m.cp_percentage = round(len(cpm.critical_path) / m.activity_count * 100, 1)
        m.project_duration_days = round(cpm.project_duration, 1)
    except Exception:
        logger.warning("CPM failed during benchmark extraction")

    # Progress status
    complete = sum(1 for t in activities if t.status_code.lower() == "tk_complete")
    active = sum(1 for t in activities if t.status_code.lower() == "tk_active")
    not_started = sum(1 for t in activities if t.status_code.lower() == "tk_notstart")
    total = m.activity_count
    m.complete_pct = round(complete / total * 100, 1)
    m.active_pct = round(active / total * 100, 1)
    m.not_started_pct = round(not_started / total * 100, 1)

    return m


# ---------------------------------------------------------------------------
# Benchmark comparison
# ---------------------------------------------------------------------------


def compare_to_benchmarks(
    schedule: ParsedSchedule,
    benchmark_dataset: list[BenchmarkMetrics],
    filter_size: bool = True,
) -> BenchmarkComparison:
    """Compare a schedule's metrics against a benchmark dataset.

    Calculates percentile ranking for each key metric relative to the
    benchmark dataset, optionally filtered by project size category.

    Args:
        schedule: The schedule to compare.
        benchmark_dataset: List of benchmark metrics to compare against.
        filter_size: If True, only compare against same size_category.

    Returns:
        ``BenchmarkComparison`` with percentile rankings.
    """
    result = BenchmarkComparison()
    project_metrics = extract_benchmark_metrics(schedule)
    result.project_metrics = project_metrics
    result.size_category = project_metrics.size_category

    if not benchmark_dataset:
        result.summary = {"error": "No benchmark data available"}
        return result

    # Filter by size if requested
    if filter_size:
        filtered = [
            b for b in benchmark_dataset if b.size_category == project_metrics.size_category
        ]
        if not filtered:
            filtered = benchmark_dataset  # Fallback to all
    else:
        filtered = benchmark_dataset

    result.benchmark_count = len(filtered)

    # Compute percentile rankings for key metrics
    metrics_to_rank = [
        ("dcma_score", project_metrics.dcma_score, True),  # Higher is better
        ("logic_pct", project_metrics.logic_pct, True),
        ("constraint_pct", project_metrics.constraint_pct, False),  # Lower is better
        ("negative_float_pct", project_metrics.negative_float_pct, False),
        ("high_float_pct", project_metrics.high_float_pct, False),
        ("relationship_density", project_metrics.relationship_density, True),
        ("cp_percentage", project_metrics.cp_percentage, None),  # Neutral
        ("float_mean_days", project_metrics.float_mean_days, None),
        ("bei", project_metrics.bei, True),
    ]

    rankings: list[PercentileRanking] = []

    for metric_name, value, higher_is_better in metrics_to_rank:
        bench_values = [getattr(b, metric_name, 0.0) for b in filtered]
        if not bench_values:
            continue

        percentile = _percentile_rank(value, bench_values)
        bench_mean = round(statistics.mean(bench_values), 2)
        bench_median = round(statistics.median(bench_values), 2)

        if higher_is_better is True:
            interp = (
                "above_average"
                if percentile > 60
                else "below_average"
                if percentile < 40
                else "average"
            )
        elif higher_is_better is False:
            interp = (
                "above_average"
                if percentile < 40
                else "below_average"
                if percentile > 60
                else "average"
            )
        else:
            interp = "average"

        rankings.append(
            PercentileRanking(
                metric_name=metric_name,
                value=round(value, 2),
                percentile=round(percentile, 1),
                benchmark_mean=bench_mean,
                benchmark_median=bench_median,
                benchmark_count=len(bench_values),
                interpretation=interp,
            )
        )

    result.rankings = rankings

    # Overall percentile (average of key metric percentiles)
    if rankings:
        result.overall_percentile = round(statistics.mean(r.percentile for r in rankings), 1)

    result.summary = {
        "project_size": project_metrics.size_category,
        "project_activity_count": project_metrics.activity_count,
        "benchmark_count": result.benchmark_count,
        "overall_percentile": result.overall_percentile,
        "dcma_score": project_metrics.dcma_score,
        "dcma_percentile": next(
            (r.percentile for r in rankings if r.metric_name == "dcma_score"), 0
        ),
        "rankings_count": len(rankings),
        "above_average_count": sum(1 for r in rankings if r.interpretation == "above_average"),
        "below_average_count": sum(1 for r in rankings if r.interpretation == "below_average"),
    }

    return result


def _percentile_rank(value: float, dataset: list[float]) -> float:
    """Calculate the percentile rank of a value within a dataset."""
    if not dataset:
        return 50.0
    below = sum(1 for v in dataset if v < value)
    equal = sum(1 for v in dataset if abs(v - value) < 0.001)
    return (below + 0.5 * equal) / len(dataset) * 100
