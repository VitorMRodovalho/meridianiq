# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Migration 039: the function that places a schedule in a program.

The function runs as ``service_role``, which bypasses RLS, so its ownership
checks are the only tenant boundary. These tests pin the text that carries
them; the behaviour (numbering, moves, deleting the emptied program, the
revision-history guard, serialisation of concurrent calls) was exercised on
a Postgres 17 copy of the production schema before the migration shipped.
"""

from __future__ import annotations

import re
from pathlib import Path

SQL = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "039_program_revision_placement.sql"
).read_text()
CODE = re.sub(r"--[^\n]*", "", SQL)
FN = "public.place_project_in_program(uuid, uuid, uuid)"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def test_runs_in_one_transaction() -> None:
    body = _norm(CODE)
    assert body.startswith("begin;")
    assert "commit;" in body
    assert body.index("commit;") > body.index("create or replace function")


def test_only_service_role_may_execute() -> None:
    body = _norm(CODE)
    assert f"revoke all on function {FN} from public, anon, authenticated;" in body
    assert re.findall(r"grant execute on function [^;]+ to ([^;]+);", body) == ["service_role"]


def test_invoker_rights_and_a_pinned_search_path() -> None:
    body = _norm(CODE)
    assert "security invoker" in body
    assert "security definer" not in body
    assert "set search_path = pg_catalog, public" in body


def test_both_rows_are_checked_against_the_caller_and_locked() -> None:
    body = _norm(CODE)
    assert "where id = p_program_id and user_id = p_user_id for update" in body
    assert "where p.id = p_project_id and p.user_id = p_user_id for update" in body
    # A missing and a foreign row raise the same error, so a caller cannot
    # tell another user's id from a nonexistent one.
    assert body.count("'project or program not found' using errcode = 'p0002'") == 3


def test_only_the_callers_emptied_unshared_program_is_deleted() -> None:
    body = _norm(CODE)
    assert (
        "not exists (select 1 from public.program_shares ps where ps.program_id = v_source)" in body
    )
    assert "delete from public.programs where id = v_source and user_id = p_user_id;" in body
    assert body.count("delete from") == 1


def test_duplicate_numbers_in_a_program_are_rejected_by_the_schema() -> None:
    body = _norm(CODE)
    assert (
        "create unique index if not exists idx_projects_program_revision_unique "
        "on public.projects (program_id, revision_number) "
        "where program_id is not null and revision_number is not null;"
    ) in body
