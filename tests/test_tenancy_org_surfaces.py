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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

import src.api.deps as deps
from src.api import access, auth, organizations
from src.api.access import Principal
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

# (table, embedded resource) -> the local column that references ``<resource>.id``.
# Only embeds a real foreign key allows: PostgREST refuses the others
# (PGRST200). memberships and audit_log have no FK to user_profiles (both
# reference auth.users), so they are deliberately absent.
_EMBEDS: dict[tuple[str, str], str] = {
    ("memberships", "organizations"): "org_id",
    ("project_shares", "organizations"): "shared_with_org",
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
    op: str  # select | insert | upsert | update | delete | rpc
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
        self.ignore_duplicates = False
        self.cap: int | None = None

    def select(self, columns: str = "*") -> _Query:
        self.op, self.columns = "select", columns
        return self

    def insert(self, payload: Any) -> _Query:
        self.op, self.payload = "insert", payload
        return self

    def upsert(
        self, payload: Any, on_conflict: str = "", ignore_duplicates: bool = False
    ) -> _Query:
        self.op, self.payload, self.on_conflict = "upsert", payload, on_conflict
        self.ignore_duplicates = ignore_duplicates
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

    def gte(self, column: str, value: Any) -> _Query:
        return self._filter("gte", column, value)

    def in_(self, column: str, values: list[Any]) -> _Query:
        return self._filter("in", column, tuple(values))

    def limit(self, count: int) -> _Query:
        self.cap = count
        return self

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
            elif operator == "in":
                ok = row.get(column) in value
            elif operator == "gte":
                # Postgres compares timestamptz by instant, not by spelling.
                cell = row.get(column)
                ok = cell is not None and _instant(cell) >= _instant(value)
            else:  # pragma: no cover - the routes use only these operators
                raise AssertionError(f"unsupported operator {operator}")
            if not ok:
                return False
        return True

    def execute(self) -> Any:
        return type("Result", (), {"data": self._db.run(self)})()


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value)


