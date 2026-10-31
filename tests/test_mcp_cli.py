# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the MCP server CLI argument parsing.

We don't actually start the server (would block on a socket); we exercise
the argparse layer and verify which transport options reach ``run()`` when
the http / sse transports are selected.
"""

from __future__ import annotations

import importlib

import pytest

# Skip on the *SDK*, not on this module.  ``importorskip("src.mcp_server")``
# reports a broken module as an absent one, because the ``ModuleNotFoundError``
# raised by mcp 2.x dropping ``mcp.server.fastmcp`` is an ``ImportError``
# subclass — so it stayed green through the #227 regression it appears to
# cover.  Keyed this way, a missing extra skips and a broken import fails.
pytest.importorskip("mcp", reason="the `mcp` extra is not installed")

mcp_server = importlib.import_module("src.mcp_server")


def test_default_transport_is_stdio() -> None:
    args = mcp_server._parse_args([])
    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_http_transport_accepted() -> None:
    args = mcp_server._parse_args(["--transport", "http"])
    assert args.transport == "http"


def test_sse_transport_accepted() -> None:
    args = mcp_server._parse_args(["--transport", "sse"])
    assert args.transport == "sse"


def test_invalid_transport_rejected() -> None:
    with pytest.raises(SystemExit):
        mcp_server._parse_args(["--transport", "websocket"])


def test_host_and_port_overrides() -> None:
    args = mcp_server._parse_args(["--transport", "http", "--host", "0.0.0.0", "--port", "9090"])
    assert args.host == "0.0.0.0"
    assert args.port == 9090


def test_main_passes_host_and_port_to_run_for_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """When --transport http is selected, run() receives the host + port."""
    captured: dict = {}

    def fake_run(self: object, transport: str = "stdio", **kwargs: object) -> None:
        captured["transport"] = transport
        captured.update(kwargs)

    monkeypatch.setattr(mcp_server.mcp, "run", fake_run.__get__(mcp_server.mcp))
    mcp_server.main(["--transport", "http", "--host", "0.0.0.0", "--port", "8765"])

    assert captured == {"transport": "streamable-http", "host": "0.0.0.0", "port": 8765}


def test_main_passes_host_and_port_to_run_for_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_run(self: object, transport: str = "stdio", **kwargs: object) -> None:
        captured["transport"] = transport
        captured.update(kwargs)

    monkeypatch.setattr(mcp_server.mcp, "run", fake_run.__get__(mcp_server.mcp))
    mcp_server.main(["--transport", "sse", "--port", "8766"])

    assert captured == {"transport": "sse", "host": "127.0.0.1", "port": 8766}


def test_server_reports_the_package_version() -> None:
    """mcp 2.x reports an empty version unless the server is given one."""
    from importlib.metadata import version

    assert mcp_server.mcp.version == version("meridianiq")


def test_main_uses_stdio_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_run(self: object, transport: str = "stdio", **kwargs: object) -> None:
        captured["transport"] = transport
        captured.update(kwargs)

    monkeypatch.setattr(mcp_server.mcp, "run", fake_run.__get__(mcp_server.mcp))
    mcp_server.main([])

    assert captured == {"transport": "stdio"}
