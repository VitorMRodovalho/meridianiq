# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Every foreign key to auth.users says what happens when the account goes.

A key without ON DELETE makes Postgres refuse to delete any account it
still references. Measured in production on 2026-10-09: nine such keys,
and an erased account still held by 2 audit_log rows and 1 organization.
Migration 038 gives each a rule. The ratchet replays every migration and
fails on a reference to auth.users that ends without a rule; the control
replays the files before 038 and must find exactly the nine.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "supabase" / "migrations"

#: Migration 002 added these columns with IF NOT EXISTS; in production the
#: columns predated it, so the constraints never existed there, and the
#: user's erasure deletes these rows before any account deletion.
OUT_OF_SCOPE_002 = {
    ("schedule_uploads", "user_id"),
    ("projects", "user_id"),
    ("analysis_results", "user_id"),
    ("comparison_results", "user_id"),
    ("forensic_timelines", "user_id"),
    ("tia_analyses", "user_id"),
    ("evm_analyses", "user_id"),
    ("risk_simulations", "user_id"),
}

MEASURED_NO_RULE = {
    ("programs", "user_id"),
    ("reports", "user_id"),
    ("audit_log", "user_id"),
    ("forensic_access_log", "user_id"),
    ("organizations", "created_by"),
    ("memberships", "invited_by"),
    ("project_shares", "shared_by"),
    ("program_shares", "shared_by"),
    ("value_milestones", "created_by"),
}

_TABLE = re.compile(
    r"(?:create\s+table\s+(?:if\s+not\s+exists\s+)?|alter\s+table\s+(?:if\s+exists\s+)?"
    r"(?:only\s+)?)(?:public\.)?([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
_USERS = r"references\s+auth\.users\b(?:\s*\(\s*id\s*\))?"
_REF = re.compile(
    r"(?:[(,]|\bcolumn\s+(?:if\s+not\s+exists\s+)?)\s*([a-z_][a-z0-9_]*)\s+[a-z]+\b[^,;(]*?"
    + _USERS
    + r"([^,;]*)",
    re.IGNORECASE,
)
_FK = re.compile(
    r"foreign\s+key\s*\(\s*([a-z_][a-z0-9_]*)\s*\)\s*" + _USERS + r"([^,;]*)",
    re.IGNORECASE,
)
#: Only these let the account go; NO ACTION and RESTRICT still block it.
_RULE = re.compile(r"on\s+delete\s+(?:cascade|set\s+null|set\s+default)", re.IGNORECASE)


def _strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _statements(path: Path) -> list[str]:
    return _strip_comments(path.read_text(encoding="utf-8")).split(";")


def _rules(files: list[Path]) -> dict[tuple[str, str], bool]:
    """(table, column) -> whether its latest reference to auth.users has ON DELETE."""
    state: dict[tuple[str, str], bool] = {}
    for path in files:
        for stmt in _statements(path):
            table = _TABLE.search(stmt)
            if not table:
                continue
            name = table.group(1).lower()
            for pattern in (_REF, _FK):
                for column, tail in pattern.findall(stmt):
                    state[(name, column.lower())] = bool(_RULE.search(tail))
    return state


def _without_rule(files: list[Path]) -> set[tuple[str, str]]:
    return {key for key, ruled in _rules(files).items() if not ruled} - OUT_OF_SCOPE_002


def test_every_auth_users_reference_has_a_delete_rule() -> None:
    assert _without_rule(sorted(MIGRATIONS.glob("*.sql"))) == set()


def test_negative_control_finds_the_nine_measured_keys_before_038() -> None:
    before = [p for p in sorted(MIGRATIONS.glob("*.sql")) if p.name < "038_"]
    assert _without_rule(before) == MEASURED_NO_RULE


def test_forensic_access_log_user_id_can_be_set_null() -> None:
    sql = _strip_comments((MIGRATIONS / "038_account_deletion_fk_rules.sql").read_text())
    assert re.search(
        r"alter\s+table\s+public\.forensic_access_log\s+alter\s+column\s+user_id\s+drop\s+not\s+null",
        sql,
        re.IGNORECASE,
    )


def test_the_replay_is_not_fooled_by_a_rule_that_still_blocks(tmp_path: Path) -> None:
    """NO ACTION / RESTRICT spelled out, no ``(id)``, ALTER TABLE IF EXISTS."""
    probe = tmp_path / "999_probe.sql"
    probe.write_text(
        "CREATE TABLE public.t1 (a UUID REFERENCES auth.users(id) ON DELETE NO ACTION);\n"
        "CREATE TABLE public.t2 (b UUID REFERENCES auth.users ON DELETE RESTRICT);\n"
        "ALTER TABLE IF EXISTS public.t3 ADD COLUMN c UUID REFERENCES auth.users(id);\n"
        "CREATE TABLE public.t4 (d UUID REFERENCES auth.users(id) ON DELETE SET NULL);\n"
    )
    assert _without_rule([probe]) == {("t1", "a"), ("t2", "b"), ("t3", "c")}
