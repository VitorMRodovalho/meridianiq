# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Root Cause Analysis — backwards network trace to delay origin.

Walks backwards through the schedule dependency network from a target
activity (typically the project completion milestone) to identify the
chain of driving predecessors that determine the project end date.

At each step, the *driving predecessor* is the predecessor whose
early finish + lag produces the latest early start for the successor
(i.e., the predecessor that actually controls when work can begin).

The result is an ordered chain from target back to root cause — the
activity or constraint that ultimately drives the project completion.

Standards:
    - AACE RP 49R-06 — Identifying Critical Activities
    - AACE RP 29R-03 — Forensic Schedule Analysis (root cause identification)
    - PMI Practice Standard for Scheduling §6 — Critical Path Method
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import networkx as nx

from src.parser.models import ParsedSchedule, Task

logger = logging.getLogger(__name__)

_HOURS_PER_DAY = 8.0


@dataclass
class RootCauseStep:
    """A single step in the root cause chain.

    Attributes:
        task_id: The activity's system ID.
        task_code: The user-visible activity code.
        task_name: The activity description.
        duration_days: Remaining duration in days.
        total_float_days: Total float in days.
        early_start: Early start (days from project start).
        early_finish: Early finish (days from project start).
        is_critical: Whether this activity is on the critical path.
        is_constraint: Whether this activity has a hard constraint.
        constraint_type: The constraint type (if any).
        driving_reason: Why this predecessor drives the successor.
    """

    task_id: str = ""
    task_code: str = ""
    task_name: str = ""
    duration_days: float = 0.0
    total_float_days: float = 0.0
    early_start: float = 0.0
    early_finish: float = 0.0
    is_critical: bool = False
    is_constraint: bool = False
    constraint_type: str = ""
    driving_reason: str = ""


@dataclass
class RootCauseResult:
    """Result of root cause analysis.

    Attributes:
        target_activity: The starting activity (typically project end milestone).
        chain: Ordered list of driving predecessors from target to root cause.
            First element is the target itself, last is the root cause.
        chain_length: Number of steps in the chain.
        root_cause: The final activity in the chain (the originating cause).
        methodology: Description of the analysis methodology.
    """

    target_activity: str = ""
    chain: list[RootCauseStep] = field(default_factory=list)
    chain_length: int = 0
    root_cause: str = ""
    methodology: str = (
        "Backwards network trace per AACE RP 49R-06 and PMI Practice Standard "
        "for Scheduling. At each node, the driving predecessor is identified as "
        "the predecessor whose early finish + lag produces the latest early start "
        "for the successor. The trace continues until an activity with no "
        "predecessors or a hard constraint is reached."
    )


# Hard constraint types in P6
_HARD_CONSTRAINTS = {
    "cs_meoa",
    "cs_meob",
    "cs_meo",
    "cs_msoa",
    "cs_msob",
    "cs_mso",
    "cs_mandfin",
    "cs_mandstart",
}


