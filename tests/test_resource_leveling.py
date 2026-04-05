# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the resource leveling (RCPSP) engine."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.analytics.resource_leveling import (
    LevelingConfig,
    LevelingResult,
    ResourceLimit,
    level_resources,
)
from src.parser.models import (
    Calendar,
    ParsedSchedule,
    Project,
    Relationship,
    Resource,
    Task,
    TaskResource,
)
from src.parser.xer_reader import XERReader

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


def _make_resource_schedule() -> ParsedSchedule:
    """Schedule with resource conflicts: A and B in parallel, both need crane."""
    return ParsedSchedule(
        projects=[_make_project()],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        resources=[
            Resource(rsrc_id="R1", rsrc_name="Crane", rsrc_type="RT_EQUIP"),
            Resource(rsrc_id="R2", rsrc_name="Labor", rsrc_type="RT_LABOR"),
        ],
        activities=[
            Task(
                task_id="1",
                task_code="START",
                task_name="Mobilization",
                status_code="TK_Complete",
                remain_drtn_hr_cnt=0.0,
                target_drtn_hr_cnt=40.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="2",
                task_code="A",
                task_name="Steel Erection",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=80.0,  # 10 days
                target_drtn_hr_cnt=80.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="3",
                task_code="B",
                task_name="Precast Install",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=80.0,  # 10 days
                target_drtn_hr_cnt=80.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="4",
                task_code="C",
                task_name="Finishes",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=40.0,  # 5 days
                target_drtn_hr_cnt=40.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            # START → A, START → B (parallel), A → C, B → C
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="3", pred_task_id="1", pred_type="PR_FS"),
            Relationship(task_id="4", pred_task_id="2", pred_type="PR_FS"),
            Relationship(task_id="4", pred_task_id="3", pred_type="PR_FS"),
        ],
        task_resources=[
            # Both A and B need 1 crane (but only 1 available)
            TaskResource(task_id="2", rsrc_id="R1", target_qty=1.0, remain_qty=1.0),
            TaskResource(task_id="3", rsrc_id="R1", target_qty=1.0, remain_qty=1.0),
            # A needs 5 laborers, B needs 3
            TaskResource(task_id="2", rsrc_id="R2", target_qty=5.0, remain_qty=5.0),
            TaskResource(task_id="3", rsrc_id="R2", target_qty=3.0, remain_qty=3.0),
        ],
    )


