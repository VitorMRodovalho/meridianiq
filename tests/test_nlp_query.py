# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for NLP schedule query engine (v2.0).

Tests verify that:
1. Schedule summary builder extracts correct data
2. DCMA summary builder works
3. API endpoint validates inputs correctly
4. Missing API key returns proper error
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.analytics.nlp_query import _build_schedule_summary, _build_dcma_summary
from src.api.app import app, get_store

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XER = FIXTURES / "sample.xer"


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
    relationships: list = field(default_factory=lambda: [MockRelationship()])
    calendars: list = field(default_factory=list)
    wbs_nodes: list = field(default_factory=list)
    task_resources: list = field(default_factory=list)
    parser_version: str = "1.0"


class TestScheduleSummary:
    """Tests for schedule summary builder."""

    def test_empty_schedule(self):
        schedule = MockSchedule(activities=[])
        summary = _build_schedule_summary(schedule)
        assert summary["total_activities"] == 0
        assert summary["completion_pct"] == 0

    def test_summary_counts(self):
        activities = [
            MockTask(task_id="1", status_code="TK_Complete"),
            MockTask(task_id="2", status_code="TK_Active"),
            MockTask(task_id="3", status_code="TK_NotStart"),
        ]
        schedule = MockSchedule(activities=activities)
        summary = _build_schedule_summary(schedule)
        assert summary["total_activities"] == 3
        assert summary["complete"] == 1
        assert summary["in_progress"] == 1
        assert summary["not_started"] == 1
        assert summary["completion_pct"] == pytest.approx(33.3, abs=0.1)

    def test_float_stats(self):
        activities = [
            MockTask(task_id="1", total_float_hr_cnt=0.0),
            MockTask(task_id="2", total_float_hr_cnt=-16.0),
            MockTask(task_id="3", total_float_hr_cnt=400.0),
        ]
        schedule = MockSchedule(activities=activities)
        summary = _build_schedule_summary(schedule)
        assert summary["critical_activities"] == 1
        assert summary["negative_float_activities"] == 1
        assert summary["high_float_activities"] == 1

    def test_relationship_types(self):
        rels = [
            MockRelationship(pred_type="PR_FS"),
            MockRelationship(pred_type="PR_FS"),
            MockRelationship(pred_type="PR_SS"),
        ]
        schedule = MockSchedule(relationships=rels)
        summary = _build_schedule_summary(schedule)
        assert summary["relationship_types"]["PR_FS"] == 2
        assert summary["relationship_types"]["PR_SS"] == 1

    def test_project_name(self):
        schedule = MockSchedule()
        summary = _build_schedule_summary(schedule)
        assert summary["project_name"] == "Test"


class TestDCMASummary:
    """Tests for DCMA summary builder with real XER."""

    def test_dcma_with_sample_xer(self):
        from src.parser.xer_reader import XERReader

        reader = XERReader(SAMPLE_XER)
        schedule = reader.parse()
        dcma = _build_dcma_summary(schedule)
        assert dcma is not None
        assert "overall_score" in dcma
        assert "passed" in dcma
        assert "failed" in dcma
        assert dcma["passed"] + dcma["failed"] == 14


class TestNLPQueryAPI:
    """Tests for POST /api/v1/projects/{id}/ask."""

    @pytest.fixture(autouse=True)
    def clear(self):
        get_store().clear()

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_missing_question(self, client):
        with open(SAMPLE_XER, "rb") as f:
            resp = client.post("/api/v1/upload", files={"file": ("s.xer", f)})
        pid = resp.json()["project_id"]

        resp = client.post(f"/api/v1/projects/{pid}/ask", json={})
        assert resp.status_code == 400
        assert "question" in resp.json()["detail"]

    def test_missing_api_key(self, client):
        import os
        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with open(SAMPLE_XER, "rb") as f:
                resp = client.post("/api/v1/upload", files={"file": ("s.xer", f)})
            pid = resp.json()["project_id"]

            resp = client.post(
                f"/api/v1/projects/{pid}/ask",
                json={"question": "How many activities?"},
            )
            assert resp.status_code == 400
            assert "API key" in resp.json()["detail"]
        finally:
            if old:
                os.environ["ANTHROPIC_API_KEY"] = old

    def test_project_not_found(self, client):
        resp = client.post(
            "/api/v1/projects/nonexistent/ask",
            json={"question": "test"},
        )
        assert resp.status_code == 404
