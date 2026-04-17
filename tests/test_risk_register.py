# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the risk register engine."""

from __future__ import annotations

from src.analytics.risk_register import (
    RiskEntry,
    RiskRegisterSummary,
    register_to_risk_events,
    summarize_register,
)


def _sample_entries() -> list[RiskEntry]:
    return [
        RiskEntry(
            risk_id="R001",
            name="Weather delay",
            category="external",
            probability=0.6,
            impact_days=15,
            impact_cost=50000,
            status="open",
            affected_activities=["A100", "A200"],
        ),
        RiskEntry(
            risk_id="R002",
            name="Material shortage",
            category="schedule",
            probability=0.3,
            impact_days=10,
            impact_cost=30000,
            status="open",
            affected_activities=["A300"],
        ),
        RiskEntry(
            risk_id="R003",
            name="Design change",
            category="scope",
            probability=0.2,
            impact_days=20,
            impact_cost=100000,
            status="mitigated",
            mitigation="Freeze design at 60% completion",
        ),
        RiskEntry(
            risk_id="R004",
            name="Equipment failure",
            category="schedule",
            probability=0.4,
            impact_days=5,
            status="open",
            affected_activities=["A100"],
        ),
        RiskEntry(
            risk_id="R005",
            name="Permit delay",
            category="external",
            probability=0.8,
            impact_days=30,
            status="closed",
        ),
    ]


class TestSummarize:
    def test_returns_summary(self) -> None:
        result = summarize_register(_sample_entries())
        assert isinstance(result, RiskRegisterSummary)

    def test_counts(self) -> None:
        result = summarize_register(_sample_entries())
        assert result.total_risks == 5
        assert result.open_risks == 3
        assert result.mitigated_risks == 1
        assert result.closed_risks == 1

    def test_expected_impact(self) -> None:
        result = summarize_register(_sample_entries())
        # R001: 0.6*15=9, R002: 0.3*10=3, R004: 0.4*5=2 = 14 days
        assert result.total_expected_impact_days == 14.0

    def test_expected_cost(self) -> None:
        result = summarize_register(_sample_entries())
        # R001: 0.6*50000=30000, R002: 0.3*30000=9000, R004: 0 = 39000
        assert result.total_expected_impact_cost == 39000.0

    def test_risk_score_bounded(self) -> None:
        result = summarize_register(_sample_entries())
        assert 0 <= result.risk_score <= 100

    def test_categories(self) -> None:
        result = summarize_register(_sample_entries())
        assert result.categories["external"] == 2
        assert result.categories["schedule"] == 2

    def test_top_risks_sorted(self) -> None:
        result = summarize_register(_sample_entries())
        expected_days = [r["expected_days"] for r in result.top_risks]
        assert expected_days == sorted(expected_days, reverse=True)

    def test_empty_register(self) -> None:
        result = summarize_register([])
        assert result.total_risks == 0
        assert result.risk_score == 0

    def test_methodology_set(self) -> None:
        result = summarize_register(_sample_entries())
        assert "risk register" in result.methodology.lower()


class TestRegisterToRiskEvents:
    def test_converts_open_with_activities(self) -> None:
        events = register_to_risk_events(_sample_entries())
        # R001 (open, has activities), R002 (open, has activities), R004 (open, has activities)
        assert len(events) == 3

    def test_skips_closed_and_mitigated(self) -> None:
        events = register_to_risk_events(_sample_entries())
        ids = {e.risk_id for e in events}
        assert "R003" not in ids  # mitigated
        assert "R005" not in ids  # closed

    def test_event_fields(self) -> None:
        events = register_to_risk_events(_sample_entries())
        r001 = next(e for e in events if e.risk_id == "R001")
        assert r001.probability == 0.6
        assert r001.impact_hours == 15 * 8  # days to hours
        assert r001.affected_activities == ["A100", "A200"]

    def test_empty_register(self) -> None:
        events = register_to_risk_events([])
        assert len(events) == 0

    def test_no_activities_skipped(self) -> None:
        entry = RiskEntry(
            risk_id="X", name="No acts", probability=0.5, impact_days=10, status="open"
        )
        events = register_to_risk_events([entry])
        assert len(events) == 0


