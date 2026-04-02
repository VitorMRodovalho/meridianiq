# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for JSON and CSV export endpoints (v1.2).

Tests verify that:
1. JSON export returns valid JSON with expected structure
2. CSV export returns valid CSV for each dataset type
3. Invalid dataset parameter returns 400
4. Non-existent project returns 404
"""

from __future__ import annotations

import csv
import io
import json
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


def _upload(client: TestClient) -> str:
    """Upload sample XER and return project_id."""
    with open(SAMPLE_XER, "rb") as f:
        resp = client.post(
            "/api/v1/upload",
            files={"file": (SAMPLE_XER.name, f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    return resp.json()["project_id"]


class TestJSONExport:
    """Tests for GET /api/v1/projects/{id}/export/json."""

    def test_json_export_returns_200(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/json")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]

    def test_json_export_valid_structure(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/json")
        data = json.loads(resp.content)

        assert data["export_version"] == "1.0"
        assert data["generator"] == "MeridianIQ"
        assert "project" in data
        assert "health_score" in data
        assert "dcma" in data
        assert "activities" in data
        assert "relationships" in data

    def test_json_export_project_metadata(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/json")
        data = json.loads(resp.content)

        proj = data["project"]
        assert "name" in proj
        assert "activity_count" in proj
        assert "relationship_count" in proj
        assert proj["activity_count"] > 0

    def test_json_export_health_score(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/json")
        data = json.loads(resp.content)

        hs = data["health_score"]
        assert "overall" in hs
        assert "rating" in hs
        assert hs["rating"] in ("excellent", "good", "fair", "poor")
        assert 0 <= hs["overall"] <= 100

    def test_json_export_dcma_metrics(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/json")
        data = json.loads(resp.content)

        dcma = data["dcma"]
        assert "overall_score" in dcma
        assert "metrics" in dcma
        assert len(dcma["metrics"]) > 0
        m = dcma["metrics"][0]
        assert "number" in m
        assert "name" in m
        assert "value" in m
        assert "passed" in m

    def test_json_export_activities(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/json")
        data = json.loads(resp.content)

        activities = data["activities"]
        assert len(activities) > 0
        a = activities[0]
        assert "task_id" in a
        assert "task_code" in a
        assert "task_name" in a
        assert "status_code" in a
        assert "total_float_hr" in a

    def test_json_export_content_disposition(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/json")
        assert "content-disposition" in resp.headers
        assert ".json" in resp.headers["content-disposition"]

    def test_json_export_project_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects/nonexistent/export/json")
        assert resp.status_code == 404


class TestCSVExport:
    """Tests for GET /api/v1/projects/{id}/export/csv."""

    def test_csv_activities_returns_200(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/csv?dataset=activities")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_csv_activities_valid_content(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/csv?dataset=activities")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)

        # Header row
        assert rows[0][0] == "task_id"
        assert "task_code" in rows[0]
        assert "status_code" in rows[0]
        # At least one data row
        assert len(rows) > 1

    def test_csv_dcma_valid_content(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/csv?dataset=dcma")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)

        assert rows[0][0] == "number"
        assert "name" in rows[0]
        assert "passed" in rows[0]
        assert len(rows) > 1

    def test_csv_relationships_valid_content(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/csv?dataset=relationships")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)

        assert rows[0][0] == "task_id"
        assert "pred_task_id" in rows[0]
        assert "pred_type" in rows[0]

    def test_csv_default_dataset_is_activities(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/csv")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert rows[0][0] == "task_id"

    def test_csv_invalid_dataset_returns_400(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/csv?dataset=invalid")
        assert resp.status_code == 400
        assert "Invalid dataset" in resp.json()["detail"]

    def test_csv_content_disposition(self, client: TestClient) -> None:
        pid = _upload(client)
        resp = client.get(f"/api/v1/projects/{pid}/export/csv?dataset=dcma")
        assert "content-disposition" in resp.headers
        assert "-dcma.csv" in resp.headers["content-disposition"]

    def test_csv_project_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/projects/nonexistent/export/csv")
        assert resp.status_code == 404
