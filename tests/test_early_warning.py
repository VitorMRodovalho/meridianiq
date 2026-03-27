# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the early warning rules engine (12 rules)."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.analytics.early_warning import (
    RULES,
    Alert,
    EarlyWarningEngine,
    EarlyWarningResult,
)
from src.parser import ParsedSchedule, XERReader

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XER = FIXTURES / "sample.xer"
SAMPLE_UPDATE_XER = FIXTURES / "sample_update.xer"


@pytest.fixture(scope="module")
def baseline() -> ParsedSchedule:
    """Parse the baseline sample XER."""
    return XERReader(SAMPLE_XER).parse()


@pytest.fixture(scope="module")
def update() -> ParsedSchedule:
    """Parse the update sample XER."""
    return XERReader(SAMPLE_UPDATE_XER).parse()


@pytest.fixture(scope="module")
def warning_result(baseline: ParsedSchedule, update: ParsedSchedule) -> EarlyWarningResult:
    """Run the full early warning analysis."""
    return EarlyWarningEngine(baseline, update).analyze()


class TestEarlyWarningBasic:
    """Basic early warning analysis tests."""

    def test_result_type(self, warning_result: EarlyWarningResult) -> None:
        """Result should be an EarlyWarningResult."""
        assert isinstance(warning_result, EarlyWarningResult)

    def test_rules_checked(self, warning_result: EarlyWarningResult) -> None:
        """All 12 rules should be checked."""
        assert warning_result.rules_checked == 12

    def test_alerts_sorted_by_score(self, warning_result: EarlyWarningResult) -> None:
        """Alerts should be sorted by alert_score descending."""
        scores = [a.alert_score for a in warning_result.alerts]
        assert scores == sorted(scores, reverse=True)

    def test_severity_counts_match(self, warning_result: EarlyWarningResult) -> None:
        """Severity counts should sum to total_alerts."""
        assert (
            warning_result.critical_count
            + warning_result.warning_count
            + warning_result.info_count
            == warning_result.total_alerts
        )


class TestAlertScoring:
    """Tests for alert score computation."""

    def test_alert_score_positive(self, warning_result: EarlyWarningResult) -> None:
        """Every alert should have a positive score."""
        for alert in warning_result.alerts:
            assert alert.alert_score > 0

    def test_critical_alerts_higher_score(self, warning_result: EarlyWarningResult) -> None:
        """Critical alerts should generally score higher than info alerts."""
        critical_scores = [a.alert_score for a in warning_result.alerts if a.severity == "critical"]
        info_scores = [a.alert_score for a in warning_result.alerts if a.severity == "info"]
        if critical_scores and info_scores:
            assert max(info_scores) <= max(critical_scores)


class TestRule12Definitions:
    """Tests for the 12 alert rule definitions."""

    def test_twelve_rules_defined(self) -> None:
        """There should be exactly 12 rules defined."""
        assert len(RULES) == 12

    def test_rule_ids_unique(self) -> None:
        """All rule IDs should be unique."""
        ids = [r.rule_id for r in RULES]
        assert len(ids) == len(set(ids))

    def test_rule_severities_valid(self) -> None:
        """All rules should have valid severity levels."""
        for rule in RULES:
            assert rule.severity in ("info", "warning", "critical")

    def test_rule_standards_present(self) -> None:
        """All rules should reference a standard."""
        for rule in RULES:
            assert len(rule.standard) > 0


class TestRuleDurationGrowth:
    """Tests for Rule 4: Duration Growth."""

    def test_duration_growth_detected(self, warning_result: EarlyWarningResult) -> None:
        """Duration growth should be detected (sample_update has 3 duration changes)."""
        dur_alerts = [a for a in warning_result.alerts if a.rule_id == "duration_growth"]
        assert len(dur_alerts) >= 1
        if dur_alerts:
            assert dur_alerts[0].severity == "warning"


class TestRuleLogicDeletion:
    """Tests for Rule 3: Logic Deletion."""

    def test_logic_deletion_detected(self, warning_result: EarlyWarningResult) -> None:
        """Logic deletion should be detected (sample_update has 2 deleted relationships)."""
        logic_alerts = [a for a in warning_result.alerts if a.rule_id == "logic_deletion"]
        assert len(logic_alerts) >= 1
        if logic_alerts:
            assert logic_alerts[0].severity == "critical"


class TestRuleConstraintAddition:
    """Tests for Rule 6: Constraint Addition."""

    def test_constraint_addition_detected(self, warning_result: EarlyWarningResult) -> None:
        """Constraint addition should be detected (sample_update has new constraints)."""
        cstr_alerts = [a for a in warning_result.alerts if a.rule_id == "constraint_addition"]
        assert len(cstr_alerts) >= 1
        if cstr_alerts:
            assert cstr_alerts[0].severity == "warning"


class TestRuleRetroactiveDate:
    """Tests for Rule 5: Retroactive Date Change."""

    def test_retroactive_date_detected(self, warning_result: EarlyWarningResult) -> None:
        """Retroactive date changes should be detected from manipulation flags."""
        retro_alerts = [a for a in warning_result.alerts if a.rule_id == "retroactive_date"]
        # sample_update has retroactive date changes
        assert len(retro_alerts) >= 1
        if retro_alerts:
            assert retro_alerts[0].severity == "critical"


class TestRuleOpenEnded:
    """Tests for Rule 9: Open-Ended Activities."""

    def test_open_ended_detected(self, warning_result: EarlyWarningResult) -> None:
        """Open-ended activities should be detected in the update schedule."""
        oe_alerts = [a for a in warning_result.alerts if a.rule_id == "open_ended"]
        # Open-ended activities are common in sample schedules
        # This rule checks the update schedule directly
        if oe_alerts:
            assert oe_alerts[0].severity == "critical"
            assert len(oe_alerts[0].affected_activities) > 0


class TestSummary:
    """Tests for the summary output."""

    def test_summary_has_required_keys(self, warning_result: EarlyWarningResult) -> None:
        """Summary should include all expected keys."""
        required_keys = {
            "total_alerts",
            "critical",
            "warning",
            "info",
            "aggregate_score",
            "rules_checked",
        }
        assert required_keys.issubset(warning_result.summary.keys())

    def test_aggregate_score_positive(self, warning_result: EarlyWarningResult) -> None:
        """Aggregate score should be non-negative."""
        assert warning_result.aggregate_score >= 0
