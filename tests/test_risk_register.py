# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the risk register engine."""

from __future__ import annotations

from src.analytics.risk_register import (
    RiskEntry,
    RiskRegisterSummary,
    register_to_risk_events,
    summarize_register,
)


def _sample_entries() -> list[RiskEntry]:
    return [
        RiskEntry(
            risk_id="R001",
            name="Weather delay",
            category="external",
            probability=0.6,
            impact_days=15,
            impact_cost=50000,
            status="open",
            affected_activities=["A100", "A200"],
        ),
        RiskEntry(
            risk_id="R002",
            name="Material shortage",
            category="schedule",
            probability=0.3,
            impact_days=10,
            impact_cost=30000,
            status="open",
            affected_activities=["A300"],
        ),
        RiskEntry(
            risk_id="R003",
            name="Design change",
            category="scope",
            probability=0.2,
            impact_days=20,
            impact_cost=100000,
            status="mitigated",
            mitigation="Freeze design at 60% completion",
        ),
        RiskEntry(
            risk_id="R004",
            name="Equipment failure",
            category="schedule",
            probability=0.4,
            impact_days=5,
            status="open",
            affected_activities=["A100"],
        ),
        RiskEntry(
            risk_id="R005",
            name="Permit delay",
            category="external",
            probability=0.8,
            impact_days=30,
            status="closed",
        ),
    ]


class TestSummarize:
    def test_returns_summary(self) -> None:
        result = summarize_register(_sample_entries())
        assert isinstance(result, RiskRegisterSummary)

    def test_counts(self) -> None:
        result = summarize_register(_sample_entries())
        assert result.total_risks == 5
        assert result.open_risks == 3
        assert result.mitigated_risks == 1
        assert result.closed_risks == 1

    def test_expected_impact(self) -> None:
        result = summarize_register(_sample_entries())
        # R001: 0.6*15=9, R002: 0.3*10=3, R004: 0.4*5=2 = 14 days
        assert result.total_expected_impact_days == 14.0

    def test_expected_cost(self) -> None:
        result = summarize_register(_sample_entries())
        # R001: 0.6*50000=30000, R002: 0.3*30000=9000, R004: 0 = 39000
        assert result.total_expected_impact_cost == 39000.0

    def test_risk_score_bounded(self) -> None:
        result = summarize_register(_sample_entries())
        assert 0 <= result.risk_score <= 100

    def test_categories(self) -> None:
        result = summarize_register(_sample_entries())
        assert result.categories["external"] == 2
        assert result.categories["schedule"] == 2

    def test_top_risks_sorted(self) -> None:
        result = summarize_register(_sample_entries())
        expected_days = [r["expected_days"] for r in result.top_risks]
        assert expected_days == sorted(expected_days, reverse=True)

    def test_empty_register(self) -> None:
        result = summarize_register([])
        assert result.total_risks == 0
        assert result.risk_score == 0

    def test_methodology_set(self) -> None:
        result = summarize_register(_sample_entries())
        assert "risk register" in result.methodology.lower()


class TestRegisterToRiskEvents:
    def test_converts_open_with_activities(self) -> None:
        events = register_to_risk_events(_sample_entries())
        # R001 (open, has activities), R002 (open, has activities), R004 (open, has activities)
        assert len(events) == 3

    def test_skips_closed_and_mitigated(self) -> None:
        events = register_to_risk_events(_sample_entries())
        ids = {e.risk_id for e in events}
        assert "R003" not in ids  # mitigated
        assert "R005" not in ids  # closed

    def test_event_fields(self) -> None:
        events = register_to_risk_events(_sample_entries())
        r001 = next(e for e in events if e.risk_id == "R001")
        assert r001.probability == 0.6
        assert r001.impact_hours == 15 * 8  # days to hours
        assert r001.affected_activities == ["A100", "A200"]

    def test_empty_register(self) -> None:
        events = register_to_risk_events([])
        assert len(events) == 0

    def test_no_activities_skipped(self) -> None:
        entry = RiskEntry(
            risk_id="X", name="No acts", probability=0.5, impact_days=10, status="open"
        )
        events = register_to_risk_events([entry])
        assert len(events) == 0
