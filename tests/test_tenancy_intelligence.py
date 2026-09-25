# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Single-project analysis reads are owner-only (ADR-0030).

Covers every project-scoped route in the what-if, intelligence and
schedule-metric (float entropy, constraint accumulation, narrative)
routers. The tests run with ``ENVIRONMENT=production`` and real HS256
JWTs, never ``dependency_overrides``, so the whole auth -> principal ->
access path is exercised.

For each route:

* the owner reaches their project (positive control: fails, never skips);
* another tenant gets a 404 identical to a random id, and the foreign
  schedule is never read;
* for a route that takes a second project id, the other tenant's own
  project with a foreign or random second id is a 404, and neither
  schedule is read before the refusal.

None of these routes uses the per-project analysis cache; a spy on the
store's cache methods asserts that, so a route that starts caching fails
here until it gets cache-isolation tests of its own.
"""

from __future__ import annotations

import copy
import functools
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import src.api.deps as deps
from src.analytics.nlp_query import NLPQueryResult
from src.api import access, auth
from src.api.app import app
from src.api.routers import cost, intelligence, whatif
from src.database import config
from src.database.store import InMemoryStore
from src.parser.models import ParsedSchedule
from src.parser.xer_reader import XERReader

FIXTURES = Path(__file__).parent / "fixtures"
TEST_JWT_SECRET = "test-secret"  # tests/conftest.py sets SUPABASE_JWT_SECRET to this

USER_A = "00000000-0000-4000-8000-00000000a4b1"
USER_B = "00000000-0000-4000-8000-00000000b4b2"

NOT_FOUND = {"detail": "Project not found"}


# ------------------------------------------------------------------ #
# Route table                                                        #
# ------------------------------------------------------------------ #


@dataclass(frozen=True)
class Route:
    method: str
    path: str  # with ``{project_id}``, exactly as registered
    body: dict[str, Any] | None = None
    secondary: str | None = None  # query parameter naming a second project
    secondary_required: bool = False

    @property
    def key(self) -> tuple[str, str]:
        return (self.method, self.path)

    def __str__(self) -> str:
        return f"{self.method} {self.path}"


_P = "/api/v1/projects/{project_id}"

ROUTES: list[Route] = [
    # whatif.py
    Route(
        "POST",
        f"{_P}/what-if",
        body={"name": "s", "adjustments": [{"target": "*", "pct_change": 10.0}], "iterations": 1},
    ),
    Route(
        "POST",
        f"{_P}/pareto",
        body={
            "scenarios": [
                {
                    "name": "crash",
                    "adjustments": [{"target": "*", "pct_change": -10.0}],
                    "cost_delta": 1000.0,
                }
            ],
            "base_cost": 0.0,
        },
    ),
    Route("POST", f"{_P}/resource-leveling", body={"resource_limits": []}),
    Route("GET", f"{_P}/duration-prediction"),
    Route("GET", f"{_P}/scorecard"),
    Route(
        "POST",
        f"{_P}/optimize",
        body={"population_size": 2, "parent_size": 1, "generations": 2, "resource_limits": []},
    ),
    Route("GET", f"{_P}/visualization"),
    # intelligence.py
    Route("GET", f"{_P}/health", secondary="baseline_id"),
    Route("GET", f"{_P}/float-trends", secondary="baseline_id", secondary_required=True),
    Route("GET", f"{_P}/root-cause"),
    Route("POST", f"{_P}/ask", body={"question": "Which path drives completion?", "api_key": "k"}),
    Route("GET", f"{_P}/anomalies"),
    Route("GET", f"{_P}/delay-prediction", secondary="baseline_id"),
    Route("GET", f"{_P}/alerts", secondary="baseline_id", secondary_required=True),
    # cost.py (schedule metrics only)
    Route("GET", f"{_P}/float-entropy"),
    Route("GET", f"{_P}/constraint-accumulation", secondary="baseline_id", secondary_required=True),
    Route("GET", f"{_P}/narrative", secondary="baseline_id"),
]

WITH_SECONDARY = [r for r in ROUTES if r.secondary]

#: Routes of these routers that this module deliberately does not cover, and why.
EXEMPT: dict[tuple[str, str], str] = {
    ("GET", "/api/v1/dashboard"): "portfolio list route; migrates with the list routes",
    ("POST", "/api/v1/cost/upload"): "cost snapshots are a separate slice",
    ("GET", f"{_P}/cost/snapshots"): "cost snapshots are a separate slice",
    ("GET", f"{_P}/cost/compare"): "cost snapshots are a separate slice",
    ("POST", "/api/v1/trends"): "multi-project body route; a separate slice",
}

_ROUTER_MODULES = {m.__name__ for m in (whatif, intelligence, cost)}


# ------------------------------------------------------------------ #
# Harness                                                            #
# ------------------------------------------------------------------ #


def _token(sub: str) -> str:
    now = int(time.time())
    claims = {"sub": sub, "aud": "authenticated", "role": "authenticated", "iat": now}
    claims["exp"] = now + 3600
    return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256")


@functools.cache
def _parsed(name: str) -> ParsedSchedule:
    return XERReader(FIXTURES / name).parse()


@dataclass
class World:
    client: TestClient
    a: dict[str, str]  # auth headers of user A
    b: dict[str, str]  # auth headers of user B
    pa: str  # A's project (sample.xer)
    pa2: str  # A's second project (sample_update.xer)
    pb: str  # B's project (sample.xer)
    pb2: str  # B's second project (sample_update.xer)
    reads: list[str] = field(default_factory=list)  # project ids whose schedule was read
    cache_calls: list[str] = field(default_factory=list)  # analysis-cache methods called
    asked: list[str] = field(default_factory=list)  # questions that reached the NLP engine

    def call(
        self,
        route: Route,
        headers: dict[str, str],
        project_id: str,
        secondary: str | None = None,
    ) -> Any:
        url = route.path.format(project_id=project_id)
        params = {route.secondary: secondary} if route.secondary and secondary else None
        return self.client.request(
            route.method, url, params=params, json=route.body, headers=headers
        )


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> World:
    # Production auth: no anonymous development principal, invalid tokens are 401.
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    # Every module that reads ENVIRONMENT must be reading that same object.
    assert vars(access)["settings"] is config.settings
    assert vars(auth)["settings"] is config.settings
    assert config.settings.SUPABASE_JWT_SECRET == TEST_JWT_SECRET

    store = InMemoryStore()
    monkeypatch.setattr(deps, "_store", store)
    assert deps.get_store() is store

    def seed(name: str, owner: str) -> str:
        return str(store.add(copy.deepcopy(_parsed(name)), b"x", user_id=owner))

    w = World(
        client=TestClient(app),
        a={"Authorization": f"Bearer {_token(USER_A)}"},
        b={"Authorization": f"Bearer {_token(USER_B)}"},
        pa=seed("sample.xer", USER_A),
        pa2=seed("sample_update.xer", USER_A),
        pb=seed("sample.xer", USER_B),
        pb2=seed("sample_update.xer", USER_B),
    )

    # Spy on every way a route can load a schedule. The owner lookup
    # (``get_project_owner``) is the one read the access layer is allowed.
    def spy_reads(name: str) -> None:
        original: Callable[..., Any] = getattr(store, name)

        def wrapper(project_id: str, *args: Any, **kwargs: Any) -> Any:
            w.reads.append(project_id)
            return original(project_id, *args, **kwargs)

        monkeypatch.setattr(store, name, wrapper)

    for name in ("get_project", "get_parsed_schedule", "get_xer_bytes"):
        spy_reads(name)

    def spy_cache(name: str) -> None:
        original: Callable[..., Any] = getattr(store, name)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            w.cache_calls.append(name)
            return original(*args, **kwargs)

        monkeypatch.setattr(store, name, wrapper)

    for name in ("get_analysis", "save_analysis", "invalidate_analysis"):
        spy_cache(name)

    # /ask must not reach the Claude API from a test; the stub records who got through.
    async def fake_query(schedule: ParsedSchedule, question: str, **_: Any) -> NLPQueryResult:
        w.asked.append(question)
        return NLPQueryResult(question=question, answer="stub", model="stub", tokens_used=0)

    monkeypatch.setattr("src.analytics.nlp_query.query_schedule", fake_query)
    return w


def _ok(resp: Any, what: str) -> Any:
    """Positive control: the caller must succeed. Fails (never skips) otherwise."""
    assert 200 <= resp.status_code < 300, f"denied on {what}: {resp.status_code} {resp.text}"
    return resp.json()


def _answer(resp: Any) -> tuple[int, Any]:
    return resp.status_code, resp.json()


def _owner_call(w: World, route: Route, headers: dict[str, str], own: str, own2: str) -> Any:
    """The caller's own request: a second id, when the route needs one, is also theirs."""
    if route.secondary_required:
        return w.call(route, headers, own2, secondary=own)
    return w.call(route, headers, own)


