# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Time Impact Analysis (TIA) engine.

Implements prospective delay analysis per AACE RP 52R-06 and AACE RP 29R-03.
Inserts delay fragments into a schedule network and measures the impact on
the project completion date.

Methodology:
1. Load base schedule -> run CPM -> unimpacted completion
2. For each delay fragment:
   a. Copy the schedule network graph
   b. Insert fragment activities and relationships
   c. Run CPM on impacted network -> impacted completion
   d. Delay = impacted - unimpacted completion
3. Detect concurrent delays (overlapping fragments on CP)
4. Classify by responsibility

References:
    - AACE RP 52R-06 Time Impact Analysis -- As Applied in Construction
    - AACE RP 29R-03 Forensic Schedule Analysis
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import networkx as nx

from src.analytics.cpm import CPMCalculator, CPMResult, ActivityResult
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)

# Relationship type constants (matching cpm.py)
_FS = "PR_FS"
_FF = "PR_FF"
_SS = "PR_SS"
_SF = "PR_SF"

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


class ResponsibleParty(str, Enum):
    """Party responsible for a delay event."""

    OWNER = "owner"
    CONTRACTOR = "contractor"
    SHARED = "shared"
    THIRD_PARTY = "third_party"
    FORCE_MAJEURE = "force_majeure"


class DelayType(str, Enum):
    """Classification of a delay event per AACE RP 52R-06."""

    EXCUSABLE_COMPENSABLE = "excusable_compensable"
    EXCUSABLE_NON_COMPENSABLE = "excusable_non_compensable"
    NON_EXCUSABLE = "non_excusable"
    CONCURRENT = "concurrent"


@dataclass
class FragmentActivity:
    """A single activity within a delay fragment.

    Durations are in hours, consistent with P6 convention.
    """

    fragment_activity_id: str
    name: str
    duration_hours: float
    predecessors: list[dict[str, Any]] = field(default_factory=list)
    successors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DelayFragment:
    """A delay fragment to insert into the schedule network.

    A fragment represents a discrete delay event with one or more
    activities that tie into the existing schedule network.
    """

    fragment_id: str
    name: str
    description: str
    responsible_party: ResponsibleParty
    activities: list[FragmentActivity] = field(default_factory=list)


@dataclass
class TIAResult:
    """Result of analyzing a single delay fragment.

    Per AACE RP 52R-06, the delay is the difference between the
    impacted and unimpacted project completion dates.
    """

    fragment: DelayFragment
    unimpacted_completion_days: float = 0.0
    impacted_completion_days: float = 0.0
    delay_days: float = 0.0
    critical_path_affected: bool = False
    float_consumed_hours: float = 0.0
    delay_type: DelayType = DelayType.NON_EXCUSABLE
    concurrent_with: list[str] = field(default_factory=list)
    impacted_driving_path: list[str] = field(default_factory=list)


@dataclass
class TIAAnalysis:
    """Complete TIA output across all delay fragments.

    Aggregates per-fragment results and provides responsibility totals.
    """

    analysis_id: str
    project_name: str
    base_project_id: str
    fragments: list[DelayFragment] = field(default_factory=list)
    results: list[TIAResult] = field(default_factory=list)
    total_owner_delay: float = 0.0
    total_contractor_delay: float = 0.0
    total_shared_delay: float = 0.0
    net_delay: float = 0.0
    summary: dict[str, Any] = field(default_factory=dict)


