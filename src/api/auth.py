# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""JWT + API Key authentication middleware for Supabase Auth.

Supports:
- JWT (HS256, RS256, ES256) via Supabase Auth
- API keys via X-API-Key header for programmatic access

Auto-detects the algorithm from the token header.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import jwt
from jwt import PyJWKClient

from src.database.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# Cache for JWKS client (RS256 verification)
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient | None:
    """Lazy-initialize JWKS client for RS256 token verification."""
    global _jwks_client
    if _jwks_client is None and settings.SUPABASE_URL:
        jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url)
        logger.info("Initialized JWKS client: %s", jwks_url)
    return _jwks_client


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """Extract and verify user from Supabase JWT.

    Supports both HS256 and RS256 algorithms. Checks the token header
    to determine which verification method to use.
    """
    if credentials is None:
        return None

    token = credentials.credentials

    try:
        # Read the token header to detect algorithm
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg", "HS256")
        logger.debug("JWT algorithm: %s", alg)

        if alg == "HS256":
            # Classic Supabase: verify with shared secret
            jwt_secret = settings.SUPABASE_JWT_SECRET
            if not jwt_secret:
                logger.warning("SUPABASE_JWT_SECRET not set — auth disabled")
                return None
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        elif alg in ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512"):
            # Newer Supabase: verify with JWKS public key
            jwks_client = _get_jwks_client()
            if not jwks_client:
                raise HTTPException(
                    status_code=500,
                    detail="Server misconfiguration: SUPABASE_URL not set for JWKS",
                )
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
            )
        else:
            raise HTTPException(status_code=401, detail=f"Unsupported JWT algorithm: {alg}")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user ID")

        return {
            "id": user_id,
            "email": payload.get("email", ""),
            "role": payload.get("role", "authenticated"),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def require_auth(user: Optional[dict] = Depends(get_current_user)) -> dict:
    """Dependency that requires authentication. Raises 401 if not authenticated."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _is_superadmin(user: dict) -> bool:
    """Return True if the authenticated user is a SuperAdmin.

    SuperAdmin is the top of the 5-tier role hierarchy
    (SuperAdmin → Enterprise → Program → Project → Contract).  Today
    it is env-gated via ``SUPERADMIN_USER_IDS`` (comma-separated
    Supabase user UUIDs) and/or ``SUPERADMIN_EMAILS`` (comma-separated
    case-insensitive emails).  A future Tier-model migration will
    replace this primitive with a DB-backed ``users.tier`` column.

    Fail-closed: if neither env var is set, no user is SuperAdmin.

    API-key callers are NEVER SuperAdmin in this primitive — even if
    their ``user_id`` matches.  SuperAdmin actions must originate from
    a session JWT (proves recent human auth via OAuth) so an exfil-
    trated long-lived API key cannot be used to e.g. force a Fly
    restart or read runtime memory of arbitrary other users' sessions.
    """
    import os

    if user.get("role") == "api_key":
        return False

    ids_env = os.environ.get("SUPERADMIN_USER_IDS", "").strip()
    emails_env = os.environ.get("SUPERADMIN_EMAILS", "").strip()
    if not ids_env and not emails_env:
        return False

    if ids_env:
        allowed_ids = {s.strip() for s in ids_env.split(",") if s.strip()}
        if user.get("id") in allowed_ids:
            return True

    if emails_env:
        allowed_emails = {s.strip().lower() for s in emails_env.split(",") if s.strip()}
        user_email = (user.get("email") or "").strip().lower()
        if user_email and user_email in allowed_emails:
            return True

    return False


def require_superadmin(user: dict = Depends(require_auth)) -> dict:
    """Dependency that requires the caller to be a SuperAdmin.

    Layered on top of ``require_auth`` — first proves authentication
    (raises 401 if no valid token), then proves SuperAdmin tier
    (raises 403 if authenticated but not SuperAdmin).

    See ``_is_superadmin`` for the env-gated allowlist contract.
    """
    if not _is_superadmin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SuperAdmin access required",
        )
    return user


def optional_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """Optional auth — returns user or None, never raises in development.

    Checks X-API-Key header first, then falls back to JWT Bearer token.
    In production: raises 401 if no valid token.
    In development: returns None (tests pass without tokens).
    """
    # Check API key first
    api_key = request.headers.get("x-api-key")
    if api_key:
        user = validate_api_key(api_key)
        if user:
            return user
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not credentials:
        if settings.ENVIRONMENT == "production":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None
    try:
        return get_current_user(credentials)
    except HTTPException:
        if settings.ENVIRONMENT == "production":
            raise
        return None


# ══════════════════════════════════════════════════════════
# API Key Management
# ══════════════════════════════════════════════════════════

# ── API Key Store ────────────────────────────────────────
# Uses Supabase when available, falls back to in-memory for dev.

_api_keys: dict[str, dict] = {}  # In-memory fallback


def _get_supabase_client() -> object | None:
    """Get Supabase client if configured."""
    try:
        import os

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return None
        from supabase import create_client

        return create_client(url, key)
    except Exception:
        return None


def _hash_key(key: str) -> str:
    """Hash an API key for secure storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key(user_id: str, name: str = "default") -> dict:
    """Generate a new API key for a user.

    Persists to Supabase ``api_keys`` table if available,
    otherwise stores in-memory.  The raw key is returned only once.

    Args:
        user_id: The user's ID.
        name: A friendly name for the key.

    Returns:
        Dict with key (raw, show once), key_id, name, created_at.
    """
    raw_key = f"miq_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)
    key_id = f"key_{secrets.token_hex(4)}"
    created_at = datetime.now().isoformat()

    entry = {
        "key_id": key_id,
        "user_id": user_id,
        "name": name,
        "created_at": created_at,
    }

    # Try Supabase persistence
    sb = _get_supabase_client()
    if sb:
        try:
            sb.table("api_keys").insert(
                {
                    "key_id": key_id,
                    "key_hash": key_hash,
                    "user_id": user_id,
                    "name": name,
                    "created_at": created_at,
                }
            ).execute()
            logger.info("API key %s created for user %s (Supabase)", key_id, user_id)
        except Exception as exc:
            logger.warning("Supabase api_keys insert failed, using in-memory: %s", exc)
            _api_keys[key_hash] = entry
    else:
        _api_keys[key_hash] = entry

    return {
        "key": raw_key,
        "key_id": key_id,
        "name": name,
        "created_at": created_at,
    }


def validate_api_key(raw_key: str) -> Optional[dict]:
    """Validate an API key and return the associated user info.

    In production, Supabase is the sole source of truth.  If the
    Supabase lookup fails (network, auth service degraded, etc.) we
    fail-closed with HTTP 503 so the caller can distinguish
    "key is invalid" from "auth backend is unavailable".

    In development, we fall through to the in-memory ``_api_keys``
    dict after a Supabase miss / error so local testing works without
    a Supabase project.

    Per audit AUDIT-002 (issue #17): the prior ``except Exception: pass``
    silently swallowed Supabase errors AND allowed in-memory keys to
    be accepted in production.

    Args:
        raw_key: The raw API key from the request header.

    Returns:
        User dict with id, email, role — or None if invalid.

    Raises:
        HTTPException(503): In production when the Supabase lookup
            fails for any reason other than "no matching row".
    """
    key_hash = _hash_key(raw_key)

    sb = _get_supabase_client()
    if sb is not None:
        try:
            res = sb.table("api_keys").select("*").eq("key_hash", key_hash).execute()
        except Exception as exc:  # noqa: BLE001 — we convert to 503 below
            if settings.ENVIRONMENT == "production":
                logger.error("api_keys lookup failed: %s", exc)
                raise HTTPException(
                    status_code=503,
                    detail="Auth service degraded",
                ) from exc
            # Dev: log and fall through to in-memory so local workflows survive
            logger.warning("api_keys Supabase lookup failed (dev fallback): %s", exc)
        else:
            if res.data:
                entry = res.data[0]
                return {
                    "id": entry["user_id"],
                    "email": "",
                    "role": "api_key",
                    "key_id": entry["key_id"],
                }
            # Supabase responded with empty result → key is genuinely invalid
            if settings.ENVIRONMENT == "production":
                return None

    # Development-only in-memory fallback
    entry = _api_keys.get(key_hash)
    if entry is None:
        return None

    return {
        "id": entry["user_id"],
        "email": "",
        "role": "api_key",
        "key_id": entry["key_id"],
    }


def list_api_keys(user_id: str) -> list[dict]:
    """List all API keys for a user (without raw keys).

    In production, Supabase is the sole source of truth; the
    in-memory dict is not consulted (a user with zero keys must see
    an empty list, not dev leftovers).

    Per audit AUDIT-002 follow-up: the prior implementation mixed
    Supabase data with in-memory entries on error AND on empty
    result, creating a confusing hybrid.

    Args:
        user_id: The user's ID.

    Returns:
        List of key metadata (key_id, name, created_at).

    Raises:
        HTTPException(503): In production when Supabase is degraded.
    """
    sb = _get_supabase_client()
    if sb is not None:
        try:
            res = (
                sb.table("api_keys")
                .select("key_id, name, created_at")
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            if settings.ENVIRONMENT == "production":
                logger.error("api_keys list failed: %s", exc)
                raise HTTPException(
                    status_code=503,
                    detail="Auth service degraded",
                ) from exc
            logger.warning("api_keys list Supabase failed (dev fallback): %s", exc)
        else:
            # Even when data is empty, this is the authoritative answer in prod.
            if settings.ENVIRONMENT == "production":
                return list(res.data) if res.data else []
            if res.data:
                return list(res.data)
            # Dev: if Supabase returned empty, still show in-memory keys for local testing

    return [
        {"key_id": v["key_id"], "name": v["name"], "created_at": v["created_at"]}
        for v in _api_keys.values()
        if v["user_id"] == user_id
    ]


def revoke_api_key(user_id: str, key_id: str) -> bool:
    """Revoke an API key.

    In production, Supabase is the sole source of truth.  A successful
    DELETE returns True; a miss returns False.  In development, we
    also check the in-memory dict so local testing works without
    Supabase.

    Args:
        user_id: The user's ID (for ownership check).
        key_id: The key identifier to revoke.

    Returns:
        True if revoked, False if not found.

    Raises:
        HTTPException(503): In production when Supabase is degraded.
    """
    sb = _get_supabase_client()
    if sb is not None:
        try:
            res = (
                sb.table("api_keys").delete().eq("key_id", key_id).eq("user_id", user_id).execute()
            )
        except Exception as exc:  # noqa: BLE001
            if settings.ENVIRONMENT == "production":
                logger.error("api_keys revoke failed: %s", exc)
                raise HTTPException(
                    status_code=503,
                    detail="Auth service degraded",
                ) from exc
            logger.warning("api_keys revoke Supabase failed (dev fallback): %s", exc)
        else:
            if res.data:
                logger.info("API key %s revoked for user %s (Supabase)", key_id, user_id)
                return True
            if settings.ENVIRONMENT == "production":
                return False

    to_remove = None
    for h, v in _api_keys.items():
        if v["key_id"] == key_id and v["user_id"] == user_id:
            to_remove = h
            break
    if to_remove:
        del _api_keys[to_remove]
        return True
    return False
