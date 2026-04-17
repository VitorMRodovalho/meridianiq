# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for audit-trail IP / User-Agent capture (v3.8 wave 13).

Focuses on the ``_client_ip`` and ``_user_agent`` helpers which run
deterministically on any fastapi.Request.  The ``_audit`` writer itself
talks to Supabase and is only exercised in integration environments —
unit tests here confirm the extraction logic a proxied request goes
through before hitting the database.
"""

from __future__ import annotations

import pytest
from starlette.datastructures import Headers
from starlette.requests import Request

from src.api.organizations import _client_ip, _user_agent


def _make_request(
    headers: dict[str, str] | None = None,
    client: tuple[str, int] | None = ("127.0.0.1", 5000),
) -> Request:
    """Build a minimal ASGI scope for a synthesised Request."""
    raw_headers: list[tuple[bytes, bytes]] = [
        (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
    ]
    scope: dict = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": raw_headers,
        "client": client,
    }
    # Starlette normalises headers through its datastructure
    scope["headers"] = list(Headers(raw=scope["headers"]).raw)
    return Request(scope)


class TestClientIP:
    def test_x_forwarded_for_single_ip(self) -> None:
        req = _make_request(headers={"X-Forwarded-For": "203.0.113.42"})
        assert _client_ip(req) == "203.0.113.42"

    def test_x_forwarded_for_chain_takes_leftmost(self) -> None:
        """Comma-separated list — original client is the first entry."""
        req = _make_request(headers={"X-Forwarded-For": "203.0.113.42, 198.51.100.10, 10.0.0.1"})
        assert _client_ip(req) == "203.0.113.42"

    def test_x_forwarded_for_whitespace_trimmed(self) -> None:
        req = _make_request(headers={"X-Forwarded-For": "   203.0.113.42   "})
        assert _client_ip(req) == "203.0.113.42"

    def test_x_real_ip_fallback(self) -> None:
        """When XFF is absent, X-Real-IP wins over direct client."""
        req = _make_request(headers={"X-Real-IP": "203.0.113.99"})
        assert _client_ip(req) == "203.0.113.99"

    def test_direct_client_fallback_when_no_proxy_headers(self) -> None:
        req = _make_request()
        assert _client_ip(req) == "127.0.0.1"

    def test_none_request_returns_none(self) -> None:
        assert _client_ip(None) is None

    def test_no_client_and_no_headers_returns_none(self) -> None:
        req = _make_request(client=None)
        assert _client_ip(req) is None

    def test_xff_precedence_over_real_ip(self) -> None:
        """Both proxy headers present: XFF leftmost entry wins."""
        req = _make_request(
            headers={
                "X-Forwarded-For": "203.0.113.42",
                "X-Real-IP": "198.51.100.99",
            }
        )
        assert _client_ip(req) == "203.0.113.42"

    def test_empty_xff_falls_through_to_real_ip(self) -> None:
        """Empty XFF value shouldn't short-circuit the fallback chain."""
        req = _make_request(headers={"X-Forwarded-For": "", "X-Real-IP": "198.51.100.99"})
        assert _client_ip(req) == "198.51.100.99"


class TestUserAgent:
    def test_returns_header_value(self) -> None:
        req = _make_request(headers={"User-Agent": "MeridianIQ/3.8 (test)"})
        assert _user_agent(req) == "MeridianIQ/3.8 (test)"

    def test_none_when_header_missing(self) -> None:
        req = _make_request()
        assert _user_agent(req) is None

    def test_none_request_returns_none(self) -> None:
        assert _user_agent(None) is None

    def test_empty_header_returns_none(self) -> None:
        req = _make_request(headers={"User-Agent": ""})
        assert _user_agent(req) is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.2.3.4", "1.2.3.4"),
        ("1.2.3.4, 5.6.7.8", "1.2.3.4"),
        ("  1.2.3.4  ,  5.6.7.8  ", "1.2.3.4"),
        ("2001:db8::1", "2001:db8::1"),
        ("2001:db8::1, 5.6.7.8", "2001:db8::1"),
    ],
)
def test_xff_various_shapes(raw: str, expected: str) -> None:
    req = _make_request(headers={"X-Forwarded-For": raw})
    assert _client_ip(req) == expected
