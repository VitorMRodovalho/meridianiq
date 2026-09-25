# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Owned result stores (ADR-0030 §5): results are listed and read only by their owner.

Two layers:

* unit tests of ``OwnedResultStore`` and the five stores built on it;
* two-tenant API tests over every route that creates or reads a stored
  result. They run with ``ENVIRONMENT=production`` and real HS256 JWTs,
  never ``dependency_overrides``, so the whole auth -> principal -> access
  path is exercised. Each test first has user A create the resource and
  asserts a 2xx: that positive control must fail, never skip, if A is
  denied. User B then gets the not-found answer, identical to a random id.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

import src.api.deps as deps
from src.analytics.evm import EVMAnalysisResult
from src.analytics.forensics import ForensicTimeline
from src.analytics.report_generator import ReportGenerator
from src.analytics.risk import SimulationResult
from src.analytics.tia import TIAAnalysis
from src.api import access, auth
from src.api.app import app
from src.api.storage import (
    REPORTS_PER_OWNER,
    EVMStore,
    OwnedResultStore,
    ReportStore,
    RiskStore,
    TIAStore,
    TimelineStore,
)
from src.database import config
from src.database.store import InMemoryStore
from src.parser.xer_reader import XERReader

FIXTURES = Path(__file__).parent / "fixtures"
TEST_JWT_SECRET = "test-secret"  # tests/conftest.py sets SUPABASE_JWT_SECRET to this

USER_A = "00000000-0000-4000-8000-0000000000a1"
USER_B = "00000000-0000-4000-8000-0000000000b2"


# ------------------------------------------------------------------ #
# Unit: the generic store                                            #
# ------------------------------------------------------------------ #


def _values() -> list[tuple[type[OwnedResultStore[Any]], str, Any]]:
    """One (store class, id prefix, fresh value factory) per result store."""
    return [
        (TimelineStore, "timeline", lambda: ForensicTimeline(timeline_id="")),
        (TIAStore, "tia", lambda: TIAAnalysis(analysis_id="", project_name="", base_project_id="")),
        (EVMStore, "evm", EVMAnalysisResult),
        (RiskStore, "risk", SimulationResult),
        (ReportStore, "report", lambda: {"bytes": b"%PDF-1.4", "report_type": "health"}),
    ]


@pytest.mark.parametrize(("store_cls", "prefix", "make"), _values())
class TestEveryResultStore:
    def test_ids_are_prefix_plus_uuid_hex(
        self, store_cls: type[OwnedResultStore[Any]], prefix: str, make: Any
    ) -> None:
        store = store_cls()
        first = store.add(make(), owner_id="a", project_ids=["p1"])
        second = store.add(make(), owner_id="a", project_ids=["p1"])
        assert re.fullmatch(rf"{prefix}-[0-9a-f]{{32}}", first)
        assert re.fullmatch(rf"{prefix}-[0-9a-f]{{32}}", second)
        assert first != second

    def test_only_the_owner_reads_lists_and_summarises(
        self, store_cls: type[OwnedResultStore[Any]], prefix: str, make: Any
    ) -> None:
        store = store_cls()
        a_value = make()
        a_id = store.add(a_value, owner_id="a", project_ids=["p1"])
        b_id = store.add(make(), owner_id="b", project_ids=["p1"])

        assert store.get(a_id, owner_id="a") is a_value
        assert store.get(a_id, owner_id="b") is None
        assert store.get(a_id, owner_id="") is None
        assert store.list("a") == [a_value]
        assert len(store.list("b")) == 1
        assert store.list("nobody") == []
        assert len(store.summaries("a")) == 1
        assert b_id not in str(store.summaries("a"))

    def test_owner_is_keyword_only_and_required(
        self, store_cls: type[OwnedResultStore[Any]], prefix: str, make: Any
    ) -> None:
        store = store_cls()
        with pytest.raises(TypeError):
            store.add(make())  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            store.add(make(), "a", ["p1"])  # type: ignore[misc]
        with pytest.raises(TypeError):
            store.get("x")  # type: ignore[call-arg]
        with pytest.raises(ValueError):
            store.add(make(), owner_id="", project_ids=["p1"])
        with pytest.raises(TypeError):
            store.add(make(), owner_id="a", project_ids="p1")


