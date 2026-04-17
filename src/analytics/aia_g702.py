# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""AIA G702 Application and Certificate for Payment — data model.

Produces the figures for an AIA G702 cover certificate that pairs with
a G703 Continuation Sheet. Lines 1–9 of the G702 form are computed from
the G703 totals (Total Completed & Stored, Retainage) combined with
caller-supplied contract inputs (original contract sum, change orders,
previously-certified payments). No PDF rendering is done here — this
module is a pure dataclass builder so the figures can be unit-tested
and reused by the HTML/PDF renderer.

Reference:
    AIA Document G702™-1992 (current edition) — Application and
    Certificate for Payment. https://www.aiacontracts.org/contract-documents/25131-application-for-payment
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class G702ChangeOrder:
    """Single line in the Change Order summary block."""

    prior_additions: float = 0.0
    prior_deductions: float = 0.0
    this_period_additions: float = 0.0
    this_period_deductions: float = 0.0

    @property
    def total_additions(self) -> float:
        return round(self.prior_additions + self.this_period_additions, 2)

    @property
    def total_deductions(self) -> float:
        return round(self.prior_deductions + self.this_period_deductions, 2)

    @property
    def net_change(self) -> float:
        return round(self.total_additions - self.total_deductions, 2)


@dataclass
class G702Application:
    """Full G702 form data — lines 1-9 plus certification context.

    Line 1  — Original Contract Sum
    Line 2  — Net change by Change Orders
    Line 3  — Contract Sum to Date (line 1 ± line 2)
    Line 4  — Total Completed & Stored to Date (G703 column G total)
    Line 5  — Retainage
        5a — Completed Work retainage
        5b — Stored Materials retainage
    Line 6  — Total Earned Less Retainage (line 4 − line 5)
    Line 7  — Less Previous Certificates for Payment
    Line 8  — Current Payment Due (line 6 − line 7)
    Line 9  — Balance to Finish, Including Retainage (line 3 − line 6)
    """

    # Header
    project_name: str = ""
    application_number: int = 1
    period_to: str = ""
    contract_for: str = ""
    architects_project_number: str = ""
    contract_date: str = ""
    owner: str = ""
    contractor: str = ""
    architect: str = ""
    via_architect: str = ""

    # Line 1
    original_contract_sum: float = 0.0

    # Line 2 / Change Order summary
    change_order: G702ChangeOrder = field(default_factory=G702ChangeOrder)

    # Line 4 (from G703 column G grand total)
    total_completed_and_stored: float = 0.0

    # Line 5 — retainage split
    retainage_completed_work: float = 0.0
    retainage_stored_materials: float = 0.0

    # Line 7
    previous_certificates_total: float = 0.0

    # Computed (populated by build_g702 / _compute)
    net_change_by_change_orders: float = 0.0
    contract_sum_to_date: float = 0.0
    total_retainage: float = 0.0
    total_earned_less_retainage: float = 0.0
    current_payment_due: float = 0.0
    balance_to_finish_including_retainage: float = 0.0

    def compute(self) -> None:
        """Recompute derived lines 2, 3, 5-total, 6, 8, 9."""
        self.net_change_by_change_orders = self.change_order.net_change
        self.contract_sum_to_date = round(
            self.original_contract_sum + self.net_change_by_change_orders, 2
        )
        self.total_retainage = round(
            self.retainage_completed_work + self.retainage_stored_materials, 2
        )
        self.total_earned_less_retainage = round(
            self.total_completed_and_stored - self.total_retainage, 2
        )
        self.current_payment_due = round(
            self.total_earned_less_retainage - self.previous_certificates_total, 2
        )
        self.balance_to_finish_including_retainage = round(
            self.contract_sum_to_date - self.total_earned_less_retainage, 2
        )


def build_g702_from_g703(
    g703: Any,
    original_contract_sum: float,
    previous_certificates_total: float = 0.0,
    change_order: G702ChangeOrder | None = None,
    retainage_stored_fraction: float = 0.0,
    owner: str = "",
    contractor: str = "",
    architect: str = "",
    contract_for: str = "",
    architects_project_number: str = "",
    contract_date: str = "",
    via_architect: str = "",
) -> G702Application:
    """Assemble a G702 Application from a G703 continuation sheet.

    Args:
        g703: A ``G703ContinuationSheet`` (from ``aia_g703.build_g703_from_cbs``).
        original_contract_sum: Line 1. The baseline contract value.
        previous_certificates_total: Line 7. Cumulative paid on prior apps.
        change_order: Change order summary for line 2. Defaults to zero.
        retainage_stored_fraction: Fraction of ``g703.total_retainage`` that
            should be attributed to Stored Materials (line 5b). The remainder
            goes to Completed Work (5a). G703 carries a single retainage
            column, so the split is caller-driven.
        owner, contractor, architect, contract_for, architects_project_number,
        contract_date, via_architect: Optional header fields.

    Returns:
        A populated ``G702Application`` with all nine lines computed.

    Reference: AIA Document G702™.
    """
    change_order = change_order or G702ChangeOrder()

    frac = max(0.0, min(1.0, float(retainage_stored_fraction)))
    total_retainage = float(getattr(g703, "total_retainage", 0.0) or 0.0)
    retainage_stored = round(total_retainage * frac, 2)
    retainage_completed = round(total_retainage - retainage_stored, 2)

    app = G702Application(
        project_name=getattr(g703, "project_name", "") or "",
        application_number=int(getattr(g703, "application_number", 1) or 1),
        period_to=getattr(g703, "period_to", "") or "",
        contract_for=contract_for or getattr(g703, "contract_for", "") or "",
        architects_project_number=(
            architects_project_number
            or getattr(g703, "architects_project_number", "")
            or ""
        ),
        contract_date=contract_date or getattr(g703, "contract_date", "") or "",
        owner=owner,
        contractor=contractor,
        architect=architect,
        via_architect=via_architect,
        original_contract_sum=float(original_contract_sum),
        change_order=change_order,
        total_completed_and_stored=float(
            getattr(g703, "total_completed_and_stored", 0.0) or 0.0
        ),
        retainage_completed_work=retainage_completed,
        retainage_stored_materials=retainage_stored,
        previous_certificates_total=float(previous_certificates_total),
    )
    app.compute()
    return app
