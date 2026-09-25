# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Static checks on migration 033 (invitation identity).

These read the migration's CONTENT. They do not show the effect in a
database: after applying it, the grants are verified with the queries in
the migration's pull request (``has_function_privilege`` /
``has_column_privilege`` as ``anon`` and ``authenticated``).
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parent.parent
    / "supabase"
    / "migrations"
    / "033_invitation_identity.sql"
)


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _normalised() -> str:
    return re.sub(r"\s+", " ", _sql()).lower()


def test_lookup_function_reads_auth_users_only_for_confirmed_live_accounts() -> None:
    sql = _normalised()
    assert "create or replace function public.auth_user_id_for_email(p_email text)" in sql
    assert "security definer" in sql and "set search_path = ''" in sql
    assert "from auth.users as u" in sql
    assert "u.deleted_at is null" in sql
    assert "u.email_confirmed_at is not null" in sql
    # Ambiguity answers NULL rather than picking a row.
    assert "case when count(*) = 1 then" in sql


def test_lookup_function_is_callable_by_service_role_only() -> None:
    sql = _normalised()
    assert (
        "revoke all on function public.auth_user_id_for_email(text) "
        "from public, anon, authenticated;" in sql
    )
    grants = re.findall(
        r"grant execute on function public\.auth_user_id_for_email\(text\) to ([^;]+);", sql
    )
    assert grants == ["service_role"]


def test_profile_identity_columns_are_not_user_writable() -> None:
    sql = _normalised()
    assert "revoke update on public.user_profiles from public, anon, authenticated;" in sql
    (columns,) = re.findall(
        r"grant update \(([^)]*)\) on public\.user_profiles to authenticated;", sql
    )
    writable = {c.strip() for c in columns.split(",")}
    assert writable == {"full_name", "company", "avatar_url", "updated_at"}
    assert not writable & {"email", "role", "id"}
    # No table-wide UPDATE grant comes back later in the file.
    assert not re.search(r"grant (all|update) on (table )?public\.user_profiles", sql)


def test_api_calls_the_function_the_migration_defines() -> None:
    source = (
        Path(__file__).resolve().parent.parent / "src" / "api" / "organizations.py"
    ).read_text(encoding="utf-8")
    assert 'rpc("auth_user_id_for_email", {"p_email": email})' in source
    assert 'table("user_profiles").select("id")' not in source
