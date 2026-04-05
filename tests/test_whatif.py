# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the what-if schedule simulator.

Verifies deterministic and probabilistic modes, duration adjustments,
critical path change detection, and edge cases.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.analytics.whatif import (
    DurationAdjustment,
    WhatIfResult,
    WhatIfScenario,
    simulate_whatif,
)
from src.parser.models import (
    Calendar,
    ParsedSchedule,
    Project,
    Relationship,
    Task,
)
from src.parser.xer_reader import XERReader

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def real_schedule() -> ParsedSchedule:
    return XERReader(FIXTURES / "sample.xer").parse()


def _make_project() -> Project:
    return Project(
        proj_id="P1",
        proj_short_name="Test",
        last_recalc_date=datetime(2025, 3, 1),
        plan_start_date=datetime(2025, 1, 1),
        sum_data_date=datetime(2025, 3, 1),
    )


def _make_schedule() -> ParsedSchedule:
    """Linear 4-activity schedule: A→B→C→D, all FS."""
    return ParsedSchedule(
        projects=[_make_project()],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        activities=[
            Task(
                task_id="1",
                task_code="A",
                task_name="Foundation",
                status_code="TK_Active",
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=80.0,
                phys_complete_pct=50.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Structure",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=160.0,
                target_drtn_hr_cnt=160.0,
                phys_complete_pct=0.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="3",
                task_code="C",
                task_name="MEP",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=120.0,
                target_drtn_hr_cnt=120.0,
                phys_complete_pct=0.0,
                total_float_hr_cnt=80.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="4",
                task_code="D",
                task_name="Finishes",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=80.0,
                phys_complete_pct=0.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="3", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="4", pred_task_id="2", pred_type="PR_FS"),
            Relationship(task_id="4", pred_task_id="3", pred_type="PR_FS"),
        ],
    )


@pytest.fixture
def schedule() -> ParsedSchedule:
    return _make_schedule()


# ===========================================================================
# Tests: Basic Deterministic
# ===========================================================================


