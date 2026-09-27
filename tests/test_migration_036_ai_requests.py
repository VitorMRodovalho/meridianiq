# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Static checks on migration 036 (AI access requests).

These read the migration's CONTENT. The effect in a database is exercised
by scripts/rls_replica/run.sh (stages "036 ..."): the request scenarios,
the client roles refused, the definer's scope, and the concurrency probe.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "supabase" / "migrations"
M035 = MIGRATIONS / "035_ai_access_ledger.sql"
M036 = MIGRATIONS / "036_ai_access_requests.sql"

FUNCTIONS = {
    "ai_request_cooldown_until": "uuid",
    "ai_access_state": "uuid",
    "ai_request_access": "uuid, text",
    "ai_pending_requests": "uuid, integer",
    "ai_approve_request": "uuid, uuid, text, text",
    "ai_dismiss_request": "uuid, uuid, text, text",
    "ai_grant": "uuid, text, uuid, integer, numeric, text, text, text",
}


def _normalised(path: Path) -> str:
    text = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8"))
    return re.sub(r"\s+", " ", text).lower().strip()


def _function(sql: str, name: str) -> str:
    start = sql.index(f"create or replace function public.{name}(")
    return sql[start : sql.index("$$;", sql.index("as $$", start)) + 3]


def _body(sql: str, name: str) -> str:
    fn = _function(sql, name)
    return fn[fn.index("as $$") + 5 : fn.rindex("$$;")].strip()


def test_single_transaction_guard_and_reload() -> None:
    sql = _normalised(M036)
    assert sql.startswith("begin; set local lock_timeout = '5s';")
    assert sql.endswith("notify pgrst, 'reload schema'; commit;")
    guard = sql[sql.index("do $$") :]
    assert "has_function_privilege('anon', p.oid, 'execute')" in guard
    assert "has_function_privilege('authenticated', p.oid, 'execute')" in guard
    assert "p.prosecdef and p.proname <> 'ai_pending_requests'" in guard
    assert "raise exception" in guard


def test_table_is_api_only() -> None:
    sql = _normalised(M036)
    assert "alter table public.ai_access_requests enable row level security;" in sql
    assert "revoke all on table public.ai_access_requests from public, anon, authenticated;" in sql
    assert "revoke all on table public.ai_access_requests from service_role;" in sql
    assert re.findall(r"grant ([^;]*?) on table public\.ai_access_requests to ([^;]+);", sql) == [
        ("select, insert, update", "service_role")
    ]
    assert "create policy" not in sql


def test_functions_are_callable_by_service_role_only() -> None:
    sql = _normalised(M036)
    for name, args in FUNCTIONS.items():
        assert (
            f"revoke all on function public.{name}({args}) "
            "from public, anon, authenticated, service_role;" in sql
        ), name
        grants = re.findall(rf"grant execute on function public\.{name}\([^)]*\) to ([^;]+);", sql)
        assert grants == ["service_role"], (name, grants)


def test_exactly_one_definer_and_it_is_narrow() -> None:
    sql = _normalised(M036)
    definers = [n for n in FUNCTIONS if "security definer" in _function(sql, n)]
    assert definers == ["ai_pending_requests"]
    fn = _function(sql, "ai_pending_requests")
    assert "language sql stable security definer set search_path = ''" in fn
    assert "where r.status = 'pending'" in fn  # addresses of pending requesters only
    assert "u.email_confirmed_at is not null" in fn and "u.deleted_at is null" in fn
    assert "alter function public.ai_pending_requests(uuid, integer) owner to postgres;" in sql


def test_every_other_function_is_invoker_with_an_empty_search_path() -> None:
    sql = _normalised(M036)
    for name in FUNCTIONS:
        fn = _function(sql, name)
        assert "set search_path = ''" in fn, name
        if name != "ai_pending_requests":
            assert "security invoker" in fn, name


def test_request_creation_is_one_conditional_statement() -> None:
    body = _body(_normalised(M036), "ai_request_access")
    assert "on conflict (user_id) do update" in body
    assert "where r.status <> 'pending' returning r.requested_at into v_at;" in body


def test_decisions_clear_the_note() -> None:
    sql = _normalised(M036)
    for name in ("ai_approve_request", "ai_dismiss_request", "ai_grant"):
        assert "note = null where r.user_id = p_user_id and r.status = 'pending'" in _body(
            sql, name
        ), name


def test_ai_grant_keeps_035_and_only_adds_the_request_close() -> None:
    old = _function(_normalised(M035), "ai_grant")
    new = _function(_normalised(M036), "ai_grant")
    # Same signature and header (so CREATE OR REPLACE keeps owner and grants).
    assert old[: old.index("as $$")] == new[: new.index("as $$")]
    old_body, new_body = _body(_normalised(M035), "ai_grant"), _body(_normalised(M036), "ai_grant")
    assert old_body.endswith("end") and new_body.endswith("end")
    added = new_body[: -len("end")].strip()
    assert added.startswith(old_body[: -len("end")].strip())
    extra = added[len(old_body[: -len("end")].strip()) :].strip()
    assert extra == (
        "update public.ai_access_requests as r set status = 'approved', decided_at = now(), "
        "decided_by = p_granted_by, note = null where r.user_id = p_user_id "
        "and r.status = 'pending';"
    )
