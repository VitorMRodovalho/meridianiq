# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""The rate limiter keys on the trusted client address, not the socket peer.

On Fly.io every connection reaches the app from the proxy's private
address, and uvicorn ignores forwarding headers from anything outside
``FORWARDED_ALLOW_IPS`` (default 127.0.0.1). Keying on the socket peer would
therefore put every client in one bucket: one caller's traffic would
exhaust the limit for everybody. ``deps.rate_limit_key`` reads the same
trusted address as the audit trail (``deps.trusted_client_ip``).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from src.api import deps
from src.api.deps import limiter, rate_limit_key, trusted_client_ip

slowapi = pytest.importorskip("slowapi")


def _request(
    headers: dict[str, str], client: tuple[str, int] | None = ("10.0.0.9", 5000)
) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": list(Headers(raw=raw).raw),
        "client": client,
    }
    return Request(scope)


class TestKey:
    def test_fly_client_ip_wins(self) -> None:
        req = _request({"Fly-Client-IP": "198.51.100.5", "X-Forwarded-For": "6.6.6.6, 203.0.113.7"})
        assert rate_limit_key(req) == "198.51.100.5"

    def test_rightmost_forwarded_hop_without_fly_header(self) -> None:
        req = _request({"X-Forwarded-For": "6.6.6.6, 203.0.113.7"})
        assert rate_limit_key(req) == "203.0.113.7"

    def test_socket_peer_last(self) -> None:
        assert rate_limit_key(_request({})) == "10.0.0.9"

    def test_no_client_at_all(self) -> None:
        assert trusted_client_ip(_request({}, client=None)) is None
        assert rate_limit_key(_request({}, client=None)) == "127.0.0.1"

    def test_the_limiter_uses_it(self) -> None:
        assert limiter._key_func is rate_limit_key  # type: ignore[attr-defined]

    def test_audit_trail_uses_the_same_address(self) -> None:
        from src.api import organizations

        assert organizations._client_ip is deps.trusted_client_ip


def _limited_app() -> FastAPI:
    """A minimal app on the real shared limiter.

    Built once per module: slowapi registers a route's limits under the
    function's qualified name, so decorating a fresh copy per test would
    stack the limits and count each request twice.
    """
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    @app.get("/limited")
    @limiter.limit("2/minute")
    def limited(request: Request) -> dict[str, bool]:
        return {"ok": True}

    return app


_APP = _limited_app()


@pytest.fixture
def limited_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The limiter switched on, with an empty store before and after."""
    monkeypatch.setattr(limiter, "enabled", True)
    limiter.reset()
    try:
        yield TestClient(_APP)
    finally:
        limiter.reset()


class TestBuckets:
    def _hit(self, client: TestClient, **headers: str) -> int:
        return client.get("/limited", headers=headers).status_code

    def test_each_client_address_has_its_own_bucket(self, limited_client: TestClient) -> None:
        a = {"Fly-Client-IP": "198.51.100.1"}
        b = {"Fly-Client-IP": "198.51.100.2"}
        assert [self._hit(limited_client, **a) for _ in range(3)] == [200, 200, 429]
        # Same socket peer (the TestClient), different client: not blocked by A.
        assert self._hit(limited_client, **b) == 200

    def test_forwarded_for_cannot_open_a_new_bucket_behind_fly(
        self, limited_client: TestClient
    ) -> None:
        fly = "198.51.100.3"
        assert self._hit(limited_client, **{"Fly-Client-IP": fly}) == 200
        assert self._hit(limited_client, **{"Fly-Client-IP": fly}) == 200
        spoofed = {"Fly-Client-IP": fly, "X-Forwarded-For": "7.7.7.7"}
        assert self._hit(limited_client, **spoofed) == 429
