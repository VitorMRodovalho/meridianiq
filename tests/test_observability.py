# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for src/api/observability.py — runtime snapshot + breadcrumb throttle.

Covers the diagnostic primitive that pairs with the 2026-05-06 OOM
incident response (Fly memory bump + admin/runtime endpoint).  The
module's contract is "diagnostic helpers must NEVER raise" — these
tests pin that invariant.
"""

from __future__ import annotations

import logging
import os
import time

import pytest

from src.api import observability


def test_get_runtime_snapshot_returns_dict_with_expected_keys() -> None:
    snapshot = observability.get_runtime_snapshot()
    expected_keys = {
        "pid",
        "memory_rss_mb",
        "memory_vms_mb",
        "cpu_percent",
        "cpu_count",
        "process_uptime_seconds",
        "boot_time_iso",
        "gc_counts",
        "version",
        "environment",
        "python_version",
        "active_ws_channels",
        "rate_limit_buckets",
        "psutil_available",
    }
    assert set(snapshot.keys()) == expected_keys


def test_get_runtime_snapshot_field_types() -> None:
    snapshot = observability.get_runtime_snapshot()
    assert isinstance(snapshot["pid"], int)
    assert snapshot["pid"] > 0
    assert isinstance(snapshot["memory_rss_mb"], float)
    assert isinstance(snapshot["memory_vms_mb"], float)
    assert isinstance(snapshot["cpu_percent"], float)
    assert isinstance(snapshot["cpu_count"], int)
    assert isinstance(snapshot["process_uptime_seconds"], float)
    assert isinstance(snapshot["boot_time_iso"], str)
    assert isinstance(snapshot["gc_counts"], list)
    assert all(isinstance(c, int) for c in snapshot["gc_counts"])
    assert isinstance(snapshot["version"], str)
    assert isinstance(snapshot["environment"], str)
    assert isinstance(snapshot["python_version"], str)
    assert isinstance(snapshot["active_ws_channels"], int)
    assert isinstance(snapshot["rate_limit_buckets"], int)
    assert isinstance(snapshot["psutil_available"], bool)


def test_pid_matches_current_process() -> None:
    """The reported PID is the process running this test, not the import-time PID."""
    snapshot = observability.get_runtime_snapshot()
    assert snapshot["pid"] == os.getpid()


def test_psutil_fields_populated_when_available() -> None:
    """psutil is in the [api] / [dev] extras so this test env has it."""
    snapshot = observability.get_runtime_snapshot()
    assert snapshot["psutil_available"] is True
    # RSS must be > 0 in any live Python process; 0 would indicate that
    # the psutil branch failed silently (defensive try/except hid the bug).
    assert snapshot["memory_rss_mb"] > 0
    assert snapshot["memory_vms_mb"] > 0


def test_uptime_monotonically_increases() -> None:
    s1 = observability.get_runtime_snapshot()
    time.sleep(0.01)
    s2 = observability.get_runtime_snapshot()
    assert s2["process_uptime_seconds"] > s1["process_uptime_seconds"]


def test_python_version_format() -> None:
    snapshot = observability.get_runtime_snapshot()
    parts = snapshot["python_version"].split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_boot_time_iso_format() -> None:
    snapshot = observability.get_runtime_snapshot()
    # ISO-8601 UTC "YYYY-MM-DDTHH:MM:SSZ"
    boot = snapshot["boot_time_iso"]
    assert len(boot) == 20
    assert boot[4] == "-" and boot[7] == "-"
    assert boot[10] == "T"
    assert boot[-1] == "Z"


def test_active_ws_channels_returns_non_negative_int() -> None:
    """Defensive helper must NEVER raise — 0 on import failure is acceptable."""
    n = observability._active_ws_channels()
    assert isinstance(n, int)
    assert n >= 0


def test_rate_limit_buckets_returns_non_negative_int() -> None:
    n = observability._rate_limit_buckets()
    assert isinstance(n, int)
    assert n >= 0


def test_maybe_emit_breadcrumb_first_call_after_reset_returns_true() -> None:
    observability._reset_throttle_for_tests()
    assert observability.maybe_emit_breadcrumb() is True


def test_maybe_emit_breadcrumb_throttle_blocks_within_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observability._reset_throttle_for_tests()
    observability.maybe_emit_breadcrumb()
    # Second call immediately after — must be blocked by throttle.
    assert observability.maybe_emit_breadcrumb() is False
    assert observability.maybe_emit_breadcrumb() is False


def test_maybe_emit_breadcrumb_after_reset_unblocks() -> None:
    observability._reset_throttle_for_tests()
    observability.maybe_emit_breadcrumb()
    assert observability.maybe_emit_breadcrumb() is False
    observability._reset_throttle_for_tests()
    assert observability.maybe_emit_breadcrumb() is True


def test_maybe_emit_breadcrumb_swallows_snapshot_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If get_runtime_snapshot raises, breadcrumb emission must NOT propagate
    — but the WARNING log MUST fire, otherwise the leak-class failure that
    the diagnostic exists to surface would be silently swallowed forever.

    DA fix-up #P2 (PR #71): the original test only asserted ``result is True``,
    pinning the wrong invariant. The asserted logger.warning call is what
    keeps the next OOM investigation from finding the same diagnostic
    darkness as the 2026-05-06 incident.
    """
    observability._reset_throttle_for_tests()

    def _boom() -> dict:
        raise RuntimeError("simulated psutil meltdown")

    monkeypatch.setattr(observability, "get_runtime_snapshot", _boom)
    with caplog.at_level(logging.WARNING, logger="src.api.observability"):
        result = observability.maybe_emit_breadcrumb()

    # Throttle advanced (the contract; tests would otherwise tight-loop).
    assert result is True
    # The failure path MUST log a WARNING with the underlying exception.
    matching = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and "breadcrumb emission failed" in r.getMessage()
        and "simulated psutil meltdown" in r.getMessage()
    ]
    assert matching, (
        "expected logger.warning('breadcrumb emission failed: ...') with the "
        "underlying exception text — defensive code must remain VISIBLE in logs"
    )


