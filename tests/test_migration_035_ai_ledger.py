# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Static checks on migration 035 (AI entitlements and spend ledger).

These read the migration's CONTENT. Its effect in a database is exercised by
scripts/rls_replica/run.sh (stages "035 ..."): the ledger scenarios as
service_role, the client roles refused, and the concurrency probe with a
no-lock control.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "035_ai_access_ledger.sql"
)

FUNCTIONS = {
    "ai_quota": "uuid, integer, numeric",
    "ai_reserve": "uuid, uuid, numeric, integer, numeric, numeric, text, numeric, numeric",
    "ai_settle": "bigint, text, integer, integer, numeric",
    "ai_admin_report": "integer, numeric",
    "ai_grant": "uuid, text, uuid, integer, numeric, text, text, text",
    "ai_revoke": "uuid, uuid, text, text",
}


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _normalised() -> str:
    return re.sub(r"\s+", " ", _sql()).lower()


def _function_body(name: str) -> str:
    sql = _normalised()
    start = sql.index(f"create or replace function public.{name}(")
    end = sql.index("$$;", start)
    return sql[start:end]


def test_single_transaction_with_a_lock_timeout_and_a_schema_reload() -> None:
    sql = _normalised().strip()
    assert sql.startswith("begin; set local lock_timeout = '5s';")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema'; commit;")


def test_tables_have_rls_and_nothing_for_client_roles() -> None:
    sql = _normalised()
    for table in ("ai_entitlements", "ai_usage"):
        assert f"alter table public.{table} enable row level security;" in sql
    assert (
        "revoke all on table public.ai_entitlements, public.ai_usage "
        "from public, anon, authenticated;" in sql
    )
    assert "revoke all on sequence public.ai_usage_id_seq from public, anon, authenticated;" in sql
    assert not re.search(r"grant [^;]* to [^;]*\b(anon|authenticated)\b", sql)
    assert not re.search(r"create policy", sql)


def test_service_role_can_neither_delete_nor_truncate() -> None:
    sql = _normalised()
    assert "revoke all on table public.ai_entitlements, public.ai_usage from service_role;" in sql
    grants = re.findall(
        r"grant ([^;]*?) on table public\.(ai_entitlements|ai_usage) to service_role;", sql
    )
    assert sorted(grants) == [
        ("select, insert, update", "ai_entitlements"),
        ("select, insert, update", "ai_usage"),
    ]


def test_grant_and_revoke_write_their_audit_row_inside_the_function() -> None:
    for name, action in (("ai_grant", "ai_access_granted"), ("ai_revoke", "ai_access_revoked")):
        body = _function_body(name)
        assert "insert into public.audit_log" in body, name
        assert f"'{action}'" in body, name


def test_the_ledger_survives_account_and_project_deletion() -> None:
    sql = _normalised()
    usage = sql[sql.index("create table if not exists public.ai_usage") :]
    usage = usage[: usage.index(");")]
    assert "references" not in usage
    assert "check (status in ('reserved', 'completed', 'failed', 'unknown'))" in usage
    assert "check (status <> 'completed' or cost_usd is not null)" in usage


def test_functions_are_callable_by_service_role_only() -> None:
    sql = _normalised()
    for name, args in FUNCTIONS.items():
        signature = f"public.{name}({args})"
        assert f"revoke all on function {signature} from public, anon, authenticated;" in sql, name
        grants = re.findall(rf"grant execute on function public\.{name}\([^)]*\) to ([^;]+);", sql)
        assert grants == ["service_role"], (name, grants)


def test_functions_are_invoker_with_an_empty_search_path() -> None:
    for name in FUNCTIONS:
        body = _function_body(name)
        assert "security invoker" in body, name
        assert "security definer" not in body, name
        assert "set search_path = ''" in body, name


def test_writers_are_volatile_and_readers_stable() -> None:
    # PostgREST runs a STABLE function in a read-only transaction.
    for name in ("ai_reserve", "ai_settle", "ai_grant", "ai_revoke"):
        body = _function_body(name)
        assert "language plpgsql volatile" in body, name
    for name in ("ai_quota", "ai_admin_report"):
        assert "stable" in _function_body(name), name


def test_reserve_takes_the_lock_before_reading_the_quota() -> None:
    body = _function_body("ai_reserve")
    lock = body.index(
        "perform pg_advisory_xact_lock(hashtext('meridianiq'), hashtext('ai_budget'));"
    )
    read = body.index("from public.ai_quota(")
    insert = body.index("insert into public.ai_usage")
    assert lock < read < insert


def test_windows_are_utc() -> None:
    sql = _normalised()
    assert "date_trunc('day', now(), 'utc')" in sql
    assert "date_trunc('month', now(), 'utc')" in sql
    assert not re.search(r"date_trunc\('(day|month)', now\(\)\)", sql)
