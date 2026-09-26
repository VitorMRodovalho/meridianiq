# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Project ids carried in a request body are authorized first (ADR-0030).

Routes covered, each taking every project id it uses from the JSON body:

* ``POST /api/v1/compare`` in ``src/api/routers/comparison.py``;
* ``POST /api/v1/forensic/half-step``, ``mip-3-1``, ``mip-3-2``, ``mip-3-5``,
  ``mip-3-6``, ``mip-3-7`` and ``create-timeline`` in
  ``src/api/routers/forensics.py``;
* ``POST /api/v1/trends`` in ``src/api/routers/cost.py``;
* ``POST /api/v1/ips/reconcile`` and ``POST /api/v1/recovery/validate`` in
  ``src/api/routers/admin.py``.

The harness follows ``tests/test_tenancy_analysis.py``: ``ENVIRONMENT=production``,
real HS256 JWTs and a fresh ``InMemoryStore`` wired into ``src.api.deps``,
never ``dependency_overrides``, so the whole auth -> principal -> access path
runs.

Each route is driven slot by slot, a slot being one project id in its body:

* each tenant, with every id their own, reaches the route and its engine runs
  (positive control: fails, never skips);
* B's own ids with one of A's in a single slot is a 404 identical to a random
  id in that slot, and so are A's ids with only one of B's own among them
  (the mixed-ownership arms, both ways round);
* an ownerless project in any slot is a 404 for a user;
* no refused request reads a schedule or runs the engine;
* an API key acts as its owner (ADR-0030 section 6), over HTTP;
* an id list is bounded before any lookup, since each id costs a full load;
* a granted project whose schedule fails to load is logged with its id.

