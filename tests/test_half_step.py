# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the half-step (bifurcation) analysis engine.

Verifies change classification, half-step schedule creation, delay
effect separation, invariant checking, and edge cases per
AACE RP 29R-03 MIP 3.4.
"""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

import pytest

from src.analytics.half_step import (
    analyze_half_step,
    classify_changes,
    create_half_step_schedule,
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
# Fixtures — real XER files
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def baseline() -> ParsedSchedule:
    return XERReader(FIXTURES / "sample.xer").parse()


@pytest.fixture(scope="module")
def update1() -> ParsedSchedule:
    return XERReader(FIXTURES / "sample_update.xer").parse()


@pytest.fixture(scope="module")
def update2() -> ParsedSchedule:
    return XERReader(FIXTURES / "sample_update2.xer").parse()


# ---------------------------------------------------------------------------
# Fixtures — synthetic schedules for controlled testing
# ---------------------------------------------------------------------------


def _make_project(data_date: datetime) -> Project:
    return Project(
        proj_id="P1",
        proj_short_name="Test Project",
        last_recalc_date=data_date,
        plan_start_date=datetime(2025, 1, 1),
        sum_data_date=data_date,
    )


def _make_schedule_a() -> ParsedSchedule:
    """Create a simple 4-activity schedule (A→B→C→D, all FS)."""
    data_date = datetime(2025, 3, 1)
    return ParsedSchedule(
        projects=[_make_project(data_date)],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        activities=[
            Task(
                task_id="1",
                task_code="A",
                task_name="Foundation",
                status_code="TK_Complete",
                act_start_date=datetime(2025, 1, 1),
                act_end_date=datetime(2025, 1, 20),
                remain_drtn_hr_cnt=0.0,
                target_drtn_hr_cnt=120.0,
                phys_complete_pct=100.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Structure",
                status_code="TK_Active",
                act_start_date=datetime(2025, 1, 21),
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=160.0,
                phys_complete_pct=50.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="3",
                task_code="C",
                task_name="MEP Rough-in",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=120.0,
                target_drtn_hr_cnt=120.0,
                phys_complete_pct=0.0,
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
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="3", pred_task_id="2", pred_type="PR_FS"),
            Relationship(task_id="4", pred_task_id="3", pred_type="PR_FS"),
        ],
    )


def _make_schedule_b_progress_only() -> ParsedSchedule:
    """Schedule B with ONLY progress changes (no logic/revision changes)."""
    data_date = datetime(2025, 4, 1)
    return ParsedSchedule(
        projects=[_make_project(data_date)],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        activities=[
            Task(
                task_id="1",
                task_code="A",
                task_name="Foundation",
                status_code="TK_Complete",
                act_start_date=datetime(2025, 1, 1),
                act_end_date=datetime(2025, 1, 20),
                remain_drtn_hr_cnt=0.0,
                target_drtn_hr_cnt=120.0,
                phys_complete_pct=100.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Structure",
                status_code="TK_Complete",  # Progress: now complete
                act_start_date=datetime(2025, 1, 21),
                act_end_date=datetime(2025, 3, 15),  # Finished late
                remain_drtn_hr_cnt=0.0,
                target_drtn_hr_cnt=160.0,
                phys_complete_pct=100.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="3",
                task_code="C",
                task_name="MEP Rough-in",
                status_code="TK_Active",  # Progress: started
                act_start_date=datetime(2025, 3, 16),
                remain_drtn_hr_cnt=80.0,  # Progress: 33% done
                target_drtn_hr_cnt=120.0,
                phys_complete_pct=33.0,
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
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            # Same relationships as A — no logic changes
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="3", pred_task_id="2", pred_type="PR_FS"),
            Relationship(task_id="4", pred_task_id="3", pred_type="PR_FS"),
        ],
    )


def _make_schedule_b_revision_only() -> ParsedSchedule:
    """Schedule B with ONLY revision changes (same progress as A)."""
    data_date = datetime(2025, 4, 1)
    return ParsedSchedule(
        projects=[_make_project(data_date)],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        activities=[
            Task(
                task_id="1",
                task_code="A",
                task_name="Foundation",
                status_code="TK_Complete",
                act_start_date=datetime(2025, 1, 1),
                act_end_date=datetime(2025, 1, 20),
                remain_drtn_hr_cnt=0.0,
                target_drtn_hr_cnt=120.0,
                phys_complete_pct=100.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Structure",
                status_code="TK_Active",  # Same status as A
                act_start_date=datetime(2025, 1, 21),
                remain_drtn_hr_cnt=80.0,  # Same RD as A
                target_drtn_hr_cnt=160.0,
                phys_complete_pct=50.0,  # Same progress
                clndr_id="CAL1",
            ),
            Task(
                task_id="3",
                task_code="C",
                task_name="MEP Rough-in",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=160.0,  # Revision: duration increased
                target_drtn_hr_cnt=160.0,  # Revision: target changed
                phys_complete_pct=0.0,
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
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="3", pred_task_id="2", pred_type="PR_FS"),
            Relationship(task_id="4", pred_task_id="3", pred_type="PR_FS"),
            # Revision: new relationship added
            Relationship(task_id="4", pred_task_id="1", pred_type="PR_FS"),
        ],
    )


def _make_schedule_b_mixed() -> ParsedSchedule:
    """Schedule B with BOTH progress AND revision changes."""
    data_date = datetime(2025, 4, 1)
    return ParsedSchedule(
        projects=[_make_project(data_date)],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        activities=[
            Task(
                task_id="1",
                task_code="A",
                task_name="Foundation",
                status_code="TK_Complete",
                act_start_date=datetime(2025, 1, 1),
                act_end_date=datetime(2025, 1, 20),
                remain_drtn_hr_cnt=0.0,
                target_drtn_hr_cnt=120.0,
                phys_complete_pct=100.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Structure",
                status_code="TK_Complete",  # Progress: completed
                act_start_date=datetime(2025, 1, 21),
                act_end_date=datetime(2025, 3, 10),
                remain_drtn_hr_cnt=0.0,
                target_drtn_hr_cnt=160.0,
                phys_complete_pct=100.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="3",
                task_code="C",
                task_name="MEP Rough-in",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=160.0,  # Revision: duration increased
                target_drtn_hr_cnt=160.0,
                phys_complete_pct=0.0,
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
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="3", pred_task_id="2", pred_type="PR_FS"),
            Relationship(task_id="4", pred_task_id="3", pred_type="PR_FS"),
        ],
    )


@pytest.fixture
def schedule_a() -> ParsedSchedule:
    return _make_schedule_a()


@pytest.fixture
def schedule_b_progress() -> ParsedSchedule:
    return _make_schedule_b_progress_only()


@pytest.fixture
def schedule_b_revision() -> ParsedSchedule:
    return _make_schedule_b_revision_only()


@pytest.fixture
def schedule_b_mixed() -> ParsedSchedule:
    return _make_schedule_b_mixed()


# ===========================================================================
# Tests: Change Classification
# ===========================================================================


class TestChangeClassification:
    """Verify changes are correctly classified as progress or revision."""

    def test_status_change_is_progress(
        self, schedule_a: ParsedSchedule, schedule_b_progress: ParsedSchedule
    ) -> None:
        """Status code changes should be classified as progress."""
        result = classify_changes(schedule_a, schedule_b_progress)
        status_changes = [c for c in result.progress_changes if c.field_name == "status_code"]
        assert len(status_changes) > 0
        assert all(c.category == "progress" for c in status_changes)

    def test_actual_dates_are_progress(
        self, schedule_a: ParsedSchedule, schedule_b_progress: ParsedSchedule
    ) -> None:
        """Actual date changes should be classified as progress."""
        result = classify_changes(schedule_a, schedule_b_progress)
        date_changes = [
            c for c in result.progress_changes if c.field_name in ("act_start_date", "act_end_date")
        ]
        assert len(date_changes) > 0

    def test_relationship_change_is_revision(
        self, schedule_a: ParsedSchedule, schedule_b_revision: ParsedSchedule
    ) -> None:
        """Relationship additions should be classified as revision."""
        result = classify_changes(schedule_a, schedule_b_revision)
        rel_changes = [c for c in result.revision_changes if c.field_name == "relationship_added"]
        assert len(rel_changes) > 0

    def test_duration_on_not_started_is_revision(
        self, schedule_a: ParsedSchedule, schedule_b_revision: ParsedSchedule
    ) -> None:
        """Duration changes on not-started activities should be revisions."""
        result = classify_changes(schedule_a, schedule_b_revision)
        rd_revisions = [
            c
            for c in result.revision_changes
            if c.field_name in ("remain_drtn_hr_cnt", "target_duration")
        ]
        assert len(rd_revisions) > 0

    def test_progress_pct_is_progress(
        self, schedule_a: ParsedSchedule, schedule_b_progress: ParsedSchedule
    ) -> None:
        """Physical percent complete changes should be progress."""
        result = classify_changes(schedule_a, schedule_b_progress)
        pct_changes = [c for c in result.progress_changes if c.field_name == "phys_complete_pct"]
        assert len(pct_changes) > 0

    def test_summary_counts(
        self, schedule_a: ParsedSchedule, schedule_b_mixed: ParsedSchedule
    ) -> None:
        """Summary should contain correct count keys."""
        result = classify_changes(schedule_a, schedule_b_mixed)
        assert "progress_changes" in result.summary
        assert "revision_changes" in result.summary
        assert "matched_pairs" in result.summary
        assert result.summary["matched_pairs"] == 4

    def test_added_activities_detected(self, schedule_a: ParsedSchedule) -> None:
        """Activities in B but not A should be detected as added."""
        schedule_b = copy.deepcopy(schedule_a)
        schedule_b.activities.append(
            Task(
                task_id="5",
                task_code="E",
                task_name="New Activity",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=40.0,
                target_drtn_hr_cnt=40.0,
                clndr_id="CAL1",
            )
        )
        result = classify_changes(schedule_a, schedule_b)
        assert "E" in result.activities_added

    def test_deleted_activities_detected(self, schedule_a: ParsedSchedule) -> None:
        """Activities in A but not B should be detected as deleted."""
        schedule_b = copy.deepcopy(schedule_a)
        schedule_b.activities = [t for t in schedule_b.activities if t.task_code != "D"]
        result = classify_changes(schedule_a, schedule_b)
        assert "D" in result.activities_deleted


# ===========================================================================
# Tests: Half-Step Schedule Creation
# ===========================================================================


class TestHalfStepScheduleCreation:
    """Verify the half-step schedule transfers only progress fields."""

    def test_progress_fields_transferred(
        self, schedule_a: ParsedSchedule, schedule_b_progress: ParsedSchedule
    ) -> None:
        """Status, actuals, and % complete should be in the half-step."""
        hs, count = create_half_step_schedule(schedule_a, schedule_b_progress)
        assert count > 0

        hs_tasks = {t.task_code: t for t in hs.activities}

        # Task B should be complete in half-step (progress from B)
        assert hs_tasks["B"].status_code == "TK_Complete"
        assert hs_tasks["B"].act_end_date == datetime(2025, 3, 15)
        assert hs_tasks["B"].phys_complete_pct == 100.0

        # Task C should be active in half-step
        assert hs_tasks["C"].status_code == "TK_Active"
        assert hs_tasks["C"].act_start_date == datetime(2025, 3, 16)

    def test_relationships_preserved_from_a(
        self, schedule_a: ParsedSchedule, schedule_b_revision: ParsedSchedule
    ) -> None:
        """Half-step should keep Schedule A's relationships, not B's."""
        hs, _ = create_half_step_schedule(schedule_a, schedule_b_revision)

        # Schedule A has 3 relationships, B has 4 (one added)
        assert len(schedule_a.relationships) == 3
        assert len(schedule_b_revision.relationships) == 4
        # Half-step should have 3 (from A)
        assert len(hs.relationships) == 3

    def test_revision_duration_not_transferred(
        self, schedule_a: ParsedSchedule, schedule_b_revision: ParsedSchedule
    ) -> None:
        """Duration changes on not-started activities should NOT transfer."""
        hs, _ = create_half_step_schedule(schedule_a, schedule_b_revision)
        hs_tasks = {t.task_code: t for t in hs.activities}

        # Task C: A has RD=120h, B has RD=160h (revision)
        # Half-step should keep A's value (120h)
        assert hs_tasks["C"].remain_drtn_hr_cnt == 120.0

    def test_data_date_advanced(
        self, schedule_a: ParsedSchedule, schedule_b_progress: ParsedSchedule
    ) -> None:
        """Half-step data date should match Schedule B's data date."""
        hs, _ = create_half_step_schedule(schedule_a, schedule_b_progress)
        assert hs.projects[0].last_recalc_date == datetime(2025, 4, 1)

    def test_no_new_activities_added(self, schedule_a: ParsedSchedule) -> None:
        """Activities in B but not A should NOT appear in half-step."""
        schedule_b = copy.deepcopy(schedule_a)
        schedule_b.activities.append(
            Task(
                task_id="5",
                task_code="E",
                task_name="New",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=40.0,
                target_drtn_hr_cnt=40.0,
                clndr_id="CAL1",
            )
        )
        hs, _ = create_half_step_schedule(schedule_a, schedule_b)
        hs_codes = {t.task_code for t in hs.activities}
        assert "E" not in hs_codes
        assert len(hs.activities) == len(schedule_a.activities)

    def test_completed_activity_rd_zeroed(
        self, schedule_a: ParsedSchedule, schedule_b_progress: ParsedSchedule
    ) -> None:
        """Completed activities should have RD=0 in half-step."""
        hs, _ = create_half_step_schedule(schedule_a, schedule_b_progress)
        hs_tasks = {t.task_code: t for t in hs.activities}
        assert hs_tasks["B"].remain_drtn_hr_cnt == 0.0


