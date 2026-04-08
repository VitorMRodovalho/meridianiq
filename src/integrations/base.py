# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Base adapter protocol for ERP/PMIS integrations.

All ERP connectors must satisfy this ``Protocol`` so that the cost
router can call them polymorphically.  Adapters are stateless —
they receive configuration and return normalized dicts matching
the DB table columns defined in migration 019.

Reference: AACE RP 10S-90 (Cost Engineering Terminology),
           ANSI/EIA-748 (EVMS), ISO 21511 (WBS).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ERPAdapter(Protocol):
    """Protocol that every ERP/PMIS connector must implement.

    Each method returns normalized dicts ready for Supabase insert.
    The keys must match the column names in migration 019 tables.
    """

    @property
    def source_system(self) -> str:
        """Identifier for this adapter (e.g. 'primavera_unifier')."""
        ...

    def test_connection(self) -> bool:
        """Verify that the external system is reachable.

        Returns True if the connection succeeds, False otherwise.
        """
        ...

    def sync_cbs(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch CBS hierarchy from the external system.

        Returns dicts with keys matching ``cbs_elements`` table columns:
        cbs_code, cbs_description, cbs_level, parent_cbs_code,
        coding_system, masterformat_code, uniformat_code,
        source_record_id, sort_order.
        """
        ...

    def sync_cost_snapshots(
        self, project_id: str, as_of: date
    ) -> list[dict[str, Any]]:
        """Fetch cost snapshot data as of a specific date.

        Returns dicts with keys matching ``cost_snapshots`` table columns:
        cbs_code, snapshot_date, original_budget, approved_changes,
        current_budget, committed_cost, actual_cost, estimate_to_complete,
        estimate_at_completion, bcws, bcwp, acwp, contingency_original,
        contingency_remaining, escalation, source_record_id.
        """
        ...

    def sync_change_orders(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch change orders from the external system.

        Returns dicts with keys matching ``change_orders`` table columns:
        change_id, change_type, status, title, description,
        requested_amount, approved_amount, effective_date,
        submitted_date, approved_date, cbs_code, source_record_id.
        """
        ...

    def sync_time_phased(
        self,
        project_id: str,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        """Fetch time-phased cost data for a date range.

        Returns dicts with keys matching ``cost_time_phased`` table columns:
        cbs_code, period_start, period_end, budget_this_period,
        actual_this_period, forecast_this_period, committed_this_period,
        cumulative_budget, cumulative_actual, cumulative_forecast,
        resource_type.
        """
        ...

    def get_last_sync_time(self, project_id: str) -> datetime | None:
        """Return the timestamp of the last successful sync, or None."""
        ...