class TimeImpactAnalyzer:
    """Perform Time Impact Analysis on a parsed P6 schedule.

    Per AACE RP 52R-06, the TIA methodology:
    1. Runs CPM on the unimpacted (base) schedule
    2. For each delay fragment, inserts fragment activities into a copy
       of the schedule network
    3. Runs CPM on the impacted network
    4. Measures the change in project completion date
    5. Classifies delays by type and detects concurrency

    Usage::

        analyzer = TimeImpactAnalyzer(schedule)
        result = analyzer.analyze_fragment(fragment)
        # or
        analysis = analyzer.analyze_all(fragments)
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
            hours_per_day: Hours per working day for duration conversion.
        """
        self.schedule = schedule
        self.hours_per_day = hours_per_day

        # Build the base CPM calculator and run it
        self._base_calc = CPMCalculator(schedule, hours_per_day=hours_per_day)
        self._base_cpm = self._base_calc.calculate()
        self._base_completion = self._base_cpm.project_duration
        self._base_cp = set(self._base_cpm.critical_path)

        # Build a task_code -> task_id lookup for connecting fragments
        self._code_to_id: dict[str, str] = {}
        for task in schedule.activities:
            if task.task_code:
                self._code_to_id[task.task_code] = task.task_id

        # Store the base graph for copying (rebuild it)
        self._base_graph = self._rebuild_base_graph()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_fragment(self, fragment: DelayFragment) -> TIAResult:
        """Analyze the impact of a single delay fragment.

        1. Build a copy of the CPM graph
        2. Insert fragment activities and relationships
        3. Run CPM on the impacted graph
        4. Compare completion dates

        Args:
            fragment: The delay fragment to analyze.

        Returns:
            A ``TIAResult`` with delay measurement and classification.
        """
        result = TIAResult(
            fragment=fragment,
            unimpacted_completion_days=self._base_completion,
        )

        # Build the impacted graph
        impacted_graph = self._build_impacted_graph(fragment)

        # Run CPM on the impacted graph
        impacted_duration, impacted_cp = self._run_impacted_cpm(impacted_graph)
        result.impacted_completion_days = impacted_duration

        # Calculate delay
        result.delay_days = round(impacted_duration - self._base_completion, 6)

        # Check if fragment activities appear on the impacted critical path
        fragment_ids = {a.fragment_activity_id for a in fragment.activities}
        result.critical_path_affected = bool(fragment_ids & set(impacted_cp))

        # Store the impacted driving path
        result.impacted_driving_path = impacted_cp

        # Calculate float consumed (for non-CP fragments)
        if not result.critical_path_affected and fragment.activities:
            # Float consumed = original float of the tie-in activity
            result.float_consumed_hours = self._estimate_float_consumed(fragment)

        # Classify the delay
        result.delay_type = self._classify_delay(
            fragment, result.delay_days, result.critical_path_affected
        )

        return result

    def analyze_all(self, fragments: list[DelayFragment]) -> TIAAnalysis:
        """Analyze all fragments and detect concurrency.

        Args:
            fragments: List of delay fragments to analyze.

        Returns:
            A ``TIAAnalysis`` with per-fragment results and totals.
        """
        project_name = ""
        base_project_id = ""
        if self.schedule.projects:
            project_name = self.schedule.projects[0].proj_short_name
            base_project_id = self.schedule.projects[0].proj_id

        analysis = TIAAnalysis(
            analysis_id=f"tia-{uuid.uuid4().hex[:8]}",
            project_name=project_name,
            base_project_id=base_project_id,
            fragments=list(fragments),
        )

        # Analyze each fragment individually
        for fragment in fragments:
            result = self.analyze_fragment(fragment)
            analysis.results.append(result)

        # Detect concurrency
        self._detect_concurrency(analysis.results)

        # Calculate totals by responsibility
        for r in analysis.results:
            delay = max(0.0, r.delay_days)
            party = r.fragment.responsible_party

            if party == ResponsibleParty.OWNER:
                analysis.total_owner_delay += delay
            elif party == ResponsibleParty.CONTRACTOR:
                analysis.total_contractor_delay += delay
            elif party in (
                ResponsibleParty.SHARED,
                ResponsibleParty.THIRD_PARTY,
                ResponsibleParty.FORCE_MAJEURE,
            ):
                analysis.total_shared_delay += delay

        analysis.net_delay = round(
            analysis.total_owner_delay
            + analysis.total_contractor_delay
            + analysis.total_shared_delay,
            6,
        )

        # Build summary
        analysis.summary = self._build_summary(analysis)

        return analysis

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _rebuild_base_graph(self) -> nx.DiGraph:
        """Rebuild the base schedule graph from the parsed schedule.

        Replicates the graph construction logic from CPMCalculator so
        we have a standalone DiGraph we can copy and modify.

        Returns:
            A NetworkX DiGraph representing the unimpacted schedule.
        """
        graph = nx.DiGraph()

        task_map = {t.task_id: t for t in self.schedule.activities}

        for task in self.schedule.activities:
            duration_days = task.remain_drtn_hr_cnt / self.hours_per_day
            if task.status_code == "TK_Complete":
                duration_days = 0.0
            graph.add_node(
                task.task_id,
                duration=duration_days,
                task_code=task.task_code,
                task_name=task.task_name,
            )

        for rel in self.schedule.relationships:
            pred_id = rel.pred_task_id
            succ_id = rel.task_id
            if pred_id not in task_map or succ_id not in task_map:
                continue

            rel_type = _TYPE_ALIASES.get(rel.pred_type, _FS)
            lag_days = rel.lag_hr_cnt / self.hours_per_day

            graph.add_edge(
                pred_id,
                succ_id,
                rel_type=rel_type,
                lag=lag_days,
            )

        return graph

    def _build_impacted_graph(self, fragment: DelayFragment) -> nx.DiGraph:
        """Create a copy of the schedule graph with fragment inserted.

        1. Copy the existing base graph
        2. Add fragment activities as new nodes
        3. Add edges from fragment predecessors (connecting to existing
           activities by task_code)
        4. Add edges to fragment successors

        Args:
            fragment: The delay fragment to insert.

        Returns:
            A modified DiGraph with the fragment activities inserted.
        """
        graph = self._base_graph.copy()

        # Build a lookup of fragment activity IDs for intra-fragment edges
        frag_act_ids = {a.fragment_activity_id for a in fragment.activities}

        for frag_act in fragment.activities:
            # Add fragment activity as a new node
            duration_days = frag_act.duration_hours / self.hours_per_day
            graph.add_node(
                frag_act.fragment_activity_id,
                duration=duration_days,
                task_code=frag_act.fragment_activity_id,
                task_name=frag_act.name,
            )

            # Add predecessor edges (existing activities -> fragment activity)
            for pred_spec in frag_act.predecessors:
                pred_code = pred_spec.get("activity_code", "")
                rel_type_raw = pred_spec.get("rel_type", "FS")
                lag_hours = pred_spec.get("lag_hours", 0.0)

                rel_type = _TYPE_ALIASES.get(rel_type_raw, _FS)
                lag_days = lag_hours / self.hours_per_day

                # Resolve the predecessor: could be an existing activity
                # or another fragment activity
                if pred_code in frag_act_ids:
                    pred_node = pred_code
                else:
                    pred_node = self._code_to_id.get(pred_code)

                if pred_node is None:
                    logger.warning(
                        "Fragment %s: predecessor %s not found in schedule",
                        fragment.fragment_id,
                        pred_code,
                    )
                    continue

                if pred_node not in graph:
                    logger.warning(
                        "Fragment %s: predecessor node %s not in graph",
                        fragment.fragment_id,
                        pred_node,
                    )
                    continue

                graph.add_edge(
                    pred_node,
                    frag_act.fragment_activity_id,
                    rel_type=rel_type,
                    lag=lag_days,
                )

            # Add successor edges (fragment activity -> existing activities)
            for succ_spec in frag_act.successors:
                succ_code = succ_spec.get("activity_code", "")
                rel_type_raw = succ_spec.get("rel_type", "FS")
                lag_hours = succ_spec.get("lag_hours", 0.0)

                rel_type = _TYPE_ALIASES.get(rel_type_raw, _FS)
                lag_days = lag_hours / self.hours_per_day

                # Resolve the successor: could be an existing activity
                # or another fragment activity
                if succ_code in frag_act_ids:
                    succ_node = succ_code
                else:
                    succ_node = self._code_to_id.get(succ_code)

                if succ_node is None:
                    logger.warning(
                        "Fragment %s: successor %s not found in schedule",
                        fragment.fragment_id,
                        succ_code,
                    )
                    continue

                if succ_node not in graph:
                    logger.warning(
                        "Fragment %s: successor node %s not in graph",
                        fragment.fragment_id,
                        succ_node,
                    )
                    continue

                graph.add_edge(
                    frag_act.fragment_activity_id,
                    succ_node,
                    rel_type=rel_type,
                    lag=lag_days,
                )

        return graph

    # ------------------------------------------------------------------
    # CPM on impacted graph
    # ------------------------------------------------------------------

    def _run_impacted_cpm(
        self, graph: nx.DiGraph
    ) -> tuple[float, list[str]]:
        """Run forward/backward pass on impacted graph.

        Replicates the CPM logic from CPMCalculator on a raw NetworkX
        graph, since the calculator expects a ParsedSchedule.

        Args:
            graph: The impacted schedule graph.

        Returns:
            Tuple of (project_duration, critical_path_node_ids).
        """
        # Check for cycles
        if not nx.is_directed_acyclic_graph(graph):
            logger.error("Impacted graph contains cycles -- CPM aborted")
            return self._base_completion, []

        if not graph.nodes:
            return 0.0, []

        topo_order = list(nx.topological_sort(graph))

        # Forward pass: calculate ES and EF
        es: dict[str, float] = {}
        ef: dict[str, float] = {}

        for node_id in topo_order:
            duration = graph.nodes[node_id].get("duration", 0.0)

            # Determine ES from predecessors
            node_es = 0.0
            for pred_id in graph.predecessors(node_id):
                edge = graph.edges[pred_id, node_id]
                rel_type = edge.get("rel_type", _FS)
                lag = edge.get("lag", 0.0)

                imposed = self._forward_constraint(
                    es[pred_id], ef[pred_id], duration, rel_type, lag
                )
                if imposed > node_es:
                    node_es = imposed

            es[node_id] = node_es
            ef[node_id] = node_es + duration

        # Project duration
        project_duration = max(ef.values()) if ef else 0.0

        # Backward pass: calculate LS and LF
        ls: dict[str, float] = {}
        lf: dict[str, float] = {}

        for node_id in reversed(topo_order):
            duration = graph.nodes[node_id].get("duration", 0.0)

            # Determine LF from successors
            node_lf = project_duration
            has_successor = False

            for succ_id in graph.successors(node_id):
                has_successor = True
                edge = graph.edges[node_id, succ_id]
                rel_type = edge.get("rel_type", _FS)
                lag = edge.get("lag", 0.0)

                imposed = self._backward_constraint(
                    ls[succ_id], lf[succ_id], duration, rel_type, lag
                )
                if imposed < node_lf:
                    node_lf = imposed

            if not has_successor:
                node_lf = project_duration

            lf[node_id] = node_lf
            ls[node_id] = node_lf - duration

        # Identify critical path (TF ~= 0)
        critical_path: list[str] = []
        for node_id in topo_order:
            total_float = ls[node_id] - es[node_id]
            if abs(total_float) < 1e-6:
                critical_path.append(node_id)

        return project_duration, critical_path

    @staticmethod
    def _forward_constraint(
        pred_es: float,
        pred_ef: float,
        succ_duration: float,
        rel_type: str,
        lag: float,
    ) -> float:
        """Compute the earliest start imposed on a successor by one predecessor.

        Args:
            pred_es: Predecessor early start.
            pred_ef: Predecessor early finish.
            succ_duration: Duration of the successor activity.
            rel_type: Relationship type.
            lag: Lag in days.

        Returns:
            The earliest permissible start of the successor.
        """
        if rel_type == _FS:
            return pred_ef + lag
        elif rel_type == _SS:
            return pred_es + lag
        elif rel_type == _FF:
            return pred_ef + lag - succ_duration
        elif rel_type == _SF:
            return pred_es + lag - succ_duration
        return pred_ef + lag  # default FS

    @staticmethod
    def _backward_constraint(
        succ_ls: float,
        succ_lf: float,
        pred_duration: float,
        rel_type: str,
        lag: float,
    ) -> float:
        """Compute the latest finish imposed on a predecessor by one successor.

        Args:
            succ_ls: Successor late start.
            succ_lf: Successor late finish.
            pred_duration: Duration of the predecessor activity.
            rel_type: Relationship type.
            lag: Lag in days.

        Returns:
            The latest permissible finish of the predecessor.
        """
        if rel_type == _FS:
            return succ_ls - lag
        elif rel_type == _SS:
            return succ_ls - lag + pred_duration
        elif rel_type == _FF:
            return succ_lf - lag
        elif rel_type == _SF:
            return succ_lf - lag + pred_duration
        return succ_ls - lag  # default FS

    # ------------------------------------------------------------------
    # Classification and concurrency
    # ------------------------------------------------------------------

    def _classify_delay(
        self,
        fragment: DelayFragment,
        delay_days: float,
        cp_affected: bool,
    ) -> DelayType:
        """Classify the delay type based on responsibility and CP impact.

        Per AACE RP 52R-06 and standard construction contract provisions:
        - Owner delays -> excusable compensable
        - Contractor delays -> non-excusable
        - Shared/force majeure -> excusable non-compensable

        Args:
            fragment: The delay fragment.
            delay_days: Measured delay in days.
            cp_affected: Whether the fragment is on the critical path.

        Returns:
            The classified ``DelayType``.
        """
        if delay_days <= 0:
            return DelayType.NON_EXCUSABLE  # No actual project delay
        if fragment.responsible_party == ResponsibleParty.OWNER:
            return DelayType.EXCUSABLE_COMPENSABLE
        elif fragment.responsible_party == ResponsibleParty.CONTRACTOR:
            return DelayType.NON_EXCUSABLE
        elif fragment.responsible_party in (
            ResponsibleParty.SHARED,
            ResponsibleParty.FORCE_MAJEURE,
            ResponsibleParty.THIRD_PARTY,
        ):
            return DelayType.EXCUSABLE_NON_COMPENSABLE
        return DelayType.NON_EXCUSABLE

    def _detect_concurrency(self, results: list[TIAResult]) -> None:
        """Mark fragments as concurrent if they both affect the critical path.

        Two fragments are concurrent if both have delay_days > 0 and
        critical_path_affected is True.  In that case, the combined
        delay does not equal the sum of individual delays.

        Args:
            results: List of TIA results to check for concurrency.
        """
        cp_fragments = [
            r for r in results
            if r.delay_days > 0 and r.critical_path_affected
        ]

        if len(cp_fragments) < 2:
            return

        # Mark all CP-affecting fragments as concurrent with each other
        for i, r1 in enumerate(cp_fragments):
            for j, r2 in enumerate(cp_fragments):
                if i != j:
                    r1.concurrent_with.append(r2.fragment.fragment_id)

        # Reclassify concurrent fragments
        for r in cp_fragments:
            if r.concurrent_with:
                r.delay_type = DelayType.CONCURRENT

    def _estimate_float_consumed(self, fragment: DelayFragment) -> float:
        """Estimate how much float a non-CP fragment consumes.

        Looks at the tie-in activity's total float from the base CPM
        result and compares it to the fragment's total duration.

        Args:
            fragment: The delay fragment.

        Returns:
            Estimated float consumed in hours.
        """
        total_fragment_duration_hours = sum(
            a.duration_hours for a in fragment.activities
        )

        # Find the tie-in activity's float
        max_float_hours = 0.0
        for frag_act in fragment.activities:
            for pred_spec in frag_act.predecessors:
                pred_code = pred_spec.get("activity_code", "")
                pred_id = self._code_to_id.get(pred_code)
                if pred_id and pred_id in self._base_cpm.activity_results:
                    ar = self._base_cpm.activity_results[pred_id]
                    float_hours = ar.total_float * self.hours_per_day
                    if float_hours > max_float_hours:
                        max_float_hours = float_hours

        return min(total_fragment_duration_hours, max_float_hours)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _build_summary(self, analysis: TIAAnalysis) -> dict[str, Any]:
        """Build a summary dictionary for the TIA analysis.

        Args:
            analysis: The completed analysis.

        Returns:
            Dictionary with summary metrics.
        """
        fragments_on_cp = sum(
            1 for r in analysis.results if r.critical_path_affected
        )
        fragments_with_delay = sum(
            1 for r in analysis.results if r.delay_days > 0
        )
        concurrent_count = sum(
            1 for r in analysis.results if r.delay_type == DelayType.CONCURRENT
        )

        return {
            "fragment_count": len(analysis.fragments),
            "fragments_on_cp": fragments_on_cp,
            "fragments_with_delay": fragments_with_delay,
            "concurrent_fragments": concurrent_count,
            "base_completion_days": self._base_completion,
            "total_owner_delay": round(analysis.total_owner_delay, 2),
            "total_contractor_delay": round(analysis.total_contractor_delay, 2),
            "total_shared_delay": round(analysis.total_shared_delay, 2),
            "net_delay": round(analysis.net_delay, 2),
            "delay_by_type": {
                dt.value: sum(
                    1 for r in analysis.results if r.delay_type == dt
                )
                for dt in DelayType
            },
        }
