# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Rate-limit RUNTIME regression — slowapi actually fires 429 at burst.

Closes the structural-vs-runtime gap PR #60's devils-advocate exit-council
flagged as N3. ``tests/test_rate_limit_policy.py`` validates the AST shape
of the contract (Rules 1–4: write coverage, expensive coverage, exception
discipline, ``Request`` parameter presence). It cannot prove that slowapi's
runtime path actually issues 429 at the configured burst threshold —
e.g., a misconfigured ``key_func``, a swallowed exception in the limiter
backend, or a future async-conversion regression would all pass the AST
test while silently no-op'ing in production.

This file pins one runtime burst per Convention A endpoint family that
PR #60 either fixed or precedented. Together with the long-standing
``test_whatif_router.py::TestOptimizeRateLimit`` (which covers
``optimize_schedule_endpoint``, the original Convention A pattern), this
is the runtime correlate of Rule 4.

Why ``build_schedule_endpoint``?

  - It was rewritten by PR #60 as part of the body-collision sweep
    (``request: dict`` → ``body: dict`` + ``request: Request`` first-param).
  - It is ``async`` — exercises the async + slowapi interaction that
    bit ``optimize_schedule_endpoint`` historically.
  - Its decorator uses the constant ``RATE_LIMIT_EXPENSIVE`` (= ``3/minute``)
    so the burst threshold is small (4th call returns 429), keeping the
    test fast.
  - Its body is a free-form ``dict`` with one required ``description``
    field — no upload fixture or DB state needed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture()
def client() -> TestClient:
    """Plain TestClient — no store mutation needed for this test."""
    return TestClient(app)


class TestSlowapiRuntime:
    """Burst-fire each endpoint family until 429.

    Each test follows the pattern:

      1. Skip if ``slowapi`` is not installed (CI runners may use the
         ``deps._NoOpLimiter`` fallback — there is nothing to assert).
      2. Flip ``api_limiter.enabled`` back to ``True`` (``conftest.py``
         disables it suite-wide so other tests don't fight the limiter).
      3. Reset the in-memory backend so the budget for this run is fresh.
      4. Burst N calls; the (N+1)th MUST return 429.
    """

    def test_build_schedule_endpoint_4th_call_returns_429(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``POST /api/v1/schedule/build`` is decorated with
        ``@limiter.limit(RATE_LIMIT_EXPENSIVE)`` (= ``3/minute``).

        The 4th request from the same IP within the minute MUST return 429.
        Pre-PR-#60 the endpoint had ``request: dict`` and no ``Request``
        parameter — slowapi was silently no-op'ing or raising. This test
        is the runtime correlate of Rule 4 for that endpoint.
        """
        from src.api.deps import limiter as api_limiter

        if not hasattr(api_limiter, "enabled"):
            pytest.skip("slowapi _NoOpLimiter fallback — rate-limit not active")

        monkeypatch.setattr(api_limiter, "enabled", True)
        if hasattr(api_limiter, "reset"):
            api_limiter.reset()

        body = {"description": "build a small commercial schedule"}
        statuses: list[int] = []
        for _ in range(4):
            resp = client.post("/api/v1/schedule/build", json=body)
            statuses.append(resp.status_code)

        # First three within budget — must NOT be 429.
        assert statuses[0] != 429, f"1st call should not be rate-limited (got {statuses[0]})"
        assert statuses[1] != 429, f"2nd call should not be rate-limited (got {statuses[1]})"
        assert statuses[2] != 429, f"3rd call should not be rate-limited (got {statuses[2]})"
        # The 4th is the 429 boundary.
        assert statuses[3] == 429, (
            f"expected 429 on 4th call within the minute, got {statuses[3]}. "
            f"Full status sequence: {statuses}. Either RATE_LIMIT_EXPENSIVE drifted "
            "from the 3/min budget, or slowapi can no longer extract the IP from "
            "the request: Request parameter (PR #60 regression)."
        )
