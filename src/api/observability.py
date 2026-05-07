# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Runtime observability — process memory, CPU, GC, and uptime snapshot.

Single source of truth for the ``/api/v1/admin/runtime`` endpoint and a
throttled Sentry breadcrumb emitter wired into ``/health``.

Designed to diagnose slow native-allocation leaks (numpy / scipy /
Cairo / Pango) that accumulate across long-uptime Fly.io machines.
The 2026-05-06 OOM incident on instance ``0800d09a69e258`` (idle Fly
machine, ~40 days uptime, no user traffic) is the motivating event:
without runtime telemetry, post-mortem of an OOM-killed Python process
is opaque — the curve up to the kill is the only diagnostic, and it
must be captured proactively because the dead process cannot tell you.
"""

from __future__ import annotations

import gc
import logging
import os
import sys
import time
from typing import Any

logger = logging.getLogger(__name__)

# psutil is in the [api] extras (pyproject.toml).  Imported lazily so
# this module loads even when [api] is not installed (test envs).
# Stubs not shipped with psutil — types-psutil is unmaintained, so we
# accept the import-untyped at this single boundary.
try:
    import psutil  # type: ignore[import-untyped]

    _PSUTIL_AVAILABLE = True
    _PROCESS: "psutil.Process | None" = psutil.Process()
except ImportError:  # pragma: no cover — exercised via monkeypatch in tests
    psutil = None
    _PSUTIL_AVAILABLE = False
    _PROCESS = None


# Process start time captured at module import — i.e., when uvicorn
# imports the FastAPI app.  Wall-clock for the boot timestamp,
# monotonic for uptime accounting (immune to NTP / clock drift).
_BOOT_TS_WALL = time.time()
_BOOT_TS_MONO = time.monotonic()

# Throttle for Sentry breadcrumb emission from /health.  Module-level
# state — process-local, NOT shared across Fly machines.  That is
# intentional: each machine has its own memory leak curve to track.
_BREADCRUMB_INTERVAL_SECONDS = float(os.environ.get("RUNTIME_BREADCRUMB_INTERVAL_SECONDS", "300"))
_last_breadcrumb_mono: float = 0.0


def _read_version() -> str:
    """Best-effort meridianiq version string.

    Falls back through env → importlib.metadata → ``"unknown"`` so the
    snapshot ALWAYS returns a usable value.  Mirrors the
    ``src.api.app._RELEASE`` resolution chain.
    """
    if version := os.environ.get("FLY_RELEASE_VERSION"):
        return str(version)
    try:
        import importlib.metadata as md

        return md.version("meridianiq")
    except Exception:  # noqa: BLE001 — best-effort
        return "unknown"


def _active_ws_channels() -> int:
    """Count of currently-open WebSocket progress channels.

    Returns 0 if the progress module is unimportable (defensive — a
    diagnostic helper must NEVER raise, otherwise the snapshot
    endpoint becomes unreliable as a leak-curve probe).
    """
    try:
        from src.api.progress import channel_count

        return channel_count()
    except Exception:  # noqa: BLE001 — diagnostic must not raise
        return 0


def _rate_limit_buckets() -> int:
    """Best-effort bucket count of slowapi's MemoryStorage.

    ``limits.storage.memory.MemoryStorage`` exposes a public
    ``.storage`` attribute (a ``collections.Counter``).  This count
    is a coarse leak indicator — under normal load it stays low; a
    runaway IP allowlist would show as continuous growth here.
    """
    try:
        from src.api.deps import limiter

        storage = getattr(limiter, "_storage", None)
        if storage is None:
            return 0
        backing = getattr(storage, "storage", None)
        if backing is None:
            return 0
        return len(backing)
    except Exception:  # noqa: BLE001 — diagnostic must not raise
        return 0


def get_runtime_snapshot() -> dict[str, Any]:
    """Return a JSON-serialisable snapshot of process runtime state.

    Fields (all numeric defaults to 0 on introspection failure):

    - ``memory_rss_mb``  Resident set size — load-bearing leak metric
    - ``memory_vms_mb``  Virtual memory — diverges from RSS on fork
                         (signals subprocess presence; e.g.
                         materializer ProcessPoolExecutor spawn)
    - ``cpu_percent``    CPU % since the previous probe (first call
                         always reads 0 by psutil contract)
    - ``cpu_count``      Number of vCPUs visible to the process
    - ``process_uptime_seconds``  Monotonic seconds since module import
    - ``boot_time_iso``  ISO-8601 wall-clock at module import (UTC)
    - ``gc_counts``      Python GC generation counts ``[g0, g1, g2]``
    - ``version``        meridianiq version string
    - ``environment``    ``ENVIRONMENT`` env (production / development)
    - ``python_version`` ``major.minor.micro``
    - ``active_ws_channels``  Open WebSocket progress channels
    - ``rate_limit_buckets``  Estimate of slowapi MemoryStorage size
    - ``psutil_available``    True if psutil is importable
    """
    snapshot: dict[str, Any] = {
        "memory_rss_mb": 0.0,
        "memory_vms_mb": 0.0,
        "cpu_percent": 0.0,
        "cpu_count": os.cpu_count() or 1,
        "process_uptime_seconds": time.monotonic() - _BOOT_TS_MONO,
        "boot_time_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(_BOOT_TS_WALL)),
        "gc_counts": list(gc.get_count()),
        "version": _read_version(),
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "python_version": (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ),
        "active_ws_channels": _active_ws_channels(),
        "rate_limit_buckets": _rate_limit_buckets(),
        "psutil_available": _PSUTIL_AVAILABLE,
    }

    if _PSUTIL_AVAILABLE and _PROCESS is not None:
        try:
            mem = _PROCESS.memory_info()
            snapshot["memory_rss_mb"] = round(mem.rss / (1024 * 1024), 1)
            snapshot["memory_vms_mb"] = round(mem.vms / (1024 * 1024), 1)
            # ``cpu_percent(interval=None)`` returns % since last call;
            # first invocation per process always reads 0.0 (psutil
            # contract), which is fine — subsequent calls give signal.
            snapshot["cpu_percent"] = _PROCESS.cpu_percent(interval=None)
        except Exception as exc:  # noqa: BLE001 — diagnostic must not raise
            logger.warning("psutil snapshot failed: %s", exc)

    return snapshot


def maybe_emit_breadcrumb() -> bool:
    """Throttled Sentry breadcrumb + INFO log of the runtime snapshot.

    Designed to be called from the ``/health`` endpoint on every probe.
    Emits at most once per ``RUNTIME_BREADCRUMB_INTERVAL_SECONDS``
    (default 300s) per process.  Returns True iff a breadcrumb was
    emitted on this call (used by tests).

    Defensive: any failure during emission is swallowed.  Health
    endpoint correctness is more important than breadcrumb correctness.
    """
    global _last_breadcrumb_mono
    now = time.monotonic()
    if now - _last_breadcrumb_mono < _BREADCRUMB_INTERVAL_SECONDS:
        return False
    _last_breadcrumb_mono = now

    try:
        snapshot = get_runtime_snapshot()
        # INFO log preserves a trail in Fly logs even when Sentry is
        # disabled (e.g., dev) — independently of breadcrumb capture.
        logger.info(
            "runtime_snapshot rss_mb=%s vms_mb=%s uptime_s=%s ws=%s rl_buckets=%s",
            snapshot["memory_rss_mb"],
            snapshot["memory_vms_mb"],
            int(snapshot["process_uptime_seconds"]),
            snapshot["active_ws_channels"],
            snapshot["rate_limit_buckets"],
        )
        try:
            import sentry_sdk

            sentry_sdk.add_breadcrumb(
                category="runtime",
                message="memory snapshot",
                data=snapshot,
                level="info",
            )
        except ImportError:
            pass
    except Exception as exc:  # noqa: BLE001 — must not break /health
        logger.warning("breadcrumb emission failed: %s", exc)

    return True


def _reset_throttle_for_tests() -> None:
    """Test-only helper to reset the breadcrumb throttle.

    Lets a test trigger a fresh emission without sleeping for 5 minutes.
    NOT exported in ``__all__``; tests reach in via the leading underscore.
    """
    global _last_breadcrumb_mono
    _last_breadcrumb_mono = 0.0
