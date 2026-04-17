# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for MIP 3.1 (Static Logic Gross) and MIP 3.2 (Dynamic Logic As-Is)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.analytics.mip_observational import (
    Mip31Result,
    Mip32Result,
    analyze_mip_3_1,
    analyze_mip_3_2,
)
from src.api.app import app
from src.api.deps import get_store
from src.parser.xer_reader import XERReader

FIXTURES = Path(__file__).parent / "fixtures"


def _parse(name: str):
    return XERReader(FIXTURES / name).parse()


@pytest.fixture
def baseline():
    return _parse("sample.xer")


@pytest.fixture
def update1():
    return _parse("sample_update.xer")


@pytest.fixture
def update2():
    return _parse("sample_update2.xer")


@pytest.fixture(autouse=True)
def _clear():
    get_store().clear()


# ---------------------------------------------------------------------------
# MIP 3.1 unit tests
# ---------------------------------------------------------------------------


class TestMip31Unit:
    def test_returns_result(self, baseline, update2):
        result = analyze_mip_3_1(baseline, update2, baseline_id="b", final_id="f")
        assert isinstance(result, Mip31Result)
        assert result.baseline_project_id == "b"
        assert result.final_project_id == "f"

    def test_methodology_string(self, baseline, update2):
        result = analyze_mip_3_1(baseline, update2)
        assert "MIP 3.1" in result.methodology
        assert "Gross" in result.methodology

    def test_gross_delay_is_numeric(self, baseline, update2):
        result = analyze_mip_3_1(baseline, update2)
        assert isinstance(result.gross_delay_days, float)

    def test_gross_delay_baseline_vs_self_is_zero(self, baseline):
        result = analyze_mip_3_1(baseline, baseline)
        assert result.gross_delay_days == 0.0
        # Same schedule → empty symmetric differences
        assert result.cp_activities_joined == []
        assert result.cp_activities_left == []

    def test_critical_paths_populated(self, baseline, update2):
        result = analyze_mip_3_1(baseline, update2)
        # CP may be empty only if CPM cycles — fixture has no cycles
        assert isinstance(result.baseline_critical_path, list)
        assert isinstance(result.final_critical_path, list)

    def test_comparison_summary_counts_present(self, baseline, update2):
        result = analyze_mip_3_1(baseline, update2)
        assert result.activities_added >= 0
        assert result.activities_deleted >= 0
        assert result.activities_changed >= 0


# ---------------------------------------------------------------------------
# MIP 3.2 unit tests
# ---------------------------------------------------------------------------


class TestMip32Unit:
    def test_requires_two_schedules(self, baseline):
        with pytest.raises(ValueError):
            analyze_mip_3_2([baseline])

    def test_returns_result(self, baseline, update1, update2):
        result = analyze_mip_3_2([baseline, update1, update2], project_ids=["a", "b", "c"])
        assert isinstance(result, Mip32Result)
        assert result.schedule_count == 3
        assert len(result.events) == 3
        assert result.project_ids == ["a", "b", "c"]

    def test_first_event_has_zero_delay_since_previous(self, baseline, update1):
        result = analyze_mip_3_2([baseline, update1])
        assert result.events[0].delay_since_previous_days == 0.0
        assert result.events[0].cp_activities_joined_since_previous == []
        assert result.events[0].cp_activities_left_since_previous == []

    def test_total_delay_equals_final_event(self, baseline, update1, update2):
        result = analyze_mip_3_2([baseline, update1, update2])
        # Final event's delay since baseline == total_delay_days
        assert result.events[-1].delay_since_baseline_days == result.total_delay_days

    def test_ever_critical_is_superset_of_each_events_cp(self, baseline, update1, update2):
        result = analyze_mip_3_2([baseline, update1, update2])
        ever = set(result.cp_activities_ever_critical)
        for e in result.events:
            assert set(e.critical_path).issubset(ever)

    def test_methodology_string(self, baseline, update1):
        result = analyze_mip_3_2([baseline, update1])
        assert "MIP 3.2" in result.methodology
        assert "As-Is" in result.methodology

    def test_project_ids_padded_when_shorter(self, baseline, update1, update2):
        result = analyze_mip_3_2([baseline, update1, update2], project_ids=["only-one"])
        assert result.project_ids == ["only-one", "", ""]


# ---------------------------------------------------------------------------
# Router integration tests
# ---------------------------------------------------------------------------


def _upload_xer(client: TestClient, path: Path) -> str:
    with open(path, "rb") as fh:
        r = client.post(
            "/api/v1/upload",
            files={"file": (path.name, fh, "application/octet-stream")},
        )
    assert r.status_code == 200, r.text
    return r.json()["project_id"]


class TestMip31Router:
    def test_missing_baseline_returns_404(self):
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forensic/mip-3-1",
            json={"baseline_id": "missing", "final_id": "missing"},
        )
        assert resp.status_code == 404

    def test_missing_final_returns_404(self):
        client = TestClient(app)
        pid = _upload_xer(client, FIXTURES / "sample.xer")
        resp = client.post(
            "/api/v1/forensic/mip-3-1",
            json={"baseline_id": pid, "final_id": "missing"},
        )
        assert resp.status_code == 404

    def test_end_to_end(self):
        client = TestClient(app)
        base_id = _upload_xer(client, FIXTURES / "sample.xer")
        final_id = _upload_xer(client, FIXTURES / "sample_update2.xer")
        resp = client.post(
            "/api/v1/forensic/mip-3-1",
            json={"baseline_id": base_id, "final_id": final_id},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "MIP 3.1" in data["methodology"]
        assert data["baseline_project_id"] == base_id
        assert data["final_project_id"] == final_id
        assert "gross_delay_days" in data


class TestMip32Router:
    def test_empty_project_ids_rejected(self):
        client = TestClient(app)
        resp = client.post("/api/v1/forensic/mip-3-2", json={"project_ids": []})
        assert resp.status_code == 422  # Pydantic min_length=2

    def test_one_project_id_rejected(self):
        client = TestClient(app)
        resp = client.post("/api/v1/forensic/mip-3-2", json={"project_ids": ["p1"]})
        assert resp.status_code == 422

    def test_missing_project_returns_404(self):
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forensic/mip-3-2",
            json={"project_ids": ["missing-a", "missing-b"]},
        )
        assert resp.status_code == 404

    def test_end_to_end_three_updates(self):
        client = TestClient(app)
        pa = _upload_xer(client, FIXTURES / "sample.xer")
        pb = _upload_xer(client, FIXTURES / "sample_update.xer")
        pc = _upload_xer(client, FIXTURES / "sample_update2.xer")
        resp = client.post(
            "/api/v1/forensic/mip-3-2",
            json={"project_ids": [pa, pb, pc]},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["schedule_count"] == 3
        assert len(data["events"]) == 3
        assert data["events"][0]["index"] == 0
        assert data["events"][0]["delay_since_previous_days"] == 0.0
        assert "MIP 3.2" in data["methodology"]