def _make_no_conflict_schedule() -> ParsedSchedule:
    """Sequential schedule — no resource conflicts."""
    return ParsedSchedule(
        projects=[_make_project()],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        resources=[Resource(rsrc_id="R1", rsrc_name="Crane")],
        activities=[
            Task(
                task_id="1",
                task_code="A",
                task_name="First",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=80.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Second",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=80.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
        ],
        task_resources=[
            TaskResource(task_id="1", rsrc_id="R1", target_qty=1.0, remain_qty=1.0),
            TaskResource(task_id="2", rsrc_id="R1", target_qty=1.0, remain_qty=1.0),
        ],
    )


@pytest.fixture
def resource_schedule() -> ParsedSchedule:
    return _make_resource_schedule()


@pytest.fixture
def no_conflict_schedule() -> ParsedSchedule:
    return _make_no_conflict_schedule()


# ===========================================================================
# Tests: Basic Leveling
# ===========================================================================


class TestBasicLeveling:
    def test_returns_result(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)])
        result = level_resources(resource_schedule, config)
        assert isinstance(result, LevelingResult)

    def test_crane_conflict_extends_duration(self, resource_schedule: ParsedSchedule) -> None:
        """A and B both need 1 crane but only 1 available → must serialize."""
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)])
        result = level_resources(resource_schedule, config)
        # Original: A and B in parallel (10d), then C (5d) = 15d total
        # Leveled: A (10d) then B (10d) then C (5d) = 25d total
        assert result.leveled_duration_days > result.original_duration_days
        assert result.extension_days > 0

    def test_sufficient_resources_no_extension(self, resource_schedule: ParsedSchedule) -> None:
        """If 2 cranes available, no extension needed."""
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id="R1", max_units=2.0)])
        result = level_resources(resource_schedule, config)
        assert result.extension_days == 0

    def test_no_conflict_no_shift(self, no_conflict_schedule: ParsedSchedule) -> None:
        """Sequential activities don't conflict even with 1 resource."""
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)])
        result = level_resources(no_conflict_schedule, config)
        assert result.extension_days == 0

    def test_no_limits_returns_unconstrained(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig()
        result = level_resources(resource_schedule, config)
        assert "unconstrained" in result.methodology.lower()


# ===========================================================================
# Tests: Priority Rules
# ===========================================================================


class TestPriorityRules:
    def test_late_start_rule(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig(
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
            priority_rule="late_start",
        )
        result = level_resources(resource_schedule, config)
        assert result.priority_rule == "late_start"
        assert result.leveled_duration_days > 0

    def test_early_start_rule(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig(
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
            priority_rule="early_start",
        )
        result = level_resources(resource_schedule, config)
        assert result.priority_rule == "early_start"

    def test_float_rule(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig(
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
            priority_rule="float",
        )
        result = level_resources(resource_schedule, config)
        assert result.priority_rule == "float"

    def test_duration_rule(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig(
            resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)],
            priority_rule="duration",
        )
        result = level_resources(resource_schedule, config)
        assert result.priority_rule == "duration"


# ===========================================================================
# Tests: Resource Profiles
# ===========================================================================


class TestResourceProfiles:
    def test_has_profiles(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)])
        result = level_resources(resource_schedule, config)
        assert len(result.resource_profiles) == 1
        assert result.resource_profiles[0].rsrc_id == "R1"

    def test_peak_demand_within_capacity(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)])
        result = level_resources(resource_schedule, config)
        for profile in result.resource_profiles:
            assert profile.peak_demand <= profile.max_units

    def test_multiple_resources(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig(
            resource_limits=[
                ResourceLimit(rsrc_id="R1", max_units=1.0),
                ResourceLimit(rsrc_id="R2", max_units=5.0),
            ]
        )
        result = level_resources(resource_schedule, config)
        assert len(result.resource_profiles) == 2


# ===========================================================================
# Tests: Activity Shifts
# ===========================================================================


class TestActivityShifts:
    def test_shifted_activities(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)])
        result = level_resources(resource_schedule, config)
        shifted = [s for s in result.activity_shifts if s.shift_days > 0]
        assert len(shifted) > 0

    def test_shifts_sorted_by_magnitude(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)])
        result = level_resources(resource_schedule, config)
        shifts = [abs(s.shift_days) for s in result.activity_shifts]
        assert shifts == sorted(shifts, reverse=True)


# ===========================================================================
# Tests: Summary & Metadata
# ===========================================================================


class TestSummary:
    def test_summary_keys(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)])
        result = level_resources(resource_schedule, config)
        s = result.summary
        assert "original_duration_days" in s
        assert "leveled_duration_days" in s
        assert "extension_days" in s
        assert "methodology" in s
        assert "references" in s

    def test_methodology_set(self, resource_schedule: ParsedSchedule) -> None:
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)])
        result = level_resources(resource_schedule, config)
        assert "sgs" in result.methodology.lower()


# ===========================================================================
# Tests: Real XER
# ===========================================================================


class TestRealXER:
    def test_leveling_real_no_limits(self, real_schedule: ParsedSchedule) -> None:
        """Real XER with no limits should return unconstrained."""
        config = LevelingConfig()
        result = level_resources(real_schedule, config)
        assert result.original_duration_days > 0

    def test_leveling_real_with_limits(self, real_schedule: ParsedSchedule) -> None:
        """Real XER with a generic limit."""
        # Get resource IDs from schedule
        if not real_schedule.resources:
            pytest.skip("No resources in fixture")
        rsrc_id = real_schedule.resources[0].rsrc_id
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id=rsrc_id, max_units=1.0)])
        result = level_resources(real_schedule, config)
        assert result.leveled_duration_days >= result.original_duration_days


# ===========================================================================
# Tests: Edge Cases
# ===========================================================================


class TestEdgeCases:
    def test_empty_schedule(self) -> None:
        s = ParsedSchedule(projects=[_make_project()])
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)])
        result = level_resources(s, config)
        assert result.original_duration_days == 0

    def test_no_task_resources(self) -> None:
        """Schedule with activities but no resource assignments."""
        s = ParsedSchedule(
            projects=[_make_project()],
            activities=[
                Task(
                    task_id="1",
                    task_code="A",
                    task_name="Solo",
                    status_code="TK_NotStart",
                    remain_drtn_hr_cnt=80.0,
                    target_drtn_hr_cnt=80.0,
                    clndr_id="CAL1",
                )
            ],
        )
        config = LevelingConfig(resource_limits=[ResourceLimit(rsrc_id="R1", max_units=1.0)])
        result = level_resources(s, config)
        # No resources assigned = no conflict = no extension
        assert result.extension_days == 0
