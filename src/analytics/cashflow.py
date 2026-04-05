# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Cash flow analysis — cost distribution over time with S-Curve.

Distributes planned and actual costs across the project timeline using
CPM-calculated dates and TaskResource cost data.  Produces a cumulative
S-Curve for planned vs actual cost tracking.

References:
    - AACE RP 10S-90 — Cost Engineering Terminology
    - PMI Practice Standard for EVM — Budget at Completion (BAC)
    - AACE RP 48R-06 — Schedule Contingency
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.cpm import CPMCalculator
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)

_HOURS_PER_DAY = 8.0


@dataclass
class CashFlowPoint:
    """A single point on the cash flow curve."""

    day: int = 0
    planned_period: float = 0.0  # Cost incurred this period
    actual_period: float = 0.0
    planned_cumulative: float = 0.0
    actual_cumulative: float = 0.0


@dataclass
class CashFlowResult:
    """Complete cash flow analysis."""

    total_planned_cost: float = 0.0
    total_actual_cost: float = 0.0
    total_remaining_cost: float = 0.0
    budget_variance: float = 0.0  # planned - actual
    cost_performance_index: float = 0.0
    curve: list[CashFlowPoint] = field(default_factory=list)
    peak_spend_day: int = 0
    peak_spend_amount: float = 0.0
    methodology: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


def analyze_cashflow(
    schedule: ParsedSchedule,
) -> CashFlowResult:
    """Analyze cash flow and generate S-Curve data.

    Distributes costs across the timeline based on CPM dates and
    activity cost assignments.

    Args:
        schedule: Schedule with activities and task_resources containing costs.

    Returns:
        A ``CashFlowResult`` with cumulative planned/actual curves.

    References:
        - AACE RP 10S-90 — Cost Engineering Terminology
        - PMI Practice Standard for EVM
    """
    result = CashFlowResult()

    # Run CPM
    try:
        cpm = CPMCalculator(schedule, hours_per_day=_HOURS_PER_DAY).calculate()
    except Exception:
        logger.warning("CPM failed for cash flow")
        result.methodology = "CPM failed"
        return result

    if not cpm.activity_results:
        result.methodology = "No activities for cash flow"
        return result

    # Build cost map: task_id → (planned_cost, actual_cost, remaining)
    cost_map: dict[str, tuple[float, float, float]] = {}
    for tr in schedule.task_resources:
        tid = tr.task_id
        if tid not in cost_map:
            cost_map[tid] = (0.0, 0.0, 0.0)
        planned, actual, remaining = cost_map[tid]
        cost_map[tid] = (
            planned + tr.target_cost,
            actual + tr.act_reg_cost,
            remaining + tr.remain_cost,
        )

    # If no cost data, use duration as proxy (1 unit/day)
    use_proxy = not cost_map
    if use_proxy:
        for task in schedule.activities:
            ar = cpm.activity_results.get(task.task_id)
            if ar and ar.duration > 0:
                cost_map[task.task_id] = (ar.duration, 0.0, 0.0)

    # Distribute costs over timeline
    total_days = int(cpm.project_duration) + 1
    if total_days <= 0:
        result.methodology = "Zero duration project"
        return result

    planned_daily = [0.0] * total_days
    actual_daily = [0.0] * total_days

    for task in schedule.activities:
        ar = cpm.activity_results.get(task.task_id)
        if ar is None or ar.duration <= 0:
            continue

        costs = cost_map.get(task.task_id, (0.0, 0.0, 0.0))
        planned_total, actual_total, _ = costs

        if planned_total <= 0:
            continue

        # Distribute planned cost linearly across duration
        start_day = max(0, int(ar.early_start))
        dur_days = max(1, int(ar.duration))
        daily_rate = planned_total / dur_days

        for d in range(start_day, min(start_day + dur_days, total_days)):
            planned_daily[d] += daily_rate

        # Distribute actual cost linearly across completed portion
        if actual_total > 0 and task.phys_complete_pct > 0:
            completed_days = max(1, int(dur_days * task.phys_complete_pct / 100))
            actual_rate = actual_total / completed_days
            for d in range(start_day, min(start_day + completed_days, total_days)):
                actual_daily[d] += actual_rate

    # Build cumulative curve
    planned_cum = 0.0
    actual_cum = 0.0
    curve: list[CashFlowPoint] = []
    peak_day = 0
    peak_amount = 0.0

    for d in range(total_days):
        planned_cum += planned_daily[d]
        actual_cum += actual_daily[d]
        curve.append(
            CashFlowPoint(
                day=d,
                planned_period=round(planned_daily[d], 2),
                actual_period=round(actual_daily[d], 2),
                planned_cumulative=round(planned_cum, 2),
                actual_cumulative=round(actual_cum, 2),
            )
        )
        if planned_daily[d] > peak_amount:
            peak_amount = planned_daily[d]
            peak_day = d

    result.total_planned_cost = round(planned_cum, 2)
    result.total_actual_cost = round(actual_cum, 2)
    result.total_remaining_cost = round(sum(c[2] for c in cost_map.values()), 2)
    result.budget_variance = round(planned_cum - actual_cum, 2)
    result.cost_performance_index = round(planned_cum / actual_cum, 3) if actual_cum > 0 else 0.0
    result.curve = curve
    result.peak_spend_day = peak_day
    result.peak_spend_amount = round(peak_amount, 2)

    result.methodology = (
        "Cash flow S-Curve: cost distributed linearly across CPM durations "
        f"({'proxy: duration-based' if use_proxy else 'TaskResource costs'}, "
        f"AACE RP 10S-90)"
    )

    result.summary = {
        "total_planned": result.total_planned_cost,
        "total_actual": result.total_actual_cost,
        "total_remaining": result.total_remaining_cost,
        "budget_variance": result.budget_variance,
        "cpi": result.cost_performance_index,
        "peak_spend_day": result.peak_spend_day,
        "project_duration_days": total_days,
        "cost_source": "proxy" if use_proxy else "task_resources",
        "methodology": result.methodology,
    }

    return result
