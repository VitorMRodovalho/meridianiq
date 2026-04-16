# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""FastAPI application for MeridianIQ.

Application shell: creates the FastAPI instance, configures middleware
(CORS, security headers, rate limiting, Sentry), and includes all
domain routers.  Business logic lives in ``src/api/routers/``.
"""

from __future__ import annotations

import logging
import os

import sentry_sdk

if dsn := os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0.1,
        environment=os.environ.get("ENVIRONMENT", "development"),
        release="meridianiq-api@3.7.0-dev",
    )

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="MeridianIQ",
    description="The intelligence standard for project schedules",
    version="3.7.0-dev",
)

# Rate limiting
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["60/minute"],
        enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false",
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:

    class _NoOpLimiter:
        def limit(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            def decorator(func):  # type: ignore[no-untyped-def]
                return func

            return decorator

    limiter = _NoOpLimiter()  # type: ignore[assignment]

# CORS — whitelist known origins (not wildcard)
_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:4321",
    "https://meridianiq.vitormr.dev",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
    max_age=3600,
)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Add standard security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ------------------------------------------------------------------ #
# Router registration                                                #
# ------------------------------------------------------------------ #

from .organizations import router as org_router  # noqa: E402
from .routers.health import router as health_router  # noqa: E402
from .routers.upload import router as upload_router  # noqa: E402
from .routers.projects import router as projects_router  # noqa: E402
from .routers.programs import router as programs_router  # noqa: E402
from .routers.comparison import router as comparison_router  # noqa: E402
from .routers.forensics import router as forensics_router  # noqa: E402
from .routers.tia import router as tia_router  # noqa: E402
from .routers.evm import router as evm_router  # noqa: E402
from .routers.risk import router as risk_router  # noqa: E402
from .routers.analysis import router as analysis_router  # noqa: E402
from .routers.intelligence import router as intelligence_router  # noqa: E402
from .routers.whatif import router as whatif_router  # noqa: E402
from .routers.schedule_ops import router as schedule_ops_router  # noqa: E402
from .routers.cost import router as cost_router  # noqa: E402
from .routers.exports import router as exports_router  # noqa: E402
from .routers.benchmarks import router as benchmarks_router  # noqa: E402
from .routers.reports import router as reports_router  # noqa: E402
from .routers.admin import router as admin_router  # noqa: E402

app.include_router(org_router)
app.include_router(health_router)
app.include_router(upload_router)
app.include_router(projects_router)
app.include_router(programs_router)
app.include_router(comparison_router)
app.include_router(forensics_router)
app.include_router(tia_router)
app.include_router(evm_router)
app.include_router(risk_router)
app.include_router(analysis_router)
app.include_router(intelligence_router)
app.include_router(whatif_router)
app.include_router(schedule_ops_router)
app.include_router(cost_router)
app.include_router(exports_router)
app.include_router(benchmarks_router)
app.include_router(reports_router)
app.include_router(admin_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler — generic message in production."""
    is_dev = os.getenv("ENVIRONMENT", "development") == "development"
    detail = str(exc) if is_dev else "Internal server error"
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": detail})


# ------------------------------------------------------------------ #
# Backward-compat aliases for tests                                  #
# ------------------------------------------------------------------ #
# Store singletons live in deps.py.  These aliases allow tests that
# do ``from src.api.app import _store`` to still work.  For monkeypatch
# targets, use ``src.api.deps._store``.

import src.api.deps as _deps  # noqa: E402

_store = _deps._store
_timeline_store = _deps._timeline_store
_tia_store = _deps._tia_store
_evm_store = _deps._evm_store
_risk_store = _deps._risk_store
_report_store = _deps._report_store


def get_store():  # type: ignore[no-redef]
    """Return the global project store (delegates to deps._store)."""
    return _deps._store
