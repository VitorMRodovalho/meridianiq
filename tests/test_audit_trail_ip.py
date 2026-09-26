# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for audit-trail IP / User-Agent capture (v3.8 wave 13).

Focuses on the ``_client_ip`` and ``_user_agent`` helpers which run
deterministically on any fastapi.Request.  The ``_audit`` writer itself
is exercised end to end in ``tests/test_tenancy_org_surfaces.py``.

Trust rule under test (``deps.trusted_client_ip``): a forwarding header is
read only when the deployment names it in ``TRUSTED_CLIENT_IP_HEADER``
(``fly-client-ip`` on Fly). For ``x-forwarded-for`` the RIGHTMOST hop is
used; a header that occurs twice resolves to its LAST occurrence; with no
configured header, or an empty one, the socket peer is used. ``X-Real-IP``
is never read.
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


@pytest.fixture
def header_mode(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    def set_mode(name: str | None) -> None:
        if name is None:
            monkeypatch.delenv("TRUSTED_CLIENT_IP_HEADER", raising=False)
        else:
            monkeypatch.setenv("TRUSTED_CLIENT_IP_HEADER", name)

    return set_mode


SPOOF = {"Fly-Client-IP": "6.6.6.6", "X-Forwarded-For": "6.6.6.6, 7.7.7.7", "X-Real-IP": "6.6.6.6"}


class TestNoTrustedHeader:
    """Direct connections (docker compose): every forwarding header is the client's."""

    def test_headers_are_ignored(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode(None)
        assert _client_ip(_make_request(headers=SPOOF)) == "127.0.0.1"

    def test_blank_setting_is_unset(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode("   ")
        assert _client_ip(_make_request(headers=SPOOF)) == "127.0.0.1"

    def test_none_request_returns_none(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode(None)
        assert _client_ip(None) is None

    def test_no_client_and_no_headers_returns_none(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode(None)
        assert _client_ip(_make_request(client=None)) is None


class TestFlyClientIP:
    def test_fly_client_ip_is_used(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode("fly-client-ip")
        req = _make_request(
            headers={"Fly-Client-IP": "198.51.100.7", "X-Forwarded-For": "6.6.6.6, 203.0.113.42"}
        )
        assert _client_ip(req) == "198.51.100.7"

    def test_setting_is_case_insensitive(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode("Fly-Client-IP")
        assert (
            _client_ip(_make_request(headers={"Fly-Client-IP": "198.51.100.7"})) == "198.51.100.7"
        )

    def test_forwarded_for_is_not_trusted_in_fly_mode(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode("fly-client-ip")
        assert _client_ip(_make_request(headers={"X-Forwarded-For": "203.0.113.42"})) == "127.0.0.1"

    def test_empty_value_falls_back_to_the_peer(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode("fly-client-ip")
        assert _client_ip(_make_request(headers={"Fly-Client-IP": "  "})) == "127.0.0.1"

    def test_last_occurrence_wins(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        """A proxy that appends leaves the client's copy first and its own last."""
        header_mode("fly-client-ip")
        raw = [(b"fly-client-ip", b"6.6.6.6"), (b"fly-client-ip", b"203.0.113.9")]
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": raw,
            "client": ("127.0.0.1", 5000),
        }
        assert _client_ip(Request(scope)) == "203.0.113.9"


class TestForwardedFor:
    def test_x_forwarded_for_single_ip(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode("x-forwarded-for")
        assert (
            _client_ip(_make_request(headers={"X-Forwarded-For": "203.0.113.42"})) == "203.0.113.42"
        )

    def test_chain_takes_rightmost(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode("x-forwarded-for")
        req = _make_request(headers={"X-Forwarded-For": "203.0.113.42, 198.51.100.10, 10.0.0.1"})
        assert _client_ip(req) == "10.0.0.1"

    def test_spoofed_leftmost_entry_is_not_recorded(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode("x-forwarded-for")
        req = _make_request(headers={"X-Forwarded-For": "6.6.6.6, 203.0.113.42"})
        assert _client_ip(req) == "203.0.113.42"

    def test_whitespace_and_trailing_empty_entries(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode("x-forwarded-for")
        req = _make_request(headers={"X-Forwarded-For": "6.6.6.6,   203.0.113.42  , "})
        assert _client_ip(req) == "203.0.113.42"

    def test_fly_header_is_not_trusted_in_forwarded_for_mode(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode("x-forwarded-for")
        assert _client_ip(_make_request(headers={"Fly-Client-IP": "6.6.6.6"})) == "127.0.0.1"

    def test_x_real_ip_is_never_trusted(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode("x-forwarded-for")
        assert _client_ip(_make_request(headers={"X-Real-IP": "203.0.113.99"})) == "127.0.0.1"

    def test_empty_value_falls_back_to_the_peer(self, header_mode) -> None:  # type: ignore[no-untyped-def]
        header_mode("x-forwarded-for")
        assert _client_ip(_make_request(headers={"X-Forwarded-For": ""})) == "127.0.0.1"


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
def test_xff_various_shapes(raw: str, expected: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTED_CLIENT_IP_HEADER", "x-forwarded-for")
    req = _make_request(headers={"X-Forwarded-For": raw})
    assert _client_ip(req) == expected
