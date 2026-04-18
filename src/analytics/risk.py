# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Monte Carlo schedule risk simulation per AACE RP 57R-09.

Implements Quantitative Schedule Risk Analysis (QSRA) using Monte Carlo
simulation.  Samples activity durations from probability distributions,
runs CPM for each iteration, and produces completion date probability
distributions, criticality indices, and sensitivity analysis.

References:
    - AACE RP 57R-09: Integrated Cost and Schedule Risk Analysis
    - AACE RP 41R-08: Risk Analysis and Contingency Determination
    - AACE RP 65R-11: Integrated Cost and Schedule Risk Analysis Using
      Monte Carlo Simulation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from collections.abc import Callable
from typing import Any

import networkx as nx
import numpy as np

from src.analytics.cpm import CPMCalculator, _FS, _FF, _SS, _SF
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


# ── Enumerations ─────────────────────────────────────────────────────


class DistributionType(str, Enum):
    """Probability distribution types for activity duration sampling."""

    TRIANGULAR = "triangular"
    PERT = "pert"
    UNIFORM = "uniform"
    LOGNORMAL = "lognormal"
    FIXED = "fixed"


# ── Data classes ─────────────────────────────────────────────────────


@dataclass
class DurationRisk:
    """Duration risk specification for a single activity.

    All durations are in hours to match P6 ``target_drtn_hr_cnt``.

    Attributes:
        activity_id: The task_code (or task_id) of the activity.
        distribution: The probability distribution to sample from.
        min_duration: Optimistic duration in hours.
        most_likely: Most likely duration in hours.
        max_duration: Pessimistic duration in hours.
    """

    activity_id: str
    distribution: DistributionType = DistributionType.PERT
    min_duration: float = 0.0
    most_likely: float = 0.0
    max_duration: float = 0.0


@dataclass
class RiskEvent:
    """A discrete risk event that may affect one or more activities.

    Attributes:
        risk_id: Unique identifier for this risk event.
        name: Human-readable name.
        probability: Probability of occurrence per iteration (0.0-1.0).
        impact_hours: Additional hours added when the event fires.
        affected_activities: List of activity_ids (task_code) impacted.
    """

    risk_id: str
    name: str = ""
    probability: float = 0.0
    impact_hours: float = 0.0
    affected_activities: list[str] = field(default_factory=list)


@dataclass
class SimulationConfig:
    """Configuration for a Monte Carlo simulation run.

    Attributes:
        iterations: Number of Monte Carlo iterations.
        default_distribution: Distribution for activities without explicit risk.
        default_uncertainty: Default +/- uncertainty as fraction (0.2 = 20%).
        seed: Random seed for reproducibility (None = random).
        confidence_levels: P-value percentiles to compute.
    """

    iterations: int = 1000
    default_distribution: DistributionType = DistributionType.PERT
    default_uncertainty: float = 0.2
    seed: int | None = None
    confidence_levels: list[int] = field(default_factory=lambda: [10, 25, 50, 75, 80, 90])


# ── Result data classes ──────────────────────────────────────────────


@dataclass
class HistogramBin:
    """A single bin of the completion-duration histogram.

    Attributes:
        bin_start: Left edge of the bin (days).
        bin_end: Right edge of the bin (days).
        count: Number of iterations in this bin.
        frequency: Fraction of iterations in this bin (0.0-1.0).
    """

    bin_start: float = 0.0
    bin_end: float = 0.0
    count: int = 0
    frequency: float = 0.0


@dataclass
class CriticalityEntry:
    """Criticality index for a single activity.

    Attributes:
        activity_id: The task_code (or task_id).
        activity_name: Human-readable name.
        criticality_pct: Percentage of iterations on the critical path.
    """

    activity_id: str = ""
    activity_name: str = ""
    criticality_pct: float = 0.0