class TestDeterministic:
    """Verify deterministic single-run what-if analysis."""

    def test_returns_result(self, schedule: ParsedSchedule) -> None:
        scenario = WhatIfScenario(name="Test", adjustments=[])
        result = simulate_whatif(schedule, scenario)
        assert isinstance(result, WhatIfResult)

    def test_no_adjustments_no_change(self, schedule: ParsedSchedule) -> None:
        scenario = WhatIfScenario(name="Baseline")
        result = simulate_whatif(schedule, scenario)
        assert result.delta_days == 0
        assert result.base_duration_days == result.adjusted_duration_days

    def test_increase_duration(self, schedule: ParsedSchedule) -> None:
        """Increasing a critical activity should extend the project."""
        scenario = WhatIfScenario(
            name="Extend B",
            adjustments=[DurationAdjustment(target="B", pct_change=0.50)],
        )
        result = simulate_whatif(schedule, scenario)
        assert result.delta_days > 0
        assert result.adjusted_duration_days > result.base_duration_days

    def test_decrease_duration(self, schedule: ParsedSchedule) -> None:
        """Decreasing a critical activity should shorten the project."""
        scenario = WhatIfScenario(
            name="Compress B",
            adjustments=[DurationAdjustment(target="B", pct_change=-0.30)],
        )
        result = simulate_whatif(schedule, scenario)
        assert result.delta_days < 0

    def test_non_critical_no_effect(self, schedule: ParsedSchedule) -> None:
        """Adjusting non-critical activity within float should not extend."""
        scenario = WhatIfScenario(
            name="Extend C (non-critical)",
            adjustments=[DurationAdjustment(target="C", pct_change=0.10)],
        )
        result = simulate_whatif(schedule, scenario)
        # C has 80h float (10 days), 10% of 120h = 12h (1.5 days) — within float
        assert result.delta_days == 0

    def test_wildcard_adjustment(self, schedule: ParsedSchedule) -> None:
        """Wildcard * should adjust all non-complete activities."""
        scenario = WhatIfScenario(
            name="All +20%",
            adjustments=[DurationAdjustment(target="*", pct_change=0.20)],
        )
        result = simulate_whatif(schedule, scenario)
        assert result.delta_days > 0

    def test_wbs_adjustment(self) -> None:
        """WBS-targeted adjustment should only affect matching activities."""
        s = _make_schedule()
        for t in s.activities:
            if t.task_code in ("A", "B"):
                t.wbs_id = "1.1"
            else:
                t.wbs_id = "1.2"

        scenario = WhatIfScenario(
            name="WBS 1.1 +50%",
            adjustments=[DurationAdjustment(target="WBS:1.1", pct_change=0.50)],
        )
        result = simulate_whatif(s, scenario)
        assert result.delta_days > 0
        # Only A and B should be impacted
        impacted = [i for i in result.activity_impacts if i.delta_days != 0]
        impacted_codes = {i.task_code for i in impacted}
        assert "A" in impacted_codes or "B" in impacted_codes

    def test_critical_path_change_detected(self, schedule: ParsedSchedule) -> None:
        """Extending a non-critical activity past its float should shift CP."""
        scenario = WhatIfScenario(
            name="C becomes critical",
            adjustments=[DurationAdjustment(target="C", pct_change=2.0)],
        )
        result = simulate_whatif(schedule, scenario)
        assert result.critical_path_changed is True

    def test_complete_activity_not_adjusted(self) -> None:
        """Completed activities should not be modified."""
        s = _make_schedule()
        s.activities[0].status_code = "TK_Complete"
        scenario = WhatIfScenario(
            name="All +50%",
            adjustments=[DurationAdjustment(target="*", pct_change=0.50)],
        )
        result = simulate_whatif(s, scenario)
        impact_a = next((i for i in result.activity_impacts if i.task_code == "A"), None)
        if impact_a:
            assert impact_a.delta_days == 0

    def test_activity_impacts_sorted(self, schedule: ParsedSchedule) -> None:
        scenario = WhatIfScenario(
            name="Mixed",
            adjustments=[
                DurationAdjustment(target="A", pct_change=0.10),
                DurationAdjustment(target="B", pct_change=0.50),
            ],
        )
        result = simulate_whatif(schedule, scenario)
        deltas = [abs(i.delta_days) for i in result.activity_impacts]
        assert deltas == sorted(deltas, reverse=True)

    def test_delta_pct(self, schedule: ParsedSchedule) -> None:
        scenario = WhatIfScenario(
            name="Test",
            adjustments=[DurationAdjustment(target="B", pct_change=0.50)],
        )
        result = simulate_whatif(schedule, scenario)
        assert result.delta_pct > 0

    def test_methodology_set(self, schedule: ParsedSchedule) -> None:
        scenario = WhatIfScenario(
            name="Test",
            adjustments=[DurationAdjustment(target="B", pct_change=0.10)],
        )
        result = simulate_whatif(schedule, scenario)
        assert "deterministic" in result.methodology.lower()


# ===========================================================================
# Tests: Probabilistic
# ===========================================================================


