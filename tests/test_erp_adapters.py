# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for ERP adapter multi-domain protocol system.

Verifies:
1. All adapters satisfy the base ERPAdapter protocol
2. Each adapter satisfies domain-specific protocols it declares
3. Domain declarations match actual method availability
4. Placeholder methods raise NotImplementedError
5. Manual adapter (only real implementation) works correctly
"""

from __future__ import annotations

from datetime import date

import pytest

from src.integrations.base import (
    CostAdapter,
    ERPAdapter,
    ReportingAdapter,
    ResourceAdapter,
    RiskAdapter,
    ScheduleAdapter,
)
from src.integrations.manual import ManualAdapter


# ------------------------------------------------------------------ #
# Base ERPAdapter protocol compliance                                #
# ------------------------------------------------------------------ #


class TestERPAdapterProtocol:
    """Verify all adapters satisfy the base ERPAdapter protocol."""

    def test_manual(self) -> None:
        assert isinstance(ManualAdapter(), ERPAdapter)

    def test_procore(self) -> None:
        from src.integrations.procore import ProcoreAdapter

        assert isinstance(ProcoreAdapter(), ERPAdapter)

    def test_primavera_unifier(self) -> None:
        from src.integrations.primavera_unifier import PrimaveraUnifierAdapter

        assert isinstance(PrimaveraUnifierAdapter(), ERPAdapter)

    def test_ineight(self) -> None:
        from src.integrations.ineight import InEightAdapter

        assert isinstance(InEightAdapter(), ERPAdapter)

    def test_sap_ps(self) -> None:
        from src.integrations.sap_ps import SAPPSAdapter

        assert isinstance(SAPPSAdapter(), ERPAdapter)

    def test_kahua(self) -> None:
        from src.integrations.kahua import KahuaAdapter

        assert isinstance(KahuaAdapter(), ERPAdapter)

    def test_ebuilder(self) -> None:
        from src.integrations.ebuilder import EBuilderAdapter

        assert isinstance(EBuilderAdapter(), ERPAdapter)


# ------------------------------------------------------------------ #
# Domain-specific protocol compliance                                #
# ------------------------------------------------------------------ #


class TestDomainProtocols:
    """Verify each adapter satisfies the domain protocols it declares."""

    def test_procore_all_domains(self) -> None:
        from src.integrations.procore import ProcoreAdapter

        adapter = ProcoreAdapter()
        assert "cost" in adapter.supported_domains
        assert "schedule" in adapter.supported_domains
        assert "risk" in adapter.supported_domains
        assert "reporting" in adapter.supported_domains
        assert "resource" in adapter.supported_domains
        assert isinstance(adapter, CostAdapter)
        assert isinstance(adapter, ScheduleAdapter)
        assert isinstance(adapter, RiskAdapter)
        assert isinstance(adapter, ReportingAdapter)
        assert isinstance(adapter, ResourceAdapter)

    def test_unifier_cost_risk_reporting(self) -> None:
        from src.integrations.primavera_unifier import PrimaveraUnifierAdapter

        adapter = PrimaveraUnifierAdapter()
        assert adapter.supported_domains == ["cost", "risk", "reporting"]
        assert isinstance(adapter, CostAdapter)
        assert isinstance(adapter, RiskAdapter)
        assert isinstance(adapter, ReportingAdapter)

    def test_ineight_cost_schedule_resource(self) -> None:
        from src.integrations.ineight import InEightAdapter

        adapter = InEightAdapter()
        assert adapter.supported_domains == ["cost", "schedule", "resource"]
        assert isinstance(adapter, CostAdapter)
        assert isinstance(adapter, ScheduleAdapter)
        assert isinstance(adapter, ResourceAdapter)

    def test_sap_cost_schedule_resource(self) -> None:
        from src.integrations.sap_ps import SAPPSAdapter

        adapter = SAPPSAdapter()
        assert adapter.supported_domains == ["cost", "schedule", "resource"]
        assert isinstance(adapter, CostAdapter)
        assert isinstance(adapter, ScheduleAdapter)
        assert isinstance(adapter, ResourceAdapter)

    def test_kahua_cost_reporting(self) -> None:
        from src.integrations.kahua import KahuaAdapter

        adapter = KahuaAdapter()
        assert adapter.supported_domains == ["cost", "reporting"]
        assert isinstance(adapter, CostAdapter)
        assert isinstance(adapter, ReportingAdapter)

    def test_ebuilder_cost_reporting(self) -> None:
        from src.integrations.ebuilder import EBuilderAdapter

        adapter = EBuilderAdapter()
        assert adapter.supported_domains == ["cost", "reporting"]
        assert isinstance(adapter, CostAdapter)
        assert isinstance(adapter, ReportingAdapter)

    def test_manual_cost_only(self) -> None:
        adapter = ManualAdapter()
        assert adapter.supported_domains == ["cost"]
        assert isinstance(adapter, CostAdapter)


# ------------------------------------------------------------------ #
# Placeholder stubs raise NotImplementedError                        #
# ------------------------------------------------------------------ #


class TestPlaceholderStubs:
    """Placeholder adapters should raise NotImplementedError on all methods."""

    def test_procore_cost_stubs(self) -> None:
        from src.integrations.procore import ProcoreAdapter

        adapter = ProcoreAdapter()
        with pytest.raises(NotImplementedError):
            adapter.sync_cbs("p1")
        with pytest.raises(NotImplementedError):
            adapter.sync_cost_snapshots("p1", date.today())
        with pytest.raises(NotImplementedError):
            adapter.sync_change_orders("p1")

    def test_procore_schedule_stubs(self) -> None:
        from src.integrations.procore import ProcoreAdapter

        adapter = ProcoreAdapter()
        with pytest.raises(NotImplementedError):
            adapter.sync_activities("p1")
        with pytest.raises(NotImplementedError):
            adapter.sync_milestones("p1")

    def test_procore_risk_stubs(self) -> None:
        from src.integrations.procore import ProcoreAdapter

        adapter = ProcoreAdapter()
        with pytest.raises(NotImplementedError):
            adapter.sync_risk_register("p1")

    def test_procore_reporting_stubs(self) -> None:
        from src.integrations.procore import ProcoreAdapter

        adapter = ProcoreAdapter()
        with pytest.raises(NotImplementedError):
            adapter.sync_daily_logs("p1", date.today(), date.today())
        with pytest.raises(NotImplementedError):
            adapter.sync_rfis("p1")
        with pytest.raises(NotImplementedError):
            adapter.sync_submittals("p1")

    def test_procore_resource_stubs(self) -> None:
        from src.integrations.procore import ProcoreAdapter

        adapter = ProcoreAdapter()
        with pytest.raises(NotImplementedError):
            adapter.sync_resources("p1")
        with pytest.raises(NotImplementedError):
            adapter.sync_timesheets("p1", date.today(), date.today())

    def test_unifier_risk_stubs(self) -> None:
        from src.integrations.primavera_unifier import PrimaveraUnifierAdapter

        adapter = PrimaveraUnifierAdapter()
        with pytest.raises(NotImplementedError):
            adapter.sync_risk_register("p1")

    def test_unifier_reporting_stubs(self) -> None:
        from src.integrations.primavera_unifier import PrimaveraUnifierAdapter

        adapter = PrimaveraUnifierAdapter()
        with pytest.raises(NotImplementedError):
            adapter.sync_daily_logs("p1", date.today(), date.today())
        with pytest.raises(NotImplementedError):
            adapter.sync_rfis("p1")

    def test_ineight_schedule_stubs(self) -> None:
        from src.integrations.ineight import InEightAdapter

        adapter = InEightAdapter()
        with pytest.raises(NotImplementedError):
            adapter.sync_activities("p1")
        with pytest.raises(NotImplementedError):
            adapter.sync_relationships("p1")

    def test_sap_schedule_stubs(self) -> None:
        from src.integrations.sap_ps import SAPPSAdapter

        adapter = SAPPSAdapter()
        with pytest.raises(NotImplementedError):
            adapter.sync_activities("p1")
        with pytest.raises(NotImplementedError):
            adapter.sync_resources("p1")

    def test_kahua_reporting_stubs(self) -> None:
        from src.integrations.kahua import KahuaAdapter

        adapter = KahuaAdapter()
        with pytest.raises(NotImplementedError):
            adapter.sync_rfis("p1")

    def test_ebuilder_reporting_stubs(self) -> None:
        from src.integrations.ebuilder import EBuilderAdapter

        adapter = EBuilderAdapter()
        with pytest.raises(NotImplementedError):
            adapter.sync_submittals("p1")


# ------------------------------------------------------------------ #
# Manual adapter (real implementation)                               #
# ------------------------------------------------------------------ #


class TestManualAdapter:
    """Tests for the manual Excel/CSV adapter — the only real implementation."""

    def test_source_system(self) -> None:
        adapter = ManualAdapter()
        assert adapter.source_system == "manual"

    def test_supported_domains(self) -> None:
        adapter = ManualAdapter()
        assert adapter.supported_domains == ["cost"]

    def test_connection_always_true(self) -> None:
        adapter = ManualAdapter()
        assert adapter.test_connection() is True

    def test_cost_sync_methods_return_empty(self) -> None:
        adapter = ManualAdapter()
        assert adapter.sync_cbs("proj-1") == []
        assert adapter.sync_cost_snapshots("proj-1", date.today()) == []
        assert adapter.sync_change_orders("proj-1") == []
        assert adapter.sync_time_phased("proj-1", date(2026, 1, 1), date(2026, 12, 31)) == []

    def test_last_sync_time_none(self) -> None:
        adapter = ManualAdapter()
        assert adapter.get_last_sync_time("proj-1") is None
