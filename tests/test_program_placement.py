# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Choosing a schedule's program: at upload, by moving one, and in bulk.

Runs with production auth (no anonymous principal) against an InMemoryStore
whose ``place_project_in_program`` mirrors the SQL function of migration 039.
Every refusal to another user is a 404 indistinguishable from a missing row.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

import src.api.deps as deps
from src.api import access, auth
from src.api.app import app
from src.api.routers import revisions as revisions_router
from src.api.schemas import MAX_PLACEMENT_PROJECT_IDS
from src.database import config
from src.database.store import InMemoryStore
from src.parser.models import ParsedSchedule, Project, Relationship, Task

TEST_JWT_SECRET = "test-secret"  # tests/conftest.py sets SUPABASE_JWT_SECRET to this
USER_A = "00000000-0000-4000-8000-0000000000a1"
USER_B = "00000000-0000-4000-8000-0000000000b2"
SAMPLE = Path(__file__).parent / "fixtures" / "sample.xer"
NOT_FOUND = {"detail": "Project not found"}


def _token(sub: str) -> str:
    now = int(time.time())
    claims = {"sub": sub, "aud": "authenticated", "role": "authenticated", "iat": now}
    claims["exp"] = now + 3600
    return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256")


def _schedule(name: str, day: int) -> ParsedSchedule:
    return ParsedSchedule(
        projects=[
            Project(proj_id="P1", proj_short_name=name, last_recalc_date=datetime(2026, day, 1))
        ],
        activities=[
            Task(task_id=f"T{i}", task_code=f"A{i}", task_name=f"Activity {i}") for i in (1, 2)
        ],
        relationships=[Relationship(task_id="T2", pred_task_id="T1")],
    )


class World:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store
        self.client = TestClient(app)
        self.a = {"Authorization": f"Bearer {_token(USER_A)}"}
        self.b = {"Authorization": f"Bearer {_token(USER_B)}"}

    def seed(self, owner: str, name: str, day: int) -> str:
        return self.store.add(_schedule(name, day), b"x", user_id=owner)

    def program_of(self, pid: str) -> str | None:
        return self.store._upload_program.get(pid)

    def revision_of(self, pid: str) -> int | None:
        return self.store._upload_revision.get(pid)

    def state(self) -> tuple[dict[str, Any], dict[str, Any], set[str]]:
        return (
            dict(self.store._upload_program),
            dict(self.store._upload_revision),
            set(self.store._programs),
        )


@pytest.fixture
def w(monkeypatch: pytest.MonkeyPatch) -> World:
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    assert vars(access)["settings"] is config.settings
    assert vars(auth)["settings"] is config.settings
    assert config.settings.SUPABASE_JWT_SECRET == TEST_JWT_SECRET
    store = InMemoryStore()
    monkeypatch.setattr(deps, "_store", store)
    assert deps.get_store() is store
    return World(store)


def _move(w: World, pid: str, body: dict[str, Any], headers: dict[str, str]) -> Any:
    return w.client.put(f"/api/v1/projects/{pid}/program", json=body, headers=headers)


