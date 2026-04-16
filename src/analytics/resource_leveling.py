# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Resource-constrained project scheduling (RCPSP) via Serial SGS.

Solves the resource-constrained scheduling problem using a Serial
Schedule Generation Scheme (SGS).  Activities are scheduled in priority
order at their earliest feasible start time, subject to both precedence
and resource constraints.

The algorithm:
1. Run unconstrained CPM to get the baseline schedule.
2. Build resource demand per activity from TaskResource data.
3. Iterate through activities in priority order (configurable rule).
4. For each activity, find the earliest start where resource capacity
   is not exceeded for the activity's full duration.
5. Re-compute floats on the leveled schedule.

References:
    - AACE RP 46R-11 — Required Skills and Knowledge of a Scheduling
      Professional (resource analysis)
    - PMI Practice Standard for Scheduling — Resource Leveling
    - Kelley & Walker (1959) — CPM with Resource Constraints
    - Kolisch (1996) — Serial and Parallel SGS for RCPSP
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.cpm import CPMCalculator, CPMResult
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)

_HOURS_PER_DAY = 8.0


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


@dataclass
class ResourceLimit:
    """Maximum available units for a resource type."""

    rsrc_id: str
    max_units: float = 1.0
    cost_per_unit_day: float = 0.0


@dataclass
class LevelingConfig:
    """Configuration for resource leveling."""

    resource_limits: list[ResourceLimit] = field(default_factory=list)
    priority_rule: str = "late_start"  # late_start, early_start, float, duration
    max_project_extension_pct: float | None = None  # e.g. 0.20 = max 20% extension


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


@dataclass
class ResourceDemand:
    """Resource demand for a single time period."""

    period: int  # Day index (0-based)
    rsrc_id: str
    demand: float  # Units demanded
    capacity: float  # Units available
    overloaded: bool = False


@dataclass
class ActivityShift:
    """How an activity was shifted during leveling."""

    task_id: str
    task_code: str
    task_name: str
    original_start: float  # Day
    leveled_start: float  # Day
    shift_days: float
    duration_days: float
    resources: dict[str, float] = field(default_factory=dict)  # rsrc_id → units


@dataclass
class ResourceProfile:
    """Resource usage profile over time for one resource."""

    rsrc_id: str
    rsrc_name: str
    max_units: float
    peak_demand: float
    demand_by_day: list[float] = field(default_factory=list)  # demand per day


@dataclass
class LevelingResult:
    """Complete resource leveling result."""

    original_duration_days: float = 0.0
    leveled_duration_days: float = 0.0
    extension_days: float = 0.0
    extension_pct: float = 0.0
    activity_shifts: list[ActivityShift] = field(default_factory=list)
    resource_profiles: list[ResourceProfile] = field(default_factory=list)
    overloaded_periods: int = 0
    leveling_iterations: int = 0
    priority_rule: str = ""
    methodology: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Priority rules
# ---------------------------------------------------------------------------

_PRIORITY_RULES = {
    "late_start": lambda tid, cpm: (
        cpm.activity_results[tid].late_start if tid in cpm.activity_results else 0
    ),
    "early_start": lambda tid, cpm: (
        cpm.activity_results[tid].early_start if tid in cpm.activity_results else 0
    ),
    "float": lambda tid, cpm: (
        cpm.activity_results[tid].total_float if tid in cpm.activity_results else 999
    ),
    "duration": lambda tid, cpm: (
        -(cpm.activity_results[tid].duration if tid in cpm.activity_results else 0)
    ),
}


# ---------------------------------------------------------------------------
# Core SGS algorithm
# ---------------------------------------------------------------------------


