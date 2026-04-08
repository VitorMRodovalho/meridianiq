# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Oracle Primavera Unifier adapter — placeholder for future integration.

Oracle Primavera Unifier is an enterprise capital project lifecycle
management platform that manages costs, contracts, cash flows, change
orders, and business processes.  This adapter targets the Unifier
REST/SOAP Web Services API to synchronize cost data with MeridianIQ.

API documentation:
    https://docs.oracle.com/cd/F74686_01/10296222.htm

Authentication:
    Unifier REST API uses OAuth 2.0 with client credentials grant type.
    The SOAP API supports WS-Security with UsernameToken.  Both require
    an administrative account with the "Web Services" permission in
    Unifier's user administration.

Field mapping (Unifier → MeridianIQ normalized schema):
    ┌──────────────────────────────┬────────────────────────────────┐
    │ Unifier Field                │ MeridianIQ Column              │
    ├──────────────────────────────┼────────────────────────────────┤
    │ Cost Code (uuu_cost_code)    │ cbs_code                       │
    │ Cost Code Description        │ cbs_description                │
    │ Cost Code Level              │ cbs_level                      │
    │ Parent Cost Code             │ parent_cbs_code                │
    │ WBS Code (uuu_wbs_code)      │ wbs_code (cbs_wbs_mappings)    │
    │ Original Budget              │ original_budget                │
    │ Approved Changes             │ approved_changes               │
    │ Current Budget               │ current_budget                 │
    │ Committed Cost               │ committed_cost                 │
    │ Actual Cost                  │ actual_cost                    │
    │ Estimate to Complete (ETC)   │ estimate_to_complete           │
    │ Estimate at Completion (EAC) │ estimate_at_completion         │
    │ BCWS / Planned Value         │ bcws                           │
    │ BCWP / Earned Value          │ bcwp                           │
    │ ACWP / Actual Cost           │ acwp                           │
    │ Change Order ID              │ change_id                      │
    │ Change Type                  │ change_type                    │
    │ Change Status                │ status                         │
    │ Change Title                 │ title                          │
    │ Requested Amount             │ requested_amount               │
    │ Approved Amount              │ approved_amount                │
    │ Fund Code                    │ resource_type (time-phased)    │
    │ Record Number (sys field)    │ source_record_id               │
    └──────────────────────────────┴────────────────────────────────┘

Key Unifier entities:
    - Cost Sheets: tabular cost breakdown with rows per cost code
    - Business Process Forms: change orders, RFIs, invoices
    - Fund Consumption: time-phased cash flow by fund/account
    - Shell Structure: hierarchical project container (maps to WBS)

Reference:
    AACE RP 10S-90 (Cost Engineering Terminology)
    AACE RP 21R-98 (Project Code of Accounts)
    ANSI/EIA-748 (Earned Value Management Systems)
    PMI Practice Standard for Earned Value Management (3rd ed.)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


class PrimaveraUnifierAdapter:
    """Oracle Primavera Unifier cost data adapter.

    Connects to Unifier REST/SOAP Web Services to synchronize cost
    sheets, business process forms, and fund consumption data into
    the MeridianIQ normalized cost schema.

    Not yet implemented — all methods raise ``NotImplementedError``.
    """

    @property
    def source_system(self) -> str:
        """Identifier for this adapter."""
        return "primavera_unifier"

    def test_connection(self) -> bool:
        """Verify connectivity to the Unifier REST API.

        Will authenticate via OAuth 2.0 client credentials and call
        the ``/ws/rest/v1/admin/health`` endpoint.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError(
            "Primavera Unifier adapter is a placeholder. "
            "See https://docs.oracle.com/cd/F74686_01/10296222.htm"
        )

    def sync_cbs(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch CBS hierarchy from Unifier cost sheets.

        Will call ``/ws/rest/v1/costsheet/{shell_number}`` to retrieve
        cost code structure and map ``uuu_cost_code`` → ``cbs_code``.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("Primavera Unifier CBS sync not yet implemented.")

    def sync_cost_snapshots(self, project_id: str, as_of: date) -> list[dict[str, Any]]:
        """Fetch cost snapshot from Unifier cost sheet as of a date.

        Will query cost sheet columns for budget, committed, actual,
        and EVM values, filtered by the snapshot date.

        Args:
            project_id: MeridianIQ project UUID.
            as_of: Snapshot reference date.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("Primavera Unifier cost snapshot sync not yet implemented.")

    def sync_change_orders(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch change orders from Unifier business process forms.

        Will query the configured change order BP type and extract
        fields: record number, title, status, amounts, and dates.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("Primavera Unifier change order sync not yet implemented.")

    def sync_time_phased(
        self,
        project_id: str,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        """Fetch time-phased cost data from Unifier fund consumption.

        Will query ``/ws/rest/v1/cashflow/{shell_number}`` for
        periodic budget, actual, and forecast values by cost code.

        Args:
            project_id: MeridianIQ project UUID.
            period_start: Start of the reporting period.
            period_end: End of the reporting period.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("Primavera Unifier time-phased sync not yet implemented.")

    def get_last_sync_time(self, project_id: str) -> datetime | None:
        """Return the timestamp of the last successful Unifier sync.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("Primavera Unifier last-sync tracking not yet implemented.")
