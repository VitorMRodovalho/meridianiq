# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for src/api/observability.py — runtime snapshot + breadcrumb throttle.

Covers the diagnostic primitive that pairs with the 2026-05-06 OOM
incident response (Fly memory bump + admin/runtime endpoint).  The
module's contract is "diagnostic helpers must NEVER raise" — these
tests pin that invariant.
"""

from __future__ import annotations

import time

import pytest

from src.api import observability


def test_get_runtime_snapshot_returns_dict_with_expected_keys() -> None:
    snapshot = observability.get_runtime_snapshot()
    expected_keys = {
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
) -> None:
    """If get_runtime_snapshot raises, breadcrumb emission must NOT propagate.

    /health endpoint correctness is the load-bearing invariant.
    """
    observability._reset_throttle_for_tests()

    def _boom() -> dict:
        raise RuntimeError("simulated psutil meltdown")

    monkeypatch.setattr(observability, "get_runtime_snapshot", _boom)
    # Returns True (throttle was advanced) but did NOT raise.
    result = observability.maybe_emit_breadcrumb()
    assert result is True


def test_get_runtime_snapshot_version_is_non_empty() -> None:
    snapshot = observability.get_runtime_snapshot()
    assert snapshot["version"]
    assert snapshot["version"] != ""
