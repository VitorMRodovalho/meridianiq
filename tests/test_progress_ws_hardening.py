# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Wave 0 #7 hardening tests for the progress WS channel.

Covers:
  - Ownership binding on ``open_channel`` prevents another user hijacking
    a channel by guessing its id.
  - Stale channels are reaped after ``_STALE_TTL_SECONDS`` inactivity.
  - ``POST /api/v1/jobs/progress/start`` returns a server-generated UUID
    bound to the authenticated user.
  - WS handler rejects non-UUID path params with close code 4404.
  - Static guards: modules import the hardened symbols the routers rely on.
"""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient

from src.api import progress
from src.api.app import app


@pytest.fixture(autouse=True)
def _reset_channels() -> None:
    progress._reset_for_tests()


class TestChannelOwnershipBinding:
    def test_same_owner_reopens_returns_existing_queue(self) -> None:
        q1 = progress.open_channel("aaaa", owner_user_id="user-1")
        q2 = progress.open_channel("aaaa", owner_user_id="user-1")
        assert q1 is q2, "same owner must observe the same queue (idempotent)"

    def test_different_owner_is_rejected(self) -> None:
        progress.open_channel("bbbb", owner_user_id="user-1")
        with pytest.raises(progress.ChannelAuthError):
            progress.open_channel("bbbb", owner_user_id="user-2")

    def test_unbound_channel_can_be_adopted_but_cannot_be_reclaimed_by_another(
        self,
    ) -> None:
        # Dev-mode flow: someone opens anonymously first, then an authed
        # caller adopts it.
        progress.open_channel("cccc", owner_user_id=None)
        # Adoption by any user is allowed when the channel is unbound.
        progress.open_channel("cccc", owner_user_id="user-1")
        # But a second different user attempting to bind must fail.
        with pytest.raises(progress.ChannelAuthError):
            progress.open_channel("cccc", owner_user_id="user-2")

    def test_get_channel_owner_returns_bound_user(self) -> None:
        progress.open_channel("dddd", owner_user_id="user-1")
        assert progress.get_channel_owner("dddd") == "user-1"

    def test_get_channel_owner_none_for_unknown(self) -> None:
        assert progress.get_channel_owner("never-existed") is None


class TestStaleChannelReaper:
    def test_reaper_evicts_channel_past_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        progress.open_channel("stale-1", owner_user_id="u")
        assert progress.channel_count() == 1

        # Fast-forward "now" past the TTL.
        fake_now = time.monotonic() + progress._STALE_TTL_SECONDS + 10
        reaped = progress.reap_stale_channels(now=fake_now)
        assert reaped == 1
        assert progress.channel_count() == 0

    def test_reaper_keeps_recent_channel(self) -> None:
        progress.open_channel("fresh-1", owner_user_id="u")
        reaped = progress.reap_stale_channels()
        assert reaped == 0
        assert progress.channel_count() == 1

    def test_opportunistic_reap_on_new_open_channel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """open_channel calls reap_stale_channels internally — a long-idle
        channel should be cleared when a new one is opened."""
        progress.open_channel("stale-2", owner_user_id="u")
        # Manually make it stale by rewinding its last_activity.
        progress._channels["stale-2"].last_activity = (
            time.monotonic() - progress._STALE_TTL_SECONDS - 10
        )
        progress.open_channel("fresh-2", owner_user_id="u")
        assert "stale-2" not in progress._channels
        assert "fresh-2" in progress._channels


class TestStartProgressJobEndpoint:
    def test_unauthenticated_in_production_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.database import config as cfg

        monkeypatch.setattr(cfg.settings, "ENVIRONMENT", "production")
        client = TestClient(app)
        resp = client.post("/api/v1/jobs/progress/start")
        assert resp.status_code == 401

    def test_authenticated_returns_uuid_and_ws_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """In development environment, ``require_auth`` still enforces; we
        stub it via dependency override."""
        from src.api import auth as auth_module
        from src.api.routers import ws as ws_module

        def _fake_require_auth() -> dict[str, str]:
            return {"id": "test-user", "email": "t@x", "role": "authenticated"}

        # Override at the router module level (import-time capture).
        app.dependency_overrides[auth_module.require_auth] = _fake_require_auth
        try:
            client = TestClient(app)
            resp = client.post("/api/v1/jobs/progress/start")
            assert resp.status_code == 201, resp.text
            body = resp.json()
            assert "job_id" in body
            job_id = body["job_id"]
            # Valid UUID v4 shape
            uuid.UUID(job_id)
            assert body["ws_url"] == f"/api/v1/ws/progress/{job_id}"
            # Channel is pre-opened and bound to the test user
            assert progress.get_channel_owner(job_id) == "test-user"
        finally:
            app.dependency_overrides.pop(auth_module.require_auth, None)
            # Keep ws_module reference used so linter doesn't drop the import.
            _ = ws_module


class TestWSPathParamValidation:
    def test_non_uuid_job_id_closes_with_4404(self) -> None:
        client = TestClient(app)
        # The handler closes BEFORE accept, so TestClient sees a WebSocket
        # that can't be entered — expect WebSocketDisconnect.
        from fastapi.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect("/api/v1/ws/progress/not-a-uuid") as ws:
                ws.receive_json()
        assert excinfo.value.code == 4404

    def test_uuid_job_id_passes_routing(self) -> None:
        """A valid UUID passes the UUID check in dev (even without auth,
        since dev permits unbound channels)."""
        import uuid as _uuid

        jid = str(_uuid.uuid4())
        client = TestClient(app)
        # Just confirm the connection is accepted — no events needed.
        with client.websocket_connect(f"/api/v1/ws/progress/{jid}") as ws:
            # Immediately close; the server should have opened the channel.
            assert progress.get_channel_owner(jid) is None  # unbound in dev
            ws.close()


class TestSourceGuards:
    """Static guards that the hardened symbols are imported by the router
    — regression-proofs against a refactor that drops them."""

    def test_progress_module_exposes_auth_error(self) -> None:
        assert hasattr(progress, "ChannelAuthError")
        assert issubclass(progress.ChannelAuthError, PermissionError)

    def test_ws_router_imports_channel_auth_error(self) -> None:
        from pathlib import Path

        source = Path("src/api/routers/ws.py").read_text(encoding="utf-8")
        assert "ChannelAuthError" in source
        assert "get_channel_owner" in source
        assert "start_progress_job" in source

    def test_progress_module_has_reaper(self) -> None:
        assert callable(progress.reap_stale_channels)
        assert progress._STALE_TTL_SECONDS > 0
