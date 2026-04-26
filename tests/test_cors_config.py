# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the ALLOWED_ORIGINS env override (AUDIT-004).

Covers:
- Default origins (env unset) preserve pre-audit behaviour.
- ALLOWED_ORIGINS parses comma-separated and trims whitespace.
- Empty / whitespace-only entries are dropped.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Iterator

import pytest


@pytest.fixture
def reload_app_with_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reload src.api.app so module-level env reads pick up new values."""
    import src.api.app as app_module

    monkeypatch.setattr(os.environ, "data", os.environ.copy(), raising=False)
    yield
    importlib.reload(app_module)


def _reload_and_get_origins(monkeypatch: pytest.MonkeyPatch, value: str | None) -> list[str]:
    if value is None:
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("ALLOWED_ORIGINS", value)
    import src.api.app as app_module

    importlib.reload(app_module)
    return list(app_module._CORS_ORIGINS)


def test_default_origins_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """ALLOWED_ORIGINS unset → pre-audit defaults preserved."""
    origins = _reload_and_get_origins(monkeypatch, None)
    assert "http://localhost:5173" in origins
    assert "http://localhost:4321" in origins
    assert "https://meridianiq.vitormr.dev" in origins


def test_custom_origins_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Comma-separated env value replaces the defaults entirely."""
    origins = _reload_and_get_origins(
        monkeypatch, "https://fork.example.com,https://staging.example.net"
    )
    assert origins == [
        "https://fork.example.com",
        "https://staging.example.net",
    ]


def test_whitespace_is_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Whitespace around commas is trimmed; empty entries are dropped."""
    origins = _reload_and_get_origins(monkeypatch, "  https://a.example  ,  , https://b.example  ")
    assert origins == ["https://a.example", "https://b.example"]


def test_empty_env_preserves_defaults_via_split(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicitly empty ALLOWED_ORIGINS yields empty list (opt-out).

    Behaviour-level note: setting the var to "" is an intentional
    "deny all" — the operator shuts down CORS.  That's distinct from
    unset (which restores defaults).  Documented here so the behaviour
    does not drift silently.
    """
    origins = _reload_and_get_origins(monkeypatch, "")
    assert origins == []
