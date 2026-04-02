# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for novel schedule metrics (v1.2): float entropy and constraint accumulation rate.

Tests verify that:
1. Float entropy computes correctly for known distributions
2. Constraint accumulation rate detects added/removed constraints
3. API endpoints return expected structures
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.analytics.float_trends import (
    compute_float_entropy,
    compute_constraint_accumulation,
)
from src.api.app import app, get_store

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XER = FIXTURES / "sample.xer"
SAMPLE_UPDATE_XER = FIXTURES / "sample_update.xer"


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
    total_float_hr_cnt: float = 40.0
    remain_drtn_hr_cnt: float = 80.0
    target_drtn_hr_cnt: float = 160.0
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
    relationships: list = field(default_factory=lambda: [MockRelationship()])
    calendars: list = field(default_factory=list)
    wbs_nodes: list = field(default_factory=list)
    task_resources: list = field(default_factory=list)
    parser_version: str = "1.0"


# ── Float Entropy Tests ──


class TestFloatEntropy:
    """Tests for Shannon float entropy calculation."""

    def test_empty_schedule(self):
        """Empty schedule returns zero entropy."""
        schedule = MockSchedule(activities=[])
        result = compute_float_entropy(schedule)
        assert result.entropy == 0.0
        assert result.total_activities == 0

    def test_single_bucket_zero_entropy(self):
        """All activities in one float bucket should give zero entropy."""
        # All activities with float=40h (near-critical bucket)
        activities = [
            MockTask(task_id=f"A{i}", task_code=f"A{i}", total_float_hr_cnt=40.0)
            for i in range(10)
        ]
        schedule = MockSchedule(activities=activities)
        result = compute_float_entropy(schedule)
        assert result.entropy == 0.0
        assert result.normalised_entropy == 0.0
        assert result.bucket_count == 1

    def test_two_equal_buckets(self):
        """Two equally populated buckets should give entropy = 1.0 bit."""
        activities = []
        # 5 critical (float=0)
        for i in range(5):
            activities.append(
                MockTask(task_id=f"C{i}", task_code=f"C{i}", total_float_hr_cnt=0.0)
            )
        # 5 near-critical (float=40h)
        for i in range(5):
            activities.append(
                MockTask(task_id=f"N{i}", task_code=f"N{i}", total_float_hr_cnt=40.0)
            )
        schedule = MockSchedule(activities=activities)
        result = compute_float_entropy(schedule)
        assert abs(result.entropy - 1.0) < 0.01
        assert result.bucket_count == 2

    def test_uniform_distribution_max_entropy(self):
        """Uniform distribution across all 6 buckets gives maximum normalised entropy."""
        activities = []
        # 2 per bucket: negative, critical, near-crit, moderate, high, excessive
        floats = [-10.0, 0.0, 40.0, 120.0, 200.0, 400.0]
        for i, tf in enumerate(floats):
            activities.append(
                MockTask(task_id=f"T{i}a", task_code=f"T{i}a", total_float_hr_cnt=tf)
            )
            activities.append(
                MockTask(task_id=f"T{i}b", task_code=f"T{i}b", total_float_hr_cnt=tf)
            )
        schedule = MockSchedule(activities=activities)
        result = compute_float_entropy(schedule)
        assert abs(result.normalised_entropy - 1.0) < 0.01
        assert result.bucket_count == 6

    def test_excludes_loe_and_complete(self):
        """LOE and complete activities should be excluded."""
        activities = [
            MockTask(task_id="T1", task_code="T1", total_float_hr_cnt=40.0),
            MockTask(
                task_id="L1", task_code="L1",
                task_type="TT_LOE", total_float_hr_cnt=40.0,
            ),
            MockTask(
                task_id="C1", task_code="C1",
                status_code="TK_Complete", total_float_hr_cnt=0.0,
            ),
        ]
        schedule = MockSchedule(activities=activities)
        result = compute_float_entropy(schedule)
        assert result.total_activities == 1

    def test_interpretation_low(self):
        """Low entropy should get concentration interpretation."""
        activities = [
            MockTask(task_id=f"T{i}", task_code=f"T{i}", total_float_hr_cnt=40.0)
            for i in range(10)
        ]
        schedule = MockSchedule(activities=activities)
        result = compute_float_entropy(schedule)
        assert "concentrated" in result.interpretation.lower()

    def test_interpretation_high(self):
        """High entropy should get spread interpretation."""
        floats = [-10.0, 0.0, 40.0, 120.0, 200.0, 400.0]
        activities = [
            MockTask(task_id=f"T{i}", task_code=f"T{i}", total_float_hr_cnt=tf)
            for i, tf in enumerate(floats)
        ]
        schedule = MockSchedule(activities=activities)
        result = compute_float_entropy(schedule)
        assert "spread" in result.interpretation.lower()

    def test_distribution_keys(self):
        """Distribution dict should contain all bucket keys."""
        activities = [MockTask(total_float_hr_cnt=40.0)]
        schedule = MockSchedule(activities=activities)
        result = compute_float_entropy(schedule)
        assert "negative" in result.distribution
        assert "critical" in result.distribution
        assert "near_critical_0_10d" in result.distribution


