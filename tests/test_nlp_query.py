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


class TestPromptBounds:
    """The prompt's size depends on the question, not on the uploaded file."""

    def test_project_name_is_truncated(self):
        from src.analytics.nlp_query import MAX_PROJECT_NAME_CHARS, build_prompt

        sched = MockSchedule(projects=[MockProject(proj_short_name="N" * 5000)])
        _, message = build_prompt(sched, "q")
        assert "N" * MAX_PROJECT_NAME_CHARS in message
        assert "N" * (MAX_PROJECT_NAME_CHARS + 1) not in message

    def test_unknown_relationship_types_are_grouped(self):
        from src.analytics.nlp_query import _build_schedule_summary

        rels = [MockRelationship(pred_type=f"PR_X{i}") for i in range(500)]
        rels.append(MockRelationship(pred_type="PR_FS"))
        summary = _build_schedule_summary(MockSchedule(relationships=rels))
        assert summary["relationship_types"] == {"other": 500, "PR_FS": 1}

    def test_question_is_the_last_line(self):
        from src.analytics.nlp_query import SYSTEM_PROMPT, build_prompt

        system, message = build_prompt(MockSchedule(), "How many activities?")
        assert system == SYSTEM_PROMPT
        assert message.endswith("\n\nQuestion: How many activities?")


class TestResponseReading:
    """Usage is read without parsing the answer; the answer tolerates odd blocks."""

    def test_usage_and_text(self):
        from src.analytics.nlp_query import ModelUsage, answer_text, usage_of
        from tests.ai_fakes import FakeBlock, FakeResponse, FakeUsage

        resp = FakeResponse(
            content=[FakeBlock("a"), FakeBlock("ignored", type="tool_use"), FakeBlock("b")],
            usage=FakeUsage(input_tokens=10, output_tokens=5, cache_read_input_tokens=2),
        )
        assert usage_of(resp) == ModelUsage(10, 5, 0, 2)
        assert answer_text(resp) == "ab"

    def test_missing_usage_and_content(self):
        from src.analytics.nlp_query import answer_text, usage_of
        from tests.ai_fakes import FakeResponse

        resp = FakeResponse(content=[], usage=None)
        assert usage_of(resp) is None
        assert answer_text(resp) == ""


class TestNLPQueryAPI:
    """POST /api/v1/projects/{id}/ask without a signed-in session.

    The gated behaviour (entitlement, limits, ledger) is covered in
    tests/test_ai_gate.py with real tokens.
    """

    @pytest.fixture(autouse=True)
    def clear(self):
        get_store().clear()

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def _upload(self, client) -> str:
        with open(SAMPLE_XER, "rb") as f:
            resp = client.post("/api/v1/upload", files={"file": ("s.xer", f)})
        return resp.json()["project_id"]

    def test_missing_question_field(self, client):
        pid = self._upload(client)
        resp = client.post(f"/api/v1/projects/{pid}/ask", json={})
        assert resp.status_code == 422

    def test_anonymous_development_caller_is_refused_even_when_ai_is_on(self, client, monkeypatch):
        from tests.ai_fakes import enable_ai

        fake = enable_ai(monkeypatch)
        pid = self._upload(client)
        resp = client.post(f"/api/v1/projects/{pid}/ask", json={"question": "How many?"})
        assert resp.status_code == 403
        assert resp.json()["detail"]["error_code"] == "ai_session_required"
        assert fake.calls == []

    def test_project_not_found(self, client):
        resp = client.post("/api/v1/projects/nonexistent/ask", json={"question": "test"})
        assert resp.status_code == 404
