# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the tenant access layer (src/api/access.py) and the owner lookup."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from src.api import access
from src.api.access import (
    DEV_USER_ID,
    SYSTEM,
    AccessContext,
    Principal,
    owned_project,
    principal_from_user,
)
from src.database.store import InMemoryStore, SupabaseStore
from src.parser.xer_reader import XERReader

OWNER_A = "00000000-0000-4000-8000-00000000000a"
OWNER_B = "00000000-0000-4000-8000-00000000000b"


class _OwnerMap:
    """Minimal store: ``get_project_owner`` from a dict, counting lookups."""

    def __init__(self, owners: dict[str, str | None]) -> None:
        self._owners = owners
        self.lookups: list[str] = []

    def get_project_owner(self, project_id: str) -> tuple[bool, str | None]:
        self.lookups.append(project_id)
        if project_id not in self._owners:
            return False, None
        return True, self._owners[project_id]


def _ctx(principal: Principal, owners: dict[str, str | None]) -> AccessContext:
    return AccessContext(principal, _OwnerMap(owners))


USER_A = Principal(OWNER_A, "user")
USER_B = Principal(OWNER_B, "user")
KEY_A = Principal(OWNER_A, "api_key")
DEV = Principal(DEV_USER_ID, "dev")
OWNERS = {"pa": OWNER_A, "pb": OWNER_B, "orphan": None}


class TestPrincipalFromUser:
    def test_anonymous_in_development_with_memory_store_is_dev(self) -> None:
        assert principal_from_user(None, InMemoryStore()) == DEV

    def test_anonymous_in_production_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(access.settings, "ENVIRONMENT", "production")
        with pytest.raises(HTTPException) as exc_info:
            principal_from_user(None, InMemoryStore())
        assert exc_info.value.status_code == 401

    def test_anonymous_with_a_real_store_is_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            principal_from_user(None, object())
        assert exc_info.value.status_code == 401

    def test_jwt_user_and_api_key_user(self) -> None:
        store = InMemoryStore()
        assert principal_from_user({"id": OWNER_A, "role": "authenticated"}, store) == USER_A
        assert principal_from_user({"id": OWNER_A, "role": "api_key"}, store) == KEY_A

    def test_user_without_id_is_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            principal_from_user({"id": "", "role": "authenticated"}, InMemoryStore())
        assert exc_info.value.status_code == 401


class TestAccessRule:
    @pytest.mark.parametrize(
        ("principal", "project_id", "granted"),
        [
            (USER_A, "pa", True),  # owner
            (KEY_A, "pa", True),  # owner through an API key
            (KEY_A, "pb", False),  # an API key reaches only its owner's projects
            (KEY_A, "orphan", False),
            (USER_B, "pa", False),  # another tenant
            (USER_A, "orphan", False),  # ownerless is hidden from real users
            (DEV, "orphan", True),  # ...and visible to the dev principal
            (DEV, "pa", False),  # dev never sees an owned project
            (SYSTEM, "pa", True),  # trusted background work
            (SYSTEM, "missing", False),  # nothing grants a project that does not exist
            (USER_A, "missing", False),
            (USER_A, "", False),
        ],
    )
    def test_matrix(self, principal: Principal, project_id: str, granted: bool) -> None:
        assert _ctx(principal, OWNERS).can_access_project(project_id) is granted

    def test_hidden_and_missing_are_indistinguishable(self) -> None:
        ctx = _ctx(USER_B, OWNERS)
        with pytest.raises(HTTPException) as foreign:
            ctx.project("pa")
        with pytest.raises(HTTPException) as missing:
            ctx.project("does-not-exist")
        assert (foreign.value.status_code, foreign.value.detail) == (
            missing.value.status_code,
            missing.value.detail,
        )
        assert foreign.value.status_code == 404

    def test_maybe_project(self) -> None:
        ctx = _ctx(USER_A, OWNERS)
        assert ctx.maybe_project(None) is None
        assert ctx.maybe_project("") is None
        assert ctx.maybe_project("pa") == "pa"
        with pytest.raises(HTTPException):
            ctx.maybe_project("pb")  # given but hidden is 404, never silently ignored

    def test_projects_is_all_or_nothing(self) -> None:
        ctx = _ctx(USER_A, {**OWNERS, "pa2": OWNER_A})
        assert ctx.projects(["pa", "pa2"]) == ["pa", "pa2"]
        with pytest.raises(HTTPException):
            ctx.projects(["pa", "pb"])

    def test_lookups_are_memoised_per_request(self) -> None:
        ctx = _ctx(USER_A, OWNERS)
        for _ in range(3):
            ctx.project("pa")
        assert ctx.store.lookups == ["pa"]


