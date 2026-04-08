# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for ERP adapter protocol and manual adapter implementation."""

from __future__ import annotations

from datetime import date

import pytest

from src.integrations.base import ERPAdapter
from src.integrations.manual import ManualAdapter


class TestERPAdapterProtocol:
    """Verify all adapters satisfy the ERPAdapter protocol."""

    def test_manual_adapter_satisfies_protocol(self) -> None:
        assert isinstance(ManualAdapter(), ERPAdapter)

    def test_primavera_unifier_satisfies_protocol(self) -> None:
        from src.integrations.primavera_unifier import PrimaveraUnifierAdapter

        assert isinstance(PrimaveraUnifierAdapter(), ERPAdapter)

    def test_sap_ps_satisfies_protocol(self) -> None:
        from src.integrations.sap_ps import SAPPSAdapter

        assert isinstance(SAPPSAdapter(), ERPAdapter)

    def test_kahua_satisfies_protocol(self) -> None:
        from src.integrations.kahua import KahuaAdapter

        assert isinstance(KahuaAdapter(), ERPAdapter)

    def test_ebuilder_satisfies_protocol(self) -> None:
        from src.integrations.ebuilder import EBuilderAdapter

        assert isinstance(EBuilderAdapter(), ERPAdapter)

    def test_ineight_satisfies_protocol(self) -> None:
        from src.integrations.ineight import InEightAdapter

        assert isinstance(InEightAdapter(), ERPAdapter)

    def test_procore_satisfies_protocol(self) -> None:
        from src.integrations.procore import ProcoreAdapter

        assert isinstance(ProcoreAdapter(), ERPAdapter)


class TestPlaceholderAdaptersRaiseNotImplemented:
    """Placeholder adapters should raise NotImplementedError."""

    def test_primavera_unifier(self) -> None:
        from src.integrations.primavera_unifier import PrimaveraUnifierAdapter

        adapter = PrimaveraUnifierAdapter()
        assert adapter.source_system == "primavera_unifier"
        with pytest.raises(NotImplementedError):
            adapter.test_connection()
        with pytest.raises(NotImplementedError):
            adapter.sync_cbs("proj-1")

    def test_sap_ps(self) -> None:
        from src.integrations.sap_ps import SAPPSAdapter

        adapter = SAPPSAdapter()
        assert adapter.source_system == "sap_ps"
        with pytest.raises(NotImplementedError):
            adapter.sync_cost_snapshots("proj-1", date.today())

    def test_kahua(self) -> None:
        from src.integrations.kahua import KahuaAdapter

        adapter = KahuaAdapter()
        assert adapter.source_system == "kahua"
        with pytest.raises(NotImplementedError):
            adapter.sync_change_orders("proj-1")

    def test_ebuilder(self) -> None:
        from src.integrations.ebuilder import EBuilderAdapter

        adapter = EBuilderAdapter()
        assert adapter.source_system == "ebuilder"
        with pytest.raises(NotImplementedError):
            adapter.sync_time_phased("proj-1", date.today(), date.today())

    def test_ineight(self) -> None:
        from src.integrations.ineight import InEightAdapter

        adapter = InEightAdapter()
        assert adapter.source_system == "ineight"
        with pytest.raises(NotImplementedError):
            adapter.get_last_sync_time("proj-1")

    def test_procore(self) -> None:
        from src.integrations.procore import ProcoreAdapter

        adapter = ProcoreAdapter()
        assert adapter.source_system == "procore"
        with pytest.raises(NotImplementedError):
            adapter.test_connection()
        with pytest.raises(NotImplementedError):
            adapter.sync_cbs("proj-1")
        with pytest.raises(NotImplementedError):
            adapter.sync_change_orders("proj-1")


class TestManualAdapter:
    """Tests for the manual Excel/CSV adapter."""

    def test_source_system(self) -> None:
        adapter = ManualAdapter()
        assert adapter.source_system == "manual"

    def test_connection_always_true(self) -> None:
        adapter = ManualAdapter()
        assert adapter.test_connection() is True

    def test_sync_methods_return_empty(self) -> None:
        adapter = ManualAdapter()
        assert adapter.sync_cbs("proj-1") == []
        assert adapter.sync_cost_snapshots("proj-1", date.today()) == []
        assert adapter.sync_change_orders("proj-1") == []
        assert adapter.sync_time_phased("proj-1", date(2026, 1, 1), date(2026, 12, 31)) == []
        assert adapter.get_last_sync_time("proj-1") is None