# ------------------------------------------------------------------ #
# The table is the whole surface                                     #
# ------------------------------------------------------------------ #


def test_route_table_covers_every_route_of_these_routers() -> None:
    registered = {
        (method, r.path)
        for r in app.routes
        if isinstance(r, APIRoute) and r.endpoint.__module__ in _ROUTER_MODULES
        for method in r.methods
    }
    covered = {r.key for r in ROUTES}
    assert len(covered) == len(ROUTES), "duplicate route in the table"
    assert covered.isdisjoint(EXEMPT)
    assert registered == covered | set(EXEMPT), (
        f"untested: {sorted(registered - covered - set(EXEMPT))}; "
        f"stale: {sorted((covered | set(EXEMPT)) - registered)}"
    )


def test_instrument_is_armed_anonymous_is_rejected(world: World) -> None:
    """Negative control for the harness itself: production auth really is on."""
    resp = world.client.get(f"/api/v1/projects/{world.pa}/scorecard")
    assert resp.status_code == 401


# ------------------------------------------------------------------ #
# Every route                                                        #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize("route", ROUTES, ids=str)
def test_owner_reaches_own_project(world: World, route: Route) -> None:
    w = world
    _ok(_owner_call(w, route, w.a, w.pa, w.pa2), f"{route} as owner")
    if route.secondary and not route.secondary_required:
        _ok(w.call(route, w.a, w.pa2, secondary=w.pa), f"{route} as owner with {route.secondary}")
    assert w.pa in w.reads or w.pa2 in w.reads, "the route never read the schedule"
    assert w.cache_calls == [], f"{route} uses the analysis cache: add cache-isolation tests"