The last part is a census of the request bodies in the OpenAPI schema. It
flags a body with a top-level field named like an id (``id``, ``ids``,
``*_id``, ``*_ids``), and any body it cannot read field by field (a free-form
dict, an array, a scalar or an untyped body). Each flagged route has to be
placed: covered here, covered by another module, listed as not migrated, or
stated to take no project id. Nested fields with no declared shape are listed
with the reason no tenant id is read from them, and a typed id list must
declare ``maxItems``. What the census does not read: id-named fields nested in
typed sub-objects (today all activity, fragment, risk or resource ids), and
routes left out of the schema, which are listed in ``HIDDEN``.
"""

from __future__ import annotations

import copy
import functools
import importlib
import logging
import pkgutil
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi import Body, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

import src.api.deps as deps
import src.api.routers as routers_pkg
from src.api import schemas
from src.api import access, auth, organizations
from src.api.app import app
from src.api.routers import admin, comparison, cost, forensics
from src.api.storage import TimelineStore
from src.database import config
from src.database.store import InMemoryStore
from src.parser.models import ParsedSchedule
from src.parser.xer_reader import XERReader

FIXTURES = Path(__file__).parent / "fixtures"
TEST_JWT_SECRET = "test-secret"  # tests/conftest.py sets SUPABASE_JWT_SECRET to this

USER_A = "00000000-0000-4000-8000-00000000c5a1"
USER_B = "00000000-0000-4000-8000-00000000c5b2"

NOT_FOUND = (404, {"detail": "Project not found"})

#: One project per file and tenant; a route with n slots uses the first n.
SCHEDULES = ("sample.xer", "sample_update.xer", "sample_update2.xer")


# ------------------------------------------------------------------ #
# Route table                                                        #
# ------------------------------------------------------------------ #


@dataclass(frozen=True)
class Route:
    path: str
    slots: int  # how many project ids the body carries
    body: Callable[[list[str]], dict[str, Any]]  # the body, from one id per slot
    engine: str  # dotted path of the analysis the route runs

    @property
    def key(self) -> tuple[str, str]:
        return ("POST", self.path)

    def __str__(self) -> str:
        return self.path


def _pair(first: str, second: str) -> Callable[[list[str]], dict[str, Any]]:
    return lambda ids: {first: ids[0], second: ids[1]}


def _listed(ids: list[str]) -> dict[str, Any]:
    return {"project_ids": ids}


_F = "src.api.routers.forensics"

ROUTES: list[Route] = [
    Route(
        "/api/v1/compare",
        2,
        _pair("baseline_id", "update_id"),
        "src.api.routers.comparison.ScheduleComparison",
    ),
    Route(
        "/api/v1/forensic/half-step",
        2,
        _pair("baseline_id", "update_id"),
        f"{_F}.analyze_half_step",
    ),
    Route("/api/v1/forensic/mip-3-1", 2, _pair("baseline_id", "final_id"), f"{_F}.analyze_mip_3_1"),
    Route("/api/v1/forensic/mip-3-2", 3, _listed, f"{_F}.analyze_mip_3_2"),
    Route(
        "/api/v1/forensic/mip-3-5",
        3,
        lambda ids: {"project_ids": ids, "window_delay_events": []},
        f"{_F}.analyze_mip_3_5",
    ),
    Route(
        "/api/v1/forensic/mip-3-6",
        1,
        lambda ids: {"project_id": ids[0], "delay_events": [{"task_id": "A1000", "days": 1.0}]},
        f"{_F}.analyze_mip_3_6",
    ),
    Route("/api/v1/forensic/mip-3-7", 3, _listed, f"{_F}.analyze_mip_3_7"),
    Route("/api/v1/forensic/create-timeline", 3, _listed, f"{_F}.ForensicAnalyzer"),
    Route("/api/v1/trends", 3, _listed, "src.analytics.schedule_trends.compute_trend_point"),
    Route(
        "/api/v1/ips/reconcile",
        3,
        lambda ids: {"master_project_id": ids[0], "sub_project_ids": ids[1:]},
        "src.analytics.ips_reconciliation.IPSReconciler",
    ),
    Route(
        "/api/v1/recovery/validate",
        2,
        _pair("impacted_project_id", "recovery_project_id"),
        "src.analytics.recovery_validation.RecoveryValidator",
    ),
]

SLOTS = [pytest.param(r, i, id=f"{r}[{i}]") for r in ROUTES for i in range(r.slots)]
MULTI_SLOTS = [
    pytest.param(r, i, id=f"{r}[{i}]") for r in ROUTES if r.slots > 1 for i in range(r.slots)
]

_TIMELINES = "/api/v1/forensic/timelines"
_OWNED_RESULT = "an owned result, no project id; tests/test_owned_result_stores.py"
_OWN_ACCOUNT = "no project id: the caller's own account (require_auth)"

#: Routes of comparison.py, forensics.py and admin.py this module does not drive, and why.
EXEMPT: dict[tuple[str, str], str] = {
    ("GET", _TIMELINES): _OWNED_RESULT,
    ("GET", f"{_TIMELINES}/{{timeline_id}}"): _OWNED_RESULT,
    ("GET", f"{_TIMELINES}/{{timeline_id}}/delay-trend"): _OWNED_RESULT,
    ("POST", "/api/v1/api-keys"): _OWN_ACCOUNT,
    ("GET", "/api/v1/api-keys"): _OWN_ACCOUNT,
    ("DELETE", "/api/v1/api-keys/{key_id}"): _OWN_ACCOUNT,
    ("DELETE", "/api/v1/user/data"): _OWN_ACCOUNT,
}


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
    store: InMemoryStore
    a: dict[str, str]  # auth headers of user A
    b: dict[str, str]  # auth headers of user B
    own_a: list[str]  # A's projects, one per file in SCHEDULES
    own_b: list[str]  # B's projects, one per file in SCHEDULES
    p0: str  # a project with no recorded owner
    lookups: list[str] = field(default_factory=list)  # owner lookups by the access check
    reads: list[str] = field(default_factory=list)  # project ids whose schedule was read
    engines: list[str] = field(default_factory=list)  # analyses that ran
    cache_calls: list[str] = field(default_factory=list)  # analysis-cache methods called

    def post(self, route: Route, headers: dict[str, str] | None, ids: list[str]) -> Any:
        return self.client.post(route.path, json=route.body(ids), headers=headers)

    def forget(self) -> None:
        self.reads.clear()
        self.engines.clear()


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
    monkeypatch.setattr(deps, "_timeline_store", TimelineStore())
    assert deps.get_store() is store

    def seed(name: str, owner: str | None) -> str:
        return str(store.add(copy.deepcopy(_parsed(name)), b"x", user_id=owner))

    w = World(
        client=TestClient(app),
        store=store,
        a={"Authorization": f"Bearer {_token(USER_A)}"},
        b={"Authorization": f"Bearer {_token(USER_B)}"},
        own_a=[seed(name, USER_A) for name in SCHEDULES],
        own_b=[seed(name, USER_B) for name in SCHEDULES],
        p0=seed("sample.xer", None),
    )
    assert store.get_project_owner(w.p0) == (True, None)

    # The access check's one read. Recorded, so a test can show a request was
    # refused before any lookup at all.
    owner_lookup: Callable[[str], tuple[bool, str | None]] = store.get_project_owner

    def spy_owner(project_id: str) -> tuple[bool, str | None]:
        w.lookups.append(project_id)
        return owner_lookup(project_id)

    monkeypatch.setattr(store, "get_project_owner", spy_owner)

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

    # Spy on each route's engine where the route looks it up, so a refusal
    # that still computed would show.
    def spy_engine(target: str) -> None:
        module_name, attr = target.rsplit(".", 1)
        module = importlib.import_module(module_name)
        original: Callable[..., Any] = getattr(module, attr)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            w.engines.append(target)
            return original(*args, **kwargs)

        monkeypatch.setattr(module, attr, wrapper)

    for route in ROUTES:
        spy_engine(route.engine)
    return w


def _ok(resp: Any, what: str) -> Any:
    """Positive control: the caller must succeed. Fails (never skips) otherwise."""
    assert 200 <= resp.status_code < 300, f"denied on {what}: {resp.status_code} {resp.text}"
    return resp.json()


def _answer(resp: Any) -> tuple[int, Any]:
    return resp.status_code, resp.json()


def _with(ids: list[str], slot: int, value: str) -> list[str]:
    out = list(ids)
    out[slot] = value
    return out


def _assert_refused_before_any_read(w: World, route: Route) -> None:
    assert w.reads == [], f"{route} read a schedule before refusing: {w.reads}"
    assert w.engines == [], f"{route} ran its engine before refusing: {w.engines}"


# ------------------------------------------------------------------ #
# The table is the whole surface of these routers                    #
# ------------------------------------------------------------------ #


def test_route_table_covers_every_route_of_these_routers() -> None:
    # Read each module's own router: from FastAPI 0.141, app.routes holds the
    # included routers unflattened, so filtering app.routes finds nothing.
    def registered(*modules: Any) -> set[tuple[str, str]]:
        return {
            (method, r.path)
            for module in modules
            for r in module.router.routes
            if isinstance(r, APIRoute)
            for method in r.methods
        }

    covered = {r.key for r in ROUTES}
    assert len(covered) == len(ROUTES), "duplicate route in the table"
    assert covered.isdisjoint(EXEMPT)
    # cost.py's other routes are classified by tests/test_tenancy_intelligence.py.
    trends = ("POST", "/api/v1/trends")
    assert trends in registered(cost)
    surface = registered(comparison, forensics, admin) | {trends}
    assert surface == covered | set(EXEMPT), (
        f"untested: {sorted(surface - covered - set(EXEMPT))}; "
        f"stale: {sorted((covered | set(EXEMPT)) - surface)}"
    )


# ------------------------------------------------------------------ #
# Every route                                                        #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize("route", ROUTES, ids=str)
def test_anonymous_is_rejected(world: World, route: Route) -> None:
    """Negative control for the harness: production auth really is on."""
    resp = world.post(route, None, world.own_a[: route.slots])
    assert resp.status_code == 401, resp.text
    _assert_refused_before_any_read(world, route)


@pytest.mark.parametrize("route", ROUTES, ids=str)
def test_each_tenant_reaches_own_projects(world: World, route: Route) -> None:
    """Positive controls; they also show the read and engine spies are armed."""
    w = world
    for headers, own, who in ((w.a, w.own_a, "A"), (w.b, w.own_b, "B")):
        w.forget()
        ids = own[: route.slots]
        _ok(w.post(route, headers, ids), f"{route} as {who}")
        assert set(ids) <= set(w.reads), f"{route} never read the schedules: {w.reads}"
        assert route.engine in w.engines, f"{route} never ran {route.engine}"
    assert w.cache_calls == [], f"{route} uses the analysis cache: add cache-isolation tests"


@pytest.mark.parametrize(("route", "slot"), SLOTS)
def test_one_foreign_id_is_not_found_like_a_random_one(
    world: World, route: Route, slot: int
) -> None:
    """B's own ids with one of A's: 404, identical to a missing id in that slot.

    For ``/trends`` this is also the change from skipping an unknown id to
    refusing the request: a random id is a 404, never a shorter series.
    """
    w = world
    own = w.own_b[: route.slots]
    _ok(w.post(route, w.b, own), f"{route} as B")  # control: the rest of the body is fine
    w.forget()

    foreign = w.post(route, w.b, _with(own, slot, w.own_a[slot]))
    random_id = w.post(route, w.b, _with(own, slot, str(uuid.uuid4())))
    sequential = w.post(route, w.b, _with(own, slot, "proj-9999"))

    assert _answer(foreign) == NOT_FOUND, foreign.text
    assert _answer(foreign) == _answer(random_id) == _answer(sequential)
    _assert_refused_before_any_read(w, route)


@pytest.mark.parametrize(("route", "slot"), MULTI_SLOTS)
def test_one_own_id_among_foreign_ones_is_not_found(world: World, route: Route, slot: int) -> None:
    """The mixed arm the other way round: B's own id in one slot, A's in every other."""
    w = world
    ids = _with(w.own_a[: route.slots], slot, w.own_b[slot])
    resp = w.post(route, w.b, ids)
    assert _answer(resp) == NOT_FOUND, resp.text
    _assert_refused_before_any_read(w, route)


@pytest.mark.parametrize(("route", "slot"), SLOTS)
def test_ownerless_project_is_hidden_from_users(world: World, route: Route, slot: int) -> None:
    """Separates the access check from the store's own ``user_id`` filter.

    ``InMemoryStore.get(pid, user_id=...)`` hands an ownerless project to
    anyone, so this is the case only the access context can refuse.
    """
    w = world
    assert w.store.get(w.p0, user_id=USER_B) is not None  # the filter lets it by
    w.forget()
    own = w.own_b[: route.slots]
    ownerless = w.post(route, w.b, _with(own, slot, w.p0))
    missing = w.post(route, w.b, _with(own, slot, str(uuid.uuid4())))
    assert _answer(ownerless) == NOT_FOUND, ownerless.text
    assert _answer(ownerless) == _answer(missing)
    _assert_refused_before_any_read(w, route)


# ------------------------------------------------------------------ #
# Loose (dict) bodies: a malformed id is a 400 for everyone          #
# ------------------------------------------------------------------ #

MALFORMED: list[tuple[str, dict[str, Any]]] = [
    ("/api/v1/trends", {"project_ids": "not-a-list"}),
    ("/api/v1/trends", {"project_ids": [1, 2]}),
    ("/api/v1/trends", {"project_ids": [["nested"]]}),
    ("/api/v1/ips/reconcile", {"master_project_id": ["x"], "sub_project_ids": ["y"]}),
    ("/api/v1/ips/reconcile", {"master_project_id": "x", "sub_project_ids": "y"}),
    ("/api/v1/ips/reconcile", {"master_project_id": "x", "sub_project_ids": [{"id": "y"}]}),
    ("/api/v1/recovery/validate", {"impacted_project_id": 1, "recovery_project_id": "y"}),
    ("/api/v1/recovery/validate", {"impacted_project_id": "x", "recovery_project_id": ["y"]}),
]


@pytest.mark.parametrize(("path", "body"), MALFORMED)
def test_malformed_ids_are_a_bad_request_before_any_lookup(
    world: World, path: str, body: dict[str, Any]
) -> None:
    """The shape is checked before the ids, so a 400 says nothing about any project."""
    w = world
    resp = w.client.post(path, json=body, headers=w.b)
    assert resp.status_code == 400, resp.text
    assert w.lookups == [] and w.reads == [] and w.engines == []


# ------------------------------------------------------------------ #
# Id lists are bounded before any lookup                             #
# ------------------------------------------------------------------ #

#: Routes whose body carries a list of ids: the most ids ``Route.body`` may
#: hold, and the answer to one more. Reconcile holds a master id plus the subs.
_SERIES = schemas.MAX_SERIES_PROJECT_IDS
CAPPED: list[tuple[str, int, int]] = [
    ("/api/v1/forensic/mip-3-2", _SERIES, 422),
    ("/api/v1/forensic/mip-3-5", _SERIES, 422),
    ("/api/v1/forensic/mip-3-7", _SERIES, 422),
    ("/api/v1/forensic/create-timeline", _SERIES, 422),
    ("/api/v1/trends", schemas.MAX_TREND_PROJECT_IDS, 400),
    ("/api/v1/ips/reconcile", _SERIES + 1, 400),
]


def test_series_routes_accept_a_multi_year_program() -> None:
    """Forensic series must fit five years of monthly updates (60), as on main."""
    assert schemas.MAX_SERIES_PROJECT_IDS >= 60
    assert schemas.MAX_TREND_PROJECT_IDS == 50  # unchanged from main


_BY_PATH = {r.path: r for r in ROUTES}


@pytest.mark.parametrize(("path", "most", "over"), CAPPED)
def test_id_lists_are_capped_before_any_lookup(
    world: World, path: str, most: int, over: int
) -> None:
    """Each id costs a full schedule load and an engine pass, a repeated id too.

    At the cap the request reaches the access check (random ids, so a 404).
    One id more, even the caller's own id repeated, is refused before any
    owner lookup, schedule read or engine run.
    """
    w = world
    route = _BY_PATH[path]
    at_cap = w.post(route, w.b, [str(uuid.uuid4()) for _ in range(most)])
    assert _answer(at_cap) == NOT_FOUND, at_cap.text
    assert w.lookups, f"{route} never reached the access check at the cap"
    w.lookups.clear()

    over_cap = w.post(route, w.b, [w.own_b[0]] * (most + 1))
    assert over_cap.status_code == over, over_cap.text
    assert w.lookups == [] and w.reads == [] and w.engines == []


# ------------------------------------------------------------------ #
# API keys act as their owner (ADR-0030 section 6)                   #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize("route", ROUTES, ids=str)
def test_api_key_acts_as_its_owner(
    world: World, monkeypatch: pytest.MonkeyPatch, route: Route
) -> None:
    """A's key reaches A's projects and none of B's, over ``X-API-Key`` alone.

    The key lives in the in-memory key table: the harness has no Supabase
    client (asserted), so this runs the header -> key -> principal -> access
    path with no bearer token at all.
    """
    w = world
    monkeypatch.setattr(auth, "_api_keys", {})
    assert auth._get_supabase_client() is None
    key = {"X-API-Key": auth.generate_api_key(USER_A, "body-ids")["key"]}

    own = w.own_a[: route.slots]
    _ok(w.post(route, key, own), f"{route} with A's key")
    assert route.engine in w.engines, f"{route} never ran {route.engine}"
    w.forget()

    foreign = w.post(route, key, _with(own, 0, w.own_b[0]))
    random_id = w.post(route, key, _with(own, 0, str(uuid.uuid4())))
    assert _answer(foreign) == NOT_FOUND, foreign.text
    assert _answer(foreign) == _answer(random_id)
    _assert_refused_before_any_read(w, route)


# ------------------------------------------------------------------ #
# A granted project whose schedule fails to load                     #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(("route", "slot"), SLOTS)
def test_granted_project_that_fails_to_load_is_logged(
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    route: Route,
    slot: int,
) -> None:
    """After the access check, a missing schedule is a load failure, not a refusal.

    The Supabase store answers ``None`` when a Storage download or a re-parse
    fails. The route keeps its 404 (the caller owns the project, so the answer
    tells them nothing about anyone else) and logs the id, so the report can
    be traced to the project that failed.
    """
    w = world
    own = w.own_b[: route.slots]
    broken = own[slot]
    load = w.store.get_project

    def load_fails_for_broken(project_id: str, *args: Any, **kwargs: Any) -> Any:
        return None if project_id == broken else load(project_id, *args, **kwargs)

    monkeypatch.setattr(w.store, "get_project", load_fails_for_broken)
    with caplog.at_level(logging.WARNING, logger=deps.logger.name):
        resp = w.post(route, w.b, own)
    assert _answer(resp) == NOT_FOUND, resp.text
    assert set(own) <= set(w.lookups), "the ids were not all granted first"
    logged = [r.getMessage() for r in caplog.records if r.name == deps.logger.name]
    assert logged == [f"granted project {broken} has no loadable schedule"]


# ------------------------------------------------------------------ #
# Census: every request body that can carry an id is placed          #
# ------------------------------------------------------------------ #

_RESULT_STORES = "tests/test_owned_result_stores.py"
_ORG_SURFACES = "tests/test_tenancy_org_surfaces.py"

#: Body-id routes whose check is tested in another module.
ELSEWHERE: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/reports/generate"): _RESULT_STORES,
    ("POST", "/api/v1/tia/analyze"): _RESULT_STORES,
    ("POST", "/api/v1/contract/check"): f"analysis_id names an owned result; {_RESULT_STORES}",
    ("POST", "/api/v1/shares/project"): _ORG_SURFACES,
    ("POST", "/api/v1/projects/{project_id}/value-milestones"): _ORG_SURFACES,
    ("PUT", "/api/v1/value-milestones/{milestone_id}"): f"project_id key; {_ORG_SURFACES}",
}

#: Body-id routes that do not resolve their body id through the access context
#: yet: the body field, and what holds until they do. Both move when the
#: revisions router's reads, path id included, leave the store's ``user_id``
#: filter for the access context (ADR-0030: routes migrate in slices).
#: ``test_not_migrated_gap_is_as_stated`` exercises the in-memory half of each
#: reason (the SupabaseStore half is read from its query, not exercised) and
#: fails once a route migrates, so an entry cannot outlive its gap.
_REVISIONS_GAP = (
    "is read with get_project_meta(user_id=...), not through the access context. "
    "That filter is owner-only on SupabaseStore, but InMemoryStore lets a project "
    "with no recorded owner through for any user, and the refusal is the structured "
    "error_code 404 the revision card matches on (issue #86), not ADR-0030's body. "
    "Moves with the revisions router's store-scoped reads."
)
NOT_MIGRATED: dict[tuple[str, str], tuple[str, str]] = {
    ("POST", "/api/v1/projects/{project_id}/confirm-revision-of"): (
        "parent_project_id",
        f"parent_project_id {_REVISIONS_GAP}",
    ),
    ("POST", "/api/v1/projects/{project_id}/skip-revision-of"): (
        "candidate_project_id",
        f"candidate_project_id {_REVISIONS_GAP}",
    ),
}

#: Loose (dict) bodies read by their handler, which takes no project id from them.
NO_PROJECT_ID: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/api-keys"): "a key name",
    ("PUT", "/api/v1/programs/{program_id}"): "program name and description",
    ("POST", "/api/v1/schedule/generate"): "generation parameters",
    ("POST", "/api/v1/schedule/build"): "a free-text description",
    ("POST", "/api/v1/projects/{project_id}/risk-register"): "a risk entry; project is the path id",
    (
        "POST",
        "/api/v1/projects/{project_id}/optimize",
    ): "optimizer settings; project is the path id",
}

#: Nested fields with no declared shape: where they are, and why no tenant id
#: is read from them.
NESTED_FREE_FORM: dict[tuple[str, str], tuple[tuple[str, ...], str]] = {
    ("POST", "/api/v1/reports/generate"): (
        ("options",),
        "report settings; options['snapshot_id'] is only read through "
        "get_cost_snapshot(project_id, snapshot_id) with the authorized project_id, "
        "which finds no snapshot of another project",
    ),
    ("POST", "/api/v1/tia/analyze"): (
        (
            "fragments[].activities[].predecessors[]",
            "fragments[].activities[].successors[]",
        ),
        "fragment logic links; their activity codes resolve inside the authorized "
        "project's schedule",
    ),
}

#: Routes left out of the OpenAPI schema, which the census therefore cannot see.
HIDDEN: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/internal/hooks/auth-user-created"): "auth webhook payload; no project id",
}


def _is_id_name(name: str) -> bool:
    return name in ("id", "ids") or name.endswith(("_id", "_ids"))


@dataclass(frozen=True)
class BodyShape:
    """What the census can say about one request body."""

    ids: tuple[str, ...] = ()  # top-level fields named like an id
    loose: bool = False  # no fields to read one by one: dict, array, scalar or untyped
    free_form: tuple[str, ...] = ()  # nested fields with no declared shape
    unbounded: tuple[str, ...] = ()  # top-level id lists with no maxItems


def _body_census(spec: dict[str, Any] | None = None) -> dict[tuple[str, str], BodyShape]:
    """Map each route with a request body to its :class:`BodyShape`.

    Read from an OpenAPI document, ``app.openapi()`` unless one is given. It is
    public and does not depend on how FastAPI stores included routers.
    """
    spec = app.openapi() if spec is None else spec
    schemas: dict[str, Any] = spec.get("components", {}).get("schemas", {})

    def resolve(schema: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        ref = schema.get("$ref")
        if ref is None:
            return schema, None
        name = ref.rsplit("/", 1)[-1]
        return schemas[name], name

    def alternatives(schema: dict[str, Any]) -> list[dict[str, Any]]:
        return list(schema.get("anyOf") or schema.get("oneOf") or schema.get("allOf") or [])

    def variants(schema: dict[str, Any]) -> list[dict[str, Any]]:
        """The shapes a value may take, ``null`` (an optional value) left out."""
        schema, _ = resolve(schema)
        alts = alternatives(schema)
        if alts:
            return [v for alt in alts for v in variants(alt)]
        return [] if schema.get("type") == "null" else [schema]

    def free(schema: dict[str, Any]) -> bool:
        """An object with no declared fields, or one that also takes undeclared ones."""
        if schema.get("type") not in ("object", None):
            return False
        extra = schema.get("additionalProperties")
        return not schema.get("properties") or extra not in (None, False)

    def walk(schema: dict[str, Any], where: str, seen: frozenset[str]) -> list[str]:
        """The places under ``where`` that have no declared shape."""
        schema, name = resolve(schema)
        if name is not None:
            if name in seen:
                return []
            seen = seen | {name}
        alts = alternatives(schema)
        if alts:
            return [p for alt in alts for p in walk(alt, where, seen)]
        if schema.get("type") == "null":
            return []
        if schema.get("type") == "array":
            return walk(schema.get("items", {}), f"{where}[]", seen)
        if free(schema):
            return [where]
        return [
            p
            for field_name, sub in schema.get("properties", {}).items()
            for p in walk(sub, f"{where}.{field_name}", seen)
        ]

    def shape(schema: dict[str, Any]) -> BodyShape:
        ids: list[str] = []
        loose = False
        free_form: list[str] = []
        unbounded: list[str] = []
        for body in variants(schema):
            props: dict[str, Any] = body.get("properties") or {}
            loose = loose or not props or free(body)
            for name, sub in props.items():
                if _is_id_name(name):
                    ids.append(name)
                    lists = [v for v in variants(sub) if v.get("type") == "array"]
                    if any("maxItems" not in v for v in lists):
                        unbounded.append(name)
                free_form += walk(sub, name, frozenset())
        return BodyShape(
            ids=tuple(dict.fromkeys(ids)),
            loose=loose,
            free_form=tuple(dict.fromkeys(free_form)),
            unbounded=tuple(dict.fromkeys(unbounded)),
        )

    census: dict[tuple[str, str], BodyShape] = {}
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            content = operation.get("requestBody", {}).get("content", {})
            shapes = [shape(media["schema"]) for media in content.values()]
            if not shapes:
                continue
            census[(method.upper(), path)] = BodyShape(
                ids=tuple(dict.fromkeys(i for s in shapes for i in s.ids)),
                loose=any(s.loose for s in shapes),
                free_form=tuple(dict.fromkeys(p for s in shapes for p in s.free_form)),
                unbounded=tuple(dict.fromkeys(u for s in shapes for u in s.unbounded)),
            )
    return census


class _ProbeLeaf(BaseModel):
    note: str
    count: int = 0


class _ProbeNested(BaseModel):
    note: str
    extra: dict[str, Any] = {}


class _ProbeTyped(BaseModel):
    name: str
    project_ids: list[str] = Field(..., max_length=3)
    child: _ProbeNested | None = None
    leaves: list[_ProbeLeaf] = []


class _ProbeUnbounded(BaseModel):
    project_ids: list[str]


def _probe_spec() -> dict[str, Any]:
    """An app with one route per body shape the census has to tell apart."""
    probe = FastAPI()

    @probe.post("/array")
    def array_body(body: list[str] = Body(...)) -> None: ...

    @probe.post("/untyped")
    def untyped_body(body: Any = Body(...)) -> None: ...

    @probe.post("/scalar")
    def scalar_body(body: str = Body(...)) -> None: ...

    @probe.post("/dict")
    def dict_body(body: dict[str, Any]) -> None: ...

    @probe.post("/typed")
    def typed_body(body: _ProbeTyped) -> None: ...

    @probe.post("/unbounded")
    def unbounded_body(body: _ProbeUnbounded) -> None: ...

    @probe.post("/plain")
    def plain_body(body: _ProbeLeaf) -> None: ...

    return probe.openapi()


def test_census_instrument_tells_each_body_shape_apart() -> None:
    """Negative control on a probe app: each arm fires on its shape and nowhere else."""
    assert _body_census(_probe_spec()) == {
        ("POST", "/array"): BodyShape(loose=True),
        ("POST", "/untyped"): BodyShape(loose=True),
        ("POST", "/scalar"): BodyShape(loose=True),
        ("POST", "/dict"): BodyShape(loose=True),
        ("POST", "/typed"): BodyShape(ids=("project_ids",), free_form=("child.extra",)),
        ("POST", "/unbounded"): BodyShape(ids=("project_ids",), unbounded=("project_ids",)),
        ("POST", "/plain"): BodyShape(),
    }


def test_census_instrument_reads_this_app() -> None:
    """The same arms on real bodies, so the probe app is not the only evidence."""
    census = _body_census()
    assert census[("POST", "/api/v1/compare")] == BodyShape(ids=("baseline_id", "update_id"))
    assert census[("POST", "/api/v1/trends")] == BodyShape(loose=True)
    assert census[("POST", "/api/v1/projects/{project_id}/what-if")] == BodyShape()
    assert census[("POST", "/api/v1/reports/generate")] == BodyShape(
        ids=("project_id", "baseline_id"), free_form=("options",)
    )


def test_every_body_that_can_carry_an_id_is_placed() -> None:
    census = _body_census()
    flagged = {key for key, shape in census.items() if shape.ids or shape.loose}
    here = {r.key for r in ROUTES}
    groups = [here, set(ELSEWHERE), set(NOT_MIGRATED), set(NO_PROJECT_ID)]
    placed: set[tuple[str, str]] = set()
    for group in groups:
        assert placed.isdisjoint(group), f"placed twice: {sorted(placed & group)}"
        placed |= group
    assert flagged == placed, (
        f"unplaced: {sorted(flagged - placed)}; stale: {sorted(placed - flagged)}"
    )
    # A loose body is opaque to the census, so it cannot be "no project id"
    # by inspection; those claims are the entries in NO_PROJECT_ID.
    assert all(census[key].loose for key in NO_PROJECT_ID)


def test_every_nested_free_form_field_is_accounted_for() -> None:
    """A nested dict can carry any id; each one states why none is read from it."""
    found = {key: shape.free_form for key, shape in _body_census().items() if shape.free_form}
    assert found == {key: places for key, (places, _why) in NESTED_FREE_FORM.items()}


def test_every_typed_id_list_is_bounded() -> None:
    """Each id costs a full schedule load, so a typed id list declares ``maxItems``."""
    unbounded = {key: s.unbounded for key, s in _body_census().items() if s.unbounded}
    assert unbounded == {}


@pytest.mark.parametrize("key", sorted(NOT_MIGRATED), ids=lambda key: key[1].rsplit("/", 1)[-1])
def test_not_migrated_gap_is_as_stated(world: World, key: tuple[str, str]) -> None:
    """Tripwire for NOT_MIGRATED: the gap its reason states, measured in memory.

    Another tenant's project is refused like a missing one, and a project with
    no recorded owner gets past the body-id check. Once the route resolves the
    id through the access context the last assertion fails: then take the
    route out of NOT_MIGRATED and drop its arm here.
    """
    w = world
    body_field, _why = NOT_MIGRATED[key]

    def saved(owner: str | None) -> str:
        upload = f"upload-{uuid.uuid4().hex[:8]}"
        schedule = copy.deepcopy(_parsed("sample_update.xer"))
        return str(w.store.save_project(upload, schedule, b"x", user_id=owner))

    url = key[1].replace("{project_id}", saved(USER_B))

    def answer(body_id: str) -> tuple[int, Any]:
        resp = w.client.post(url, json={body_field: body_id}, headers=w.b)
        detail = resp.json().get("detail")
        return resp.status_code, detail.get("error_code") if isinstance(detail, dict) else detail

    missing = answer(str(uuid.uuid4()))
    assert missing == (404, "parent_not_found")
    assert answer(saved(USER_A)) == missing  # the owner filter holds for an owned row
    assert answer(saved(None)) != missing  # the gap: an ownerless row gets through


def test_census_blind_spot_is_only_the_known_hidden_routes() -> None:
    """Routes left out of OpenAPI escape the census; list them so a new one fails here."""
    modules = [
        importlib.import_module(f"{routers_pkg.__name__}.{m.name}")
        for m in pkgutil.iter_modules(routers_pkg.__path__)
    ]
    hidden = {
        (method, r.path)
        for module in [*modules, organizations]
        for r in module.router.routes
        if isinstance(r, APIRoute) and not r.include_in_schema
        for method in r.methods
    }
    assert hidden == set(HIDDEN)
