# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Remote Supabase access requires an explicit opt-in.

``src/database/config.py`` loads ``.env`` at import, and a developer's
``.env`` usually carries the production project's URL and service-role
key. Every entry point that builds a Supabase client must therefore
refuse unless ``ALLOW_REMOTE_SUPABASE=1`` is set (the deployed app sets
it in ``fly.toml``).

Each guard is tested in both directions: refused without the opt-in, and
reaching ``create_client`` with it. The second arm is the control that
shows the test can tell the two states apart.
"""

from __future__ import annotations

import sys
import types

import pytest

_FAKE_URL = "https://example.invalid"
_FAKE_KEY = "not-a-real-key"


@pytest.fixture
def fake_credentials(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Set fake credentials and a recording ``supabase.create_client``."""
    monkeypatch.setenv("SUPABASE_URL", _FAKE_URL)
    monkeypatch.setenv("SUPABASE_ANON_KEY", _FAKE_KEY)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", _FAKE_KEY)
    monkeypatch.delenv("ALLOW_REMOTE_SUPABASE", raising=False)

    calls: list[tuple[str, str]] = []

    def _create_client(url: str, key: str) -> object:
        calls.append((url, key))
        return object()

    fake_module = types.ModuleType("supabase")
    fake_module.create_client = _create_client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "supabase", fake_module)
    return calls


def _settings(monkeypatch: pytest.MonkeyPatch, environment: str) -> object:
    from src.database import config

    monkeypatch.setenv("ENVIRONMENT", environment)
    return config.Settings()


class TestSettingsUseSupabase:
    def test_production_with_credentials_but_no_opt_in_stays_in_memory(
        self, monkeypatch: pytest.MonkeyPatch, fake_credentials: list
    ) -> None:
        settings = _settings(monkeypatch, "production")
        assert settings.use_supabase is False  # type: ignore[attr-defined]

    def test_production_with_opt_in_uses_supabase(
        self, monkeypatch: pytest.MonkeyPatch, fake_credentials: list
    ) -> None:
        monkeypatch.setenv("ALLOW_REMOTE_SUPABASE", "1")
        settings = _settings(monkeypatch, "production")
        assert settings.use_supabase is True  # type: ignore[attr-defined]

    @pytest.mark.parametrize("value", ["", "0", "true", "yes"])
    def test_only_the_literal_one_opts_in(
        self, monkeypatch: pytest.MonkeyPatch, fake_credentials: list, value: str
    ) -> None:
        monkeypatch.setenv("ALLOW_REMOTE_SUPABASE", value)
        settings = _settings(monkeypatch, "production")
        assert settings.use_supabase is False  # type: ignore[attr-defined]


class TestDatabaseClient:
    @pytest.fixture(autouse=True)
    def _reset_singleton(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.database import client

        monkeypatch.setattr(client, "_client", None)

    def test_refuses_without_opt_in(self, fake_credentials: list) -> None:
        from src.database.client import get_supabase_client

        with pytest.raises(RuntimeError, match="ALLOW_REMOTE_SUPABASE"):
            get_supabase_client()
        assert fake_credentials == []

    def test_creates_client_with_opt_in(
        self, monkeypatch: pytest.MonkeyPatch, fake_credentials: list
    ) -> None:
        from src.database import config
        from src.database.client import get_supabase_client

        monkeypatch.setenv("ALLOW_REMOTE_SUPABASE", "1")
        monkeypatch.setattr(config, "settings", config.Settings())
        get_supabase_client()
        assert fake_credentials == [(_FAKE_URL, _FAKE_KEY)]


class TestApiKeyClient:
    def test_refuses_without_opt_in(self, fake_credentials: list) -> None:
        from src.api.auth import _get_supabase_client

        assert _get_supabase_client() is None
        assert fake_credentials == []

    def test_creates_client_with_opt_in(
        self, monkeypatch: pytest.MonkeyPatch, fake_credentials: list
    ) -> None:
        from src.api.auth import _get_supabase_client

        monkeypatch.setenv("ALLOW_REMOTE_SUPABASE", "1")
        assert _get_supabase_client() is not None
        assert fake_credentials == [(_FAKE_URL, _FAKE_KEY)]


class TestMcpStore:
    @pytest.fixture(autouse=True)
    def _reset_store(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mcp_server = pytest.importorskip("src.mcp_server")
        monkeypatch.setattr(mcp_server, "_store", None)

    def test_uses_in_memory_store_without_opt_in(self, fake_credentials: list) -> None:
        from src.database.store import InMemoryStore
        from src.mcp_server import _get_store

        assert isinstance(_get_store(), InMemoryStore)
        assert fake_credentials == []

    def test_selects_supabase_store_with_opt_in(
        self, monkeypatch: pytest.MonkeyPatch, fake_credentials: list
    ) -> None:
        from src.database import store as store_module
        from src.mcp_server import _get_store

        class _Sentinel:
            pass

        monkeypatch.setenv("ALLOW_REMOTE_SUPABASE", "1")
        monkeypatch.setattr(store_module, "SupabaseStore", _Sentinel)
        assert isinstance(_get_store(), _Sentinel)


def test_conftest_blanks_credentials_for_the_suite() -> None:
    """The suite itself must never inherit usable credentials from .env."""
    import os

    # Read in a fresh test with no monkeypatching: conftest's values stand.
    assert os.environ.get("ALLOW_REMOTE_SUPABASE") is None
    assert os.environ.get("SUPABASE_URL") == ""
    assert os.environ.get("SUPABASE_SERVICE_ROLE_KEY") == ""
