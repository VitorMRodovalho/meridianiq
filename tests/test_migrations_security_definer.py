# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Every SECURITY DEFINER function must pin its search_path.

A SECURITY DEFINER function without ``SET search_path`` resolves unqualified
names through the *caller's* search_path. The Supabase auth service inserts
into ``auth.users`` with ``search_path=auth``, so the signup triggers could
not find ``organizations`` / ``memberships``. From migration 007 (2026-03-29)
until migration 031 (2026-09-25), no new user could register.

The check is static and covers ``supabase/migrations``. A function is
compliant if its CREATE statement carries ``SET search_path`` or a later
migration runs ``ALTER FUNCTION <name> ... SET search_path``.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "supabase" / "migrations"

_CREATE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:public\.)?(\w+)\s*\((.*?)(?=CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_ALTER_SET_PATH = re.compile(
    r"ALTER\s+FUNCTION\s+(?:public\.)?(\w+)\s*\([^)]*\)\s+SET\s+search_path",
    re.IGNORECASE,
)


def _strip_sql_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _definer_functions_without_pinned_path() -> set[str]:
    """Return SECURITY DEFINER functions whose search_path is never pinned."""
    unpinned: set[str] = set()
    pinned_later: set[str] = set()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        sql = _strip_sql_comments(path.read_text(encoding="utf-8"))
        for match in _CREATE.finditer(sql):
            name, body = match.group(1).lower(), match.group(2)
            # The span runs to the next CREATE FUNCTION, so it also covers the
            # options written after the body (where SET search_path often sits).
            if re.search(r"SECURITY\s+DEFINER", body, re.IGNORECASE):
                if re.search(r"SET\s+search_path", body, re.IGNORECASE):
                    unpinned.discard(name)
                else:
                    unpinned.add(name)
        for match in _ALTER_SET_PATH.finditer(sql):
            pinned_later.add(match.group(1).lower())
    return unpinned - pinned_later


def test_migrations_directory_is_scanned() -> None:
    """Control: the scanner must see the SECURITY DEFINER functions it guards."""
    names: set[str] = set()
    for path in MIGRATIONS.glob("*.sql"):
        sql = _strip_sql_comments(path.read_text(encoding="utf-8"))
        for match in _CREATE.finditer(sql):
            if re.search(r"SECURITY\s+DEFINER", match.group(2), re.IGNORECASE):
                names.add(match.group(1).lower())
    assert {"handle_new_user", "handle_new_user_org", "delete_user_data"} <= names


def test_every_security_definer_function_pins_search_path() -> None:
    offenders = _definer_functions_without_pinned_path()
    assert not offenders, (
        "SECURITY DEFINER functions without a pinned search_path "
        f"(add `SET search_path = public, pg_temp`): {sorted(offenders)}"
    )
