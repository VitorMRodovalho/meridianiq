# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Static checks on migration 040 (retention of AI access requests).

These read the migration's CONTENT. The effect in a database is exercised
by scripts/rls_replica/run.sh with the Supabase image (stages "040 ..."):
the purge horizon (29/30/31 days, pending kept), a real pg_cron run, who
can reach the purge, a second apply, negative controls and the recovery
after re-applying 036.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "supabase" / "migrations"
M036 = MIGRATIONS / "036_ai_access_requests.sql"
M040 = MIGRATIONS / "040_ai_request_retention.sql"


def _normalised(path: Path) -> str:
    text = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8"))
    return re.sub(r"\s+", " ", text).lower().strip()


def _function(sql: str, name: str) -> str:
    start = sql.index(f"create or replace function public.{name}(")
    return sql[start : sql.index("$$;", sql.index("as $$", start)) + 3]


def _body(sql: str, name: str) -> str:
    fn = _function(sql, name)
    return fn[fn.index("as $$") + 5 : fn.rindex("$$;")].strip()


def test_single_transaction_with_a_guard() -> None:
    sql = _normalised(M040)
    assert sql.startswith("begin; set local lock_timeout = '5s';")
    assert sql.endswith("commit;")
    assert sql.count("begin;") == 1 and sql.count("commit;") == 1
    guard = sql[sql.index("do $$ declare v_purge regprocedure") :]
    assert guard.count("raise exception") == 6


def test_purge_deletes_only_decided_rows_past_the_block() -> None:
    body = _body(_normalised(M040), "ai_purge_decided_requests")
    assert (
        "delete from public.ai_access_requests as r where r.status <> 'pending' "
        "and r.decided_at < now() - interval '30 days';"
    ) in body
    assert body.count("delete from") == 1
    # The block ends at decided_at + 30 days (036): the purge never runs ahead of it.
    assert "decided_at <= now() - interval '30 days'" in _normalised(M036)


def test_purge_runs_as_invoker_and_no_api_role_can_call_it() -> None:
    sql = _normalised(M040)
    fn = _function(sql, "ai_purge_decided_requests")
    assert "security invoker" in fn and "set search_path = ''" in fn
    assert (
        "revoke all on function public.ai_purge_decided_requests() "
        "from public, anon, authenticated, service_role;"
    ) in sql
    assert "grant execute on function public.ai_purge_decided_requests" not in sql
    # No DELETE for the API: the only deleter is the cron job as postgres.
    assert "grant delete" not in sql


def test_forget_user_keeps_036_and_only_clears_the_entitlement_note() -> None:
    old = _function(_normalised(M036), "ai_forget_user")
    new = _function(_normalised(M040), "ai_forget_user")
    assert old[: old.index("as $$")] == new[: new.index("as $$")]
    old_body = _body(_normalised(M036), "ai_forget_user")
    new_body = _body(_normalised(M040), "ai_forget_user")
    assert new_body == old_body.replace(
        "set email = null where", "set email = null, note = null where"
    )
    assert new_body != old_body
    sql = _normalised(M040)
    assert "grant execute on function public.ai_forget_user(uuid) to service_role;" in sql


def test_jobs_are_named_and_scheduled_once_each() -> None:
    sql = _normalised(M040)
    assert "create extension if not exists pg_cron with schema pg_catalog;" in sql
    assert sql.count("select cron.schedule(") == 2
    assert (
        "'meridianiq-ai-requests-purge', '17 3 * * *', 'select public.ai_purge_decided_requests()'"
        in sql
    )
    assert "'meridianiq-cron-history-cleanup', '27 3 * * *'" in sql
    assert "coalesce(end_time, start_time) < now() - interval '7 days'" in sql
    assert "jobid not in (select jobid from cron.job where jobname not like 'meridianiq-%')" in sql


def test_refuses_to_overwrite_an_unknown_forget_user() -> None:
    sql = _normalised(M040)
    check = sql.index("'e6742565f03a0d0c551817c169cef9ad'")
    assert check < sql.index("create or replace function public.ai_forget_user(")
    assert "'10c2f987c6eb5637f1a4dbcc894591c1'" in sql[: check + 200]


def test_header_gives_the_safe_apply_command() -> None:
    header = M040.read_text(encoding="utf-8").split("BEGIN;", 1)[0]
    assert (
        "psql -X -v ON_ERROR_STOP=1 -f supabase/migrations/040_ai_request_retention.sql" in header
    )


def test_no_grant_on_schema_cron() -> None:
    """Supabase's after-create script revokes them on re-apply ("dependent privileges exist")."""
    sql = _normalised(M040)
    assert "grant usage on schema cron" not in sql
    assert "grant all privileges on all tables in schema cron" not in sql
    assert "has_schema_privilege('postgres', 'cron', 'usage')" in sql
