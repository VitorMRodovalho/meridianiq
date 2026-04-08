# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Multi-domain adapter protocols for ERP/PMIS integrations.

Instead of a single monolithic protocol, the integration framework uses
**domain-specific protocols** that adapters opt into based on what their
source system actually supports.  This follows the Interface Segregation
Principle — a SAP adapter shouldn't need to stub out ``sync_rfis`` if
SAP PS doesn't expose RFI data.

Protocol hierarchy::

    ERPAdapter (base — every adapter)
    ├── CostAdapter        — budgets, actuals, forecasts, change orders
    ├── ScheduleAdapter    — activities, relationships, milestones, progress
    ├── RiskAdapter        — risk registers, risk events, mitigations
    ├── ReportingAdapter   — daily logs, RFIs, submittals, inspections
    └── ResourceAdapter    — labor, equipment, materials, timesheets

Usage in routers::

    adapter = get_adapter(source_system)
    if isinstance(adapter, CostAdapter):
        cbs = adapter.sync_cbs(project_id)
    if isinstance(adapter, ScheduleAdapter):
        activities = adapter.sync_activities(project_id)

Reference: AACE RP 10S-90, ANSI/EIA-748, ISO 21511, UN/CEFACT.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable


# ------------------------------------------------------------------ #
# Base — every adapter must implement this                           #
# ------------------------------------------------------------------ #


@runtime_checkable
class ERPAdapter(Protocol):
    """Base protocol that every ERP/PMIS connector must satisfy.

    Provides identity, connection testing, and sync tracking.
    Domain-specific capabilities are declared via additional protocols.
    """

    @property
    def source_system(self) -> str:
        """Identifier for this adapter (e.g. 'procore', 'sap_ps')."""
        ...

    @property
    def supported_domains(self) -> list[str]:
        """List of domains this adapter supports.

        Returns a list of domain names: 'cost', 'schedule', 'risk',
        'reporting', 'resource'.  Used by the UI to show available
        integration capabilities.
        """
        ...

    def test_connection(self) -> bool:
        """Verify that the external system is reachable."""
        ...

    def get_last_sync_time(self, project_id: str) -> datetime | None:
        """Return the timestamp of the last successful sync, or None."""
        ...


# ------------------------------------------------------------------ #
# Cost domain — budgets, actuals, forecasts, change orders           #
# ------------------------------------------------------------------ #


