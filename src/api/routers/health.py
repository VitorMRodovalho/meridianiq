# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Health check router."""

from __future__ import annotations

import logging
import threading
import time
from typing import Literal

from fastapi import APIRouter, Request, Response

from ..deps import RATE_LIMIT_READ, get_store, limiter
from ..observability import maybe_emit_breadcrumb
from ..schemas import DatabaseHealthResponse, HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)

#: One database probe per this many seconds, whoever asks. The endpoint is
#: public, so a flood of requests reads the cached answer instead of the database.
DB_PROBE_TTL_S = 60.0

DatabaseState = Literal["ok", "unavailable", "in_memory"]

_db_probe_lock = threading.Lock()
_db_state: DatabaseState | None = None  # None until the first probe completes
_db_checked_at = float("-inf")


@router.get("/health")
async def root_health() -> dict[str, str]:
    # Throttled at 5 min by default — see ``observability.maybe_emit_breadcrumb``.
    # Captures the runtime snapshot into Sentry breadcrumbs + INFO log so the
    # leak curve is observable without a separate background task pattern.
    maybe_emit_breadcrumb()
    return {"status": "ok", "version": "1.0.0-dev"}


@router.get("/api/v1/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()


def _probe_database() -> DatabaseState:
    try:
        reachable = get_store().database_reachable()
    except Exception as exc:  # any failure to reach the database is the answer
        logger.warning("database health probe failed: %s", type(exc).__name__)
        return "unavailable"
    return "in_memory" if reachable is None else "ok"


@router.get(
    "/api/v1/health/db",
    response_model=DatabaseHealthResponse,
    responses={503: {"model": DatabaseHealthResponse}},
)
@limiter.limit(RATE_LIMIT_READ)
def database_health(request: Request, response: Response) -> DatabaseHealthResponse:
    """Whether the API can reach its database.

    ``/health`` answers without touching the database, so it stayed green on
    2026-10-09 while the Supabase project was paused and its hostnames did not
    resolve. This endpoint is what ``.github/workflows/uptime.yml`` polls. It
    answers 503 when the database is unreachable and never says why: the
    exception class goes to the log only.
    """
    global _db_state, _db_checked_at
    stale = time.monotonic() - _db_checked_at >= DB_PROBE_TTL_S
    # One probe at a time. While it runs, other requests get the last answer,
    # so a hanging database does not hold every worker; only before the first
    # answer exists do they wait for it.
    if stale and _db_probe_lock.acquire(blocking=_db_state is None):
        try:
            if time.monotonic() - _db_checked_at >= DB_PROBE_TTL_S:
                _db_state = _probe_database()
                _db_checked_at = time.monotonic()
        finally:
            _db_probe_lock.release()
    state: DatabaseState = _db_state or "unavailable"
    if state == "unavailable":
        response.status_code = 503
    return DatabaseHealthResponse(database=state)


def reset_database_probe() -> None:
    """Forget the cached answer (tests)."""
    global _db_state, _db_checked_at
    with _db_probe_lock:
        _db_state = None
        _db_checked_at = float("-inf")