class FakeSupabase:
    """Tables as lists of rows; every executed query is appended to ``log``."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.log: list[Emitted] = []
        self._clock = itertools.count(1)
        # Rows are stamped an hour ago plus one second per row: recent enough
        # for an open invitation, and in insertion order.
        self._epoch = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=1)

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    def rpc(self, name: str, params: dict[str, Any]) -> Any:
        db = self

        class _Call:
            def execute(self) -> Any:
                return type("Result", (), {"data": db.call(name, params)})()

        return _Call()

    def call(self, name: str, params: dict[str, Any]) -> Any:
        """The SQL functions the routes call, as migration 033 defines them."""
        self.log.append(Emitted(f"rpc:{name}", "rpc", None, (), copy.deepcopy(params)))
        assert name == "auth_user_id_for_email", f"unexpected rpc {name}"
        address = str(params["p_email"]).strip().lower()
        hits = [
            u
            for u in self.tables.get("auth.users", [])
            if str(u.get("email") or "").lower() == address
            and u.get("deleted_at") is None
            and u.get("email_confirmed_at") is not None
        ]
        return hits[0]["id"] if len(hits) == 1 else None

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
        return [q for q in self.log if q.op not in ("select", "rpc")]

    def queries(self, table: str) -> list[Emitted]:
        return [q for q in self.log if q.table == table]

    # -- execution ----------------------------------------------------
    def _tick(self) -> str:
        return (self._epoch + timedelta(seconds=next(self._clock))).isoformat()

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
            if q.cap is not None:
                hits = hits[: q.cap]
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
                if clash and q.op == "upsert" and q.ignore_duplicates and merges:
                    continue  # ON CONFLICT DO NOTHING
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
        db.seed(
            "auth.users",
            id=user,
            email=email(user),
            email_confirmed_at="2026-01-01T00:00:00+00:00",
            deleted_at=None,
        )
    db.seed("organizations", id=ORG_A, name="Org A", slug="org-a", org_type="owner")
    db.seed("organizations", id=ORG_B, name="Org B", slug="org-b", org_type="general")
    accepted = "2026-01-01T00:00:00+00:00"
    for org, user, role, when, inviter in (
        (ORG_A, USER_A, "owner", accepted, None),
        (ORG_A, ADMIN, "admin", accepted, USER_A),
        (ORG_A, MEMBER, "member", accepted, USER_A),
        (ORG_A, VIEWER, "viewer", accepted, USER_A),
        (ORG_A, PENDING, "member", None, ADMIN),
        (ORG_B, USER_B, "owner", accepted, None),
        (ORG_B, MEMBER, "member", accepted, USER_B),
    ):
        db.seed(
            "memberships",
            org_id=org,
            user_id=user,
            role=role,
            accepted_at=when,
            invited_by=inviter,
        )
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


def _revoke(w: World, user: str, org: str, address: str) -> Any:
    return w.client.post(
        f"/api/v1/organizations/{org}/invitations/revoke",
        json={"email": address},
        headers=w.h(user),
    )


def _invitations(w: World, user: str) -> list[tuple[str, str]]:
    resp = w.client.get("/api/v1/invitations", headers=w.h(user))
    _ok(resp, f"invitations as {NAMES[user]}")
    return [(i["org_id"], i["role"]) for i in resp.json()["invitations"]]


def _decline(w: World, user: str, org: str) -> Any:
    return w.client.post(f"/api/v1/organizations/{org}/decline", headers=w.h(user))


def _row(w: World, table: str, **match: Any) -> dict[str, Any]:
    """The live (mutable) row, for tests that change state behind the API."""
    (row,) = [r for r in w.db.tables[table] if all(r.get(k) == v for k, v in match.items())]
    return row


def _pending_row(w: World, user: str, org: str = ORG_A) -> dict[str, Any]:
    (row,) = w.db.rows("memberships", org_id=org, user_id=user)
    assert row["accepted_at"] is None
    return row


def _age(w: World, user: str, days: float, org: str = ORG_A) -> None:
    """Back-date the invitation of ``user`` to ``days`` ago."""
    (row,) = [r for r in w.db.tables["memberships"] if (r["org_id"], r["user_id"]) == (org, user)]
    row["created_at"] = (datetime.now(UTC) - timedelta(days=days)).isoformat()


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
    "revoke-invitation": OrgRoute(
        "POST", "/api/v1/organizations/{org}/invitations/revoke", {"email": email(PENDING)}
    ),
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
        _check, org_row, member_list, profiles = world.db.log
        assert org_row.table == "organizations" and org_row.has("eq", "id", ORG_A)
        assert member_list.table == "memberships"
        assert member_list.has("eq", "org_id", ORG_A)
        assert member_list.has("not.is", "accepted_at", "null")
        # Profiles are read for the listed members only, never the pending one.
        assert profiles.table == "user_profiles"
        assert profiles.has("in", "id", tuple(sorted([USER_A, ADMIN, MEMBER, VIEWER])))


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
        cases = {
            "new account": email(NEWBIE),
            "no account": NO_ACCOUNT_EMAIL,
            "pending": email(PENDING),
            "member": email(MEMBER),
        }

        answers = {case: _invite(world, USER_A, ORG_A, addr) for case, addr in cases.items()}

        for case, addr in cases.items():
            assert _answer(answers[case]) == (
                200,
                {"status": "requested", "email": addr, "role": "member"},
            ), case
        # Control: the address with an account did get a (pending) row.
        assert _pending_row(world, NEWBIE)["role"] == "member"
        # The admin-visible trail is the same for every case, and grants nothing.
        entries = world.db.rows("audit_log", org_id=ORG_A, user_id=USER_A)
        assert [(e["action"], e["entity_id"], e["details"]) for e in entries[1:]] == [
            ("invite_requested", None, {"email": addr, "requested_role": "member"})
            for addr in cases.values()
        ]
        # ...and so is the member list: the pending rows are not shown.
        assert _get_org(world, USER_A, ORG_A).json() == members_before

    def test_invitation_is_pending_and_grants_nothing(self, world: World) -> None:
        _ok(_invite(world, USER_A, ORG_A, email(NEWBIE)), "invite")
        row = _pending_row(world, NEWBIE)
        assert (row["org_id"], row["invited_by"]) == (ORG_A, USER_A)

        assert _answer(_get_org(world, NEWBIE, ORG_A)) == ORG_NOT_FOUND
        assert _list_orgs(world, NEWBIE) == []

    def test_reinviting_a_member_changes_nothing(self, world: World) -> None:
        before = world.db.rows("memberships")
        resp = _invite(world, USER_A, ORG_A, email(MEMBER), role="admin")
        assert _answer(resp) == (
            200,
            {"status": "requested", "email": email(MEMBER), "role": "admin"},
        )
        assert world.db.rows("memberships") == before
        assert [q for q in world.db.writes() if q.table == "memberships"] == []
        # The requested role is not recorded as granted anywhere.
        assert world.db.rows("audit_log", action="accept_invite") == []

    def test_reinviting_a_pending_user_reissues_the_invitation(self, world: World) -> None:
        _age(world, PENDING, days=10)
        stale = _pending_row(world, PENDING)
        assert (stale["role"], stale["invited_by"]) == ("member", ADMIN)

        _ok(_invite(world, USER_A, ORG_A, email(PENDING), role="viewer"), "re-invite")

        row = _pending_row(world, PENDING)
        assert (row["id"], row["role"], row["invited_by"]) == (stale["id"], "viewer", USER_A)
        assert _instant(row["created_at"]) > _instant(stale["created_at"])
        (update,) = [q for q in world.db.writes() if q.table == "memberships"]
        assert update.has("eq", "org_id", ORG_A) and update.has("eq", "user_id", PENDING)
        assert update.has("is", "accepted_at", "null")
        # What the invite answered is what the invited user gets.
        assert _answer(_accept(world, PENDING, ORG_A)) == (
            200,
            {"status": "accepted", "org_id": ORG_A, "role": "viewer"},
        )
        assert (ORG_A, "viewer") in _list_orgs(world, PENDING)

    def test_reissue_restarts_the_acceptance_window(self, world: World) -> None:
        _age(world, PENDING, days=20)
        assert _answer(_accept(world, PENDING, ORG_A)) == INVITATION_NOT_FOUND
        _ok(_invite(world, ADMIN, ORG_A, email(PENDING)), "re-invite")
        _ok(_accept(world, PENDING, ORG_A), "accept after re-invite")

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
        _pending_row(world, PENDING)
        # Nothing was written, and the lookups only ever named the caller.
        assert [q for q in world.db.log if q.op != "select"] == []
        lookups = world.db.queries("memberships")
        assert len(lookups) == 2  # the malformed id sends nothing
        for q in lookups:
            assert q.has("eq", "user_id", USER_B)
            assert q.has("is", "accepted_at", "null")

    def test_accept_sends_the_invitation_conditions(self, world: World) -> None:
        _ok(_accept(world, PENDING, ORG_A), "accept")
        (update,) = [q for q in world.db.log if q.op == "update"]
        assert update.has("eq", "org_id", ORG_A)
        assert update.has("eq", "user_id", PENDING)
        assert update.has("is", "accepted_at", "null")
        assert update.has("eq", "role", "member")
        assert update.has("eq", "invited_by", ADMIN)
        assert any(op == "gte" and col == "created_at" for op, col, _ in update.filters)

    def test_grant_is_recorded_at_acceptance(self, world: World) -> None:
        _ok(_accept(world, PENDING, ORG_A), "accept")
        (entry,) = world.db.rows("audit_log", action="accept_invite")
        assert (entry["org_id"], entry["user_id"], entry["entity_id"]) == (
            ORG_A,
            PENDING,
            PENDING,
        )
        assert entry["details"] == {"role": "member", "invited_by": ADMIN}

    def test_accepted_member_has_nothing_to_accept(self, world: World) -> None:
        before = world.db.rows("memberships")
        assert _answer(_accept(world, USER_A, ORG_A)) == INVITATION_NOT_FOUND
        assert world.db.rows("memberships") == before

    def test_anonymous_is_rejected(self, world: World) -> None:
        assert world.client.post(f"/api/v1/organizations/{ORG_A}/accept").status_code == 401


class TestInvitationLifecycle:
    def test_expired_invitation_cannot_be_accepted(self, world: World) -> None:
        _age(world, PENDING, days=15)
        before = world.db.snapshot()
        assert _answer(_accept(world, PENDING, ORG_A)) == INVITATION_NOT_FOUND
        assert world.db.snapshot() == before
        assert _answer(_get_org(world, PENDING, ORG_A)) == ORG_NOT_FOUND
        assert _invitations(world, PENDING) == []

    def test_invitation_within_the_window_is_accepted(self, world: World) -> None:
        """Control for the expiry test: 13 days is still open."""
        _age(world, PENDING, days=13)
        assert _invitations(world, PENDING) == [(ORG_A, "member")]
        _ok(_accept(world, PENDING, ORG_A), "accept at 13 days")

    def test_window_boundary(self, world: World) -> None:
        """Pins the TTL at 14 days: a minute either side decides it."""
        _age(world, PENDING, days=14 - 1 / 1440)
        assert _invitations(world, PENDING) == [(ORG_A, "member")]
        _age(world, PENDING, days=14 + 1 / 1440)
        assert _invitations(world, PENDING) == []
        assert _answer(_accept(world, PENDING, ORG_A)) == INVITATION_NOT_FOUND

    def test_removing_the_inviter_withdraws_their_invitations(self, world: World) -> None:
        _ok(_invite(world, USER_A, ORG_A, email(NEWBIE)), "invite by the owner")
        _ok(_remove(world, USER_A, ORG_A, ADMIN), "remove the admin")

        assert world.db.rows("memberships", org_id=ORG_A, user_id=PENDING) == []
        assert _answer(_accept(world, PENDING, ORG_A)) == INVITATION_NOT_FOUND
        # Control: an invitation someone else issued is untouched.
        _ok(_accept(world, NEWBIE, ORG_A), "accept the owner's invitation")

    def test_removal_withdraws_only_that_orgs_pending_invitations(self, world: World) -> None:
        world.db.seed(
            "memberships",
            org_id=ORG_B,
            user_id=NEWBIE,
            role="member",
            accepted_at=None,
            invited_by=MEMBER,
        )
        _ok(_remove(world, ADMIN, ORG_A, MEMBER), "remove marco from A")
        # MEMBER is still a member of ORG_B, and their invitation there stands.
        _pending_row(world, NEWBIE, org=ORG_B)

    def test_accepted_members_keep_their_seat_when_the_inviter_leaves(self, world: World) -> None:
        (viewer_row,) = [
            r
            for r in world.db.tables["memberships"]
            if (r["org_id"], r["user_id"]) == (ORG_A, VIEWER)
        ]
        viewer_row["invited_by"] = ADMIN  # ADMIN invited both VIEWER (accepted) and PENDING
        _ok(_remove(world, USER_A, ORG_A, ADMIN), "remove the admin")
        assert world.db.rows("memberships", org_id=ORG_A, user_id=PENDING) == []
        assert (ORG_A, "viewer") in _list_orgs(world, VIEWER)

    def test_inviter_no_longer_a_manager_closes_the_invitation(self, world: World) -> None:
        """The accept-time check, independent of the removal clean-up."""
        (admin_row,) = [
            r
            for r in world.db.tables["memberships"]
            if (r["org_id"], r["user_id"]) == (ORG_A, ADMIN)
        ]
        admin_row["role"] = "member"
        assert _invitations(world, PENDING) == []
        assert _answer(_accept(world, PENDING, ORG_A)) == INVITATION_NOT_FOUND
        _pending_row(world, PENDING)

    def test_inviter_whose_own_invitation_is_pending_does_not_count(self, world: World) -> None:
        (admin_row,) = [
            r
            for r in world.db.tables["memberships"]
            if (r["org_id"], r["user_id"]) == (ORG_A, ADMIN)
        ]
        admin_row["accepted_at"] = None
        assert _answer(_accept(world, PENDING, ORG_A)) == INVITATION_NOT_FOUND

    def test_invitation_without_an_issuer_is_not_open(self, world: World) -> None:
        (row,) = [
            r
            for r in world.db.tables["memberships"]
            if (r["org_id"], r["user_id"]) == (ORG_A, PENDING)
        ]
        row["invited_by"] = None
        assert _invitations(world, PENDING) == []
        assert _answer(_accept(world, PENDING, ORG_A)) == INVITATION_NOT_FOUND

    def test_reissue_between_check_and_write_leaves_the_row_pending(
        self, world: World, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Compare-and-set: the write carries the role and issuer that were checked."""
        checked = organizations._open_invitations

        def reissue_after_check(client: Any, user_id: str, org_id: Any = None) -> Any:
            open_now = checked(client, user_id, org_id)
            row = next(
                r
                for r in world.db.tables["memberships"]
                if (r["org_id"], r["user_id"]) == (ORG_A, PENDING)
            )
            row.update(role="admin", invited_by=USER_A)
            return open_now

        monkeypatch.setattr(organizations, "_open_invitations", reissue_after_check)
        assert _answer(_accept(world, PENDING, ORG_A)) == INVITATION_NOT_FOUND
        assert _pending_row(world, PENDING)["role"] == "admin"


