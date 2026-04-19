# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Evolution Strategies optimizer for resource-constrained scheduling.

Uses (mu, lambda) Evolution Strategy to optimize RCPSP solutions beyond
the greedy Serial SGS.  The optimizer evolves a population of priority
vectors (activity ordering), each decoded through SGS, and selects based
on makespan fitness.

References:
    - Loncar (2023) — Evolution Strategies for Task Scheduling
    - Hartmann & Kolisch (2000) — RCPSP Benchmark Instances
    - Beyer & Schwefel (2002) — Evolution Strategies: A Comprehensive Introduction
    - Kolisch (1996) — Serial SGS for RCPSP
"""

from __future__ import annotations

import logging
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


from src.analytics.cpm import CPMCalculator
from src.analytics.resource_leveling import LevelingConfig, LevelingResult, level_resources
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class EvolutionConfig:
    """Configuration for Evolution Strategies optimization."""

    population_size: int = 30  # lambda (offspring)
    parent_size: int = 7  # mu (parents)
    generations: int = 50
    mutation_rate: float = 0.15
    seed: int = 42
    resource_limits: list[Any] = field(default_factory=list)  # ResourceLimit list
    priority_rules: list[str] = field(
        default_factory=lambda: ["late_start", "early_start", "float", "duration"]
    )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


@dataclass
class OptimizationResult:
    """Result of Evolution Strategies optimization."""

    best_duration_days: float = 0.0
    greedy_duration_days: float = 0.0  # Best greedy SGS result
    improvement_days: float = 0.0
    improvement_pct: float = 0.0
    best_priority_rule: str = ""
    convergence_history: list[float] = field(default_factory=list)
    generations_run: int = 0
    population_size: int = 0
    best_leveling: LevelingResult | None = None
    methodology: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evolution Strategies core
# ---------------------------------------------------------------------------


def _evaluate_priority_order(
    schedule: ParsedSchedule,
    config: LevelingConfig,
) -> float:
    """Evaluate a leveling configuration and return makespan."""
    result = level_resources(schedule, config)
    return result.leveled_duration_days


def _mutate_priority_rule(
    rules: list[str],
    current: str,
    rng: random.Random,
    mutation_rate: float,
) -> str:
    """Mutate the priority rule with given probability."""
    if rng.random() < mutation_rate:
        return rng.choice(rules)
    return current


def _mutate_limits(
    base_limits: list[Any],
    rng: random.Random,
    mutation_rate: float,
) -> list[Any]:
    """Mutate resource limits slightly (adjust max_units by ±10%)."""
    from src.analytics.resource_leveling import ResourceLimit

    mutated = []
    for rl in base_limits:
        if rng.random() < mutation_rate:
            factor = rng.uniform(0.9, 1.1)
            new_units = max(1.0, rl.max_units * factor)
            mutated.append(
                ResourceLimit(
                    rsrc_id=rl.rsrc_id,
                    max_units=round(new_units, 1),
                    cost_per_unit_day=rl.cost_per_unit_day,
                )
            )
        else:
            mutated.append(rl)
    return mutated


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def optimize_schedule(
    schedule: ParsedSchedule,
    config: EvolutionConfig,
    progress_callback: Callable[[int, int], None] | None = None,
) -> OptimizationResult:
    """Optimize resource-constrained schedule using Evolution Strategies.

    Evolves priority rules and resource allocation across generations
    to minimize project makespan (duration).

    Args:
        schedule: The schedule to optimize.
        config: Evolution strategy configuration.
        progress_callback: Optional ``(completed_evaluations, total)``
            callback fired roughly every 1% of total evaluations (or
            every evaluation on very small runs). Total equals
            ``len(priority_rules) + generations * population_size``;
            the bookkeeping re-evaluation triggered when a new best is
            found is NOT counted. Cheap if omitted — no per-iteration
            overhead added when ``None``. Consumers wire this hook to
            the WebSocket progress channel (see ADR-0009 Amendment 2
            W5/W6 carry-over + ADR-0013 publisher pattern).

    Returns:
        An ``OptimizationResult`` with best duration, improvement, and
        convergence history.

    References:
        - Loncar (2023) — Evolution Strategies for Task Scheduling
        - Beyer & Schwefel (2002) — ES Introduction
        - Kolisch (1996) — Serial SGS for RCPSP
    """
    result = OptimizationResult()
    result.population_size = config.population_size
    rng = random.Random(config.seed)

    if not config.resource_limits:
        # No resource constraints — just run CPM. No heavy-work units to
        # report, so we skip the progress callback entirely.
        cpm = CPMCalculator(schedule).calculate()
        result.best_duration_days = round(cpm.project_duration, 1)
        result.greedy_duration_days = result.best_duration_days
        result.methodology = "No resource limits — unconstrained CPM"
        return result

    total_evals = len(config.priority_rules) + config.generations * config.population_size
    progress_step = max(1, total_evals // 100) if progress_callback else 0
    done_evals = 0

    # Phase 1: Evaluate all greedy priority rules.
    greedy_results: list[tuple[str, float, LevelingResult]] = []
    for rule in config.priority_rules:
        lconfig = LevelingConfig(
            resource_limits=config.resource_limits,
            priority_rule=rule,
        )
        lr = level_resources(schedule, lconfig)
        greedy_results.append((rule, lr.leveled_duration_days, lr))

        done_evals += 1
        if progress_callback and progress_step and done_evals % progress_step == 0:
            progress_callback(done_evals, total_evals)

    greedy_results.sort(key=lambda x: x[1])
    best_rule, best_greedy_dur, best_greedy_lr = greedy_results[0]
    result.greedy_duration_days = round(best_greedy_dur, 1)

    # Phase 2: Evolution — evolve priority rule + slight limit mutations.
    best_duration = best_greedy_dur
    best_leveling = best_greedy_lr
    best_priority = best_rule
    convergence: list[float] = [round(best_duration, 1)]

    for gen in range(config.generations):
        # Generate offspring
        offspring: list[tuple[str, list[Any], float]] = []

        for _ in range(config.population_size):
            # Mutate priority rule
            rule = _mutate_priority_rule(
                config.priority_rules, best_priority, rng, config.mutation_rate
            )
            # Mutate resource limits
            limits = _mutate_limits(config.resource_limits, rng, config.mutation_rate)

            lconfig = LevelingConfig(resource_limits=limits, priority_rule=rule)
            lr = level_resources(schedule, lconfig)
            offspring.append((rule, limits, lr.leveled_duration_days))

            done_evals += 1
            if progress_callback and progress_step and done_evals % progress_step == 0:
                progress_callback(done_evals, total_evals)

        # Select mu best
        offspring.sort(key=lambda x: x[2])
        parents = offspring[: config.parent_size]

        # Update best
        if parents[0][2] < best_duration:
            best_priority = parents[0][0]
            best_duration = parents[0][2]
            # Re-run to get full LevelingResult. This re-evaluation is
            # bookkeeping (captures the full LevelingResult for the new
            # incumbent); intentionally NOT counted toward the progress
            # total so the emission contract stays monotonic and bounded.
            lconfig = LevelingConfig(resource_limits=parents[0][1], priority_rule=best_priority)
            best_leveling = level_resources(schedule, lconfig)

        convergence.append(round(best_duration, 1))

    # Final guaranteed (total, total) frame so consumers always see 100%
    # even when total_evals is not a multiple of progress_step.
    if progress_callback:
        progress_callback(total_evals, total_evals)

    result.best_duration_days = round(best_duration, 1)
    result.best_priority_rule = best_priority
    result.improvement_days = round(best_greedy_dur - best_duration, 1)
    if best_greedy_dur > 0:
        result.improvement_pct = round(result.improvement_days / best_greedy_dur * 100, 1)
    result.convergence_history = convergence
    result.generations_run = config.generations
    result.best_leveling = best_leveling

    result.methodology = (
        f"(μ={config.parent_size}, λ={config.population_size}) Evolution Strategy "
        f"over {config.generations} generations "
        f"(Loncar 2023, Beyer & Schwefel 2002)"
    )

    result.summary = {
        "best_duration_days": result.best_duration_days,
        "greedy_duration_days": result.greedy_duration_days,
        "improvement_days": result.improvement_days,
        "improvement_pct": result.improvement_pct,
        "best_priority_rule": result.best_priority_rule,
        "generations_run": result.generations_run,
        "population_size": result.population_size,
        "methodology": result.methodology,
        "references": [
            "Loncar (2023) — Evolution Strategies for Task Scheduling",
            "Beyer & Schwefel (2002) — ES Introduction",
            "Kolisch (1996) — Serial SGS for RCPSP",
        ],
    }

    return result