@runtime_checkable
class CostAdapter(Protocol):
    """Protocol for cost management integration.

    Maps to migration 019 tables: cbs_elements, cost_snapshots,
    cost_time_phased, change_orders.

    Reference: AACE RP 10S-90 (Cost Engineering Terminology),
               ANSI/EIA-748 (EVMS).
    """

    def sync_cbs(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch CBS hierarchy from the external system.

        Returns dicts with keys matching ``cbs_elements`` table:
        cbs_code, cbs_description, cbs_level, parent_cbs_code,
        coding_system, source_record_id, sort_order.
        """
        ...

    def sync_cost_snapshots(self, project_id: str, as_of: date) -> list[dict[str, Any]]:
        """Fetch cost snapshot data as of a specific date.

        Returns dicts matching ``cost_snapshots`` table:
        cbs_code, snapshot_date, original_budget, approved_changes,
        current_budget, committed_cost, actual_cost, estimate_to_complete,
        estimate_at_completion, bcws, bcwp, acwp.
        """
        ...

    def sync_change_orders(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch change orders from the external system.

        Returns dicts matching ``change_orders`` table:
        change_id, change_type, status, title, description,
        requested_amount, approved_amount, effective_date, cbs_code.
        """
        ...

    def sync_time_phased(
        self,
        project_id: str,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        """Fetch time-phased cost data for a date range.

        Returns dicts matching ``cost_time_phased`` table:
        cbs_code, period_start, period_end, budget_this_period,
        actual_this_period, forecast_this_period, resource_type.
        """
        ...


# ------------------------------------------------------------------ #
# Schedule domain — activities, relationships, milestones, progress  #
# ------------------------------------------------------------------ #


@runtime_checkable
class ScheduleAdapter(Protocol):
    """Protocol for schedule data integration.

    Enables pulling schedule data from PMIS systems that have schedule
    modules (Procore Scheduling, InEight Schedule, P6 via Unifier).
    This complements the native XER parser — useful when the source
    system has schedule data but no XER export.

    Maps to migration 001 tables: activities, predecessors, wbs_elements.

    Reference: ISO 21511 (WBS), AACE RP 49R-06 (Scheduling).
    """

    def sync_activities(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch activities/tasks from the external system.

        Returns dicts with keys:
        task_id, task_code, task_name, task_type, status_code,
        wbs_id, planned_start, planned_finish, actual_start,
        actual_finish, duration_days, percent_complete,
        source_record_id.
        """
        ...

    def sync_relationships(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch predecessor relationships.

        Returns dicts with keys:
        task_id, pred_task_id, relationship_type (FS/FF/SS/SF),
        lag_days, source_record_id.
        """
        ...

    def sync_milestones(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch key milestones / summary tasks.

        Returns dicts with keys:
        milestone_id, name, planned_date, actual_date,
        is_critical, weight, source_record_id.
        """
        ...

    def sync_progress(self, project_id: str, as_of: date) -> list[dict[str, Any]]:
        """Fetch progress updates as of a specific date.

        Returns dicts with keys:
        task_id, percent_complete, remaining_duration_days,
        actual_start, actual_finish, status, report_date,
        source_record_id.
        """
        ...


# ------------------------------------------------------------------ #
# Risk domain — risk registers, events, mitigations                  #
# ------------------------------------------------------------------ #


@runtime_checkable
class RiskAdapter(Protocol):
    """Protocol for risk management integration.

    Enables pulling risk register data from PMIS risk modules
    (Procore, custom Unifier BPs, InEight Compliance).

    Maps to migration 016 table: risk_register.

    Reference: AACE RP 57R-09 (Integrated Cost/Schedule Risk),
               ISO 31000 (Risk Management).
    """

    def sync_risk_register(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch risk register entries.

        Returns dicts with keys:
        risk_id, title, description, category,
        probability (0-1), impact_cost, impact_schedule_days,
        status (open/mitigated/closed), owner,
        response_strategy (avoid/mitigate/transfer/accept),
        source_record_id.
        """
        ...

    def sync_risk_events(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch realized risk events (issues that materialized).

        Returns dicts with keys:
        event_id, risk_id, title, occurred_date,
        actual_cost_impact, actual_schedule_impact_days,
        resolution, source_record_id.
        """
        ...


# ------------------------------------------------------------------ #
# Reporting domain — daily logs, RFIs, submittals, inspections       #
# ------------------------------------------------------------------ #


@runtime_checkable
class ReportingAdapter(Protocol):
    """Protocol for field reporting integration.

    Enables pulling field data that enriches schedule analysis:
    daily logs reveal actual work progress, RFIs indicate blockers,
    submittals track procurement delays.

    Reference: AGC ConsensusDocs, AIA A201 (General Conditions).
    """

    def sync_daily_logs(
        self,
        project_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch daily log entries for a date range.

        Returns dicts with keys:
        log_date, weather, temperature_f, wind_mph,
        crew_count, work_description, delays_noted,
        source_record_id.
        """
        ...

    def sync_rfis(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch RFIs (Requests for Information).

        Returns dicts with keys:
        rfi_id, number, subject, status (open/closed),
        date_submitted, date_due, date_responded,
        days_open, responsible_party, cost_impact,
        schedule_impact_days, source_record_id.
        """
        ...

    def sync_submittals(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch submittals (material/equipment approvals).

        Returns dicts with keys:
        submittal_id, number, title, spec_section,
        status (pending/approved/rejected/resubmit),
        date_submitted, date_required, date_returned,
        lead_time_days, source_record_id.
        """
        ...


# ------------------------------------------------------------------ #
# Resource domain — labor, equipment, materials, timesheets          #
# ------------------------------------------------------------------ #


@runtime_checkable
class ResourceAdapter(Protocol):
    """Protocol for resource management integration.

    Enables pulling actual resource usage from ERP/PMIS to compare
    against P6 resource-loaded schedules.

    Reference: AACE RP 22R-01 (Resource Planning).
    """

    def sync_resources(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch resource catalog.

        Returns dicts with keys:
        resource_id, name, type (labor/equipment/material/subcontract),
        unit, unit_rate, availability_hours_per_day,
        source_record_id.
        """
        ...

    def sync_timesheets(
        self,
        project_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch timesheet / resource usage data.

        Returns dicts with keys:
        resource_id, task_id, work_date, hours,
        cost, overtime_hours, source_record_id.
        """
        ...
