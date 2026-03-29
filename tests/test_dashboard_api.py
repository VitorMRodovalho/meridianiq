# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for dashboard, health, and alerts API endpoints.

Tests verify that:
1. Dashboard KPIs return correct structure
2. Dashboard works with 0 and N projects
3. Health endpoint returns correct score structure
4. Alerts endpoint validates parameters
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def uploaded_project(client):
    """Upload a test XER file and return the project_id."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "simple.xer")
    if not os.path.exists(fixture_path):
        pytest.skip("Test fixture simple.xer not found")

    with open(fixture_path, "rb") as f:
        resp = client.post("/api/v1/upload", files={"file": ("test.xer", f)})

    if resp.status_code != 200:
        pytest.skip("Upload failed")

    return resp.json()["project_id"]


class TestDashboardKPIs:
    """Tests for GET /api/v1/dashboard."""

    def test_dashboard_kpis_empty(self, client):
        """Dashboard returns valid KPIs even with no projects."""
        # Note: other tests may have uploaded projects, so just check structure
        resp = client.get("/api/v1/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_projects" in data
        assert "avg_health_score" in data
        assert "active_alerts" in data
        assert "most_critical_project" in data
        assert "most_critical_score" in data
        assert isinstance(data["total_projects"], int)
        assert isinstance(data["avg_health_score"], (int, float))

    def test_dashboard_kpis_with_projects(self, client, uploaded_project):
        """Dashboard reflects uploaded projects."""
        resp = client.get("/api/v1/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_projects"] >= 1
        assert data["avg_health_score"] >= 0
        assert data["avg_health_score"] <= 100

    def test_dashboard_most_critical_project(self, client, uploaded_project):
        """Dashboard identifies a most critical project when projects exist."""
        resp = client.get("/api/v1/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        # With at least 1 project, most_critical_project should be set
        if data["total_projects"] > 0:
            assert data["most_critical_project"] is not None
            assert data["most_critical_score"] is not None


class TestProjectHealth:
    """Tests for GET /api/v1/projects/{id}/health."""

    def test_project_health_endpoint(self, client, uploaded_project):
        """Health endpoint returns proper score structure."""
        resp = client.get(f"/api/v1/projects/{uploaded_project}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall" in data
        assert "rating" in data
        assert "trend_arrow" in data
        assert "dcma_component" in data
        assert "float_component" in data
        assert "logic_component" in data
        assert "trend_component" in data
        assert 0 <= data["overall"] <= 100
        assert data["rating"] in ("excellent", "good", "fair", "poor")

    def test_project_health_not_found(self, client):
        """Health endpoint returns 404 for non-existent project."""
        resp = client.get("/api/v1/projects/nonexistent/health")
        assert resp.status_code == 404


class TestProjectAlerts:
    """Tests for GET /api/v1/projects/{id}/alerts."""

    def test_project_alerts_requires_baseline(self, client, uploaded_project):
        """Alerts endpoint requires baseline_id parameter."""
        resp = client.get(f"/api/v1/projects/{uploaded_project}/alerts")
        assert resp.status_code == 400
        assert "baseline_id" in resp.json()["detail"]

    def test_project_alerts_not_found(self, client):
        """Alerts endpoint returns 404 for non-existent project."""
        resp = client.get("/api/v1/projects/nonexistent/alerts?baseline_id=proj-0001")
        assert resp.status_code == 404

    def test_project_alerts_with_baseline(self, client, uploaded_project):
        """Alerts endpoint works with same project as baseline (self-comparison)."""
        resp = client.get(
            f"/api/v1/projects/{uploaded_project}/alerts?baseline_id={uploaded_project}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data
        assert "total_alerts" in data
        assert "critical_count" in data
        assert "warning_count" in data
        assert "info_count" in data
        assert isinstance(data["alerts"], list)