@dataclass
class SensitivityEntry:
    """Sensitivity (Spearman correlation) for a single activity.

    Attributes:
        activity_id: The task_code (or task_id).
        activity_name: Human-readable name.
        correlation: Spearman rank correlation with project completion.
    """

    activity_id: str = ""
    activity_name: str = ""
    correlation: float = 0.0


@dataclass
class SCurvePoint:
    """A single point on the cumulative probability S-curve.

    Attributes:
        duration_days: Project completion duration in days.
        cumulative_probability: Cumulative probability (0.0-1.0).
    """

    duration_days: float = 0.0
    cumulative_probability: float = 0.0


@dataclass
class PValueEntry:
    """A P-value (percentile) result.

    Attributes:
        percentile: The percentile (e.g. 10, 50, 80, 90).
        duration_days: Completion duration at this percentile.
        delta_days: Difference from the deterministic duration.
    """

    percentile: int = 0
    duration_days: float = 0.0
    delta_days: float = 0.0


@dataclass
class SimulationResult:
    """Full output of a Monte Carlo simulation run.

    Attributes:
        simulation_id: Unique identifier (set by the store).
        project_name: Name of the analysed project.
        project_id: Store identifier of the project.
        iterations: Number of iterations performed.
        deterministic_days: Deterministic CPM project duration in days.
        mean_days: Mean simulated completion in days.
        std_days: Standard deviation of completion in days.
        p_values: P-value entries for requested confidence levels.
        histogram: Histogram of completion durations.
        criticality: Criticality index per activity.
        sensitivity: Sensitivity (Spearman) per activity.
        s_curve: Cumulative probability S-curve data.
        config: The simulation configuration used.
        duration_risks: Custom duration risks provided.
        risk_events: Discrete risk events provided.
    """

    simulation_id: str = ""
    project_name: str = ""
    project_id: str = ""
    iterations: int = 0
    deterministic_days: float = 0.0
    mean_days: float = 0.0
    std_days: float = 0.0
    p_values: list[PValueEntry] = field(default_factory=list)
    histogram: list[HistogramBin] = field(default_factory=list)
    criticality: list[CriticalityEntry] = field(default_factory=list)
    sensitivity: list[SensitivityEntry] = field(default_factory=list)
    s_curve: list[SCurvePoint] = field(default_factory=list)
    config: SimulationConfig = field(default_factory=SimulationConfig)
    duration_risks: list[DurationRisk] = field(default_factory=list)
    risk_events: list[RiskEvent] = field(default_factory=list)


# ── Monte Carlo Simulator ───────────────────────────────────────────


