# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""AIA G703 Continuation Sheet — build billing line items from CBS snapshots.

Produces the row data for an AIA G703 "Continuation Sheet" (the schedule
of values attached to an AIA G702 Application for Payment). Fields
that require contractual data not captured in the CBS (retainage %,
change orders, previous period billings) are accepted as caller inputs
with sensible defaults so the user can still bootstrap a draft G703
from a parsed CBS workbook.

Reference:
    AIA Document G703™-1992 (current edition) — Continuation Sheet for G702.
    https://www.aiacontracts.org/contract-documents/25131-application-for-payment
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class G703LineItem:
    """A single row on the continuation sheet.

    Attributes:
        line_number: Sequential item number (A-column on the form).
        description: Description of work / scope (B-column).
        scheduled_value: Original contract sum for this line (C-column).
        previous_application_value: Work completed + stored, prior apps (D-column).
        this_period_value: Work completed this period (E-column).
        materials_presently_stored: Materials stored not yet incorporated (F-column).
        total_completed_and_stored: D + E + F (G-column, cumulative).
        percent_complete: G / C, expressed 0-100 (H-column).
        balance_to_finish: C - G (I-column).
        retainage: Retainage withheld on this line (J-column).
    """

    line_number: str = ""
    description: str = ""
    scheduled_value: float = 0.0
    previous_application_value: float = 0.0
    this_period_value: float = 0.0
    materials_presently_stored: float = 0.0
    total_completed_and_stored: float = 0.0
    percent_complete: float = 0.0
    balance_to_finish: float = 0.0
    retainage: float = 0.0


@dataclass
class G703ContinuationSheet:
    """Full G703 data package ready to render as Excel."""

    project_name: str = ""
    application_number: int = 1
    period_to: str = ""
    contract_for: str = ""
    architects_project_number: str = ""
    contract_date: str = ""
    retainage_pct: float = 0.10
    line_items: list[G703LineItem] = field(default_factory=list)
    # Totals (computed)
    total_scheduled_value: float = 0.0
    total_previous_application: float = 0.0
    total_this_period: float = 0.0
    total_materials_stored: float = 0.0
    total_completed_and_stored: float = 0.0
    total_balance_to_finish: float = 0.0
    total_retainage: float = 0.0


def build_g703_from_cbs(
    cost_snapshot: Any,
    project_name: str = "",
    application_number: int = 1,
    period_to: str = "",
    retainage_pct: float = 0.10,
    previous_completion_pct: dict[str, float] | None = None,
    current_completion_pct: dict[str, float] | None = None,
) -> G703ContinuationSheet:
    """Assemble a G703 continuation sheet from a CBS snapshot.

    Each CBS element becomes one G703 line item keyed by ``cbs_code``.
    Prior/current completion percentages are optional overlays keyed by
    ``cbs_code``. Lines without a completion entry default to 0 %.

    Args:
        cost_snapshot: A ``CostIntegrationResult`` (from the CBS engine).
        project_name: Project identifier shown in the G703 header.
        application_number: Billing application sequence (1, 2, 3, …).
        period_to: End-of-period date string (e.g. "2026-04-30").
        retainage_pct: Retainage fraction (0.10 = 10 %). Applied uniformly.
        previous_completion_pct: Optional {cbs_code: pct 0-100} for
            cumulative completion reported on the PRIOR application.
        current_completion_pct: Optional {cbs_code: pct 0-100} for
            cumulative completion reported on THIS application. When not
            supplied the line is treated as having zero work billed.

    Returns:
        A ``G703ContinuationSheet`` with per-line and total figures.

    Reference: AIA Document G703™ Continuation Sheet.
    """
    retainage_pct = max(0.0, min(1.0, float(retainage_pct)))
    previous_completion_pct = previous_completion_pct or {}
    current_completion_pct = current_completion_pct or {}

    sheet = G703ContinuationSheet(
        project_name=project_name,
        application_number=application_number,
        period_to=period_to,
        retainage_pct=retainage_pct,
    )

    elements = list(getattr(cost_snapshot, "cbs_elements", []) or [])

    for i, elem in enumerate(elements, start=1):
        scheduled = float(getattr(elem, "budget", 0.0) or 0.0)
        if scheduled <= 0:
            # Fall back to estimate + contingency + escalation when budget is 0
            scheduled = (
                float(getattr(elem, "estimate", 0.0) or 0.0)
                + float(getattr(elem, "contingency", 0.0) or 0.0)
                + float(getattr(elem, "escalation", 0.0) or 0.0)
            )

        code = getattr(elem, "cbs_code", "") or ""
        prev_pct = float(previous_completion_pct.get(code, 0.0) or 0.0)
        cur_pct = float(current_completion_pct.get(code, prev_pct) or prev_pct)
        cur_pct = max(prev_pct, cur_pct)  # monotonic

        prev_value = round(scheduled * (prev_pct / 100.0), 2)
        cumulative_value = round(scheduled * (cur_pct / 100.0), 2)
        this_period = round(cumulative_value - prev_value, 2)

        line = G703LineItem(
            line_number=str(i).zfill(3),
            description=(
                getattr(elem, "scope", "")
                or getattr(elem, "cbs_level2", "")
                or getattr(elem, "cbs_level1", "")
                or code
            ),
            scheduled_value=scheduled,
            previous_application_value=prev_value,
            this_period_value=this_period,
            materials_presently_stored=0.0,
            total_completed_and_stored=cumulative_value,
            percent_complete=round(cur_pct, 2),
            balance_to_finish=round(scheduled - cumulative_value, 2),
            retainage=round(cumulative_value * retainage_pct, 2),
        )
        sheet.line_items.append(line)

    _accumulate_totals(sheet)
    return sheet


def _accumulate_totals(sheet: G703ContinuationSheet) -> None:
    """Roll up line totals into the sheet header fields."""
    sheet.total_scheduled_value = round(sum(li.scheduled_value for li in sheet.line_items), 2)
    sheet.total_previous_application = round(
        sum(li.previous_application_value for li in sheet.line_items), 2
    )
    sheet.total_this_period = round(sum(li.this_period_value for li in sheet.line_items), 2)
    sheet.total_materials_stored = round(
        sum(li.materials_presently_stored for li in sheet.line_items), 2
    )
    sheet.total_completed_and_stored = round(
        sum(li.total_completed_and_stored for li in sheet.line_items), 2
    )
    sheet.total_balance_to_finish = round(sum(li.balance_to_finish for li in sheet.line_items), 2)
    sheet.total_retainage = round(sum(li.retainage for li in sheet.line_items), 2)
