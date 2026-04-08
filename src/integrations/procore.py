# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Procore adapter — placeholder for the most widely used construction PMIS.

Procore is the dominant PMIS in US commercial construction with 500+
marketplace integrations.  Its REST API (v1.0/v1.1/v2.0) provides
comprehensive access to cost, schedule, and project management data.

Developer Portal: https://developers.procore.com
API Base URL: https://api.procore.com/rest/v{api_version}.{resource_version}/
Auth Base URL: https://login.procore.com (production)
Sandbox: https://login-sandbox-monthly.procore.com

Authentication:
  OAuth 2.0 with two grant types:
  1. Authorization Code — for web apps with user interaction
  2. Client Credentials — for server-to-server via Developer Managed
     Service Accounts (DMSAs), replacing traditional service accounts
  - Access tokens: 90 minutes (5400s), refresh tokens: indefinite (one-time use)
  - Requires company admin to authorize app installation
  - Permissions defined in app manifest

API Versioning:
  Dual-component: v{api_version}.{resource_version}
  - v2.0 is latest (responses wrapped in "data" envelope, string IDs)
  - Resources versioned independently within API version

Rate Limits:
  - Hourly: ~3600 requests/60min (varies per app)
  - Spike: ~25 requests/10s
  - Headers: X-Rate-Limit-Limit, X-Rate-Limit-Remaining, X-Rate-Limit-Reset
  - 429 Too Many Requests when exceeded

Webhooks:
  POST /rest/v1.0/webhooks/hooks — company or project scope
  Events: create, update, delete on most resources
  Delivery: HTTPS POST, 5s timeout, auto-retry
  Consumers must be idempotent

Security:
  - SOC 1 Type 2, SOC 2 Type 2 (SSAE 18)
  - ISO 27001:2013
  - FedRAMP authorized
  - Trust center: https://trust.procore.com

Field Mapping (Procore → MeridianIQ generic schema):
  ┌─────────────────────────────┬────────────────────────────────┐
  │ Procore Field               │ MeridianIQ Table.Column        │
  ├─────────────────────────────┼────────────────────────────────┤
  │ cost_code.id/code           │ cbs_elements.cbs_code          │
  │ cost_code.name              │ cbs_elements.cbs_description   │
  │ cost_code.standard          │ cbs_elements.coding_system     │
  │ budget_line_item.original   │ cost_snapshots.original_budget │
  │ budget_line_item.forecast   │ cost_snapshots.estimate_at_completion │
  │ budget_line_item.jtd_cost   │ cost_snapshots.actual_cost     │
  │ commitment.amount           │ cost_snapshots.committed_cost  │
  │ change_order_package.id     │ change_orders.change_id        │
  │ change_order_package.status │ change_orders.status           │
  │ change_order_package.amount │ change_orders.approved_amount  │
  │ potential_change_order.*    │ change_orders (status=pending) │
  │ direct_cost.amount          │ cost_snapshots.actual_cost     │
  │ wbs.id                      │ cbs_wbs_mappings linkage       │
  │ project.origin_id           │ erp_sources.source_record_id   │
  └─────────────────────────────┴────────────────────────────────┘

Key Cost Endpoints (v1.0 paths):
  GET  /rest/v1.0/budget_views                    — list budget views
  GET  /rest/v1.0/budget_views/{id}/detail_rows   — budget line items
  POST /rest/v1.0/budget_line_items               — create budget item
  GET  /rest/v1.0/cost_codes                      — cost code hierarchy
  GET  /rest/v1.0/change_order_packages           — change order packages
  GET  /rest/v1.0/change_order_requests           — change order requests
  GET  /rest/v1.0/potential_change_orders          — PCOs
  GET  /rest/v1.0/commitments                     — contracts/POs
  GET  /rest/v1.0/direct_costs                    — direct cost items
  GET  /rest/v1.0/prime_contracts                 — prime contracts

