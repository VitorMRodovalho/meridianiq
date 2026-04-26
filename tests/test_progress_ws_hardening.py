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


class TestStartProgressJobRateLimit:
    """ADR-0019 §"W0 — D1": ``POST /api/v1/jobs/progress/start`` is
    decorated with ``@limiter.limit(RATE_LIMIT_READ)`` (30/minute).
    Without a cap a single client can exhaust memory by allocating
    channels in a tight loop; the 15-minute reaper bounds long-term
    leakage but does nothing against burst abuse.

    conftest.py sets ``RATE_LIMIT_ENABLED=false`` for the suite so
    tests don't fight the limiter accidentally; this test flips it
    back on for one run, then resets the limiter in finally so it
    cannot pollute later tests that share the in-memory backend.
    """

    def test_thirty_first_call_within_minute_returns_429(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api import auth as auth_module
        from src.api.deps import limiter as api_limiter

        if not hasattr(api_limiter, "enabled"):
            # slowapi not installed; ``deps._NoOpLimiter`` is active and
            # ``@limiter.limit`` is a pass-through. ADR-0019 §"W0 — D10"
            # adds slowapi to the [dev] extras so this branch goes away
            # in CI; keep the skip for environments that haven't refreshed.
            pytest.skip("slowapi _NoOpLimiter fallback — rate-limit not active")

        monkeypatch.setattr(api_limiter, "enabled", True)
        # Reset the in-memory backend — previous tests may have consumed
        # part of the per-IP budget already.
        if hasattr(api_limiter, "reset"):
            api_limiter.reset()

        def _fake_require_auth() -> dict[str, str]:
            return {"id": "test-user", "email": "t@x", "role": "authenticated"}

        app.dependency_overrides[auth_module.require_auth] = _fake_require_auth
        try:
            client = TestClient(app)
            tenth_status: int | None = None
            last_status: int | None = None
            for i in range(31):
                resp = client.post("/api/v1/jobs/progress/start")
                last_status = resp.status_code
                if i == 9:  # 10th call (0-indexed) — sanity check still allowed
                    tenth_status = resp.status_code
            assert tenth_status == 201, (
                f"10th call should still be allowed under 30/min; got {tenth_status}"
            )
            assert last_status == 429, (
                f"expected 429 on 31st call, got {last_status} "
                "(RATE_LIMIT_READ=30/min not enforced on jobs/progress/start)"
            )
        finally:
            app.dependency_overrides.pop(auth_module.require_auth, None)
            # Reset the bucket so this test's 31 entries don't poison
            # later tests that flip ``enabled=True`` (e.g. the optimize
            # rate-limit test) — slowapi's in-memory backend is shared
            # across tests in the same process.
            if hasattr(api_limiter, "reset"):
                api_limiter.reset()


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


class TestHeartbeatAndTokenExpiry:
    """ADR-0019 §"W1 — D3" — server-initiated heartbeat that re-checks
    JWT ``exp`` and emits an ``auth_check`` keepalive frame every
    ``HEARTBEAT_INTERVAL_SECONDS``. On expiry the WS closes 4401.
    """

    def test_decode_exp_unverified_extracts_exp_claim(self) -> None:
        from src.api.routers import ws as ws_module

        import jwt as _jwt
        import time as _time

        future_exp = int(_time.time()) + 3600
        token = _jwt.encode(
            {"sub": "u", "aud": "authenticated", "exp": future_exp},
            "test-secret",
            algorithm="HS256",
        )
        decoded_exp = ws_module._decode_exp_unverified(token)
        assert decoded_exp == float(future_exp)

    def test_decode_exp_unverified_returns_none_for_no_exp(self) -> None:
        from src.api.routers import ws as ws_module

        import jwt as _jwt

        token = _jwt.encode(
            {"sub": "u", "aud": "authenticated"},
            "test-secret",
            algorithm="HS256",
        )
        assert ws_module._decode_exp_unverified(token) is None

    def test_decode_exp_unverified_returns_none_for_malformed(self) -> None:
        from src.api.routers import ws as ws_module

        assert ws_module._decode_exp_unverified("not-a-jwt") is None
        assert ws_module._decode_exp_unverified(None) is None
        assert ws_module._decode_exp_unverified("") is None

    def test_heartbeat_emits_auth_check_frame_when_hb_opted_in(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With a fast heartbeat interval AND ``?hb=1`` opt-in, the
        first frame on an authenticated WS with no progress event in
        flight is the server-initiated ``auth_check`` keepalive."""
        from src.api.routers import ws as ws_module

        import jwt as _jwt
        import time as _time
        import uuid as _uuid

        # Drop heartbeat to a value the test harness can wait on.
        monkeypatch.setattr(ws_module, "HEARTBEAT_INTERVAL_SECONDS", 0.05)

        future_exp = int(_time.time()) + 3600
        token = _jwt.encode(
            {"sub": "u", "aud": "authenticated", "exp": future_exp},
            "test-secret",
            algorithm="HS256",
        )
        jid = str(_uuid.uuid4())
        client = TestClient(app)

        with client.websocket_connect(f"/api/v1/ws/progress/{jid}?token={token}&hb=1") as ws:
            event = ws.receive_json()
            assert event["type"] == "auth_check", (
                f"first server-initiated frame should be auth_check; got {event}"
            )
            assert "ts" in event

    def test_no_hb_query_param_silences_heartbeat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Legacy frontend bundles (no ``?hb=1``) must keep the v4.0.1
        silent-streaming behavior — no ``auth_check`` frames. Otherwise
        a stale tab cached before this deploy would mis-classify the
        unknown frame as ``error`` and fail every long-running job 30s
        in. We assert the silence by waiting one heartbeat interval and
        verifying the queue is empty (no frame was sent)."""
        from src.api.routers import ws as ws_module

        import jwt as _jwt
        import time as _time
        import uuid as _uuid

        monkeypatch.setattr(ws_module, "HEARTBEAT_INTERVAL_SECONDS", 0.05)

        future_exp = int(_time.time()) + 3600
        token = _jwt.encode(
            {"sub": "u", "aud": "authenticated", "exp": future_exp},
            "test-secret",
            algorithm="HS256",
        )
        jid = str(_uuid.uuid4())
        client = TestClient(app)

        with client.websocket_connect(f"/api/v1/ws/progress/{jid}?token={token}") as ws:
            # Without ``hb=1``, no heartbeat. Use a tiny receive timeout
            # to confirm silence; ``starlette`` TestClient surfaces no
            # native non-blocking receive, so we sleep past one
            # heartbeat interval and try a non-blocking read.
            _time.sleep(0.15)
            # A clean way to assert "nothing sent" via TestClient is
            # send a producer event and verify it's the FIRST thing
            # received (no auth_check ahead of it).
            from src.api import progress as _progress

            _progress.publish(jid, {"type": "done", "simulation_id": "sim-test"})
            event = ws.receive_json()
            assert event["type"] == "done", (
                f"expected first frame to be the producer ``done`` (no heartbeat ahead); got {event}"
            )

    def test_revoked_api_key_closes_with_4401_on_heartbeat(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """API-key sessions don't have a JWT ``exp`` — they need
        revocation re-checks. Flip ``validate_api_key`` to return
        ``None`` (revoked) and confirm the heartbeat closes 4401."""
        from fastapi.websockets import WebSocketDisconnect

        from src.api.routers import ws as ws_module

        import uuid as _uuid

        monkeypatch.setattr(ws_module, "HEARTBEAT_INTERVAL_SECONDS", 0.05)

        # Stub validate_api_key: first call (handshake) returns a user;
        # subsequent calls (heartbeat re-check) return None (revoked).
        call_count = {"n": 0}

        def _stub_validate(key: str) -> dict | None:
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"id": "key-user", "email": "k@x", "role": "authenticated"}
            return None

        monkeypatch.setattr(ws_module, "validate_api_key", _stub_validate)

        jid = str(_uuid.uuid4())
        client = TestClient(app)

        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect(f"/api/v1/ws/progress/{jid}?api_key=fake-key&hb=1") as ws:
                ws.receive_json()
        assert excinfo.value.code == 4401, (
            f"expected close 4401 on heartbeat with revoked api_key; got {excinfo.value.code}"
        )

    def test_expired_token_closes_with_4401_on_heartbeat(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Token that becomes expired between handshake and the first
        heartbeat tick is detected by ``_decode_exp_unverified`` ≥
        ``time.time()`` and triggers a 4401 close. We monkey-patch the
        unverified-decode helper to short-circuit the fixture to an
        already-past exp, since making the real JWT validate-at-handshake
        and then expire-by-tick is racy at sub-second timing.
        """
        from fastapi.websockets import WebSocketDisconnect

        from src.api.routers import ws as ws_module

        import jwt as _jwt
        import time as _time
        import uuid as _uuid

        monkeypatch.setattr(ws_module, "HEARTBEAT_INTERVAL_SECONDS", 0.05)
        # Force the heartbeat helper to report an exp in the past.
        monkeypatch.setattr(ws_module, "_decode_exp_unverified", lambda token: _time.time() - 1)

        future_exp = int(_time.time()) + 3600
        token = _jwt.encode(
            {"sub": "u", "aud": "authenticated", "exp": future_exp},
            "test-secret",
            algorithm="HS256",
        )
        jid = str(_uuid.uuid4())
        client = TestClient(app)

        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect(f"/api/v1/ws/progress/{jid}?token={token}&hb=1") as ws:
                ws.receive_json()
        assert excinfo.value.code == 4401, (
            f"expected close 4401 on heartbeat with expired token; got {excinfo.value.code}"
        )


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