# ── Constraint Accumulation Tests ──


class TestConstraintAccumulation:
    """Tests for constraint accumulation rate calculation."""

    def test_no_constraints(self):
        """Two schedules with no constraints should show zero change."""
        baseline = MockSchedule(activities=[
            MockTask(task_id="A1", task_code="A1"),
        ])
        update = MockSchedule(
            projects=[MockProject(last_recalc_date=datetime(2026, 4, 1))],
            activities=[MockTask(task_id="A1", task_code="A1")],
        )
        result = compute_constraint_accumulation(baseline, update)
        assert result.added == 0
        assert result.removed == 0
        assert result.net_change == 0

    def test_constraint_added(self):
        """Adding a constraint should be detected."""
        baseline = MockSchedule(activities=[
            MockTask(task_id="A1", task_code="A1", cstr_type=""),
        ])
        update = MockSchedule(
            projects=[MockProject(last_recalc_date=datetime(2026, 4, 1))],
            activities=[
                MockTask(task_id="A1", task_code="A1", cstr_type="CS_MSO"),
            ],
        )
        result = compute_constraint_accumulation(baseline, update)
        assert result.added == 1
        assert result.net_change == 1
        assert "A1" in result.added_activities

    def test_constraint_removed(self):
        """Removing a constraint should be detected."""
        baseline = MockSchedule(activities=[
            MockTask(task_id="A1", task_code="A1", cstr_type="CS_MSOA"),
        ])
        update = MockSchedule(
            projects=[MockProject(last_recalc_date=datetime(2026, 4, 1))],
            activities=[
                MockTask(task_id="A1", task_code="A1", cstr_type=""),
            ],
        )
        result = compute_constraint_accumulation(baseline, update)
        assert result.removed == 1
        assert result.net_change == -1

    def test_rate_per_day(self):
        """Rate should be net_change / days_between."""
        baseline = MockSchedule(
            projects=[MockProject(last_recalc_date=datetime(2026, 3, 1))],
            activities=[
                MockTask(task_id="A1", task_code="A1", cstr_type=""),
                MockTask(task_id="A2", task_code="A2", cstr_type=""),
            ],
        )
        update = MockSchedule(
            projects=[MockProject(last_recalc_date=datetime(2026, 4, 1))],
            activities=[
                MockTask(task_id="A1", task_code="A1", cstr_type="CS_MSO"),
                MockTask(task_id="A2", task_code="A2", cstr_type="CS_MEOA"),
            ],
        )
        result = compute_constraint_accumulation(baseline, update)
        assert result.added == 2
        # ~31 days between March 1 and April 1
        assert result.rate_per_day > 0
        assert abs(result.rate_per_day - 2 / 31) < 0.01

    def test_constraint_percentages(self):
        """Constraint percentages should be calculated correctly."""
        baseline = MockSchedule(activities=[
            MockTask(task_id="A1", task_code="A1", cstr_type="CS_MSO"),
            MockTask(task_id="A2", task_code="A2"),
        ])
        update = MockSchedule(
            projects=[MockProject(last_recalc_date=datetime(2026, 4, 1))],
            activities=[
                MockTask(task_id="A1", task_code="A1", cstr_type="CS_MSO"),
                MockTask(task_id="A2", task_code="A2", cstr_type="CS_MEOB"),
            ],
        )
        result = compute_constraint_accumulation(baseline, update)
        assert result.baseline_constraint_pct == 50.0
        assert result.update_constraint_pct == 100.0

    def test_interpretation_stable(self):
        """No growth should give stable interpretation."""
        baseline = MockSchedule(activities=[MockTask(task_code="A1")])
        update = MockSchedule(
            projects=[MockProject(last_recalc_date=datetime(2026, 4, 1))],
            activities=[MockTask(task_code="A1")],
        )
        result = compute_constraint_accumulation(baseline, update)
        assert "stable" in result.interpretation.lower()

    def test_interpretation_significant(self):
        """Many constraints added should flag manipulation."""
        activities_base = [
            MockTask(task_id=f"A{i}", task_code=f"A{i}")
            for i in range(15)
        ]
        activities_upd = [
            MockTask(task_id=f"A{i}", task_code=f"A{i}", cstr_type="CS_MSO")
            for i in range(15)
        ]
        baseline = MockSchedule(activities=activities_base)
        update = MockSchedule(
            projects=[MockProject(last_recalc_date=datetime(2026, 4, 1))],
            activities=activities_upd,
        )
        result = compute_constraint_accumulation(baseline, update)
        assert result.net_change == 15
        assert "manipulation" in result.interpretation.lower()

    def test_cstr_type2_detected(self):
        """Constraints in cstr_type2 field should also be detected."""
        baseline = MockSchedule(activities=[
            MockTask(task_code="A1", cstr_type="", cstr_type2=""),
        ])
        update = MockSchedule(
            projects=[MockProject(last_recalc_date=datetime(2026, 4, 1))],
            activities=[
                MockTask(task_code="A1", cstr_type="", cstr_type2="CS_MANDFIN"),
            ],
        )
        result = compute_constraint_accumulation(baseline, update)
        assert result.added == 1


