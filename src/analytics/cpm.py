# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Critical Path Method (CPM) calculator using NetworkX.

Builds a directed activity-on-node graph from parsed P6 schedule data,
performs forward and backward passes, and identifies the critical path
based on total float.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from src.parser.models import ParsedSchedule, Relationship, Task

logger = logging.getLogger(__name__)

# Relationship type constants (P6 uses PR_ prefix)
_FS = "PR_FS"
_FF = "PR_FF"
_SS = "PR_SS"
_SF = "PR_SF"

# Also handle short forms without PR_ prefix
_TYPE_ALIASES: dict[str, str] = {
    "FS": _FS,
    "FF": _FF,
    "SS": _SS,
    "SF": _SF,
    "PR_FS": _FS,
    "PR_FF": _FF,
    "PR_SS": _SS,
    "PR_SF": _SF,
}


@dataclass
class ActivityResult:
    """CPM calculation results for a single activity."""

    task_id: str
    task_code: str = ""
    task_name: str = ""
    duration: float = 0.0
    early_start: float = 0.0
    early_finish: float = 0.0
    late_start: float = 0.0
    late_finish: float = 0.0
    total_float: float = 0.0
    free_float: float = 0.0
    is_critical: bool = False


@dataclass
class CPMResult:
    """Full CPM analysis output."""

    activity_results: dict[str, ActivityResult] = field(default_factory=dict)
    critical_path: list[str] = field(default_factory=list)
    project_duration: float = 0.0
    has_cycles: bool = False
    cycle_nodes: list[str] = field(default_factory=list)