class TestProbabilistic:
    """Verify probabilistic multi-iteration mode."""

    def test_probabilistic_returns_distribution(self, schedule: ParsedSchedule) -> None:
        scenario = WhatIfScenario(
            name="Range test",
            adjustments=[
                DurationAdjustment(target="B", pct_change=0.20, min_pct=0.0, max_pct=0.40),
            ],
            iterations=50,
        )
        result = simulate_whatif(schedule, scenario)
        assert len(result.distribution) == 50
        assert result.iterations == 50

    def test_probabilistic_has_p_values(self, schedule: ParsedSchedule) -> None:
        scenario = WhatIfScenario(
            name="P-values",
            adjustments=[
                DurationAdjustment(target="*", pct_change=0.0, min_pct=-0.10, max_pct=0.30),
            ],
            iterations=100,
        )
        result = simulate_whatif(schedule, scenario)
        assert 50 in result.p_values
        assert 80 in result.p_values
        assert 90 in result.p_values
        # P90 >= P50
        assert result.p_values[90] >= result.p_values[50]

    def test_probabilistic_has_std(self, schedule: ParsedSchedule) -> None:
        scenario = WhatIfScenario(
            name="Std",
            adjustments=[
                DurationAdjustment(target="B", pct_change=0.0, min_pct=-0.20, max_pct=0.20),
            ],
            iterations=50,
        )
        result = simulate_whatif(schedule, scenario)
        assert result.std_days > 0

    def test_probabilistic_methodology(self, schedule: ParsedSchedule) -> None:
        scenario = WhatIfScenario(
            name="Method",
            adjustments=[DurationAdjustment(target="B", pct_change=0.10)],
            iterations=20,
        )
        result = simulate_whatif(schedule, scenario)
        assert "probabilistic" in result.methodology.lower()
        assert "20" in result.methodology

    def test_deterministic_seed_reproducibility(self, schedule: ParsedSchedule) -> None:
        """Same scenario should produce same results (seeded RNG)."""
        scenario = WhatIfScenario(
            name="Repro",
            adjustments=[
                DurationAdjustment(target="*", pct_change=0.0, min_pct=0.0, max_pct=0.50),
            ],
            iterations=30,
        )
        r1 = simulate_whatif(schedule, scenario)
        r2 = simulate_whatif(schedule, scenario)
        assert r1.distribution == r2.distribution


# ===========================================================================
# Tests: Summary
# ===========================================================================


class TestSummary:
    """Verify summary dict contains expected keys."""

    def test_summary_keys(self, schedule: ParsedSchedule) -> None:
        scenario = WhatIfScenario(
            name="Summary",
            adjustments=[DurationAdjustment(target="B", pct_change=0.20)],
        )
        result = simulate_whatif(schedule, scenario)
        s = result.summary
        assert "scenario_name" in s
        assert "base_duration_days" in s
        assert "adjusted_duration_days" in s
        assert "delta_days" in s
        assert "methodology" in s
        assert "references" in s
        assert "activities_impacted" in s


# ===========================================================================
# Tests: Real XER
# ===========================================================================


class TestRealXER:
    """Integration tests with real XER files."""

    def test_deterministic_real(self, real_schedule: ParsedSchedule) -> None:
        scenario = WhatIfScenario(
            name="Real +10%",
            adjustments=[DurationAdjustment(target="*", pct_change=0.10)],
        )
        result = simulate_whatif(real_schedule, scenario)
        assert result.base_duration_days > 0
        assert result.delta_days >= 0

    def test_probabilistic_real(self, real_schedule: ParsedSchedule) -> None:
        scenario = WhatIfScenario(
            name="Real range",
            adjustments=[
                DurationAdjustment(target="*", pct_change=0.0, min_pct=-0.10, max_pct=0.20),
            ],
            iterations=30,
        )
        result = simulate_whatif(real_schedule, scenario)
        assert len(result.distribution) == 30
        assert result.p_values[50] > 0


# ===========================================================================
# Tests: Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Edge case handling."""

    def test_empty_schedule(self) -> None:
        s = ParsedSchedule(projects=[_make_project()])
        scenario = WhatIfScenario(
            name="Empty",
            adjustments=[DurationAdjustment(target="*", pct_change=0.20)],
        )
        result = simulate_whatif(s, scenario)
        assert result.base_duration_days == 0

    def test_negative_pct_floor_at_zero(self, schedule: ParsedSchedule) -> None:
        """Duration should not go below 0."""
        scenario = WhatIfScenario(
            name="Extreme compress",
            adjustments=[DurationAdjustment(target="*", pct_change=-2.0)],
        )
        result = simulate_whatif(schedule, scenario)
        assert result.adjusted_duration_days >= 0

    def test_multiple_adjustments_same_activity(self, schedule: ParsedSchedule) -> None:
        """Multiple adjustments to same activity stack."""
        scenario = WhatIfScenario(
            name="Stacked",
            adjustments=[
                DurationAdjustment(target="B", pct_change=0.20),
                DurationAdjustment(target="B", pct_change=0.10),
            ],
        )
        result = simulate_whatif(schedule, scenario)
        # Both adjustments applied sequentially
        assert result.delta_days > 0
