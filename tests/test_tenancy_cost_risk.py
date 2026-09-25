# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Cost snapshots and the risk register are owner-only, reads and writes (ADR-0030).

Routes covered:

* ``POST /api/v1/cost/upload`` (with ``project_id``), ``GET .../cost/snapshots``
  and ``GET .../cost/compare`` in ``src/api/routers/cost.py``;
* ``GET``/``POST``/``DELETE .../risk-register`` in ``src/api/routers/schedule_ops.py``;
* ``GET /api/v1/risk/simulations/{id}/register-entries`` in ``src/api/routers/risk.py``.

The harness follows ``tests/test_tenancy_analysis.py``: ``ENVIRONMENT=production``,
real HS256 JWTs and a fresh ``InMemoryStore`` wired into ``src.api.deps``,
never ``dependency_overrides``, so the whole auth -> principal -> access path
runs. Every positive control fails (never skips) if the owner is denied, and
every "hidden" answer is compared with the answer for ids that do not exist:
they must be identical, ``404 {"detail": "Project not found"}``.

For the writes, the victim's data is read back as the owner after the
attempt and must be unchanged; the upload is refused before the file is
read or parsed. The last part drives ``SupabaseStore`` with a recording fake
client and shows the owner filter is emitted before any cost row is read.
"""

from __future__ import annotations

import importlib.util
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

import src.api.deps as deps
from src.analytics import cost_integration
from src.analytics.cost_integration import CBSElement, CostIntegrationResult
from src.analytics.risk import SensitivityEntry, SimulationResult
from src.api import access, auth
from src.api.app import app
from src.api.routers import cost, risk, schedule_ops
from src.api.storage import RiskStore
from src.database import config
from src.database.store import InMemoryStore, SupabaseStore
from src.parser.xer_reader import XERReader

FIXTURES = Path(__file__).parent / "fixtures"
TEST_JWT_SECRET = "test-secret"  # tests/conftest.py sets SUPABASE_JWT_SECRET to this

USER_A = "00000000-0000-4000-8000-0000000000a1"
USER_B = "00000000-0000-4000-8000-0000000000b2"

NOT_FOUND = (404, {"detail": "Project not found"})
OPENPYXL = importlib.util.find_spec("openpyxl") is not None
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _token(sub: str) -> str:
    now = int(time.time())
    claims = {"sub": sub, "aud": "authenticated", "role": "authenticated", "iat": now}
    claims["exp"] = now + 3600
    return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256")


def _cbs(budget: float, source: str = "") -> CostIntegrationResult:
    return CostIntegrationResult(
        cbs_elements=[
            CBSElement(
                cbs_code="C.SP.100",
                cbs_level1="Construction",
                scope=f"Foundations {source}".strip(),
                estimate=budget,
                budget=budget,
            )
        ],
        total_budget=budget,
        program_total=budget,
    )


def _risk(name: str, risk_id: str = "R001") -> dict[str, Any]:
    return {
        "risk_id": risk_id,
        "name": name,
        "category": "schedule",
        "probability": 0.5,
        "impact_days": 10,
        "affected_activities": ["A100"],
    }


def _production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production auth: no anonymous development principal, invalid tokens are 401."""
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    # Every module that reads ENVIRONMENT must be reading that same object.
    assert vars(access)["settings"] is config.settings
    assert vars(auth)["settings"] is config.settings
    assert config.settings.SUPABASE_JWT_SECRET == TEST_JWT_SECRET


