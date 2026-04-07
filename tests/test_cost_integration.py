"""Tests for cost-schedule integration engine."""

from __future__ import annotations

from src.analytics.cost_integration import (
    CBSElement,
    CBSWBSMapping,
    CostIntegrationResult,
    WBSBudget,
    _generate_insights,
)


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
