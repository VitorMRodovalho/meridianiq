# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Security-headers regression test.

The five security headers shipped by ``add_security_headers`` in
``src/api/app.py`` are a load-bearing operational contract (X-Frame-Options,
X-Content-Type-Options, Referrer-Policy, Permissions-Policy, and
Strict-Transport-Security under https).  They are emitted by FastAPI's
``@app.middleware("http")`` decorator — an API that upstream Starlette
1.0.0 removed but FastAPI 0.136.x re-exposes via a compatibility shim
(verified empirically during Cycle 6 W1 entry-council, 2026-05-17).

If a future FastAPI release drops the shim, or if a router-ordering
refactor short-circuits before the middleware runs, the headers vanish
silently.  This test makes that regression loud — file a P0 issue when
it fails, never just delete the assertions.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import app


def test_health_endpoint_ships_all_security_headers() -> None:
    """All five security headers must ship on every response."""
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert (
        response.headers.get("Permissions-Policy")
        == "geolocation=(), microphone=(), camera=()"
    )


def test_security_headers_present_on_404_responses() -> None:
    """Security headers must ship on non-2xx responses too — auditors care."""
    response = TestClient(app).get("/this-route-does-not-exist")

    assert response.status_code == 404
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
