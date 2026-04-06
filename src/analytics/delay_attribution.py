# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Delay Attribution Summary — aggregate delay by responsible party.

Provides a claims-ready breakdown of project delay by party (Owner,
Contractor, Shared, Third Party, Force Majeure). Designed for the
scheduler or claims consultant who needs to answer: "Who caused how
much delay, and which activities drove it?"

Works with two data sources:
1. **TIA fragments** — if TIA analysis has been run, uses the explicit
   party assignments from delay fragments.
2. **Standalone estimation** — if no TIA data, infers attribution from
   activity characteristics (out-of-sequence, constraint changes, etc.)

References:
    - AACE RP 29R-03 — Forensic Schedule Analysis
    - AACE RP 52R-06 — Time Impact Analysis
    - SCL Delay and Disruption Protocol, 2nd ed., Core Principles 1-4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


@dataclass
class PartyDelay:
    """Delay attributed to a single responsible party.

    Attributes:
        party: Party name (Owner, Contractor, Shared, Third Party, Force Majeure).
        delay_days: Total delay days attributed.
        pct_of_total: Percentage of total project delay.
        activity_count: Number of driving activities attributed to this party.
        top_activities: Names of the top contributing activities.
    """

    party: str = ""
    delay_days: float = 0.0
    pct_of_total: float = 0.0
    activity_count: int = 0
    top_activities: list[str] = field(default_factory=list)


@dataclass
class AttributionResult:
    """Complete delay attribution summary.

    Attributes:
        parties: Per-party delay breakdown.
        total_delay_days: Total project delay.
        excusable_days: Owner + Shared + Third Party + Force Majeure.
        non_excusable_days: Contractor-caused delay.
        concurrent_days: Shared delay (both parties).
        data_source: "tia" if TIA data used, "estimated" if inferred.
        methodology: Description of attribution approach.
    """

    parties: list[PartyDelay] = field(default_factory=list)
    total_delay_days: float = 0.0
    excusable_days: float = 0.0
    non_excusable_days: float = 0.0
    concurrent_days: float = 0.0
    data_source: str = "estimated"
    methodology: str = (
        "Delay attribution per AACE RP 29R-03 and SCL Protocol. "
        "Excusable = Owner + Shared + Third Party + Force Majeure. "
        "Non-excusable = Contractor. "
        "Concurrent = Shared between parties."
    )


