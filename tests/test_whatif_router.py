# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Router-level tests for POST /api/v1/projects/{project_id}/optimize.

Covers the W5/W6 progress_callback wire-in PLUS the issue #14 contract:
  - response is `OptimizeResponse` Pydantic — UI-aligned field names
    (regression guard for the v4.0.0 broken contract that #14 closes)
  - convergence is enumerated from engine `convergence_history`
  - shifted_activities is populated from `best_leveling.activity_shifts`
  - progress events + final done event reach the WS when a job_id is
    supplied (end-to-end, mirrors test_progress_ws.py pattern)
  - foreign job_id (bound to a different user) is rejected with 403
  - exceptions raised by the engine are published as an error event on
    the channel before the HTTP 500 bubbles up
  - the @limiter.limit("5/minute") decorator (held as literal per ADR-0019
    Amendment 1 §"Empirical state" — /optimize is an EXPENSIVE_PATTERNS
    match held at WRITE rate, not EXPENSIVE rate) survives the async
    conversion (6th call within the minute returns 429)
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.api import progress
from src.api.app import app
from src.api.storage import ProjectStore
from src.parser.models import (
    Calendar,
    ParsedSchedule,
    Project,
    Resource,
    Task,
    TaskResource,
)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Fresh channel map per test; store reset is handled in the
    `client` fixture so we can swap stores around request lifecycles."""
    progress._channels.clear()


@pytest.fixture()
def client():
    """TestClient with a fresh ProjectStore bound to deps._store."""
    import src.api.deps as deps_module

    test_store = ProjectStore()
    original_store = deps_module._store
    deps_module._store = test_store
    try:
        yield TestClient(app)
    finally:
        deps_module._store = original_store


def _tiny_optimizable_schedule() -> ParsedSchedule:
    """4-activity schedule with a shared resource, matching the pattern
    used in tests/test_evolution_optimizer.py. Enough structure for the
    optimizer to run but small enough to finish fast."""
    return ParsedSchedule(
        projects=[
            Project(
                proj_id="P1",
                proj_short_name="OptimizeRouterTest",
                last_recalc_date=datetime(2025, 3, 1),
                plan_start_date=datetime(2025, 1, 1),
                sum_data_date=datetime(2025, 3, 1),
            )
        ],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        resources=[Resource(rsrc_id="R1", rsrc_name="Crew")],
        activities=[
            Task(
                task_id=str(i),
                task_code=chr(ord("A") + i - 1),
                task_name=f"Task {chr(ord('A') + i - 1)}",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=16.0,
                target_drtn_hr_cnt=16.0,
                clndr_id="CAL1",
            )
            for i in range(1, 5)
        ],
    )


@pytest.fixture()
def uploaded_project_id(client: TestClient) -> str:
    """Seed deps._store with a schedule the optimize endpoint can find."""
    import src.api.deps as deps_module

    pid = deps_module._store.add(_tiny_optimizable_schedule(), b"raw")
    return pid


def _fast_config(resource_limits: list[dict] | None = None) -> dict:
    """Small optimization config so tests finish in <1s."""
    return {
        "population_size": 2,
        "parent_size": 1,
        "generations": 2,
        "resource_limits": resource_limits or [{"rsrc_id": "R1", "max_units": 1.0}],
    }


# ---------------------------------------------------------------------------
# Issue #14 regression — OptimizeResponse Pydantic contract
# ---------------------------------------------------------------------------


class TestOptimizeResponseContract:
    """Issue #14: the response must match `OptimizeResponse` (UI-aligned
    field names), not the v4.0.0 raw dataclass dict. This was the breakage
    that left /optimizer rendering `undefined` for every result panel from
    v4.0.0 ship to v4.0.1 release. Hard regression guard going forward."""

    def test_response_carries_ui_aligned_field_names(
        self, client: TestClient, uploaded_project_id: str
    ) -> None:
        """Field names match what `web/src/routes/optimizer/+page.svelte`
        consumes. Renames vs engine: original_makespan ← greedy_duration_days,
        optimized_makespan ← best_duration_days, generations ← generations_run."""
        resp = client.post(
            f"/api/v1/projects/{uploaded_project_id}/optimize",
            json=_fast_config(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # UI-aligned names present
        for key in (
            "original_makespan",
            "optimized_makespan",
            "improvement_days",
            "improvement_pct",
            "generations",
            "best_priority_rule",
            "convergence",
            "shifted_activities",
            "methodology",
            "summary",
        ):
            assert key in data, f"missing UI-contract key: {key}"

        # Raw engine names are NOT exposed (they belong to the dataclass)
        for legacy_key in (
            "greedy_duration_days",
            "best_duration_days",
            "convergence_history",
            "generations_run",
            "best_leveling",
        ):
            assert legacy_key not in data, (
                f"raw engine field {legacy_key!r} leaked into public response"
            )

    def test_convergence_is_enumerated_from_history(
        self, client: TestClient, uploaded_project_id: str
    ) -> None:
        """convergence is `list[{generation, best_fitness}]` derived from
        `enumerate(convergence_history)`. Mean fitness is intentionally
        absent (not produced by the engine — see issue #14 curated 2026-04-26)."""
        resp = client.post(
            f"/api/v1/projects/{uploaded_project_id}/optimize",
            json=_fast_config(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        convergence = data["convergence"]
        assert isinstance(convergence, list)
        assert len(convergence) >= 1
        first = convergence[0]
        assert set(first.keys()) == {"generation", "best_fitness"}
        assert first["generation"] == 1  # 1-indexed for UI display
        # mean_fitness must NOT be present — engine never emits it
        assert "mean_fitness" not in first

    def test_shifted_activities_populated_from_best_leveling(self, client: TestClient) -> None:
        """shifted_activities is extracted from
        `OptimizationResult.best_leveling.activity_shifts`. Each entry
        carries `task_id`, `task_code`, `task_name`, `shift_days` plus
        the rest of `ActivityShiftSchema`.

        Uses a local fixture with `task_resources` populated so the
        leveling step actually detects resource demand and produces
        shifts (the shared `_tiny_optimizable_schedule()` has bare
        Tasks + Resources with no TASKRSRC link)."""
        import src.api.deps as deps_module

        schedule = ParsedSchedule(
            projects=[
                Project(
                    proj_id="P1",
                    proj_short_name="OptimizeContractTest",
                    last_recalc_date=datetime(2025, 3, 1),
                    plan_start_date=datetime(2025, 1, 1),
                    sum_data_date=datetime(2025, 3, 1),
                )
            ],
            calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
            resources=[Resource(rsrc_id="R1", rsrc_name="Crew")],
            activities=[
                Task(
                    task_id=str(i),
                    task_code=chr(ord("A") + i - 1),
                    task_name=f"Task {chr(ord('A') + i - 1)}",
                    status_code="TK_NotStart",
                    remain_drtn_hr_cnt=16.0,
                    target_drtn_hr_cnt=16.0,
                    clndr_id="CAL1",
                )
                for i in range(1, 5)
            ],
            task_resources=[
                TaskResource(
                    taskrsrc_id=f"TR{i}",
                    task_id=str(i),
                    rsrc_id="R1",
                    proj_id="P1",
                    target_qty=16.0,
                    remain_qty=16.0,
                )
                for i in range(1, 5)
            ],
        )
        pid = deps_module._store.add(schedule, b"raw")

        resp = client.post(
            f"/api/v1/projects/{pid}/optimize",
            json=_fast_config(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        shifts = data["shifted_activities"]
        assert isinstance(shifts, list)
        assert len(shifts) >= 1, "expected ≥1 shift on the 4-task / 1-resource fixture"
        first = shifts[0]
        # Field names match `ActivityShiftSchema`, NOT the legacy
        # `{activity_id, activity_name, shift_days}` shape that v4.0.0
        # frontend incorrectly assumed.
        for key in ("task_id", "task_code", "task_name", "shift_days", "duration_days"):
            assert key in first, f"missing ActivityShiftSchema key: {key}"


# ---------------------------------------------------------------------------
# End-to-end WS progress
# ---------------------------------------------------------------------------


class TestOptimizeWithJobIdStreamsProgress:
    def test_ws_receives_done_with_improvement_fields(
        self, client: TestClient, uploaded_project_id: str
    ) -> None:
        """Open WS, fire optimize with ?job_id=<uuid>, drain WS until
        terminal. Assert the `done` event carries improvement_pct +
        improvement_days (the honest terminal contract for optimize —
        distinct from risk's simulation_id).

        Channel is created by the WS handler itself via `open_channel`
        (mirrors tests/test_progress_ws.py::test_websocket_streams_done_event
        pattern) — no explicit pre-open is needed because the WS
        handshake completes synchronously within websocket_connect's
        context manager entry.

        Coverage split (intentional, post-2026-04-26 hardening):
          - Engine `progress_callback` emission rate is covered by
            `test_evolution_optimizer.py::TestProgressCallback`.
          - Wire transit (publish → channel → WS frame) is covered by
            `tests/test_progress_ws.py`.
          - This test only locks the router-level terminal contract
            (`done` event + improvement fields), which is deterministic.
          - The earlier "at least one progress event arrives via WS"
            assertion was racy on CI: TestClient runs sync, and a small
            optimization can complete before the asyncio WS consumer
            yields, so progress frames published into the queue can be
            in-flight at receive time. Dropped per ruling the contract
            (terminal event) is what matters at the router boundary.
        """
        job_id = str(uuid.uuid4())

        # Modest config — only needs to make the engine produce non-zero
        # convergence_history so improvement fields are well-defined.
        config = {
            "population_size": 5,
            "parent_size": 2,
            "generations": 10,
            "resource_limits": [{"rsrc_id": "R1", "max_units": 1.0}],
        }

        with client.websocket_connect(f"/api/v1/ws/progress/{job_id}") as ws:
            resp = client.post(
                f"/api/v1/projects/{uploaded_project_id}/optimize?job_id={job_id}",
                json=config,
            )
            assert resp.status_code == 200, resp.text

            events: list[dict] = []
            for _ in range(500):
                events.append(ws.receive_json())
                if events[-1].get("type") in ("done", "error"):
                    break

        types = [e.get("type") for e in events]
        assert "done" in types, f"no done event in {types}"

        done = next(e for e in events if e["type"] == "done")
        assert "improvement_pct" in done
        assert "improvement_days" in done


# ---------------------------------------------------------------------------
# Ownership check (ADR-0013)
# ---------------------------------------------------------------------------


class TestOptimizeRejectsForeignJobId:
    def test_returns_403_when_channel_bound_to_other_user(
        self,
        client: TestClient,
        uploaded_project_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If the progress channel was bound to user A and user B calls
        optimize with that job_id, the router must reject with 403 before
        running the optimizer."""
        from src.api import auth as auth_module

        job_id = str(uuid.uuid4())
        progress.open_channel(job_id, owner_user_id="user-A")

        # Inject a fake caller (user-B) via optional_auth override.
        def _fake_optional_auth() -> dict:
            return {"id": "user-B", "email": "b@example.com"}

        app.dependency_overrides[auth_module.optional_auth] = _fake_optional_auth
        try:
            resp = client.post(
                f"/api/v1/projects/{uploaded_project_id}/optimize?job_id={job_id}",
                json=_fast_config(),
            )
        finally:
            app.dependency_overrides.pop(auth_module.optional_auth, None)

        assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# Error path publishes to channel
# ---------------------------------------------------------------------------


class TestOptimizePublishesErrorOnException:
    def test_engine_exception_publishes_error_event_and_returns_500(
        self,
        client: TestClient,
        uploaded_project_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If the engine raises, the router must push a
        {"type":"error","message":...} frame into the channel before
        letting the 500 bubble up — so the WS subscriber isn't left
        hanging indefinitely."""
        from src.api.routers import whatif as whatif_module

        job_id = str(uuid.uuid4())
        progress.open_channel(job_id, owner_user_id=None)

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("simulated engine failure")

        monkeypatch.setattr(
            "src.analytics.evolution_optimizer.optimize_schedule",
            _boom,
        )

        # Double-check the router looks up the engine via its module import
        # path, not a cached reference. The endpoint does
        # `from src.analytics.evolution_optimizer import optimize_schedule`
        # inside the handler on each call, so the monkeypatch above hits it.
        _ = whatif_module  # noqa: F841 — ensures patch import order

        with client.websocket_connect(f"/api/v1/ws/progress/{job_id}") as ws:
            resp = client.post(
                f"/api/v1/projects/{uploaded_project_id}/optimize?job_id={job_id}",
                json=_fast_config(),
            )
            assert resp.status_code == 500, resp.text

            event = ws.receive_json()
            assert event["type"] == "error"
            assert "simulated engine failure" in event["message"]


# ---------------------------------------------------------------------------
# Rate-limit survives async conversion
# ---------------------------------------------------------------------------


class TestOptimizeRateLimit:
    def test_sixth_call_within_minute_returns_429(
        self,
        client: TestClient,
        uploaded_project_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """@limiter.limit("5/minute") is applied to the async handler.
        The 6th request within the window must be throttled — regression
        guard for the sync→async conversion interacting with slowapi.

        The literal (not RATE_LIMIT_WRITE constant) is intentional: see
        the inline comment above the decorator at
        ``src/api/routers/whatif.py:353-354`` and ADR-0019 Amendment 1
        §"Empirical state" line 389.  /optimize is an EXPENSIVE_PATTERNS
        match held at the WRITE bucket rate as a documented exception.

        conftest.py disables rate-limiting globally for the suite
        (RATE_LIMIT_ENABLED=false) so tests don't fight the limiter
        by accident. This test flips it back on for one run, then
        lets the autouse monkeypatch.undo restore it afterwards.
        Slowapi stores `enabled` as a mutable attribute that is read
        at request time, so the flip is live without re-importing
        the app.
        """
        from src.api.deps import limiter as api_limiter

        if not hasattr(api_limiter, "enabled"):
            # Environment has slowapi uninstalled — `deps._NoOpLimiter`
            # is active and `@limiter.limit` is a pass-through. There
            # is nothing to assert 429 against. (Also the state most
            # CI runners hit since slowapi is not a hard runtime dep.)
            pytest.skip("slowapi _NoOpLimiter fallback — rate-limit not active")

        monkeypatch.setattr(api_limiter, "enabled", True)
        # The limiter shares its in-memory backend across tests —
        # previous successful calls in the session may have consumed
        # the 5/min budget already. Reset the backend for this run.
        if hasattr(api_limiter, "reset"):
            api_limiter.reset()

        last_status: int | None = None
        for _ in range(6):
            resp = client.post(
                f"/api/v1/projects/{uploaded_project_id}/optimize",
                json=_fast_config(),
            )
            last_status = resp.status_code

        assert last_status == 429, (
            f"expected 429 on 6th call, got {last_status} "
            "(async + @limiter.limit interaction regressed)"
        )
