# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for audit-trail IP / User-Agent capture (v3.8 wave 13).

Focuses on the ``_client_ip`` and ``_user_agent`` helpers which run
deterministically on any fastapi.Request.  The ``_audit`` writer itself
is exercised end to end in ``tests/test_tenancy_org_surfaces.py``.

Trust rule under test: ``Fly-Client-IP`` (set by Fly.io's edge), else the
RIGHTMOST ``X-Forwarded-For`` entry (appended by the proxy in front of the
app), else the socket peer. Leftmost ``X-Forwarded-For`` entries and
``X-Real-IP`` arrive from the client and are never recorded.
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

    def test_x_forwarded_for_chain_takes_rightmost(self) -> None:
        """The rightmost entry is the proxy's; everything left of it is client-supplied."""
        req = _make_request(headers={"X-Forwarded-For": "203.0.113.42, 198.51.100.10, 10.0.0.1"})
        assert _client_ip(req) == "10.0.0.1"

    def test_spoofed_leftmost_entry_is_not_recorded(self) -> None:
        req = _make_request(headers={"X-Forwarded-For": "6.6.6.6, 203.0.113.42"})
        assert _client_ip(req) == "203.0.113.42"

    def test_x_forwarded_for_whitespace_trimmed(self) -> None:
        req = _make_request(headers={"X-Forwarded-For": "   203.0.113.42   "})
        assert _client_ip(req) == "203.0.113.42"

    def test_trailing_empty_entries_are_skipped(self) -> None:
        req = _make_request(headers={"X-Forwarded-For": "6.6.6.6, 203.0.113.42, "})
        assert _client_ip(req) == "203.0.113.42"

    def test_fly_client_ip_wins(self) -> None:
        req = _make_request(
            headers={
                "Fly-Client-IP": "198.51.100.7",
                "X-Forwarded-For": "6.6.6.6, 203.0.113.42",
                "X-Real-IP": "6.6.6.6",
            }
        )
        assert _client_ip(req) == "198.51.100.7"

    def test_empty_fly_client_ip_falls_through_to_forwarded_for(self) -> None:
        req = _make_request(headers={"Fly-Client-IP": "  ", "X-Forwarded-For": "203.0.113.42"})
        assert _client_ip(req) == "203.0.113.42"

    def test_x_real_ip_is_not_trusted(self) -> None:
        """Nothing in this deployment sets X-Real-IP, so it is whatever the client sent."""
        req = _make_request(headers={"X-Real-IP": "203.0.113.99"})
        assert _client_ip(req) == "127.0.0.1"

    def test_direct_client_fallback_when_no_proxy_headers(self) -> None:
        req = _make_request()
        assert _client_ip(req) == "127.0.0.1"

    def test_none_request_returns_none(self) -> None:
        assert _client_ip(None) is None

    def test_no_client_and_no_headers_returns_none(self) -> None:
        req = _make_request(client=None)
        assert _client_ip(req) is None

    def test_xff_precedence_over_real_ip(self) -> None:
        """Both proxy headers present: the forwarded-for hop wins."""
        req = _make_request(
            headers={
                "X-Forwarded-For": "203.0.113.42",
                "X-Real-IP": "198.51.100.99",
            }
        )
        assert _client_ip(req) == "203.0.113.42"

    def test_empty_xff_falls_through_to_socket_peer(self) -> None:
        """An empty XFF value does not short-circuit, and X-Real-IP is still ignored."""
        req = _make_request(headers={"X-Forwarded-For": "", "X-Real-IP": "198.51.100.99"})
        assert _client_ip(req) == "127.0.0.1"


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
        ("1.2.3.4, 5.6.7.8", "5.6.7.8"),
        ("  1.2.3.4  ,  5.6.7.8  ", "5.6.7.8"),
        ("2001:db8::1", "2001:db8::1"),
        ("5.6.7.8, 2001:db8::1", "2001:db8::1"),
    ],
)
def test_xff_various_shapes(raw: str, expected: str) -> None:
    req = _make_request(headers={"X-Forwarded-For": raw})
    assert _client_ip(req) == expected
