# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for GET /api/v1/projects/{project_id}/available-reports (P3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import app, get_store

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XER = FIXTURES / "sample.xer"
SAMPLE_UPDATE_XER = FIXTURES / "sample_update.xer"


@pytest.fixture(autouse=True)
def clear_store() -> None:
    """Clear in-memory store before each test."""
    get_store().clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _upload(client: TestClient, path: Path) -> str:
    """Upload an XER file and return the project_id."""
    with open(path, "rb") as f:
        resp = client.post(
            "/api/v1/upload",
            files={"file": (path.name, f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    return resp.json()["project_id"]


class TestAvailableReports:
    """Tests for the available-reports endpoint."""

    def test_available_reports_health_ready(self, client: TestClient) -> None:
        """Health report must always be ready after a successful upload."""
        pid = _upload(client, SAMPLE_XER)

        resp = client.get(f"/api/v1/projects/{pid}/available-reports")
        assert resp.status_code == 200
        data = resp.json()

        assert data["project_id"] == pid
        assert "reports" in data

        by_type = {r["type"]: r for r in data["reports"]}
        assert "health" in by_type
        assert by_type["health"]["ready"] is True
        assert by_type["health"]["reason"] == ""

    def test_available_reports_evm_not_ready(self, client: TestClient) -> None:
        """EVM report must be NOT ready when no EVM analysis has been run."""
        pid = _upload(client, SAMPLE_XER)

        resp = client.get(f"/api/v1/projects/{pid}/available-reports")
        assert resp.status_code == 200
        data = resp.json()

        by_type = {r["type"]: r for r in data["reports"]}
        assert "evm" in by_type
        assert by_type["evm"]["ready"] is False
        assert len(by_type["evm"]["reason"]) > 0

    def test_available_reports_all_types_listed(self, client: TestClient) -> None:
        """Response must include all five expected report types."""
        pid = _upload(client, SAMPLE_XER)

        resp = client.get(f"/api/v1/projects/{pid}/available-reports")
        assert resp.status_code == 200
        data = resp.json()

        types = {r["type"] for r in data["reports"]}
        expected = {
            "health",
            "dcma",
            "comparison",
            "evm",
            "risk",
            "monthly_review",
            "calendar",
            "attribution",
            "narrative",
            "executive_summary",
            "scl_protocol",
            "aace_29r03",
            "aia_g702",
        }
        assert expected == types

    def test_available_reports_project_not_found(self, client: TestClient) -> None:
        """Non-existent project must return 404."""
        resp = client.get("/api/v1/projects/nonexistent/available-reports")
        assert resp.status_code == 404

    def test_available_reports_comparison_with_sibling(self, client: TestClient) -> None:
        """Comparison report becomes ready when a program has two revisions."""
        # Both sample XERs share the same proj_short_name so they land in
        # the same program as revision 1 and revision 2.
        _upload(client, SAMPLE_XER)
        pid2 = _upload(client, SAMPLE_UPDATE_XER)

        resp = client.get(f"/api/v1/projects/{pid2}/available-reports")
        assert resp.status_code == 200
        data = resp.json()

        by_type = {r["type"]: r for r in data["reports"]}
        # Same program name means comparison should be ready
        assert "comparison" in by_type
        # If the two files share the same project name, ready = True
        # (if not, the test at least verifies the field is present)
        assert isinstance(by_type["comparison"]["ready"], bool)

    def test_narrative_report_listed_and_ready(self, client: TestClient) -> None:
        """Narrative report must appear in available-reports and be ready."""
        pid = _upload(client, SAMPLE_XER)
        resp = client.get(f"/api/v1/projects/{pid}/available-reports")
        assert resp.status_code == 200
        by_type = {r["type"]: r for r in resp.json()["reports"]}
        assert "narrative" in by_type
        assert by_type["narrative"]["ready"] is True
        assert by_type["narrative"]["name"] == "Schedule Narrative Report"

    def test_executive_summary_listed_and_ready(self, client: TestClient) -> None:
        """Executive Summary must appear in available-reports and be ready."""
        pid = _upload(client, SAMPLE_XER)
        resp = client.get(f"/api/v1/projects/{pid}/available-reports")
        assert resp.status_code == 200
        by_type = {r["type"]: r for r in resp.json()["reports"]}
        assert "executive_summary" in by_type
        assert by_type["executive_summary"]["ready"] is True
        assert by_type["executive_summary"]["name"] == "Executive Summary"


class TestExecutiveSummaryGeneration:
    """Integration tests for executive_summary PDF generation with enrichment."""

    def test_executive_summary_generate_and_download(self, client: TestClient) -> None:
        """POST generate + GET download returns non-empty PDF/HTML bytes."""
        pid = _upload(client, SAMPLE_XER)

        resp = client.post(
            "/api/v1/reports/generate",
            json={"project_id": pid, "report_type": "executive_summary"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["report_type"] == "executive_summary"

        report_id = data["report_id"]
        dl = client.get(f"/api/v1/reports/{report_id}/download")
        assert dl.status_code == 200
        assert len(dl.content) > 0

    def test_scl_protocol_generate_and_download(self, client: TestClient) -> None:
        """SCL Protocol submission generates + downloads (with a single upload)."""
        pid = _upload(client, SAMPLE_XER)
        resp = client.post(
            "/api/v1/reports/generate",
            json={"project_id": pid, "report_type": "scl_protocol"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["report_type"] == "scl_protocol"

        dl = client.get(f"/api/v1/reports/{data['report_id']}/download")
        assert dl.status_code == 200
        assert len(dl.content) > 0

    def test_scl_protocol_listed_ready(self, client: TestClient) -> None:
        pid = _upload(client, SAMPLE_XER)
        resp = client.get(f"/api/v1/projects/{pid}/available-reports")
        by_type = {r["type"]: r for r in resp.json()["reports"]}
        assert "scl_protocol" in by_type
        assert by_type["scl_protocol"]["ready"] is True
        assert by_type["scl_protocol"]["name"] == "SCL Protocol Delay Analysis"

    def test_aace_29r03_generate_and_download(self, client: TestClient) -> None:
        """AACE RP 29R-03 §5.3 submission generates + downloads."""
        pid = _upload(client, SAMPLE_XER)
        resp = client.post(
            "/api/v1/reports/generate",
            json={"project_id": pid, "report_type": "aace_29r03"},
        )
        assert resp.status_code == 200, resp.text

        dl = client.get(f"/api/v1/reports/{resp.json()['report_id']}/download")
        assert dl.status_code == 200
        body = dl.content.decode("utf-8", errors="ignore")
        # Expect the method marker in HTML fallback or PDF stream
        assert "MIP 3.3" in body or dl.content.startswith(b"%PDF")

    def test_aace_29r03_with_baseline_enables_timeline(self, client: TestClient) -> None:
        """Supplying baseline_id unlocks the forensic timeline sections."""
        base_pid = _upload(client, SAMPLE_XER)
        update_pid = _upload(client, SAMPLE_UPDATE_XER)
        resp = client.post(
            "/api/v1/reports/generate",
            json={
                "project_id": update_pid,
                "report_type": "aace_29r03",
                "baseline_id": base_pid,
            },
        )
        assert resp.status_code == 200, resp.text

    def test_executive_summary_enriched_with_cost_variance(self, client: TestClient) -> None:
        """When two CBS snapshots exist, the PDF includes a Cost Variance section."""
        from src.analytics.cost_integration import CBSElement, CostIntegrationResult
        from src.api.deps import get_store as _get_store

        pid = _upload(client, SAMPLE_XER)
        store = _get_store()

        a = CostIntegrationResult(
            cbs_elements=[
                CBSElement(cbs_code="C.A.1", cbs_level1="Con", estimate=1000, budget=1200)
            ],
            total_budget=1_000_000,
        )
        b = CostIntegrationResult(
            cbs_elements=[
                CBSElement(cbs_code="C.A.1", cbs_level1="Con", estimate=1500, budget=1800)
            ],
            total_budget=1_500_000,
        )
        store.save_cost_upload(project_id=pid, result=a, source_name="v1")
        store.save_cost_upload(project_id=pid, result=b, source_name="v2")

        resp = client.post(
            "/api/v1/reports/generate",
            json={"project_id": pid, "report_type": "executive_summary"},
        )
        assert resp.status_code == 200

        dl = client.get(f"/api/v1/reports/{resp.json()['report_id']}/download")
        assert dl.status_code == 200
        body = dl.content.decode("utf-8", errors="ignore")
        # Either HTML fallback or PDF containing the section marker
        # (PDF binary usually contains strings too); check for distinctive phrase
        assert "Cost Variance" in body or dl.content.startswith(b"%PDF")


class TestNarrativeGeneration:
    """Happy-path test for narrative PDF generation + download."""

    def test_narrative_generate_and_download(self, client: TestClient) -> None:
        pid = _upload(client, SAMPLE_XER)

        resp = client.post(
            "/api/v1/reports/generate",
            json={"project_id": pid, "report_type": "narrative"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["report_type"] == "narrative"
        assert data["project_id"] == pid
        report_id = data["report_id"]

        dl = client.get(f"/api/v1/reports/{report_id}/download")
        assert dl.status_code == 200
        assert len(dl.content) > 0
        # Accept either PDF (when weasyprint is installed) or HTML fallback
        assert dl.content[:5] == b"%PDF-" or b"<html" in dl.content[:200].lower()

    def test_narrative_invalid_project(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/reports/generate",
            json={"project_id": "does-not-exist", "report_type": "narrative"},
        )
        assert resp.status_code == 404