Key Schedule Endpoints:
  GET  /rest/v1.0/schedule/tasks                  — schedule tasks (simplified)
  POST /rest/v1.0/schedule_integration            — P6/MSP import integration
  Note: Procore is a schedule VIEWER, not a CPM engine.
        Master schedules should remain in P6.

Note: Procore cost codes align with CSI MasterFormat divisions.
  Default cost types: L=Labor, E=Equipment, M=Materials,
  C=Commitment, OC=Owner Cost, SVC=Professional Services, O=Other.

Reference: AACE RP 10S-90 (Cost Engineering Terminology),
           CSI MasterFormat (cost code classification).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


class ProcoreAdapter:
    """Procore REST API adapter — placeholder for future implementation.

    Procore is the most widely adopted PMIS in US commercial construction,
    serving as the hub for cost management, field coordination, and
    project documents.  Its API is the most mature and best-documented
    in the construction PMIS ecosystem.

    Implementation priority: HIGH — Procore's market share and API maturity
    make it the first ERP integration to implement after the manual adapter.
    """

    @property
    def source_system(self) -> str:
        return "procore"

    def test_connection(self) -> bool:
        """Test OAuth 2.0 connection to Procore.

        Requires:
        - client_id and client_secret from Procore Developer Portal
        - Company admin authorization (DMSA setup)
        - Access: GET /oauth/token/info → verify token validity
        """
        raise NotImplementedError(
            "Procore integration requires OAuth 2.0 setup. "
            "See: https://developers.procore.com/documentation/oauth-endpoints"
        )

    def sync_cbs(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch cost code hierarchy from Procore.

        Endpoint: GET /rest/v1.0/cost_codes?project_id={project_id}
        Returns: cost codes with CSI MasterFormat alignment.
        Pagination: per_page=100 max, Link header for next page.
        """
        raise NotImplementedError(
            "Procore cost code sync not yet implemented. "
            "Endpoint: GET /rest/v1.0/cost_codes"
        )

    def sync_cost_snapshots(
        self, project_id: str, as_of: date
    ) -> list[dict[str, Any]]:
        """Fetch budget data from Procore budget views.

        Endpoints:
        1. GET /rest/v1.0/budget_views → find the active budget view
        2. GET /rest/v1.0/budget_views/{id}/detail_rows → line items
        3. GET /rest/v1.0/commitments → committed costs
        4. GET /rest/v1.0/direct_costs → direct cost actuals

        Budget detail rows contain: original_budget_amount, forecast,
        approved_cos, pending_cos, jtd_costs (job-to-date).
        """
        raise NotImplementedError(
            "Procore budget sync not yet implemented. "
            "Endpoint: GET /rest/v1.0/budget_views/{id}/detail_rows"
        )

    def sync_change_orders(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch change orders from Procore's 3-tier CO model.

        Procore has a multi-tier change order workflow:
        1. Potential Change Orders (PCOs) → status: pending
        2. Change Order Requests (CORs) → status: submitted
        3. Change Order Packages (COPs) → status: approved

        Endpoints:
        - GET /rest/v1.0/potential_change_orders
        - GET /rest/v1.0/change_order_requests
        - GET /rest/v1.0/change_order_packages
        """
        raise NotImplementedError(
            "Procore change order sync not yet implemented. "
            "Endpoints: /potential_change_orders, /change_order_requests, "
            "/change_order_packages"
        )

    def sync_time_phased(
        self,
        project_id: str,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        """Fetch time-phased cost data from Procore.

        Procore budget views provide period columns when configured.
        Direct costs have transaction dates for period allocation.

        Note: Procore's budget is primarily point-in-time, not natively
        time-phased like ERP systems.  Period allocation may require
        combining budget snapshots with direct cost transaction dates.
        """
        raise NotImplementedError(
            "Procore time-phased sync not yet implemented. "
            "Requires combining budget detail rows with direct cost dates."
        )

    def get_last_sync_time(self, project_id: str) -> datetime | None:
        raise NotImplementedError("Procore sync tracking not yet implemented.")
