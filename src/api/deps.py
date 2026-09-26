# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Shared FastAPI dependencies for all routers.

Provides store accessors, rate limiter, and common helpers.
All store singletons live here so both ``app.py`` and routers share
the same instances.  Tests monkeypatch ``src.api.deps._store`` etc.
"""

from __future__ import annotations

import ipaddress
import logging
import os
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

from starlette.requests import Request

from src.database.store import get_store as _get_db_store

from .storage import EVMStore, ReportStore, RiskStore, TIAStore, TimelineStore

if TYPE_CHECKING:
    from src.parser.models import ParsedSchedule

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


def granted_schedule(store: Any, project_id: str) -> ParsedSchedule:
    """Load the schedule of a project the access context has already granted.

    A ``None`` from the store is then not an access decision: the caller may
    reach the project, so it was deleted after the check or its schedule could
    not be rebuilt (the Supabase store returns ``None`` on a storage or parse
    failure). The answer stays a 404, and the id is logged, so a "Project not
    found" report can be traced to the project that failed to load.
    """
    schedule: ParsedSchedule | None = store.get(project_id)
    if schedule is None:
        logger.warning("granted project %s has no loadable schedule", project_id)
        raise HTTPException(status_code=404, detail="Project not found")
    return schedule


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


# Shared rate-limit buckets — use these instead of hard-coding per-router
# strings so audit (AUDIT-003) stays reviewable in one place.  Tune values
# here and the whole API moves together.
#
#   EXPENSIVE — Monte Carlo, PDF generation, XER round-trip export, /optimize,
#               /pareto, /resource-leveling, /schedule/build, /plugins/.
#   WRITE     — Mutation/write endpoints (admin actions, cost upload, ask,
#               schedule control, override). Between EXPENSIVE and MODERATE
#               so accidental misuse on heavy work surfaces via 429 quickly.
#   MODERATE  — Forensic window analysis, file upload, EVM/TIA submit,
#               explicit reads with large serialisation (Excel, AIA G703).
#   ANALYSIS  — Analytical reads (lifecycle inference preview, comparison
#               summaries, override mutations).
#   READ      — Cached reads, aggregated rollups, search, pending-statuses.
#   LIGHT     — Very light reads (lifecycle status / list); matches
#               ``Limiter.default_limits`` so per-route bucket scope is
#               preserved without inventing a stricter rate.
RATE_LIMIT_EXPENSIVE = "3/minute"
RATE_LIMIT_WRITE = "5/minute"
RATE_LIMIT_MODERATE = "10/minute"
RATE_LIMIT_ANALYSIS = "20/minute"
RATE_LIMIT_READ = "30/minute"
RATE_LIMIT_LIGHT = "60/minute"


#: Environment variable naming the header that a proxy in front of the app sets
#: to the client address (``fly-client-ip`` on Fly.io, see fly.toml). When it is
#: unset no forwarding header is trusted.
TRUSTED_CLIENT_IP_HEADER_ENV = "TRUSTED_CLIENT_IP_HEADER"


def trusted_client_ip(request: Request | None) -> str | None:
    """The client address a request is attributed to (rate limits, audit trail).

    A forwarding header is read only when the deployment names it in
    ``TRUSTED_CLIENT_IP_HEADER``, because only a proxy in front of the app
    makes such a header trustworthy; without one the client writes it.

    - ``fly-client-ip`` (Fly.io, set in fly.toml): Fly's edge sets it to the
      address it accepted the connection from.
    - ``x-forwarded-for``: the RIGHTMOST hop, the one the proxy directly in
      front of the app appended; everything to its left came from the client.
    - any other header name: its value.

    If the header occurs more than once, the LAST occurrence is used: a proxy
    that appends rather than replaces leaves a client-sent copy before its own.
    With no configured header, or an empty one, the socket peer
    (``request.client.host``) is used. That is right for direct connections
    (``docker compose``) and wrong behind a proxy, where every connection comes
    from the proxy: on Fly, uvicorn sees Fly-internal addresses, so keying on
    the peer would put all clients in one bucket.

    Returns ``None`` when there is no request or no client (synthesised test
    requests).
    """
    if request is None:
        return None
    header = os.environ.get(TRUSTED_CLIENT_IP_HEADER_ENV, "").strip().lower()
    if header:
        values = request.headers.getlist(header)
        if values:
            last = values[-1]
            if header == "x-forwarded-for":
                hops = [hop.strip() for hop in last.split(",") if hop.strip()]
                if hops:
                    return hops[-1]
            elif last.strip():
                return last.strip()
    return request.client.host if request.client else None


def _rate_limit_bucket(address: str) -> str:
    """Group addresses one client controls together.

    An IPv6 client usually holds a whole /64 and can send each request from a
    new address in it, so IPv6 is keyed on its /64. IPv4-mapped IPv6 is keyed
    as the IPv4 address. Anything unparsable is used as given.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


def rate_limit_key(request: Request) -> str:
    """slowapi key: one bucket per client (see :func:`trusted_client_ip`).

    Counters live in each process's memory, so on N machines a client can
    reach up to N times a limit before a 429.
    """
    return _rate_limit_bucket(trusted_client_ip(request) or "127.0.0.1")


# Rate limiter (shared instance)
try:
    from slowapi import Limiter

    limiter = Limiter(
        key_func=rate_limit_key,
        default_limits=[RATE_LIMIT_LIGHT],
        enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false",
    )
except ImportError:

    class _NoOpLimiter:
        def limit(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            def decorator(func):  # type: ignore[no-untyped-def]
                return func

            return decorator

    limiter = _NoOpLimiter()  # type: ignore[assignment]
