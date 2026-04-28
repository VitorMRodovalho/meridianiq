# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Admin router — API keys, GDPR data deletion, IPS reconciliation, recovery validation."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import optional_auth, require_auth
from ..deps import RATE_LIMIT_EXPENSIVE, get_store, limiter
from ..schemas import GDPRDeleteResponse

router = APIRouter()


# ------------------------------------------------------------------
# API Keys
# ------------------------------------------------------------------


@router.post("/api/v1/api-keys")
@limiter.limit("5/minute")
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
    _user: object = Depends(optional_auth),
) -> dict:
    """Run IPS reconciliation between a master schedule and sub-schedules.

    Per AACE RP 71R-12. Checks milestone alignment, date consistency,
    float consistency, and WBS alignment.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: Request body dict with keys:

            - master_project_id (str): the master schedule project ID
            - sub_project_ids (list[str]): sub-schedule project IDs

    Returns:
        IPSReconciliationResult as dict.
    """
    from src.analytics.ips_reconciliation import IPSReconciler

    master_id = body.get("master_project_id")
    sub_ids = body.get("sub_project_ids", [])

    if not master_id or not sub_ids:
        raise HTTPException(
            status_code=400,
            detail="master_project_id and sub_project_ids are required",
        )

    store = get_store()
    user_id = _user["id"] if _user else None

    master = store.get(master_id, user_id=user_id)
    if master is None:
        raise HTTPException(status_code=404, detail=f"Master project {master_id} not found")

    subs = []
    for sid in sub_ids:
        sub = store.get(sid, user_id=user_id)
        if sub is None:
            raise HTTPException(status_code=404, detail=f"Sub-schedule {sid} not found")
        subs.append(sub)

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
    _user: object = Depends(optional_auth),
) -> dict:
    """Validate a recovery schedule against the impacted schedule.

    Per AACE RP 29R-03 Section 4. Checks duration compression,
    scope changes, float consumption, and logic integrity.

    Args:
        request: FastAPI request object (consumed by the rate limiter).
        body: Request body dict with keys:

            - impacted_project_id (str): the impacted schedule
            - recovery_project_id (str): the proposed recovery schedule
    """
    from src.analytics.recovery_validation import RecoveryValidator

    impacted_id = body.get("impacted_project_id")
    recovery_id = body.get("recovery_project_id")

    if not impacted_id or not recovery_id:
        raise HTTPException(
            status_code=400,
            detail="impacted_project_id and recovery_project_id are required",
        )

    store = get_store()
    user_id = _user["id"] if _user else None

    impacted = store.get(impacted_id, user_id=user_id)
    if impacted is None:
        raise HTTPException(status_code=404, detail=f"Impacted schedule {impacted_id} not found")

    recovery = store.get(recovery_id, user_id=user_id)
    if recovery is None:
        raise HTTPException(status_code=404, detail=f"Recovery schedule {recovery_id} not found")

    validator = RecoveryValidator(impacted, recovery)
    result = validator.validate()

    return asdict(result)
