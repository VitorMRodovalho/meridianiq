# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tenant isolation for organization, membership, sharing and value-milestone routes.

The harness follows ``tests/test_tenancy_analysis.py``: ``ENVIRONMENT=production``,
real HS256 JWTs and a fresh ``InMemoryStore`` for project ownership, never
``dependency_overrides``, so the whole auth -> principal -> access path runs.

In production the organization tables are read with the service-role
Supabase client, which bypasses RLS. Here they are served by
:class:`FakeSupabase`, an in-memory PostgREST stand-in that APPLIES the
filters it receives and RECORDS every query. A test can therefore assert the
answer and also that the membership / project filter was actually sent.

Every refusal is compared with the answer for an id that does not exist.
Every positive control fails (never skips) if the rightful caller is denied.
Every refused write is followed by reading the victim's rows back.
"""

from __future__ import annotations

import copy
import itertools
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

import src.api.deps as deps
from src.api import access, auth, organizations
from src.api.app import app
from src.database import config
from src.database.store import InMemoryStore, SupabaseStore
from src.parser.xer_reader import XERReader

FIXTURES = Path(__file__).parent / "fixtures"
TEST_JWT_SECRET = "test-secret"  # tests/conftest.py sets SUPABASE_JWT_SECRET to this

USER_A = "00000000-0000-4000-8000-0000000000a1"  # owner of ORG_A and of projects pa, pa2
USER_B = "00000000-0000-4000-8000-0000000000b2"  # owner of ORG_B and of project pb
ADMIN = "00000000-0000-4000-8000-0000000000c3"  # admin of ORG_A
MEMBER = "00000000-0000-4000-8000-0000000000d4"  # member of ORG_A and of ORG_B
VIEWER = "00000000-0000-4000-8000-0000000000e5"  # viewer of ORG_A
PENDING = "00000000-0000-4000-8000-0000000000f6"  # invited to ORG_A, not accepted
NEWBIE = "00000000-0000-4000-8000-0000000000a7"  # has an account, belongs nowhere

ORG_A = "0a0a0a0a-0000-4000-8000-00000000000a"
ORG_B = "0b0b0b0b-0000-4000-8000-00000000000b"

NAMES = {
    USER_A: "alice",
    USER_B: "bruno",
    ADMIN: "adele",
    MEMBER: "marco",
    VIEWER: "vera",
    PENDING: "paula",
    NEWBIE: "nadia",
}


def email(user: str) -> str:
    return f"{NAMES[user]}@example.test"


def profile(user: str) -> dict[str, str]:
    name = NAMES[user]
    return {
        "id": user,
        "email": email(user),
        "full_name": f"{name.title()} Example",
        "avatar_url": f"https://example.test/avatars/{name}.png",
    }


NO_ACCOUNT_EMAIL = "nobody@example.test"

NOT_FOUND = (404, {"detail": "Project not found"})
ORG_NOT_FOUND = (404, {"detail": "Organization not found"})
INVITATION_NOT_FOUND = (404, {"detail": "Invitation not found"})
MILESTONE_NOT_FOUND = (404, {"detail": "Value milestone not found"})


def _token(sub: str) -> str:
    now = int(time.time())
    claims = {"sub": sub, "aud": "authenticated", "role": "authenticated", "iat": now}
    claims["exp"] = now + 3600
    return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256")


def _answer(resp: Any) -> tuple[int, Any]:
    return resp.status_code, resp.json()


def _ok(resp: Any, what: str) -> None:
    """Positive control: the caller must get past the access check. Fails, never skips."""
    assert 200 <= resp.status_code < 300, f"denied on {what}: {resp.status_code} {resp.text}"


# ------------------------------------------------------------------ #
# A recording, filter-applying stand-in for the Supabase client      #
# ------------------------------------------------------------------ #

# (table, embedded resource) -> the local column that references ``<resource>.id``
_EMBEDS: dict[tuple[str, str], str] = {
    ("memberships", "organizations"): "org_id",
    ("memberships", "user_profiles"): "user_id",
    ("project_shares", "organizations"): "shared_with_org",
    ("audit_log", "user_profiles"): "user_id",
}
# Column defaults of migration 007 that the routes rely on (a missing column reads NULL).
_DEFAULTS: dict[str, dict[str, Any]] = {
    "memberships": {"accepted_at": None, "invited_by": None},
}
_UNIQUE: dict[str, tuple[str, ...]] = {
    "memberships": ("org_id", "user_id"),
    "project_shares": ("project_id", "shared_with_org"),
}


def _split_columns(spec: str) -> list[str]:
    parts: list[str] = []
    depth, current = 0, ""
    for ch in spec:
        if ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        depth += (ch == "(") - (ch == ")")
        current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


@dataclass(frozen=True)
class Emitted:
    """One executed query, as the client would have sent it."""

    table: str
    op: str  # select | insert | upsert | update | delete
    columns: str | None
    filters: tuple[tuple[str, str, Any], ...]  # (operator, column, value)
    payload: Any

    def has(self, operator: str, column: str, value: Any) -> bool:
        return (operator, column, value) in self.filters


class _Query:
    def __init__(self, db: FakeSupabase, table: str) -> None:
        self._db = db
        self.table = table
        self.op = "select"
        self.columns: str | None = None
        self.payload: Any = None
        self.filters: list[tuple[str, str, Any]] = []
        self._negate = False
        self.order_by: tuple[str, bool] | None = None
        self.window: tuple[int, int] | None = None
        self.on_conflict = ""

    def select(self, columns: str = "*") -> _Query:
        self.op, self.columns = "select", columns
        return self

    def insert(self, payload: Any) -> _Query:
        self.op, self.payload = "insert", payload
        return self

    def upsert(self, payload: Any, on_conflict: str = "") -> _Query:
        self.op, self.payload, self.on_conflict = "upsert", payload, on_conflict
        return self

    def update(self, payload: Any) -> _Query:
        self.op, self.payload = "update", payload
        return self

    def delete(self) -> _Query:
        self.op = "delete"
        return self

    @property
    def not_(self) -> _Query:
        self._negate = True
        return self

    def eq(self, column: str, value: Any) -> _Query:
        return self._filter("eq", column, value)

    def is_(self, column: str, value: Any) -> _Query:
        return self._filter("is", column, "null" if value is None else value)

    def order(self, column: str, desc: bool = False) -> _Query:
        self.order_by = (column, desc)
        return self

    def range(self, start: int, end: int) -> _Query:
        self.window = (start, end)
        return self

    def _filter(self, operator: str, column: str, value: Any) -> _Query:
        if self._negate:
            operator, self._negate = f"not.{operator}", False
        self.filters.append((operator, column, value))
        return self

    def matches(self, row: dict[str, Any]) -> bool:
        for operator, column, value in self.filters:
            if operator == "eq":
                ok = row.get(column) == value
            elif operator in ("is", "not.is"):
                assert value == "null", f"unsupported is-value {value!r}"
                ok = (row.get(column) is None) == (operator == "is")
            else:  # pragma: no cover - the routes use only these operators
                raise AssertionError(f"unsupported operator {operator}")
            if not ok:
                return False
        return True

    def execute(self) -> Any:
        return type("Result", (), {"data": self._db.run(self)})()


class FakeSupabase:
    """Tables as lists of rows; every executed query is appended to ``log``."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.log: list[Emitted] = []
        self._clock = itertools.count(1)

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    # -- helpers for tests --------------------------------------------
    def seed(self, table: str, **row: Any) -> dict[str, Any]:
        full = {"id": str(uuid.uuid4()), "created_at": self._tick(), **row}
        self.tables.setdefault(table, []).append(full)
        return full

    def rows(self, table: str, **match: Any) -> list[dict[str, Any]]:
        return [
            copy.deepcopy(r)
            for r in self.tables.get(table, [])
            if all(r.get(k) == v for k, v in match.items())
        ]

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        return copy.deepcopy(self.tables)

    def writes(self) -> list[Emitted]:
        return [q for q in self.log if q.op != "select"]

    def queries(self, table: str) -> list[Emitted]:
        return [q for q in self.log if q.table == table]

    # -- execution ----------------------------------------------------
    def _tick(self) -> str:
        return f"2026-01-01T00:00:{next(self._clock):06d}"

    def _project(self, table: str, row: dict[str, Any], spec: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for part in _split_columns(spec):
            if "(" in part:
                name, inner = part.split("(", 1)
                name, inner = name.strip(), inner.rsplit(")", 1)[0]
                fk = _EMBEDS[(table, name)]
                target = next(
                    (r for r in self.tables.get(name, []) if r.get("id") == row.get(fk)), None
                )
                out[name] = None if target is None else self._project(name, target, inner)
            elif part == "*":
                out.update(row)
            else:
                out[part] = row.get(part)
        return copy.deepcopy(out)

    def run(self, q: _Query) -> list[dict[str, Any]]:
        self.log.append(
            Emitted(q.table, q.op, q.columns, tuple(q.filters), copy.deepcopy(q.payload))
        )
        rows = self.tables.setdefault(q.table, [])
        if q.op == "select":
            hits = [r for r in rows if q.matches(r)]
            if q.order_by:
                column, desc = q.order_by
                hits.sort(key=lambda r: str(r.get(column) or ""), reverse=desc)
            if q.window:
                hits = hits[q.window[0] : q.window[1] + 1]
            return [self._project(q.table, r, q.columns or "*") for r in hits]
        if q.op in ("insert", "upsert"):
            out = []
            for payload in q.payload if isinstance(q.payload, list) else [q.payload]:
                row = {
                    "id": str(uuid.uuid4()),
                    "created_at": self._tick(),
                    **_DEFAULTS.get(q.table, {}),
                    **payload,
                }
                key = _UNIQUE.get(q.table, ())
                clash = [r for r in rows if key and all(r.get(k) == row.get(k) for k in key)]
                # PostgREST merges only on the conflict target it is given (the
                # primary key by default); a clash on another unique key is an error.
                merges = q.op == "upsert" and q.on_conflict == ",".join(key)
                if clash and not merges:
                    raise RuntimeError(f"duplicate key value violates unique constraint {key}")
                if clash:
                    clash[0].update(payload)
                    out.append(copy.deepcopy(clash[0]))
                else:
                    rows.append(row)
                    out.append(copy.deepcopy(row))
            return out
        assert q.filters, f"unfiltered {q.op} on {q.table}"
        hits = [r for r in rows if q.matches(r)]
        if q.op == "update":
            for r in hits:
                r.update(q.payload)
            return copy.deepcopy(hits)
        if q.op == "delete":
            doomed = {id(r) for r in hits}
            self.tables[q.table] = [r for r in rows if id(r) not in doomed]
            return copy.deepcopy(hits)
        raise AssertionError(f"unsupported op {q.op}")  # pragma: no cover


# ------------------------------------------------------------------ #
# World                                                              #
# ------------------------------------------------------------------ #


@dataclass
class World:
    client: TestClient
    store: InMemoryStore
    db: FakeSupabase
    pa: str  # A's project (org ORG_A)
    pa2: str  # A's second project
    pb: str  # B's project (org ORG_B)
    p0: str  # a project with no recorded owner
    ma: str = ""  # value milestone in pa
    mb: str = ""  # value milestone in pb
    m0: str = ""  # value milestone in p0
    tokens: dict[str, str] = field(default_factory=dict)

    def h(self, user: str) -> dict[str, str]:
        if user not in self.tokens:
            self.tokens[user] = _token(user)
        return {"Authorization": f"Bearer {self.tokens[user]}"}


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> World:
    # Production auth: no anonymous development principal, invalid tokens are 401.
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    assert vars(access)["settings"] is config.settings
    assert vars(auth)["settings"] is config.settings
    assert config.settings.SUPABASE_JWT_SECRET == TEST_JWT_SECRET

    store = InMemoryStore()
    monkeypatch.setattr(deps, "_store", store)
    assert deps.get_store() is store

    db = FakeSupabase()
    monkeypatch.setattr(organizations, "_get_supabase", lambda: db)
    assert organizations._get_supabase() is db

    def seed_project(owner: str | None) -> str:
        return str(store.add(XERReader(FIXTURES / "sample.xer").parse(), b"x", user_id=owner))

    w = World(
        client=TestClient(app),
        store=store,
        db=db,
        pa=seed_project(USER_A),
        pa2=seed_project(USER_A),
        pb=seed_project(USER_B),
        p0=seed_project(None),
    )
    assert store.get_project_owner(w.pa) == (True, USER_A)
    assert store.get_project_owner(w.p0) == (True, None)

    for user in NAMES:
        db.seed("user_profiles", **profile(user))
    db.seed("organizations", id=ORG_A, name="Org A", slug="org-a", org_type="owner")
    db.seed("organizations", id=ORG_B, name="Org B", slug="org-b", org_type="general")
    accepted = "2026-01-01T00:00:00+00:00"
    for org, user, role, when in (
        (ORG_A, USER_A, "owner", accepted),
        (ORG_A, ADMIN, "admin", accepted),
        (ORG_A, MEMBER, "member", accepted),
        (ORG_A, VIEWER, "viewer", accepted),
        (ORG_A, PENDING, "member", None),
        (ORG_B, USER_B, "owner", accepted),
        (ORG_B, MEMBER, "member", accepted),
    ):
        db.seed("memberships", org_id=org, user_id=user, role=role, accepted_at=when)
    # The org column of each project, as the projects table would hold it.
    db.seed("projects", id=w.pa, org_id=ORG_A, user_id=USER_A)
    db.seed("projects", id=w.pa2, org_id=ORG_A, user_id=USER_A)
    db.seed("projects", id=w.pb, org_id=ORG_B, user_id=USER_B)
    db.seed("projects", id=w.p0, org_id=None, user_id=None)

    def milestone(pid: str, org: str | None, notes: str) -> str:
        row = db.seed(
            "value_milestones",
            project_id=pid,
            org_id=org,
            task_code="M100",
            notes=notes,
            commercial_value=1000.0,
            created_by=USER_A,
        )
        return str(row["id"])

    w.ma = milestone(w.pa, ORG_A, "a-original")
    w.mb = milestone(w.pb, ORG_B, "b-original")
    w.m0 = milestone(w.p0, None, "ownerless-original")
    # A shared pa with ORG_B, where B is the owner.
    db.seed(
        "project_shares",
        project_id=w.pa,
        shared_with_org=ORG_B,
        permission="viewer",
        shared_by=USER_A,
    )
    db.seed("audit_log", org_id=ORG_A, user_id=USER_A, action="create", details={"k": "a-log"})
    db.seed("audit_log", org_id=ORG_B, user_id=USER_B, action="create", details={"k": "b-log"})
    db.log.clear()
    return w


def _get_org(w: World, user: str, org: str) -> Any:
    return w.client.get(f"/api/v1/organizations/{org}", headers=w.h(user))


def _list_orgs(w: World, user: str) -> list[tuple[str, str]]:
    resp = w.client.get("/api/v1/organizations", headers=w.h(user))
    _ok(resp, f"list organizations as {NAMES[user]}")
    return [(o["id"], o["role"]) for o in resp.json()["organizations"]]


def _invite(
    w: World,
    user: str,
    org: str,
    address: str,
    role: str = "member",
    headers: dict[str, str] | None = None,
) -> Any:
    return w.client.post(
        f"/api/v1/organizations/{org}/invite",
        json={"email": address, "role": role},
        headers={**w.h(user), **(headers or {})},
    )


def _accept(w: World, user: str, org: str) -> Any:
    return w.client.post(f"/api/v1/organizations/{org}/accept", headers=w.h(user))


def _remove(w: World, user: str, org: str, target: str) -> Any:
    return w.client.delete(f"/api/v1/organizations/{org}/members/{target}", headers=w.h(user))


def _member_ids(w: World, user: str, org: str) -> set[str]:
    resp = _get_org(w, user, org)
    _ok(resp, f"organization as {NAMES[user]}")
    return {m["user_id"] for m in resp.json()["members"]}


# ------------------------------------------------------------------ #
# Every organization route: members pass, everyone else is 404       #
# ------------------------------------------------------------------ #


@dataclass(frozen=True)
class OrgRoute:
    method: str
    path: str  # "{org}" is replaced by the organization under test
    body: dict[str, Any] | None = None
    managers_only: bool = True


ORG_ROUTES: dict[str, OrgRoute] = {
    "organization": OrgRoute("GET", "/api/v1/organizations/{org}", managers_only=False),
    "audit": OrgRoute("GET", "/api/v1/organizations/{org}/audit"),
    "invite": OrgRoute(
        "POST", "/api/v1/organizations/{org}/invite", {"email": email(NEWBIE), "role": "member"}
    ),
    "remove-member": OrgRoute("DELETE", "/api/v1/organizations/{org}/members/" + MEMBER),
}


def _org_call(w: World, route: OrgRoute, user: str | None, org: str) -> Any:
    headers = w.h(user) if user else None
    return w.client.request(
        route.method, route.path.format(org=org), json=route.body, headers=headers
    )


@pytest.mark.parametrize("name", list(ORG_ROUTES))
class TestEveryOrgRoute:
    def test_anonymous_is_rejected(self, world: World, name: str) -> None:
        """Negative control for the harness: production auth really is on."""
        assert _org_call(world, ORG_ROUTES[name], None, ORG_A).status_code == 401
        assert world.db.log == []

    def test_owner_reaches_own_org(self, world: World, name: str) -> None:
        _ok(_org_call(world, ORG_ROUTES[name], USER_A, ORG_A), f"{name} as A")

    def test_other_tenant_reaches_own_org(self, world: World, name: str) -> None:
        """B's token works, so B's 404 on ORG_A is the membership rule, not a broken B."""
        _ok(_org_call(world, ORG_ROUTES[name], USER_B, ORG_B), f"{name} as B")

    @pytest.mark.parametrize("outsider", [USER_B, PENDING, NEWBIE])
    def test_non_member_gets_not_found_identical_to_missing(
        self, world: World, name: str, outsider: str
    ) -> None:
        route = ORG_ROUTES[name]
        before = world.db.snapshot()

        foreign = _org_call(world, route, outsider, ORG_A)
        random_org = _org_call(world, route, outsider, str(uuid.uuid4()))
        malformed = _org_call(world, route, outsider, "not-a-uuid")

        for resp in (foreign, random_org, malformed):
            assert _answer(resp) == ORG_NOT_FOUND, resp.text
        assert world.db.writes() == []
        assert world.db.snapshot() == before
        # Only the membership lookup ran: nothing of ORG_A was read.
        assert {q.table for q in world.db.log} == {"memberships"}

    def test_role_gate(self, world: World, name: str) -> None:
        route = ORG_ROUTES[name]
        before = world.db.snapshot()
        resp = _org_call(world, route, VIEWER, ORG_A)
        if route.managers_only:
            assert resp.status_code == 403, resp.text
            assert world.db.writes() == []
            assert world.db.snapshot() == before
        else:
            _ok(resp, f"{name} as viewer")

    def test_membership_filter_is_sent(self, world: World, name: str) -> None:
        _org_call(world, ORG_ROUTES[name], USER_A, ORG_A)
        check = world.db.log[0]
        assert (check.table, check.op) == ("memberships", "select")
        assert check.has("eq", "org_id", ORG_A)
        assert check.has("eq", "user_id", USER_A)
        assert check.has("not.is", "accepted_at", "null")


# ------------------------------------------------------------------ #
# Listing and reading organizations                                  #
# ------------------------------------------------------------------ #


class TestListOrganizations:
    def test_only_accepted_memberships_are_listed(self, world: World) -> None:
        assert _list_orgs(world, USER_A) == [(ORG_A, "owner")]
        assert _list_orgs(world, USER_B) == [(ORG_B, "owner")]
        assert sorted(_list_orgs(world, MEMBER)) == sorted([(ORG_A, "member"), (ORG_B, "member")])
        assert _list_orgs(world, PENDING) == []

    def test_filters_are_sent(self, world: World) -> None:
        _list_orgs(world, PENDING)
        (query,) = world.db.log
        assert query.table == "memberships"
        assert query.has("eq", "user_id", PENDING)
        assert query.has("not.is", "accepted_at", "null")


class TestOrganizationDetail:
    def test_members_see_accepted_members_with_profiles(self, world: World) -> None:
        resp = _get_org(world, VIEWER, ORG_A)
        _ok(resp, "organization as viewer")
        members = {m["user_id"]: m for m in resp.json()["members"]}
        assert set(members) == {USER_A, ADMIN, MEMBER, VIEWER}
        # Control: profiles do reach members, so their absence below means something.
        assert members[MEMBER]["user_profiles"]["email"] == email(MEMBER)

    def test_pending_invitation_is_not_listed(self, world: World) -> None:
        resp = _get_org(world, USER_A, ORG_A)
        _ok(resp, "organization as A")
        for value in profile(PENDING).values():
            assert value not in resp.text

    def test_non_member_sees_nothing_of_the_org(self, world: World) -> None:
        resp = _get_org(world, USER_B, ORG_A)
        assert _answer(resp) == ORG_NOT_FOUND
        assert "Org A" not in resp.text
        for user in (USER_A, ADMIN, MEMBER, VIEWER, PENDING):
            assert email(user) not in resp.text
        assert [q.table for q in world.db.log] == ["memberships"]

    def test_uppercase_id_names_the_same_org(self, world: World) -> None:
        _ok(_get_org(world, USER_A, ORG_A.upper()), "organization by uppercase id")
        assert all(q.has("eq", "org_id", ORG_A) for q in world.db.queries("memberships"))
        assert _answer(_get_org(world, USER_B, ORG_A.upper())) == ORG_NOT_FOUND

    def test_member_list_filter_is_sent(self, world: World) -> None:
        _get_org(world, USER_A, ORG_A)
        _check, org_row, member_list = world.db.log
        assert org_row.table == "organizations" and org_row.has("eq", "id", ORG_A)
        assert member_list.table == "memberships"
        assert member_list.has("eq", "org_id", ORG_A)
        assert member_list.has("not.is", "accepted_at", "null")


# ------------------------------------------------------------------ #
# Invitations                                                        #
# ------------------------------------------------------------------ #


class TestInvite:
    @pytest.mark.parametrize("role", ["owner", "superuser", "", "Admin"])
    def test_role_is_a_closed_set(self, world: World, role: str) -> None:
        resp = _invite(world, USER_A, ORG_A, email(NEWBIE), role=role)
        assert resp.status_code == 422, resp.text
        assert world.db.log == []  # refused before any query

    @pytest.mark.parametrize("role", ["admin", "member", "viewer"])
    def test_invitable_roles(self, world: World, role: str) -> None:
        resp = _invite(world, ADMIN, ORG_A, email(NEWBIE), role=role)
        _ok(resp, f"invite as {role}")
        (row,) = world.db.rows("memberships", org_id=ORG_A, user_id=NEWBIE)
        assert row["role"] == role

    def test_answer_does_not_reveal_whether_an_account_exists(self, world: World) -> None:
        members_before = _get_org(world, USER_A, ORG_A).json()

        with_account = _invite(world, USER_A, ORG_A, email(NEWBIE))
        without_account = _invite(world, USER_A, ORG_A, NO_ACCOUNT_EMAIL)

        assert _answer(with_account) == (
            200,
            {"status": "invited", "email": email(NEWBIE), "role": "member"},
        )
        assert _answer(without_account) == (
            200,
            {"status": "invited", "email": NO_ACCOUNT_EMAIL, "role": "member"},
        )
        # Control: the address with an account did get a (pending) row.
        assert len(world.db.rows("memberships", user_id=NEWBIE)) == 1
        # The admin-visible trail is the same shape for both...
        invites = world.db.rows("audit_log", action="invite")
        assert [(e["entity_id"], sorted(e["details"])) for e in invites] == [
            (None, ["email", "role"]),
            (None, ["email", "role"]),
        ]
        # ...and so is the member list: the pending row is not shown.
        assert _get_org(world, USER_A, ORG_A).json() == members_before

    def test_invitation_is_pending_and_grants_nothing(self, world: World) -> None:
        _ok(_invite(world, USER_A, ORG_A, email(NEWBIE)), "invite")
        (row,) = world.db.rows("memberships", user_id=NEWBIE)
        assert (row["org_id"], row["accepted_at"], row["invited_by"]) == (ORG_A, None, USER_A)

        assert _answer(_get_org(world, NEWBIE, ORG_A)) == ORG_NOT_FOUND
        assert _list_orgs(world, NEWBIE) == []

    def test_reinviting_a_member_changes_nothing(self, world: World) -> None:
        before = world.db.rows("memberships")
        resp = _invite(world, USER_A, ORG_A, email(MEMBER), role="admin")
        assert _answer(resp) == (
            200,
            {"status": "invited", "email": email(MEMBER), "role": "admin"},
        )
        assert world.db.rows("memberships") == before

    def test_reinviting_a_pending_user_adds_no_row(self, world: World) -> None:
        before = world.db.rows("memberships")
        _ok(_invite(world, USER_A, ORG_A, email(PENDING)), "re-invite")
        assert world.db.rows("memberships") == before

    def test_address_is_normalised(self, world: World) -> None:
        resp = _invite(world, USER_A, ORG_A, "  Nadia@Example.TEST ")
        assert resp.json()["email"] == email(NEWBIE)
        assert len(world.db.rows("memberships", org_id=ORG_A, user_id=NEWBIE)) == 1


class TestAcceptInvitation:
    def test_invited_user_accepts_and_becomes_a_member(self, world: World) -> None:
        # Control: before accepting, the pending row grants nothing.
        assert _answer(_get_org(world, PENDING, ORG_A)) == ORG_NOT_FOUND

        resp = _accept(world, PENDING, ORG_A)
        assert _answer(resp) == (200, {"status": "accepted", "org_id": ORG_A, "role": "member"})
        _ok(_get_org(world, PENDING, ORG_A), "organization after accepting")
        assert PENDING in _member_ids(world, USER_A, ORG_A)
        assert (ORG_A, "member") in _list_orgs(world, PENDING)

    def test_invite_then_accept(self, world: World) -> None:
        _ok(_invite(world, ADMIN, ORG_A, email(NEWBIE), role="viewer"), "invite")
        assert NEWBIE not in _member_ids(world, USER_A, ORG_A)
        _ok(_accept(world, NEWBIE, ORG_A), "accept")
        assert NEWBIE in _member_ids(world, USER_A, ORG_A)

    def test_nobody_else_can_accept(self, world: World) -> None:
        before = world.db.snapshot()

        foreign = _accept(world, USER_B, ORG_A)
        random_org = _accept(world, USER_B, str(uuid.uuid4()))
        malformed = _accept(world, USER_B, "not-a-uuid")

        for resp in (foreign, random_org, malformed):
            assert _answer(resp) == INVITATION_NOT_FOUND, resp.text
        assert world.db.snapshot() == before
        (pending,) = world.db.rows("memberships", user_id=PENDING)
        assert pending["accepted_at"] is None
        # The update can only ever reach the caller's own pending row.
        updates = [q for q in world.db.log if q.op == "update"]
        assert len(updates) == 2  # the malformed id sends nothing
        for q in updates:
            assert q.table == "memberships"
            assert q.has("eq", "user_id", USER_B)
            assert q.has("is", "accepted_at", "null")

    def test_accepted_member_has_nothing_to_accept(self, world: World) -> None:
        before = world.db.rows("memberships")
        assert _answer(_accept(world, USER_A, ORG_A)) == INVITATION_NOT_FOUND
        assert world.db.rows("memberships") == before

    def test_anonymous_is_rejected(self, world: World) -> None:
        assert world.client.post(f"/api/v1/organizations/{ORG_A}/accept").status_code == 401


# ------------------------------------------------------------------ #
# Removing members                                                   #
# ------------------------------------------------------------------ #


class TestRemoveMember:
    def test_admin_removes_member_of_this_org_only(self, world: World) -> None:
        _ok(_remove(world, ADMIN, ORG_A, MEMBER), "remove as admin")
        assert world.db.rows("memberships", org_id=ORG_A, user_id=MEMBER) == []
        # The same user's membership elsewhere is untouched.
        assert len(world.db.rows("memberships", org_id=ORG_B, user_id=MEMBER)) == 1
        (delete,) = [q for q in world.db.log if q.op == "delete"]
        assert delete.has("eq", "org_id", ORG_A) and delete.has("eq", "user_id", MEMBER)

    def test_admin_cannot_remove_an_owner(self, world: World) -> None:
        before = world.db.rows("memberships")
        resp = _remove(world, ADMIN, ORG_A, USER_A)
        assert resp.status_code == 403, resp.text
        assert world.db.rows("memberships") == before

    def test_owner_removes_admin(self, world: World) -> None:
        _ok(_remove(world, USER_A, ORG_A, ADMIN), "remove as owner")
        assert world.db.rows("memberships", org_id=ORG_A, user_id=ADMIN) == []

    def test_admin_revokes_pending_invitation(self, world: World) -> None:
        _ok(_remove(world, ADMIN, ORG_A, PENDING), "revoke")
        assert world.db.rows("memberships", org_id=ORG_A, user_id=PENDING) == []

    def test_malformed_member_id_writes_nothing(self, world: World) -> None:
        _ok(_remove(world, USER_A, ORG_A, "not-a-uuid"), "remove malformed")
        assert world.db.writes() == []

    def test_other_tenant_cannot_remove_the_owner(self, world: World) -> None:
        before = world.db.snapshot()
        assert _answer(_remove(world, USER_B, ORG_A, USER_A)) == ORG_NOT_FOUND
        assert world.db.snapshot() == before
        # Read back as the owner: the org still has its owner.
        assert USER_A in _member_ids(world, USER_A, ORG_A)


# ------------------------------------------------------------------ #
# Audit trail                                                        #
# ------------------------------------------------------------------ #


class TestAuditLog:
    def test_entries_are_scoped_to_the_org(self, world: World) -> None:
        resp = world.client.get(f"/api/v1/organizations/{ORG_A}/audit", headers=world.h(ADMIN))
        _ok(resp, "audit as admin")
        entries = resp.json()["entries"]
        assert entries and {e["org_id"] for e in entries} == {ORG_A}
        assert "b-log" not in resp.text
        (query,) = world.db.queries("audit_log")
        assert query.has("eq", "org_id", ORG_A)

    def test_member_role_is_forbidden(self, world: World) -> None:
        resp = world.client.get(f"/api/v1/organizations/{ORG_A}/audit", headers=world.h(MEMBER))
        assert resp.status_code == 403, resp.text
        assert world.db.queries("audit_log") == []


class TestAuditTrailAddress:
    def _recorded_ip(self, world: World) -> Any:
        (row,) = world.db.rows("audit_log", action="invite")
        return row["ip_address"]

    def test_client_supplied_forwarded_for_is_not_recorded(self, world: World) -> None:
        spoof = {"X-Forwarded-For": "6.6.6.6, 203.0.113.7", "X-Real-IP": "6.6.6.6"}
        _ok(_invite(world, USER_A, ORG_A, email(NEWBIE), headers=spoof), "invite")
        assert self._recorded_ip(world) == "203.0.113.7"

    def test_fly_client_ip_wins(self, world: World) -> None:
        headers = {"Fly-Client-IP": "198.51.100.5", "X-Forwarded-For": "6.6.6.6, 203.0.113.7"}
        _ok(_invite(world, USER_A, ORG_A, email(NEWBIE), headers=headers), "invite")
        assert self._recorded_ip(world) == "198.51.100.5"


# ------------------------------------------------------------------ #
# Project shares                                                     #
# ------------------------------------------------------------------ #


def _share(w: World, user: str, project: str, org: str, permission: str = "viewer") -> Any:
    body = {"project_id": project, "shared_with_org_id": org, "permission": permission}
    return w.client.post("/api/v1/shares/project", json=body, headers=w.h(user))


def _shares(w: World, user: str, project: str) -> Any:
    return w.client.get(f"/api/v1/shares/project/{project}", headers=w.h(user))


class TestProjectShares:
    def test_owner_shares_own_project(self, world: World) -> None:
        resp = _share(world, USER_A, world.pa2, ORG_B, "editor")
        assert _answer(resp) == (200, {"status": "shared", "permission": "editor"})
        (row,) = world.db.rows("project_shares", project_id=world.pa2)
        assert (row["shared_with_org"], row["shared_by"]) == (ORG_B, USER_A)

    def test_other_tenant_cannot_share_a_foreign_project(self, world: World) -> None:
        before = world.db.snapshot()

        foreign = _share(world, USER_B, world.pa, ORG_B, "admin")
        random_id = _share(world, USER_B, str(uuid.uuid4()), ORG_B, "admin")
        legacy_id = _share(world, USER_B, "proj-9999", ORG_B, "admin")
        ownerless = _share(world, USER_B, world.p0, ORG_B, "admin")

        for resp in (foreign, random_id, legacy_id, ownerless):
            assert _answer(resp) == NOT_FOUND, resp.text
        assert world.db.log == []  # nothing read or written in Supabase
        assert world.db.snapshot() == before
        # Read back as the owner: the only share of pa is still A's viewer share.
        assert [
            (s["shared_with_org"], s["permission"])
            for s in _shares(world, USER_A, world.pa).json()["shares"]
        ] == [(ORG_B, "viewer")]

    def test_project_is_checked_before_the_target_org(self, world: World) -> None:
        assert _answer(_share(world, USER_B, world.pa, "not-an-org")) == NOT_FOUND
        assert _answer(_share(world, USER_B, world.pa, str(uuid.uuid4()))) == NOT_FOUND

    def test_unknown_target_org(self, world: World) -> None:
        assert _answer(_share(world, USER_A, world.pa2, str(uuid.uuid4()))) == ORG_NOT_FOUND
        assert _answer(_share(world, USER_A, world.pa2, "not-an-org")) == ORG_NOT_FOUND
        assert world.db.writes() == []

    @pytest.mark.parametrize("permission", ["owner", "write", "", "VIEWER"])
    def test_permission_is_a_closed_set(self, world: World, permission: str) -> None:
        resp = _share(world, USER_A, world.pa2, ORG_B, permission)
        assert resp.status_code == 422, resp.text
        assert world.db.log == []

    def test_owner_lists_shares(self, world: World) -> None:
        resp = _shares(world, USER_A, world.pa)
        _ok(resp, "shares as A")
        assert [s["shared_with_org"] for s in resp.json()["shares"]] == [ORG_B]
        (query,) = world.db.queries("project_shares")
        assert query.has("eq", "project_id", world.pa)

    def test_other_tenant_lists_own_project(self, world: World) -> None:
        _ok(_shares(world, USER_B, world.pb), "shares as B")

    def test_other_tenant_cannot_list_shares(self, world: World) -> None:
        foreign = _shares(world, USER_B, world.pa)
        for resp in (
            foreign,
            _shares(world, USER_B, str(uuid.uuid4())),
            _shares(world, USER_B, "proj-9999"),
            _shares(world, USER_B, world.p0),
        ):
            assert _answer(resp) == NOT_FOUND, resp.text
        assert world.db.queries("project_shares") == []

    def test_a_share_grants_no_read(self, world: World) -> None:
        """ADR-0030 §4: B owns the org pa is shared with, and still cannot reach pa."""
        assert world.db.rows("project_shares", project_id=world.pa, shared_with_org=ORG_B)
        (b_in_org_b,) = world.db.rows("memberships", org_id=ORG_B, user_id=USER_B)
        assert b_in_org_b["accepted_at"] is not None

        assert _answer(_shares(world, USER_B, world.pa)) == NOT_FOUND
        milestones = world.client.get(
            f"/api/v1/projects/{world.pa}/value-milestones", headers=world.h(USER_B)
        )
        assert _answer(milestones) == NOT_FOUND


# ------------------------------------------------------------------ #
# Value milestones                                                   #
# ------------------------------------------------------------------ #


def _milestones(w: World, user: str, project: str) -> Any:
    return w.client.get(f"/api/v1/projects/{project}/value-milestones", headers=w.h(user))


def _create(w: World, user: str, path_project: str, body_project: str, notes: str) -> Any:
    body = {"project_id": body_project, "task_code": "M200", "notes": notes}
    return w.client.post(
        f"/api/v1/projects/{path_project}/value-milestones", json=body, headers=w.h(user)
    )


def _update(w: World, user: str, milestone: str, body: dict[str, Any]) -> Any:
    return w.client.put(f"/api/v1/value-milestones/{milestone}", json=body, headers=w.h(user))


def _notes(w: World, user: str, project: str) -> list[str]:
    resp = _milestones(w, user, project)
    _ok(resp, f"milestones as {NAMES[user]}")
    return [m["notes"] for m in resp.json()["milestones"]]


class TestValueMilestoneReads:
    def test_owner_lists_own_milestones(self, world: World) -> None:
        assert _notes(world, USER_A, world.pa) == ["a-original"]
        (query,) = world.db.queries("value_milestones")
        assert query.has("eq", "project_id", world.pa)

    def test_other_tenant_lists_own_milestones(self, world: World) -> None:
        assert _notes(world, USER_B, world.pb) == ["b-original"]

    def test_other_tenant_gets_not_found_identical_to_missing(self, world: World) -> None:
        for resp in (
            _milestones(world, USER_B, world.pa),
            _milestones(world, USER_B, str(uuid.uuid4())),
            _milestones(world, USER_B, "proj-9999"),
            _milestones(world, USER_A, world.p0),
        ):
            assert _answer(resp) == NOT_FOUND, resp.text
        assert world.db.log == []  # authorized before any milestone query


class TestValueMilestoneCreate:
    def test_owner_creates(self, world: World) -> None:
        _ok(_create(world, USER_A, world.pa, world.pa, "a-new"), "create as A")
        assert _notes(world, USER_A, world.pa) == ["a-original", "a-new"]
        (row,) = world.db.rows("value_milestones", notes="a-new")
        assert (row["project_id"], row["org_id"], row["created_by"]) == (world.pa, ORG_A, USER_A)

    def test_other_tenant_cannot_create_in_a_foreign_project(self, world: World) -> None:
        before = world.db.snapshot()
        random_id = str(uuid.uuid4())

        for resp in (
            _create(world, USER_B, world.pa, world.pa, "b-injected"),
            _create(world, USER_B, random_id, random_id, "b-injected"),
            _create(world, USER_B, world.p0, world.p0, "b-injected"),
        ):
            assert _answer(resp) == NOT_FOUND, resp.text
        assert world.db.log == []
        assert world.db.snapshot() == before
        assert _notes(world, USER_A, world.pa) == ["a-original"]

    def test_foreign_project_in_the_body_is_not_found(self, world: World) -> None:
        # Control: B may create in B's own project.
        _ok(_create(world, USER_B, world.pb, world.pb, "b-own"), "create as B")
        world.db.log.clear()

        resp = _create(world, USER_B, world.pb, world.pa, "b-injected")
        assert _answer(resp) == NOT_FOUND
        assert world.db.writes() == []
        assert _notes(world, USER_A, world.pa) == ["a-original"]

    def test_body_project_must_match_the_path(self, world: World) -> None:
        resp = _create(world, USER_A, world.pa, world.pa2, "a-mismatch")
        assert resp.status_code == 422, resp.text
        assert world.db.writes() == []


class TestValueMilestoneUpdate:
    def test_owner_updates(self, world: World) -> None:
        resp = _update(world, USER_A, world.ma, {"notes": "a-revised"})
        _ok(resp, "update as A")
        assert resp.json()["milestone"]["notes"] == "a-revised"
        (write,) = world.db.writes()
        assert write.has("eq", "id", world.ma) and write.has("eq", "project_id", world.pa)

    def test_other_tenant_gets_not_found_identical_to_missing(self, world: World) -> None:
        before = world.db.snapshot()
        attack = {"notes": "pwned", "commercial_value": 1.0, "status": "achieved"}

        for resp in (
            _update(world, USER_B, world.ma, attack),
            _update(world, USER_B, str(uuid.uuid4()), attack),
            _update(world, USER_B, "not-a-uuid", attack),
            _update(world, USER_A, world.m0, attack),  # ownerless project
        ):
            assert _answer(resp) == MILESTONE_NOT_FOUND, resp.text
        assert world.db.writes() == []
        assert world.db.snapshot() == before
        assert _notes(world, USER_A, world.pa) == ["a-original"]

    def test_cannot_move_into_a_foreign_project(self, world: World) -> None:
        resp = _update(world, USER_B, world.mb, {"project_id": world.pa, "notes": "moved"})
        assert _answer(resp) == NOT_FOUND
        assert world.db.writes() == []
        assert _notes(world, USER_B, world.pb) == ["b-original"]
        assert _notes(world, USER_A, world.pa) == ["a-original"]

    def test_cannot_move_between_own_projects(self, world: World) -> None:
        resp = _update(world, USER_A, world.ma, {"project_id": world.pa2, "notes": "moved"})
        assert resp.status_code == 422, resp.text
        assert world.db.writes() == []
        assert _notes(world, USER_A, world.pa) == ["a-original"]
        assert _notes(world, USER_A, world.pa2) == []

    def test_same_project_in_the_body_is_accepted(self, world: World) -> None:
        _ok(_update(world, USER_A, world.ma, {"project_id": world.pa, "notes": "same"}), "update")
        (row,) = world.db.rows("value_milestones", id=world.ma)
        assert (row["project_id"], row["notes"]) == (world.pa, "same")

    def test_ownership_columns_are_not_writable(self, world: World) -> None:
        body = {"org_id": ORG_B, "created_by": USER_B, "id": str(uuid.uuid4()), "notes": "n"}
        _ok(_update(world, USER_A, world.ma, body), "update")
        (row,) = world.db.rows("value_milestones", id=world.ma)
        assert (row["org_id"], row["created_by"], row["notes"]) == (ORG_A, USER_A, "n")


# ------------------------------------------------------------------ #
# Production path: ownership comes from the same Supabase client      #
# ------------------------------------------------------------------ #


class TestWithSupabaseStore:
    PROJECT = "11111111-1111-4111-8111-111111111111"

    def test_owner_lookup_runs_before_any_milestone_query(
        self, world: World, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        supabase_store = SupabaseStore.__new__(SupabaseStore)
        supabase_store._client = world.db  # type: ignore[attr-defined]
        monkeypatch.setattr(deps, "_store", supabase_store)
        world.db.seed("projects", id=self.PROJECT, org_id=ORG_A, user_id=USER_A)
        world.db.seed("value_milestones", project_id=self.PROJECT, notes="supabase-a")

        assert _notes(world, USER_A, self.PROJECT) == ["supabase-a"]
        lookup, read = world.db.log
        assert (lookup.table, lookup.columns) == ("projects", "id,user_id")
        assert lookup.has("eq", "id", self.PROJECT)
        assert read.table == "value_milestones" and read.has("eq", "project_id", self.PROJECT)

        world.db.log.clear()
        assert _answer(_milestones(world, USER_B, self.PROJECT)) == NOT_FOUND
        assert [q.table for q in world.db.log] == ["projects"]