def compute_delay_attribution(
    schedule: ParsedSchedule,
    baseline: ParsedSchedule | None = None,
    tia_results: dict | None = None,
) -> AttributionResult:
    """Compute delay attribution breakdown by responsible party.

    Args:
        schedule: The current/update schedule.
        baseline: The original baseline schedule (for comparison-based estimation).
        tia_results: Optional TIA analysis results dict with party totals.

    Returns:
        AttributionResult with per-party breakdown.
    """
    result = AttributionResult()

    # Source 1: Use TIA results if available (most accurate)
    if tia_results and "total_owner_delay" in tia_results:
        result.data_source = "tia"
        owner = tia_results.get("total_owner_delay", 0.0)
        contractor = tia_results.get("total_contractor_delay", 0.0)
        shared = tia_results.get("total_shared_delay", 0.0)
        third_party = tia_results.get("total_third_party_delay", 0.0)
        force_majeure = tia_results.get("total_force_majeure_delay", 0.0)

        total = owner + contractor + shared + third_party + force_majeure
        result.total_delay_days = total

        parties = [
            ("Owner", owner),
            ("Contractor", contractor),
            ("Shared", shared),
            ("Third Party", third_party),
            ("Force Majeure", force_majeure),
        ]

        for name, days in parties:
            if days > 0:
                result.parties.append(
                    PartyDelay(
                        party=name,
                        delay_days=round(days, 1),
                        pct_of_total=round(days / total * 100, 1)
                        if total > 0
                        else 0.0,
                    )
                )

        result.excusable_days = round(
            owner + shared + third_party + force_majeure, 1
        )
        result.non_excusable_days = round(contractor, 1)
        result.concurrent_days = round(shared, 1)
        return result

    # Source 2: Estimate from schedule characteristics
    result.data_source = "estimated"

    from src.analytics.cpm import CPMCalculator

    cpm = CPMCalculator(schedule)
    cpm_result = cpm.calculate()

    # Estimate total delay from schedule vs baseline
    total_delay = 0.0
    if baseline:
        base_cpm = CPMCalculator(baseline)
        base_result = base_cpm.calculate()
        if (
            cpm_result.project_finish
            and base_result.project_finish
        ):
            delta = cpm_result.project_finish - base_result.project_finish
            total_delay = max(0.0, delta.days)

    if total_delay == 0.0:
        # No baseline or no delay — use negative float as proxy
        neg_float_tasks = [
            t
            for t in schedule.activities
            if t.total_float_hr_cnt is not None
            and t.total_float_hr_cnt < 0
            and t.status_code.upper() != "TK_COMPLETE"
        ]
        if neg_float_tasks:
            # Take worst negative float as total delay estimate
            worst = min(t.total_float_hr_cnt or 0 for t in neg_float_tasks)
            day_hr = 8.0
            if schedule.calendars:
                day_hr = schedule.calendars[0].day_hr_cnt or 8.0
            total_delay = abs(worst) / day_hr

    result.total_delay_days = round(total_delay, 1)

    if total_delay <= 0:
        result.parties.append(
            PartyDelay(
                party="None",
                delay_days=0,
                pct_of_total=100.0,
                activity_count=0,
            )
        )
        return result

    # Heuristic attribution based on activity characteristics
    # Activities with constraints → likely Owner-directed
    constraint_tasks = [
        t
        for t in schedule.activities
        if t.cstr_type and t.cstr_type not in ("", "CS_MEO")
        and t.status_code.upper() != "TK_COMPLETE"
    ]
    # Activities with out-of-sequence → likely Contractor execution
    oos_tasks = [
        t
        for t in schedule.activities
        if t.status_code.upper() == "TK_ACTIVE"
        and t.act_start_date
        and t.early_start_date
        and t.act_start_date < t.early_start_date
    ]
    # Activities with very high remaining duration → schedule risk
    critical_tasks = [
        t
        for t in schedule.activities
        if t.total_float_hr_cnt is not None
        and t.total_float_hr_cnt <= 0
        and t.status_code.upper() != "TK_COMPLETE"
    ]

    total_indicators = (
        len(constraint_tasks) + len(oos_tasks) + len(critical_tasks)
    )
    if total_indicators == 0:
        total_indicators = 1

    # Proportional attribution (heuristic)
    owner_pct = len(constraint_tasks) / total_indicators
    contractor_pct = len(oos_tasks) / total_indicators
    shared_pct = len(critical_tasks) / total_indicators

    # Normalize
    total_pct = owner_pct + contractor_pct + shared_pct
    if total_pct > 0:
        owner_pct /= total_pct
        contractor_pct /= total_pct
        shared_pct /= total_pct

    parties_data = [
        (
            "Owner",
            round(total_delay * owner_pct, 1),
            len(constraint_tasks),
            [t.task_name or t.task_code or t.task_id for t in constraint_tasks[:5]],
        ),
        (
            "Contractor",
            round(total_delay * contractor_pct, 1),
            len(oos_tasks),
            [t.task_name or t.task_code or t.task_id for t in oos_tasks[:5]],
        ),
        (
            "Shared",
            round(total_delay * shared_pct, 1),
            len(critical_tasks),
            [t.task_name or t.task_code or t.task_id for t in critical_tasks[:5]],
        ),
    ]

    for name, days, count, activities in parties_data:
        if days > 0:
            result.parties.append(
                PartyDelay(
                    party=name,
                    delay_days=days,
                    pct_of_total=round(
                        days / total_delay * 100, 1
                    )
                    if total_delay > 0
                    else 0.0,
                    activity_count=count,
                    top_activities=activities,
                )
            )

    result.excusable_days = round(total_delay * owner_pct, 1)
    result.non_excusable_days = round(total_delay * contractor_pct, 1)
    result.concurrent_days = round(total_delay * shared_pct, 1)

    result.parties.sort(key=lambda p: p.delay_days, reverse=True)
    return result