def test_get_runtime_snapshot_version_is_non_empty() -> None:
    snapshot = observability.get_runtime_snapshot()
    assert snapshot["version"]
    assert snapshot["version"] != ""


def test_read_breadcrumb_interval_env_default() -> None:
    """Unset env returns the documented default 300s."""
    import os

    os.environ.pop("RUNTIME_BREADCRUMB_INTERVAL_SECONDS", None)
    assert observability._read_breadcrumb_interval_env() == 300.0


def test_read_breadcrumb_interval_env_non_numeric_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """DA fix-up #P1 (PR #71): non-numeric env must not brick startup."""
    monkeypatch.setenv("RUNTIME_BREADCRUMB_INTERVAL_SECONDS", "5min")
    with caplog.at_level(logging.WARNING, logger="src.api.observability"):
        value = observability._read_breadcrumb_interval_env()
    assert value == 300.0
    assert any("non-numeric" in r.getMessage() for r in caplog.records)


def test_read_breadcrumb_interval_env_clamps_below_minimum(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Below-5s values clamp to 5s with a warning — guards the Fly log /
    Sentry quota during an active incident."""
    monkeypatch.setenv("RUNTIME_BREADCRUMB_INTERVAL_SECONDS", "0")
    with caplog.at_level(logging.WARNING, logger="src.api.observability"):
        value = observability._read_breadcrumb_interval_env()
    assert value == 5.0
    assert any("below 5s minimum" in r.getMessage() for r in caplog.records)


def test_read_breadcrumb_interval_env_negative_clamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_BREADCRUMB_INTERVAL_SECONDS", "-100")
    assert observability._read_breadcrumb_interval_env() == 5.0


def test_read_breadcrumb_interval_env_valid_passes_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_BREADCRUMB_INTERVAL_SECONDS", "60")
    assert observability._read_breadcrumb_interval_env() == 60.0


def test_rate_limit_buckets_contract_pin() -> None:
    """DA fix-up #P3 (PR #71): pin the slowapi private-internals contract.

    ``_rate_limit_buckets`` reaches into ``limiter._storage.storage``.
    A future slowapi bump that renames either layer would silently turn
    this into 0 forever.  This test asserts the structure exists at the
    expected path so a contract regression fails LOUDLY.
    """
    from src.api.deps import limiter

    storage = getattr(limiter, "_storage", None)
    assert storage is not None, "slowapi Limiter._storage missing — contract drift"
    backing = getattr(storage, "storage", None)
    assert backing is not None, "MemoryStorage.storage missing — contract drift"
    assert hasattr(backing, "__len__"), (
        "Expected dict-like backing (Counter); got something with no __len__"
    )
