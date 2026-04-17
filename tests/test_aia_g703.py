# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for AIA G703 Continuation Sheet builder + export endpoint."""

from __future__ import annotations

import importlib.util

import pytest
from fastapi.testclient import TestClient

from src.analytics.aia_g703 import (
    G703ContinuationSheet,
    G703LineItem,
    build_g703_from_cbs,
)
from src.analytics.cost_integration import CBSElement, CostIntegrationResult
from src.api.app import app
from src.api.deps import get_store

_openpyxl_available = importlib.util.find_spec("openpyxl") is not None


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


class TestBuildG703:
    def test_returns_sheet_with_line_items(self) -> None:
        sheet = build_g703_from_cbs(_sample_snapshot(), project_name="Proj")
        assert isinstance(sheet, G703ContinuationSheet)
        assert len(sheet.line_items) == 2
        assert sheet.project_name == "Proj"

    def test_line_numbers_are_zero_padded(self) -> None:
        sheet = build_g703_from_cbs(_sample_snapshot())
        assert sheet.line_items[0].line_number == "001"
        assert sheet.line_items[1].line_number == "002"

    def test_scheduled_value_uses_budget(self) -> None:
        sheet = build_g703_from_cbs(_sample_snapshot())
        assert sheet.line_items[0].scheduled_value == 1_300_000.0
        assert sheet.line_items[1].scheduled_value == 650_000.0

    def test_zero_billing_without_completion_pcts(self) -> None:
        sheet = build_g703_from_cbs(_sample_snapshot())
        for li in sheet.line_items:
            assert li.previous_application_value == 0.0
            assert li.this_period_value == 0.0
            assert li.percent_complete == 0.0
            assert li.balance_to_finish == li.scheduled_value
            assert li.retainage == 0.0

    def test_current_completion_generates_this_period_delta(self) -> None:
        snap = _sample_snapshot()
        sheet = build_g703_from_cbs(
            snap,
            previous_completion_pct={"C.SP.100": 20.0},
            current_completion_pct={"C.SP.100": 50.0},
        )
        li = sheet.line_items[0]
        # prev: 1.3M * 20% = 260k; cur: 1.3M * 50% = 650k; this period = 390k
        assert li.previous_application_value == 260_000.0
        assert li.total_completed_and_stored == 650_000.0
        assert li.this_period_value == 390_000.0
        assert li.percent_complete == 50.0

    def test_retainage_applied_on_cumulative(self) -> None:
        sheet = build_g703_from_cbs(
            _sample_snapshot(),
            current_completion_pct={"C.SP.100": 100.0},
            retainage_pct=0.05,
        )
        # 1.3M * 100% = 1.3M cumulative; 5% retainage = 65k
        assert sheet.line_items[0].retainage == 65_000.0

    def test_current_pct_is_monotonic_vs_previous(self) -> None:
        """A prior application's % should not exceed the current one."""
        sheet = build_g703_from_cbs(
            _sample_snapshot(),
            previous_completion_pct={"C.SP.100": 60.0},
            current_completion_pct={"C.SP.100": 30.0},  # (invalid — should clamp up)
        )
        li = sheet.line_items[0]
        assert li.percent_complete >= 60.0

    def test_grand_totals(self) -> None:
        sheet = build_g703_from_cbs(
            _sample_snapshot(),
            current_completion_pct={"C.SP.100": 50.0, "C.EN.200": 100.0},
            retainage_pct=0.10,
        )
        assert sheet.total_scheduled_value == 1_950_000.0
        # 50% of 1.3M + 100% of 650k = 650k + 650k = 1.3M
        assert sheet.total_completed_and_stored == 1_300_000.0
        # 10% of 1.3M cumulative = 130k
        assert sheet.total_retainage == 130_000.0

    def test_fallback_when_budget_is_zero(self) -> None:
        snap = CostIntegrationResult(
            cbs_elements=[
                CBSElement(
                    cbs_code="C.X",
                    estimate=500.0,
                    contingency=100.0,
                    escalation=50.0,
                    budget=0.0,
                )
            ]
        )
        sheet = build_g703_from_cbs(snap)
        assert sheet.line_items[0].scheduled_value == 650.0

    def test_empty_snapshot(self) -> None:
        sheet = build_g703_from_cbs(CostIntegrationResult())
        assert sheet.line_items == []
        assert sheet.total_scheduled_value == 0.0


class TestG703LineItem:
    def test_default_values(self) -> None:
        li = G703LineItem()
        assert li.scheduled_value == 0.0
        assert li.retainage == 0.0


class TestG703ExportEndpoint:
    def test_missing_snapshot_returns_404(self) -> None:
        get_store().clear()
        client = TestClient(app)
        resp = client.get(
            "/api/v1/projects/some-project/export/aia-g703",
            params={"snapshot_id": "nonexistent"},
        )
        assert resp.status_code == 404

    @pytest.mark.skipif(not _openpyxl_available, reason="openpyxl required for xlsx generation")
    def test_end_to_end_xlsx(self) -> None:
        get_store().clear()
        store = get_store()
        snap_id = store.save_cost_upload(
            project_id="p-g703", result=_sample_snapshot(), source_name="Q1"
        )

        client = TestClient(app)
        resp = client.get(
            "/api/v1/projects/p-g703/export/aia-g703",
            params={"snapshot_id": snap_id, "retainage_pct": 0.10},
        )
        assert resp.status_code == 200, resp.text
        ct = resp.headers["content-type"]
        assert "spreadsheetml" in ct or "xlsx" in ct
        # Non-empty body
        assert len(resp.content) > 500
        # Default xlsx signature starts with PK (zip file)
        assert resp.content[:2] == b"PK"

    @pytest.mark.skipif(not _openpyxl_available, reason="openpyxl required for xlsx generation")
    def test_filename_includes_application_number(self) -> None:
        get_store().clear()
        store = get_store()
        snap_id = store.save_cost_upload(
            project_id="p-g703-app", result=_sample_snapshot(), source_name="Q2"
        )

        client = TestClient(app)
        resp = client.get(
            "/api/v1/projects/p-g703-app/export/aia-g703",
            params={"snapshot_id": snap_id, "application_number": 5},
        )
        assert resp.status_code == 200
        assert "app005" in resp.headers["content-disposition"]
