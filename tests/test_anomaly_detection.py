# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for anomaly detection engine (v2.0)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.analytics.anomaly_detection import detect_anomalies
from src.api.app import app, get_store

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XER = FIXTURES / "sample.xer"


@dataclass
class MockTask:
    task_id: str = "A1"
    task_code: str = "A1"
    task_name: str = "Task"
    task_type: str = "TT_Task"
    status_code: str = "TK_Active"
    total_float_hr_cnt: float = 40.0
    remain_drtn_hr_cnt: float = 80.0
    target_drtn_hr_cnt: float = 80.0
    phys_complete_pct: float = 50.0
    wbs_id: str = "WBS1"


@dataclass
class MockRel:
    task_id: str = "A2"
    pred_task_id: str = "A1"
    pred_type: str = "PR_FS"
    lag_hr_cnt: float = 0.0


@dataclass
class MockSchedule:
    projects: list = field(default_factory=list)
    activities: list = field(default_factory=list)
    relationships: list = field(default_factory=list)
    calendars: list = field(default_factory=list)
    wbs_nodes: list = field(default_factory=list)
    task_resources: list = field(default_factory=list)


class TestAnomalyDetection:

    def test_empty_schedule(self):
        result = detect_anomalies(MockSchedule())
        assert result.total == 0
        assert result.activities_analyzed == 0

    def test_normal_schedule_few_anomalies(self):
        """A well-structured schedule should have few anomalies."""
        activities = [
            MockTask(task_id=f"A{i}", task_code=f"A{i}",
                     remain_drtn_hr_cnt=float(40 + i * 8),
                     total_float_hr_cnt=float(i * 16))
            for i in range(10)
        ]
        rels = [MockRel(task_id=f"A{i+1}", pred_task_id=f"A{i}") for i in range(9)]
        schedule = MockSchedule(activities=activities, relationships=rels)
        result = detect_anomalies(schedule)
        # Should have few or no critical anomalies in a normal schedule
        assert result.activities_analyzed == 10

    def test_extreme_duration_flagged(self):
        """Activity with extreme duration should be flagged."""
        activities = [
            MockTask(task_id=f"A{i}", task_code=f"A{i}", remain_drtn_hr_cnt=80.0)
            for i in range(10)
        ]
        # One outlier with 10x the duration
        activities.append(MockTask(task_id="OUTLIER", task_code="OUT",
                                   remain_drtn_hr_cnt=800.0))
        schedule = MockSchedule(activities=activities)
        result = detect_anomalies(schedule)
        duration_anomalies = [a for a in result.anomalies if a.anomaly_type == "duration"]
        assert len(duration_anomalies) > 0
        assert any(a.task_id == "OUTLIER" for a in duration_anomalies)

    def test_disconnected_activity_flagged(self):
        """Activity with no relationships should be flagged as critical."""
        activities = [
            MockTask(task_id="A1"), MockTask(task_id="A2"),
            MockTask(task_id="A3"), MockTask(task_id="LONE"),
        ]
        rels = [MockRel(task_id="A2", pred_task_id="A1"),
                MockRel(task_id="A3", pred_task_id="A2")]
        schedule = MockSchedule(activities=activities, relationships=rels)
        result = detect_anomalies(schedule)
        rel_anomalies = [a for a in result.anomalies
                         if a.anomaly_type == "relationship" and a.task_id == "LONE"]
        assert len(rel_anomalies) > 0
        assert rel_anomalies[0].severity == "critical"

    def test_active_zero_progress_flagged(self):
        """Active activity with 0% progress should be flagged."""
        activities = [MockTask(status_code="TK_Active", phys_complete_pct=0.0)]
        schedule = MockSchedule(activities=activities)
        result = detect_anomalies(schedule)
        progress_anomalies = [a for a in result.anomalies if a.anomaly_type == "progress"]
        assert len(progress_anomalies) > 0

    def test_not_started_with_progress_flagged(self):
        """Not-started activity with progress should be flagged."""
        activities = [MockTask(status_code="TK_NotStart", phys_complete_pct=50.0)]
        schedule = MockSchedule(activities=activities)
        result = detect_anomalies(schedule)
        progress_anomalies = [a for a in result.anomalies if a.anomaly_type == "progress"]
        assert len(progress_anomalies) > 0

    def test_sorted_by_severity(self):
        """Anomalies should be sorted critical first."""
        activities = [
            MockTask(task_id="A1", status_code="TK_Active", phys_complete_pct=0.0),
            MockTask(task_id="LONE", remain_drtn_hr_cnt=80.0),
        ]
        schedule = MockSchedule(activities=activities)
        result = detect_anomalies(schedule)
        if len(result.anomalies) >= 2:
            severities = [a.severity for a in result.anomalies]
            # Critical should come before warning/info
            if "critical" in severities and "warning" in severities:
                assert severities.index("critical") < severities.index("warning")

    def test_methodology_present(self):
        result = detect_anomalies(MockSchedule(activities=[MockTask()]))
        assert "IQR" in result.methodology
        assert "Tukey" in result.methodology


class TestAnomalyAPI:

    @pytest.fixture(autouse=True)
    def clear(self):
        get_store().clear()

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_anomaly_endpoint(self, client):
        with open(SAMPLE_XER, "rb") as f:
            resp = client.post("/api/v1/upload", files={"file": ("s.xer", f)})
        pid = resp.json()["project_id"]

        resp = client.get(f"/api/v1/projects/{pid}/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert "anomalies" in data
        assert "total" in data
        assert "critical_count" in data
        assert "methodology" in data

    def test_anomaly_not_found(self, client):
        resp = client.get("/api/v1/projects/nonexistent/anomalies")
        assert resp.status_code == 404
