# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for Risk (Monte Carlo QSRA) API endpoints.

Verifies the REST API for running simulations, fetching results,
histogram, tornado, criticality, and S-curve data.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.storage import ProjectStore, RiskStore
from tests.fixtures.sample_xer_generator import generate_sample_xer


@pytest.fixture()
def client():
    """Create a test client with fresh stores."""
    import src.api.app as app_module

    test_store = ProjectStore()
    test_risk_store = RiskStore()

    original_store = app_module._store
    original_risk_store = app_module._risk_store

    app_module._store = test_store
    app_module._risk_store = test_risk_store

    yield TestClient(app)

    app_module._store = original_store
    app_module._risk_store = original_risk_store


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


class TestRunSimulation:
    """Test POST /api/v1/risk/simulate/{project_id}."""

    def test_run_simulation(self, client: TestClient, uploaded_project: str) -> None:
        """Running a simulation returns valid results."""
        body = {
            "config": {
                "iterations": 200,
                "default_distribution": "pert",
                "default_uncertainty": 0.2,
                "seed": 42,
                "confidence_levels": [10, 50, 80, 90],
            },
            "duration_risks": [],
            "risk_events": [],
        }
        resp = client.post(
            f"/api/v1/risk/simulate/{uploaded_project}",
            json=body,
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "simulation_id" in data
        assert data["project_name"] == "Sample Construction"
        assert data["iterations"] == 200
        assert data["deterministic_days"] > 0
        assert data["mean_days"] > 0
        assert len(data["p_values"]) == 4
        assert len(data["histogram"]) == 30
        assert len(data["criticality"]) > 0
        assert len(data["sensitivity"]) > 0
        assert len(data["s_curve"]) > 0

    def test_run_simulation_not_found(self, client: TestClient) -> None:
        """Running simulation on missing project returns 404."""
        resp = client.post(
            "/api/v1/risk/simulate/nonexistent",
            json={"config": None, "duration_risks": [], "risk_events": []},
        )
        assert resp.status_code == 404


class TestListSimulations:
    """Test GET /api/v1/risk/simulations."""

    def test_list_empty(self, client: TestClient) -> None:
        """Empty list returned when no simulations exist."""
        resp = client.get("/api/v1/risk/simulations")
        assert resp.status_code == 200
        assert resp.json()["simulations"] == []

    def test_list_after_simulation(
        self, client: TestClient, uploaded_project: str
    ) -> None:
        """List includes simulation after running one."""
        body = {
            "config": {"iterations": 100, "seed": 42},
            "duration_risks": [],
            "risk_events": [],
        }
        client.post(f"/api/v1/risk/simulate/{uploaded_project}", json=body)

        resp = client.get("/api/v1/risk/simulations")
        assert resp.status_code == 200
        sims = resp.json()["simulations"]
        assert len(sims) == 1
        assert sims[0]["project_name"] == "Sample Construction"


class TestGetHistogram:
    """Test GET /api/v1/risk/simulations/{id}/histogram."""

    def test_get_histogram(self, client: TestClient, uploaded_project: str) -> None:
        """Histogram endpoint returns bins and P-value lines."""
        body = {
            "config": {"iterations": 200, "seed": 42},
            "duration_risks": [],
            "risk_events": [],
        }
        resp = client.post(f"/api/v1/risk/simulate/{uploaded_project}", json=body)
        sid = resp.json()["simulation_id"]

        resp = client.get(f"/api/v1/risk/simulations/{sid}/histogram")
        assert resp.status_code == 200

        data = resp.json()
        assert data["simulation_id"] == sid
        assert len(data["bins"]) == 30
        assert len(data["p_values"]) > 0
        assert data["deterministic_days"] > 0

    def test_get_histogram_not_found(self, client: TestClient) -> None:
        """Histogram for missing simulation returns 404."""
        resp = client.get("/api/v1/risk/simulations/nonexistent/histogram")
        assert resp.status_code == 404


class TestGetTornado:
    """Test GET /api/v1/risk/simulations/{id}/tornado."""

    def test_get_tornado(self, client: TestClient, uploaded_project: str) -> None:
        """Tornado endpoint returns sensitivity entries."""
        body = {
            "config": {"iterations": 200, "seed": 42},
            "duration_risks": [],
            "risk_events": [],
        }
        resp = client.post(f"/api/v1/risk/simulate/{uploaded_project}", json=body)
        sid = resp.json()["simulation_id"]

        resp = client.get(f"/api/v1/risk/simulations/{sid}/tornado")
        assert resp.status_code == 200

        data = resp.json()
        assert data["simulation_id"] == sid
        # Should have up to 15 entries
        assert len(data["entries"]) <= 15
        assert len(data["entries"]) > 0
        # Should be sorted by absolute correlation
        for i in range(len(data["entries"]) - 1):
            assert abs(data["entries"][i]["correlation"]) >= abs(
                data["entries"][i + 1]["correlation"]
            )


class TestGetCriticality:
    """Test GET /api/v1/risk/simulations/{id}/criticality."""

    def test_get_criticality(self, client: TestClient, uploaded_project: str) -> None:
        """Criticality endpoint returns per-activity criticality index."""
        body = {
            "config": {"iterations": 200, "seed": 42},
            "duration_risks": [],
            "risk_events": [],
        }
        resp = client.post(f"/api/v1/risk/simulate/{uploaded_project}", json=body)
        sid = resp.json()["simulation_id"]

        resp = client.get(f"/api/v1/risk/simulations/{sid}/criticality")
        assert resp.status_code == 200

        data = resp.json()
        assert data["simulation_id"] == sid
        assert len(data["entries"]) > 0

        # Criticality should be between 0 and 100
        for entry in data["entries"]:
            assert 0 <= entry["criticality_pct"] <= 100

        # At least one activity should have >0% criticality
        nonzero = [e for e in data["entries"] if e["criticality_pct"] > 0]
        assert len(nonzero) > 0


class TestGetSCurve:
    """Test GET /api/v1/risk/simulations/{id}/s-curve."""

    def test_get_s_curve(self, client: TestClient, uploaded_project: str) -> None:
        """S-curve endpoint returns cumulative probability data."""
        body = {
            "config": {"iterations": 200, "seed": 42},
            "duration_risks": [],
            "risk_events": [],
        }
        resp = client.post(f"/api/v1/risk/simulate/{uploaded_project}", json=body)
        sid = resp.json()["simulation_id"]

        resp = client.get(f"/api/v1/risk/simulations/{sid}/s-curve")
        assert resp.status_code == 200

        data = resp.json()
        assert data["simulation_id"] == sid
        assert data["deterministic_days"] > 0
        assert len(data["points"]) > 0
        assert len(data["p_values"]) > 0

        # Cumulative probability should be monotonically increasing
        for i in range(1, len(data["points"])):
            assert data["points"][i]["cumulative_probability"] >= data["points"][i - 1]["cumulative_probability"]

        # Last point should reach ~1.0
        assert data["points"][-1]["cumulative_probability"] >= 0.99

    def test_get_s_curve_not_found(self, client: TestClient) -> None:
        """S-curve for missing simulation returns 404."""
        resp = client.get("/api/v1/risk/simulations/nonexistent/s-curve")
        assert resp.status_code == 404
