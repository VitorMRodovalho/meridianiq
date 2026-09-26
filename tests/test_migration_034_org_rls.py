# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Static checks on migration 034 (organization RLS rewrite).

These read the migrations' CONTENT and replay CREATE/DROP POLICY in file
order to derive the resulting policy set. They do not show the effect in a
database. The effect was exercised on local replicas with
``scripts/rls_replica/run.sh`` (postgres:17 with Supabase-style roles, and
Supabase's own image): it replays 001-034 and probes as anon, authenticated
and service_role, with a control arm that must first reproduce the
recursion.

Every detector below ships with a negative control that shows it can say
no on the migrations before 034.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "034_org_rls_rewrite.sql"
REPLICA = ROOT / "scripts" / "rls_replica" / "run.sh"

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


def _array_literal(pattern: str) -> list[str]:
    """Quoted items of the ARRAY[...] that follows ``pattern`` in 034."""
    match = re.search(pattern + r"\s*array\s*\[(.*?)\]", _sql(), re.IGNORECASE | re.DOTALL)
    assert match, f"034: no ARRAY[...] after {pattern!r}"
    return re.findall(r"'([^']*)'", match.group(1))


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
        "create or replace function public.is_org_member"
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
    match = re.search(r"function public\.is_org_member\((.*?)\)\s*returns", _normalised())
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
        "revoke all on function public.is_org_member(uuid, text[]) "
        "from public, anon, authenticated;" in sql
    )
    grants = re.findall(
        r"grant execute on function public\.is_org_member\(uuid, text\[\]\) to ([^;]+);", sql
    )
    assert grants == ["authenticated, service_role"]


def test_helper_owner_is_checked_for_rls_exemption() -> None:
    sql = _normalised()
    assert "alter function public.is_org_member(uuid, text[]) owner to postgres;" in sql
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
    assert selects[0].body == "for select to authenticated using (auth.uid() = user_id)"


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


# ── Privileges ──────────────────────────────────────────────────────────


def test_client_write_privileges_are_revoked_on_every_table() -> None:
    listed = _array_literal(r"foreach\s+v_table\s+in\s+array")
    assert len(listed) == len(set(listed))
    assert set(listed) == _tables(_files("034_"))
    sql = _normalised()
    assert "v_privs text := 'insert, update, delete, truncate, references, trigger';" in sql
    assert "v_privs := v_privs || ', maintain';" in sql
    assert "'revoke %s on table public.%i from public, anon, authenticated'" in sql


def test_table_list_detector_negative_control() -> None:
    """The comparison would notice a table missing from the list."""
    listed = set(_array_literal(r"foreach\s+v_table\s+in\s+array"))
    assert _tables(_files("034_")) != listed - {"activities"}


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
        f"public.{t}" for t in ORG_TABLES if t != "program_shares"
    ]


# ── In-migration checks ─────────────────────────────────────────────────


def _affected(state: dict[tuple[str, str], Policy]) -> set[str]:
    reads = re.compile(r"\b(projects|organizations|project_shares|is_org_member)\b")
    return {p.table for p in state.values() if reads.search(p.body)}


def test_expected_read_policies_match_the_state_after_034() -> None:
    """The list 034 checks against equals the permissive SELECT/ALL policies
    that migrations 001-034 leave on the affected tables."""
    expected = set(_array_literal(r"v_expected\s+text\[\]\s*:="))
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
    assert r"~ '\mmemberships\m'" in sql
    assert "p.permissive = 'permissive'" in sql
    assert "p.cmd in ('select', 'all')" in sql
    assert "set local role authenticated;" in sql
    assert "execute format('explain select 1 from public.%i', v_table);" in sql
    assert sql.index("explain select 1") < sql.index("commit;")


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
