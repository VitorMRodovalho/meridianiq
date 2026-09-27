# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""AI access routes: the caller's status and the operator's controls.

The rules live in :mod:`src.api.ai_gate`; these routes only expose them.
The operator routes require a signed-in session whose id is listed in
``SUPERADMIN_USER_IDS`` (``ai_gate.is_ai_admin``).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Request

from .. import ai_gate
from ..access import Principal, get_principal
from ..deps import RATE_LIMIT_LIGHT, RATE_LIMIT_READ, RATE_LIMIT_WRITE, get_store, limiter
from ..schemas import (
    AIAdminResponse,
    AIConfigFlags,
    AIDefaults,
    AIEntitlementGrantRequest,
    AIEntitlementSchema,
    AIMonthCalls,
    AIRevokeResponse,
    AIStatusResponse,
)

router = APIRouter()


def _ai_admin(principal: Principal = Depends(get_principal)) -> Principal:
    """The operator: a signed-in session listed in ``SUPERADMIN_USER_IDS``."""
    if not ai_gate.is_ai_admin(principal):
        raise ai_gate.error(403, "superadmin_required")
    return principal


def _money(value: Any) -> str | None:
    """A money amount as a decimal string, or ``None``."""
    if value is None:
        return None
    return format(Decimal(str(value)).normalize(), "f")


def _when(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, datetime) else str(value)


def _entitlement(row: dict[str, Any]) -> AIEntitlementSchema:
    return AIEntitlementSchema(
        user_id=str(row["user_id"]),
        email=row.get("email"),
        active=bool(row.get("active")),
        granted_at=_when(row.get("granted_at")),
        revoked_at=_when(row.get("revoked_at")),
        daily_questions=row.get("daily_questions"),
        monthly_budget_usd=_money(row.get("monthly_budget_usd")),
        note=row.get("note"),
        used_today=int(row.get("used_today") or 0),
        spent_month_usd=_money(row.get("spent_month_usd")) or "0",
    )


@router.get("/api/v1/ai/status", response_model=AIStatusResponse)
@limiter.limit(RATE_LIMIT_READ)
def ai_status(
    request: Request,
    principal: Principal = Depends(get_principal),
    store: Any = Depends(get_store),
) -> AIStatusResponse:
    """Whether the caller may use the AI assistant now, and why not.

    Gate states answer 200 (``available=false`` with a ``reason``); only a
    signed-out caller gets 401.
    """
    status = ai_gate.status_for(principal, store)
    return AIStatusResponse(
        available=status.available,
        reason=status.reason,
        daily_limit=status.daily_limit,
        used_today=status.used_today,
        remaining_today=status.remaining_today,
        resets_at=status.resets_at,
    )


@router.get("/api/v1/superadmin/ai", response_model=AIAdminResponse)
@limiter.limit(RATE_LIMIT_LIGHT)
def ai_admin_overview(
    request: Request,
    _operator: Principal = Depends(_ai_admin),
    store: Any = Depends(get_store),
) -> AIAdminResponse:
    """Configuration state (never secret values), spend and entitlements.

    Answers 200 with ``reason="ai_ledger_unavailable"`` and the configuration
    flags when the ledger cannot be read.
    """
    report = ai_gate.admin_report(store)
    return AIAdminResponse(
        available=report["available"],
        reason=report["reason"],
        config=AIConfigFlags(**report["config"]),
        model=report["model"],
        global_budget_usd=_money(report["global_budget_usd"]),
        global_spent_month_usd=_money(report["global_spent_month_usd"]) or "0",
        month_calls=AIMonthCalls(**report["month_calls"]),
        last_failure_at=_when(report["last_failure_at"]),
        reserve_per_question_usd=_money(report["reserve_per_question_usd"]),
        defaults=AIDefaults(
            daily_questions=report["defaults"]["daily_questions"],
            account_monthly_budget_usd=_money(report["defaults"]["account_monthly_budget_usd"])
            or "0",
        ),
        stale_reservations=report["stale_reservations"],
        entitlements=[_entitlement(r) for r in report["entitlements"]],
    )


@router.post("/api/v1/superadmin/ai/entitlements", response_model=AIEntitlementSchema)
@limiter.limit(RATE_LIMIT_WRITE)
def ai_grant_entitlement(
    request: Request,
    body: AIEntitlementGrantRequest,
    operator: Principal = Depends(_ai_admin),
    store: Any = Depends(get_store),
) -> AIEntitlementSchema:
    """Grant AI access to the account that owns ``email``.

    The account must exist (the person signed in at least once). A re-grant
    replaces the limits and reactivates a revoked entitlement. Audited.
    """
    row = ai_gate.grant(
        store,
        operator=operator,
        email=body.email,
        daily_questions=body.daily_questions,
        monthly_budget_usd=body.monthly_budget_usd,
        note=body.note,
        request=request,
    )
    return _entitlement(row)


@router.delete(
    "/api/v1/superadmin/ai/entitlements/{user_id}",
    response_model=AIRevokeResponse,
)
@limiter.limit(RATE_LIMIT_WRITE)
def ai_revoke_entitlement(
    request: Request,
    user_id: str,
    operator: Principal = Depends(_ai_admin),
    store: Any = Depends(get_store),
) -> AIRevokeResponse:
    """Revoke an account's AI access (soft: the row and its history stay). Audited."""
    try:
        canonical = str(uuid.UUID(user_id))
    except ValueError as exc:
        raise ai_gate.error(404, "ai_entitlement_not_found") from exc
    ai_gate.revoke(store, operator=operator, user_id=canonical, request=request)
    return AIRevokeResponse(revoked=True)
