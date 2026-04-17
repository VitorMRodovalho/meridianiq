# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for AIA G702 Application and Certificate for Payment."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.analytics.aia_g702 import (
    G702Application,
    G702ChangeOrder,
    build_g702_from_g703,
)
from src.analytics.aia_g703 import build_g703_from_cbs
from src.analytics.cost_integration import CBSElement, CostIntegrationResult
from src.api.app import app
from src.api.deps import get_store
from src.parser.models import ParsedSchedule, Project, Task


def _sample_snapshot() -> CostIntegrationResult:
    return CostIntegrationResult(
        cbs_elements=[
            CBSElement(
                cbs_code="C.SP.100",
                cbs_level1="Construction",
                scope="Foundations",
                estimate=1_000_000.0,
                contingency=250_000.0,
                escalation=50_000.0,
                budget=1_300_000.0,
            ),
            CBSElement(
                cbs_code="C.EN.200",
                cbs_level1="Engineering",
                scope="Design",
                estimate=500_000.0,
                contingency=125_000.0,
                escalation=25_000.0,
                budget=650_000.0,
            ),
        ],
        total_budget=1_500_000.0,
    )


def _half_complete_g703():
    # 1.3M @ 50% = 650k completed; 650k @ 100% = 650k completed.
    # Grand total completed & stored = 1.3M. At 10% retainage = 130k.
    return build_g703_from_cbs(
        _sample_snapshot(),
        project_name="G702 Test",
        application_number=3,
        period_to="2026-04-30",
        retainage_pct=0.10,
        current_completion_pct={"C.SP.100": 50.0, "C.EN.200": 100.0},
    )


class TestG702ChangeOrder:
    def test_defaults_zero(self) -> None:
        co = G702ChangeOrder()
        assert co.total_additions == 0.0
        assert co.total_deductions == 0.0
        assert co.net_change == 0.0

    def test_aggregates_prior_and_current(self) -> None:
        co = G702ChangeOrder(
            prior_additions=100_000.0,
            prior_deductions=25_000.0,
            this_period_additions=40_000.0,
            this_period_deductions=5_000.0,
        )
        assert co.total_additions == 140_000.0
        assert co.total_deductions == 30_000.0
        assert co.net_change == 110_000.0


class TestBuildG702:
    def test_minimum_inputs_produce_valid_app(self) -> None:
        g703 = _half_complete_g703()
        g702 = build_g702_from_g703(g703, original_contract_sum=2_000_000.0)
        assert isinstance(g702, G702Application)
        assert g702.project_name == "G702 Test"
        assert g702.application_number == 3
        assert g702.original_contract_sum == 2_000_000.0

    def test_lines_balance(self) -> None:
        """Contract sum to date = line 1 + net CO; earnings = completed - retainage."""
        g703 = _half_complete_g703()
        co = G702ChangeOrder(prior_additions=50_000.0, this_period_additions=25_000.0)
        g702 = build_g702_from_g703(
            g703,
            original_contract_sum=2_000_000.0,
            previous_certificates_total=400_000.0,
            change_order=co,
        )
        assert g702.net_change_by_change_orders == 75_000.0
        assert g702.contract_sum_to_date == 2_075_000.0
        # completed & stored = 1.3M; retainage = 130k → earned less retainage = 1.17M
        assert g702.total_completed_and_stored == 1_300_000.0
        assert g702.total_retainage == 130_000.0
        assert g702.total_earned_less_retainage == 1_170_000.0
        # current due = 1.17M - 400k previously certified = 770k
        assert g702.current_payment_due == 770_000.0
        # balance = contract to date - earned less retainage = 2.075M - 1.17M = 905k
        assert g702.balance_to_finish_including_retainage == 905_000.0

    def test_retainage_split_between_completed_and_stored(self) -> None:
        g703 = _half_complete_g703()
        g702 = build_g702_from_g703(
            g703,
            original_contract_sum=2_000_000.0,
            retainage_stored_fraction=0.25,
        )
        # 25% of 130k = 32 500 stored, remaining 97 500 completed
        assert g702.retainage_stored_materials == 32_500.0
        assert g702.retainage_completed_work == 97_500.0
        assert (
            g702.retainage_stored_materials + g702.retainage_completed_work
            == g702.total_retainage
        )

    def test_zero_retainage_split_defaults_to_all_completed(self) -> None:
        g703 = _half_complete_g703()
        g702 = build_g702_from_g703(g703, original_contract_sum=2_000_000.0)
        assert g702.retainage_stored_materials == 0.0
        assert g702.retainage_completed_work == g702.total_retainage

    def test_net_negative_change_order_reduces_contract_sum(self) -> None:
        g703 = _half_complete_g703()
        co = G702ChangeOrder(prior_deductions=200_000.0)
        g702 = build_g702_from_g703(
            g703,
            original_contract_sum=2_000_000.0,
            change_order=co,
        )
        assert g702.net_change_by_change_orders == -200_000.0
        assert g702.contract_sum_to_date == 1_800_000.0

    def test_header_fields_pass_through(self) -> None:
        g703 = _half_complete_g703()
        g702 = build_g702_from_g703(
            g703,
            original_contract_sum=1_000_000.0,
            owner="Acme Owner LLC",
            contractor="BuildCo",
            architect="DesignStudio",
            contract_for="Phase 2 Construction",
            architects_project_number="DS-2026-042",
            contract_date="2025-10-01",
        )
        assert g702.owner == "Acme Owner LLC"
        assert g702.contractor == "BuildCo"
        assert g702.architect == "DesignStudio"
        assert g702.contract_for == "Phase 2 Construction"
        assert g702.architects_project_number == "DS-2026-042"
        assert g702.contract_date == "2025-10-01"

    def test_retainage_split_fraction_clamped(self) -> None:
        g703 = _half_complete_g703()
        # Fraction > 1 should clamp to 1 (all into stored materials)
        g702 = build_g702_from_g703(
            g703,
            original_contract_sum=1_000_000.0,
            retainage_stored_fraction=2.5,
        )
        assert g702.retainage_stored_materials == g702.total_retainage
        assert g702.retainage_completed_work == 0.0