def _build_resource_demand(
    schedule: ParsedSchedule,
) -> dict[str, dict[str, float]]:
    """Build per-activity resource demand map: task_id → {rsrc_id: units}."""
    demand: dict[str, dict[str, float]] = {}
    for tr in schedule.task_resources:
        if tr.task_id not in demand:
            demand[tr.task_id] = {}
        # Use remain_qty if available, else target_qty
        qty = tr.remain_qty if tr.remain_qty > 0 else tr.target_qty
        if qty > 0:
            demand[tr.task_id][tr.rsrc_id] = demand[tr.task_id].get(tr.rsrc_id, 0) + qty
    return demand


def _get_predecessors(
    schedule: ParsedSchedule,
) -> dict[str, list[str]]:
    """Build predecessor map: task_id → [pred_task_ids]."""
    preds: dict[str, list[str]] = {}
    for rel in schedule.relationships:
        if rel.task_id not in preds:
            preds[rel.task_id] = []
        preds[rel.task_id].append(rel.pred_task_id)
    return preds


def _serial_sgs(
    schedule: ParsedSchedule,
    cpm: CPMResult,
    config: LevelingConfig,
) -> tuple[dict[str, float], int]:
    """Run Serial Schedule Generation Scheme.

    Returns:
        Tuple of (task_id → leveled_start_day, iterations).
    """
    task_map = {t.task_id: t for t in schedule.activities}
    resource_demand = _build_resource_demand(schedule)
    pred_map = _get_predecessors(schedule)

    # Resource capacity map
    capacity: dict[str, float] = {rl.rsrc_id: rl.max_units for rl in config.resource_limits}

    # Get all non-complete activity IDs with CPM results
    active_ids = [
        tid
        for tid in cpm.activity_results
        if task_map.get(tid) and task_map[tid].status_code.lower() != "tk_complete"
    ]

    # Sort by priority rule
    rule_fn = _PRIORITY_RULES.get(config.priority_rule, _PRIORITY_RULES["late_start"])
    active_ids.sort(key=lambda tid: rule_fn(tid, cpm))

    # Track resource usage: rsrc_id → {day: units_used}
    usage: dict[str, dict[int, float]] = {rid: {} for rid in capacity}

    # Schedule each activity
    leveled_start: dict[str, float] = {}
    iterations = 0

    for tid in active_ids:
        ar = cpm.activity_results[tid]
        dur = ar.duration
        if dur <= 0:
            leveled_start[tid] = ar.early_start
            continue

        dur_days = int(max(1, round(dur)))
        demands = resource_demand.get(tid, {})

        # Earliest start from predecessors
        earliest = 0.0
        for pred_id in pred_map.get(tid, []):
            if pred_id in leveled_start:
                pred_ar = cpm.activity_results.get(pred_id)
                pred_dur = pred_ar.duration if pred_ar else 0
                earliest = max(earliest, leveled_start[pred_id] + pred_dur)
            elif pred_id in cpm.activity_results:
                pred_ar = cpm.activity_results[pred_id]
                earliest = max(earliest, pred_ar.early_finish)

        # Find earliest feasible start (resource-constrained)
        start_day = int(max(0, round(earliest)))

        if demands and capacity:
            max_search = start_day + 5000  # Safety limit
            while start_day < max_search:
                feasible = True
                for d in range(start_day, start_day + dur_days):
                    for rsrc_id, qty in demands.items():
                        if rsrc_id in capacity:
                            current = usage.get(rsrc_id, {}).get(d, 0)
                            if current + qty > capacity[rsrc_id]:
                                feasible = False
                                break
                    if not feasible:
                        break

                if feasible:
                    break
                start_day += 1
                iterations += 1

        leveled_start[tid] = float(start_day)

        # Reserve resources
        for d in range(start_day, start_day + dur_days):
            for rsrc_id, qty in demands.items():
                if rsrc_id not in usage:
                    usage[rsrc_id] = {}
                usage[rsrc_id][d] = usage[rsrc_id].get(d, 0) + qty

    return leveled_start, iterations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def level_resources(
    schedule: ParsedSchedule,
    config: LevelingConfig,
) -> LevelingResult:
    """Run resource-constrained scheduling using Serial SGS.

    Args:
        schedule: The schedule with activities, relationships, and
            task_resources.
        config: Resource limits and priority configuration.

    Returns:
        A ``LevelingResult`` with original/leveled duration, activity
        shifts, and resource profiles.

    References:
        - AACE RP 46R-11 — Scheduling Professional Skills (resource analysis)
        - PMI Practice Standard for Scheduling — Resource Leveling
        - Kolisch (1996) — Serial SGS for RCPSP
        - Kelley & Walker (1959) — CPM Resource Extension
    """
    result = LevelingResult(priority_rule=config.priority_rule)

    # Run unconstrained CPM
    cpm = CPMCalculator(schedule, hours_per_day=_HOURS_PER_DAY).calculate()
    if cpm.has_cycles:
        result.methodology = "CPM detected cycles — leveling aborted"
        return result

    result.original_duration_days = round(cpm.project_duration, 1)

    task_map = {t.task_id: t for t in schedule.activities}
    resource_demand = _build_resource_demand(schedule)
    rsrc_name_map = {r.rsrc_id: r.rsrc_name for r in schedule.resources}

    # If no resource limits specified, return unconstrained result
    if not config.resource_limits:
        result.leveled_duration_days = result.original_duration_days
        result.methodology = "No resource limits specified — unconstrained CPM"
        return result

    # Run SGS
    leveled_starts, iterations = _serial_sgs(schedule, cpm, config)
    result.leveling_iterations = iterations

    # Compute leveled project duration
    max_finish = 0.0
    for tid, start in leveled_starts.items():
        ar = cpm.activity_results.get(tid)
        if ar:
            max_finish = max(max_finish, start + ar.duration)
    result.leveled_duration_days = round(max_finish, 1)
    result.extension_days = round(max_finish - cpm.project_duration, 1)
    if cpm.project_duration > 0:
        result.extension_pct = round(result.extension_days / cpm.project_duration * 100, 1)

    # Activity shifts
    for tid, start in leveled_starts.items():
        ar = cpm.activity_results.get(tid)
        if ar is None:
            continue
        task = task_map.get(tid)
        shift = start - ar.early_start
        if abs(shift) > 0.01 or resource_demand.get(tid):
            result.activity_shifts.append(
                ActivityShift(
                    task_id=tid,
                    task_code=ar.task_code,
                    task_name=task.task_name if task else ar.task_name,
                    original_start=round(ar.early_start, 1),
                    leveled_start=round(start, 1),
                    shift_days=round(shift, 1),
                    duration_days=round(ar.duration, 1),
                    resources=resource_demand.get(tid, {}),
                )
            )

    result.activity_shifts.sort(key=lambda s: abs(s.shift_days), reverse=True)

    # Resource profiles
    total_days = int(max_finish) + 1

    for rl in config.resource_limits:
        demand_by_day = [0.0] * total_days
        for tid, start in leveled_starts.items():
            ar = cpm.activity_results.get(tid)
            if ar is None:
                continue
            demands = resource_demand.get(tid, {})
            qty = demands.get(rl.rsrc_id, 0)
            if qty > 0:
                dur_days = int(max(1, round(ar.duration)))
                s = int(round(start))
                for d in range(s, min(s + dur_days, total_days)):
                    demand_by_day[d] += qty

        peak = max(demand_by_day) if demand_by_day else 0
        overloaded = sum(1 for d in demand_by_day if d > rl.max_units)
        result.overloaded_periods += overloaded

        result.resource_profiles.append(
            ResourceProfile(
                rsrc_id=rl.rsrc_id,
                rsrc_name=rsrc_name_map.get(rl.rsrc_id, rl.rsrc_id),
                max_units=rl.max_units,
                peak_demand=round(peak, 1),
                demand_by_day=[round(d, 1) for d in demand_by_day],
            )
        )

    result.methodology = (
        f"Resource-constrained scheduling via Serial SGS "
        f"(priority: {config.priority_rule}, "
        f"Kolisch 1996, AACE RP 46R-11)"
    )

    result.summary = {
        "original_duration_days": result.original_duration_days,
        "leveled_duration_days": result.leveled_duration_days,
        "extension_days": result.extension_days,
        "extension_pct": result.extension_pct,
        "activities_shifted": len([s for s in result.activity_shifts if s.shift_days > 0]),
        "overloaded_periods": result.overloaded_periods,
        "leveling_iterations": result.leveling_iterations,
        "priority_rule": config.priority_rule,
        "resources_constrained": len(config.resource_limits),
        "methodology": result.methodology,
        "references": [
            "AACE RP 46R-11 — Scheduling Professional Skills",
            "PMI Practice Standard for Scheduling — Resource Leveling",
            "Kolisch (1996) — Serial SGS for RCPSP",
            "Kelley & Walker (1959) — CPM Resource Extension",
        ],
    }

    return result


