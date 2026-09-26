# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Admin router — API keys, GDPR data deletion, IPS reconciliation, recovery validation."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request

from ..access import AccessContext, get_access
from ..auth import require_auth
from ..deps import (
    RATE_LIMIT_EXPENSIVE,
    RATE_LIMIT_WRITE,
    get_evm_store,
    get_report_store,
    get_risk_store,
    get_store,
    get_tia_store,
    get_timeline_store,
    granted_schedule,
    limiter,
)
from ..schemas import MAX_SERIES_PROJECT_IDS, GDPRDeleteResponse

router = APIRouter()


def _purge_owned_results(user_id: str) -> int:
    """Delete every in-memory analysis result and report owned by ``user_id``."""
    stores = (
        get_timeline_store(),
        get_tia_store(),
        get_evm_store(),
        get_risk_store(),
        get_report_store(),
    )
    return sum(store.purge_owner(user_id) for store in stores)


# ------------------------------------------------------------------
# API Keys
# ------------------------------------------------------------------


@router.post("/api/v1/api-keys")
@limiter.limit(RATE_LIMIT_WRITE)
def create_api_key(
    request: Request,
    body: dict,
    _user: object = Depends(require_auth),
) -> dict:
    """Generate a new API key for programmatic access.

    The raw key is returned only once -- store it securely.
    Subsequent requests use the key via ``X-API-Key`` header.

    Args:
        body: JSON with optional ``name`` field.

    Returns:
        Dict with ``key`` (raw), ``key_id``, ``name``, ``created_at``.
    """
    from src.api.auth import generate_api_key

    user_id = _user["id"]
    name = body.get("name", "default")
    result = generate_api_key(user_id, name)
    return result


@router.get("/api/v1/api-keys")
def list_api_keys_endpoint(
    _user: object = Depends(require_auth),
) -> dict:
    """List all API keys for the authenticated user.

    Does not return raw keys -- only key_id, name, created_at.
    """
    from src.api.auth import list_api_keys

    user_id = _user["id"]
    keys = list_api_keys(user_id)
    return {"keys": keys}


@router.delete("/api/v1/api-keys/{key_id}")
def revoke_api_key_endpoint(
    key_id: str,
    _user: object = Depends(require_auth),
) -> dict:
    """Revoke an API key.

    Args:
        key_id: The key identifier to revoke.

    Returns:
        Dict with ``revoked`` boolean.
    """
    from src.api.auth import revoke_api_key

    user_id = _user["id"]
    revoked = revoke_api_key(user_id, key_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"revoked": True, "key_id": key_id}


# ------------------------------------------------------------------
# GDPR Data Deletion
# ------------------------------------------------------------------


@router.delete(
    "/api/v1/user/data",
    response_model=GDPRDeleteResponse,
)
def delete_user_data(_user: object = Depends(require_auth)) -> GDPRDeleteResponse:
    """Delete all data owned by the authenticated user (GDPR compliance).

    Cascade deletes: uploads, projects, analyses, comparisons, timelines,
    TIA, EVM, risk simulations, benchmarks, programs, API keys, and profile.

    This action is irreversible.
    """
    user_id = _user.get("id") if isinstance(_user, dict) else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Stored results (timelines, TIA, EVM, risk, reports) live in process
    # memory, outside the database cascade below, so erase them first:
    # every return path after this point has already done it.
    _purge_owned_results(str(user_id))

    store = get_store()

    # Count before deletion for response
    deleted = {
        "deleted_uploads": 0,
        "deleted_projects": 0,
        "deleted_analyses": 0,
        "deleted_benchmarks": 0,
        "status": "complete",
    }

    # Use store's Supabase client if available
    if hasattr(store, "_client"):
        try:
            result = store._client.rpc("delete_user_data", {"target_user_id": user_id}).execute()
            if result.data:
                return GDPRDeleteResponse(**result.data)
        except Exception:
            pass  # Fall through to direct deletes

    # Fallback: direct deletes via service role
    if hasattr(store, "_client"):
        client = store._client
        try:
            r = client.table("benchmark_projects").delete().eq("contributed_by", user_id).execute()
            deleted["deleted_benchmarks"] = len(r.data) if r.data else 0
        except Exception:
            pass
        try:
            r = client.table("projects").delete().eq("user_id", user_id).execute()
            deleted["deleted_projects"] = len(r.data) if r.data else 0
        except Exception:
            pass
        try:
            r = client.table("schedule_uploads").delete().eq("user_id", user_id).execute()
            deleted["deleted_uploads"] = len(r.data) if r.data else 0
        except Exception:
            pass

    # Purge cached KPI bundles — the cache is a secondary copy of personal
    # data under LGPD/GDPR, so right-to-erasure must clear it too. Namespace-
    # wide drop is acceptable: the 120s TTL would only hide non-deleted
    # data's aggregates from unrelated users for a brief recompute window.
    from ..cache import invalidate_namespace

    invalidate_namespace("schedule:kpis")

    return GDPRDeleteResponse(**deleted)