class TestOwnedResultStore:
    def test_project_filter_and_latest(self) -> None:
        store = RiskStore()
        first = SimulationResult(project_name="first")
        second = SimulationResult(project_name="second")
        other = SimulationResult(project_name="other project")
        store.add(first, owner_id="a", project_ids=["p1"])
        store.add(other, owner_id="a", project_ids=["p2"])
        store.add(second, owner_id="a", project_ids=["p1", "p3"])
        store.add(SimulationResult(), owner_id="b", project_ids=["p1"])

        assert store.list("a", "p1") == [first, second]
        assert store.list("a", "p3") == [second]
        assert store.latest("a", "p1") is second
        assert store.latest("a", "p2") is other
        assert store.latest("a", "p9") is None
        assert len(store.list("b", "p1")) == 1

    def test_report_cap_evicts_only_that_owners_oldest(self) -> None:
        store = ReportStore()
        b_id = store.add({"bytes": b"b"}, owner_id="b", project_ids=["pb"])
        a_ids = [
            store.add({"bytes": b"a", "n": n}, owner_id="a", project_ids=["pa"])
            for n in range(REPORTS_PER_OWNER + 3)
        ]
        assert len(store.list("a")) == REPORTS_PER_OWNER
        for evicted in a_ids[:3]:
            assert store.get(evicted, owner_id="a") is None
        assert store.get(a_ids[3], owner_id="a") is not None
        assert store.get(a_ids[-1], owner_id="a") is not None
        assert store.get(b_id, owner_id="b") is not None

    def test_purge_owner_removes_results_and_job_bindings(self) -> None:
        store = RiskStore()
        a_sid = store.add(SimulationResult(), owner_id="a", project_ids=["pa"])
        b_sid = store.add(SimulationResult(), owner_id="b", project_ids=["pb"])
        store.bind_job("job-a", a_sid)
        store.bind_job("job-b", b_sid)

        assert store.purge_owner("a") == 1
        assert store.get(a_sid, owner_id="a") is None
        assert store.get_simulation_id_by_job("job-a", owner_id="a") is None
        assert store.get(b_sid, owner_id="b") is not None
        assert store.get_simulation_id_by_job("job-b", owner_id="b") == b_sid

    def test_job_lookup_answers_only_the_owner(self) -> None:
        store = RiskStore()
        sid = store.add(SimulationResult(), owner_id="a", project_ids=["pa"])
        store.bind_job("job-a", sid)
        assert store.get_simulation_id_by_job("job-a", owner_id="a") == sid
        assert store.get_simulation_id_by_job("job-a", owner_id="b") is None


# ------------------------------------------------------------------ #
# API: two tenants, production auth, real JWTs                       #
# ------------------------------------------------------------------ #


def _token(sub: str) -> str:
    now = int(time.time())
    claims = {"sub": sub, "aud": "authenticated", "role": "authenticated", "iat": now}
    claims["exp"] = now + 3600
    return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256")


@dataclass
class World:
    client: TestClient
    a: dict[str, str]  # auth headers of user A
    b: dict[str, str]  # auth headers of user B
    pa: str  # A's project (sample.xer)
    pa2: str  # A's second project (sample_update.xer)
    pb: str  # B's project (sample.xer)


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
    monkeypatch.setattr(deps, "_tia_store", TIAStore())
    monkeypatch.setattr(deps, "_evm_store", EVMStore())
    monkeypatch.setattr(deps, "_risk_store", RiskStore())
    monkeypatch.setattr(deps, "_report_store", ReportStore())
    assert deps.get_store() is store

    def seed(name: str, owner: str) -> str:
        return str(store.add(XERReader(FIXTURES / name).parse(), b"x", user_id=owner))

    return World(
        client=TestClient(app),
        a={"Authorization": f"Bearer {_token(USER_A)}"},
        b={"Authorization": f"Bearer {_token(USER_B)}"},
        pa=seed("sample.xer", USER_A),
        pa2=seed("sample_update.xer", USER_A),
        pb=seed("sample.xer", USER_B),
    )