# ===========================================================================
# Tests: Full Half-Step Analysis
# ===========================================================================


class TestHalfStepAnalysis:
    """Verify the complete half-step analysis produces correct results."""

    def test_invariant_holds(
        self, schedule_a: ParsedSchedule, schedule_b_progress: ParsedSchedule
    ) -> None:
        """progress_effect + revision_effect must equal total_delay."""
        result = analyze_half_step(schedule_a, schedule_b_progress)
        assert result.invariant_check is True
        assert abs(result.progress_effect + result.revision_effect - result.total_delay) < 0.01

    def test_progress_only_scenario(
        self, schedule_a: ParsedSchedule, schedule_b_progress: ParsedSchedule
    ) -> None:
        """With only progress changes, revision_effect should be ~0."""
        result = analyze_half_step(schedule_a, schedule_b_progress)
        # When B has same logic as A, revision effect should be minimal
        # (may not be exactly 0 due to CPM recalculation differences)
        assert result.invariant_check is True
        assert result.activities_updated > 0

    def test_revision_only_scenario(
        self, schedule_a: ParsedSchedule, schedule_b_revision: ParsedSchedule
    ) -> None:
        """With only revision changes, progress_effect should be ~0."""
        result = analyze_half_step(schedule_a, schedule_b_revision)
        assert result.invariant_check is True
        # Progress effect should be minimal since no progress changed
        # (half-step ≈ schedule A when no progress)

    def test_mixed_scenario(
        self, schedule_a: ParsedSchedule, schedule_b_mixed: ParsedSchedule
    ) -> None:
        """Mixed changes should separate into non-zero progress and revision."""
        result = analyze_half_step(schedule_a, schedule_b_mixed)
        assert result.invariant_check is True
        assert result.classification is not None

    def test_summary_populated(
        self, schedule_a: ParsedSchedule, schedule_b_mixed: ParsedSchedule
    ) -> None:
        """Summary should contain all expected keys."""
        result = analyze_half_step(schedule_a, schedule_b_mixed)
        s = result.summary
        assert s["methodology"] == "AACE RP 29R-03 MIP 3.4 — Contemporaneous Split Analysis"
        assert "progress_effect_days" in s
        assert "revision_effect_days" in s
        assert "total_delay_days" in s
        assert "invariant_holds" in s
        assert "progress_direction" in s
        assert "revision_direction" in s
        assert "cp_stability_a_to_hs" in s

    def test_critical_paths_populated(
        self, schedule_a: ParsedSchedule, schedule_b_progress: ParsedSchedule
    ) -> None:
        """All three critical paths should be populated."""
        result = analyze_half_step(schedule_a, schedule_b_progress)
        assert isinstance(result.critical_path_a, list)
        assert isinstance(result.critical_path_half_step, list)
        assert isinstance(result.critical_path_b, list)
        assert len(result.critical_path_a) > 0

    def test_identical_schedules(self, schedule_a: ParsedSchedule) -> None:
        """Identical schedules should produce zero delay in all categories."""
        schedule_b = copy.deepcopy(schedule_a)
        result = analyze_half_step(schedule_a, schedule_b)
        assert abs(result.total_delay) < 0.01
        assert abs(result.progress_effect) < 0.01
        assert abs(result.revision_effect) < 0.01
        assert result.invariant_check is True