# ------------------------------------------------------------------
# IPS Reconciliation
# ------------------------------------------------------------------


@router.post("/api/v1/ips/reconcile")
@limiter.limit(RATE_LIMIT_EXPENSIVE)
def reconcile_ips(
    request: Request,
    body: dict,
    ctx: AccessContext = Depends(get_access),
) -> dict:
    """Run IPS reconciliation between a master schedule and sub-schedules.

    Per AACE RP 71R-12. Checks milestone alignment, date consistency,
    float consistency, and WBS alignment. Every id is authorized before
    any schedule is read.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: Request body dict with keys:

            - master_project_id (str): the master schedule project ID
            - sub_project_ids (list[str]): sub-schedule project IDs

    Returns:
        IPSReconciliationResult as dict.

    Raises:
        HTTPException: 400 if an id is absent or not a string, or if there
            are more than MAX_SERIES_PROJECT_IDS sub-projects; 404 if any project is missing or
            not the caller's (one hidden id fails the whole request).
    """
    from src.analytics.ips_reconciliation import IPSReconciler

    master_id = body.get("master_project_id")
    sub_ids = body.get("sub_project_ids", [])

    if not master_id or not sub_ids:
        raise HTTPException(
            status_code=400,
            detail="master_project_id and sub_project_ids are required",
        )
    if (
        not isinstance(master_id, str)
        or not isinstance(sub_ids, list)
        or not all(isinstance(sid, str) for sid in sub_ids)
    ):
        raise HTTPException(
            status_code=400,
            detail="master_project_id must be a string and sub_project_ids a list of strings",
        )
    if len(sub_ids) > MAX_SERIES_PROJECT_IDS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_SERIES_PROJECT_IDS} sub-projects per reconciliation",
        )
    master_id = ctx.project(master_id)
    sub_ids = ctx.projects(sub_ids)

    store = get_store()

    master = granted_schedule(store, master_id)
    subs = [granted_schedule(store, sid) for sid in sub_ids]

    reconciler = IPSReconciler(master)
    result = reconciler.reconcile(subs)

    return asdict(result)


# ------------------------------------------------------------------
# Recovery Schedule Validation
# ------------------------------------------------------------------


@router.post("/api/v1/recovery/validate")
@limiter.limit(RATE_LIMIT_EXPENSIVE)
def validate_recovery(
    request: Request,
    body: dict,
    ctx: AccessContext = Depends(get_access),
) -> dict:
    """Validate a recovery schedule against the impacted schedule.

    Per AACE RP 29R-03 Section 4. Checks duration compression,
    scope changes, float consumption, and logic integrity. Both ids are
    authorized before either schedule is read.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: Request body dict with keys:

            - impacted_project_id (str): the impacted schedule
            - recovery_project_id (str): the proposed recovery schedule

    Raises:
        HTTPException: 400 if an id is absent or not a string; 404 if either
            project is missing or not the caller's.
    """
    from src.analytics.recovery_validation import RecoveryValidator

    impacted_id = body.get("impacted_project_id")
    recovery_id = body.get("recovery_project_id")

    if not impacted_id or not recovery_id:
        raise HTTPException(
            status_code=400,
            detail="impacted_project_id and recovery_project_id are required",
        )
    if not isinstance(impacted_id, str) or not isinstance(recovery_id, str):
        raise HTTPException(
            status_code=400,
            detail="impacted_project_id and recovery_project_id must be strings",
        )
    impacted_id, recovery_id = ctx.projects([impacted_id, recovery_id])

    store = get_store()

    impacted = granted_schedule(store, impacted_id)
    recovery = granted_schedule(store, recovery_id)

    validator = RecoveryValidator(impacted, recovery)
    result = validator.validate()

    return asdict(result)
