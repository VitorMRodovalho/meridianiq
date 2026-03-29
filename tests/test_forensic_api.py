# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the forensic analysis API endpoints.

Verifies timeline creation, listing, retrieval, and delay trend data
through the FastAPI test client.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.storage import ProjectStore, TimelineStore

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _reset_stores(monkeypatch):
    """Reset global stores before each test."""
    store = ProjectStore()
    tl_store = TimelineStore()
    monkeypatch.setattr("src.api.app._store", store)
    monkeypatch.setattr("src.api.app._timeline_store", tl_store)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _upload(client: TestClient, filename: str) -> str:
    """Upload a fixture XER file and return the project_id."""
    xer_path = FIXTURES / filename
    with open(xer_path, "rb") as f:
        resp = client.post(
            "/api/v1/upload",
            files={"file": (filename, f, "application/octet-stream")},
        )
    assert resp.status_code == 200, resp.text
    return resp.json()["project_id"]


class TestCreateTimeline:
    """Test POST /api/v1/forensic/create-timeline."""

    def test_create_with_3_projects(self, client):
        """Uploading 3 XERs and creating a timeline should work."""
        p1 = _upload(client, "sample.xer")
        p2 = _upload(client, "sample_update.xer")
        p3 = _upload(client, "sample_update2.xer")

        resp = client.post(
            "/api/v1/forensic/create-timeline",
            json={"project_ids": [p1, p2, p3]},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["timeline_id"].startswith("timeline-")
        assert data["schedule_count"] == 3
        assert len(data["windows"]) == 2
        assert "total_delay_days" in data
        assert "summary" in data

    def test_create_with_2_projects(self, client):
        """Minimum 2 projects should work."""
        p1 = _upload(client, "sample.xer")
        p2 = _upload(client, "sample_update.xer")

        resp = client.post(
            "/api/v1/forensic/create-timeline",
            json={"project_ids": [p1, p2]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["windows"]) == 1

    def test_create_missing_project(self, client):
        """Should return 404 for unknown project ID."""
        p1 = _upload(client, "sample.xer")
        resp = client.post(
            "/api/v1/forensic/create-timeline",
            json={"project_ids": [p1, "proj-9999"]},
        )
        assert resp.status_code == 404

    def test_create_single_project_rejected(self, client):
        """Should return 422 for fewer than 2 projects (validation)."""
        p1 = _upload(client, "sample.xer")
        resp = client.post(
            "/api/v1/forensic/create-timeline",
            json={"project_ids": [p1]},
        )
        assert resp.status_code == 422


class TestListTimelines:
    """Test GET /api/v1/forensic/timelines."""

    def test_empty_list(self, client):
        """Should return empty list when no timelines exist."""
        resp = client.get("/api/v1/forensic/timelines")
        assert resp.status_code == 200
        assert resp.json()["timelines"] == []

    def test_list_after_create(self, client):
        """Should list created timelines."""
        p1 = _upload(client, "sample.xer")
        p2 = _upload(client, "sample_update.xer")
        client.post(
            "/api/v1/forensic/create-timeline",
            json={"project_ids": [p1, p2]},
        )

        resp = client.get("/api/v1/forensic/timelines")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["timelines"]) == 1
        tl = data["timelines"][0]
        assert "timeline_id" in tl
        assert "project_name" in tl
        assert "schedule_count" in tl
        assert "total_delay_days" in tl
        assert "window_count" in tl


class TestGetTimeline:
    """Test GET /api/v1/forensic/timelines/{timeline_id}."""

    def test_get_existing(self, client):
        """Should return full timeline data."""
        p1 = _upload(client, "sample.xer")
        p2 = _upload(client, "sample_update.xer")
        p3 = _upload(client, "sample_update2.xer")

        create_resp = client.post(
            "/api/v1/forensic/create-timeline",
            json={"project_ids": [p1, p2, p3]},
        )
        tid = create_resp.json()["timeline_id"]

        resp = client.get(f"/api/v1/forensic/timelines/{tid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["timeline_id"] == tid
        assert len(data["windows"]) == 2

        # Verify window structure
        w = data["windows"][0]
        assert "window_id" in w
        assert "delay_days" in w
        assert "cumulative_delay" in w
        assert "driving_activity" in w
        assert "comparison_summary" in w

    def test_get_nonexistent(self, client):
        """Should return 404 for unknown timeline."""
        resp = client.get("/api/v1/forensic/timelines/timeline-9999")
        assert resp.status_code == 404


class TestGetDelayTrend:
    """Test GET /api/v1/forensic/timelines/{timeline_id}/delay-trend."""

    def test_trend_data(self, client):
        """Should return trend points matching window count."""
        p1 = _upload(client, "sample.xer")
        p2 = _upload(client, "sample_update.xer")
        p3 = _upload(client, "sample_update2.xer")

        create_resp = client.post(
            "/api/v1/forensic/create-timeline",
            json={"project_ids": [p1, p2, p3]},
        )
        tid = create_resp.json()["timeline_id"]

        resp = client.get(f"/api/v1/forensic/timelines/{tid}/delay-trend")
        assert resp.status_code == 200
        data = resp.json()
        assert data["timeline_id"] == tid
        assert len(data["points"]) == 2

        pt = data["points"][0]
        assert "window_id" in pt
        assert "delay_days" in pt
        assert "cumulative_delay" in pt
        assert "data_date" in pt
        assert "completion_date" in pt

    def test_trend_nonexistent(self, client):
        """Should return 404 for unknown timeline."""
        resp = client.get("/api/v1/forensic/timelines/timeline-9999/delay-trend")
        assert resp.status_code == 404
