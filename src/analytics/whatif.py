# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""What-if schedule simulator — deterministic and probabilistic scenario analysis.

Applies duration adjustments to selected activities, re-runs CPM, and
returns the impact on project duration, critical path, and per-activity
dates.  Supports two modes:

1. **Deterministic** — single adjustment per activity, one CPM run.
2. **Probabilistic** — sample adjustments from a range, run CPM N times,
   return distribution with P-values.

The simulator uses the existing CPM engine (fully reentrant) to compute
each scenario.

References:
    - AACE RP 57R-09 — Schedule Risk Analysis (scenario modelling)
    - PMI PMBOK 7 S4.6 — Measurement Performance Domain
    - PMI Practice Standard for Scheduling — What-If Analysis
"""

from __future__ import annotations

import copy
import logging
import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from src.analytics.cpm import CPMCalculator, CPMResult
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


@dataclass
class DurationAdjustment:
    """A single duration adjustment for a what-if scenario.

    Target activities by ``task_code``, ``wbs_id`` prefix (e.g. ``"WBS:1.2"``),
    or ``"*"`` for all non-complete activities.
    """

    target: str  # task_code, "WBS:xxx", or "*"
    pct_change: float = 0.0  # e.g. 0.20 = +20%, -0.10 = -10%
    min_pct: float | None = None  # for probabilistic mode
    max_pct: float | None = None

    def get_pct(self, rng: random.Random | None = None) -> float:
        """Return the adjustment percentage (sampled if probabilistic)."""
        if self.min_pct is not None and self.max_pct is not None and rng:
            return rng.uniform(self.min_pct, self.max_pct)
        return self.pct_change


@dataclass
class WhatIfScenario:
    """Definition of a single what-if scenario."""

    name: str = "Scenario"
    adjustments: list[DurationAdjustment] = field(default_factory=list)
    iterations: int = 1  # 1 = deterministic, >1 = probabilistic


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


@dataclass
class ActivityImpact:
    """Per-activity impact of a what-if scenario."""

    task_id: str
    task_code: str
    task_name: str
    original_duration_days: float
    adjusted_duration_days: float
    delta_days: float
    original_total_float: float
    adjusted_total_float: float
    was_critical: bool
    is_critical: bool


@dataclass
class WhatIfResult:
    """Result of a what-if scenario simulation."""

    scenario_name: str = ""
    base_duration_days: float = 0.0
    adjusted_duration_days: float = 0.0  # mean if probabilistic
    delta_days: float = 0.0
    delta_pct: float = 0.0
    critical_path_changed: bool = False
    new_critical_path: list[str] = field(default_factory=list)
    activity_impacts: list[ActivityImpact] = field(default_factory=list)
    # Probabilistic fields
    iterations: int = 1
    distribution: list[float] = field(default_factory=list)
    p_values: dict[int, float] = field(default_factory=dict)
    std_days: float = 0.0
    methodology: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

_HOURS_PER_DAY = 8.0


def _matches_target(target: str, task_code: str, wbs_id: str) -> bool:
    """Check if a task matches an adjustment target."""
    if target == "*":
        return True
    if target.startswith("WBS:"):
        prefix = target[4:]
        return (wbs_id or "").startswith(prefix)
    return task_code == target


def _apply_adjustments(
    schedule: ParsedSchedule,
    adjustments: list[DurationAdjustment],
    rng: random.Random | None = None,
) -> ParsedSchedule:
    """Return a deep copy of the schedule with duration adjustments applied."""
    modified = copy.deepcopy(schedule)

    for task in modified.activities:
        if task.status_code.lower() == "tk_complete":
            continue
        for adj in adjustments:
            if _matches_target(adj.target, task.task_code, task.wbs_id):
                pct = adj.get_pct(rng)
                task.remain_drtn_hr_cnt = max(0.0, task.remain_drtn_hr_cnt * (1.0 + pct))
                task.target_drtn_hr_cnt = max(0.0, task.target_drtn_hr_cnt * (1.0 + pct))

    return modified


def _run_single(
    schedule: ParsedSchedule,
    adjustments: list[DurationAdjustment],
    base_cpm: CPMResult,
    rng: random.Random | None = None,
) -> tuple[float, CPMResult]:
    """Run a single what-if iteration. Returns (duration, cpm_result)."""
    modified = _apply_adjustments(schedule, adjustments, rng)
    cpm = CPMCalculator(modified, hours_per_day=_HOURS_PER_DAY).calculate()
    return cpm.project_duration, cpm


def _compute_impacts(
    base_cpm: CPMResult,
    adj_cpm: CPMResult,
    schedule: ParsedSchedule,
) -> list[ActivityImpact]:
    """Compute per-activity impact between base and adjusted CPM results."""
    impacts: list[ActivityImpact] = []
    task_map = {t.task_id: t for t in schedule.activities}

    for tid, base_ar in base_cpm.activity_results.items():
        adj_ar = adj_cpm.activity_results.get(tid)
        if adj_ar is None:
            continue
        task = task_map.get(tid)
        impacts.append(
            ActivityImpact(
                task_id=tid,
                task_code=base_ar.task_code,
                task_name=base_ar.task_name if task is None else task.task_name,
                original_duration_days=base_ar.duration,
                adjusted_duration_days=adj_ar.duration,
                delta_days=round(adj_ar.duration - base_ar.duration, 2),
                original_total_float=base_ar.total_float,
                adjusted_total_float=adj_ar.total_float,
                was_critical=base_ar.is_critical,
                is_critical=adj_ar.is_critical,
            )
        )

    # Sort by absolute delta descending
    impacts.sort(key=lambda x: abs(x.delta_days), reverse=True)
    return impacts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def simulate_whatif(
    schedule: ParsedSchedule,
    scenario: WhatIfScenario,
) -> WhatIfResult:
    """Run a what-if scenario on a schedule.

    Applies duration adjustments and re-runs CPM to determine the impact
    on project duration, critical path, and per-activity dates.

    Args:
        schedule: The schedule to analyze.
        scenario: The what-if scenario definition.

    Returns:
        A ``WhatIfResult`` with base vs. adjusted metrics.

    References:
        - AACE RP 57R-09 — Scenario Analysis
        - PMI PMBOK 7 S4.6 — Measurement Performance Domain
    """
    result = WhatIfResult(scenario_name=scenario.name)

    # Baseline CPM
    base_cpm = CPMCalculator(schedule, hours_per_day=_HOURS_PER_DAY).calculate()
    result.base_duration_days = round(base_cpm.project_duration, 1)
    base_cp_set = set(base_cpm.critical_path)

    if not scenario.adjustments:
        result.adjusted_duration_days = result.base_duration_days
        result.methodology = "No adjustments applied"
        return result

    iterations = max(1, scenario.iterations)
    result.iterations = iterations

    if iterations == 1:
        # Deterministic mode
        duration, adj_cpm = _run_single(schedule, scenario.adjustments, base_cpm)
        result.adjusted_duration_days = round(duration, 1)
        result.delta_days = round(duration - base_cpm.project_duration, 1)
        if base_cpm.project_duration > 0:
            result.delta_pct = round(result.delta_days / base_cpm.project_duration * 100, 1)
        result.new_critical_path = list(adj_cpm.critical_path)
        result.critical_path_changed = set(adj_cpm.critical_path) != base_cp_set
        result.activity_impacts = _compute_impacts(base_cpm, adj_cpm, schedule)
        result.methodology = "Deterministic what-if analysis (single CPM run)"

    else:
        # Probabilistic mode
        rng = random.Random(42)
        durations: list[float] = []

        for _ in range(iterations):
            dur, _ = _run_single(schedule, scenario.adjustments, base_cpm, rng)
            durations.append(dur)

        arr = np.array(durations)
        result.distribution = [round(d, 1) for d in sorted(durations)]
        result.adjusted_duration_days = round(float(np.mean(arr)), 1)
        result.std_days = round(float(np.std(arr)), 1)
        result.delta_days = round(result.adjusted_duration_days - base_cpm.project_duration, 1)
        if base_cpm.project_duration > 0:
            result.delta_pct = round(result.delta_days / base_cpm.project_duration * 100, 1)

        # P-values
        for p in [10, 25, 50, 75, 80, 90, 95]:
            result.p_values[p] = round(float(np.percentile(arr, p)), 1)

        # Run one deterministic for CP analysis
        _, adj_cpm = _run_single(schedule, scenario.adjustments, base_cpm)
        result.new_critical_path = list(adj_cpm.critical_path)
        result.critical_path_changed = set(adj_cpm.critical_path) != base_cp_set
        result.activity_impacts = _compute_impacts(base_cpm, adj_cpm, schedule)
        result.methodology = (
            f"Probabilistic what-if analysis ({iterations} iterations, "
            f"AACE RP 57R-09 scenario modelling)"
        )

    # Summary
    result.summary = {
        "scenario_name": scenario.name,
        "base_duration_days": result.base_duration_days,
        "adjusted_duration_days": result.adjusted_duration_days,
        "delta_days": result.delta_days,
        "delta_pct": result.delta_pct,
        "critical_path_changed": result.critical_path_changed,
        "iterations": result.iterations,
        "methodology": result.methodology,
        "adjustments_applied": len(scenario.adjustments),
        "activities_impacted": len([i for i in result.activity_impacts if i.delta_days != 0]),
        "references": [
            "AACE RP 57R-09 — Schedule Risk Analysis",
            "PMI PMBOK 7 S4.6 — Measurement Performance Domain",
        ],
    }
    if result.p_values:
        result.summary["p_values"] = result.p_values

    return result