class TestMove:
    def test_into_another_program_becomes_its_next_revision(self, w: World) -> None:
        first = w.seed(USER_A, "ALPHA UP01", 1)
        second = w.seed(USER_A, "ALPHA UP02", 2)
        target, source = w.program_of(first), w.program_of(second)
        assert target != source  # the short names differ, so they were split

        resp = _move(w, second, {"program_id": target}, w.a)

        assert resp.status_code == 200, resp.text
        assert resp.json() == {
            "project_id": second,
            "program_id": target,
            "revision_number": 2,
            "source_program_deleted": True,
        }
        assert w.program_of(second) == target
        assert source not in w.store._programs
        listed = w.client.get(f"/api/v1/programs/{target}", headers=w.a).json()
        assert [r["id"] for r in listed["revisions"]] == [second, first]
        assert listed["program"]["revision_count"] == 2

    def test_into_a_new_program_by_name(self, w: World) -> None:
        pid = w.seed(USER_A, "ALPHA UP01", 1)
        resp = _move(w, pid, {"new_program_name": "  Alpha Program "}, w.a)
        assert resp.status_code == 200, resp.text
        prog = w.store._programs[resp.json()["program_id"]]
        assert prog["name"] == "Alpha Program" and prog["user_id"] == USER_A

    def test_a_new_name_matching_an_existing_program_joins_it(self, w: World) -> None:
        first = w.seed(USER_A, "Alpha", 1)
        second = w.seed(USER_A, "Beta", 2)
        resp = _move(w, second, {"new_program_name": "ALPHA"}, w.a)
        assert resp.json()["program_id"] == w.program_of(first)

    def test_into_the_program_it_is_in_changes_nothing(self, w: World) -> None:
        pid = w.seed(USER_A, "Alpha", 1)
        before = w.state()
        resp = _move(w, pid, {"program_id": w.program_of(pid)}, w.a)
        assert resp.json()["revision_number"] == 1
        assert resp.json()["source_program_deleted"] is False
        assert w.state() == before

    def test_a_program_left_with_schedules_is_kept(self, w: World) -> None:
        w.seed(USER_A, "Alpha", 1)
        stays = w.seed(USER_A, "Alpha", 2)
        source = w.program_of(stays)
        mover = w.seed(USER_A, "Alpha", 3)
        other = w.seed(USER_A, "Beta", 4)
        resp = _move(w, mover, {"program_id": w.program_of(other)}, w.a)
        assert resp.json()["source_program_deleted"] is False
        assert source in w.store._programs

    def test_confirmed_revision_links_block_the_move(self, w: World) -> None:
        pid = w.seed(USER_A, "Alpha", 1)
        other = w.seed(USER_A, "Beta", 2)
        w.store._revision_history.append({"project_id": pid, "tombstoned_at": None})
        before = w.state()
        resp = _move(w, pid, {"program_id": w.program_of(other)}, w.a)
        assert resp.status_code == 409, resp.text
        assert w.state() == before


class TestMoveIsTheOwnersAlone:
    def test_another_users_project_is_not_found(self, w: World) -> None:
        theirs = w.seed(USER_A, "Alpha", 1)
        mine = w.seed(USER_B, "Beta", 2)
        before = w.state()
        resp = _move(w, theirs, {"program_id": w.program_of(mine)}, w.b)
        assert (resp.status_code, resp.json()) == (404, NOT_FOUND)
        missing = _move(w, "no-such-project", {"program_id": w.program_of(mine)}, w.b)
        assert (missing.status_code, missing.json()) == (404, NOT_FOUND)
        assert w.state() == before

    def test_another_users_program_is_not_found(self, w: World) -> None:
        mine = w.seed(USER_A, "Alpha", 1)
        theirs = w.seed(USER_B, "Beta", 2)
        before = w.state()
        resp = _move(w, mine, {"program_id": w.program_of(theirs)}, w.a)
        assert (resp.status_code, resp.json()) == (404, {"detail": "Program not found"})
        missing = _move(w, mine, {"program_id": "prog-9999"}, w.a)
        assert (missing.status_code, missing.json()) == (404, {"detail": "Program not found"})
        assert w.state() == before

    def test_anonymous_is_rejected(self, w: World) -> None:
        pid = w.seed(USER_A, "Alpha", 1)
        assert _move(w, pid, {"new_program_name": "X"}, {}).status_code == 401

    @pytest.mark.parametrize(
        "body",
        [
            {},
            {"program_id": "p", "new_program_name": "n"},
            {"new_program_name": ""},
            {"new_program_name": "x" * 201},
            {"new_program_name": "n", "user_id": USER_B},
        ],
    )
    def test_body_names_exactly_one_target(self, w: World, body: dict[str, Any]) -> None:
        pid = w.seed(USER_A, "Alpha", 1)
        assert _move(w, pid, body, w.a).status_code == 422


