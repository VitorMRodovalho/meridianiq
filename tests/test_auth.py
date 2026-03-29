# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for JWT authentication middleware (src/api/auth.py).

Covers:
- Valid JWT returns user dict
- Expired JWT raises 401
- Missing token returns None (optional_auth) / raises 401 (require_auth)
- Invalid/tampered token raises 401
"""

from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.api.auth import get_current_user, require_auth

_SECRET = "test-secret"
_ALGORITHM = "HS256"


def _make_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _make_token(extra: dict[str, Any] | None = None, expired: bool = False) -> str:
    payload: dict[str, Any] = {
        "sub": "user-uuid-1234",
        "email": "test@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "iat": int(time.time()) - 60,
        "exp": int(time.time()) - 1 if expired else int(time.time()) + 3600,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


# ---------------------------------------------------------------------------
# Test 1: Valid JWT returns user dict
# ---------------------------------------------------------------------------


def test_valid_jwt_returns_user():
    """A well-formed, unexpired JWT signed with the correct secret decodes correctly."""
    token = _make_token()
    creds = _make_credentials(token)
    user = get_current_user(creds)
    assert user is not None
    assert user["id"] == "user-uuid-1234"
    assert user["email"] == "test@example.com"
    assert user["role"] == "authenticated"


# ---------------------------------------------------------------------------
# Test 2: Expired JWT raises 401
# ---------------------------------------------------------------------------


def test_expired_jwt_raises_401():
    """An expired JWT raises HTTP 401 with 'Token expired' detail."""
    token = _make_token(expired=True)
    creds = _make_credentials(token)
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(creds)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Test 3: Missing token returns None (get_current_user / optional_auth)
# ---------------------------------------------------------------------------


def test_missing_token_returns_none():
    """No credentials yields None from get_current_user (dev-mode optional auth)."""
    user = get_current_user(None)  # type: ignore[arg-type]
    assert user is None


def test_require_auth_raises_401_when_no_token():
    """require_auth raises 401 when user is None."""
    with pytest.raises(HTTPException) as exc_info:
        require_auth(user=None)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Test 4: Invalid / tampered token raises 401
# ---------------------------------------------------------------------------


def test_invalid_token_raises_401():
    """A token signed with the wrong secret raises HTTP 401."""
    wrong_secret = "wrong-secret"
    token = jwt.encode(
        {
            "sub": "attacker",
            "email": "evil@example.com",
            "role": "authenticated",
            "aud": "authenticated",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        wrong_secret,
        algorithm=_ALGORITHM,
    )
    creds = _make_credentials(token)
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(creds)
    assert exc_info.value.status_code == 401
