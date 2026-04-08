# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Health check router."""

from __future__ import annotations

from fastapi import APIRouter

from ..schemas import HealthResponse

router = APIRouter()


@router.get("/health")
async def root_health():
    return {"status": "ok", "version": "1.0.0-dev"}


@router.get("/api/v1/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()
