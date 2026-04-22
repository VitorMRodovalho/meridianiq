# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Shared FastAPI dependencies for all routers.

Provides store accessors, rate limiter, and common helpers.
All store singletons live here so both ``app.py`` and routers share
the same instances.  Tests monkeypatch ``src.api.deps._store`` etc.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from src.database.store import get_store as _get_db_store
from src.parser.models import ParsedSchedule

from .storage import EVMStore, ReportStore, RiskStore, TIAStore, TimelineStore

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Global store singletons — canonical location                       #
# ------------------------------------------------------------------ #

_store = _get_db_store()
_timeline_store = TimelineStore()
_tia_store = TIAStore()
_evm_store = EVMStore()
_risk_store = RiskStore()
_report_store = ReportStore()

# Sandbox project tracking (in-memory for dev)
_sandbox_projects: set[str] = set()


def get_store() -> Any:
    """Return the global data store (InMemory or Supabase)."""
    return _store


# ------------------------------------------------------------------ #
# Async materializer singleton (ADR-0015)                             #
# ------------------------------------------------------------------ #
#
# One ``Materializer`` shared across every HTTP worker in the process so
# the ``asyncio.Semaphore(1)`` actually serialises uploads. Per-request
# instantiation would give each upload its own Semaphore and defeat the
# serialisation commitment ADR-0015 §1 makes for Fly.io's 1-CPU deploy.

_materializer: Any | None = None


def get_materializer() -> Any:
    """Return the process-wide materializer bound to the current global store.

    If a test harness or reload swaps ``deps._store``, the materializer is
    rebuilt so it does not keep a stale reference to the previous backend.
    The ``asyncio.Semaphore`` is therefore per-binding — a fresh test
    fixture gets a fresh semaphore, which matches the test isolation the
    fixtures already rely on.
    """
    global _materializer
    if _materializer is None or _materializer._store is not _store:
        from src.materializer import Materializer

        _materializer = Materializer(_store)
    return _materializer


def get_timeline_store() -> TimelineStore:
    """Return the global forensic timeline store."""
    return _timeline_store


def get_tia_store() -> TIAStore:
    """Return the global TIA store."""
    return _tia_store


def get_evm_store() -> EVMStore:
    """Return the global EVM store."""
    return _evm_store


def get_risk_store() -> RiskStore:
    """Return the global Risk store."""
    return _risk_store


def get_report_store() -> ReportStore:
    """Return the report store."""
    return _report_store


def get_schedule_or_404(project_id: str, user_id: str | None = None) -> ParsedSchedule:
    """Fetch a parsed schedule, raising 404 if not found."""
    from fastapi import HTTPException

    store = get_store()
    schedule = store.get(project_id, user_id=user_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return schedule


# Rate limiter (shared instance)
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["60/minute"],
        enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false",
    )
except ImportError:

    class _NoOpLimiter:
        def limit(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            def decorator(func):  # type: ignore[no-untyped-def]
                return func

            return decorator

    limiter = _NoOpLimiter()  # type: ignore[assignment]


# Shared rate-limit buckets — use these instead of hard-coding per-router
# strings so audit (AUDIT-003) stays reviewable in one place.  Tune values
# here and the whole API moves together.
#
#   EXPENSIVE — Monte Carlo, PDF generation, XER round-trip export.
#   MODERATE  — Forensic window analysis, comparison, explicit reads with
#               large serialisation (Excel, AIA G703).
#   READ      — Cached reads, aggregated rollups, search.
RATE_LIMIT_EXPENSIVE = "3/minute"
RATE_LIMIT_MODERATE = "10/minute"
RATE_LIMIT_READ = "30/minute"
