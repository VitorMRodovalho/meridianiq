# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for /api/v1/bi/* connector endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_store
from src.parser.models import ParsedSchedule, Project, Relationship, Task


def _schedule(name: str = "BIProj", num_activities: int = 3) -> ParsedSchedule:
    activities = [
        Task(task_id=f"T{i}", task_code=f"A{i:04d}", task_name=f"Act {i}")
        for i in range(1, num_activities + 1)
    ]
    relationships = [Relationship(task_id="T2", pred_task_id="T1")] if num_activities >= 2 else []
    return ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name=name)],
        activities=activities,
        relationships=relationships,
    )


@pytest.fixture(autouse=True)
def clear_store() -> None:
    get_store().clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestBIProjects:
    def test_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/bi/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0
        assert data["pagination"]["has_next"] is False

    def test_single_project_shape(self, client: TestClient) -> None:
        store = get_store()
        store.add(_schedule("Alpha", num_activities=5), b"xer")

        resp = client.get("/api/v1/bi/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total"] == 1
        row = data["items"][0]
        assert row["activity_count"] == 5
        # CPM/DCMA/health fields should be present (may be None if engine fails)
        assert "dcma_score" in row
        assert "health_score" in row
        assert "critical_path_length_days" in row
        assert "negative_float_count" in row

    def test_pagination_limit_and_offset(self, client: TestClient) -> None:
        store = get_store()
        for i in range(5):
            store.add(_schedule(f"P{i}"), b"xer")

        resp = client.get("/api/v1/bi/projects?limit=2&offset=0")
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["has_next"] is True

        resp = client.get("/api/v1/bi/projects?limit=2&offset=4")
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["pagination"]["has_next"] is False

    def test_limit_clamped_by_validator(self, client: TestClient) -> None:
        # limit above max triggers FastAPI validation 422 (max_le=500)
        resp = client.get("/api/v1/bi/projects?limit=9999")
        assert resp.status_code == 422


class TestBIDcmaMetrics:
    def test_empty_with_no_projects(self, client: TestClient) -> None:
        resp = client.get("/api/v1/bi/dcma-metrics")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_returns_14_rows_per_project(self, client: TestClient) -> None:
        store = get_store()
        store.add(_schedule("Alpha", num_activities=10), b"xer")

        resp = client.get("/api/v1/bi/dcma-metrics?limit=50")
        assert resp.status_code == 200
        data = resp.json()
        # One row per DCMA metric (14 metrics in standard assessment)
        assert data["pagination"]["total"] == 14
        row = data["items"][0]
        assert "metric_number" in row
        assert "metric_name" in row
        assert "value" in row
        assert "threshold" in row
        assert "passed" in row
        assert row["project_id"]

    def test_filter_by_project_id_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/bi/dcma-metrics?project_id=nonexistent")
        assert resp.status_code == 404

    def test_filter_by_project_id(self, client: TestClient) -> None:
        store = get_store()
        pid = store.add(_schedule("Alpha", num_activities=5), b"xer")

        resp = client.get(f"/api/v1/bi/dcma-metrics?project_id={pid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total"] == 14
        assert all(row["project_id"] == pid for row in data["items"])


class TestBIActivities:
    def test_404_when_project_missing(self, client: TestClient) -> None:
        resp = client.get("/api/v1/bi/activities?project_id=missing")
        assert resp.status_code == 404

    def test_returns_activity_rows(self, client: TestClient) -> None:
        store = get_store()
        pid = store.add(_schedule("Alpha", num_activities=3), b"xer")

        resp = client.get(f"/api/v1/bi/activities?project_id={pid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == pid
        assert data["pagination"]["total"] == 3
        assert len(data["items"]) == 3
        row = data["items"][0]
        assert "task_id" in row
        assert "task_code" in row
        assert "cpm_total_float" in row
        assert "is_critical" in row

    def test_pagination_window(self, client: TestClient) -> None:
        store = get_store()
        pid = store.add(_schedule("Big", num_activities=20), b"xer")

        resp = client.get(f"/api/v1/bi/activities?project_id={pid}&limit=5&offset=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["pagination"]["total"] == 20
        assert data["pagination"]["offset"] == 10
        assert data["pagination"]["has_next"] is True
