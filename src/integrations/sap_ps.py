# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""SAP PS (Project System) adapter — placeholder for future integration.

SAP PS is the project management module within SAP S/4HANA (and ECC)
used for planning, budgeting, and controlling capital projects.  This
adapter targets the SAP integration layer via IDoc, BAPI, or oData
services to synchronize WBS elements, cost planning, and controlling
objects with MeridianIQ.

Integration approaches:
    - **oData V2/V4**: ``/sap/opu/odata/sap/`` service endpoints
      (preferred for cloud-to-cloud integration)
    - **BAPI**: ``BAPI_BUS2054_*`` (WBS elements), ``BAPI_COSTACTPLN_*``
      (cost activity planning), ``BAPI_PROJECT_MAINTAIN``
    - **IDoc**: ``PROACT05`` (project/WBS), ``ACC_DOCUMENT05`` (actuals)
    - **CPI/BTP**: SAP Integration Suite middleware for modern landscapes

SAP PS documentation:
    https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/project-system
    https://api.sap.com/ (SAP Business Accelerator Hub — oData catalogs)

Authentication:
    oData services use OAuth 2.0 (SAP BTP) or Basic Auth (on-premise).
    BAPI/RFC connections use SAP JCo or PyRFC with SNC encryption.

Field mapping (SAP PS → MeridianIQ normalized schema):
    ┌───────────────────────────────┬────────────────────────────────┐
    │ SAP PS Field                  │ MeridianIQ Column              │
    ├───────────────────────────────┼────────────────────────────────┤
    │ WBS Element (POSID/PSPNR)     │ cbs_code                       │
    │ WBS Description (POST1)       │ cbs_description                │
    │ WBS Level (STUFE)             │ cbs_level                      │
    │ Parent WBS (PSPNR_PARENT)     │ parent_cbs_code                │
    │ Cost Center (KOSTL)           │ obs_code (via mapping)         │
    │ Controlling Area (KOKRS)      │ coding_system                  │
    │ Plan Total (WTJHR)            │ original_budget                │
    │ Supplement Budget              │ approved_changes               │
    │ Current Budget (Released)      │ current_budget                 │
    │ Commitments (OBLIGO)          │ committed_cost                 │
    │ Actual Costs (WTIST)          │ actual_cost                    │
    │ Plan Remaining (calc.)        │ estimate_to_complete           │
    │ Plan + Actual (calc.)         │ estimate_at_completion         │
    │ Planned Value (BCWS)          │ bcws                           │
    │ Earned Value (BCWP)           │ bcwp                           │
    │ Actual Cost (ACWP)            │ acwp                           │
    │ Change Document Number         │ change_id                      │
    │ Change Category (AESSION)     │ change_type                    │
    │ Network Activity (VORNR)      │ source_record_id               │
    │ Period (PERIO)                │ period_start / period_end      │
    │ Cost Element (KSTAR)          │ resource_type                  │
    └───────────────────────────────┴────────────────────────────────┘

Key SAP PS entities:
    - WBS Elements (PRPS): hierarchical project breakdown
    - Networks & Activities (AFKO/AFVC): scheduling objects
    - Cost Planning (COSP/COSS): plan vs. actual by cost element
    - Project Budget (BPJA): released budget by fiscal year
    - DFM (Document Flow): links procurement to WBS

Reference:
    AACE RP 10S-90 (Cost Engineering Terminology)
    AACE RP 21R-98 (Project Code of Accounts)
    ANSI/EIA-748 (Earned Value Management Systems)
    ISO 21511:2018 (Work Breakdown Structures)
    PMI Practice Standard for Work Breakdown Structures (3rd ed.)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


