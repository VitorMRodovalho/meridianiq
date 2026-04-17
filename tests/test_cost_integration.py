"""Tests for cost-schedule integration engine."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.analytics.cost_integration import (
    CBSElement,
    CBSWBSMapping,
    CostIntegrationResult,
    WBSBudget,
    _generate_insights,
    compare_cost_snapshots,
)
from src.api.app import app
from src.database.store import InMemoryStore


class TestCBSElements:
    """Test CBS element data structure."""

    def test_budget_calculation(self) -> None:
        elem = CBSElement(
            cbs_code="C.SP.100123",
            estimate=1_000_000.0,
            contingency=250_000.0,
            escalation=50_000.0,
        )
        elem.budget = elem.estimate + elem.contingency + elem.escalation
        assert elem.budget == 1_300_000.0

    def test_cbs_code_format(self) -> None:
        elem = CBSElement(cbs_code="Construction.Package A")
        assert "." in elem.cbs_code


class TestWBSBudget:
    """Test WBS budget data."""

    def test_wbs_budget(self) -> None:
        wbs = WBSBudget(wbs_code="100123", total_budget=1_730_000_000.0)
        assert wbs.total_budget == 1_730_000_000.0


class TestCBSWBSMapping:
    """Test CBS-WBS mapping."""

    def test_mapping(self) -> None:
        m = CBSWBSMapping(
            cost_category="Design",
            cbs_code="C.EN.201278",
            wbs_level1="Labor: external professional fees",
        )
        assert m.cbs_code.startswith("C.")


class TestInsights:
    """Test insight generation."""

    def test_total_estimate_insight(self) -> None:
        result = CostIntegrationResult(
            cbs_elements=[
                CBSElement(
                    cbs_code="Construction", cbs_level1="Construction", estimate=3_000_000_000
                ),
                CBSElement(cbs_code="Design", cbs_level1="Design", estimate=500_000_000),
            ]
        )
        _generate_insights(result)
        assert any("Total estimate" in i for i in result.insights)

    def test_contingency_insight(self) -> None:
        result = CostIntegrationResult(
            total_budget=1_000_000_000,
            total_contingency=250_000_000,
        )
        _generate_insights(result)
        assert any("Contingency" in i for i in result.insights)

    def test_wbs_budget_insight(self) -> None:
        result = CostIntegrationResult(
            wbs_budgets=[WBSBudget(wbs_code="100123", total_budget=1_730_000_000)]
        )
        _generate_insights(result)
        assert any("WBS 100123" in i for i in result.insights)

    def test_mapping_insight(self) -> None:
        result = CostIntegrationResult(
            cbs_wbs_mappings=[
                CBSWBSMapping(cost_category="Design", cbs_code="C.EN.201278"),
                CBSWBSMapping(cost_category="Construction", cbs_code="C.SP.100123"),
            ]
        )
        _generate_insights(result)
        assert any("mappings" in i for i in result.insights)

    def test_empty_result_no_crash(self) -> None:
        result = CostIntegrationResult()
        _generate_insights(result)
        assert result.insights == []


class TestCostPersistence:
    """Round-trip tests for save_cost_upload / list_cost_snapshots."""

    def _sample_result(self) -> CostIntegrationResult:
        return CostIntegrationResult(
            cbs_elements=[
                CBSElement(
                    cbs_code="C.SP.100123",
                    cbs_level1="Construction",
                    cbs_level2="Structural",
                    scope="Foundations",
                    wbs_code="100123",
                    estimate=1_000_000.0,
                    contingency=250_000.0,
                    escalation=50_000.0,
                    budget=1_300_000.0,
                ),
                CBSElement(
                    cbs_code="C.EN.200",
                    cbs_level1="Engineering",
                    estimate=500_000.0,
                    contingency=125_000.0,
                    escalation=25_000.0,
                    budget=650_000.0,
                ),
            ],
            wbs_budgets=[WBSBudget(wbs_code="100123", total_budget=1_300_000.0)],
            cbs_wbs_mappings=[
                CBSWBSMapping(cost_category="Design", cbs_code="C.EN.200", wbs_level1="Labor")
            ],
            total_budget=1_500_000.0,
            total_contingency=375_000.0,
            total_escalation=75_000.0,
            program_total=1_950_000.0,
            budget_date="2026-04-01",
        )

    def test_save_and_list_in_memory(self) -> None:
        store = InMemoryStore()
        result = self._sample_result()

        snap_id = store.save_cost_upload(
            project_id="proj-1", result=result, user_id="u1", source_name="Q2 Budget"
        )
        assert snap_id.startswith("cost-")

        listed = store.list_cost_snapshots("proj-1", user_id="u1")
        assert len(listed) == 1
        assert listed[0]["snapshot_id"] == snap_id
        assert listed[0]["source_name"] == "Q2 Budget"
        assert listed[0]["cbs_element_count"] == 2
        assert listed[0]["total_budget"] == 1_500_000.0
        assert listed[0]["budget_date"] == "2026-04-01"

    def test_multiple_snapshots_newest_first(self) -> None:
        store = InMemoryStore()
        store.save_cost_upload(project_id="p", result=self._sample_result(), source_name="v1")
        store.save_cost_upload(project_id="p", result=self._sample_result(), source_name="v2")
        store.save_cost_upload(project_id="p", result=self._sample_result(), source_name="v3")

        listed = store.list_cost_snapshots("p")
        assert [s["source_name"] for s in listed] == ["v3", "v2", "v1"]

    def test_isolated_per_project(self) -> None:
        store = InMemoryStore()
        store.save_cost_upload(project_id="a", result=self._sample_result())
        store.save_cost_upload(project_id="b", result=self._sample_result())
        assert len(store.list_cost_snapshots("a")) == 1
        assert len(store.list_cost_snapshots("b")) == 1
        assert len(store.list_cost_snapshots("nonexistent")) == 0

    def test_get_full_snapshot_round_trip(self) -> None:
        store = InMemoryStore()
        original = self._sample_result()
        snap_id = store.save_cost_upload(project_id="p", result=original)
        retrieved = store.get_cost_snapshot("p", snap_id)
        assert retrieved is original  # Same object
        assert len(retrieved.cbs_elements) == 2


class TestCostSnapshotsAPI:
    """Integration test for GET /api/v1/projects/{id}/cost/snapshots."""

    def test_empty_project(self) -> None:
        client = TestClient(app)
        resp = client.get("/api/v1/projects/never-uploaded/cost/snapshots")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "never-uploaded"
        assert data["count"] == 0
        assert data["snapshots"] == []


class TestCostCompare:
    """Unit tests for compare_cost_snapshots."""

    def _snap(
        self,
        elements: list[CBSElement],
        total_budget: float = 0.0,
        total_contingency: float = 0.0,
        total_escalation: float = 0.0,
    ) -> CostIntegrationResult:
        return CostIntegrationResult(
            cbs_elements=elements,
            total_budget=total_budget,
            total_contingency=total_contingency,
            total_escalation=total_escalation,
            program_total=total_budget + total_contingency + total_escalation,
        )

    def test_identical_snapshots_zero_delta(self) -> None:
        elem = CBSElement(cbs_code="C.A.1", cbs_level1="Con", estimate=1000, budget=1200)
        a = self._snap([elem], total_budget=1000)
        b = self._snap(
            [CBSElement(cbs_code="C.A.1", cbs_level1="Con", estimate=1000, budget=1200)],
            total_budget=1000,
        )

        result = compare_cost_snapshots(a, b)

        assert result.total_budget_delta == 0.0
        assert result.budget_variance_pct == 0.0
        assert result.changed_count == 0
        assert result.unchanged_count == 1
        assert result.added_count == 0
        assert result.removed_count == 0

    def test_budget_growth_variance_pct(self) -> None:
        a = self._snap([], total_budget=1_000_000)
        b = self._snap([], total_budget=1_200_000)

        result = compare_cost_snapshots(a, b)

        assert result.total_budget_delta == 200_000
        assert result.budget_variance_pct == 20.0

    def test_added_and_removed_elements(self) -> None:
        a = self._snap(
            [CBSElement(cbs_code="C.A.1", cbs_level1="Con", budget=500_000)],
            total_budget=500_000,
        )
        b = self._snap(
            [CBSElement(cbs_code="C.B.2", cbs_level1="Eng", budget=300_000)],
            total_budget=300_000,
        )

        result = compare_cost_snapshots(a, b)

        assert result.added_count == 1
        assert result.removed_count == 1
        assert result.changed_count == 0
        statuses = {d.cbs_code: d.status for d in result.element_deltas}
        assert statuses == {"C.A.1": "removed", "C.B.2": "added"}

    def test_changed_element_delta(self) -> None:
        a = self._snap(
            [CBSElement(cbs_code="C.A.1", cbs_level1="Con", estimate=1000, budget=1200)],
            total_budget=1000,
        )
        b = self._snap(
            [CBSElement(cbs_code="C.A.1", cbs_level1="Con", estimate=1500, budget=1800)],
            total_budget=1500,
        )

        result = compare_cost_snapshots(a, b)

        assert result.changed_count == 1
        delta = result.element_deltas[0]
        assert delta.budget_delta == 600
        assert delta.estimate_delta == 500
        assert delta.variance_pct == 50.0
        assert delta.status == "changed"

    def test_zero_baseline_budget_avoids_div_by_zero(self) -> None:
        a = self._snap([CBSElement(cbs_code="C.A.1", budget=0.0)], total_budget=0.0)
        b = self._snap([CBSElement(cbs_code="C.A.1", budget=1000.0)], total_budget=1000.0)

        result = compare_cost_snapshots(a, b)

        assert result.budget_variance_pct == 0.0
        assert result.element_deltas[0].variance_pct == 0.0

    def test_insights_flag_large_variance(self) -> None:
        a = self._snap([], total_budget=1_000_000)
        b = self._snap([], total_budget=1_500_000)

        result = compare_cost_snapshots(a, b, snapshot_a_id="cost-0001", snapshot_b_id="cost-0002")

        assert result.snapshot_a == "cost-0001"
        assert result.snapshot_b == "cost-0002"
        assert any("10%" in i for i in result.insights)


class TestCostCompareAPI:
    """Integration test for GET /api/v1/projects/{id}/cost/compare."""

    def test_compare_requires_different_ids(self) -> None:
        client = TestClient(app)
        resp = client.get(
            "/api/v1/projects/p/cost/compare",
            params={"a": "cost-0001", "b": "cost-0001"},
        )
        assert resp.status_code == 400
        assert "differ" in resp.json()["detail"]

    def test_compare_missing_snapshots_404(self) -> None:
        client = TestClient(app)
        resp = client.get(
            "/api/v1/projects/never-uploaded/cost/compare",
            params={"a": "cost-9998", "b": "cost-9999"},
        )
        assert resp.status_code == 404
        assert "not retrievable" in resp.json()["detail"]

    def test_compare_roundtrip_in_memory(self) -> None:
        from src.api.deps import get_store as _get_store

        store = _get_store()

        a = CostIntegrationResult(
            cbs_elements=[
                CBSElement(cbs_code="C.A.1", cbs_level1="Con", estimate=1000, budget=1200),
            ],
            total_budget=1_000_000,
        )
        b = CostIntegrationResult(
            cbs_elements=[
                CBSElement(cbs_code="C.A.1", cbs_level1="Con", estimate=1500, budget=1800),
                CBSElement(cbs_code="C.B.2", cbs_level1="Eng", estimate=500, budget=600),
            ],
            total_budget=1_250_000,
        )

        id_a = store.save_cost_upload(project_id="compare-test", result=a, source_name="v1")
        id_b = store.save_cost_upload(project_id="compare-test", result=b, source_name="v2")

        client = TestClient(app)
        resp = client.get(
            "/api/v1/projects/compare-test/cost/compare",
            params={"a": id_a, "b": id_b},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["project_id"] == "compare-test"
        assert data["snapshot_a"] == id_a
        assert data["snapshot_b"] == id_b
        assert data["total_budget_delta"] == 250_000
        assert data["added_count"] == 1
        assert data["changed_count"] == 1
        assert data["removed_count"] == 0
