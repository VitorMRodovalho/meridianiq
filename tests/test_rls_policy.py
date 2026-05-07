# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""RLS coverage regression — Cycle 4 W1 / ADR-0022 §"AST policy regression test".

Mirror of ``tests/test_rate_limit_policy.py`` shape applied to Postgres
RLS coverage. Asserts that every ``CREATE TABLE`` in
``supabase/migrations/*.sql`` has a corresponding ``ALTER TABLE …
ENABLE ROW LEVEL SECURITY`` AND at least one ``CREATE POLICY … ON
<table>`` somewhere in the migration set (not necessarily the same
migration — migration 011 retrofitted RLS to migration 001 tables).

## Why scan ALL migrations rather than per-file

Per backend-reviewer entry-council fix-up: migration 011 retrofitted
RLS for the v0.6 tables created in migration 001. Requiring RLS+policy
in the *same* migration as ``CREATE TABLE`` would force a re-write of
the historical migration set. The contract that matters at the DB
layer is "every table HAS RLS at runtime" — independent of which
migration installed it.

## What this test does NOT enforce

- The policy logic itself (``USING`` / ``WITH CHECK`` clauses) is not
  validated — only its existence. A weak policy (e.g., ``USING (TRUE)``)
  passes the test but should be caught by code review.
- Column-level RLS (rare in this repo) is not distinguished from
  table-level RLS.
- ``security definer`` functions that bypass RLS are out of scope.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent.parent / "supabase" / "migrations"

# Tables that legitimately do NOT have user-facing RLS at the table
# level. Each entry MUST have a rationale comment. As of Cycle 4 W1
# the audit returns empty — every CREATE TABLE has matching RLS.
# Future additions belong here only when (a) FK-cascade from an
# RLS-protected parent suffices, OR (b) the table is service-role-
# managed and never user-readable.
RLS_ALLOWLIST: dict[str, str] = {
    # (intentionally empty — see migration audit 2026-05-07)
}

# RLS-enabled tables with no user-facing policy (managed entirely by
# service_role). Each entry MUST have a rationale comment.
SERVICE_ROLE_ONLY: dict[str, str] = {
    # ``program_shares`` was created in migration 007 with RLS enabled but
    # zero CREATE POLICY rows authored. As of Cycle 4 W1 audit (2026-05-07)
    # the table is referenced by NO application code in ``src/``. Treating
    # it as service-role-only documents reality without changing default-
    # deny behaviour for authenticated users. A future cycle that wires up
    # program-sharing UX must remove this entry and ship CREATE POLICY rows
    # in the same migration.
    "program_shares": "dormant since migration 007; no user-facing code path",
}

_CREATE_TABLE_RE = re.compile(
    r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(?:public\.)?([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
_ENABLE_RLS_RE = re.compile(
    r"ALTER TABLE\s+(?:public\.)?([a-z_][a-z0-9_]*)\s+ENABLE ROW LEVEL SECURITY",
    re.IGNORECASE,
)
# Policy names may be quoted (``"name"``) or unquoted bare identifiers
# (``api_keys_select``). Both are valid PostgreSQL syntax. Migrations
# 011 / 023 use the quoted form; 017 / 026 use the unquoted form.
_CREATE_POLICY_RE = re.compile(
    r'CREATE POLICY\s+(?:"[^"]+"|[a-z_][a-z0-9_]*)\s+ON\s+(?:public\.)?([a-z_][a-z0-9_]*)',
    re.IGNORECASE,
)

# SQL comments: ``-- to end of line`` and ``/* … */`` block. Stripped
# before regex scanning so a CREATE TABLE / CREATE POLICY mention inside
# a doc comment doesn't get treated as actual DDL.
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(sql: str) -> str:
    """Remove SQL line and block comments — comments often discuss DDL."""
    sql = _BLOCK_COMMENT_RE.sub("", sql)
    sql = _LINE_COMMENT_RE.sub("", sql)
    return sql


def _scan_migrations() -> tuple[set[str], set[str], set[str]]:
    """Scan all migrations; return (tables_created, rls_enabled, policy_protected)."""
    tables: set[str] = set()
    rls_enabled: set[str] = set()
    has_policy: set[str] = set()
    for p in sorted(MIGRATIONS_DIR.glob("*.sql")):
        text = _strip_comments(p.read_text())
        for m in _CREATE_TABLE_RE.finditer(text):
            tables.add(m.group(1).lower())
        for m in _ENABLE_RLS_RE.finditer(text):
            rls_enabled.add(m.group(1).lower())
        for m in _CREATE_POLICY_RE.finditer(text):
            has_policy.add(m.group(1).lower())
    return tables, rls_enabled, has_policy