class CPMCalculator:
    """Calculate the Critical Path Method for a parsed P6 schedule.

    Usage::

        calc = CPMCalculator(schedule)
        result = calc.calculate()
        print("Critical path:", result.critical_path)
        print("Project duration:", result.project_duration)
    """

    def __init__(
        self,
        schedule: ParsedSchedule,
        hours_per_day: float = 8.0,
    ) -> None:
        """Initialise with a parsed schedule.

        Args:
            schedule: Parsed XER schedule containing activities and
                relationships.
            hours_per_day: Hours per working day (used to convert hour-based
                durations into day units for readability).
        """
        self.schedule = schedule
        self.hours_per_day = hours_per_day
        self._graph: nx.DiGraph = nx.DiGraph()
        self._task_map: dict[str, Task] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(self) -> CPMResult:
        """Run the full CPM calculation.

        Returns:
            A ``CPMResult`` with per-activity ES/EF/LS/LF/TF/FF and the
            critical path list.
        """
        result = CPMResult()

        self._build_graph()

        # Check for cycles
        if not nx.is_directed_acyclic_graph(self._graph):
            result.has_cycles = True
            try:
                cycle = list(nx.find_cycle(self._graph))
                result.cycle_nodes = [str(n) for n, _ in cycle]
            except nx.NetworkXNoCycle:
                pass
            logger.error("Schedule graph contains cycles -- CPM aborted")
            return result

        if not self._graph.nodes:
            logger.warning("No activities in graph")
            return result

        self._forward_pass(result)
        self._backward_pass(result)
        self._calculate_floats(result)
        self._identify_critical_path(result)

        return result

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> None:
        """Build a directed graph from activities and relationships.

        Each activity becomes a node.  Each relationship becomes one or
        more edges with attributes for the relationship type and lag.
        """
        self._task_map = {t.task_id: t for t in self.schedule.activities}

        for task in self.schedule.activities:
            duration_days = task.remain_drtn_hr_cnt / self.hours_per_day
            if task.status_code == "TK_Complete":
                duration_days = 0.0
            self._graph.add_node(
                task.task_id,
                duration=duration_days,
                task_code=task.task_code,
                task_name=task.task_name,
            )

        for rel in self.schedule.relationships:
            pred_id = rel.pred_task_id
            succ_id = rel.task_id
            if pred_id not in self._task_map or succ_id not in self._task_map:
                logger.warning(
                    "Relationship references unknown task: %s -> %s",
                    pred_id,
                    succ_id,
                )
                continue

            rel_type = _TYPE_ALIASES.get(rel.pred_type, _FS)
            lag_days = rel.lag_hr_cnt / self.hours_per_day

            self._graph.add_edge(
                pred_id,
                succ_id,
                rel_type=rel_type,
                lag=lag_days,
            )

    # ------------------------------------------------------------------
    # Forward pass
    # ------------------------------------------------------------------

    def _forward_pass(self, result: CPMResult) -> None:
        """Calculate Early Start and Early Finish for every activity.

        Process nodes in topological order.  For each activity the ES is
        the maximum of all predecessor-imposed dates, and EF = ES + duration.

        Args:
            result: The result object to populate.
        """
        topo_order = list(nx.topological_sort(self._graph))

        for node_id in topo_order:
            duration = self._graph.nodes[node_id]["duration"]
            task_code = self._graph.nodes[node_id].get("task_code", "")
            task_name = self._graph.nodes[node_id].get("task_name", "")

            ar = ActivityResult(
                task_id=node_id,
                task_code=task_code,
                task_name=task_name,
                duration=duration,
            )

            # Determine ES from predecessors
            es = 0.0
            for pred_id in self._graph.predecessors(node_id):
                edge = self._graph.edges[pred_id, node_id]
                rel_type = edge["rel_type"]
                lag = edge["lag"]
                pred_ar = result.activity_results.get(pred_id)
                if pred_ar is None:
                    continue

                imposed = self._forward_constraint(pred_ar, duration, rel_type, lag)
                if imposed > es:
                    es = imposed

            ar.early_start = es
            ar.early_finish = es + duration
            result.activity_results[node_id] = ar

        # Project duration is the maximum EF
        if result.activity_results:
            result.project_duration = max(
                ar.early_finish for ar in result.activity_results.values()
            )

    @staticmethod
    def _forward_constraint(
        pred: ActivityResult,
        succ_duration: float,
        rel_type: str,
        lag: float,
    ) -> float:
        """Compute the earliest start imposed on a successor by one predecessor.

        Args:
            pred: Predecessor activity result (with ES/EF already set).
            succ_duration: Duration of the successor activity.
            rel_type: Relationship type (PR_FS, PR_FF, PR_SS, PR_SF).
            lag: Lag in days (negative = lead).

        Returns:
            The earliest permissible start of the successor.
        """
        if rel_type == _FS:
            return pred.early_finish + lag
        elif rel_type == _SS:
            return pred.early_start + lag
        elif rel_type == _FF:
            # FF: succ EF >= pred EF + lag  =>  succ ES >= pred EF + lag - succ_dur
            return pred.early_finish + lag - succ_duration
        elif rel_type == _SF:
            # SF: succ EF >= pred ES + lag  =>  succ ES >= pred ES + lag - succ_dur
            return pred.early_start + lag - succ_duration
        return pred.early_finish + lag  # default FS

    # ------------------------------------------------------------------
    # Backward pass
    # ------------------------------------------------------------------

    def _backward_pass(self, result: CPMResult) -> None:
        """Calculate Late Start and Late Finish for every activity.

        Process nodes in reverse topological order.  For each activity LF
        is the minimum of all successor-imposed dates, and LS = LF - duration.

        Args:
            result: The result object to populate.
        """
        project_end = result.project_duration
        topo_order = list(nx.topological_sort(self._graph))

        for node_id in reversed(topo_order):
            ar = result.activity_results[node_id]

            # Determine LF from successors
            lf = project_end  # default for activities with no successor
            has_successor = False

            for succ_id in self._graph.successors(node_id):
                has_successor = True
                edge = self._graph.edges[node_id, succ_id]
                rel_type = edge["rel_type"]
                lag = edge["lag"]
                succ_ar = result.activity_results.get(succ_id)
                if succ_ar is None:
                    continue

                imposed = self._backward_constraint(
                    succ_ar, ar.duration, rel_type, lag
                )
                if imposed < lf:
                    lf = imposed

            if not has_successor:
                lf = project_end

            ar.late_finish = lf
            ar.late_start = lf - ar.duration

    @staticmethod
    def _backward_constraint(
        succ: ActivityResult,
        pred_duration: float,
        rel_type: str,
        lag: float,
    ) -> float:
        """Compute the latest finish imposed on a predecessor by one successor.

        Args:
            succ: Successor activity result (with LS/LF already set).
            pred_duration: Duration of the predecessor activity.
            rel_type: Relationship type.
            lag: Lag in days.

        Returns:
            The latest permissible finish of the predecessor.
        """
        if rel_type == _FS:
            # FS: pred LF = succ LS - lag
            return succ.late_start - lag
        elif rel_type == _SS:
            # SS: pred LS = succ LS - lag  =>  pred LF = succ LS - lag + pred_dur
            return succ.late_start - lag + pred_duration
        elif rel_type == _FF:
            # FF: pred LF = succ LF - lag
            return succ.late_finish - lag
        elif rel_type == _SF:
            # SF: pred LS = succ LF - lag  =>  pred LF = succ LF - lag + pred_dur
            return succ.late_finish - lag + pred_duration
        return succ.late_start - lag  # default FS

    # ------------------------------------------------------------------
    # Float calculation
    # ------------------------------------------------------------------

    def _calculate_floats(self, result: CPMResult) -> None:
        """Calculate Total Float and Free Float for every activity.

        Total Float  = LS - ES  (or equivalently LF - EF).
        Free Float   = min(successor ES) - EF  (for FS relationships).

        Args:
            result: The result object to populate.
        """
        for node_id, ar in result.activity_results.items():
            ar.total_float = round(ar.late_start - ar.early_start, 6)

            # Free float: how much this activity can slip without
            # affecting any immediate successor
            min_succ_es = float("inf")
            for succ_id in self._graph.successors(node_id):
                edge = self._graph.edges[node_id, succ_id]
                rel_type = edge["rel_type"]
                lag = edge["lag"]
                succ_ar = result.activity_results.get(succ_id)
                if succ_ar is None:
                    continue

                if rel_type == _FS:
                    slack = succ_ar.early_start - ar.early_finish - lag
                elif rel_type == _SS:
                    slack = succ_ar.early_start - ar.early_start - lag
                elif rel_type == _FF:
                    slack = succ_ar.early_finish - ar.early_finish - lag
                elif rel_type == _SF:
                    slack = succ_ar.early_finish - ar.early_start - lag
                else:
                    slack = succ_ar.early_start - ar.early_finish - lag

                if slack < min_succ_es:
                    min_succ_es = slack

            if min_succ_es == float("inf"):
                # No successors -- free float equals total float
                ar.free_float = ar.total_float
            else:
                ar.free_float = round(max(0.0, min_succ_es), 6)

    # ------------------------------------------------------------------
    # Critical path identification
    # ------------------------------------------------------------------

    def _identify_critical_path(self, result: CPMResult) -> None:
        """Mark activities on the critical path (TF == 0) and build path list.

        The critical path is the longest chain through the network; it
        consists of all activities with zero total float, sorted in
        topological order.

        Args:
            result: The result object to populate.
        """
        topo_order = list(nx.topological_sort(self._graph))
        critical_ids: list[str] = []

        for node_id in topo_order:
            ar = result.activity_results[node_id]
            if abs(ar.total_float) < 1e-6:
                ar.is_critical = True
                critical_ids.append(node_id)

        result.critical_path = critical_ids