class MonteCarloSimulator:
    """Monte Carlo schedule risk simulator per AACE RP 57R-09.

    Builds a CPM network from the schedule, then runs *N* iterations
    where each iteration samples activity durations from probability
    distributions and re-runs the forward/backward pass.

    Usage::

        sim = MonteCarloSimulator(schedule, config)
        result = sim.simulate(duration_risks, risk_events)

    Args:
        schedule: Parsed P6 schedule with activities and relationships.
        config: Simulation configuration (iterations, seed, etc.).
    """

    def __init__(
        self,
        schedule: ParsedSchedule,
        config: SimulationConfig | None = None,
    ) -> None:
        self.schedule = schedule
        self.config = config or SimulationConfig()

        # Run deterministic CPM once to get the baseline
        self._cpm = CPMCalculator(schedule)
        self._base_result = self._cpm.calculate()

        # Build the internal graph reference (the CPM calculator builds it)
        self._graph: nx.DiGraph = self._cpm._graph

        # Map of activity keys -- use task_code as primary, fall back to task_id
        self._activities: dict[str, Any] = {}
        self._task_id_to_key: dict[str, str] = {}
        for t in schedule.activities:
            if t.task_type.lower() in ("tt_loe", "tt_wbs"):
                continue
            key = t.task_code or t.task_id
            self._activities[key] = t
            self._task_id_to_key[t.task_id] = key

        # Precompute topological order and edge data for fast iteration
        self._topo_order: list[str] = list(nx.topological_sort(self._graph))
        self._hours_per_day = self._cpm.hours_per_day

        # Precompute predecessor info per node for forward pass
        self._pred_info: dict[str, list[tuple[str, str, float]]] = {}
        for node_id in self._topo_order:
            preds = []
            for pred_id in self._graph.predecessors(node_id):
                edge = self._graph.edges[pred_id, node_id]
                preds.append((pred_id, edge["rel_type"], edge["lag"]))
            self._pred_info[node_id] = preds

        # Precompute successor info per node for backward pass
        self._succ_info: dict[str, list[tuple[str, str, float]]] = {}
        for node_id in self._topo_order:
            succs = []
            for succ_id in self._graph.successors(node_id):
                edge = self._graph.edges[node_id, succ_id]
                succs.append((succ_id, edge["rel_type"], edge["lag"]))
            self._succ_info[node_id] = succs

    def simulate(
        self,
        duration_risks: list[DurationRisk] | None = None,
        risk_events: list[RiskEvent] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> SimulationResult:
        """Run the full Monte Carlo simulation.

        Args:
            duration_risks: Per-activity duration risk overrides.
            risk_events: Discrete risk events to apply.
            progress_callback: Optional ``(completed_iterations, total)`` callback
                fired roughly every 1% of iterations (or every iteration on
                very small runs). Cheap if omitted — no per-iteration overhead
                added when ``None``.

        Returns:
            A ``SimulationResult`` with P-values, histogram, criticality
            index, sensitivity analysis, and S-curve data.
        """
        rng = np.random.default_rng(self.config.seed)

        risk_map = self._build_risk_map(duration_risks)
        event_map = self._build_event_map(risk_events)

        n = self.config.iterations
        activity_keys = list(self._activities.keys())
        n_acts = len(activity_keys)

        # Storage arrays
        completion_durations = np.zeros(n)
        duration_matrix = np.zeros((n, n_acts))
        cp_counts: dict[str, int] = {}

        # Node-to-column index
        key_to_col = {k: i for i, k in enumerate(activity_keys)}

        # Map task_id -> original duration in days (from graph)
        orig_dur_days: dict[str, float] = {}
        for node_id in self._topo_order:
            orig_dur_days[node_id] = self._graph.nodes[node_id]["duration"]

        # Emit a progress event roughly every 1% of iterations (or each iteration
        # for very small runs). Stays cheap when ``progress_callback`` is None.
        progress_step = max(1, n // 100) if progress_callback else 0

        for iteration in range(n):
            # 1. Sample durations for each activity
            sampled_days: dict[str, float] = {}
            for node_id in self._topo_order:
                key = self._task_id_to_key.get(node_id)
                if key is None:
                    # LOE or WBS summary -- keep original
                    sampled_days[node_id] = orig_dur_days[node_id]
                    continue

                task = self._activities[key]
                # Completed activities always have zero remaining duration
                if task.status_code == "TK_Complete":
                    sampled_days[node_id] = 0.0
                    col = key_to_col[key]
                    duration_matrix[iteration, col] = 0.0
                    continue

                risk = risk_map.get(key)
                if risk and risk.distribution != DistributionType.FIXED:
                    dur_hours = self._sample_duration(risk, rng)
                elif risk and risk.distribution == DistributionType.FIXED:
                    dur_hours = risk.most_likely
                elif self.config.default_uncertainty > 0:
                    # Apply default uncertainty to original duration
                    orig_h = task.remain_drtn_hr_cnt
                    default_risk = DurationRisk(
                        activity_id=key,
                        distribution=self.config.default_distribution,
                        min_duration=orig_h * (1 - self.config.default_uncertainty),
                        most_likely=orig_h,
                        max_duration=orig_h * (1 + self.config.default_uncertainty),
                    )
                    dur_hours = self._sample_duration(default_risk, rng)
                else:
                    dur_hours = task.remain_drtn_hr_cnt

                # Apply discrete risk events
                events = event_map.get(key, [])
                for event in events:
                    if rng.random() < event.probability:
                        dur_hours += event.impact_hours

                dur_hours = max(dur_hours, 0.0)
                dur_days = dur_hours / self._hours_per_day
                sampled_days[node_id] = dur_days

                col = key_to_col[key]
                duration_matrix[iteration, col] = dur_hours

            # 2. Run CPM forward pass with sampled durations
            ef_map, es_map = self._forward_pass(sampled_days)
            project_end = max(ef_map.values()) if ef_map else 0.0
            completion_durations[iteration] = project_end

            # 3. Run backward pass to find critical path
            lf_map, ls_map = self._backward_pass(sampled_days, project_end)

            # 4. Identify critical activities (TF ~= 0)
            for node_id in self._topo_order:
                tf = ls_map.get(node_id, 0.0) - es_map.get(node_id, 0.0)
                if abs(tf) < 1e-6:
                    key = self._task_id_to_key.get(node_id)
                    if key:
                        cp_counts[key] = cp_counts.get(key, 0) + 1

            if progress_callback and progress_step and (iteration + 1) % progress_step == 0:
                progress_callback(iteration + 1, n)

        if progress_callback:
            progress_callback(n, n)

        return self._build_results(
            completion_durations,
            cp_counts,
            duration_matrix,
            activity_keys,
            duration_risks,
            risk_events,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_risk_map(self, duration_risks: list[DurationRisk] | None) -> dict[str, DurationRisk]:
        """Build a mapping of activity_id -> DurationRisk."""
        if not duration_risks:
            return {}
        return {r.activity_id: r for r in duration_risks}

    def _build_event_map(self, risk_events: list[RiskEvent] | None) -> dict[str, list[RiskEvent]]:
        """Build a mapping of activity_id -> list of applicable RiskEvents."""
        if not risk_events:
            return {}
        result: dict[str, list[RiskEvent]] = {}
        for event in risk_events:
            for aid in event.affected_activities:
                result.setdefault(aid, []).append(event)
        return result

    @staticmethod
    def _sample_duration(risk: DurationRisk, rng: np.random.Generator) -> float:
        """Sample a duration from the specified distribution.

        Args:
            risk: The duration risk with distribution parameters.
            rng: NumPy random generator.

        Returns:
            Sampled duration in hours.
        """
        lo = risk.min_duration
        ml = risk.most_likely
        hi = risk.max_duration

        # Guard against degenerate ranges
        if hi <= lo:
            return ml
        if ml < lo:
            ml = lo
        if ml > hi:
            ml = hi

        dist = risk.distribution

        if dist == DistributionType.TRIANGULAR:
            return float(rng.triangular(lo, ml, hi))

        elif dist == DistributionType.PERT:
            # PERT-Beta distribution using the standard parameterisation.
            # mean = (min + lambda*mode + max) / (lambda + 2)
            lam = 4.0
            if abs(hi - lo) < 1e-12:
                return ml
            # Compute alpha1 from the PERT mean and range
            # alpha1 = (mu - lo) / (hi - lo) * ((mu - lo)(hi - mu)/(var) - 1)
            # Using the simplified formula with lambda:
            # alpha1 = 1 + lam * (ml - lo) / (hi - lo)
            # alpha2 = 1 + lam * (hi - ml) / (hi - lo)
            alpha1 = 1.0 + lam * (ml - lo) / (hi - lo)
            alpha2 = 1.0 + lam * (hi - ml) / (hi - lo)
            if alpha1 <= 0 or alpha2 <= 0:
                return float(rng.triangular(lo, ml, hi))
            sample = float(rng.beta(alpha1, alpha2))
            return lo + sample * (hi - lo)

        elif dist == DistributionType.UNIFORM:
            return float(rng.uniform(lo, hi))

        elif dist == DistributionType.LOGNORMAL:
            # Derive lognormal params from 3-point estimate
            mean = (lo + 4 * ml + hi) / 6
            variance = ((hi - lo) / 6) ** 2
            if mean <= 0 or variance <= 0:
                return ml
            sigma2 = np.log(1 + variance / (mean**2))
            mu_ln = np.log(mean) - sigma2 / 2
            sigma_ln = np.sqrt(sigma2)
            sample = float(rng.lognormal(mu_ln, sigma_ln))
            # Clamp to [min, max] to prevent extreme outliers
            return float(np.clip(sample, lo, hi))

        elif dist == DistributionType.FIXED:
            return ml

        # Fallback
        return ml

    def _forward_pass(
        self, durations: dict[str, float]
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Run the CPM forward pass with given durations (in days).

        Returns:
            A tuple of (early_finish_map, early_start_map).
        """
        es_map: dict[str, float] = {}
        ef_map: dict[str, float] = {}

        for node_id in self._topo_order:
            dur = durations.get(node_id, 0.0)
            es = 0.0

            for pred_id, rel_type, lag in self._pred_info[node_id]:
                pred_es = es_map.get(pred_id, 0.0)
                pred_ef = ef_map.get(pred_id, 0.0)

                if rel_type == _FS:
                    imposed = pred_ef + lag
                elif rel_type == _SS:
                    imposed = pred_es + lag
                elif rel_type == _FF:
                    imposed = pred_ef + lag - dur
                elif rel_type == _SF:
                    imposed = pred_es + lag - dur
                else:
                    imposed = pred_ef + lag

                if imposed > es:
                    es = imposed

            es_map[node_id] = es
            ef_map[node_id] = es + dur

        return ef_map, es_map

    def _backward_pass(
        self,
        durations: dict[str, float],
        project_end: float,
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Run the CPM backward pass with given durations (in days).

        Returns:
            A tuple of (late_finish_map, late_start_map).
        """
        lf_map: dict[str, float] = {}
        ls_map: dict[str, float] = {}

        for node_id in reversed(self._topo_order):
            dur = durations.get(node_id, 0.0)
            lf = project_end

            succs = self._succ_info[node_id]
            if succs:
                for succ_id, rel_type, lag in succs:
                    succ_ls = ls_map.get(succ_id, project_end)
                    succ_lf = lf_map.get(succ_id, project_end)

                    if rel_type == _FS:
                        imposed = succ_ls - lag
                    elif rel_type == _SS:
                        imposed = succ_ls - lag + dur
                    elif rel_type == _FF:
                        imposed = succ_lf - lag
                    elif rel_type == _SF:
                        imposed = succ_lf - lag + dur
                    else:
                        imposed = succ_ls - lag

                    if imposed < lf:
                        lf = imposed

            lf_map[node_id] = lf
            ls_map[node_id] = lf - dur

        return lf_map, ls_map

    def _build_results(
        self,
        completion_durations: np.ndarray,
        cp_counts: dict[str, int],
        duration_matrix: np.ndarray,
        activity_keys: list[str],
        duration_risks: list[DurationRisk] | None,
        risk_events: list[RiskEvent] | None,
    ) -> SimulationResult:
        """Build the SimulationResult from raw iteration data.

        Args:
            completion_durations: Array of project completion durations (days).
            cp_counts: Activity key -> count of iterations on critical path.
            duration_matrix: (iterations x activities) matrix of sampled durations.
            activity_keys: Ordered list of activity keys (task_code).
            duration_risks: The user-provided duration risks.
            risk_events: The user-provided risk events.

        Returns:
            Fully populated ``SimulationResult``.
        """
        n = self.config.iterations
        det = self._base_result.project_duration

        # Project name
        project_name = ""
        if self.schedule.projects:
            project_name = self.schedule.projects[0].proj_short_name

        # P-values
        p_values: list[PValueEntry] = []
        for pct in self.config.confidence_levels:
            val = float(np.percentile(completion_durations, pct))
            p_values.append(
                PValueEntry(
                    percentile=pct,
                    duration_days=round(val, 2),
                    delta_days=round(val - det, 2),
                )
            )

        # Histogram (30 bins)
        counts_arr, bin_edges = np.histogram(completion_durations, bins=30)
        histogram: list[HistogramBin] = []
        for i in range(len(counts_arr)):
            histogram.append(
                HistogramBin(
                    bin_start=round(float(bin_edges[i]), 2),
                    bin_end=round(float(bin_edges[i + 1]), 2),
                    count=int(counts_arr[i]),
                    frequency=round(float(counts_arr[i]) / n, 4),
                )
            )

        # Criticality index
        criticality: list[CriticalityEntry] = []
        for key in activity_keys:
            cnt = cp_counts.get(key, 0)
            task = self._activities.get(key)
            name = task.task_name if task else key
            criticality.append(
                CriticalityEntry(
                    activity_id=key,
                    activity_name=name,
                    criticality_pct=round(cnt / n * 100, 1),
                )
            )
        # Sort by criticality descending
        criticality.sort(key=lambda c: c.criticality_pct, reverse=True)

        # Sensitivity (Spearman rank correlation)
        sensitivity: list[SensitivityEntry] = []
        completion_ranks = _rank_array(completion_durations)
        for j, key in enumerate(activity_keys):
            col = duration_matrix[:, j]
            # Skip columns with zero variance
            if np.std(col) < 1e-12:
                corr = 0.0
            else:
                col_ranks = _rank_array(col)
                corr = float(np.corrcoef(col_ranks, completion_ranks)[0, 1])
            task = self._activities.get(key)
            name = task.task_name if task else key
            sensitivity.append(
                SensitivityEntry(
                    activity_id=key,
                    activity_name=name,
                    correlation=round(corr, 4),
                )
            )
        # Sort by absolute correlation descending
        sensitivity.sort(key=lambda s: abs(s.correlation), reverse=True)

        # S-curve (cumulative probability)
        sorted_completions = np.sort(completion_durations)
        # Sample ~100 points for the S-curve
        step = max(1, n // 100)
        s_curve: list[SCurvePoint] = []
        for i in range(0, n, step):
            s_curve.append(
                SCurvePoint(
                    duration_days=round(float(sorted_completions[i]), 2),
                    cumulative_probability=round((i + 1) / n, 4),
                )
            )
        # Always include the last point
        if s_curve and s_curve[-1].cumulative_probability < 1.0:
            s_curve.append(
                SCurvePoint(
                    duration_days=round(float(sorted_completions[-1]), 2),
                    cumulative_probability=1.0,
                )
            )

        return SimulationResult(
            project_name=project_name,
            iterations=n,
            deterministic_days=round(det, 2),
            mean_days=round(float(np.mean(completion_durations)), 2),
            std_days=round(float(np.std(completion_durations)), 2),
            p_values=p_values,
            histogram=histogram,
            criticality=criticality,
            sensitivity=sensitivity,
            s_curve=s_curve,
            config=self.config,
            duration_risks=duration_risks or [],
            risk_events=risk_events or [],
        )


def _rank_array(arr: np.ndarray) -> np.ndarray:
    """Compute ranks for a 1-D array (average method for ties).

    Uses argsort twice for O(n log n) ranking without scipy.

    Args:
        arr: 1-D numpy array.

    Returns:
        Array of ranks (1-based, averaged for ties).
    """
    n = len(arr)
    order = arr.argsort()
    ranks = np.empty(n, dtype=float)
    ranks[order] = np.arange(1, n + 1, dtype=float)

    # Handle ties by averaging
    sorted_arr = arr[order]
    i = 0
    while i < n:
        j = i
        while j < n - 1 and sorted_arr[j + 1] == sorted_arr[j]:
            j += 1
        if j > i:
            avg_rank = (ranks[order[i]] + ranks[order[j]]) / 2.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg_rank
        i = j + 1

    return ranks
