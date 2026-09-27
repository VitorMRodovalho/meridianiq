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

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from .. import ai_gate
from ..access import Principal, get_principal
from ..deps import RATE_LIMIT_LIGHT, RATE_LIMIT_READ, RATE_LIMIT_WRITE, get_store, limiter
from ..schemas import (
    AIAccessRequestBody,
    AIAccessRequestItem,
    AIAccessRequestResponse,
    AIAdminResponse,
    AIConfigFlags,
    AIDefaults,
    AIEntitlementGrantRequest,
    AIEntitlementSchema,
    AIMonthCalls,
    AIRequestDismissResponse,
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
    access = ai_gate.access_for(principal, store, status.reason)
    return AIStatusResponse(
        available=status.available,
        reason=status.reason,
        daily_limit=status.daily_limit,
        used_today=status.used_today,
        remaining_today=status.remaining_today,
        resets_at=status.resets_at,
        access=access.state if access else None,
        access_requested_at=_when(access.requested_at) if access else None,
        access_retry_after=_when(access.retry_after) if access else None,
    )


@router.post("/api/v1/ai/access-request", response_model=AIAccessRequestResponse)
@limiter.limit(RATE_LIMIT_WRITE)
def ai_request_access(
    request: Request,
    body: AIAccessRequestBody,
    background: BackgroundTasks,
    principal: Principal = Depends(get_principal),
    store: Any = Depends(get_store),
) -> AIAccessRequestResponse:
    """Ask for access to the AI assistant (signed-in session only).

    ``created``: a new pending request; the operator is emailed (without the
    requester's details). ``pending``: one is already waiting (the note is
    updated when given). ``entitled``: access is active. ``dismissed``: a
    new request is allowed from ``retry_after``.
    """
    state = ai_gate.request_access(principal, store, body.note, background)
    return AIAccessRequestResponse(
        state=state.state,
        requested_at=_when(state.requested_at),
        retry_after=_when(state.retry_after),
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
        requests=(
            None
            if report["requests"] is None
            else [
                AIAccessRequestItem(
                    user_id=str(r["user_id"]),
                    email=r.get("email"),
                    note=r.get("note"),
                    requested_at=_when(r.get("requested_at")),
                )
                for r in report["requests"]
            ]
        ),
        requests_total=report["requests_total"],
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


def _canonical_user_id(user_id: str, not_found: str) -> str:
    try:
        return str(uuid.UUID(user_id))
    except ValueError as exc:
        raise ai_gate.error(404, not_found) from exc


@router.post(
    "/api/v1/superadmin/ai/requests/{user_id}/approve",
    response_model=AIEntitlementSchema,
)
@limiter.limit(RATE_LIMIT_WRITE)
def ai_approve_request(
    request: Request,
    user_id: str,
    operator: Principal = Depends(_ai_admin),
    store: Any = Depends(get_store),
) -> AIEntitlementSchema:
    """Approve a pending access request with the default limits. Audited."""
    canonical = _canonical_user_id(user_id, "ai_request_not_found")
    row = ai_gate.approve_request(store, operator=operator, user_id=canonical, request=request)
    return _entitlement(row)


@router.delete(
    "/api/v1/superadmin/ai/requests/{user_id}",
    response_model=AIRequestDismissResponse,
)
@limiter.limit(RATE_LIMIT_WRITE)
def ai_dismiss_request(
    request: Request,
    user_id: str,
    operator: Principal = Depends(_ai_admin),
    store: Any = Depends(get_store),
) -> AIRequestDismissResponse:
    """Dismiss a pending access request (it may be sent again in 30 days). Audited."""
    canonical = _canonical_user_id(user_id, "ai_request_not_found")
    ai_gate.dismiss_request(store, operator=operator, user_id=canonical, request=request)
    return AIRequestDismissResponse(dismissed=True)
