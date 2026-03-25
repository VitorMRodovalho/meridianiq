# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the FastAPI application."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import app, _store

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XER = FIXTURES / "sample.xer"
SAMPLE_UPDATE_XER = FIXTURES / "sample_update.xer"


@pytest.fixture(autouse=True)
def clear_store() -> None:
    """Clear the in-memory store before each test."""
    _store.clear()


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


class TestHealth:
    """Tests for the health endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        """GET /api/v1/health returns 200 with status ok."""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestUpload:
    """Tests for the upload endpoint."""

    def test_upload_xer(self, client: TestClient) -> None:
        """POST /api/v1/upload with sample.xer returns project summary."""
        data = _upload_xer(client, SAMPLE_XER)
        assert "project_id" in data
        assert data["activity_count"] == 30
        assert data["relationship_count"] == 40
        assert data["name"] == "Sample Construction"

    def test_upload_invalid_file(self, client: TestClient) -> None:
        """POST with non-XER file returns 400."""
        resp = client.post(
            "/api/v1/upload",
            files={"file": ("bad.txt", b"not an xer file", "text/plain")},
        )
        assert resp.status_code == 400


class TestProjects:
    """Tests for the project list and detail endpoints."""

    def test_list_projects(self, client: TestClient) -> None:
        """Upload then list, verify project appears."""
        _upload_xer(client, SAMPLE_XER)
        resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["projects"]) == 1
        assert data["projects"][0]["name"] == "Sample Construction"

    def test_get_project_detail(self, client: TestClient) -> None:
        """Upload then get detail, verify activities present."""
        upload = _upload_xer(client, SAMPLE_XER)
        pid = upload["project_id"]
        resp = client.get(f"/api/v1/projects/{pid}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["activities"]) == 30
        assert len(data["relationships"]) == 40

    def test_get_project_not_found(self, client: TestClient) -> None:
        """GET with invalid project_id returns 404."""
        resp = client.get("/api/v1/projects/nonexistent")
        assert resp.status_code == 404


class TestValidation:
    """Tests for the DCMA validation endpoint."""

    def test_get_validation(self, client: TestClient) -> None:
        """Upload then GET validation, verify DCMA results."""
        upload = _upload_xer(client, SAMPLE_XER)
        pid = upload["project_id"]
        resp = client.get(f"/api/v1/projects/{pid}/validation")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["metrics"]) == 14
        assert data["overall_score"] > 0
        assert data["activity_count"] > 0


class TestCriticalPath:
    """Tests for the critical path endpoint."""

    def test_get_critical_path(self, client: TestClient) -> None:
        """Upload then GET critical-path, verify CP activities returned."""
        upload = _upload_xer(client, SAMPLE_XER)
        pid = upload["project_id"]
        resp = client.get(f"/api/v1/projects/{pid}/critical-path")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_duration"] > 0
        assert len(data["critical_path"]) > 0
        assert data["has_cycles"] is False


class TestFloatDistribution:
    """Tests for the float distribution endpoint."""

    def test_get_float_distribution(self, client: TestClient) -> None:
        """Upload then GET float-distribution, verify buckets returned."""
        upload = _upload_xer(client, SAMPLE_XER)
        pid = upload["project_id"]
        resp = client.get(f"/api/v1/projects/{pid}/float-distribution")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_activities"] > 0
        assert len(data["buckets"]) > 0
        # Sum of percentages should be roughly 100
        total_pct = sum(b["percentage"] for b in data["buckets"])
        assert 99.0 <= total_pct <= 101.0


class TestMilestones:
    """Tests for the milestones endpoint."""

    def test_get_milestones(self, client: TestClient) -> None:
        """Upload then GET milestones, verify milestone activities returned."""
        upload = _upload_xer(client, SAMPLE_XER)
        pid = upload["project_id"]
        resp = client.get(f"/api/v1/projects/{pid}/milestones")
        assert resp.status_code == 200
        data = resp.json()
        # Should have milestones (TT_mile + TT_finmile)
        assert len(data["milestones"]) > 0
        # All should be milestone types
        for m in data["milestones"]:
            assert m["task_type"] in ("TT_mile", "TT_finmile")


class TestCompare:
    """Tests for the compare endpoint."""

    def test_compare_schedules(self, client: TestClient) -> None:
        """Upload both, POST compare, verify changes detected."""
        base = _upload_xer(client, SAMPLE_XER)
        upd = _upload_xer(client, SAMPLE_UPDATE_XER)

        resp = client.post(
            "/api/v1/compare",
            json={
                "baseline_id": base["project_id"],
                "update_id": upd["project_id"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["activities_added"]) == 2
        assert len(data["activities_deleted"]) == 1
        assert len(data["duration_changes"]) == 3
        assert data["changed_percentage"] > 0
        assert len(data["manipulation_flags"]) > 0