class TestBulk:
    def _place(self, w: World, body: dict[str, Any], headers: dict[str, str]) -> Any:
        return w.client.post("/api/v1/programs/placements", json=body, headers=headers)

    def test_moves_every_schedule_once(self, w: World) -> None:
        pids = [w.seed(USER_A, f"ALPHA UP{n:02d}", n) for n in (1, 2, 3)]
        resp = self._place(w, {"project_ids": [*pids, pids[0]], "new_program_name": "Alpha"}, w.a)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert [p["project_id"] for p in body["placements"]] == pids
        assert {w.program_of(p) for p in pids} == {body["program_id"]}
        assert sorted(w.revision_of(p) or 0 for p in pids) == [1, 2, 3]
        assert len(w.store._programs) == 1

    def test_one_foreign_id_moves_nothing(self, w: World) -> None:
        mine = [w.seed(USER_A, f"Alpha {n}", n) for n in (1, 2)]
        theirs = w.seed(USER_B, "Beta", 3)
        before = w.state()
        resp = self._place(w, {"project_ids": [*mine, theirs], "new_program_name": "X"}, w.a)
        assert (resp.status_code, resp.json()) == (404, NOT_FOUND)
        assert w.state() == before

    def test_the_list_is_capped(self, w: World) -> None:
        pid = w.seed(USER_A, "Alpha", 1)
        ids = [pid] * (MAX_PLACEMENT_PROJECT_IDS + 1)
        resp = self._place(w, {"project_ids": ids, "new_program_name": "X"}, w.a)
        assert resp.status_code == 422
        assert self._place(w, {"project_ids": [], "new_program_name": "X"}, w.a).status_code == 422


class TestUpload:
    def _upload(self, w: World, headers: dict[str, str], **form: Any) -> Any:
        with SAMPLE.open("rb") as fh:
            return w.client.post(
                "/api/v1/upload",
                files={"file": ("sample.xer", fh, "application/octet-stream")},
                data=form,
                headers=headers,
            )

    def test_into_a_chosen_program(self, w: World) -> None:
        existing = w.seed(USER_A, "Something else", 1)
        program = w.program_of(existing)
        resp = self._upload(w, w.a, program_id=program)
        assert resp.status_code == 200, resp.text
        pid = resp.json()["project_id"]
        assert (w.program_of(pid), w.revision_of(pid)) == (program, 2)
        assert resp.json()["program_id"] == program

    def test_into_a_new_program(self, w: World) -> None:
        resp = self._upload(w, w.a, new_program_name="Fresh")
        pid = resp.json()["project_id"]
        assert w.store._programs[w.program_of(pid) or ""]["name"] == "Fresh"

    def test_without_a_choice_the_short_name_still_groups(self, w: World) -> None:
        first = self._upload(w, w.a).json()["project_id"]
        second = self._upload(w, w.a).json()["project_id"]
        assert w.program_of(first) == w.program_of(second)
        assert sorted([w.revision_of(first), w.revision_of(second)]) == [1, 2]

    def test_a_sandbox_upload_joins_no_program(self, w: World) -> None:
        resp = self._upload(w, w.a, is_sandbox="true")
        assert w.program_of(resp.json()["project_id"]) is None
        assert resp.json()["program_id"] is None
        assert w.store._programs == {}
        refused = self._upload(w, w.a, is_sandbox="true", new_program_name="X")
        assert refused.status_code == 422

    def test_another_users_program_is_refused_and_nothing_is_stored(self, w: World) -> None:
        theirs = w.program_of(w.seed(USER_B, "Beta", 1))
        before = w.store.list_ids()
        resp = self._upload(w, w.a, program_id=theirs)
        assert (resp.status_code, resp.json()) == (404, {"detail": "Program not found"})
        assert w.store.list_ids() == before

    def test_both_choices_at_once_are_refused(self, w: World) -> None:
        resp = self._upload(w, w.a, program_id="p", new_program_name="n")
        assert resp.status_code == 422
        assert resp.json()["detail"][0]["msg"].endswith(
            "Send exactly one of program_id or new_program_name"
        )


