# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Manual adapter — wraps the existing CBS Excel parser.

Converts ``CostIntegrationResult`` from ``src/analytics/cost_integration.py``
into the normalized dict format expected by migration 019 tables.

This adapter handles:
- Excel CBS uploads (the existing /api/v1/cost/upload flow)
- CSV cost imports (future)
- Manual data entry (future)

Reference: AACE RP 10S-90 (Cost Engineering Terminology).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from src.analytics.cost_integration import (
    CostIntegrationResult,
    parse_cbs_excel,
)


class ManualAdapter:
    """Adapter for manual Excel/CSV cost data imports.

    Wraps the existing ``parse_cbs_excel`` function and normalizes
    its output to the generic ERP table schema.
    """

    @property
    def source_system(self) -> str:
        return "manual"

    def test_connection(self) -> bool:
        """Manual imports are always 'connected'."""
        return True

    def sync_cbs(self, project_id: str) -> list[dict[str, Any]]:
        """Not applicable for manual — use ``parse_excel_to_cbs`` instead."""
        return []

    def sync_cost_snapshots(
        self, project_id: str, as_of: date
    ) -> list[dict[str, Any]]:
        """Not applicable for manual — use ``parse_excel_to_snapshots`` instead."""
        return []

    def sync_change_orders(self, project_id: str) -> list[dict[str, Any]]:
        return []

    def sync_time_phased(
        self,
        project_id: str,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        return []

    def get_last_sync_time(self, project_id: str) -> datetime | None:
        return None

    # -- Excel-specific methods -------------------------------------------

    def parse_excel_to_cbs(
        self, file_path: str
    ) -> list[dict[str, Any]]:
        """Parse CBS hierarchy from Excel into cbs_elements-compatible dicts.

        Args:
            file_path: Path to the Excel workbook.

        Returns:
            List of dicts ready for ``cbs_elements`` table insert.
        """
        result = parse_cbs_excel(file_path)
        return self._cbs_elements_to_dicts(result)

    def parse_excel_to_snapshots(
        self, file_path: str, snapshot_date: date | None = None
    ) -> list[dict[str, Any]]:
        """Parse CBS budget data into cost_snapshots-compatible dicts.

        Args:
            file_path: Path to the Excel workbook.
            snapshot_date: Date for the snapshot (defaults to today).

        Returns:
            List of dicts ready for ``cost_snapshots`` table insert.
        """
        result = parse_cbs_excel(file_path)
        snap_date = snapshot_date or date.today()
        return self._result_to_snapshots(result, snap_date)

    def parse_excel_to_mappings(
        self, file_path: str
    ) -> list[dict[str, Any]]:
        """Parse CBS-WBS mapping from Excel into cbs_wbs_mappings-compatible dicts.

        Args:
            file_path: Path to the Excel workbook.

        Returns:
            List of dicts with cbs_code and wbs_code for linkage.
        """
        result = parse_cbs_excel(file_path)
        return [
            {
                "cbs_code": m.cbs_code,
                "wbs_code": m.wbs_level1,
                "cost_category": m.cost_category,
                "mapping_type": "direct",
                "notes": m.notes,
            }
            for m in result.cbs_wbs_mappings
        ]

    # -- Internal helpers -------------------------------------------------

    @staticmethod
    def _cbs_elements_to_dicts(
        result: CostIntegrationResult,
    ) -> list[dict[str, Any]]:
        """Convert CBSElement list to cbs_elements table dicts."""
        elements = []
        for elem in result.cbs_elements:
            elements.append(
                {
                    "cbs_code": elem.cbs_code,
                    "cbs_description": f"{elem.cbs_level1} - {elem.cbs_level2}".strip(" -"),
                    "cbs_level": 2 if elem.cbs_level2 else 1,
                    "coding_system": "custom",
                    "source_record_id": elem.cbs_code,
                    "sort_order": len(elements),
                }
            )
        return elements

    @staticmethod
    def _result_to_snapshots(
        result: CostIntegrationResult, snap_date: date
    ) -> list[dict[str, Any]]:
        """Convert CBSElements to cost_snapshots table dicts."""
        snapshots = []
        for elem in result.cbs_elements:
            snapshots.append(
                {
                    "cbs_code": elem.cbs_code,
                    "snapshot_date": snap_date.isoformat(),
                    "original_budget": float(elem.estimate),
                    "current_budget": float(elem.budget),
                    "contingency_original": float(elem.contingency),
                    "escalation": float(elem.escalation),
                    "source_record_id": elem.cbs_code,
                }
            )
        return snapshots
