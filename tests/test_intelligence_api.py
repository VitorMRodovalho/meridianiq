# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the Intelligence v0.8 API endpoints."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import app, get_store

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XER = FIXTURES / "sample.xer"
SAMPLE_UPDATE_XER = FIXTURES / "sample_update.xer"


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest.fixture(scope="module")
def uploaded_ids(client: TestClient) -> dict[str, str]:
    """Upload baseline and update XER files and return their IDs."""
    ids = {}

    with open(SAMPLE_XER, "rb") as f:
        resp = client.post("/api/v1/upload", files={"file": ("sample.xer", f)})
        assert resp.status_code == 200
        ids["baseline"] = resp.json()["project_id"]

    with open(SAMPLE_UPDATE_XER, "rb") as f:
        resp = client.post("/api/v1/upload", files={"file": ("sample_update.xer", f)})
        assert resp.status_code == 200
        ids["update"] = resp.json()["project_id"]

    return ids


class TestHealthEndpoint:
    """Tests for GET /api/v1/projects/{id}/health."""

    def test_health_score_basic(self, client: TestClient, uploaded_ids: dict[str, str]) -> None:
        """Health score should return valid response for a single project."""
        resp = client.get(f"/api/v1/projects/{uploaded_ids['baseline']}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert 0 <= data["overall"] <= 100
        assert data["rating"] in ("excellent", "good", "fair", "poor")
        assert data["trend_arrow"] in ("↑", "→", "↓")

    def test_health_score_with_baseline(
        self, client: TestClient, uploaded_ids: dict[str, str]
    ) -> None:
        """Health score with baseline should include trend analysis."""
        resp = client.get(
            f"/api/v1/projects/{uploaded_ids['update']}/health"
            f"?baseline_id={uploaded_ids['baseline']}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["details"]["has_baseline"] is True

    def test_health_score_not_found(self, client: TestClient) -> None:
        """Non-existent project should return 404."""
        resp = client.get("/api/v1/projects/nonexistent/health")
        assert resp.status_code == 404


class TestAlertsEndpoint:
    """Tests for GET /api/v1/projects/{id}/alerts."""

    def test_alerts_require_baseline(
        self, client: TestClient, uploaded_ids: dict[str, str]
    ) -> None:
        """Alerts endpoint should require baseline_id parameter."""
        resp = client.get(f"/api/v1/projects/{uploaded_ids['update']}/alerts")
        assert resp.status_code == 400

    def test_alerts_with_baseline(
        self, client: TestClient, uploaded_ids: dict[str, str]
    ) -> None:
        """Alerts should return valid response with baseline."""
        resp = client.get(
            f"/api/v1/projects/{uploaded_ids['update']}/alerts"
            f"?baseline_id={uploaded_ids['baseline']}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data
        assert "total_alerts" in data
        assert data["total_alerts"] >= 0
        # Should have at least some alerts given the sample schedules differ
        assert data["total_alerts"] > 0


class TestDashboardEndpoint:
    """Tests for GET /api/v1/dashboard."""

    def test_dashboard_kpis(self, client: TestClient, uploaded_ids: dict[str, str]) -> None:
        """Dashboard should return portfolio KPIs."""
        resp = client.get("/api/v1/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_projects"] >= 2
        assert 0 <= data["avg_health_score"] <= 100
