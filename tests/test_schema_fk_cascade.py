# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Schema guard for ADR-0012: every table written by ``_persist_schedule_data``
MUST declare ``ON DELETE CASCADE`` on its FK to ``public.projects(id)``.

The compensating-delete atomicity contract relies on a single
``DELETE FROM projects WHERE id = :uuid`` to clean up every partial child row
on a mid-persist failure. If a future migration introduces a new child table
inside the persist chain that forgets the ``ON DELETE CASCADE`` clause, the
rollback silently stops at the projects row and leaves orphans.

Scope is deliberately narrow — analytics-side tables (``analysis_results``,
``comparisons``, etc.) are written AFTER persist completes, never exist during
a failed upload, and so fall outside this contract. Broadening the guard to
them is tracked as Wave 1/2 follow-up. This test parses
``supabase/migrations/*.sql`` statically; no live database needed.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"

# Tables written by ``SupabaseStore._persist_schedule_data`` as of ADR-0012.
# Update this set when the persist chain grows.
PERSIST_CHAIN_TABLES: frozenset[str] = frozenset(
    {
        "wbs_elements",
        "activities",
        "predecessors",
        "calendars",
        "resources",
        "resource_assignments",
        "activity_code_types",
        "activity_codes",
        "task_activity_codes",
        "udf_types",
        "udf_values",
        "financial_periods",
        "task_financials",
    }
)

# Tables written AFTER ``_persist_schedule_data`` returns, by the Wave 2 async
# materializer (ADR-0009 Wave 1 + ADR-0014). These tables are not in the
# compensating-delete chain directly, BUT they FK to ``projects`` with CASCADE
# so the W2 materializer's rows still get cleaned up when ``projects`` is
# deleted (for any reason, including GDPR delete, admin purge, etc.). This
# guard composes cleanly with the compensating-delete contract of ADR-0012:
# if any artifact exists for a project and the compensating delete fires (e.g.
# during a failed re-upload that re-uses a project row), CASCADE prevents
# orphans. Extend this set when W2+ introduces new post-persist tables.
POST_PERSIST_TABLES: frozenset[str] = frozenset(
    {
        "schedule_derived_artifacts",
    }
)

# Match a ``CREATE TABLE [IF NOT EXISTS] [schema.]name (`` header so we can
# scope the FK scan to that table's body.
_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?(?P<name>\w+)\s*\(",
    re.IGNORECASE,
)

# Match a FK clause to projects(id); ``rest`` captures up to the next comma or
# closing paren so we can search it for ON DELETE CASCADE.
_FK_TO_PROJECTS = re.compile(
    r"REFERENCES\s+(?:public\.)?projects\s*\(\s*id\s*\)(?P<rest>[^,)]*)",
    re.IGNORECASE,
)


def _find_table_bodies(sql: str) -> list[tuple[str, str]]:
    """Return a list of (table_name, body) pairs from CREATE TABLE statements."""
    bodies: list[tuple[str, str]] = []
    for header in _CREATE_TABLE.finditer(sql):
        name = header.group("name").lower()
        start = header.end()
        # Walk balanced parens to find the matching close.
        depth = 1
        i = start
        while i < len(sql) and depth > 0:
            ch = sql[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        bodies.append((name, sql[start : i - 1]))
    return bodies


def _scan_fks_for_cascade(target_tables: frozenset[str]) -> list[str]:
    """Scan migration SQL for tables in ``target_tables`` that FK to projects(id)
    without ``ON DELETE CASCADE``. Returns a list of offender strings (empty when
    clean)."""
    offenders: list[str] = []
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        text = sql_file.read_text(encoding="utf-8")
        for table_name, body in _find_table_bodies(text):
            if table_name not in target_tables:
                continue
            for fk in _FK_TO_PROJECTS.finditer(body):
                rest = fk.group("rest")
                if "ON DELETE CASCADE" not in rest.upper():
                    offenders.append(
                        f"{sql_file.name}: CREATE TABLE {table_name} has a FK to "
                        f"projects(id) without ON DELETE CASCADE"
                    )
    return offenders


def test_persist_chain_fks_declare_on_delete_cascade() -> None:
    """Every table in PERSIST_CHAIN_TABLES must have ON DELETE CASCADE on its
    FK to projects(id). Verified against all migration SQL files."""
    offenders = _scan_fks_for_cascade(PERSIST_CHAIN_TABLES)
    assert not offenders, (
        "ADR-0012 compensating-delete contract violated. Every table written "
        "by _persist_schedule_data must have ON DELETE CASCADE on its FK to "
        "projects(id); otherwise a mid-persist failure leaves orphan rows "
        "after the compensating DELETE. Offenders:\n" + "\n".join(offenders)
    )


def test_post_persist_tables_declare_on_delete_cascade() -> None:
    """Post-persist tables (Wave 2 async materializer output) must also declare
    ON DELETE CASCADE on their FK to projects(id).

    Per ADR-0014 + ADR-0009 Wave 1: when ``projects`` is deleted (for ANY reason —
    GDPR, admin purge, compensating-delete on re-upload failure), the derived
    artifacts must cascade. Omitting CASCADE here would leave forensic artefacts
    in the DB pointing at a dead FK, violating the SCL §4 chain-of-custody
    contract and breaking GDPR erasure compliance."""
    offenders = _scan_fks_for_cascade(POST_PERSIST_TABLES)
    assert not offenders, (
        "ADR-0014 cascade contract violated. Every table written by the Wave 2 "
        "async materializer must have ON DELETE CASCADE on its FK to projects(id); "
        "otherwise deletion of a project leaves orphan derived artifacts. "
        "Offenders:\n" + "\n".join(offenders)
    )
