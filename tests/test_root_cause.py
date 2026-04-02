# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for root cause analysis engine (v1.2).

Tests verify that:
1. Backwards network trace finds driving predecessors correctly
2. Chain terminates at activities with no predecessors
3. Chain terminates at hard constraints
4. Various relationship types (FS, SS, FF) are handled
5. API endpoint returns expected structure
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.analytics.root_cause import analyze_root_cause
from src.api.app import app, get_store

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XER = FIXTURES / "sample.xer"


# ── Mock objects ──


@dataclass
class MockProject:
    proj_short_name: str = "Test"
    last_recalc_date: datetime = field(default_factory=lambda: datetime(2026, 3, 1))
    sum_data_date: datetime | None = None


@dataclass
class MockTask:
    task_id: str = "A1000"
    task_code: str = "A1000"
    task_name: str = "Task"
    task_type: str = "TT_Task"
    status_code: str = "TK_Active"
    total_float_hr_cnt: float = 0.0
    remain_drtn_hr_cnt: float = 80.0  # 10 days
    target_drtn_hr_cnt: float = 80.0
    phys_complete_pct: float = 0.0
    wbs_id: str = "WBS1"
    cstr_type: str = ""
    cstr_type2: str = ""
    act_start_date: datetime | None = None
    act_end_date: datetime | None = None
    early_start_date: datetime | None = None
    early_end_date: datetime | None = None
    late_start_date: datetime | None = None
    late_end_date: datetime | None = None
    target_start_date: datetime | None = None
    target_end_date: datetime | None = None


@dataclass
class MockRelationship:
    task_id: str = "A1001"
    pred_task_id: str = "A1000"
    pred_type: str = "PR_FS"
    lag_hr_cnt: float = 0.0


@dataclass
class MockSchedule:
    projects: list = field(default_factory=lambda: [MockProject()])
    activities: list = field(default_factory=list)
    relationships: list = field(default_factory=list)
    calendars: list = field(default_factory=list)
    wbs_nodes: list = field(default_factory=list)
    task_resources: list = field(default_factory=list)
    parser_version: str = "1.0"


# ── Unit Tests ──