class TestInMemoryOwnerLookup:
    def test_owner_recorded_ownerless_and_missing(self) -> None:
        store = InMemoryStore()
        owned = store.add(XERReader("tests/fixtures/sample.xer").parse(), b"x", user_id=OWNER_A)
        ownerless = store.add(XERReader("tests/fixtures/sample.xer").parse(), b"x")
        assert store.get_project_owner(owned) == (True, OWNER_A)
        assert store.get_project_owner(ownerless) == (True, None)
        assert store.get_project_owner("proj-9999") == (False, None)
        assert store.get_project_owner("") == (False, None)


class _RecordingQuery:
    def __init__(self, calls: list[tuple[str, Any]], rows: list[dict[str, Any]]) -> None:
        self._calls = calls
        self._rows = rows

    def select(self, columns: str) -> _RecordingQuery:
        self._calls.append(("select", columns))
        return self

    def eq(self, column: str, value: Any) -> _RecordingQuery:
        self._calls.append(("eq", (column, value)))
        return self

    def execute(self) -> Any:
        self._calls.append(("execute", None))
        return type("R", (), {"data": self._rows})()


class _RecordingClient:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.calls: list[tuple[str, Any]] = []
        self._rows = rows

    def table(self, name: str) -> _RecordingQuery:
        self.calls.append(("table", name))
        return _RecordingQuery(self.calls, self._rows)


def _supabase_store(rows: list[dict[str, Any]]) -> SupabaseStore:
    store = SupabaseStore.__new__(SupabaseStore)
    store._client = _RecordingClient(rows)  # type: ignore[attr-defined]
    return store


class TestSupabaseOwnerLookup:
    def test_non_uuid_emits_no_query(self) -> None:
        store = _supabase_store([])
        assert store.get_project_owner("proj-0001") == (False, None)
        assert store._client.calls == []  # type: ignore[attr-defined]

    def test_uuid_queries_projects_by_id_only(self) -> None:
        pid = "11111111-1111-4111-8111-111111111111"
        store = _supabase_store([{"id": pid, "user_id": OWNER_A}])
        assert store.get_project_owner(pid) == (True, OWNER_A)
        calls = store._client.calls  # type: ignore[attr-defined]
        assert ("table", "projects") in calls
        assert ("eq", ("id", pid)) in calls

    def test_missing_row_and_null_owner(self) -> None:
        pid = "11111111-1111-4111-8111-111111111111"
        assert _supabase_store([]).get_project_owner(pid) == (False, None)
        assert _supabase_store([{"id": pid, "user_id": None}]).get_project_owner(pid) == (
            True,
            None,
        )


class TestOwnedProjectDependency:
    """End to end through FastAPI's dependency graph, with a real in-memory store."""

    @pytest.fixture
    def client_and_ids(self) -> tuple[TestClient, str, str, str]:
        store = InMemoryStore()
        schedule = XERReader("tests/fixtures/sample.xer").parse()
        pa = store.add(schedule, b"x", user_id=OWNER_A)
        pb = store.add(XERReader("tests/fixtures/sample.xer").parse(), b"x", user_id=OWNER_B)
        orphan = store.add(XERReader("tests/fixtures/sample.xer").parse(), b"x")

        def fake_user(request: Request) -> dict[str, Any] | None:
            uid = request.headers.get("x-test-user")
            return {"id": uid, "role": "authenticated"} if uid else None

        app = FastAPI()

        @app.get("/p/{project_id}")
        def read(project_id: str = Depends(owned_project)) -> dict[str, str]:
            return {"project_id": project_id}

        app.dependency_overrides[access.optional_auth] = fake_user
        app.dependency_overrides[access.get_store] = lambda: store
        return TestClient(app), pa, pb, orphan

    def test_owner_reaches_own_project(self, client_and_ids: tuple[Any, ...]) -> None:
        client, pa, _pb, _orphan = client_and_ids
        assert client.get(f"/p/{pa}", headers={"x-test-user": OWNER_A}).status_code == 200

    def test_other_tenant_gets_404(self, client_and_ids: tuple[Any, ...]) -> None:
        client, pa, pb, _orphan = client_and_ids
        assert client.get(f"/p/{pa}", headers={"x-test-user": OWNER_B}).status_code == 404
        assert client.get(f"/p/{pb}", headers={"x-test-user": OWNER_B}).status_code == 200

    def test_dev_caller_sees_only_ownerless(self, client_and_ids: tuple[Any, ...]) -> None:
        client, pa, _pb, orphan = client_and_ids
        assert client.get(f"/p/{orphan}").status_code == 200
        assert client.get(f"/p/{pa}").status_code == 404
