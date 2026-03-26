# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the TIA and contract compliance API endpoints."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import app, _store, _tia_store

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XER = FIXTURES / "sample.xer"


@pytest.fixture(autouse=True)
def clear_stores() -> None:
    """Clear all in-memory stores before each test."""
    _store.clear()
    _tia_store.clear()


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    return TestClient(app)


def _upload_xer(client: TestClient, xer_path: Path) -> dict:
    """Helper to upload an XER file and return the JSON response."""
    with open(xer_path, "rb") as f:
        resp = client.post(
            "/api/v1/upload",
            files={"file": (xer_path.name, f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    return resp.json()


def _make_fragment_payload(
    fragment_id: str = "FRAG-API-001",
    responsible_party: str = "contractor",
    duration_hours: float = 80.0,
) -> dict:
    """Create a fragment payload for the API."""
    return {
        "fragment_id": fragment_id,
        "name": "Test API Delay",
        "description": "Test fragment for API testing",
        "responsible_party": responsible_party,
        "activities": [
            {
                "fragment_activity_id": f"{fragment_id}-A",
                "name": "Delay Activity",
                "duration_hours": duration_hours,
                "predecessors": [
                    {"activity_code": "A3050", "rel_type": "FS", "lag_hours": 0}
                ],
                "successors": [
                    {"activity_code": "A4010", "rel_type": "FS", "lag_hours": 0}
                ],
            }
        ],
    }


class TestCreateAnalysis:
    """Test: create a TIA analysis via the API."""

    def test_create_analysis(self, client: TestClient) -> None:
        """POST /api/v1/tia/analyze with fragments returns analysis."""
        proj = _upload_xer(client, SAMPLE_XER)
        pid = proj["project_id"]

        resp = client.post(
            "/api/v1/tia/analyze",
            json={
                "project_id": pid,
                "fragments": [_make_fragment_payload()],
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "analysis_id" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["delay_days"] > 0

    def test_create_analysis_owner_delay(self, client: TestClient) -> None:
        """Owner fragment should classify as excusable_compensable."""
        proj = _upload_xer(client, SAMPLE_XER)
        pid = proj["project_id"]

        resp = client.post(
            "/api/v1/tia/analyze",
            json={
                "project_id": pid,
                "fragments": [
                    _make_fragment_payload(
                        fragment_id="FRAG-OWN",
                        responsible_party="owner",
                    )
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["delay_type"] == "excusable_compensable"
        assert data["total_owner_delay"] > 0

    def test_create_analysis_not_found(self, client: TestClient) -> None:
        """Should return 404 for unknown project."""
        resp = client.post(
            "/api/v1/tia/analyze",
            json={
                "project_id": "nonexistent",
                "fragments": [_make_fragment_payload()],
            },
        )
        assert resp.status_code == 404


class TestListAnalyses:
    """Test: list TIA analyses."""

    def test_list_analyses_empty(self, client: TestClient) -> None:
        """Empty store should return empty list."""
        resp = client.get("/api/v1/tia/analyses")
        assert resp.status_code == 200
        assert resp.json()["analyses"] == []

    def test_list_analyses_after_create(self, client: TestClient) -> None:
        """List should contain the created analysis."""
        proj = _upload_xer(client, SAMPLE_XER)
        pid = proj["project_id"]

        client.post(
            "/api/v1/tia/analyze",
            json={
                "project_id": pid,
                "fragments": [_make_fragment_payload()],
            },
        )

        resp = client.get("/api/v1/tia/analyses")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["analyses"]) == 1


class TestGetAnalysisDetail:
    """Test: get full TIA analysis detail."""

    def test_get_analysis_detail(self, client: TestClient) -> None:
        """GET /api/v1/tia/analyses/{id} returns full analysis."""
        proj = _upload_xer(client, SAMPLE_XER)
        pid = proj["project_id"]

        create_resp = client.post(
            "/api/v1/tia/analyze",
            json={
                "project_id": pid,
                "fragments": [_make_fragment_payload()],
            },
        )
        aid = create_resp.json()["analysis_id"]

        resp = client.get(f"/api/v1/tia/analyses/{aid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["analysis_id"] == aid
        assert len(data["results"]) == 1

    def test_get_analysis_not_found(self, client: TestClient) -> None:
        """Should return 404 for unknown analysis."""
        resp = client.get("/api/v1/tia/analyses/nonexistent")
        assert resp.status_code == 404


class TestGetSummary:
    """Test: get TIA analysis summary."""

    def test_get_summary(self, client: TestClient) -> None:
        """GET /api/v1/tia/analyses/{id}/summary returns delay breakdown."""
        proj = _upload_xer(client, SAMPLE_XER)
        pid = proj["project_id"]

        create_resp = client.post(
            "/api/v1/tia/analyze",
            json={
                "project_id": pid,
                "fragments": [
                    _make_fragment_payload(
                        fragment_id="FRAG-S1",
                        responsible_party="owner",
                    ),
                    _make_fragment_payload(
                        fragment_id="FRAG-S2",
                        responsible_party="contractor",
                    ),
                ],
            },
        )
        aid = create_resp.json()["analysis_id"]

        resp = client.get(f"/api/v1/tia/analyses/{aid}/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_owner_delay"] > 0
        assert data["total_contractor_delay"] > 0
        assert data["net_delay"] > 0


class TestContractCheck:
    """Test: contract compliance check via API."""

    def test_contract_check(self, client: TestClient) -> None:
        """POST /api/v1/contract/check returns compliance checks."""
        proj = _upload_xer(client, SAMPLE_XER)
        pid = proj["project_id"]

        create_resp = client.post(
            "/api/v1/tia/analyze",
            json={
                "project_id": pid,
                "fragments": [_make_fragment_payload()],
            },
        )
        aid = create_resp.json()["analysis_id"]

        resp = client.post(
            "/api/v1/contract/check",
            json={"analysis_id": aid},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_checks"] > 0
        assert len(data["checks"]) > 0

    def test_contract_check_not_found(self, client: TestClient) -> None:
        """Should return 404 for unknown analysis."""
        resp = client.post(
            "/api/v1/contract/check",
            json={"analysis_id": "nonexistent"},
        )
        assert resp.status_code == 404

    def test_contract_provisions(self, client: TestClient) -> None:
        """GET /api/v1/contract/provisions returns default provisions."""
        resp = client.get("/api/v1/contract/provisions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["provisions"]) >= 5
