# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Health check router."""

from __future__ import annotations

from fastapi import APIRouter

from ..observability import maybe_emit_breadcrumb
from ..schemas import HealthResponse

router = APIRouter()


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