def analyze_root_cause(
    schedule: ParsedSchedule,
    target_task_id: str | None = None,
    hours_per_day: float = _HOURS_PER_DAY,
    max_depth: int = 100,
) -> RootCauseResult:
    """Trace backwards from a target activity to find the root cause of delay.

    If no ``target_task_id`` is provided, the analysis starts from the
    activity with the latest early finish (the project completion driver).

    Args:
        schedule: Parsed schedule with activities and relationships.
        target_task_id: Starting activity for the trace. If None, uses
            the activity with the latest early finish.
        hours_per_day: Hours per working day for duration conversion.
        max_depth: Maximum chain depth to prevent infinite loops.

    Returns:
        RootCauseResult with the driving chain from target to root cause.

    References:
        AACE RP 49R-06 — Identifying Critical Activities.
        AACE RP 29R-03 — Forensic Schedule Analysis.
    """
    # Build task lookup
    task_map: dict[str, Task] = {t.task_id: t for t in schedule.activities}

    if not task_map:
        return RootCauseResult(target_activity=target_task_id or "")

    # Build NetworkX graph with CPM-like forward pass
    graph = nx.DiGraph()
    for task in schedule.activities:
        dur = task.remain_drtn_hr_cnt / hours_per_day
        if task.status_code.lower() == "tk_complete":
            dur = 0.0
        graph.add_node(task.task_id, duration=dur)

    # Predecessor map: for each task, which tasks are predecessors
    pred_map: dict[str, list[tuple[str, str, float]]] = {}  # succ -> [(pred, type, lag)]
    for rel in schedule.relationships:
        if rel.pred_task_id in task_map and rel.task_id in task_map:
            graph.add_edge(
                rel.pred_task_id,
                rel.task_id,
                pred_type=rel.pred_type,
                lag=rel.lag_hr_cnt / hours_per_day,
            )
            pred_map.setdefault(rel.task_id, []).append(
                (rel.pred_task_id, rel.pred_type, rel.lag_hr_cnt / hours_per_day)
            )

    # Check for cycles
    if not nx.is_directed_acyclic_graph(graph):
        logger.warning("Schedule contains cycles — root cause analysis aborted")
        return RootCauseResult(
            target_activity=target_task_id or "",
            methodology="Analysis aborted: schedule contains circular dependencies.",
        )

    # Forward pass to compute early start/finish
    es: dict[str, float] = {}
    ef: dict[str, float] = {}

    for node in nx.topological_sort(graph):
        dur = graph.nodes[node]["duration"]
        predecessors = list(graph.predecessors(node))
        if not predecessors:
            es[node] = 0.0
        else:
            max_es = 0.0
            for pred in predecessors:
                edge = graph.edges[pred, node]
                lag = edge.get("lag", 0.0)
                pred_type = edge.get("pred_type", "PR_FS")

                if pred_type.upper() == "PR_FS":
                    candidate = ef[pred] + lag
                elif pred_type.upper() == "PR_SS":
                    candidate = es[pred] + lag
                elif pred_type.upper() == "PR_FF":
                    candidate = ef[pred] + lag - dur
                elif pred_type.upper() == "PR_SF":
                    candidate = es[pred] + lag - dur
                else:
                    candidate = ef[pred] + lag

                max_es = max(max_es, candidate)
            es[node] = max_es
        ef[node] = es[node] + dur

    # Backward pass to compute total float
    project_duration = max(ef.values()) if ef else 0.0
    ls: dict[str, float] = {}
    lf: dict[str, float] = {}

    for node in reversed(list(nx.topological_sort(graph))):
        dur = graph.nodes[node]["duration"]
        successors = list(graph.successors(node))
        if not successors:
            lf[node] = project_duration
        else:
            min_lf = project_duration
            for succ in successors:
                edge = graph.edges[node, succ]
                lag = edge.get("lag", 0.0)
                pred_type = edge.get("pred_type", "PR_FS")

                if pred_type.upper() == "PR_FS":
                    candidate = ls[succ] - lag
                elif pred_type.upper() == "PR_SS":
                    candidate = ls[succ] - lag + dur
                elif pred_type.upper() == "PR_FF":
                    candidate = lf[succ] - lag
                elif pred_type.upper() == "PR_SF":
                    candidate = lf[succ] - lag + dur
                else:
                    candidate = ls[succ] - lag

                min_lf = min(min_lf, candidate)
            lf[node] = min_lf
        ls[node] = lf[node] - dur

    tf: dict[str, float] = {n: ls[n] - es[n] for n in graph.nodes}

    # Determine target activity
    if target_task_id and target_task_id in task_map:
        target = target_task_id
    else:
        # Use activity with latest early finish
        target = max(ef, key=lambda n: ef[n]) if ef else ""

    if not target:
        return RootCauseResult(target_activity=target_task_id or "")

    # Trace backwards
    chain: list[RootCauseStep] = []
    visited: set[str] = set()
    current = target

    while current and current not in visited and len(chain) < max_depth:
        visited.add(current)
        task = task_map[current]
        cstr = getattr(task, "cstr_type", "") or ""
        cstr2 = getattr(task, "cstr_type2", "") or ""
        has_constraint = cstr.lower() in _HARD_CONSTRAINTS or cstr2.lower() in _HARD_CONSTRAINTS

        step = RootCauseStep(
            task_id=current,
            task_code=task.task_code,
            task_name=task.task_name,
            duration_days=round(graph.nodes[current]["duration"], 2),
            total_float_days=round(tf.get(current, 0), 2),
            early_start=round(es.get(current, 0), 2),
            early_finish=round(ef.get(current, 0), 2),
            is_critical=abs(tf.get(current, 0)) < 0.01,
            is_constraint=has_constraint,
            constraint_type=cstr or cstr2 if has_constraint else "",
        )

        # Find driving predecessor
        preds = pred_map.get(current, [])
        if not preds:
            step.driving_reason = "No predecessors — this is the root cause"
            chain.append(step)
            break

        # Driving predecessor = the one that produces the latest ES for current
        driving_pred = None
        driving_es = -1.0
        driving_reason = ""

        for pred_id, pred_type, lag in preds:
            if pred_type.upper() == "PR_FS":
                candidate = ef[pred_id] + lag
                reason = f"FS: EF({pred_id})={ef[pred_id]:.1f} + lag={lag:.1f} = {candidate:.1f}"
            elif pred_type.upper() == "PR_SS":
                candidate = es[pred_id] + lag
                reason = f"SS: ES({pred_id})={es[pred_id]:.1f} + lag={lag:.1f} = {candidate:.1f}"
            elif pred_type.upper() == "PR_FF":
                candidate = ef[pred_id] + lag - graph.nodes[current]["duration"]
                reason = f"FF: EF({pred_id})={ef[pred_id]:.1f} + lag={lag:.1f} - dur={graph.nodes[current]['duration']:.1f}"
            elif pred_type.upper() == "PR_SF":
                candidate = es[pred_id] + lag - graph.nodes[current]["duration"]
                reason = f"SF: ES({pred_id})={es[pred_id]:.1f} + lag={lag:.1f} - dur={graph.nodes[current]['duration']:.1f}"
            else:
                candidate = ef[pred_id] + lag
                reason = f"FS(default): EF({pred_id})={ef[pred_id]:.1f}"

            if candidate > driving_es:
                driving_es = candidate
                driving_pred = pred_id
                driving_reason = reason

        step.driving_reason = f"Driven by {driving_pred}: {driving_reason}"
        chain.append(step)

        if has_constraint:
            step.driving_reason = f"Hard constraint ({cstr or cstr2}) — this constrains the chain"
            break

        current = driving_pred

    result = RootCauseResult(
        target_activity=target,
        chain=chain,
        chain_length=len(chain),
        root_cause=chain[-1].task_id if chain else "",
    )

    return result