class TestRevisionTrendsCap:
    def test_keeps_the_latest_and_always_the_current(self) -> None:
        sibs = [{"project_id": f"p{n}", "data_date": f"2026-{n:02d}-01"} for n in range(1, 13)]
        sibs += [{"project_id": "old", "data_date": "2020-01-01"}, {"project_id": "nodate"}]
        kept, left_out = revisions_router._latest_siblings(sibs, "old")
        assert left_out == 2
        assert len(kept) == revisions_router.MAX_TREND_REVISIONS
        assert "old" in {s["project_id"] for s in kept}
        assert "p12" in {s["project_id"] for s in kept}

    def test_small_programs_are_untouched(self) -> None:
        sibs = [{"project_id": "a"}, {"project_id": "b"}]
        assert revisions_router._latest_siblings(sibs, "a") == (sibs, 0)


class _Rpc:
    def __init__(self, client: _Client, name: str, params: dict[str, Any]) -> None:
        self.client, self.name, self.params = client, name, params

    def execute(self) -> Any:
        self.client.calls.append((self.name, self.params))
        if isinstance(self.client.reply, Exception):
            raise self.client.reply
        return type("Result", (), {"data": self.client.reply})()


class _Client:
    def __init__(self, reply: Any) -> None:
        self.reply = reply
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def rpc(self, name: str, params: dict[str, Any]) -> _Rpc:
        return _Rpc(self, name, params)


def _supabase(reply: Any) -> tuple[Any, _Client]:
    from src.database.store import SupabaseStore

    store = SupabaseStore.__new__(SupabaseStore)
    client = _Client(reply)
    store._client = client
    return store, client


_P = "00000000-0000-4000-8000-000000000001"
_G = "00000000-0000-4000-8000-000000000002"


class TestSupabasePlacement:
    def test_calls_the_039_function_and_reads_its_row(self) -> None:
        store, client = _supabase([{"revision_number": 3, "source_program_deleted": True}])
        assert store.place_project_in_program(USER_A, _P, _G) == (3, True)
        assert client.calls == [
            (
                "place_project_in_program",
                {"p_user_id": USER_A, "p_project_id": _P, "p_program_id": _G},
            )
        ]

    @pytest.mark.parametrize(("code", "reason"), [("P0002", "not_found"), ("P0001", "linked")])
    def test_sql_errors_map_to_reasons(self, code: str, reason: str) -> None:
        from src.database.store import ProgramPlacementError

        class Refused(Exception):
            pass

        err = Refused("refused")
        err.code = code  # type: ignore[attr-defined]
        store, _ = _supabase(err)
        with pytest.raises(ProgramPlacementError) as caught:
            store.place_project_in_program(USER_A, _P, _G)
        assert caught.value.reason == reason

    def test_other_errors_propagate(self) -> None:
        store, _ = _supabase(RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            store.place_project_in_program(USER_A, _P, _G)

    def test_ids_that_are_not_uuids_never_reach_the_database(self) -> None:
        from src.database.store import ProgramPlacementError

        store, client = _supabase([])
        for args in ((USER_A, "x", _G), (USER_A, _P, "Some Short Name"), ("", _P, _G)):
            with pytest.raises(ProgramPlacementError):
                store.place_project_in_program(*args)
        assert client.calls == []


class TestProjectDetailNamesItsProgram:
    def test_owner_sees_the_program(self, w: World) -> None:
        pid = w.seed(USER_A, "Alpha", 1)
        body = w.client.get(f"/api/v1/projects/{pid}", headers=w.a).json()
        assert body["program_id"] == w.program_of(pid)

    def test_a_schedule_in_no_program_says_so(self, w: World) -> None:
        pid = w.store.add(_schedule("Alpha", 1), b"x", user_id=USER_A, assign_program=False)
        body = w.client.get(f"/api/v1/projects/{pid}", headers=w.a).json()
        assert body["program_id"] is None
