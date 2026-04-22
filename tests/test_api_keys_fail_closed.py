# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the fail-closed api_key hardening (audit AUDIT-002, issue #17).

Covers the contract:
- In production, a Supabase error on any api_keys operation raises
  HTTPException(503) — never silently falls through to in-memory.
- In development, the same error logs a warning and the in-memory
  dict remains the fallback so local tests work without Supabase.
- In production, an empty Supabase result is authoritative — the
  in-memory dict is NOT consulted.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import src.api.auth as auth_module
from src.api.auth import (
    _api_keys,
    list_api_keys,
    revoke_api_key,
    validate_api_key,
)
from src.database.config import settings


@pytest.fixture(autouse=True)
def _clean_in_memory() -> None:
    _api_keys.clear()


@pytest.fixture
def broken_supabase(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Install a mock Supabase client whose any call raises."""
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.side_effect = (
        RuntimeError("simulated supabase outage")
    )
    client.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.side_effect = (  # noqa: E501
        RuntimeError("simulated supabase outage")
    )
    monkeypatch.setattr(auth_module, "_get_supabase_client", lambda: client)
    return client


@pytest.fixture
def empty_supabase(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Install a mock Supabase client that always returns empty data."""
    client = MagicMock()
    empty_result = MagicMock()
    empty_result.data = []
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        empty_result
    )
    client.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = (  # noqa: E501
        empty_result
    )
    monkeypatch.setattr(auth_module, "_get_supabase_client", lambda: client)
    return client


# ---------------------------------------------------------------------------
# Production: fail-closed on Supabase errors
# ---------------------------------------------------------------------------


def test_validate_raises_503_in_production_on_supabase_error(
    monkeypatch: pytest.MonkeyPatch, broken_supabase: MagicMock
) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        validate_api_key("miq_testkey")
    assert exc_info.value.status_code == 503
    assert "degraded" in exc_info.value.detail.lower()


def test_list_raises_503_in_production_on_supabase_error(
    monkeypatch: pytest.MonkeyPatch, broken_supabase: MagicMock
) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        list_api_keys("user-1")
    assert exc_info.value.status_code == 503


def test_revoke_raises_503_in_production_on_supabase_error(
    monkeypatch: pytest.MonkeyPatch, broken_supabase: MagicMock
) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        revoke_api_key("user-1", "key-1")
    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Production: in-memory dict is NOT consulted on empty Supabase result
# ---------------------------------------------------------------------------


def test_in_memory_keys_ignored_in_production_on_empty_supabase(
    monkeypatch: pytest.MonkeyPatch, empty_supabase: MagicMock
) -> None:
    """A planted in-memory key must NOT validate in production when
    Supabase authoritatively returns empty."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    # Plant an entry that would match if in-memory were consulted
    raw_key = "miq_planted"
    key_hash = auth_module._hash_key(raw_key)
    _api_keys[key_hash] = {
        "key_id": "key_dev",
        "user_id": "user-1",
        "name": "dev",
        "created_at": "2026-04-22T00:00:00",
    }
    assert validate_api_key(raw_key) is None


def test_list_returns_empty_in_production_on_empty_supabase(
    monkeypatch: pytest.MonkeyPatch, empty_supabase: MagicMock
) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    _api_keys["any-hash"] = {
        "key_id": "key_dev",
        "user_id": "user-1",
        "name": "dev",
        "created_at": "2026-04-22T00:00:00",
    }
    assert list_api_keys("user-1") == []


# ---------------------------------------------------------------------------
# Development: fall-through to in-memory dict still works
# ---------------------------------------------------------------------------


def test_validate_falls_back_in_development_on_supabase_error(
    monkeypatch: pytest.MonkeyPatch, broken_supabase: MagicMock
) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "development", raising=False)
    raw_key = "miq_devkey"
    key_hash = auth_module._hash_key(raw_key)
    _api_keys[key_hash] = {
        "key_id": "key_dev",
        "user_id": "user-1",
        "name": "dev",
        "created_at": "2026-04-22T00:00:00",
    }
    user = validate_api_key(raw_key)
    assert user is not None
    assert user["id"] == "user-1"
    assert user["key_id"] == "key_dev"


def test_validate_falls_back_in_development_on_empty_supabase(
    monkeypatch: pytest.MonkeyPatch, empty_supabase: MagicMock
) -> None:
    """Dev workflow: Supabase returned empty but an in-memory key exists."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development", raising=False)
    raw_key = "miq_devkey"
    key_hash = auth_module._hash_key(raw_key)
    _api_keys[key_hash] = {
        "key_id": "key_dev",
        "user_id": "user-1",
        "name": "dev",
        "created_at": "2026-04-22T00:00:00",
    }
    user: Any = validate_api_key(raw_key)
    assert user is not None
    assert user["id"] == "user-1"