class TestRevokeInvitation:
    def test_manager_revokes_a_pending_invitation(self, world: World) -> None:
        resp = _revoke(world, ADMIN, ORG_A, "  Paula@Example.TEST ")
        assert _answer(resp) == (200, {"status": "revoked", "email": email(PENDING)})
        assert world.db.rows("memberships", org_id=ORG_A, user_id=PENDING) == []
        assert _answer(_accept(world, PENDING, ORG_A)) == INVITATION_NOT_FOUND

    def test_accepted_member_is_not_touched(self, world: World) -> None:
        before = world.db.rows("memberships")
        _ok(_revoke(world, USER_A, ORG_A, email(MEMBER)), "revoke a member")
        assert world.db.rows("memberships") == before

    def test_only_this_orgs_invitation_is_revoked(self, world: World) -> None:
        world.db.seed(
            "memberships",
            org_id=ORG_B,
            user_id=PENDING,
            role="member",
            accepted_at=None,
            invited_by=USER_B,
        )
        _ok(_revoke(world, USER_A, ORG_A, email(PENDING)), "revoke in A")
        _pending_row(world, PENDING, org=ORG_B)
        (delete,) = [q for q in world.db.log if q.op == "delete"]
        assert delete.has("eq", "org_id", ORG_A)
        assert delete.has("eq", "user_id", PENDING)
        assert delete.has("is", "accepted_at", "null")

    def test_answer_is_the_same_in_every_case(self, world: World) -> None:
        cases = [email(PENDING), email(MEMBER), email(NEWBIE), NO_ACCOUNT_EMAIL]
        for addr in cases:
            assert _answer(_revoke(world, USER_A, ORG_A, addr)) == (
                200,
                {"status": "revoked", "email": addr},
            )
        entries = world.db.rows("audit_log", action="invite_revoked")
        assert [(e["entity_id"], e["details"]) for e in entries] == [
            (None, {"email": addr}) for addr in cases
        ]