class SAPPSAdapter:
    """SAP PS (Project System) cost data adapter.

    Connects to SAP S/4HANA or ECC via oData, BAPI, or IDoc to
    synchronize WBS elements, cost planning, and controlling data
    into the MeridianIQ normalized cost schema.

    Not yet implemented — all methods raise ``NotImplementedError``.
    """

    @property
    def source_system(self) -> str:
        """Identifier for this adapter."""
        return "sap_ps"

    @property
    def supported_domains(self) -> list[str]:
        """Domains supported by SAP PS: cost, schedule, resource."""
        return ["cost", "schedule", "resource"]

    def test_connection(self) -> bool:
        """Verify connectivity to the SAP oData service or RFC destination.

        Will attempt an OAuth token request (BTP) or BAPI ping via
        ``BAPI_USER_GET_DETAIL`` to validate credentials.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError(
            "SAP PS adapter is a placeholder. "
            "See https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/project-system"
        )

    def sync_cbs(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch WBS element hierarchy from SAP PS.

        Will call oData service ``API_PROJECT_V2`` or BAPI
        ``BAPI_BUS2054_GETDATA`` to retrieve WBS elements and map
        POSID → ``cbs_code``, STUFE → ``cbs_level``.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("SAP PS CBS sync not yet implemented.")

    def sync_cost_snapshots(self, project_id: str, as_of: date) -> list[dict[str, Any]]:
        """Fetch cost snapshot from SAP PS controlling tables.

        Will query COSP/COSS (plan/actual by cost element) and BPJA
        (budget by fiscal year) to construct a point-in-time snapshot.

        Args:
            project_id: MeridianIQ project UUID.
            as_of: Snapshot reference date.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("SAP PS cost snapshot sync not yet implemented.")

    def sync_change_orders(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch budget supplements and change documents from SAP PS.

        Will query budget change documents via ``BAPI_COSTACTPLN_*``
        and extract supplement amounts, dates, and approval status.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("SAP PS change order sync not yet implemented.")

    def sync_time_phased(
        self,
        project_id: str,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        """Fetch periodic cost data from SAP PS controlling.

        Will query COSP/COSS tables by fiscal period to extract
        plan, actual, and commitment values per WBS element.

        Args:
            project_id: MeridianIQ project UUID.
            period_start: Start of the reporting period.
            period_end: End of the reporting period.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("SAP PS time-phased sync not yet implemented.")

    def get_last_sync_time(self, project_id: str) -> datetime | None:
        """Return the timestamp of the last successful SAP PS sync.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError("SAP PS last-sync tracking not yet implemented.")

    # ------------------------------------------------------------------ #
    # Schedule domain (ScheduleAdapter protocol)                         #
    # ------------------------------------------------------------------ #

    def sync_activities(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch network activities from SAP PS.

        Will call oData service ``API_PROJECT_V2`` or BAPI
        ``BAPI_NETWORK_GETINFO`` to retrieve network activities
        (AFVC) with dates, durations, and work quantities.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.

        Reference:
            AACE RP 49R-06 (Scheduling).
        """
        raise NotImplementedError(
            "SAP PS activity sync not yet implemented. "
            "See API_PROJECT_V2 oData service — NetworkActivity entity set."
        )

    def sync_relationships(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch network activity relationships from SAP PS.

        Will call ``API_PROJECT_V2`` to retrieve predecessor
        relationships (FS/FF/SS/SF) between network activities.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError(
            "SAP PS relationship sync not yet implemented. "
            "See API_PROJECT_V2 oData service — NetworkActivityRelationship."
        )

    def sync_milestones(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch WBS milestones from SAP PS.

        Will query WBS elements flagged as milestones (PRPS-MPTS)
        via ``API_PROJECT_V2`` or ``BAPI_BUS2054_GETDATA``.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError(
            "SAP PS milestone sync not yet implemented. "
            "See API_PROJECT_V2 oData service — WBSElement (milestone flag)."
        )

    def sync_progress(self, project_id: str, as_of: date) -> list[dict[str, Any]]:
        """Fetch progress confirmations from SAP PS.

        Will query network activity confirmations (AFRU) to retrieve
        actual dates, percent complete, and remaining work.

        Args:
            project_id: MeridianIQ project UUID.
            as_of: Progress data date.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError(
            "SAP PS progress sync not yet implemented. "
            "See API_PROJECT_V2 oData service — confirmation records (AFRU)."
        )

    # ------------------------------------------------------------------ #
    # Resource domain (ResourceAdapter protocol)                         #
    # ------------------------------------------------------------------ #

    def sync_resources(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch resource catalog from SAP PS / HR.

        Will query work center master data (CRHD) and HR mini-master
        via oData or BAPI to retrieve labor and equipment resources.

        Args:
            project_id: MeridianIQ project UUID.

        Raises:
            NotImplementedError: Adapter not yet implemented.

        Reference:
            AACE RP 22R-01 (Resource Planning).
        """
        raise NotImplementedError(
            "SAP PS resource sync not yet implemented. "
            "See work center (CRHD) and HR mini-master APIs."
        )

    def sync_timesheets(
        self,
        project_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch timesheet data from SAP CATS.

        Will query CATS (Cross Application TimeSheet) via oData service
        ``API_MANAGE_WORKFORCE_TIMESHEET`` to retrieve hours, cost,
        and overtime per resource and network activity.

        Args:
            project_id: MeridianIQ project UUID.
            start_date: Start of the reporting period.
            end_date: End of the reporting period.

        Raises:
            NotImplementedError: Adapter not yet implemented.
        """
        raise NotImplementedError(
            "SAP PS timesheet sync not yet implemented. "
            "See CATS — API_MANAGE_WORKFORCE_TIMESHEET oData service."
        )
