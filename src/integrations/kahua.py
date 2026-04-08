# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Kahua adapter — placeholder for future integration.

Kahua is a construction project management platform built on a
"data pool" architecture — a centralized repository where all
project data (cost, schedule, documents, RFIs) is stored once and
accessed by multiple applications.  This adapter targets the Kahua
Open API for bidirectional cost data synchronization with MeridianIQ.

API documentation:
    https://resources.kahua.com/blog/kahua-integrations-and-open-api-because-one-size-does-not-fit-all

Authentication:
    Kahua API uses OAuth 2.0 with authorization code or client
    credentials grant.  API keys are provisioned per-domain through
    the Kahua Administration Console.

Field mapping (Kahua → MeridianIQ normalized schema):
    ┌──────────────────────────────┬────────────────────────────────┐
    │ Kahua Field                  │ MeridianIQ Column              │
    ├──────────────────────────────┼────────────────────────────────┤
    │ Cost Code                    │ cbs_code                       │
    │ Cost Code Description        │ cbs_description                │
    │ Cost Code Level              │ cbs_level                      │
    │ Parent Cost Code             │ parent_cbs_code                │
    │ MasterFormat Division        │ masterformat_code              │
    │ UniFormat Category           │ uniformat_code                 │
    │ Original Budget              │ original_budget                │
    │ Approved Changes             │ approved_changes               │
    │ Current Budget               │ current_budget                 │
    │ Committed Cost               │ committed_cost                 │
    │ Actual Cost                  │ actual_cost                    │
    │ Estimate to Complete         │ estimate_to_complete           │
    │ Estimate at Completion       │ estimate_at_completion         │
    │ Change Order ID              │ change_id                      │
    │ CO Type                      │ change_type                    │
    │ CO Status                    │ status                         │
    │ CO Title                     │ title                          │
    │ CO Requested Amount          │ requested_amount               │
    │ CO Approved Amount           │ approved_amount                │
    │ Period Budget                │ budget_this_period             │
    │ Period Actual                │ actual_this_period             │
    │ Period Forecast              │ forecast_this_period           │
    │ Data Pool Record ID          │ source_record_id               │
    └──────────────────────────────┴────────────────────────────────┘

Key Kahua concepts:
    - Data Pool: centralized repository — single source of truth
    - Apps: domain-specific views (cost, schedule, procurement)
    - Bidirectional Sync: changes propagate back to source systems
    - Pre-built Integrations: connectors for P6, Procore, SAP, etc.
    - Domains: tenant isolation with cross-domain data sharing

Reference:
    AACE RP 10S-90 (Cost Engineering Terminology)
    AACE RP 21R-98 (Project Code of Accounts)
    ANSI/EIA-748 (Earned Value Management Systems)
    CSI MasterFormat 2020 (cost code classification)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


class KahuaAdapter:
    """Kahua data pool cost data adapter.

    Connects to the Kahua Open API to synchronize cost codes,
    budgets, change orders, and time-phased data into the
    MeridianIQ normalized cost schema.

    Not yet implemented — all methods raise ``NotImplementedError``.
    """

    @property
    def source_system(self) -> str:
        """Identifier for this adapter."""
        return "kahua"

    @property
    def supported_domains(self) -> list[str]:
        """Domains supported by Kahua: cost, reporting.

        Note: Kahua has no public schedule API.
        """
        return ["cost", "reporting"]

    def test_connection(self) -> bool:
        """Verify connectivity to the Kahua Open API.

        Will authenticate via OAuth 2.0 and call the domain health
        endpoint to validate credentials and domain access.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError(
            "Kahua adapter is a placeholder. "
            "See https://resources.kahua.com/blog/"
            "kahua-integrations-and-open-api-because-one-size-does-not-fit-all"
        )

    def sync_cbs(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch CBS hierarchy from the Kahua data pool.

        Will query the cost code structure from the centralized
        data pool and map Kahua Cost Code → ``cbs_code``.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("Kahua CBS sync not yet implemented.")

    def sync_cost_snapshots(self, project_id: str, as_of: date) -> list[dict[str, Any]]:
        """Fetch cost snapshot from the Kahua cost app.

        Will query budget, committed, and actual values from the
        cost data pool, filtered by snapshot date.

        Args:
            project_id: MeridianIQ project UUID.
            as_of: Snapshot reference date.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("Kahua cost snapshot sync not yet implemented.")

    def sync_change_orders(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch change orders from the Kahua change management app.

        Will query change order records from the data pool and
        extract ID, title, status, amounts, and dates.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("Kahua change order sync not yet implemented.")

    def sync_time_phased(
        self,
        project_id: str,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        """Fetch time-phased cost data from the Kahua data pool.

        Will query periodic budget, actual, and forecast values
        by cost code for the specified date range.

        Args:
            project_id: MeridianIQ project UUID.
            period_start: Start of the reporting period.
            period_end: End of the reporting period.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("Kahua time-phased sync not yet implemented.")

    def get_last_sync_time(self, project_id: str) -> datetime | None:
        """Return the timestamp of the last successful Kahua sync.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("Kahua last-sync tracking not yet implemented.")

    # ------------------------------------------------------------------ #
    # Reporting domain (ReportingAdapter protocol)                       #
    # ------------------------------------------------------------------ #

    def sync_daily_logs(
        self,
        project_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch daily log entries from the Kahua data pool.

        Will query the Kahua form-based API to retrieve daily field
        reports including weather, crew counts, and work descriptions.

        Args:
            project_id: MeridianIQ project UUID.
            start_date: Start of the reporting period.
            end_date: End of the reporting period.

        Raises:
            NotImplementedError: Adapter not yet implemented.

        Reference:
            AGC ConsensusDocs, AIA A201 (General Conditions).
        """
        raise NotImplementedError(
            "Kahua daily log sync not yet implemented. See Kahua form-based API — daily log forms."
        )

    def sync_rfis(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch RFIs from the Kahua data pool.

        Will query the Kahua form-based API to retrieve RFI records
        with status, dates, responsible parties, and impact data.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError(
            "Kahua RFI sync not yet implemented. See Kahua form-based API — RFI forms."
        )

    def sync_submittals(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch submittals from the Kahua data pool.

        Will query the Kahua form-based API to retrieve submittal
        records with spec sections, status, and lead time data.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError(
            "Kahua submittal sync not yet implemented. See Kahua form-based API — submittal forms."
        )