class TestListInvitations:
    def test_invited_user_sees_their_open_invitation(self, world: World) -> None:
        resp = world.client.get("/api/v1/invitations", headers=world.h(PENDING))
        _ok(resp, "invitations as the invited user")
        (invitation,) = resp.json()["invitations"]
        assert (invitation["org_id"], invitation["org_name"], invitation["role"]) == (
            ORG_A,
            "Org A",
            "member",
        )

    @pytest.mark.parametrize("user", [USER_A, USER_B, MEMBER, NEWBIE])
    def test_nobody_else_sees_it(self, world: World, user: str) -> None:
        assert _invitations(world, user) == []
        for q in world.db.queries("memberships"):
            if q.has("is", "accepted_at", "null"):
                assert q.has("eq", "user_id", user)

    def test_anonymous_is_rejected(self, world: World) -> None:
        assert world.client.get("/api/v1/invitations").status_code == 401


class TestInvitationIdentity:
    """The invited person is resolved through auth.users, never user_profiles.email."""

    def test_profile_email_is_not_the_invitation_address(self, world: World) -> None:
        # A profile email that differs from the account's own address.
        _row(world, "user_profiles", id=USER_B)["email"] = "cfo@example.test"
        _ok(_invite(world, USER_A, ORG_A, "cfo@example.test", role="admin"), "invite")
        assert world.db.rows("memberships", org_id=ORG_A, user_id=USER_B) == []
        assert _invitations(world, USER_B) == []
        assert _answer(_accept(world, USER_B, ORG_A)) == INVITATION_NOT_FOUND

    def test_duplicate_profile_email_does_not_change_the_invitee(self, world: World) -> None:
        _row(world, "user_profiles", id=USER_B)["email"] = email(NEWBIE)
        _ok(_invite(world, USER_A, ORG_A, email(NEWBIE)), "invite")
        assert world.db.rows("memberships", org_id=ORG_A, user_id=USER_B) == []
        _pending_row(world, NEWBIE)

    def test_user_profiles_is_not_read(self, world: World) -> None:
        _ok(_invite(world, USER_A, ORG_A, email(NEWBIE)), "invite")
        _ok(_revoke(world, USER_A, ORG_A, email(NEWBIE)), "revoke")
        assert world.db.queries("user_profiles") == []
        calls = world.db.queries("rpc:auth_user_id_for_email")
        assert [c.payload for c in calls] == [{"p_email": email(NEWBIE)}] * 2

    def test_address_case_does_not_matter(self, world: World) -> None:
        _row(world, "auth.users", id=NEWBIE)["email"] = "Nadia@Example.Test"
        _ok(_invite(world, USER_A, ORG_A, "nadia@example.test"), "invite")
        _pending_row(world, NEWBIE)

    @pytest.mark.parametrize("state", ["unconfirmed", "deleted", "shared"])
    def test_address_without_exactly_one_confirmed_account_invites_nobody(
        self, world: World, state: str
    ) -> None:
        account = _row(world, "auth.users", id=NEWBIE)
        if state == "unconfirmed":
            account["email_confirmed_at"] = None
        elif state == "deleted":
            account["deleted_at"] = "2026-02-01T00:00:00+00:00"
        else:
            world.db.seed(
                "auth.users",
                id=str(uuid.uuid4()),
                email=email(NEWBIE).upper(),
                email_confirmed_at="2026-01-01T00:00:00+00:00",
                deleted_at=None,
            )
        before = world.db.rows("memberships")
        assert _answer(_invite(world, USER_A, ORG_A, email(NEWBIE))) == (
            200,
            {"status": "requested", "email": email(NEWBIE), "role": "member"},
        )
        assert world.db.rows("memberships") == before

    def test_concurrent_invite_of_the_same_address_is_not_an_error(
        self, world: World, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The existence check and the insert race: the insert must not raise."""
        real_run = world.db.run
        raced = []

        def run(q: Any) -> list[dict[str, Any]]:
            out = real_run(q)
            if not raced and q.table == "memberships" and q.op == "select":
                if ("eq", "user_id", NEWBIE) in q.filters:
                    raced.append(True)  # another request inserts right after our check
                    world.db.seed(
                        "memberships",
                        org_id=ORG_A,
                        user_id=NEWBIE,
                        role="viewer",
                        accepted_at=None,
                        invited_by=ADMIN,
                    )
            return out

        monkeypatch.setattr(world.db, "run", run)
        _ok(_invite(world, USER_A, ORG_A, email(NEWBIE), role="admin"), "racing invite")
        assert raced
        assert _pending_row(world, NEWBIE)["role"] == "viewer"  # the first write stands
        (insert,) = [q for q in world.db.log if q.op == "upsert"]
        assert insert.payload["user_id"] == NEWBIE


class TestSessionOnly:
    @pytest.mark.parametrize("kind", ["api_key"])
    def test_invitations_are_not_answered_with_an_api_key(self, kind: str) -> None:
        with pytest.raises(organizations.HTTPException) as refused:
            organizations._session_caller(Principal(PENDING, kind))  # type: ignore[arg-type]
        assert refused.value.status_code == 403

    def test_session_user_passes(self) -> None:
        caller = Principal(PENDING, "user")
        assert organizations._session_caller(caller) is caller

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/invitations"),
            ("POST", "/organizations/{org_id}/accept"),
            ("POST", "/organizations/{org_id}/decline"),
            ("POST", "/organizations/{org_id}/invite"),
            ("POST", "/organizations/{org_id}/invitations/revoke"),
            ("DELETE", "/organizations/{org_id}/members/{member_user_id}"),
        ],
    )
    def test_routes_use_the_session_dependency(self, method: str, path: str) -> None:
        (route,) = [
            r
            for r in organizations.router.routes
            if getattr(r, "path", None) == "/api/v1" + path and method in getattr(r, "methods", ())
        ]
        deps = {d.call for d in route.dependant.dependencies}  # type: ignore[attr-defined]
        assert organizations._session_caller in deps


class TestAcceptExpectedRole:
    def test_other_role_is_not_accepted(self, world: World) -> None:
        resp = world.client.post(
            f"/api/v1/organizations/{ORG_A}/accept",
            json={"role": "viewer"},
            headers=world.h(PENDING),
        )
        assert _answer(resp) == INVITATION_NOT_FOUND
        _pending_row(world, PENDING)

    def test_shown_role_is_accepted(self, world: World) -> None:
        resp = world.client.post(
            f"/api/v1/organizations/{ORG_A}/accept",
            json={"role": "member"},
            headers=world.h(PENDING),
        )
        assert _answer(resp) == (200, {"status": "accepted", "org_id": ORG_A, "role": "member"})


class TestDeclineInvitation:
    def test_invitee_declines(self, world: World) -> None:
        assert _answer(_decline(world, PENDING, ORG_A)) == (
            200,
            {"status": "declined", "org_id": ORG_A},
        )
        assert world.db.rows("memberships", org_id=ORG_A, user_id=PENDING) == []
        (entry,) = world.db.rows("audit_log", action="decline_invite")
        assert (entry["org_id"], entry["user_id"], entry["details"]) == (
            None,
            PENDING,
            {"org_id": ORG_A},
        )

    def test_decline_is_not_shown_to_the_organization(self, world: World) -> None:
        _ok(_decline(world, PENDING, ORG_A), "decline")
        resp = world.client.get(f"/api/v1/organizations/{ORG_A}/audit", headers=world.h(USER_A))
        _ok(resp, "audit as owner")
        assert PENDING not in resp.text
        for value in profile(PENDING).values():
            assert value not in resp.text

    def test_expired_invitation_can_still_be_declined(self, world: World) -> None:
        _age(world, PENDING, days=30)
        _ok(_decline(world, PENDING, ORG_A), "decline an expired invitation")
        assert world.db.rows("memberships", org_id=ORG_A, user_id=PENDING) == []

    @pytest.mark.parametrize("caller", [USER_B, MEMBER, USER_A])
    def test_nothing_else_is_declined(self, world: World, caller: str) -> None:
        before = world.db.snapshot()
        assert _answer(_decline(world, caller, ORG_A)) == INVITATION_NOT_FOUND
        assert _answer(_decline(world, caller, "not-a-uuid")) == INVITATION_NOT_FOUND
        assert world.db.snapshot() == before
        for q in world.db.writes():
            assert q.has("eq", "user_id", caller) and q.has("is", "accepted_at", "null")


class TestOrganizationInput:
    @pytest.mark.parametrize(
        "body",
        [
            {"name": "x" * 121},
            {"name": ""},
            {"name": "ok", "description": "d" * 2001},
            {"name": "ok", "org_type": "t" * 41},
        ],
    )
    def test_fields_are_capped(self, world: World, body: dict[str, str]) -> None:
        resp = world.client.post("/api/v1/organizations", json=body, headers=world.h(NEWBIE))
        assert resp.status_code == 422, resp.text
        assert world.db.log == []

    def test_fields_at_the_cap_are_accepted(self, world: World) -> None:
        body = {"name": "x" * 120, "description": "d" * 2000, "org_type": "t" * 40}
        resp = world.client.post("/api/v1/organizations", json=body, headers=world.h(NEWBIE))
        _ok(resp, "create at the caps")


class TestListingCost:
    def test_listing_is_capped_and_checks_issuers_in_one_query(self, world: World) -> None:
        for n in range(organizations.MAX_OPEN_INVITATIONS + 10):
            org = str(uuid.uuid4())
            owner = str(uuid.uuid4())
            world.db.seed("organizations", id=org, name=f"Org {n}", slug=f"o{n}", org_type="x")
            world.db.seed("memberships", org_id=org, user_id=owner, role="owner", accepted_at="t")
            world.db.seed(
                "memberships",
                org_id=org,
                user_id=NEWBIE,
                role="member",
                accepted_at=None,
                invited_by=owner,
            )
        world.db.log.clear()
        listed = _invitations(world, NEWBIE)
        assert len(listed) == organizations.MAX_OPEN_INVITATIONS
        _invites, seats = world.db.queries("memberships")
        # The issuer lookup is bounded by the listed organizations too.
        (org_filter,) = [f for f in seats.filters if f[:2] == ("in", "org_id")]
        assert len(org_filter[2]) == organizations.MAX_OPEN_INVITATIONS


# ------------------------------------------------------------------ #
# Removing members                                                   #
# ------------------------------------------------------------------ #


class TestRemoveMember:
    def test_admin_removes_member_of_this_org_only(self, world: World) -> None:
        _ok(_remove(world, ADMIN, ORG_A, MEMBER), "remove as admin")
        assert world.db.rows("memberships", org_id=ORG_A, user_id=MEMBER) == []
        # The same user's membership elsewhere is untouched.
        assert len(world.db.rows("memberships", org_id=ORG_B, user_id=MEMBER)) == 1
        issued, seat = [q for q in world.db.log if q.op == "delete"]
        assert seat.has("eq", "org_id", ORG_A) and seat.has("eq", "user_id", MEMBER)
        assert issued.has("eq", "org_id", ORG_A) and issued.has("eq", "invited_by", MEMBER)
        assert issued.has("is", "accepted_at", "null")

    def test_admin_cannot_remove_an_owner(self, world: World) -> None:
        before = world.db.rows("memberships")
        resp = _remove(world, ADMIN, ORG_A, USER_A)
        assert resp.status_code == 403, resp.text
        assert world.db.rows("memberships") == before

    def test_owner_removes_admin(self, world: World) -> None:
        _ok(_remove(world, USER_A, ORG_A, ADMIN), "remove as owner")
        assert world.db.rows("memberships", org_id=ORG_A, user_id=ADMIN) == []

    def test_last_owner_cannot_be_removed(self, world: World) -> None:
        before = world.db.snapshot()
        resp = _remove(world, USER_A, ORG_A, USER_A)
        assert _answer(resp) == (409, {"detail": "An organization must keep at least one owner"})
        assert world.db.snapshot() == before

    def test_an_owner_can_leave_when_another_owner_remains(self, world: World) -> None:
        _row(world, "memberships", org_id=ORG_A, user_id=ADMIN)["role"] = "owner"
        _ok(_remove(world, USER_A, ORG_A, USER_A), "owner leaves")
        assert world.db.rows("memberships", org_id=ORG_A, user_id=USER_A) == []

    def test_a_pending_owner_row_does_not_count_as_an_owner(self, world: World) -> None:
        world.db.seed("memberships", org_id=ORG_A, user_id=NEWBIE, role="owner", accepted_at=None)
        assert _remove(world, USER_A, ORG_A, USER_A).status_code == 409

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


class TestAuditLogInput:
    @pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1", "limit=abc"])
    def test_paging_is_bounded(self, world: World, query: str) -> None:
        resp = world.client.get(
            f"/api/v1/organizations/{ORG_A}/audit?{query}", headers=world.h(USER_A)
        )
        assert resp.status_code == 422, resp.text
        assert world.db.log == []

    def test_entries_carry_the_actor_profile(self, world: World) -> None:
        resp = world.client.get(f"/api/v1/organizations/{ORG_A}/audit", headers=world.h(USER_A))
        _ok(resp, "audit as owner")
        (entry,) = resp.json()["entries"]
        assert entry["user_profiles"] == {"email": email(USER_A), "full_name": "Alice Example"}
        profiles = world.db.queries("user_profiles")
        assert [q.filters for q in profiles] == [(("in", "id", (USER_A,)),)]


class TestAuditTrailAddress:
    def _recorded_ip(self, world: World) -> Any:
        (row,) = world.db.rows("audit_log", action="invite_requested")
        return row["ip_address"]

    def test_client_supplied_forwarded_for_is_not_recorded(
        self, world: World, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TRUSTED_CLIENT_IP_HEADER", "x-forwarded-for")
        spoof = {"X-Forwarded-For": "6.6.6.6, 203.0.113.7", "X-Real-IP": "6.6.6.6"}
        _ok(_invite(world, USER_A, ORG_A, email(NEWBIE), headers=spoof), "invite")
        assert self._recorded_ip(world) == "203.0.113.7"

    def test_fly_client_ip_on_fly(self, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRUSTED_CLIENT_IP_HEADER", "fly-client-ip")
        headers = {"Fly-Client-IP": "198.51.100.5", "X-Forwarded-For": "6.6.6.6, 203.0.113.7"}
        _ok(_invite(world, USER_A, ORG_A, email(NEWBIE), headers=headers), "invite")
        assert self._recorded_ip(world) == "198.51.100.5"

    def test_headers_are_ignored_without_a_trusted_proxy(
        self, world: World, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TRUSTED_CLIENT_IP_HEADER", raising=False)
        headers = {"Fly-Client-IP": "6.6.6.6", "X-Forwarded-For": "6.6.6.6"}
        _ok(_invite(world, USER_A, ORG_A, email(NEWBIE), headers=headers), "invite")
        assert self._recorded_ip(world) == "testclient"


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


class TestProjectOrganizationClaim:
    """A project's org_id counts only for members of that organization."""

    def _forged(self, world: World) -> str:
        # B's own project whose row names ORG_A, which B does not belong to.
        pid = str(world.store.add(XERReader(FIXTURES / "sample.xer").parse(), b"x", user_id=USER_B))
        world.db.seed("projects", id=pid, org_id=ORG_A, user_id=USER_B)
        world.db.log.clear()
        return pid

    def test_share_is_not_audited_into_a_foreign_org(self, world: World) -> None:
        pid = self._forged(world)
        before = world.db.rows("audit_log", org_id=ORG_A)
        _ok(_share(world, USER_B, pid, ORG_B), "share own project")
        assert world.db.rows("audit_log", org_id=ORG_A) == before
        (entry,) = [e for e in world.db.rows("audit_log", action="share") if e["entity_id"] == pid]
        assert entry["org_id"] is None

    def test_milestone_is_not_filed_under_a_foreign_org(self, world: World) -> None:
        pid = self._forged(world)
        before = world.db.rows("audit_log", org_id=ORG_A)
        resp = world.client.post(
            f"/api/v1/projects/{pid}/value-milestones",
            json={"project_id": pid, "task_code": "M1", "commercial_value": 1.0},
            headers=world.h(USER_B),
        )
        _ok(resp, "create milestone in own project")
        (row,) = [r for r in world.db.rows("value_milestones") if r["project_id"] == pid]
        assert row["org_id"] is None
        assert world.db.rows("audit_log", org_id=ORG_A) == before

    def test_a_pending_invitation_is_not_membership(self, world: World) -> None:
        pid = self._forged(world)
        world.db.seed(
            "memberships",
            org_id=ORG_A,
            user_id=USER_B,
            role="admin",
            accepted_at=None,
            invited_by=USER_A,
        )
        _ok(_share(world, USER_B, pid, ORG_B), "share own project")
        (entry,) = [e for e in world.db.rows("audit_log", action="share") if e["entity_id"] == pid]
        assert entry["org_id"] is None

    def test_a_viewer_does_not_file_work_under_the_org(self, world: World) -> None:
        pid = str(world.store.add(XERReader(FIXTURES / "sample.xer").parse(), b"x", user_id=VIEWER))
        world.db.seed("projects", id=pid, org_id=ORG_A, user_id=VIEWER)
        _ok(_share(world, VIEWER, pid, ORG_B), "share own project as a viewer of ORG_A")
        (entry,) = [e for e in world.db.rows("audit_log", action="share") if e["entity_id"] == pid]
        assert entry["org_id"] is None

    @pytest.mark.parametrize("writer", [MEMBER, ADMIN])
    def test_writers_file_work_under_the_org(self, world: World, writer: str) -> None:
        """Control for the viewer case: member and admin roles are enough."""
        pid = str(world.store.add(XERReader(FIXTURES / "sample.xer").parse(), b"x", user_id=writer))
        world.db.seed("projects", id=pid, org_id=ORG_A, user_id=writer)
        _ok(_share(world, writer, pid, ORG_B), f"share own project as {NAMES[writer]} of ORG_A")
        (entry,) = [e for e in world.db.rows("audit_log", action="share") if e["entity_id"] == pid]
        assert entry["org_id"] == ORG_A

    def test_members_keep_their_org(self, world: World) -> None:
        """Control: a project in the caller's own organization is still filed there."""
        _ok(_share(world, USER_A, world.pa, ORG_B), "share as a member of ORG_A")
        (entry,) = [
            e for e in world.db.rows("audit_log", action="share") if e["entity_id"] == world.pa
        ]
        assert entry["org_id"] == ORG_A


class TestReshare:
    def test_sharing_again_updates_the_permission(self, world: World) -> None:
        _ok(_share(world, USER_A, world.pa, ORG_B, "editor"), "re-share as editor")
        (row,) = world.db.rows("project_shares", project_id=world.pa, shared_with_org=ORG_B)
        assert row["permission"] == "editor"
        (upsert,) = [q for q in world.db.log if q.op == "upsert"]
        assert upsert.payload["permission"] == "editor"


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