class TestRootCauseAnalysis:
    """Tests for the root cause trace engine."""

    def test_empty_schedule(self):
        """Empty schedule returns empty chain."""
        schedule = MockSchedule()
        result = analyze_root_cause(schedule)
        assert result.chain_length == 0

    def test_single_activity(self):
        """Single activity is both target and root cause."""
        schedule = MockSchedule(activities=[
            MockTask(task_id="A1", task_code="A1", task_name="Only Task"),
        ])
        result = analyze_root_cause(schedule)
        assert result.chain_length == 1
        assert result.target_activity == "A1"
        assert result.root_cause == "A1"
        assert "No predecessors" in result.chain[0].driving_reason

    def test_linear_chain(self):
        """Linear A→B→C chain traces back from C to A."""
        schedule = MockSchedule(
            activities=[
                MockTask(task_id="A", task_code="A", task_name="Start", remain_drtn_hr_cnt=40),
                MockTask(task_id="B", task_code="B", task_name="Middle", remain_drtn_hr_cnt=80),
                MockTask(task_id="C", task_code="C", task_name="End", remain_drtn_hr_cnt=40),
            ],
            relationships=[
                MockRelationship(task_id="B", pred_task_id="A"),
                MockRelationship(task_id="C", pred_task_id="B"),
            ],
        )
        result = analyze_root_cause(schedule)
        assert result.target_activity == "C"
        assert result.root_cause == "A"
        assert result.chain_length == 3
        assert result.chain[0].task_id == "C"
        assert result.chain[1].task_id == "B"
        assert result.chain[2].task_id == "A"

    def test_parallel_paths_picks_driving(self):
        """With parallel paths, picks the one with the latest early finish."""
        schedule = MockSchedule(
            activities=[
                MockTask(task_id="A1", task_code="A1", task_name="Short Path",
                         remain_drtn_hr_cnt=40),  # 5 days
                MockTask(task_id="A2", task_code="A2", task_name="Long Path",
                         remain_drtn_hr_cnt=160),  # 20 days
                MockTask(task_id="END", task_code="END", task_name="End",
                         remain_drtn_hr_cnt=8),  # 1 day
            ],
            relationships=[
                MockRelationship(task_id="END", pred_task_id="A1"),
                MockRelationship(task_id="END", pred_task_id="A2"),
            ],
        )
        result = analyze_root_cause(schedule)
        assert result.target_activity == "END"
        # Should trace through A2 (longer path = driving)
        assert result.chain[1].task_id == "A2"
        assert result.root_cause == "A2"

    def test_specific_target(self):
        """Can specify a target activity explicitly."""
        schedule = MockSchedule(
            activities=[
                MockTask(task_id="A", task_code="A", remain_drtn_hr_cnt=40),
                MockTask(task_id="B", task_code="B", remain_drtn_hr_cnt=40),
            ],
            relationships=[
                MockRelationship(task_id="B", pred_task_id="A"),
            ],
        )
        result = analyze_root_cause(schedule, target_task_id="B")
        assert result.target_activity == "B"
        assert result.root_cause == "A"

    def test_stops_at_hard_constraint(self):
        """Chain stops at an activity with a hard constraint."""
        schedule = MockSchedule(
            activities=[
                MockTask(task_id="A", task_code="A", remain_drtn_hr_cnt=40),
                MockTask(task_id="B", task_code="B", remain_drtn_hr_cnt=40,
                         cstr_type="CS_MSO"),  # Must Start On
                MockTask(task_id="C", task_code="C", remain_drtn_hr_cnt=40),
            ],
            relationships=[
                MockRelationship(task_id="B", pred_task_id="A"),
                MockRelationship(task_id="C", pred_task_id="B"),
            ],
        )
        result = analyze_root_cause(schedule, target_task_id="C")
        # Should stop at B because it has a hard constraint
        assert result.root_cause == "B"
        assert result.chain[-1].is_constraint

    def test_chain_has_correct_attributes(self):
        """Each step has the expected attributes."""
        schedule = MockSchedule(
            activities=[
                MockTask(task_id="A", task_code="ACT-001", task_name="Foundation",
                         remain_drtn_hr_cnt=80),
            ],
        )
        result = analyze_root_cause(schedule)
        step = result.chain[0]
        assert step.task_code == "ACT-001"
        assert step.task_name == "Foundation"
        assert step.duration_days == 10.0
        assert step.early_start == 0.0
        assert step.early_finish == 10.0

    def test_ss_relationship(self):
        """Start-to-Start relationships are handled correctly."""
        schedule = MockSchedule(
            activities=[
                MockTask(task_id="A", task_code="A", remain_drtn_hr_cnt=80),
                MockTask(task_id="B", task_code="B", remain_drtn_hr_cnt=80),
            ],
            relationships=[
                MockRelationship(task_id="B", pred_task_id="A", pred_type="PR_SS"),
            ],
        )
        result = analyze_root_cause(schedule, target_task_id="B")
        assert result.chain_length == 2
        assert result.root_cause == "A"

    def test_max_depth_prevents_infinite_loop(self):
        """Max depth prevents excessive chain length."""
        activities = [
            MockTask(task_id=f"T{i}", task_code=f"T{i}", remain_drtn_hr_cnt=8)
            for i in range(200)
        ]
        rels = [
            MockRelationship(task_id=f"T{i+1}", pred_task_id=f"T{i}")
            for i in range(199)
        ]
        schedule = MockSchedule(activities=activities, relationships=rels)
        result = analyze_root_cause(schedule, max_depth=50)
        assert result.chain_length <= 50

    def test_methodology_string(self):
        """Result includes methodology description."""
        schedule = MockSchedule(activities=[MockTask()])
        result = analyze_root_cause(schedule)
        assert "AACE RP 49R-06" in result.methodology

    def test_completed_activities_zero_duration(self):
        """Completed activities have zero duration in the trace."""
        schedule = MockSchedule(
            activities=[
                MockTask(task_id="A", task_code="A", remain_drtn_hr_cnt=80,
                         status_code="TK_Complete"),
                MockTask(task_id="B", task_code="B", remain_drtn_hr_cnt=80),
            ],
            relationships=[
                MockRelationship(task_id="B", pred_task_id="A"),
            ],
        )
        result = analyze_root_cause(schedule, target_task_id="B")
        # A is complete, so its duration should be 0
        a_step = next(s for s in result.chain if s.task_id == "A")
        assert a_step.duration_days == 0.0


# ── API Tests ──


@pytest.fixture(autouse=True)
def clear_store() -> None:
    get_store().clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestRootCauseAPI:
    """Tests for GET /api/v1/projects/{id}/root-cause."""

    def test_root_cause_endpoint(self, client: TestClient) -> None:
        with open(SAMPLE_XER, "rb") as f:
            resp = client.post(
                "/api/v1/upload",
                files={"file": (SAMPLE_XER.name, f, "application/octet-stream")},
            )
        assert resp.status_code == 200
        pid = resp.json()["project_id"]

        resp = client.get(f"/api/v1/projects/{pid}/root-cause")
        assert resp.status_code == 200
        data = resp.json()
        assert "chain" in data
        assert "root_cause" in data
        assert "target_activity" in data
        assert "methodology" in data
        assert data["chain_length"] > 0

    def test_root_cause_with_specific_activity(self, client: TestClient) -> None:
        with open(SAMPLE_XER, "rb") as f:
            resp = client.post(
                "/api/v1/upload",
                files={"file": (SAMPLE_XER.name, f, "application/octet-stream")},
            )
        pid = resp.json()["project_id"]

        # Get first activity from the project
        proj = client.get(f"/api/v1/projects/{pid}").json()
        if proj["activities"]:
            act_id = proj["activities"][0]["task_id"]
            resp = client.get(f"/api/v1/projects/{pid}/root-cause?activity_id={act_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["target_activity"] == act_id

    def test_root_cause_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects/nonexistent/root-cause")
        assert resp.status_code == 404
