# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for GET /api/v1/projects/{project_id}/activities (P4)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import app, get_store

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XER = FIXTURES / "sample.xer"


@pytest.fixture(autouse=True)
def clear_store() -> None:
    """Clear in-memory store before each test."""
    get_store().clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def project_id(client: TestClient) -> str:
    """Upload sample.xer and return its project_id."""
    with open(SAMPLE_XER, "rb") as f:
        resp = client.post(
            "/api/v1/upload",
            files={"file": ("sample.xer", f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    return resp.json()["project_id"]


class TestActivitySearch:
    """Tests for the activities search endpoint."""

    def test_search_by_code(self, client: TestClient, project_id: str) -> None:
        """Searching by task_code prefix returns matching activities."""
        resp = client.get(f"/api/v1/projects/{project_id}/activities?q=A10")
        assert resp.status_code == 200
        data = resp.json()

        assert "activities" in data
        assert "total" in data
        assert data["total"] > 0  # sanity: there are activities in total

        # Every returned activity must contain the query string
        for act in data["activities"]:
            searchable = f"{act['task_code']} {act['task_name']}".lower()
            assert "a10" in searchable

    def test_search_by_name(self, client: TestClient, project_id: str) -> None:
        """Searching by a substring of task_name returns matching activities."""
        # First collect all activity names to find a real substring
        resp_all = client.get(f"/api/v1/projects/{project_id}/activities?limit=100")
        assert resp_all.status_code == 200
        all_acts = resp_all.json()["activities"]
        assert len(all_acts) > 0

        # Pick the first three characters of the first activity name
        sample_name = all_acts[0]["task_name"]
        query = sample_name[:4] if len(sample_name) >= 4 else sample_name

        resp = client.get(
            f"/api/v1/projects/{project_id}/activities?q={query}&limit=50"
        )
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["activities"]) >= 1
        for act in data["activities"]:
            searchable = f"{act['task_code']} {act['task_name']}".lower()
            assert query.lower() in searchable

    def test_search_limit(self, client: TestClient, project_id: str) -> None:
        """limit=5 must return at most 5 activities."""
        resp = client.get(f"/api/v1/projects/{project_id}/activities?limit=5")
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["activities"]) <= 5
        # total should reflect all activities, not just the page
        assert data["total"] >= len(data["activities"])

    def test_search_empty(self, client: TestClient, project_id: str) -> None:
        """Empty query returns the first N activities (up to limit)."""
        resp = client.get(f"/api/v1/projects/{project_id}/activities?limit=10")
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["activities"]) <= 10
        assert data["total"] == 30  # sample.xer has 30 activities

        # Each activity must have the required fields
        for act in data["activities"]:
            assert "task_code" in act
            assert "task_name" in act
            assert "task_type" in act
            assert "wbs_id" in act
            assert "status_code" in act

    def test_search_not_found(self, client: TestClient) -> None:
        """Non-existent project must return 404."""
        resp = client.get("/api/v1/projects/nonexistent/activities?q=A10")
        assert resp.status_code == 404

    def test_search_no_results(self, client: TestClient, project_id: str) -> None:
        """Query that matches nothing returns empty list, total unchanged."""
        resp = client.get(
            f"/api/v1/projects/{project_id}/activities?q=ZZZNOMATCH999"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["activities"] == []
        assert data["total"] == 30