def _ok(resp: Any, what: str) -> Any:
    """Positive control: the owner must succeed. Fails (never skips) otherwise."""
    assert 200 <= resp.status_code < 300, f"owner denied on {what}: {resp.status_code} {resp.text}"
    return (
        resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None
    )


def _answer(resp: Any) -> tuple[int, Any]:
    return resp.status_code, resp.json()


def _assert_hidden_like_missing(w: World, template: str, owned_id: str, prefix: str) -> None:
    """B reading A's id answers exactly like a random id and a legacy sequential id."""
    foreign = w.client.get(template.format(id=owned_id), headers=w.b)
    random_id = w.client.get(template.format(id=f"{prefix}-{uuid.uuid4().hex}"), headers=w.b)
    legacy = w.client.get(template.format(id=f"{prefix}-0001"), headers=w.b)
    assert foreign.status_code == 404, foreign.text
    assert _answer(foreign) == _answer(random_id) == _answer(legacy)


def _run_simulation(w: World, headers: dict[str, str], project_id: str, job_id: str = "") -> Any:
    body = {"config": {"iterations": 50, "seed": 7}, "duration_risks": [], "risk_events": []}
    suffix = f"?job_id={job_id}" if job_id else ""
    return w.client.post(f"/api/v1/risk/simulate/{project_id}{suffix}", json=body, headers=headers)


def _fragment() -> dict[str, Any]:
    return {
        "fragment_id": "FRAG-1",
        "name": "Synthetic delay",
        "description": "Synthetic fragment",
        "responsible_party": "owner",
        "activities": [
            {
                "fragment_activity_id": "FRAG-1-A",
                "name": "Delay Activity",
                "duration_hours": 80.0,
                "predecessors": [{"activity_code": "A3050", "rel_type": "FS", "lag_hours": 0}],
                "successors": [{"activity_code": "A4010", "rel_type": "FS", "lag_hours": 0}],
            }
        ],
    }


