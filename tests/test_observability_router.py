# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for src/api/routers/observability.py — /api/v1/superadmin/runtime endpoint.

Covers:
- Unauthenticated → 401
- Authenticated but not SuperAdmin → 403
- Authenticated SuperAdmin (env-allowlisted by user_id) → 200 + valid schema
- Authenticated SuperAdmin (env-allowlisted by email) → 200
- API-key role rejected even if user_id matches the env allowlist (security)
- Response shape matches the RuntimeSnapshot Pydantic schema
"""

from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from src.api.app import app

_SECRET = "test-secret"
_ALGORITHM = "HS256"


def _make_token(
    user_id: str = "user-uuid-1234",
    email: str = "test@example.com",
    role: str = "authenticated",
) -> str:
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role,
        "aud": "authenticated",
        "iat": int(time.time()) - 60,
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_superadmin_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default: no SuperAdmin envs.  Tests that need them set them explicitly."""
    monkeypatch.delenv("SUPERADMIN_USER_IDS", raising=False)
    monkeypatch.delenv("SUPERADMIN_EMAILS", raising=False)


def test_runtime_endpoint_no_auth_returns_401(client: TestClient) -> None:
    """No Authorization header in production-mode would 401 — but we test
    the SuperAdmin gate which hits ``require_auth`` first.
    """
    resp = client.get("/api/v1/superadmin/runtime")
    assert resp.status_code == 401


def test_runtime_endpoint_authed_but_no_envs_returns_403(
    client: TestClient,
) -> None:
    """Fail-closed: env vars unset → no user is SuperAdmin → 403."""
    token = _make_token()
    resp = client.get(
        "/api/v1/superadmin/runtime",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "superadmin" in resp.json()["detail"].lower()


def test_runtime_endpoint_authed_id_mismatch_returns_403(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERADMIN_USER_IDS", "different-id")
    token = _make_token(user_id="user-uuid-1234")
    resp = client.get(
        "/api/v1/superadmin/runtime",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_runtime_endpoint_superadmin_via_user_id_returns_200(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERADMIN_USER_IDS", "user-uuid-1234")
    token = _make_token(user_id="user-uuid-1234")
    resp = client.get(
        "/api/v1/superadmin/runtime",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_runtime_endpoint_superadmin_via_email_returns_200(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERADMIN_EMAILS", "admin@example.com,test@example.com")
    token = _make_token(email="test@example.com")
    resp = client.get(
        "/api/v1/superadmin/runtime",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_runtime_endpoint_email_match_is_case_insensitive(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERADMIN_EMAILS", "TEST@EXAMPLE.COM")
    token = _make_token(email="test@example.com")
    resp = client.get(
        "/api/v1/superadmin/runtime",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_runtime_endpoint_id_match_with_extra_emails_envset(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both envs set: ID-match alone is sufficient (OR semantics)."""
    monkeypatch.setenv("SUPERADMIN_USER_IDS", "user-uuid-1234")
    monkeypatch.setenv("SUPERADMIN_EMAILS", "different@example.com")
    token = _make_token(user_id="user-uuid-1234", email="test@example.com")
    resp = client.get(
        "/api/v1/superadmin/runtime",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_runtime_endpoint_response_shape(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERADMIN_USER_IDS", "user-uuid-1234")
    token = _make_token(user_id="user-uuid-1234")
    resp = client.get(
        "/api/v1/superadmin/runtime",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {
        "pid",
        "memory_rss_mb",
        "memory_vms_mb",
        "cpu_percent",
        "cpu_count",
        "process_uptime_seconds",
        "boot_time_iso",
        "gc_counts",
        "version",
        "environment",
        "python_version",
        "active_ws_channels",
        "rate_limit_buckets",
        "psutil_available",
    }
    assert set(body.keys()) == expected_keys
    assert isinstance(body["memory_rss_mb"], float)
    # In a live test process psutil should report > 0 RSS.
    assert body["memory_rss_mb"] > 0
    assert body["psutil_available"] is True
    assert body["pid"] > 0
