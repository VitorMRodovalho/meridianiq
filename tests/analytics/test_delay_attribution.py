# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for delay attribution engine."""

from __future__ import annotations

import pytest

from src.analytics.delay_attribution import (
    AttributionResult,
    compute_delay_attribution,
)
from src.parser.models import Calendar, ParsedSchedule, Relationship, Task


def _make_schedule(
    tasks: list[Task] | None = None,
    rels: list[Relationship] | None = None,
) -> ParsedSchedule:
    return ParsedSchedule(
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8, week_hr_cnt=40, default_flag="Y")],
        activities=tasks or [],
        relationships=rels or [],
    )


class TestWithTIAData:
    """When TIA results are available, use explicit party assignments."""

    def test_tia_attribution(self) -> None:
        schedule = _make_schedule()
        tia = {
            "total_owner_delay": 30.0,
            "total_contractor_delay": 15.0,
            "total_shared_delay": 5.0,
            "total_third_party_delay": 0.0,
            "total_force_majeure_delay": 10.0,
        }
        result = compute_delay_attribution(schedule, tia_results=tia)
        assert result.data_source == "tia"
        assert result.total_delay_days == 60.0
        assert result.excusable_days == 45.0
        assert result.non_excusable_days == 15.0
        assert result.concurrent_days == 5.0
        assert len(result.parties) == 4  # zero-delay parties excluded

    def test_tia_owner_only(self) -> None:
        schedule = _make_schedule()
        tia = {
            "total_owner_delay": 20.0,
            "total_contractor_delay": 0.0,
        }
        result = compute_delay_attribution(schedule, tia_results=tia)
        assert result.data_source == "tia"
        assert len(result.parties) == 1
        assert result.parties[0].party == "Owner"
        assert result.parties[0].pct_of_total == 100.0

    def test_tia_zero_delay(self) -> None:
        schedule = _make_schedule()
        tia = {
            "total_owner_delay": 0.0,
            "total_contractor_delay": 0.0,
        }
        result = compute_delay_attribution(schedule, tia_results=tia)
        assert result.total_delay_days == 0.0
        assert len(result.parties) == 0


class TestEstimatedAttribution:
    """Without TIA, attribution is heuristic-based."""

    def test_no_delay_no_baseline(self) -> None:
        tasks = [
            Task(task_id="A1", status_code="TK_Active", task_type="TT_Task"),
        ]
        result = compute_delay_attribution(_make_schedule(tasks))
        assert result.data_source == "estimated"
        # No negative float = no detected delay
        assert result.total_delay_days == 0.0

    def test_negative_float_detected(self) -> None:
        tasks = [
            Task(
                task_id="A1",
                status_code="TK_Active",
                task_type="TT_Task",
                total_float_hr_cnt=-40.0,  # 5 days negative float
            ),
        ]
        result = compute_delay_attribution(_make_schedule(tasks))
        assert result.data_source == "estimated"
        assert result.total_delay_days > 0

    def test_constraint_tasks_attributed_to_owner(self) -> None:
        tasks = [
            Task(
                task_id="A1",
                status_code="TK_Active",
                task_type="TT_Task",
                total_float_hr_cnt=-80.0,
                cstr_type="CS_MFNLT",  # Must Finish No Later Than
            ),
        ]
        result = compute_delay_attribution(_make_schedule(tasks))
        owner_party = next((p for p in result.parties if p.party == "Owner"), None)
        assert owner_party is not None
        assert owner_party.delay_days > 0


class TestMethodology:
    """Result includes methodology."""

    def test_methodology_present(self) -> None:
        result = compute_delay_attribution(_make_schedule())
        assert "AACE" in result.methodology
        assert "SCL" in result.methodology
