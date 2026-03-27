# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""JWT authentication middleware for Supabase Auth.

Supports both HS256 (classic Supabase) and RS256 (newer Supabase projects).
Auto-detects the algorithm from the token header.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
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
        elif alg in ("RS256", "RS384", "RS512"):
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
            raise HTTPException(
                status_code=401, detail=f"Unsupported JWT algorithm: {alg}"
            )

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


def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """Optional auth — returns user or None, never raises in development.

    In production: raises 401 if no valid token.
    In development: returns None (tests pass without tokens).
    """
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