@dataclass
class World:
    client: TestClient
    store: InMemoryStore
    risk_store: RiskStore
    a: dict[str, str]  # auth headers of user A
    b: dict[str, str]  # auth headers of user B
    pa: str  # A's project
    pa2: str  # A's second project (positive controls that must not disturb pa)
    pb: str  # B's project
    p0: str  # a project with no recorded owner
    snapshots: dict[str, list[str]] = field(default_factory=dict)  # project -> its 2 snapshots
    reads: list[str] = field(default_factory=list)  # uploaded files read by a handler
    parses: list[str] = field(default_factory=list)  # CBS workbooks parsed
    register_reads: list[str] = field(default_factory=list)  # projects whose register was read


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> World:
    _production(monkeypatch)
    store = InMemoryStore()
    risk_store = RiskStore()
    monkeypatch.setattr(deps, "_store", store)
    monkeypatch.setattr(deps, "_risk_store", risk_store)
    assert deps.get_store() is store
    assert deps.get_risk_store() is risk_store

    def seed(owner: str | None) -> str:
        return str(store.add(XERReader(FIXTURES / "sample.xer").parse(), b"x", user_id=owner))

    w = World(
        client=TestClient(app),
        store=store,
        risk_store=risk_store,
        a={"Authorization": f"Bearer {_token(USER_A)}"},
        b={"Authorization": f"Bearer {_token(USER_B)}"},
        pa=seed(USER_A),
        pa2=seed(USER_A),
        pb=seed(USER_B),
        p0=seed(None),
    )
    assert store.get_project_owner(w.p0) == (True, None)
    for pid, owner in ((w.pa, USER_A), (w.pa2, USER_A), (w.pb, USER_B), (w.p0, None)):
        w.snapshots[pid] = [
            store.save_cost_upload(pid, _cbs(100_000.0, "v1"), user_id=owner, source_name="v1"),
            store.save_cost_upload(pid, _cbs(125_000.0, "v2"), user_id=owner, source_name="v2"),
        ]
        store.save_risk_entry(pid, _risk(f"risk of {owner}"), user_id=owner)

    # Instruments: who read an uploaded file, parsed a workbook, read a register.
    original_read = UploadFile.read

    async def spy_read(self: UploadFile, size: int = -1) -> bytes:
        w.reads.append(self.filename or "")
        return await original_read(self, size)

    monkeypatch.setattr(UploadFile, "read", spy_read)

    def fake_parse(file_path: str) -> CostIntegrationResult:
        w.parses.append(file_path)
        return _cbs(150_000.0, "uploaded")

    monkeypatch.setattr(cost_integration, "parse_cbs_excel", fake_parse)

    original_list = store.list_risk_entries

    def spy_list(project_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        w.register_reads.append(project_id)
        return original_list(project_id, user_id=user_id)

    monkeypatch.setattr(store, "list_risk_entries", spy_list)
    return w


def _ok(resp: Any, what: str) -> Any:
    """Positive control: the caller must get past the access check. Fails, never skips."""
    assert 200 <= resp.status_code < 300, f"denied on {what}: {resp.status_code} {resp.text}"
    return resp.json()


def _answer(resp: Any) -> tuple[int, Any]:
    return resp.status_code, resp.json()


def _assert_hidden_like_missing(foreign: Any, *missing: Any) -> None:
    assert _answer(foreign) == NOT_FOUND, foreign.text
    for other in missing:
        assert _answer(other) == NOT_FOUND, other.text


# ------------------------------------------------------------------ #
# Route table                                                        #
# ------------------------------------------------------------------ #


@dataclass(frozen=True)
class Route:
    method: str
    path: str  # "{pid}" is replaced by the project id under test
    kwargs: Callable[[World, str], dict[str, Any]] = lambda _w, _pid: {}

    @property
    def key(self) -> tuple[str, str]:
        """The route as FastAPI registers it."""
        path = self.path.replace("{pid}", "{project_id}").replace("/R001", "/{risk_id}")
        return self.method, path


def _upload(_w: World, pid: str) -> dict[str, Any]:
    return {
        "params": {"project_id": pid},
        "files": {"file": ("budget.xlsx", b"synthetic workbook bytes", XLSX)},
    }


def _compare(w: World, pid: str) -> dict[str, Any]:
    """The project's own two snapshots; for any other id, A's (what an attacker would send)."""
    a, b = w.snapshots.get(pid, w.snapshots[w.pa])
    return {"params": {"a": a, "b": b}}


ROUTES: dict[str, Route] = {
    "cost-upload": Route("POST", "/api/v1/cost/upload", _upload),
    "cost-snapshots": Route("GET", "/api/v1/projects/{pid}/cost/snapshots"),
    "cost-compare": Route("GET", "/api/v1/projects/{pid}/cost/compare", _compare),
    "risk-register-list": Route("GET", "/api/v1/projects/{pid}/risk-register"),
    "risk-register-add": Route(
        "POST",
        "/api/v1/projects/{pid}/risk-register",
        lambda _w, _pid: {"json": _risk("written by the caller")},
    ),
    "risk-register-delete": Route("DELETE", "/api/v1/projects/{pid}/risk-register/R001"),
}


def _call(w: World, route: Route, headers: dict[str, str] | None, pid: str) -> Any:
    return w.client.request(
        route.method, route.path.format(pid=pid), headers=headers, **route.kwargs(w, pid)
    )


def test_route_table_covers_this_slice() -> None:
    """Every route of the slice is in the table; the rest of these routers is covered elsewhere.

    Read each module's own router: from FastAPI 0.141, ``app.routes`` holds
    the included routers unflattened, so filtering it would find nothing.
    """
    slice_keys = {
        ("POST", "/api/v1/cost/upload"),
        ("GET", "/api/v1/projects/{project_id}/cost/snapshots"),
        ("GET", "/api/v1/projects/{project_id}/cost/compare"),
        ("GET", "/api/v1/projects/{project_id}/risk-register"),
        ("POST", "/api/v1/projects/{project_id}/risk-register"),
        ("DELETE", "/api/v1/projects/{project_id}/risk-register/{risk_id}"),
    }
    registered = {
        (method, r.path)
        for module in (cost, schedule_ops, risk)
        for r in module.router.routes
        if isinstance(r, APIRoute)
        for method in r.methods
    }
    assert slice_keys <= registered, f"stale: {sorted(slice_keys - registered)}"
    assert ("GET", "/api/v1/risk/simulations/{simulation_id}/register-entries") in registered
    assert {r.key for r in ROUTES.values()} == slice_keys


# ------------------------------------------------------------------ #
# Every route: owner reaches it, the other tenant gets "not found"   #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize("name", list(ROUTES))
class TestEveryRoute:
    def test_anonymous_is_rejected(self, world: World, name: str) -> None:
        """Negative control for the harness: production auth really is on."""
        resp = _call(world, ROUTES[name], None, world.pa)
        assert resp.status_code == 401, resp.text

    def test_owner_reaches_own_project(self, world: World, name: str) -> None:
        _ok(_call(world, ROUTES[name], world.a, world.pa), f"{name} as A")

    def test_other_tenant_reaches_own_project(self, world: World, name: str) -> None:
        """B's token works, so B's 404 on A's project is the access rule, not a broken B."""
        _ok(_call(world, ROUTES[name], world.b, world.pb), f"{name} as B")

    def test_other_tenant_gets_not_found_identical_to_missing(
        self, world: World, name: str
    ) -> None:
        route = ROUTES[name]
        _ok(_call(world, route, world.a, world.pa2), f"{name} as A")

        foreign = _call(world, route, world.b, world.pa)
        random_uuid = _call(world, route, world.b, str(uuid.uuid4()))
        legacy_style = _call(world, route, world.b, "proj-9999")
        _assert_hidden_like_missing(foreign, random_uuid, legacy_style)

    def test_ownerless_project_is_hidden_from_users(self, world: World, name: str) -> None:
        """Separates the access check from the stores' own filters.

        Both in-memory filters let an ownerless project's rows through to
        any user, so this is the case only the access context can refuse.
        """
        assert world.store.list_cost_snapshots(world.p0, user_id=USER_A)
        assert world.store.list_risk_entries(world.p0, user_id=USER_A)
        ownerless = _call(world, ROUTES[name], world.a, world.p0)
        missing = _call(world, ROUTES[name], world.a, str(uuid.uuid4()))
        _assert_hidden_like_missing(ownerless, missing)


# ------------------------------------------------------------------ #
# Writes: the victim's data is unchanged after the attempt           #
# ------------------------------------------------------------------ #


def _snapshot_ids(w: World, headers: dict[str, str], pid: str) -> list[str]:
    body = _ok(w.client.get(f"/api/v1/projects/{pid}/cost/snapshots", headers=headers), "list")
    return [s["snapshot_id"] for s in body["snapshots"]]


def _register(w: World, headers: dict[str, str], pid: str) -> list[dict[str, Any]]:
    body = _ok(w.client.get(f"/api/v1/projects/{pid}/risk-register", headers=headers), "reg")
    entries: list[dict[str, Any]] = body["entries"]
    return entries


class TestCostUpload:
    def test_foreign_upload_is_refused_before_the_file_is_read(self, world: World) -> None:
        w = world
        before = _snapshot_ids(w, w.a, w.pa)

        foreign = _call(w, ROUTES["cost-upload"], w.b, w.pa)
        assert _answer(foreign) == NOT_FOUND
        assert w.reads == [] and w.parses == []
        assert _snapshot_ids(w, w.a, w.pa) == before

        # Control: the same request from the owner reads, parses and stores,
        # so the empty spies above are the refusal and not a dead instrument.
        own = _ok(_call(w, ROUTES["cost-upload"], w.a, w.pa), "upload as A")
        assert w.reads == ["budget.xlsx"] and len(w.parses) == 1
        assert _snapshot_ids(w, w.a, w.pa) == [own["snapshot_id"], *before]

    def test_upload_without_project_parses_and_stores_nothing(self, world: World) -> None:
        w = world
        counts = {pid: len(w.store.list_cost_snapshots(pid)) for pid in w.snapshots}
        files = {"file": ("budget.xlsx", b"synthetic workbook bytes", XLSX)}
        body = _ok(w.client.post("/api/v1/cost/upload", files=files, headers=w.b), "parse only")
        assert body["snapshot_id"] == "" and body["project_id"] is None
        assert {pid: len(w.store.list_cost_snapshots(pid)) for pid in w.snapshots} == counts

    def test_uploaded_snapshot_is_listed_only_for_its_project(self, world: World) -> None:
        w = world
        own = _ok(_call(w, ROUTES["cost-upload"], w.a, w.pa), "upload as A")
        assert own["snapshot_id"] in _snapshot_ids(w, w.a, w.pa)
        assert own["snapshot_id"] not in _snapshot_ids(w, w.a, w.pa2)
        assert own["snapshot_id"] not in _snapshot_ids(w, w.b, w.pb)


class TestRiskRegisterWrites:
    def test_foreign_add_leaves_victim_unchanged(self, world: World) -> None:
        w = world
        before = _register(w, w.a, w.pa)
        assert [e["name"] for e in before] == [f"risk of {USER_A}"]

        for body in (_risk("overwritten", "R001"), {"name": "planted"}):
            url = f"/api/v1/projects/{w.pa}/risk-register"
            assert _answer(w.client.post(url, json=body, headers=w.b)) == NOT_FOUND
        assert _register(w, w.a, w.pa) == before

        # Control: the owner's own upsert does change it.
        _ok(
            w.client.post(
                f"/api/v1/projects/{w.pa}/risk-register",
                json=_risk("revised", "R001"),
                headers=w.a,
            ),
            "upsert as A",
        )
        assert [e["name"] for e in _register(w, w.a, w.pa)] == ["revised"]

    def test_foreign_delete_leaves_victim_unchanged(self, world: World) -> None:
        w = world
        before = _register(w, w.a, w.pa)
        url = f"/api/v1/projects/{w.pa}/risk-register/R001"
        assert _answer(w.client.delete(url, headers=w.b)) == NOT_FOUND
        assert _register(w, w.a, w.pa) == before

        # Control: the owner's delete removes it.
        _ok(w.client.delete(url, headers=w.a), "delete as A")
        assert _register(w, w.a, w.pa) == []

    def test_other_tenant_write_to_own_project_touches_nothing_else(self, world: World) -> None:
        w = world
        before = _register(w, w.a, w.pa)
        _ok(
            w.client.post(
                f"/api/v1/projects/{w.pb}/risk-register", json=_risk("B's", "R001"), headers=w.b
            ),
            "upsert as B",
        )
        assert _register(w, w.a, w.pa) == before


class TestInMemoryRiskUpsert:
    """Store level: an entry recorded for another user is never replaced or removed."""

    def test_upsert_never_replaces_another_users_entry(self) -> None:
        store = InMemoryStore()
        store.save_risk_entry("p", _risk("A's"), user_id=USER_A)
        store.save_risk_entry("p", _risk("B's"), user_id=USER_B)

        assert [e["name"] for e in store.list_risk_entries("p", user_id=USER_A)] == ["A's"]
        assert [e["name"] for e in store.list_risk_entries("p", user_id=USER_B)] == ["B's"]

        assert store.delete_risk_entry("p", "R001", user_id=USER_B) is True
        assert [e["name"] for e in store.list_risk_entries("p", user_id=USER_A)] == ["A's"]
        assert store.delete_risk_entry("p", "R001", user_id=USER_B) is False

        # Control: the owner's own upsert replaces in place.
        store.save_risk_entry("p", _risk("A's, revised"), user_id=USER_A)
        assert [e["name"] for e in store.list_risk_entries("p", user_id=USER_A)] == ["A's, revised"]

    def test_auto_assigned_id_never_reuses_a_held_id(self) -> None:
        store = InMemoryStore()
        store.save_risk_entry("p", _risk("first", "R001"), user_id=USER_A)
        store.save_risk_entry("p", _risk("second", "R002"), user_id=USER_A)
        assert store.delete_risk_entry("p", "R001", user_id=USER_A) is True

        new = store.save_risk_entry("p", {"name": "third"}, user_id=USER_A)
        assert new["risk_id"] == "R003"
        names = {e["risk_id"]: e["name"] for e in store.list_risk_entries("p", user_id=USER_A)}
        assert names == {"R002": "second", "R003": "third"}

    def test_body_cannot_forge_owner_or_project(self) -> None:
        store = InMemoryStore()
        forged = {**_risk("forged"), "user_id": USER_B, "project_id": "other"}
        stored = store.save_risk_entry("p", forged, user_id=USER_A)
        assert (stored["user_id"], stored["project_id"]) == (USER_A, "p")


# ------------------------------------------------------------------ #
# Snapshot ids resolve only inside the authorized project            #
# ------------------------------------------------------------------ #


def _compare_ids(w: World, headers: dict[str, str], pid: str, a: str, b: str) -> Any:
    return w.client.get(
        f"/api/v1/projects/{pid}/cost/compare", params={"a": a, "b": b}, headers=headers
    )


class TestSnapshotIds:
    def test_owner_compares_own_snapshots(self, world: World) -> None:
        a, b = world.snapshots[world.pa]
        body = _ok(_compare_ids(world, world.a, world.pa, a, b), "compare as A")
        assert (body["snapshot_a"], body["snapshot_b"]) == (a, b)
        assert body["total_budget_delta"] == 25_000.0

    @pytest.mark.parametrize("position", ["a", "b"])
    def test_foreign_snapshot_on_own_project_is_not_found(
        self, world: World, position: str
    ) -> None:
        w = world
        own, _ = w.snapshots[w.pb]
        foreign_id = w.snapshots[w.pa][0]
        random_id = f"cost-{uuid.uuid4().hex}"

        def ask(other: str) -> Any:
            pair = (own, other) if position == "b" else (other, own)
            return _compare_ids(w, w.b, w.pb, *pair)

        foreign, missing = ask(foreign_id), ask(random_id)
        prefix = "Snapshot(s) not found for this project: "
        assert _answer(foreign) == (404, {"detail": prefix + foreign_id})
        assert _answer(missing) == (404, {"detail": prefix + random_id})

    def test_snapshot_of_another_own_project_is_not_found(self, world: World) -> None:
        """A snapshot id is scoped to its project even for the same owner."""
        w = world
        resp = _compare_ids(w, w.a, w.pa, w.snapshots[w.pa][0], w.snapshots[w.pa2][0])
        assert resp.status_code == 404

    def test_list_holds_only_the_projects_snapshots(self, world: World) -> None:
        w = world
        assert _snapshot_ids(w, w.a, w.pa) == list(reversed(w.snapshots[w.pa]))
        assert _snapshot_ids(w, w.b, w.pb) == list(reversed(w.snapshots[w.pb]))

    def test_aia_g703_resolves_snapshots_only_inside_the_project(self, world: World) -> None:
        """The export shares ``get_cost_snapshot``; it stays scoped after the store change."""
        w = world
        url = f"/api/v1/projects/{w.pb}/export/aia-g703"
        own = w.client.get(url, params={"snapshot_id": w.snapshots[w.pb][0]}, headers=w.b)
        if OPENPYXL:
            assert own.status_code == 200, own.text
        else:  # 501 comes only after the project and snapshot were accepted
            assert own.status_code == 501 and "openpyxl" in own.json()["detail"]

        foreign_id = w.snapshots[w.pa][0]
        foreign = w.client.get(url, params={"snapshot_id": foreign_id}, headers=w.b)
        assert _answer(foreign) == (404, {"detail": f"CBS snapshot not retrievable: {foreign_id}"})

    def test_store_owner_gate(self, world: World) -> None:
        """InMemoryStore: with ``user_id``, another owner's project yields nothing."""
        s, snap = world.store, world.snapshots[world.pa][0]
        assert s.get_cost_snapshot(world.pa, snap, user_id=USER_A) is not None
        assert s.get_cost_snapshot(world.pa, snap, user_id=USER_B) is None
        assert s.get_cost_snapshot(world.pb, snap, user_id=USER_B) is None
        assert s.list_cost_snapshots(world.pa, user_id=USER_B) == []
        assert len(s.list_cost_snapshots(world.pa, user_id=USER_A)) == 2


# ------------------------------------------------------------------ #
# Simulation register entries: the simulation's project is checked  #
# ------------------------------------------------------------------ #


def _simulation(project_id: str) -> SimulationResult:
    return SimulationResult(
        project_id=project_id,
        project_name="Synthetic",
        iterations=10,
        sensitivity=[SensitivityEntry(activity_id="A100", activity_name="Foundation")],
    )


def _register_entries(w: World, headers: dict[str, str], sid: str) -> Any:
    return w.client.get(f"/api/v1/risk/simulations/{sid}/register-entries", headers=headers)


class TestSimulationRegisterEntries:
    def test_owner_sees_entries_linked_to_own_simulation(self, world: World) -> None:
        w = world
        sid = w.risk_store.add(_simulation(w.pa), owner_id=USER_A, project_ids=[w.pa])
        body = _ok(_register_entries(w, w.a, sid), "register-entries as A")
        assert [e["name"] for e in body["entries"]] == [f"risk of {USER_A}"]
        assert w.register_reads == [w.pa]

    def test_simulation_on_an_unreachable_project_reads_no_register(self, world: World) -> None:
        """Owning the simulation is not enough: its project is authorized too.

        B holds a simulation that names A's project (no route creates one,
        which is exactly why the route must not trust it). B gets the same
        answer as for a simulation whose project does not exist, and A's
        register is never read.
        """
        w = world
        foreign = w.risk_store.add(_simulation(w.pa), owner_id=USER_B, project_ids=[w.pa])
        missing_pid = str(uuid.uuid4())
        missing = w.risk_store.add(_simulation(missing_pid), owner_id=USER_B, project_ids=[])
        ownerless = w.risk_store.add(_simulation(w.p0), owner_id=USER_B, project_ids=[w.p0])

        _assert_hidden_like_missing(
            _register_entries(w, w.b, foreign),
            _register_entries(w, w.b, missing),
            _register_entries(w, w.b, ownerless),
        )
        assert w.register_reads == []

        # Control: B's simulation on B's own project does read B's register.
        own = w.risk_store.add(_simulation(w.pb), owner_id=USER_B, project_ids=[w.pb])
        _ok(_register_entries(w, w.b, own), "register-entries as B")
        assert w.register_reads == [w.pb]


# ------------------------------------------------------------------ #
# SupabaseStore: the owner filter is actually emitted                #
# ------------------------------------------------------------------ #

PA = "11111111-1111-4111-8111-1111111111a1"
PB = "11111111-1111-4111-8111-1111111111b2"
SRC_A = "22222222-2222-4222-8222-2222222222a1"


class _Query:
    """One ``client.table(...)`` chain: records its filters, answers from the tables."""

    def __init__(self, client: _FakeClient, table: str) -> None:
        self._client = client
        self._table = table
        self._op = "select"
        self._filters: list[tuple[str, Any]] = []
        self._payload: Any = None

    def select(self, _columns: str) -> _Query:
        return self

    def eq(self, column: str, value: Any) -> _Query:
        self._filters.append((column, value))
        return self

    def insert(self, payload: Any) -> _Query:
        self._op, self._payload = "insert", payload
        return self

    def execute(self) -> Any:
        self._client.log.append((self._table, self._op, tuple(self._filters)))
        rows = self._client.tables.setdefault(self._table, [])
        if self._op == "insert":
            new = self._payload if isinstance(self._payload, list) else [self._payload]
            added = [{"id": str(uuid.uuid4()), **r} for r in new]
            rows.extend(added)
            return SimpleNamespace(data=added)
        return SimpleNamespace(
            data=[r for r in rows if all(r.get(c) == v for c, v in self._filters)]
        )


class _FakeClient:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = tables
        self.log: list[tuple[str, str, tuple[tuple[str, Any], ...]]] = []

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    def touched(self, *tables: str) -> list[tuple[str, str, tuple[tuple[str, Any], ...]]]:
        return [entry for entry in self.log if entry[0] in tables]


def _tables() -> dict[str, list[dict[str, Any]]]:
    return {
        "projects": [{"id": PA, "user_id": USER_A}, {"id": PB, "user_id": USER_B}],
        "erp_sources": [
            {"id": SRC_A, "project_id": PA, "display_name": "v1", "last_sync_at": "2026-09-01"}
        ],
        "cbs_elements": [
            {
                "id": "el-1",
                "project_id": PA,
                "erp_source_id": SRC_A,
                "cbs_code": "C.SP.100",
                "cbs_description": "Foundations",
                "cbs_level": 1,
                "sort_order": 0,
            }
        ],
        "cost_snapshots": [
            {
                "project_id": PA,
                "erp_source_id": SRC_A,
                "cbs_element_id": "el-1",
                "snapshot_date": "2026-09-01",
                "original_budget": 100.0,
                "current_budget": 100.0,
            }
        ],
    }


def _supabase_store(client: _FakeClient) -> SupabaseStore:
    store = SupabaseStore.__new__(SupabaseStore)
    store._client = client  # type: ignore[assignment]
    store._analyses = {}
    store._comparisons = {}
    return store


COST_TABLES = ("erp_sources", "cbs_elements", "cost_snapshots")


class TestSupabaseStoreOwnerFilter:
    def test_list_emits_the_owner_filter_before_any_cost_row(self) -> None:
        client = _FakeClient(_tables())
        listed = _supabase_store(client).list_cost_snapshots(PA, user_id=USER_A)
        assert [s["snapshot_id"] for s in listed] == [SRC_A]
        assert client.log == [
            ("projects", "select", (("id", PA), ("user_id", USER_A))),
            ("erp_sources", "select", (("project_id", PA),)),
        ]

    def test_list_for_a_non_owner_reads_no_cost_row(self) -> None:
        client = _FakeClient(_tables())
        assert _supabase_store(client).list_cost_snapshots(PA, user_id=USER_B) == []
        assert client.log == [("projects", "select", (("id", PA), ("user_id", USER_B)))]

    def test_get_scopes_every_query_to_the_owned_project(self) -> None:
        client = _FakeClient(_tables())
        result = _supabase_store(client).get_cost_snapshot(PA, SRC_A, user_id=USER_A)
        assert result is not None and result.total_budget == 100.0
        assert client.log == [
            ("projects", "select", (("id", PA), ("user_id", USER_A))),
            ("erp_sources", "select", (("id", SRC_A), ("project_id", PA))),
            ("cbs_elements", "select", (("erp_source_id", SRC_A), ("project_id", PA))),
            ("cost_snapshots", "select", (("erp_source_id", SRC_A), ("project_id", PA))),
        ]

    def test_get_for_a_non_owner_reads_no_cost_row(self) -> None:
        client = _FakeClient(_tables())
        assert _supabase_store(client).get_cost_snapshot(PA, SRC_A, user_id=USER_B) is None
        assert client.touched(*COST_TABLES) == []

    def test_snapshot_of_another_project_is_not_found(self) -> None:
        client = _FakeClient(_tables())
        assert _supabase_store(client).get_cost_snapshot(PB, SRC_A, user_id=USER_B) is None
        assert client.touched("cbs_elements", "cost_snapshots") == []

    def test_instrument_can_see_a_missing_owner_filter(self) -> None:
        """Negative control: an unscoped call emits no projects query, and the log shows it."""
        client = _FakeClient(_tables())
        assert len(_supabase_store(client).list_cost_snapshots(PA)) == 1
        assert client.touched("projects") == []


@dataclass
class SupabaseWorld:
    client: TestClient
    db: _FakeClient
    a: dict[str, str]
    b: dict[str, str]
    parses: list[str]


@pytest.fixture
def supabase_world(monkeypatch: pytest.MonkeyPatch) -> SupabaseWorld:
    _production(monkeypatch)
    db = _FakeClient(_tables())
    store = _supabase_store(db)
    monkeypatch.setattr(deps, "_store", store)
    assert deps.get_store() is store
    parses: list[str] = []

    def fake_parse(file_path: str) -> CostIntegrationResult:
        parses.append(file_path)
        return _cbs(150_000.0, "uploaded")

    monkeypatch.setattr(cost_integration, "parse_cbs_excel", fake_parse)
    return SupabaseWorld(
        client=TestClient(app),
        db=db,
        a={"Authorization": f"Bearer {_token(USER_A)}"},
        b={"Authorization": f"Bearer {_token(USER_B)}"},
        parses=parses,
    )


class TestThroughSupabaseStore:
    """The routes end to end on ``SupabaseStore`` (fake client), as production runs them."""

    def test_snapshots_owner_filter_reaches_the_query(self, supabase_world: SupabaseWorld) -> None:
        w = supabase_world
        body = _ok(w.client.get(f"/api/v1/projects/{PA}/cost/snapshots", headers=w.a), "list")
        assert [s["snapshot_id"] for s in body["snapshots"]] == [SRC_A]
        assert ("projects", "select", (("id", PA), ("user_id", USER_A))) in w.db.log

    def test_snapshots_for_another_tenant_read_no_cost_row(
        self, supabase_world: SupabaseWorld
    ) -> None:
        w = supabase_world
        foreign = w.client.get(f"/api/v1/projects/{PA}/cost/snapshots", headers=w.b)
        missing = w.client.get(f"/api/v1/projects/{uuid.uuid4()}/cost/snapshots", headers=w.b)
        _assert_hidden_like_missing(foreign, missing)
        assert w.db.touched(*COST_TABLES) == []

    def test_foreign_upload_inserts_nothing(self, supabase_world: SupabaseWorld) -> None:
        w = supabase_world
        files = {"file": ("budget.xlsx", b"synthetic workbook bytes", XLSX)}
        before = {t: list(w.db.tables.get(t, [])) for t in COST_TABLES}

        foreign = w.client.post(
            "/api/v1/cost/upload", params={"project_id": PA}, files=files, headers=w.b
        )
        assert _answer(foreign) == NOT_FOUND
        assert [e for e in w.db.log if e[1] == "insert"] == [] and w.parses == []
        assert {t: w.db.tables.get(t, []) for t in COST_TABLES} == before

        # Control: the owner's upload writes, under the owner's project.
        own = w.client.post(
            "/api/v1/cost/upload", params={"project_id": PA}, files=files, headers=w.a
        )
        snapshot_id = _ok(own, "upload as A")["snapshot_id"]
        inserted = [r for r in w.db.tables["erp_sources"] if r["id"] == snapshot_id]
        assert [r["project_id"] for r in inserted] == [PA]

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("POST", f"/api/v1/projects/{PA}/risk-register"),
            ("DELETE", f"/api/v1/projects/{PA}/risk-register/R001"),
        ],
    )
    def test_register_writes_stay_501_for_the_owner_only(
        self, supabase_world: SupabaseWorld, method: str, path: str
    ) -> None:
        w = supabase_world
        kwargs: dict[str, Any] = {"json": _risk("x")} if method == "POST" else {}
        own = w.client.request(method, path, headers=w.a, **kwargs)
        assert own.status_code == 501, own.text

        foreign = w.client.request(method, path, headers=w.b, **kwargs)
        missing = w.client.request(
            method, path.replace(PA, str(uuid.uuid4())), headers=w.b, **kwargs
        )
        _assert_hidden_like_missing(foreign, missing)

    def test_register_list_is_empty_for_the_owner_only(self, supabase_world: SupabaseWorld) -> None:
        w = supabase_world
        own = _ok(w.client.get(f"/api/v1/projects/{PA}/risk-register", headers=w.a), "list")
        assert own["entries"] == []
        foreign = w.client.get(f"/api/v1/projects/{PA}/risk-register", headers=w.b)
        _assert_hidden_like_missing(foreign)
