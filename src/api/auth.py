# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""JWT authentication middleware for Supabase Auth.

Verifies Supabase-issued JWTs on protected endpoints.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import jwt

from src.database.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """Decode and verify Supabase JWT. Returns user dict or None."""
    if credentials is None:
        return None

    token = credentials.credentials
    jwt_secret = settings.SUPABASE_JWT_SECRET

    if not jwt_secret:
        logger.warning("SUPABASE_JWT_SECRET not set — auth disabled")
        return None

    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return {
            "id": payload.get("sub"),
            "email": payload.get("email", ""),
            "role": payload.get("role", "authenticated"),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
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


def optional_auth(user: Optional[dict] = Depends(get_current_user)) -> Optional[dict]:
    """Dependency that makes auth optional in development, required in production.

    In development (ENVIRONMENT != 'production'): returns user or None (never raises).
    In production (ENVIRONMENT == 'production'): delegates to require_auth behaviour,
    raising 401 if no valid token is present.
    """
    if settings.ENVIRONMENT == "production" and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