# ---------------------------------------------------------------------------
# As-scheduled resource profiles (no leveling)
# ---------------------------------------------------------------------------


def compute_resource_profiles(schedule: ParsedSchedule) -> list[ResourceProfile]:
    """Compute per-resource daily demand using CPM early dates.

    Distributes each activity's resource requirement uniformly across its
    duration, starting at the activity's early start day. Returns one
    ``ResourceProfile`` per resource with ``demand_by_day`` populated.

    No leveling is performed; this is the "as-scheduled" demand curve —
    useful for drawing histograms below a Gantt or detecting overloads
    before committing to a leveling pass.

    References:
        PMI Practice Standard for Scheduling — Resource Loading.
        AACE RP 46R-11 — Scheduling Professional Skills.
    """
    # Aggregate per-activity resource demand
    per_activity = _build_resource_demand(schedule)
    if not per_activity:
        return []

    # Resource name lookup
    name_lookup: dict[str, str] = {}
    for r in getattr(schedule, "resources", []) or []:
        rid = getattr(r, "rsrc_id", "")
        if rid:
            name_lookup[rid] = (
                getattr(r, "rsrc_name", "") or getattr(r, "rsrc_short_name", "") or rid
            )

    # CPM to get early_start per activity
    cpm = CPMCalculator(schedule).calculate()
    total_days = int(cpm.project_duration) + 1 if cpm.project_duration else 1

    # demand_by_resource_day[rsrc_id][day] = units
    demand: dict[str, list[float]] = {}
    for task in schedule.activities:
        rsrcs = per_activity.get(task.task_id, {})
        if not rsrcs:
            continue
        ar = cpm.activity_results.get(task.task_id)
        if ar is None:
            continue
        start_day = int(max(0, ar.early_start))
        duration_days = max(
            1,
            int(round((task.remain_drtn_hr_cnt or task.target_drtn_hr_cnt or 0) / _HOURS_PER_DAY)),
        )
        end_day = min(total_days, start_day + duration_days)
        for rsrc_id, qty in rsrcs.items():
            per_day_units = qty / duration_days if duration_days else qty
            profile = demand.setdefault(rsrc_id, [0.0] * total_days)
            if len(profile) < end_day:
                profile.extend([0.0] * (end_day - len(profile)))
            for d in range(start_day, end_day):
                profile[d] += per_day_units

    profiles: list[ResourceProfile] = []
    for rsrc_id, by_day in demand.items():
        peak = max(by_day) if by_day else 0.0
        profiles.append(
            ResourceProfile(
                rsrc_id=rsrc_id,
                rsrc_name=name_lookup.get(rsrc_id, rsrc_id),
                max_units=peak,  # As-scheduled: treat peak as capacity baseline
                peak_demand=peak,
                demand_by_day=by_day,
            )
        )

    # Sort by peak demand desc (most-loaded resources first)
    profiles.sort(key=lambda p: p.peak_demand, reverse=True)
    return profiles