class TestRiskRegisterCRUDAPI:
    """Endpoint tests for GET/POST/DELETE /api/v1/projects/{id}/risk-register."""

    def test_empty_list(self) -> None:
        from fastapi.testclient import TestClient

        from src.api.app import app
        from src.api.deps import get_store

        get_store().clear()

        client = TestClient(app)
        resp = client.get("/api/v1/projects/some-project/risk-register")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "some-project"
        assert data["entries"] == []
        assert data["summary"]["total_risks"] == 0

    def test_post_and_list(self) -> None:
        from fastapi.testclient import TestClient

        from src.api.app import app
        from src.api.deps import get_store

        get_store().clear()
        client = TestClient(app)

        body = {
            "risk_id": "R001",
            "name": "Weather delay",
            "category": "external",
            "probability": 0.6,
            "impact_days": 15,
            "status": "open",
            "affected_activities": ["A100", "A200"],
        }
        resp = client.post("/api/v1/projects/p1/risk-register", json=body)
        assert resp.status_code == 200, resp.text
        assert resp.json()["entry"]["risk_id"] == "R001"

        resp = client.get("/api/v1/projects/p1/risk-register")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["name"] == "Weather delay"
        assert data["summary"]["total_risks"] == 1
        assert data["summary"]["open_risks"] == 1

    def test_post_auto_assigns_risk_id(self) -> None:
        from fastapi.testclient import TestClient

        from src.api.app import app
        from src.api.deps import get_store

        get_store().clear()
        client = TestClient(app)

        body = {"name": "Auto-id risk", "category": "schedule", "probability": 0.3}
        resp = client.post("/api/v1/projects/p2/risk-register", json=body)
        assert resp.status_code == 200
        assert resp.json()["entry"]["risk_id"] == "R001"

    def test_post_upsert_by_risk_id(self) -> None:
        from fastapi.testclient import TestClient

        from src.api.app import app
        from src.api.deps import get_store

        get_store().clear()
        client = TestClient(app)

        client.post(
            "/api/v1/projects/p3/risk-register",
            json={"risk_id": "R001", "name": "first", "probability": 0.5},
        )
        client.post(
            "/api/v1/projects/p3/risk-register",
            json={"risk_id": "R001", "name": "second", "probability": 0.9},
        )

        resp = client.get("/api/v1/projects/p3/risk-register")
        assert len(resp.json()["entries"]) == 1
        assert resp.json()["entries"][0]["name"] == "second"

    def test_delete(self) -> None:
        from fastapi.testclient import TestClient

        from src.api.app import app
        from src.api.deps import get_store

        get_store().clear()
        client = TestClient(app)

        client.post(
            "/api/v1/projects/p4/risk-register",
            json={"risk_id": "R001", "name": "to delete", "probability": 0.5},
        )

        resp = client.delete("/api/v1/projects/p4/risk-register/R001")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        resp = client.get("/api/v1/projects/p4/risk-register")
        assert resp.json()["entries"] == []

    def test_delete_not_found(self) -> None:
        from fastapi.testclient import TestClient

        from src.api.app import app
        from src.api.deps import get_store

        get_store().clear()
        client = TestClient(app)

        resp = client.delete("/api/v1/projects/p5/risk-register/R999")
        assert resp.status_code == 404


class TestSimulationRegisterLinkage:
    """Integration tests for GET /api/v1/risk/simulations/{id}/register-entries."""

    def test_no_simulation_returns_404(self) -> None:
        from fastapi.testclient import TestClient

        from src.api.app import app
        from src.api.deps import get_store

        get_store().clear()
        client = TestClient(app)

        resp = client.get("/api/v1/risk/simulations/sim-does-not-exist/register-entries")
        assert resp.status_code == 404

    def test_linked_by_activity_overlap(self) -> None:
        from fastapi.testclient import TestClient

        from src.analytics.risk import (
            CriticalityEntry,
            PValueEntry,
            SensitivityEntry,
            SimulationResult,
        )
        from src.api.app import app
        from src.api.deps import get_risk_store, get_store

        store = get_store()
        store.clear()

        # Add two risk register entries — one touching A100, one touching Z999
        client = TestClient(app)
        client.post(
            "/api/v1/projects/p-sim/risk-register",
            json={
                "risk_id": "R001",
                "name": "Weather",
                "probability": 0.5,
                "impact_days": 10,
                "affected_activities": ["A100"],
            },
        )
        client.post(
            "/api/v1/projects/p-sim/risk-register",
            json={
                "risk_id": "R002",
                "name": "Unrelated",
                "probability": 0.3,
                "impact_days": 5,
                "affected_activities": ["Z999"],
            },
        )

        # Seed a simulation where A100 has high sensitivity
        result = SimulationResult(
            project_id="p-sim",
            project_name="Test",
            iterations=100,
            deterministic_days=100.0,
            mean_days=105.0,
            std_days=5.0,
            p_values=[PValueEntry(percentile=50, duration_days=105.0, delta_days=5.0)],
            sensitivity=[
                SensitivityEntry(activity_id="A100", activity_name="Foundation", correlation=0.75),
                SensitivityEntry(activity_id="A200", activity_name="Framing", correlation=0.30),
            ],
            criticality=[
                CriticalityEntry(
                    activity_id="A100", activity_name="Foundation", criticality_pct=95.0
                )
            ],
        )
        sim_id = get_risk_store().add(result)

        resp = client.get(
            f"/api/v1/risk/simulations/{sim_id}/register-entries",
            params={"top_n": 5},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["project_id"] == "p-sim"
        # Only R001 overlaps (A100); R002 touches Z999 which is not in the sim
        assert data["total"] == 1
        assert data["entries"][0]["risk_id"] == "R001"
        # driver_activities should include A100
        assert "A100" in data["driver_activities"]
        # matched_activities must include the sensitivity/criticality metrics
        matched = data["entries"][0]["matched_activities"]
        assert any(m["activity"] == "A100" for m in matched)
        hit = next(m for m in matched if m["activity"] == "A100")
        assert hit["sensitivity"] == 0.75
        assert hit["criticality_pct"] == 95.0

    def test_no_overlap_returns_empty(self) -> None:
        from fastapi.testclient import TestClient

        from src.analytics.risk import (
            PValueEntry,
            SensitivityEntry,
            SimulationResult,
        )
        from src.api.app import app
        from src.api.deps import get_risk_store, get_store

        store = get_store()
        store.clear()

        client = TestClient(app)
        client.post(
            "/api/v1/projects/p-no-overlap/risk-register",
            json={
                "risk_id": "R001",
                "name": "Isolated",
                "probability": 0.5,
                "impact_days": 10,
                "affected_activities": ["X1"],
            },
        )

        result = SimulationResult(
            project_id="p-no-overlap",
            project_name="Test",
            iterations=100,
            deterministic_days=100.0,
            mean_days=100.0,
            std_days=1.0,
            p_values=[PValueEntry(percentile=50, duration_days=100.0, delta_days=0.0)],
            sensitivity=[
                SensitivityEntry(activity_id="Y2", activity_name="Other", correlation=0.9)
            ],
        )
        sim_id = get_risk_store().add(result)

        resp = client.get(f"/api/v1/risk/simulations/{sim_id}/register-entries")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["entries"] == []