# ── API Tests ──


@pytest.fixture(autouse=True)
def clear_store() -> None:
    get_store().clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _upload(client: TestClient, path: Path) -> str:
    with open(path, "rb") as f:
        resp = client.post(
            "/api/v1/upload",
            files={"file": (path.name, f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    return resp.json()["project_id"]


class TestFloatEntropyAPI:
    """Tests for GET /api/v1/projects/{id}/float-entropy."""

    def test_float_entropy_endpoint(self, client: TestClient) -> None:
        pid = _upload(client, SAMPLE_XER)
        resp = client.get(f"/api/v1/projects/{pid}/float-entropy")
        assert resp.status_code == 200
        data = resp.json()
        assert "entropy" in data
        assert "normalised_entropy" in data
        assert "distribution" in data
        assert "interpretation" in data
        assert 0 <= data["normalised_entropy"] <= 1.0

    def test_float_entropy_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects/nonexistent/float-entropy")
        assert resp.status_code == 404


class TestConstraintAccumulationAPI:
    """Tests for GET /api/v1/projects/{id}/constraint-accumulation."""

    def test_constraint_accumulation_requires_baseline(self, client: TestClient) -> None:
        pid = _upload(client, SAMPLE_XER)
        resp = client.get(f"/api/v1/projects/{pid}/constraint-accumulation")
        assert resp.status_code == 400

    def test_constraint_accumulation_with_baseline(self, client: TestClient) -> None:
        if not SAMPLE_UPDATE_XER.exists():
            pytest.skip("sample_update.xer not available")
        pid1 = _upload(client, SAMPLE_XER)
        pid2 = _upload(client, SAMPLE_UPDATE_XER)
        resp = client.get(
            f"/api/v1/projects/{pid2}/constraint-accumulation?baseline_id={pid1}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "added" in data
        assert "removed" in data
        assert "net_change" in data
        assert "rate_per_day" in data
        assert "interpretation" in data

    def test_constraint_accumulation_not_found(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/projects/nonexistent/constraint-accumulation?baseline_id=x"
        )
        assert resp.status_code == 404