@pytest.fixture(autouse=True)
def _clear() -> None:
    get_store().clear()


class TestAiaG702ReportEndpoint:
    """Integration tests for POST /api/v1/reports/generate with aia_g702."""

    def _upload_schedule(self) -> str:
        store = get_store()
        schedule = ParsedSchedule(
            projects=[Project(proj_id="PG702", proj_short_name="G702 Project")],
            activities=[Task(task_id="T1", task_code="A0001", task_name="Task")],
            relationships=[],
        )
        return store.add(schedule, b"xer")

    def _save_snapshot(self, project_id: str) -> str:
        store = get_store()
        return store.save_cost_upload(
            project_id=project_id, result=_sample_snapshot(), source_name="CBS-Q1"
        )

    def test_report_type_registered_in_available_reports(self) -> None:
        pid = self._upload_schedule()
        self._save_snapshot(pid)
        client = TestClient(app)
        resp = client.get(f"/api/v1/projects/{pid}/available-reports")
        assert resp.status_code == 200
        by_type = {r["type"]: r for r in resp.json()["reports"]}
        assert "aia_g702" in by_type
        assert by_type["aia_g702"]["ready"] is True

    def test_available_reports_marks_unready_without_snapshot(self) -> None:
        pid = self._upload_schedule()
        client = TestClient(app)
        resp = client.get(f"/api/v1/projects/{pid}/available-reports")
        by_type = {r["type"]: r for r in resp.json()["reports"]}
        # No snapshot saved → not ready, with reason populated
        assert by_type["aia_g702"]["ready"] is False
        assert "CBS snapshot" in by_type["aia_g702"]["reason"]

    def test_generate_aia_g702_missing_snapshot_id_returns_400(self) -> None:
        pid = self._upload_schedule()
        self._save_snapshot(pid)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/reports/generate",
            json={
                "project_id": pid,
                "report_type": "aia_g702",
                "options": {"original_contract_sum": 2_000_000.0},
            },
        )
        assert resp.status_code == 400
        assert "snapshot_id" in resp.text

    def test_generate_aia_g702_missing_contract_sum_returns_400(self) -> None:
        pid = self._upload_schedule()
        snap_id = self._save_snapshot(pid)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/reports/generate",
            json={
                "project_id": pid,
                "report_type": "aia_g702",
                "options": {"snapshot_id": snap_id},
            },
        )
        assert resp.status_code == 400
        assert "original_contract_sum" in resp.text

    def test_generate_aia_g702_bad_snapshot_returns_404(self) -> None:
        pid = self._upload_schedule()
        self._save_snapshot(pid)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/reports/generate",
            json={
                "project_id": pid,
                "report_type": "aia_g702",
                "options": {
                    "snapshot_id": "does-not-exist",
                    "original_contract_sum": 2_000_000.0,
                },
            },
        )
        assert resp.status_code == 404
        assert "snapshot" in resp.text.lower()

    def test_generate_aia_g702_end_to_end(self) -> None:
        pid = self._upload_schedule()
        snap_id = self._save_snapshot(pid)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/reports/generate",
            json={
                "project_id": pid,
                "report_type": "aia_g702",
                "options": {
                    "snapshot_id": snap_id,
                    "original_contract_sum": 2_000_000.0,
                    "application_number": 3,
                    "period_to": "2026-04-30",
                    "retainage_pct": 0.10,
                    "previous_certificates_total": 250_000.0,
                    "change_order": {
                        "prior_additions": 50_000.0,
                        "this_period_additions": 10_000.0,
                    },
                    "owner": "Acme Owner LLC",
                    "contractor": "BuildCo",
                    "architect": "DesignStudio",
                },
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["report_type"] == "aia_g702"
        assert body["project_id"] == pid
        report_id = body["report_id"]

        # Download and verify non-empty payload
        download = client.get(f"/api/v1/reports/{report_id}/download")
        assert download.status_code == 200
        # Either PDF (weasyprint installed) or HTML fallback; both acceptable
        ct = download.headers["content-type"]
        assert ct in ("application/pdf", "text/html; charset=utf-8", "text/html")
        assert len(download.content) > 500
        # Spot-check that the payload contains G702 form content regardless of
        # whether it rendered as PDF or fell back to HTML.
        if ct.startswith("text/html"):
            text = download.content.decode("utf-8", errors="ignore")
            assert "G702" in text
            assert "AMOUNT CERTIFIED" in text