class TestInstrumentIsArmed:
    """Negative control for the harness itself: production auth really is on."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/risk/simulations",
            "/api/v1/evm/analyses",
            "/api/v1/tia/analyses",
            "/api/v1/forensic/timelines",
        ],
    )
    def test_anonymous_is_rejected(self, world: World, path: str) -> None:
        assert world.client.get(path).status_code == 401


class TestRiskRoutes:
    READS = [
        "/api/v1/risk/simulations/{id}",
        "/api/v1/risk/simulations/{id}/histogram",
        "/api/v1/risk/simulations/{id}/tornado",
        "/api/v1/risk/simulations/{id}/criticality",
        "/api/v1/risk/simulations/{id}/s-curve",
        "/api/v1/risk/simulations/{id}/register-entries",
    ]

    def test_other_tenant_cannot_simulate_on_foreign_project(self, world: World) -> None:
        _ok(_run_simulation(world, world.a, world.pa), "simulate")
        foreign = _run_simulation(world, world.b, world.pa)
        missing = _run_simulation(world, world.b, "proj-9999")
        assert foreign.status_code == 404
        assert _answer(foreign) == _answer(missing)

    def test_list_holds_only_the_callers_simulations(self, world: World) -> None:
        sid = _ok(_run_simulation(world, world.a, world.pa), "simulate")["simulation_id"]
        b_sid = _ok(_run_simulation(world, world.b, world.pb), "simulate as B")["simulation_id"]

        a_list = _ok(world.client.get("/api/v1/risk/simulations", headers=world.a), "list")
        b_list = _ok(world.client.get("/api/v1/risk/simulations", headers=world.b), "list")
        assert [s["simulation_id"] for s in a_list["simulations"]] == [sid]
        assert [s["simulation_id"] for s in b_list["simulations"]] == [b_sid]

    @pytest.mark.parametrize("template", READS)
    def test_reads_by_id(self, world: World, template: str) -> None:
        sid = _ok(_run_simulation(world, world.a, world.pa), "simulate")["simulation_id"]
        assert re.fullmatch(r"risk-[0-9a-f]{32}", sid)
        _ok(world.client.get(template.format(id=sid), headers=world.a), template)
        _assert_hidden_like_missing(world, template, sid, "risk")

    def test_by_job_answers_null_to_another_tenant(self, world: World) -> None:
        job_id = f"job-{uuid.uuid4().hex}"
        sid = _ok(_run_simulation(world, world.a, world.pa, job_id), "simulate")["simulation_id"]
        path = f"/api/v1/risk/simulations/by-job/{job_id}"

        assert _ok(world.client.get(path, headers=world.a), "by-job") == {"simulation_id": sid}
        other = world.client.get(path, headers=world.b)
        assert other.status_code == 200
        assert other.json() == {"simulation_id": None}


class TestEVMRoutes:
    READS = [
        "/api/v1/evm/analyses/{id}",
        "/api/v1/evm/analyses/{id}/s-curve",
        "/api/v1/evm/analyses/{id}/wbs-drill",
        "/api/v1/evm/analyses/{id}/forecast",
    ]

    def _analyze(self, w: World, headers: dict[str, str], project_id: str) -> Any:
        return w.client.post(f"/api/v1/evm/analyze/{project_id}", headers=headers)

    def test_other_tenant_cannot_analyze_foreign_project(self, world: World) -> None:
        _ok(self._analyze(world, world.a, world.pa), "analyze")
        foreign = self._analyze(world, world.b, world.pa)
        assert foreign.status_code == 404
        assert _answer(foreign) == _answer(self._analyze(world, world.b, "proj-9999"))

    def test_list_holds_only_the_callers_analyses(self, world: World) -> None:
        aid = _ok(self._analyze(world, world.a, world.pa), "analyze")["analysis_id"]
        a_list = _ok(world.client.get("/api/v1/evm/analyses", headers=world.a), "list")
        b_list = _ok(world.client.get("/api/v1/evm/analyses", headers=world.b), "list")
        assert [x["analysis_id"] for x in a_list["analyses"]] == [aid]
        assert b_list["analyses"] == []

    @pytest.mark.parametrize("template", READS)
    def test_reads_by_id(self, world: World, template: str) -> None:
        aid = _ok(self._analyze(world, world.a, world.pa), "analyze")["analysis_id"]
        assert re.fullmatch(r"evm-[0-9a-f]{32}", aid)
        _ok(world.client.get(template.format(id=aid), headers=world.a), template)
        _assert_hidden_like_missing(world, template, aid, "evm")


class TestTIARoutes:
    READS = ["/api/v1/tia/analyses/{id}", "/api/v1/tia/analyses/{id}/summary"]

    def _analyze(self, w: World, headers: dict[str, str], project_id: str) -> Any:
        body = {"project_id": project_id, "fragments": [_fragment()]}
        return w.client.post("/api/v1/tia/analyze", json=body, headers=headers)

    def _check(self, w: World, headers: dict[str, str], analysis_id: str) -> Any:
        body = {"analysis_id": analysis_id}
        return w.client.post("/api/v1/contract/check", json=body, headers=headers)

    def test_other_tenant_cannot_analyze_foreign_project(self, world: World) -> None:
        _ok(self._analyze(world, world.a, world.pa), "analyze")
        foreign = self._analyze(world, world.b, world.pa)
        assert foreign.status_code == 404
        assert _answer(foreign) == _answer(self._analyze(world, world.b, "proj-9999"))

    def test_list_holds_only_the_callers_analyses(self, world: World) -> None:
        aid = _ok(self._analyze(world, world.a, world.pa), "analyze")["analysis_id"]
        a_list = _ok(world.client.get("/api/v1/tia/analyses", headers=world.a), "list")
        b_list = _ok(world.client.get("/api/v1/tia/analyses", headers=world.b), "list")
        assert [x["analysis_id"] for x in a_list["analyses"]] == [aid]
        assert b_list["analyses"] == []

    @pytest.mark.parametrize("template", READS)
    def test_reads_by_id(self, world: World, template: str) -> None:
        aid = _ok(self._analyze(world, world.a, world.pa), "analyze")["analysis_id"]
        assert re.fullmatch(r"tia-[0-9a-f]{32}", aid)
        _ok(world.client.get(template.format(id=aid), headers=world.a), template)
        _assert_hidden_like_missing(world, template, aid, "tia")

    def test_contract_check_takes_only_the_callers_analysis(self, world: World) -> None:
        aid = _ok(self._analyze(world, world.a, world.pa), "analyze")["analysis_id"]
        _ok(self._check(world, world.a, aid), "contract check")

        foreign = self._check(world, world.b, aid)
        random_id = self._check(world, world.b, f"tia-{uuid.uuid4().hex}")
        legacy = self._check(world, world.b, "tia-0001")
        assert foreign.status_code == 404
        assert _answer(foreign) == _answer(random_id) == _answer(legacy)


class TestTimelineRoutes:
    READS = [
        "/api/v1/forensic/timelines/{id}",
        "/api/v1/forensic/timelines/{id}/delay-trend",
    ]

    def _create(self, w: World, headers: dict[str, str], project_ids: list[str]) -> Any:
        return w.client.post(
            "/api/v1/forensic/create-timeline", json={"project_ids": project_ids}, headers=headers
        )

    def test_other_tenant_cannot_use_foreign_projects(self, world: World) -> None:
        _ok(self._create(world, world.a, [world.pa, world.pa2]), "create timeline")
        all_foreign = self._create(world, world.b, [world.pa, world.pa2])
        one_foreign = self._create(world, world.b, [world.pb, world.pa2])
        missing = self._create(world, world.b, [world.pb, "proj-9999"])
        assert all_foreign.status_code == 404
        assert _answer(all_foreign) == _answer(one_foreign) == _answer(missing)

    def test_list_holds_only_the_callers_timelines(self, world: World) -> None:
        tid = _ok(self._create(world, world.a, [world.pa, world.pa2]), "create")["timeline_id"]
        a_list = _ok(world.client.get("/api/v1/forensic/timelines", headers=world.a), "list")
        b_list = _ok(world.client.get("/api/v1/forensic/timelines", headers=world.b), "list")
        assert [x["timeline_id"] for x in a_list["timelines"]] == [tid]
        assert b_list["timelines"] == []

    @pytest.mark.parametrize("template", READS)
    def test_reads_by_id(self, world: World, template: str) -> None:
        tid = _ok(self._create(world, world.a, [world.pa, world.pa2]), "create")["timeline_id"]
        assert re.fullmatch(r"timeline-[0-9a-f]{32}", tid)
        _ok(world.client.get(template.format(id=tid), headers=world.a), template)
        _assert_hidden_like_missing(world, template, tid, "timeline")


class TestReportRoutes:
    def _generate(self, w: World, headers: dict[str, str], **body: Any) -> Any:
        return w.client.post("/api/v1/reports/generate", json=body, headers=headers)

    def test_download_only_by_the_owner(self, world: World) -> None:
        rid = _ok(
            self._generate(world, world.a, project_id=world.pa, report_type="health"), "generate"
        )["report_id"]
        assert re.fullmatch(r"report-[0-9a-f]{32}", rid)
        template = "/api/v1/reports/{id}/download"
        owner = world.client.get(template.format(id=rid), headers=world.a)
        assert owner.status_code == 200 and owner.content
        _assert_hidden_like_missing(world, template, rid, "report")

    def test_generate_rejects_foreign_project_and_baseline(self, world: World) -> None:
        _ok(
            self._generate(
                world, world.a, project_id=world.pa2, baseline_id=world.pa, report_type="comparison"
            ),
            "generate with baseline",
        )
        foreign = self._generate(world, world.b, project_id=world.pa, report_type="health")
        foreign_baseline = self._generate(
            world, world.b, project_id=world.pb, baseline_id=world.pa, report_type="comparison"
        )
        missing = self._generate(world, world.b, project_id="proj-9999", report_type="health")
        assert foreign.status_code == 404
        assert _answer(foreign) == _answer(foreign_baseline) == _answer(missing)

    @pytest.mark.parametrize(
        ("report_type", "id_field"), [("risk", "simulation_id"), ("tia", "analysis_id")]
    )
    def test_report_sources_are_the_callers_latest_for_that_project(
        self, world: World, report_type: str, id_field: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The renderer is stubbed so the test observes which stored result the
        # route selects, independent of PDF rendering.
        used: list[Any] = []

        def render(_self: ReportGenerator, result: Any) -> bytes:
            used.append(result)
            return b"%PDF-stub"

        monkeypatch.setattr(ReportGenerator, f"generate_{report_type}_report", render)

        def create(headers: dict[str, str], project_id: str) -> str:
            if report_type == "risk":
                resp = _run_simulation(world, headers, project_id)
            else:
                body = {"project_id": project_id, "fragments": [_fragment()]}
                resp = world.client.post("/api/v1/tia/analyze", json=body, headers=headers)
            return str(_ok(resp, f"create {report_type}")[id_field])

        create(world.a, world.pa)
        latest = create(world.a, world.pa)

        _ok(
            self._generate(world, world.a, project_id=world.pa, report_type=report_type),
            f"{report_type} report",
        )
        assert [getattr(r, id_field) for r in used] == [latest]

        # B has no analysis of its own: A's result must not feed B's report.
        other_tenant = self._generate(world, world.b, project_id=world.pb, report_type=report_type)
        # A's analysis of pa does not feed a report on A's other project.
        other_project = self._generate(
            world, world.a, project_id=world.pa2, report_type=report_type
        )
        assert other_tenant.status_code == 400
        assert other_project.status_code == 400
        assert len(used) == 1

    def test_available_reports_is_owner_only(self, world: World) -> None:
        _ok(_run_simulation(world, world.a, world.pa), "simulate")
        _ok(world.client.post(f"/api/v1/evm/analyze/{world.pa}", headers=world.a), "evm")

        path = "/api/v1/projects/{id}/available-reports"
        data = _ok(world.client.get(path.format(id=world.pa), headers=world.a), "available")
        ready = {r["type"]: r["ready"] for r in data["reports"]}
        assert ready["risk"] is True and ready["evm"] is True

        foreign = world.client.get(path.format(id=world.pa), headers=world.b)
        missing = world.client.get(path.format(id="proj-9999"), headers=world.b)
        assert foreign.status_code == 404
        assert _answer(foreign) == _answer(missing)

        own = _ok(world.client.get(path.format(id=world.pb), headers=world.b), "available as B")
        ready_b = {r["type"]: r["ready"] for r in own["reports"]}
        assert ready_b["risk"] is False and ready_b["evm"] is False


class TestUserDataErasure:
    def test_delete_user_data_purges_only_the_callers_results(self, world: World) -> None:
        w = world
        a_sid = _ok(_run_simulation(w, w.a, w.pa), "simulate")["simulation_id"]
        b_sid = _ok(_run_simulation(w, w.b, w.pb), "simulate as B")["simulation_id"]
        _ok(w.client.post(f"/api/v1/evm/analyze/{w.pa}", headers=w.a), "evm")
        body = {"project_id": w.pa, "fragments": [_fragment()]}
        _ok(w.client.post("/api/v1/tia/analyze", json=body, headers=w.a), "tia")
        timeline = {"project_ids": [w.pa, w.pa2]}
        _ok(w.client.post("/api/v1/forensic/create-timeline", json=timeline, headers=w.a), "tl")
        report = {"project_id": w.pa, "report_type": "health"}
        _ok(w.client.post("/api/v1/reports/generate", json=report, headers=w.a), "report")

        stores: list[OwnedResultStore[Any]] = [
            deps.get_timeline_store(),
            deps.get_tia_store(),
            deps.get_evm_store(),
            deps.get_risk_store(),
            deps.get_report_store(),
        ]
        assert all(store.list(USER_A) for store in stores)  # control: A had one of each

        _ok(w.client.delete("/api/v1/user/data", headers=w.a), "delete user data")

        assert [store.list(USER_A) for store in stores] == [[], [], [], [], []]
        assert w.client.get(f"/api/v1/risk/simulations/{a_sid}", headers=w.a).status_code == 404
        _ok(w.client.get(f"/api/v1/risk/simulations/{b_sid}", headers=w.b), "B after A erased")