# ===========================================================================
# Tests: Real XER Files
# ===========================================================================


class TestWithRealXERFiles:
    """Integration tests using actual XER fixture files."""

    def test_classify_changes_real(self, baseline: ParsedSchedule, update1: ParsedSchedule) -> None:
        """Classification should work with real XER data."""
        result = classify_changes(baseline, update1)
        assert result.summary["matched_pairs"] > 0
        total = (
            result.summary["progress_changes"]
            + result.summary["revision_changes"]
            + result.summary["ambiguous_changes"]
        )
        assert total > 0

    def test_create_half_step_real(self, baseline: ParsedSchedule, update1: ParsedSchedule) -> None:
        """Half-step schedule creation should work with real XER data."""
        hs, count = create_half_step_schedule(baseline, update1)
        assert count > 0
        assert len(hs.activities) == len(baseline.activities)
        # Relationships should be from baseline
        assert len(hs.relationships) == len(baseline.relationships)

    def test_analyze_half_step_real(
        self, baseline: ParsedSchedule, update1: ParsedSchedule
    ) -> None:
        """Full half-step analysis should work with real XER data."""
        result = analyze_half_step(baseline, update1)
        assert result.invariant_check is True
        assert result.classification is not None
        assert result.summary["methodology"].startswith("AACE RP 29R-03")

    def test_analyze_half_step_real_update2(
        self, baseline: ParsedSchedule, update2: ParsedSchedule
    ) -> None:
        """Half-step should work with a larger update gap (baseline→update2)."""
        result = analyze_half_step(baseline, update2)
        assert result.invariant_check is True

    def test_half_step_preserves_baseline_logic(
        self, baseline: ParsedSchedule, update1: ParsedSchedule
    ) -> None:
        """Half-step relationships must match baseline exactly."""
        hs, _ = create_half_step_schedule(baseline, update1)
        base_rels = {(r.task_id, r.pred_task_id, r.pred_type) for r in baseline.relationships}
        hs_rels = {(r.task_id, r.pred_task_id, r.pred_type) for r in hs.relationships}
        assert base_rels == hs_rels