def test_every_table_has_rls_enabled() -> None:
    """Every CREATE TABLE must have ENABLE ROW LEVEL SECURITY in the migration set."""
    tables, rls_enabled, _ = _scan_migrations()
    missing = (tables - rls_enabled) - set(RLS_ALLOWLIST)
    if missing:
        bullet = "\n".join(f"  - public.{t}" for t in sorted(missing))
        raise AssertionError(
            "Tables created without ENABLE ROW LEVEL SECURITY:\n"
            f"{bullet}\n\n"
            "Fix: add ``ALTER TABLE public.<name> ENABLE ROW LEVEL SECURITY`` "
            "in the migration that creates the table, OR add the table to "
            "``RLS_ALLOWLIST`` with rationale (FK-cascade only)."
        )


def test_every_rls_enabled_table_has_policy() -> None:
    """RLS-without-policy is silent default-deny — silent no-op for everyone.

    A table with RLS enabled and no policies returns the empty set on every
    query under any non-superuser role. A migration that enables RLS without
    creating policies is essentially indistinguishable from a typo, but
    behaves like a security feature in passing review.
    """
    _, rls_enabled, has_policy = _scan_migrations()
    missing = rls_enabled - has_policy - set(SERVICE_ROLE_ONLY)
    if missing:
        bullet = "\n".join(f"  - public.{t}" for t in sorted(missing))
        raise AssertionError(
            "RLS-enabled tables without any CREATE POLICY:\n"
            f"{bullet}\n\n"
            "Fix: author at least one ``CREATE POLICY`` for the table, OR "
            "add the table to ``SERVICE_ROLE_ONLY`` with rationale (admin-only)."
        )


def test_no_orphan_policies() -> None:
    """Every CREATE POLICY must reference a table that exists in the migration set."""
    tables, _, has_policy = _scan_migrations()
    orphans = has_policy - tables
    if orphans:
        bullet = "\n".join(f"  - public.{t}" for t in sorted(orphans))
        raise AssertionError(
            f"CREATE POLICY references tables not created in any migration:\n{bullet}"
        )


def test_revision_history_has_rls() -> None:
    """Specific regression for Cycle 4 W1 — migration 028."""
    tables, rls_enabled, has_policy = _scan_migrations()
    assert "revision_history" in tables, (
        "Migration 028 must CREATE TABLE public.revision_history (Cycle 4 W1)"
    )
    assert "revision_history" in rls_enabled, (
        "Migration 028 must ENABLE ROW LEVEL SECURITY on revision_history"
    )
    assert "revision_history" in has_policy, (
        "Migration 028 must CREATE POLICY on revision_history (RLS quadruple)"
    )


def test_revision_history_select_policy_filters_tombstone() -> None:
    """HB-C contract: SELECT policy enforces ``tombstoned_at IS NULL``.

    The application-level filter is intentionally absent (W2 deliverable
    contract). The DB-level enforcement is the load-bearing primitive — if
    a future migration drops the tombstone filter from the SELECT policy,
    every consumer of revision_history would suddenly see tombstoned rows.
    """
    p = MIGRATIONS_DIR / "028_revision_history.sql"
    text = _strip_comments(p.read_text())
    # Find the FOR SELECT policy on revision_history; assert it contains
    # ``tombstoned_at IS NULL`` in the USING clause.
    select_re = re.compile(
        r'CREATE POLICY\s+(?:"[^"]+"|[a-z_][a-z0-9_]*)\s+ON\s+(?:public\.)?revision_history\s+'
        r"FOR SELECT\s+USING\s*\(\s*([^;]+?)\s*\)\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    m = select_re.search(text)
    assert m, "Migration 028 missing FOR SELECT policy on revision_history"
    using_clause = m.group(1)
    assert "tombstoned_at IS NULL" in using_clause, (
        "FOR SELECT USING clause must filter ``tombstoned_at IS NULL`` "
        "(HB-C contract — RLS-enforced default tombstone hiding). Found:\n"
        f"  USING ({using_clause})"
    )


def test_revision_history_has_cap_trigger() -> None:
    """NFM-6/7: cap enforced via BEFORE INSERT trigger raising 23P01."""
    p = MIGRATIONS_DIR / "028_revision_history.sql"
    text = _strip_comments(p.read_text())
    assert "enforce_revision_cap" in text, (
        "Migration 028 must define a cap-enforcing trigger function"
    )
    assert "BEFORE INSERT ON public.revision_history" in text, (
        "Cap must be enforced as BEFORE INSERT trigger (binds service_role)"
    )
    assert "23P01" in text, "Cap-violation EXCEPTION must use SQLSTATE 23P01 (invalid_state)"


def test_revision_history_append_only_trigger() -> None:
    """ADR-0022 append-only contract — UPDATEs only allowed on tombstone fields."""
    p = MIGRATIONS_DIR / "028_revision_history.sql"
    text = _strip_comments(p.read_text())
    assert "enforce_revision_history_append_only" in text, (
        "Migration 028 must define an append-only trigger function"
    )
    assert "BEFORE UPDATE ON public.revision_history" in text, (
        "Append-only contract must be enforced via BEFORE UPDATE trigger"
    )
    # Confirm the trigger blocks mutation of identity columns.
    for col in ("id", "project_id", "revision_number", "data_date", "content_hash", "created_at"):
        assert f"NEW.{col}" in text, (
            f"Append-only trigger must guard column NEW.{col} against mutation"
        )
