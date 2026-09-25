# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tenant isolation for single-project reads (ADR-0030).

Covers every project-scoped route in the analysis, schedule-ops (cash flow
and look-ahead), export and benchmark routers. The harness follows
``tests/test_owned_result_stores.py``: ``ENVIRONMENT=production``, real
HS256 JWTs and a fresh ``InMemoryStore``, never ``dependency_overrides``,
so the whole auth -> principal -> access path runs.

Each check has a positive control that fails (never skips) if the owner is
denied, and every "hidden" answer is compared with the answer for an id that
does not exist: the two must be identical, ``404 {"detail": "Project not
found"}``. The cache tests seed a sentinel the route would serve if it
consulted the cache first, and show the sentinel IS served to the owner, so
a 404 for the other tenant means the check ran before the cache lookup.
"""

from __future__ import annotations

import importlib.util
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

import src.api.deps as deps
from src.analytics.cost_integration import CBSElement, CostIntegrationResult
from src.api import access, auth
from src.api.app import app
from src.api.routers import benchmarks
from src.database import config
from src.database.store import InMemoryStore
from src.parser.xer_reader import XERReader

FIXTURES = Path(__file__).parent / "fixtures"
TEST_JWT_SECRET = "test-secret"  # tests/conftest.py sets SUPABASE_JWT_SECRET to this

USER_A = "00000000-0000-4000-8000-0000000000a1"
USER_B = "00000000-0000-4000-8000-0000000000b2"

NOT_FOUND = (404, {"detail": "Project not found"})
SENTINEL = {"sentinel": "cached-schedule-view"}
OPENPYXL = importlib.util.find_spec("openpyxl") is not None


def _token(sub: str) -> str:
    now = int(time.time())
    claims = {"sub": sub, "aud": "authenticated", "role": "authenticated", "iat": now}
    claims["exp"] = now + 3600
    return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256")


def _snapshot() -> CostIntegrationResult:
    return CostIntegrationResult(
        cbs_elements=[
            CBSElement(
                cbs_code="C.SP.100",
                cbs_level1="Construction",
                scope="Foundations",
                estimate=100_000.0,
                budget=120_000.0,
            )
        ],
        total_budget=120_000.0,
    )


@dataclass
class World:
    client: TestClient
    store: InMemoryStore
    a: dict[str, str]  # auth headers of user A
    b: dict[str, str]  # auth headers of user B
    pa: str  # A's project (sample.xer)
    pa2: str  # A's second project (sample_update.xer)
    pb: str  # B's project (sample.xer)
    p0: str  # a project with no recorded owner (sample.xer)
    snapshots: dict[str, str] = field(default_factory=dict)  # project id -> its CBS snapshot


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
    # The benchmark dataset is module state; each test starts from empty.
    monkeypatch.setattr(benchmarks, "_benchmark_dataset", [])

    def seed(name: str, owner: str | None) -> str:
        return str(store.add(XERReader(FIXTURES / name).parse(), b"x", user_id=owner))

    w = World(
        client=TestClient(app),
        store=store,
        a={"Authorization": f"Bearer {_token(USER_A)}"},
        b={"Authorization": f"Bearer {_token(USER_B)}"},
        pa=seed("sample.xer", USER_A),
        pa2=seed("sample_update.xer", USER_A),
        pb=seed("sample.xer", USER_B),
        p0=seed("sample.xer", None),
    )
    assert store.get_project_owner(w.p0) == (True, None)
    for pid, owner in ((w.pa, USER_A), (w.pb, USER_B), (w.p0, None)):
        w.snapshots[pid] = store.save_cost_upload(pid, _snapshot(), user_id=owner)
    return w


# ------------------------------------------------------------------ #
# Route table                                                        #
# ------------------------------------------------------------------ #


@dataclass(frozen=True)
class Route:
    method: str
    path: str  # "{pid}" is replaced by the project id under test
    params: Callable[[World, str], dict[str, Any]] = lambda _w, _pid: {}
    needs_openpyxl: bool = False


def _a_snapshot(w: World, _pid: str) -> dict[str, Any]:
    """A's snapshot id, whatever project is asked for: only the project varies."""
    return {"snapshot_id": w.snapshots[w.pa]}


ROUTES: dict[str, Route] = {
    "validation": Route("GET", "/api/v1/projects/{pid}/validation"),
    "critical-path": Route("GET", "/api/v1/projects/{pid}/critical-path"),
    "float-distribution": Route("GET", "/api/v1/projects/{pid}/float-distribution"),
    "milestones": Route("GET", "/api/v1/projects/{pid}/milestones"),
    "schedule-view": Route("GET", "/api/v1/projects/{pid}/schedule-view"),
    "schedule-view-cache": Route("DELETE", "/api/v1/projects/{pid}/schedule-view/cache"),
    "schedule-view-resources": Route("GET", "/api/v1/projects/{pid}/schedule-view/resources"),
    "delay-attribution": Route("GET", "/api/v1/projects/{pid}/delay-attribution"),
    "calendar-validation": Route("GET", "/api/v1/projects/{pid}/calendar-validation"),
    "cashflow": Route("GET", "/api/v1/projects/{pid}/cashflow"),
    "lookahead": Route("GET", "/api/v1/projects/{pid}/lookahead", lambda _w, _p: {"weeks": 4}),
    "export-xer": Route("GET", "/api/v1/projects/{pid}/export/xer"),
    "export-excel": Route("GET", "/api/v1/projects/{pid}/export/excel", needs_openpyxl=True),
    "export-aia-g703": Route(
        "GET", "/api/v1/projects/{pid}/export/aia-g703", _a_snapshot, needs_openpyxl=True
    ),
    "export-json": Route("GET", "/api/v1/projects/{pid}/export/json"),
    "export-csv": Route(
        "GET", "/api/v1/projects/{pid}/export/csv", lambda _w, _p: {"dataset": "activities"}
    ),
    "activities": Route("GET", "/api/v1/projects/{pid}/activities", lambda _w, _p: {"q": "A"}),
    "benchmark-contribute": Route(
        "POST", "/api/v1/benchmarks/contribute", lambda _w, pid: {"project_id": pid}
    ),
    "benchmark-compare": Route("GET", "/api/v1/benchmarks/compare/{pid}"),
}


def _call(
    w: World,
    route: Route,
    headers: dict[str, str] | None,
    pid: str,
    **extra: Any,
) -> Any:
    params = {**route.params(w, pid), **extra}
    return w.client.request(
        route.method, route.path.format(pid=pid), params=params, headers=headers
    )


def _answer(resp: Any) -> tuple[int, Any]:
    return resp.status_code, resp.json()


def _ok(resp: Any, what: str, route: Route | None = None) -> None:
    """Positive control: the caller must get past the access check. Fails, never skips.

    Without openpyxl, a route that renders a workbook answers 501 only after
    the project (and snapshot) were accepted, which is still "reached".
    """
    if route is not None and route.needs_openpyxl and not OPENPYXL:
        assert resp.status_code == 501, f"owner denied on {what}: {resp.status_code} {resp.text}"
        assert "openpyxl" in resp.json()["detail"]
        return
    assert 200 <= resp.status_code < 300, f"owner denied on {what}: {resp.status_code} {resp.text}"


def _assert_hidden_like_missing(foreign: Any, *missing: Any) -> None:
    assert _answer(foreign) == NOT_FOUND, foreign.text
    for other in missing:
        assert _answer(other) == NOT_FOUND, other.text


# ------------------------------------------------------------------ #
# Every route: owner reaches it, the other tenant gets "not found"   #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize("name", list(ROUTES))
class TestEveryProjectRead:
    def test_anonymous_is_rejected(self, world: World, name: str) -> None:
        """Negative control for the harness: production auth really is on."""
        resp = _call(world, ROUTES[name], None, world.pa)
        assert resp.status_code == 401, resp.text

    def test_owner_reaches_own_project(self, world: World, name: str) -> None:
        route = ROUTES[name]
        _ok(_call(world, route, world.a, world.pa), f"{name} as A", route)

    def test_other_tenant_reaches_own_project(self, world: World, name: str) -> None:
        """B's token works, so B's 404 on A's project is the access rule, not a broken B."""
        route = ROUTES[name]
        params = {"snapshot_id": world.snapshots[world.pb]} if name == "export-aia-g703" else {}
        _ok(_call(world, route, world.b, world.pb, **params), f"{name} as B", route)

    def test_other_tenant_gets_not_found_identical_to_missing(
        self, world: World, name: str
    ) -> None:
        route = ROUTES[name]
        _ok(_call(world, route, world.a, world.pa), f"{name} as A", route)

        foreign = _call(world, route, world.b, world.pa)
        random_uuid = _call(world, route, world.b, str(uuid.uuid4()))
        legacy_style = _call(world, route, world.b, "proj-9999")
        _assert_hidden_like_missing(foreign, random_uuid, legacy_style)

    def test_ownerless_project_is_hidden_from_users(self, world: World, name: str) -> None:
        """Separates the access check from the store's own ``user_id`` filter.

        ``InMemoryStore.get(pid, user_id=...)`` returns an ownerless project
        to anyone, so for the routes that also pass ``user_id`` to the store
        this is the case where only the access context can answer 404.
        """
        route = ROUTES[name]
        params = {"snapshot_id": world.snapshots[world.p0]} if name == "export-aia-g703" else {}
        assert world.store.get(world.p0, user_id=USER_A) is not None  # the filter lets it by
        ownerless = _call(world, route, world.a, world.p0, **params)
        missing = _call(world, route, world.a, str(uuid.uuid4()), **params)
        _assert_hidden_like_missing(ownerless, missing)


# ------------------------------------------------------------------ #
# Mixed ownership: B's project with one of A's ids alongside         #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize("path", ["schedule-view", "delay-attribution"])
class TestBaselineId:
    def test_owner_may_use_own_baseline(self, world: World, path: str) -> None:
        url = f"/api/v1/projects/{world.pa}/{path}"
        resp = world.client.get(url, params={"baseline_id": world.pa2}, headers=world.a)
        _ok(resp, f"{path} with own baseline")

    def test_foreign_baseline_on_own_project_is_not_found(self, world: World, path: str) -> None:
        url = f"/api/v1/projects/{world.pb}/{path}"
        foreign = world.client.get(url, params={"baseline_id": world.pa}, headers=world.b)
        missing = world.client.get(url, params={"baseline_id": str(uuid.uuid4())}, headers=world.b)
        _assert_hidden_like_missing(foreign, missing)

    def test_own_baseline_on_foreign_project_is_not_found(self, world: World, path: str) -> None:
        url = f"/api/v1/projects/{world.pa}/{path}"
        resp = world.client.get(url, params={"baseline_id": world.pb}, headers=world.b)
        assert _answer(resp) == NOT_FOUND

    def test_empty_baseline_means_none(self, world: World, path: str) -> None:
        url = f"/api/v1/projects/{world.pb}/{path}"
        _ok(world.client.get(url, params={"baseline_id": ""}, headers=world.b), "empty baseline")


class TestSnapshotId:
    def test_foreign_snapshot_on_own_project_is_not_retrievable(self, world: World) -> None:
        url = f"/api/v1/projects/{world.pb}/export/aia-g703"
        foreign = world.client.get(
            url, params={"snapshot_id": world.snapshots[world.pa]}, headers=world.b
        )
        missing = world.client.get(
            url, params={"snapshot_id": f"cost-{uuid.uuid4().hex}"}, headers=world.b
        )
        assert foreign.status_code == 404, foreign.text
        # A snapshot is looked up inside the (authorized) project, so A's id
        # names nothing in B's project: same answer shape as a random id.
        assert foreign.json()["detail"].startswith("CBS snapshot not retrievable")
        assert missing.json()["detail"].startswith("CBS snapshot not retrievable")
        assert foreign.status_code == missing.status_code


# ------------------------------------------------------------------ #
# Schedule-view cache                                                #
# ------------------------------------------------------------------ #


def _view(w: World, headers: dict[str, str], pid: str, **params: Any) -> Any:
    return w.client.get(f"/api/v1/projects/{pid}/schedule-view", params=params, headers=headers)


def _drop_cache(w: World, headers: dict[str, str], pid: str) -> Any:
    return w.client.delete(f"/api/v1/projects/{pid}/schedule-view/cache", headers=headers)


class TestScheduleViewCache:
    KEY = "schedule_view:none:wbs"

    def _seed_a(self, w: World) -> None:
        """A computes the view, then the cached row is replaced by a sentinel."""
        _ok(_view(w, w.a, w.pa), "schedule-view as A")
        assert w.store.get_analysis(w.pa, self.KEY) is not None
        w.store.save_analysis(w.pa, self.KEY, SENTINEL)
        # Control: the cache really answers this request, so a leak would show.
        assert _view(w, w.a, w.pa).json() == SENTINEL

    def test_other_tenant_cannot_read_cached_view(self, world: World) -> None:
        self._seed_a(world)
        foreign = _view(world, world.b, world.pa)
        missing = _view(world, world.b, str(uuid.uuid4()))
        _assert_hidden_like_missing(foreign, missing)
        assert "sentinel" not in foreign.text

    def test_other_tenant_force_does_not_touch_cache(self, world: World) -> None:
        self._seed_a(world)
        resp = _view(world, world.b, world.pa, force="true")
        assert _answer(resp) == NOT_FOUND
        assert world.store.get_analysis(world.pa, self.KEY) == SENTINEL

    def test_other_tenant_cannot_invalidate_cache(self, world: World) -> None:
        self._seed_a(world)
        foreign = _drop_cache(world, world.b, world.pa)
        missing = _drop_cache(world, world.b, str(uuid.uuid4()))
        _assert_hidden_like_missing(foreign, missing)
        assert world.store.get_analysis(world.pa, self.KEY) == SENTINEL

        # Control: the same request from the owner does remove it.
        own = _drop_cache(world, world.a, world.pa)
        _ok(own, "drop cache as A")
        assert own.json()["invalidated"] >= 1
        assert world.store.get_analysis(world.pa, self.KEY) is None

    def test_baseline_is_authorized_before_the_cache(self, world: World) -> None:
        """A cached variant keyed by a foreign baseline is never served."""
        foreign_key = f"schedule_view:{world.pa}:wbs"
        own_key = f"schedule_view:{world.pb}:wbs"
        world.store.save_analysis(world.pb, foreign_key, SENTINEL)
        world.store.save_analysis(world.pb, own_key, SENTINEL)

        # Control: with a baseline B may reach, the seeded row is served.
        assert _view(world, world.b, world.pb, baseline_id=world.pb).json() == SENTINEL

        resp = _view(world, world.b, world.pb, baseline_id=world.pa)
        assert _answer(resp) == NOT_FOUND

    def test_refused_request_writes_no_cache_row(self, world: World) -> None:
        _assert_hidden_like_missing(_view(world, world.b, world.pb, baseline_id=world.pa))
        _assert_hidden_like_missing(_view(world, world.b, world.pa))
        assert world.store.get_analysis(world.pb, f"schedule_view:{world.pa}:wbs") is None
        assert world.store.get_analysis(world.pa, self.KEY) is None


# ------------------------------------------------------------------ #
# Benchmarks                                                         #
# ------------------------------------------------------------------ #


class TestBenchmarks:
    def _contribute(self, w: World, headers: dict[str, str], pid: str) -> Any:
        return w.client.post(
            "/api/v1/benchmarks/contribute", params={"project_id": pid}, headers=headers
        )

    def test_foreign_contribution_adds_nothing(self, world: World) -> None:
        _ok(self._contribute(world, world.a, world.pa), "contribute as A")
        assert len(benchmarks._benchmark_dataset) == 1

        foreign = self._contribute(world, world.b, world.pa)
        missing = self._contribute(world, world.b, str(uuid.uuid4()))
        _assert_hidden_like_missing(foreign, missing)
        assert len(benchmarks._benchmark_dataset) == 1

    def test_summary_needs_no_project(self, world: World) -> None:
        _ok(self._contribute(world, world.a, world.pa), "contribute as A")
        resp = world.client.get("/api/v1/benchmarks/summary", headers=world.b)
        _ok(resp, "summary as B")
        assert resp.json()["total_projects"] == 1