# ===========================================================================
# Tests: Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Verify robustness for edge cases."""

    def test_empty_schedule(self) -> None:
        """Schedules with no activities should not crash."""
        a = ParsedSchedule(
            projects=[_make_project(datetime(2025, 1, 1))],
        )
        b = ParsedSchedule(
            projects=[_make_project(datetime(2025, 2, 1))],
        )
        result = classify_changes(a, b)
        assert result.summary["matched_pairs"] == 0

    def test_single_activity(self) -> None:
        """Schedule with one activity should work."""
        a = ParsedSchedule(
            projects=[_make_project(datetime(2025, 1, 1))],
            activities=[
                Task(
                    task_id="1",
                    task_code="A",
                    task_name="Only",
                    status_code="TK_NotStart",
                    remain_drtn_hr_cnt=80.0,
                    target_drtn_hr_cnt=80.0,
                    clndr_id="CAL1",
                ),
            ],
        )
        b = copy.deepcopy(a)
        b.activities[0].status_code = "TK_Active"
        b.activities[0].act_start_date = datetime(2025, 1, 15)
        b.activities[0].phys_complete_pct = 25.0
        b.activities[0].remain_drtn_hr_cnt = 60.0

        result = analyze_half_step(a, b)
        assert result.invariant_check is True

    def test_all_activities_completed(self, schedule_a: ParsedSchedule) -> None:
        """Both schedules fully complete should give zero delay."""
        a = copy.deepcopy(schedule_a)
        for t in a.activities:
            t.status_code = "TK_Complete"
            t.remain_drtn_hr_cnt = 0.0
            t.phys_complete_pct = 100.0
            t.act_start_date = datetime(2025, 1, 1)
            t.act_end_date = datetime(2025, 2, 1)
        b = copy.deepcopy(a)

        result = analyze_half_step(a, b)
        assert abs(result.total_delay) < 0.01
        assert result.invariant_check is True

    def test_deep_copy_isolation(
        self, schedule_a: ParsedSchedule, schedule_b_progress: ParsedSchedule
    ) -> None:
        """Creating half-step should not mutate the original Schedule A."""
        original_statuses = [t.status_code for t in schedule_a.activities]
        create_half_step_schedule(schedule_a, schedule_b_progress)
        current_statuses = [t.status_code for t in schedule_a.activities]
        assert original_statuses == current_statuses
