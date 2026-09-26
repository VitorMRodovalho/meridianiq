# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Static checks on migration 034 (organization RLS rewrite).

These read the migrations' CONTENT and replay CREATE/DROP POLICY in file
order to derive the resulting policy set. They do not show the effect in a
database. The effect was exercised on local replicas with
``scripts/rls_replica/run.sh`` (postgres:17 with Supabase-style roles, and
Supabase's own image): it replays 001-034 and probes as anon, authenticated
and service_role, with a control arm that must first reproduce the
recursion, and runs the read-only ``034/preflight.sql`` and
``034/postcheck.sql`` against both a clean and a deliberately drifted
database.

Every detector below ships with a negative control that shows it can say
no, on the migrations before 034 or on synthetic migration text.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "034_org_rls_rewrite.sql"
REPLICA = ROOT / "scripts" / "rls_replica" / "run.sh"
PREFLIGHT = ROOT / "scripts" / "rls_replica" / "034" / "preflight.sql"
POSTCHECK = ROOT / "scripts" / "rls_replica" / "034" / "postcheck.sql"

# The 11 policies that read memberships, measured in production on
# 2026-09-26 (read-only, as authenticated), matching migrations 007/008/009.
LEGACY_MEMBERSHIP_POLICIES: frozenset[tuple[str, str]] = frozenset(
    {
        ("audit_log", "Members can view org audit log"),
        ("forensic_access_log", "Org admins can view forensic access logs"),
        ("forensic_timelines", "Users can view accessible timelines"),
        ("memberships", "Admins can manage memberships"),
        ("memberships", "Members can view org memberships"),
        ("organizations", "Members can view their organizations"),
        ("project_shares", "Org members can view shares"),
        ("projects", "Users can view accessible projects"),
        ("value_milestones", "Org admins can manage value milestones"),
        ("value_milestones", "Org admins can update value milestones"),
        ("value_milestones", "Org members can view value milestones"),
    }
)

ORG_TABLES = (
    "organizations",
    "memberships",
    "project_shares",
    "program_shares",
    "audit_log",
    "forensic_access_log",
    "value_milestones",
)

_NAME = r'(?:"(?P<{g}q>[^"]+)"|(?P<{g}u>[a-z_][a-z0-9_]*))'
_CREATE_POLICY = re.compile(
    r"create\s+policy\s+"
    + _NAME.format(g="c")
    + r"\s+on\s+(?:public\.)?(?P<ctable>[a-z_][a-z0-9_]*)(?P<rest>.*?);",
    re.IGNORECASE | re.DOTALL,
)
_DROP_POLICY = re.compile(
    r"drop\s+policy\s+(?:if\s+exists\s+)?"
    + _NAME.format(g="d")
    + r"\s+on\s+(?:public\.)?(?P<dtable>[a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
_CREATE_TABLE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
_FROM_OR_JOIN = re.compile(r"\b(?:from|join)\s+(?:public\.)?([a-z_][a-z0-9_]*)", re.IGNORECASE)


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", "", sql)


def _sql() -> str:
    return _strip_comments(MIGRATION.read_text(encoding="utf-8"))


def _normalised() -> str:
    return re.sub(r"\s+", " ", _sql()).lower()


def _files(upto: str) -> list[Path]:
    """Migration files whose name sorts before ``upto`` (e.g. ``"034_"``)."""
    return [p for p in sorted(MIGRATIONS.glob("*.sql")) if p.name < upto]


class Policy:
    def __init__(self, table: str, name: str, rest: str) -> None:
        self.table = table
        self.name = name
        self.body = re.sub(r"\s+", " ", rest).strip().lower()
        cmd = re.search(r"\bfor\s+(select|insert|update|delete|all)\b", self.body)
        self.cmd = cmd.group(1) if cmd else "all"
        self.permissive = not re.search(r"\bas\s+restrictive\b", self.body)

    def references(self, tables: set[str]) -> set[str]:
        return {m.lower() for m in _FROM_OR_JOIN.findall(self.body)} & tables


def _replay(files: list[Path]) -> dict[tuple[str, str], Policy]:
    """Apply CREATE/DROP POLICY in file order; return the surviving policies."""
    state: dict[tuple[str, str], Policy] = {}
    for path in files:
        sql = _strip_comments(path.read_text(encoding="utf-8"))
        events = [(m.start(), "create", m) for m in _CREATE_POLICY.finditer(sql)]
        events += [(m.start(), "drop", m) for m in _DROP_POLICY.finditer(sql)]
        for _, kind, m in sorted(events, key=lambda e: e[0]):
            if kind == "create":
                name = m.group("cq") or m.group("cu").lower()
                table = m.group("ctable").lower()
                state[(table, name)] = Policy(table, name, m.group("rest"))
            else:
                name = m.group("dq") or m.group("du").lower()
                state.pop((m.group("dtable").lower(), name), None)
    return state


def _tables(files: list[Path]) -> set[str]:
    found: set[str] = set()
    for path in files:
        sql = _strip_comments(path.read_text(encoding="utf-8"))
        found |= {t.lower() for t in _CREATE_TABLE.findall(sql)}
    return found


def _reading_memberships(state: dict[tuple[str, str], Policy]) -> set[tuple[str, str]]:
    return {key for key, pol in state.items() if re.search(r"\bmemberships\b", pol.body)}


def _cycles(state: dict[tuple[str, str], Policy], tables: set[str]) -> list[list[str]]:
    """Cycles in the graph table -> tables its policies read (FROM/JOIN).

    A SECURITY DEFINER helper called from a policy is not an edge: it reads
    as its owner, which the migration requires to be exempt from RLS.
    """
    edges: dict[str, set[str]] = {}
    for pol in state.values():
        edges.setdefault(pol.table, set()).update(pol.references(tables))
    cycles: list[list[str]] = []
    for start in sorted(edges):
        stack: list[tuple[str, list[str]]] = [(start, [start])]
        while stack:
            node, path = stack.pop()
            for nxt in sorted(edges.get(node, ())):
                if nxt == start:
                    cycles.append([*path, nxt])
                elif nxt not in path and nxt > start:
                    stack.append((nxt, [*path, nxt]))
    return cycles


def _array_literal(pattern: str, sql: str | None = None) -> list[str]:
    """Quoted items of the ARRAY[...] that follows ``pattern`` (in 034 by default)."""
    text = _sql() if sql is None else sql
    match = re.search(pattern + r"\s*array\s*\[(.*?)\]", text, re.IGNORECASE | re.DOTALL)
    assert match, f"no ARRAY[...] after {pattern!r}"
    return re.findall(r"'([^']*)'", match.group(1))


_TABLE_LIST = r"v_tables\s+text\[\]\s*:="
_EXPECTED_LIST = r"v_expected\s+text\[\]\s*:="


def _034_policies() -> list[re.Match[str]]:
    return list(_CREATE_POLICY.finditer(_sql()))


# ── Transaction ─────────────────────────────────────────────────────────


def test_single_transaction_with_lock_timeout() -> None:
    statements = [s.strip() for s in _sql().split(";") if s.strip()]
    assert statements[0] == "BEGIN"
    assert statements[1].lower() == "set local lock_timeout = '5s'"
    assert statements[-1] == "COMMIT"


def test_postgrest_schema_cache_is_reloaded() -> None:
    assert "notify pgrst, 'reload schema';" in _normalised()


# ── Helper ──────────────────────────────────────────────────────────────


def test_helper_reads_accepted_memberships_of_the_caller() -> None:
    sql = _normalised()
    assert (
        "create or replace function private.is_org_member"
        "(p_org_id uuid, p_roles text[] default null)" in sql
    )
    assert "returns boolean language sql stable security definer set search_path = ''" in sql
    assert "from public.memberships as m" in sql
    assert "m.org_id = p_org_id" in sql
    assert "m.user_id = auth.uid()" in sql
    assert "m.accepted_at is not null" in sql
    assert "(p_roles is null or m.role = any (p_roles))" in sql


def _memberships_columns() -> set[str]:
    sql = _strip_comments((MIGRATIONS / "007_organizations.sql").read_text(encoding="utf-8"))
    block = re.search(r"create table if not exists memberships \((.*?)\n\);", sql, re.I | re.S)
    assert block, "007: CREATE TABLE memberships not found"
    columns = set()
    for line in block.group(1).splitlines():
        word = line.strip().split(" ", 1)[0].lower()
        if word and not word.startswith(("unique", "constraint", "primary", "foreign")):
            columns.add(word)
    return columns


def _helper_parameters() -> list[str]:
    match = re.search(r"function private\.is_org_member\((.*?)\)\s*returns", _normalised())
    assert match, "034: helper signature not found"
    return [part.strip().split(" ", 1)[0] for part in match.group(1).split(",")]


def _shadowed(parameters: list[str], columns: set[str]) -> set[str]:
    return set(parameters) & columns


def test_helper_parameters_do_not_shadow_memberships_columns() -> None:
    """In LANGUAGE sql a column wins over a parameter of the same name, which
    turns ``m.org_id = org_id`` into a tautology (measured on the replica:
    the shadowed helper answers true for an outsider and for a random id)."""
    columns = _memberships_columns()
    assert {"org_id", "user_id", "role", "accepted_at"} <= columns
    assert _helper_parameters() == ["p_org_id", "p_roles"]
    assert not _shadowed(_helper_parameters(), columns)


def test_shadowing_detector_negative_control() -> None:
    """The unprefixed names flag the column the helper compares against."""
    assert _shadowed(["org_id", "roles"], _memberships_columns()) == {"org_id"}


def test_helper_is_executable_by_authenticated_and_service_role_only() -> None:
    sql = _normalised()
    assert (
        "revoke all on function private.is_org_member(uuid, text[]) "
        "from public, anon, authenticated, service_role;" in sql
    )
    grants = re.findall(
        r"grant execute on function private\.is_org_member\(uuid, text\[\]\) to ([^;]+);", sql
    )
    assert grants == ["authenticated, service_role"]


def _exposes_private(sql: str) -> bool:
    """True when the text gives a client role USAGE on schema private."""
    return bool(
        re.search(
            r"grant\s+[^;]*\busage\b[^;]*\bon\s+schema\s+[^;]*\bprivate\b[^;]*\bto\s+[^;]*"
            r"\b(anon|authenticated|public)\b",
            sql,
            re.IGNORECASE,
        )
    )


def test_helper_lives_in_a_schema_clients_cannot_reach() -> None:
    """PostgREST serves functions of the exposed schemas as RPC endpoints;
    schema private is not exposed and client roles get no USAGE on it, so
    only the policies call the helper."""
    sql = _normalised()
    assert "create schema if not exists private;" in sql
    assert "raise exception 'migration 034: schema private is owned by %, expected postgres'" in sql
    assert (
        "raise exception 'migration 034: client roles have usage or create on schema private'"
        in sql
    )
    assert "public.is_org_member" not in sql
    calls = re.findall(r"using \(.*?is_org_member\(", sql)
    assert calls and all("private.is_org_member(" in c for c in calls)
    for path in sorted(MIGRATIONS.glob("*.sql")):
        assert not _exposes_private(_strip_comments(path.read_text(encoding="utf-8"))), path.name
    config = ROOT / "supabase" / "config.toml"
    if config.exists():
        assert not re.search(
            r"schemas\s*=\s*\[[^\]]*\"private\"", config.read_text(encoding="utf-8")
        )


def test_schema_exposure_detector_negative_control() -> None:
    assert _exposes_private("GRANT USAGE ON SCHEMA private TO authenticated;")
    assert not _exposes_private("GRANT USAGE ON SCHEMA private TO service_role;")


def test_helper_owner_is_checked_for_rls_exemption() -> None:
    sql = _normalised()
    assert "alter function private.is_org_member(uuid, text[]) owner to postgres;" in sql
    for marker in (
        "r.rolsuper or r.rolbypassrls",
        "c.relforcerowsecurity",
        "v_fn_owner = v_tbl_owner",
    ):
        assert marker in sql, marker


# ── Policies written by 034 ─────────────────────────────────────────────


def test_every_new_policy_is_select_to_authenticated() -> None:
    created = _034_policies()
    assert len(created) == 8
    for m in created:
        rest = re.sub(r"\s+", " ", m.group("rest")).strip().lower()
        assert rest.startswith("for select to authenticated using ("), (m.group("cu"), rest)


def test_every_new_policy_is_dropped_by_name_first() -> None:
    sql = _sql()
    for m in _034_policies():
        name, table = m.group("cu"), m.group("ctable")
        drop = re.search(
            rf"drop\s+policy\s+if\s+exists\s+{name}\s+on\s+public\.{table}\b", sql, re.I
        )
        assert drop and drop.start() < m.start(), (
            f"{table}.{name} is not dropped before it is created"
        )


def test_new_policy_names_were_never_used_before() -> None:
    """Re-running an earlier migration cannot drop or recreate them."""
    earlier = " ".join(
        _strip_comments(p.read_text(encoding="utf-8")).lower() for p in _files("034_")
    )
    for m in _034_policies():
        assert m.group("cu") not in earlier, m.group("cu")


def test_legacy_policies_are_dropped() -> None:
    sql = _sql()
    legacy = set(LEGACY_MEMBERSHIP_POLICIES) | {
        ("organizations", "Anyone can create an organization"),
        ("projects", "Users can view own projects"),
        ("forensic_timelines", "Users can view own timelines"),
    }
    for table, name in legacy:
        pattern = rf'drop\s+policy\s+if\s+exists\s+"{re.escape(name)}"\s+on\s+public\.{table}\s*;'
        assert re.search(pattern, sql, re.I), f"not dropped: {table}.{name}"


def test_projects_select_policy_is_owner_only() -> None:
    state = _replay(_files("035_"))
    selects = [p for p in state.values() if p.table == "projects" and p.cmd in ("select", "all")]
    assert [p.name for p in selects] == ["projects_select_owner"]
    assert selects[0].body == "for select to authenticated using ((select auth.uid()) = user_id)"


def _bare_uid_calls(policies: list[Policy]) -> set[str]:
    """Policies that call auth.uid() outside a scalar subquery, i.e. once per row."""
    return {
        f"{p.table}.{p.name}"
        for p in policies
        if len(re.findall(r"auth\.uid\(\)", p.body))
        != len(re.findall(r"\(select auth\.uid\(\)\)", p.body))
    }


def test_new_policies_evaluate_auth_uid_once_per_statement() -> None:
    created = [
        Policy(m.group("ctable").lower(), m.group("cu"), m.group("rest")) for m in _034_policies()
    ]
    assert sum("auth.uid()" in p.body for p in created) == 4
    assert _bare_uid_calls(created) == set()


def test_bare_uid_detector_negative_control() -> None:
    """The projects read policy of 007 calls auth.uid() once per row."""
    assert "projects.Users can view accessible projects" in _bare_uid_calls(
        list(_replay(_files("034_")).values())
    )


# ── Replayed policy state ───────────────────────────────────────────────


def test_no_policy_reads_memberships_after_034() -> None:
    assert _reading_memberships(_replay(sorted(MIGRATIONS.glob("*.sql")))) == set()


def test_replay_negative_control_finds_the_measured_policies_before_034() -> None:
    assert _reading_memberships(_replay(_files("034_"))) == LEGACY_MEMBERSHIP_POLICIES


def test_policy_graph_is_acyclic_after_034() -> None:
    tables = _tables(sorted(MIGRATIONS.glob("*.sql")))
    assert _cycles(_replay(sorted(MIGRATIONS.glob("*.sql"))), tables) == []


def test_cycle_detector_negative_control_before_034() -> None:
    """Before 034: memberships reads itself, and projects <-> project_shares."""
    cycles = _cycles(_replay(_files("034_")), _tables(_files("034_")))
    assert ["memberships", "memberships"] in cycles
    assert ["project_shares", "projects", "project_shares"] in cycles


def test_cycle_detector_sees_a_share_read_added_after_034() -> None:
    """A later migration whose projects policy reads project_shares closes
    the cycle again (project_shares' policy reads projects); the replay of
    all migration files catches it in CI."""
    state = _replay(sorted(MIGRATIONS.glob("*.sql")))
    state[("projects", "probe_shared_read")] = Policy(
        "projects",
        "probe_shared_read",
        "FOR SELECT TO authenticated USING (id IN (SELECT ps.project_id FROM project_shares ps))",
    )
    cycles = _cycles(state, _tables(sorted(MIGRATIONS.glob("*.sql"))))
    assert ["project_shares", "projects", "project_shares"] in cycles


# ── Privileges ──────────────────────────────────────────────────────────


def test_client_write_privileges_are_revoked_on_every_table() -> None:
    listed = _array_literal(_TABLE_LIST)
    assert len(listed) == len(set(listed))
    assert set(listed) == _tables(_files("034_"))
    sql = _normalised()
    assert "v_privs text := 'insert, update, delete, truncate, references, trigger';" in sql
    assert "v_privs := v_privs || ', maintain';" in sql
    assert "'revoke %s on table public.%i from public, anon, authenticated'" in sql
    assert "raise exception 'migration 034: tables missing from schema public: %'" in sql


def test_table_list_detector_negative_control() -> None:
    """The comparison would notice a table missing from the list."""
    listed = set(_array_literal(_TABLE_LIST))
    assert _tables(_files("034_")) != listed - {"activities"}


def test_default_privileges_of_postgres_drop_client_writes() -> None:
    """Supabase grants every table postgres creates in public to anon and
    authenticated; 034 removes the write privileges from that default."""
    sql = _normalised()
    assert (
        "execute format('alter default privileges for role postgres in schema public ' "
        "'revoke %s on tables from public, anon, authenticated', v_privs);" in sql
    )


_GRANTED_MEMBERSHIP_COLUMNS = ("org_id", "user_id", "role", "accepted_at")


def test_org_tables_are_select_only_for_authenticated() -> None:
    sql = _normalised()
    revoke = re.search(r"revoke all on table (.*?) from public, anon, authenticated;", sql)
    assert revoke
    assert [t.strip() for t in revoke.group(1).split(",")] == [f"public.{t}" for t in ORG_TABLES]
    grants = re.findall(r"grant ([a-z, ]+) on table (.*?) to ([^;]+);", sql)
    assert len(grants) == 1
    privilege, targets, grantee = grants[0]
    assert privilege == "select" and grantee == "authenticated"
    assert [t.strip() for t in targets.split(",")] == [
        f"public.{t}" for t in ORG_TABLES if t not in ("program_shares", "memberships")
    ]
    columns = re.findall(
        r"grant select \(([a-z_, ]+)\) on table public\.memberships to authenticated;", sql
    )
    assert [tuple(c.strip() for c in cols.split(",")) for cols in columns] == [
        _GRANTED_MEMBERSHIP_COLUMNS
    ]


def test_memberships_columns_granted_are_those_the_member_listing_returns() -> None:
    """The API lists members with ``select("user_id, role, accepted_at")``
    filtered by org_id; invited_by, created_at and id are not shown to
    members."""
    api = (ROOT / "src" / "api" / "organizations.py").read_text(encoding="utf-8")
    listing = re.search(
        r'def get_organization\(.*?table\("memberships"\)\s*\.select\("([^"]+)"\)\s*'
        r'\.eq\("org_id", org_id\)',
        api,
        re.DOTALL,
    )
    assert listing, "member listing query not found in src/api/organizations.py"
    listed = {c.strip() for c in listing.group(1).split(",")} | {"org_id"}
    assert listed == set(_GRANTED_MEMBERSHIP_COLUMNS)
    assert not listed & {"invited_by", "created_at", "id"}


# ── Tables and grants added after 034 ───────────────────────────────────

_WRITE_PRIVILEGES = frozenset({"insert", "update", "delete", "truncate"})
_CLIENTS = frozenset({"anon", "authenticated"})
_REVOKE = re.compile(
    r"\brevoke\s+(?P<privs>[^;]+?)\s+on\s+(?:table\s+)?(?P<tables>[^;]+?)\s+from\s+(?P<who>[^;]+);",
    re.IGNORECASE,
)
_GRANT = re.compile(
    r"\bgrant\s+(?P<privs>[^;]+?)\s+on\s+(?P<target>[^;]+?)\s+to\s+(?P<who>[^;]+);",
    re.IGNORECASE,
)


def _names(text: str) -> set[str]:
    return {re.sub(r"^public\.", "", t.strip().strip('"').lower()) for t in text.split(",")}


def _privileges(text: str) -> set[str]:
    words = {re.sub(r"\(.*?\)", "", w).strip().lower() for w in text.split(",")}
    if {"all", "all privileges"} & words:
        return set(_WRITE_PRIVILEGES)
    return words


def _unguarded_tables(migrations: list[tuple[str, str]]) -> set[str]:
    """Tables created in ``migrations`` (name, text) that no REVOKE in the
    same or a later one strips of INSERT, UPDATE, DELETE and TRUNCATE for
    both anon and authenticated."""
    created: list[tuple[int, str]] = []
    revoked: list[tuple[int, set[str], set[str], set[str]]] = []
    for index, (_, text) in enumerate(migrations):
        sql = _strip_comments(text)
        created += [(index, t.lower()) for t in _CREATE_TABLE.findall(sql)]
        for m in _REVOKE.finditer(sql):
            revoked.append(
                (
                    index,
                    _privileges(m.group("privs")),
                    _names(m.group("tables")),
                    _names(m.group("who")),
                )
            )
    # REVOKE ... FROM PUBLIC does not remove what was granted to anon or
    # authenticated by name (Supabase's default privileges do exactly that),
    # so only the two roles named explicitly count.
    unguarded = set()
    for index, table in created:
        stripped: dict[str, set[str]] = {c: set() for c in _CLIENTS}
        for r_index, privs, tables, who in revoked:
            if r_index >= index and (table in tables or "all tables in schema public" in tables):
                for client in _CLIENTS & who:
                    stripped[client] |= privs
        if any(not _WRITE_PRIVILEGES <= stripped[c] for c in _CLIENTS):
            unguarded.add(table)
    return unguarded


def _client_write_grants(text: str) -> list[str]:
    """GRANT statements that give PUBLIC, anon or authenticated a write
    privilege on a table (column-level included)."""
    found = []
    for m in _GRANT.finditer(_strip_comments(text)):
        target = m.group("target").strip().lower()
        if re.match(
            r"(function|procedure|routine|schema|sequence|type|database|language)\b", target
        ):
            continue
        if _privileges(m.group("privs")) & _WRITE_PRIVILEGES and _names(m.group("who")) & (
            _CLIENTS | {"public"}
        ):
            found.append(re.sub(r"\s+", " ", m.group(0)))
    return found


def _migrations_from(start: str) -> list[tuple[str, str]]:
    return [
        (p.name, p.read_text(encoding="utf-8"))
        for p in sorted(MIGRATIONS.glob("*.sql"))
        if p.name >= start
    ]


def test_tables_created_after_034_strip_client_writes() -> None:
    """Default privileges of supabase_admin still grant writes on tables it
    creates in public, and postgres cannot change them: every table a later
    migration creates must be followed by a REVOKE of the client writes."""
    assert _unguarded_tables(_migrations_from("035_")) == set()


def test_unguarded_table_detector_negative_control() -> None:
    create = ("035_probe.sql", "CREATE TABLE IF NOT EXISTS public.probe (id int);")

    def after(revoke: str) -> set[str]:
        return _unguarded_tables([create, ("036_probe.sql", revoke)])

    assert _unguarded_tables([create]) == {"probe"}
    assert after("REVOKE INSERT ON public.probe FROM anon, authenticated;") == {"probe"}
    assert after("REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.probe FROM anon;") == {"probe"}
    assert after("REVOKE ALL ON TABLE public.probe FROM PUBLIC;") == {"probe"}
    assert after("REVOKE ALL ON TABLE public.probe FROM PUBLIC, anon, authenticated;") == set()
    assert (
        after("REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON probe FROM anon, authenticated;") == set()
    )
    assert after("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;") == set()


def test_no_migration_from_034_grants_client_writes() -> None:
    for name, text in _migrations_from("034_"):
        assert _client_write_grants(text) == [], name


def test_client_write_grant_detector_negative_control() -> None:
    assert _client_write_grants("GRANT INSERT ON public.probe TO authenticated;")
    assert _client_write_grants("GRANT UPDATE (note) ON TABLE public.probe TO anon;")
    assert _client_write_grants("GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;")
    assert not _client_write_grants("GRANT SELECT ON public.probe TO authenticated;")
    assert not _client_write_grants("GRANT EXECUTE ON FUNCTION public.f() TO authenticated;")
    assert not _client_write_grants("GRANT INSERT ON public.probe TO service_role;")


# ── In-migration checks ─────────────────────────────────────────────────


def _affected(state: dict[tuple[str, str], Policy]) -> set[str]:
    reads = re.compile(r"\b(projects|organizations|project_shares|is_org_member)\b")
    return {p.table for p in state.values() if reads.search(p.body)}


def test_expected_read_policies_match_the_state_after_034() -> None:
    """The list 034 checks against equals the permissive SELECT/ALL policies
    that migrations 001-034 leave on the affected tables."""
    expected = set(_array_literal(_EXPECTED_LIST))
    state = _replay(_files("035_"))
    listed_tables = {e.split(".", 1)[0] for e in expected}
    tables = _affected(state) | listed_tables
    derived = {
        f"{p.table}.{p.name}"
        for p in state.values()
        if p.table in tables and p.permissive and p.cmd in ("select", "all")
    }
    assert expected == derived
    assert _affected(state) <= listed_tables


def test_checks_run_before_commit() -> None:
    sql = _normalised()
    markers = (
        # 5a
        r"~ '\mmemberships\m'",
        # 5b
        "p.permissive = 'permissive'",
        "p.cmd in ('select', 'all')",
        # 5c
        "has_any_column_privilege('authenticated', format('public.%i', v_table), 'select')",
        "set local role authenticated;",
        "execute format('explain select 1 from public.%i', v_table);",
        # 5d
        "c.relkind in ('r', 'p', 'v', 'm', 'f')",
        "has_table_privilege(r.role, c.oid, v_write)",
        "has_any_column_privilege(r.role, c.oid, 'insert, update, references')",
        "raise exception 'migration 034: client roles can write: %'",
        # 5e
        "o.option_name = 'security_invoker'",
        "(c.relkind in ('r', 'p') and not c.relrowsecurity)",
        "raise exception 'migration 034: client roles can read rows that rls does not filter: %'",
        # 5f
        "has_column_privilege('authenticated', a.attrelid, a.attnum, 'select')",
        "raise exception 'migration 034: unexpected client privileges on organization tables: %'",
        # 5g
        "d.defaclrole = 'postgres'::regrole",
        "raise exception 'migration 034: default privileges of postgres grant clients: %'",
    )
    for marker in markers:
        assert marker in sql, marker
        assert sql.index(marker) < sql.index("commit;"), marker
    assert _array_literal(r"v_org_tables\s+text\[\]\s*:=") == list(ORG_TABLES)


# ── Read-only census and post-apply checks ──────────────────────────────


def _read_only_violations(sql: str) -> list[str]:
    """Why ``sql`` is not a single read-only SELECT (empty when it is)."""
    text = re.sub(r"'(?:[^']|'')*'", "''", _strip_comments(sql))
    statements = [s.strip() for s in text.split(";") if s.strip()]
    problems = []
    if len(statements) != 1:
        problems.append(f"{len(statements)} statements")
    if statements and not re.match(r"(with|select)\b", statements[0], re.IGNORECASE):
        problems.append("does not start with WITH or SELECT")
    problems += sorted(
        {
            w.lower()
            for w in re.findall(
                r"\b(insert|update|delete|merge|create|alter|drop|grant|revoke|truncate|copy|"
                r"set|reset|call|do|begin|commit|lock|vacuum|analyze|notify)\b",
                text,
                re.IGNORECASE,
            )
        }
    )
    if "\\" in text:
        problems.append("psql meta-command")
    return problems


def test_census_and_postcheck_are_single_read_only_selects() -> None:
    """They are meant to be run against production as they are."""
    for path in (PREFLIGHT, POSTCHECK):
        assert _read_only_violations(path.read_text(encoding="utf-8")) == [], path.name


def test_read_only_detector_negative_control() -> None:
    assert _read_only_violations(MIGRATION.read_text(encoding="utf-8"))
    assert _read_only_violations("SELECT 1; SELECT 2;") == ["2 statements"]


_UNNEST_LIST = r"expected\(name\)\s+as\s*\(\s*select\s+unnest\s*\("


def _listed(path: Path, drop: str | None = None) -> list[str]:
    """The ARRAY in a census/postcheck file, optionally with one quoted entry removed."""
    text = path.read_text(encoding="utf-8")
    if drop is not None:
        assert f"'{drop}'," in text
        text = text.replace(f"'{drop}',", "", 1)
    return _array_literal(_UNNEST_LIST, _strip_comments(text))


def test_census_lists_the_tables_of_034() -> None:
    assert _listed(PREFLIGHT) == _array_literal(_TABLE_LIST)


def test_postcheck_expects_the_policies_of_034() -> None:
    assert _listed(POSTCHECK) == _array_literal(_EXPECTED_LIST)


def test_list_comparison_negative_control() -> None:
    """A copy with one entry removed no longer matches 034."""
    assert _listed(PREFLIGHT, drop="activities") != _array_literal(_TABLE_LIST)
    assert _listed(POSTCHECK, drop="projects.projects_select_owner") != _array_literal(
        _EXPECTED_LIST
    )


# ── Replica harness ─────────────────────────────────────────────────────


def test_replica_harness_is_isolated() -> None:
    """The harness runs next to a .env with production credentials: it must
    never publish a port or reach a network."""
    script = REPLICA.read_text(encoding="utf-8")
    runs = re.findall(r"docker run(?:\\\n|[^\n])*", script)
    assert len(runs) == 2
    for run in runs:
        assert "--network none" in run
        assert not re.search(r"\s(-p|--publish)\b", run)
    assert "SUPABASE" not in script and "DATABASE_URL" not in script
