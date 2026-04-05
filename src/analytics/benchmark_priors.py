# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Benchmark-derived priors for Monte Carlo risk simulation.

Auto-generates DurationRisk specifications from the benchmark database
by matching activities to similar projects and deriving empirical
uncertainty distributions.  This eliminates the need for manual
min/max/most_likely input for every activity.

The approach:
1. Extract metrics from the target schedule.
2. Find benchmarks in the same size category.
3. Compute the coefficient of variation (CV) of key metrics across
   benchmarks to derive a data-driven uncertainty range.
4. Generate DurationRisk entries using PERT distributions calibrated
   to the empirical variance.

References:
    - AACE RP 57R-09 — Schedule Risk Analysis (enhanced with priors)
    - Bayesian updating principles for prior specification
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from typing import Any

from src.analytics.benchmarks import BenchmarkMetrics, extract_benchmark_metrics
from src.analytics.risk import DurationRisk, DistributionType
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)

_HOURS_PER_DAY = 8.0


@dataclass
class PriorConfig:
    """Configuration for benchmark-based prior generation."""

    prior_weight: float = 0.5  # Weight of benchmark prior (0-1)
    min_uncertainty: float = 0.10  # Minimum ±10% even for well-known activities
    max_uncertainty: float = 0.50  # Maximum ±50% cap
    filter_by_size: bool = True  # Only use same-size benchmarks


@dataclass
class PriorResult:
    """Result of benchmark prior generation."""

    duration_risks: list[DurationRisk] = field(default_factory=list)
    activities_covered: int = 0
    benchmark_count: int = 0
    avg_uncertainty: float = 0.0
    methodology: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


def generate_benchmark_priors(
    schedule: ParsedSchedule,
    benchmarks: list[BenchmarkMetrics],
    config: PriorConfig | None = None,
) -> PriorResult:
    """Generate DurationRisk entries from benchmark data.

    Creates PERT distributions for each activity using empirical
    variance derived from the benchmark database.

    Args:
        schedule: The schedule to generate priors for.
        benchmarks: Benchmark dataset for deriving uncertainty.
        config: Prior generation configuration.

    Returns:
        A ``PriorResult`` with DurationRisk entries ready for
        Monte Carlo simulation.

    References:
        - AACE RP 57R-09 — Schedule Risk Analysis
        - Bayesian prior specification from empirical data
    """
    if config is None:
        config = PriorConfig()

    result = PriorResult()

    # Extract target schedule metrics
    target_metrics = extract_benchmark_metrics(schedule)

    # Filter benchmarks by size category
    if config.filter_by_size and target_metrics.size_category:
        filtered = [b for b in benchmarks if b.size_category == target_metrics.size_category]
    else:
        filtered = list(benchmarks)

    if len(filtered) < 3:
        filtered = list(benchmarks)  # Fall back to all if too few

    result.benchmark_count = len(filtered)

    if not filtered:
        result.methodology = "No benchmarks available — using default uncertainty"
        return _default_priors(schedule, config, result)

    # Compute empirical uncertainty from benchmark duration variance
    durations = [b.project_duration_days for b in filtered if b.project_duration_days > 0]
    if not durations:
        return _default_priors(schedule, config, result)

    # Coefficient of variation as base uncertainty
    mean_dur = statistics.mean(durations)
    if mean_dur > 0 and len(durations) > 1:
        stdev_dur = statistics.stdev(durations)
        cv = stdev_dur / mean_dur
    else:
        cv = 0.20  # Default 20%

    # Clamp to configured bounds
    base_uncertainty = max(config.min_uncertainty, min(config.max_uncertainty, cv))

    # Weight with prior_weight
    uncertainty = config.prior_weight * base_uncertainty + (1 - config.prior_weight) * 0.20

    # Generate DurationRisk for each non-complete activity
    risks: list[DurationRisk] = []
    for task in schedule.activities:
        if task.status_code.lower() == "tk_complete":
            continue

        base_hrs = task.remain_drtn_hr_cnt
        if base_hrs <= 0:
            continue

        min_hrs = base_hrs * (1.0 - uncertainty)
        max_hrs = base_hrs * (1.0 + uncertainty * 1.5)  # Asymmetric: more upside risk

        risks.append(
            DurationRisk(
                activity_id=task.task_code or task.task_id,
                distribution=DistributionType.PERT,
                min_duration=max(0, min_hrs),
                most_likely=base_hrs,
                max_duration=max_hrs,
            )
        )

    result.duration_risks = risks
    result.activities_covered = len(risks)
    result.avg_uncertainty = round(uncertainty * 100, 1)

    result.methodology = (
        f"Benchmark-derived PERT priors from {result.benchmark_count} projects "
        f"(CV={cv:.2f}, weighted uncertainty={uncertainty:.0%}, "
        f"AACE RP 57R-09 enhanced with Bayesian priors)"
    )

    result.summary = {
        "activities_covered": result.activities_covered,
        "benchmark_count": result.benchmark_count,
        "size_category": target_metrics.size_category,
        "empirical_cv": round(cv, 3),
        "applied_uncertainty_pct": result.avg_uncertainty,
        "prior_weight": config.prior_weight,
        "methodology": result.methodology,
        "references": [
            "AACE RP 57R-09 — Schedule Risk Analysis",
            "Bayesian prior specification from empirical data",
        ],
    }

    return result


def _default_priors(
    schedule: ParsedSchedule,
    config: PriorConfig,
    result: PriorResult,
) -> PriorResult:
    """Generate default priors when no benchmarks available."""

    risks = []
    for task in schedule.activities:
        if task.status_code.lower() == "tk_complete":
            continue
        base_hrs = task.remain_drtn_hr_cnt
        if base_hrs <= 0:
            continue

        risks.append(
            DurationRisk(
                activity_id=task.task_code or task.task_id,
                distribution=DistributionType.PERT,
                min_duration=max(0, base_hrs * 0.80),
                most_likely=base_hrs,
                max_duration=base_hrs * 1.30,
            )
        )

    result.duration_risks = risks
    result.activities_covered = len(risks)
    result.avg_uncertainty = 20.0
    result.methodology = "Default ±20% uncertainty (no benchmark data)"
    return result
