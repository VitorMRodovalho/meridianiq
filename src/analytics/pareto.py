# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Time-cost Pareto analysis — multi-scenario trade-off frontier.

Runs multiple what-if scenarios with associated cost impacts and computes
the Pareto-optimal frontier (non-dominated solutions) on the
time-vs-cost plane.  Points on the frontier represent scenarios where
no other scenario is both cheaper and shorter.

References:
    - AACE RP 36R-06 — Cost Estimate Classification
    - PMI Practice Standard for Scheduling — Time-Cost Trade-off
    - Kelley & Walker (1959) — Critical Path Planning and Scheduling
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.whatif import DurationAdjustment, WhatIfScenario, simulate_whatif
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------


@dataclass
class CostScenario:
    """A what-if scenario with an associated cost impact."""

    name: str = ""
    adjustments: list[DurationAdjustment] = field(default_factory=list)
    cost_delta: float = 0.0  # Additional cost of this scenario (positive = more expensive)


@dataclass
class ParetoPoint:
    """A single point on the time-cost plane."""

    scenario_name: str = ""
    duration_days: float = 0.0
    total_cost: float = 0.0
    is_pareto_optimal: bool = False
    delta_days: float = 0.0
    delta_cost: float = 0.0


@dataclass
class ParetoResult:
    """Result of a time-cost Pareto analysis."""

    base_duration_days: float = 0.0
    base_cost: float = 0.0
    all_points: list[ParetoPoint] = field(default_factory=list)
    frontier: list[ParetoPoint] = field(default_factory=list)
    scenarios_evaluated: int = 0
    frontier_size: int = 0
    methodology: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pareto frontier computation
# ---------------------------------------------------------------------------


def _compute_pareto_frontier(points: list[ParetoPoint]) -> list[ParetoPoint]:
    """Identify Pareto-optimal points (minimize both duration and cost).

    A point is Pareto-optimal if no other point has both lower duration
    AND lower cost.
    """
    frontier: list[ParetoPoint] = []

    for p in points:
        dominated = False
        for q in points:
            if q is p:
                continue
            if q.duration_days <= p.duration_days and q.total_cost <= p.total_cost:
                if q.duration_days < p.duration_days or q.total_cost < p.total_cost:
                    dominated = True
                    break
        if not dominated:
            p.is_pareto_optimal = True
            frontier.append(p)

    # Sort frontier by duration ascending
    frontier.sort(key=lambda p: p.duration_days)
    return frontier


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_pareto(
    schedule: ParsedSchedule,
    scenarios: list[CostScenario],
    base_cost: float = 0.0,
) -> ParetoResult:
    """Run time-cost Pareto analysis across multiple scenarios.

    Each scenario adjusts durations and has an associated cost delta.
    The analysis finds the Pareto-optimal frontier of non-dominated
    solutions on the time-vs-cost plane.

    Args:
        schedule: The schedule to analyze.
        scenarios: List of scenarios with duration adjustments and costs.
        base_cost: The base project cost (before any scenario adjustments).

    Returns:
        A ``ParetoResult`` with all points and the Pareto frontier.

    References:
        - AACE RP 36R-06 — Cost Estimate Classification
        - PMI Practice Standard for Scheduling — Time-Cost Trade-off
        - Kelley & Walker (1959) — CPM Time-Cost Extension
    """
    result = ParetoResult(base_cost=base_cost)

    # Run baseline
    baseline_scenario = WhatIfScenario(name="Baseline")
    baseline_result = simulate_whatif(schedule, baseline_scenario)
    result.base_duration_days = baseline_result.base_duration_days

    # Add baseline point
    base_point = ParetoPoint(
        scenario_name="Baseline",
        duration_days=result.base_duration_days,
        total_cost=base_cost,
        delta_days=0.0,
        delta_cost=0.0,
    )
    all_points = [base_point]

    # Run each scenario
    for cs in scenarios:
        wi_scenario = WhatIfScenario(name=cs.name, adjustments=cs.adjustments)
        wi_result = simulate_whatif(schedule, wi_scenario)

        point = ParetoPoint(
            scenario_name=cs.name,
            duration_days=wi_result.adjusted_duration_days,
            total_cost=base_cost + cs.cost_delta,
            delta_days=wi_result.delta_days,
            delta_cost=cs.cost_delta,
        )
        all_points.append(point)

    result.all_points = all_points
    result.scenarios_evaluated = len(all_points)

    # Compute Pareto frontier
    result.frontier = _compute_pareto_frontier(all_points)
    result.frontier_size = len(result.frontier)

    result.methodology = (
        f"Time-cost Pareto analysis across {result.scenarios_evaluated} scenarios "
        f"(Kelley & Walker 1959, AACE RP 36R-06)"
    )

    # Summary
    result.summary = {
        "base_duration_days": result.base_duration_days,
        "base_cost": result.base_cost,
        "scenarios_evaluated": result.scenarios_evaluated,
        "frontier_size": result.frontier_size,
        "frontier": [
            {
                "name": p.scenario_name,
                "duration_days": p.duration_days,
                "cost": p.total_cost,
            }
            for p in result.frontier
        ],
        "methodology": result.methodology,
        "references": [
            "AACE RP 36R-06 — Cost Estimate Classification",
            "PMI Practice Standard for Scheduling — Time-Cost Trade-off",
            "Kelley & Walker (1959) — CPM Time-Cost Extension",
        ],
    }

    return result
