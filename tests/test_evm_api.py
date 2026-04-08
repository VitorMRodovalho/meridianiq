# MIT License
# Copyright (c) 2025 Vitor Maia Rodovalho
"""Tests for EVM API endpoints.

Verifies the REST API for running EVM analyses, fetching results,
S-curve data, WBS drilldowns, and forecast scenarios.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.storage import EVMStore, ProjectStore
from tests.fixtures.sample_xer_generator import generate_sample_xer


@pytest.fixture()
def client():
    """Create a test client with fresh stores."""
    import src.api.deps as deps_module

    test_store = ProjectStore()
    test_evm_store = EVMStore()

    original_store = deps_module._store
    original_evm_store = deps_module._evm_store

    deps_module._store = test_store
    deps_module._evm_store = test_evm_store

    yield TestClient(app)

    deps_module._store = original_store
    deps_module._evm_store = original_evm_store


@pytest.fixture()
def uploaded_project(client: TestClient) -> str:
    """Upload the sample XER and return its project_id."""
    with tempfile.TemporaryDirectory() as tmpdir:
        xer_path = generate_sample_xer(Path(tmpdir) / "sample.xer")
        xer_bytes = xer_path.read_bytes()

    resp = client.post(
        "/api/v1/upload",
        files={"file": ("sample.xer", xer_bytes, "application/octet-stream")},
    )
    assert resp.status_code == 200
    return resp.json()["project_id"]


class TestRunEVMAnalysis:
    """Test POST /api/v1/evm/analyze/{project_id}."""

    def test_run_evm_analysis(self, client: TestClient, uploaded_project: str) -> None:
        """Running EVM analysis returns valid metrics."""
        resp = client.post(f"/api/v1/evm/analyze/{uploaded_project}")
        assert resp.status_code == 200

        data = resp.json()
        assert "analysis_id" in data
        assert data["project_name"] == "Sample Construction"
        assert data["metrics"]["bac"] > 0
        assert "schedule_health" in data
        assert "cost_health" in data
        assert data["schedule_health"]["status"] in ("good", "watch", "critical")

    def test_run_evm_not_found(self, client: TestClient) -> None:
        """Running EVM on missing project returns 404."""
        resp = client.post("/api/v1/evm/analyze/nonexistent")
        assert resp.status_code == 404


class TestGetSCurve:
    """Test GET /api/v1/evm/analyses/{id}/s-curve."""

    def test_get_s_curve(self, client: TestClient, uploaded_project: str) -> None:
        """S-curve endpoint returns time-phased data."""
        # Run analysis first
        resp = client.post(f"/api/v1/evm/analyze/{uploaded_project}")
        aid = resp.json()["analysis_id"]

        resp = client.get(f"/api/v1/evm/analyses/{aid}/s-curve")
        assert resp.status_code == 200

        data = resp.json()
        assert data["analysis_id"] == aid
        assert len(data["points"]) > 0
        # Each point should have all three cumulative values
        point = data["points"][0]
        assert "date" in point
        assert "cumulative_pv" in point
        assert "cumulative_ev" in point
        assert "cumulative_ac" in point

    def test_get_s_curve_not_found(self, client: TestClient) -> None:
        """S-curve for missing analysis returns 404."""
        resp = client.get("/api/v1/evm/analyses/nonexistent/s-curve")
        assert resp.status_code == 404


class TestGetWBSDrill:
    """Test GET /api/v1/evm/analyses/{id}/wbs-drill."""

    def test_get_wbs_drill(self, client: TestClient, uploaded_project: str) -> None:
        """WBS drill endpoint returns per-WBS metrics."""
        resp = client.post(f"/api/v1/evm/analyze/{uploaded_project}")
        aid = resp.json()["analysis_id"]

        resp = client.get(f"/api/v1/evm/analyses/{aid}/wbs-drill")
        assert resp.status_code == 200

        data = resp.json()
        assert data["analysis_id"] == aid
        assert len(data["wbs_breakdown"]) > 0
        wbs = data["wbs_breakdown"][0]
        assert "wbs_id" in wbs
        assert "wbs_name" in wbs
        assert "metrics" in wbs
        assert "bac" in wbs["metrics"]
        assert "spi" in wbs["metrics"]
        assert "cpi" in wbs["metrics"]


class TestGetForecast:
    """Test GET /api/v1/evm/analyses/{id}/forecast."""

    def test_get_forecast(self, client: TestClient, uploaded_project: str) -> None:
        """Forecast endpoint returns all EAC scenarios."""
        resp = client.post(f"/api/v1/evm/analyze/{uploaded_project}")
        aid = resp.json()["analysis_id"]

        resp = client.get(f"/api/v1/evm/analyses/{aid}/forecast")
        assert resp.status_code == 200

        data = resp.json()
        assert data["analysis_id"] == aid
        assert "bac" in data
        assert "eac_cpi" in data
        assert "eac_combined" in data
        assert "etc" in data
        assert "vac" in data
        assert "tcpi" in data

    def test_get_forecast_not_found(self, client: TestClient) -> None:
        """Forecast for missing analysis returns 404."""
        resp = client.get("/api/v1/evm/analyses/nonexistent/forecast")
        assert resp.status_code == 404


class TestListEVMAnalyses:
    """Test GET /api/v1/evm/analyses."""

    def test_list_empty(self, client: TestClient) -> None:
        """Empty list returned when no analyses exist."""
        resp = client.get("/api/v1/evm/analyses")
        assert resp.status_code == 200
        assert resp.json()["analyses"] == []

    def test_list_after_analysis(self, client: TestClient, uploaded_project: str) -> None:
        """List includes analysis after running one."""
        client.post(f"/api/v1/evm/analyze/{uploaded_project}")

        resp = client.get("/api/v1/evm/analyses")
        assert resp.status_code == 200
        analyses = resp.json()["analyses"]
        assert len(analyses) == 1
        assert analyses[0]["project_name"] == "Sample Construction"


class TestGetEVMAnalysis:
    """Test GET /api/v1/evm/analyses/{id}."""

    def test_get_full_analysis(self, client: TestClient, uploaded_project: str) -> None:
        """Get full analysis returns all sections."""
        resp = client.post(f"/api/v1/evm/analyze/{uploaded_project}")
        aid = resp.json()["analysis_id"]

        resp = client.get(f"/api/v1/evm/analyses/{aid}")
        assert resp.status_code == 200

        data = resp.json()
        assert data["analysis_id"] == aid
        assert "metrics" in data
        assert "wbs_breakdown" in data
        assert "s_curve" in data
        assert "schedule_health" in data
        assert "cost_health" in data
        assert "forecast" in data
        assert "summary" in data