@pytest.mark.parametrize("route", ROUTES, ids=str)
def test_other_tenant_gets_not_found_like_a_random_id(world: World, route: Route) -> None:
    w = world
    _ok(_owner_call(w, route, w.a, w.pa, w.pa2), f"{route} as owner")
    _ok(_owner_call(w, route, w.b, w.pb, w.pb2), f"{route} as B on B's own project")
    w.reads.clear()
    w.asked.clear()

    # A second id, when required, is B's own: only the path id is foreign.
    second = w.pb if route.secondary_required else None
    foreign = w.call(route, w.b, w.pa, secondary=second)
    foreign2 = w.call(route, w.b, w.pa2, secondary=second)
    random_id = w.call(route, w.b, str(uuid.uuid4()), secondary=second)
    sequential = w.call(route, w.b, "proj-9999", secondary=second)

    assert _answer(foreign) == (404, NOT_FOUND), foreign.text
    assert _answer(foreign) == _answer(foreign2) == _answer(random_id) == _answer(sequential)
    assert w.reads == [], f"{route} read a schedule before refusing: {w.reads}"
    assert w.asked == []


@pytest.mark.parametrize("route", WITH_SECONDARY, ids=str)
def test_foreign_second_id_on_own_project_is_not_found(world: World, route: Route) -> None:
    w = world
    assert route.secondary is not None
    # Control: B with both ids B's own succeeds, so the refusals below are
    # about the second id and not about B or the parameter.
    _ok(w.call(route, w.b, w.pb2, secondary=w.pb), f"{route} as B with own {route.secondary}")
    w.reads.clear()

    foreign = w.call(route, w.b, w.pb2, secondary=w.pa)
    foreign2 = w.call(route, w.b, w.pb, secondary=w.pa2)
    random_id = w.call(route, w.b, w.pb2, secondary=str(uuid.uuid4()))
    sequential = w.call(route, w.b, w.pb2, secondary="proj-9999")

    assert _answer(foreign) == (404, NOT_FOUND), foreign.text
    assert _answer(foreign) == _answer(foreign2) == _answer(random_id) == _answer(sequential)
    # Every id is authorized before any schedule is read, B's own included.
    assert w.reads == [], f"{route} read a schedule before refusing: {w.reads}"


@pytest.mark.parametrize("route", [r for r in ROUTES if r.secondary_required], ids=str)
def test_missing_second_id_is_a_bad_request_only_on_an_own_project(
    world: World, route: Route
) -> None:
    """The 400 for an absent second id must not become an existence oracle."""
    w = world
    own = w.call(route, w.b, w.pb2)
    foreign = w.call(route, w.b, w.pa2)
    assert own.status_code == 400, own.text
    assert _answer(foreign) == (404, NOT_FOUND)


def test_ask_engine_runs_only_for_the_owner(world: World) -> None:
    w = world
    route = next(r for r in ROUTES if r.path.endswith("/ask"))
    _ok(w.call(route, w.a, w.pa), "ask as owner")
    assert len(w.asked) == 1
    assert w.call(route, w.b, w.pa).status_code == 404
    assert len(w.asked) == 1


def test_narrative_uses_the_given_baseline(world: World) -> None:
    """A given baseline is compared, never silently dropped."""
    w = world
    route = next(r for r in ROUTES if r.path.endswith("/narrative"))
    alone = _ok(w.call(route, w.a, w.pa2), "narrative")
    compared = _ok(w.call(route, w.a, w.pa2, secondary=w.pa), "narrative with baseline")
    titles = {s["title"] for s in compared["sections"]}
    assert "Schedule Changes" in titles
    assert "Schedule Changes" not in {s["title"] for s in alone["sections"]}
