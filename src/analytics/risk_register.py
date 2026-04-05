# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Risk register — discrete risk event management and Monte Carlo integration.

Manages a register of identified risks with probability, impact, responsible
party, and mitigation plans.  Risk entries can be converted to ``RiskEvent``
objects for Monte Carlo simulation (AACE RP 57R-09).

References:
    - AACE RP 57R-09 — Schedule Risk Analysis (discrete risk events)
    - PMI Practice Standard for Risk Management
    - ISO 31000 — Risk Management Framework
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.risk import RiskEvent

logger = logging.getLogger(__name__)

_HOURS_PER_DAY = 8.0


@dataclass
class RiskEntry:
    """A single risk register entry."""

    risk_id: str = ""
    name: str = ""
    description: str = ""
    category: str = "schedule"  # schedule, cost, scope, quality, external
    probability: float = 0.5  # 0.0-1.0
    impact_days: float = 0.0
    impact_cost: float = 0.0
    status: str = "open"  # open, mitigated, closed, occurred
    responsible_party: str = ""
    mitigation: str = ""
    affected_activities: list[str] = field(default_factory=list)


@dataclass
class RiskRegisterSummary:
    """Summary of a project's risk register."""

    total_risks: int = 0
    open_risks: int = 0
    mitigated_risks: int = 0
    closed_risks: int = 0
    occurred_risks: int = 0
    avg_probability: float = 0.0
    total_expected_impact_days: float = 0.0  # sum(probability * impact)
    total_expected_impact_cost: float = 0.0
    risk_score: float = 0.0  # composite 0-100
    categories: dict[str, int] = field(default_factory=dict)
    top_risks: list[dict[str, Any]] = field(default_factory=dict)
    methodology: str = ""


def summarize_register(entries: list[RiskEntry]) -> RiskRegisterSummary:
    """Compute summary statistics for a risk register.

    Args:
        entries: List of risk register entries.

    Returns:
        A ``RiskRegisterSummary`` with counts, expected values, and risk score.

    References:
        - PMI Practice Standard for Risk Management
        - ISO 31000 — Risk Management Framework
    """
    summary = RiskRegisterSummary()
    summary.total_risks = len(entries)

    if not entries:
        summary.methodology = "No risks registered"
        return summary

    open_risks = [e for e in entries if e.status == "open"]
    summary.open_risks = len(open_risks)
    summary.mitigated_risks = len([e for e in entries if e.status == "mitigated"])
    summary.closed_risks = len([e for e in entries if e.status == "closed"])
    summary.occurred_risks = len([e for e in entries if e.status == "occurred"])

    # Expected values (only open risks)
    if open_risks:
        summary.avg_probability = sum(e.probability for e in open_risks) / len(open_risks)
        summary.total_expected_impact_days = sum(e.probability * e.impact_days for e in open_risks)
        summary.total_expected_impact_cost = sum(e.probability * e.impact_cost for e in open_risks)

    # Risk score: weighted by probability * impact, normalized to 0-100
    max_possible = len(open_risks) * 1.0 * 100 if open_risks else 1
    raw_score = sum(e.probability * min(e.impact_days, 100) for e in open_risks)
    summary.risk_score = round(min(100, (raw_score / max_possible) * 100), 1)

    # Categories
    cats: dict[str, int] = {}
    for e in entries:
        cats[e.category] = cats.get(e.category, 0) + 1
    summary.categories = cats

    # Top risks by expected impact
    sorted_risks = sorted(open_risks, key=lambda e: e.probability * e.impact_days, reverse=True)
    summary.top_risks = [
        {
            "risk_id": e.risk_id,
            "name": e.name,
            "probability": e.probability,
            "impact_days": e.impact_days,
            "expected_days": round(e.probability * e.impact_days, 1),
            "category": e.category,
        }
        for e in sorted_risks[:10]
    ]

    summary.methodology = (
        f"Risk register summary: {summary.open_risks} open risks, "
        f"expected impact {summary.total_expected_impact_days:.1f} days "
        f"(PMI Risk Management, ISO 31000)"
    )

    return summary


def register_to_risk_events(entries: list[RiskEntry]) -> list[RiskEvent]:
    """Convert risk register entries to RiskEvent objects for Monte Carlo.

    Only open risks with affected activities are converted.

    Args:
        entries: Risk register entries.

    Returns:
        List of ``RiskEvent`` objects ready for ``MonteCarloSimulator.simulate()``.

    References:
        - AACE RP 57R-09 — discrete risk event modelling
    """
    events = []
    for entry in entries:
        if entry.status != "open" or not entry.affected_activities:
            continue
        events.append(
            RiskEvent(
                risk_id=entry.risk_id,
                name=entry.name,
                probability=entry.probability,
                impact_hours=entry.impact_days * _HOURS_PER_DAY,
                affected_activities=list(entry.affected_activities),
            )
        )
    return events
