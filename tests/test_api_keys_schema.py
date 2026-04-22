# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Static regression tests for the api_keys migration contract.

Per ADR-0017 / audit AUDIT-001 (issue #16): the 017 migration is the
canonical schema and 026 reconciles any legacy 012-style live table.
These tests verify the migration files on disk encode that contract,
so a future edit that silently drops a guard triggers CI failure.

Full DB-level verification (running migrations against a Postgres
container) is intentionally out of scope here — it belongs in a
dedicated integration harness, not in the fast unit suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

MIGRATIONS = Path(__file__).resolve().parent.parent / "supabase" / "migrations"


def test_012_is_noop() -> None:
    """012 must be reduced to a SELECT 1 no-op plus comments."""
    text = (MIGRATIONS / "012_api_keys.sql").read_text(encoding="utf-8")
    assert "SUPERSEDED BY 017" in text
    assert "ADR-0017" in text
    # No real DDL — the only executable statement must be the no-op SELECT.
    executable_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    assert executable_lines == ["SELECT 1 AS migration_012_noop;"]


def test_017_defines_canonical_columns() -> None:
    """017 must create the canonical 017 column set used by src/api/auth.py."""
    text = (MIGRATIONS / "017_api_keys.sql").read_text(encoding="utf-8")
    for col in ("key_id", "key_hash", "user_id", "name", "created_at", "revoked_at"):
        assert col in text, f"017 missing canonical column {col!r}"
    assert "ENABLE ROW LEVEL SECURITY" in text


def test_026_aligns_legacy_schemas() -> None:
    """026 must contain the four idempotent reconcile steps."""
    text = (MIGRATIONS / "026_api_keys_schema_align.sql").read_text(encoding="utf-8")

    # Drops 012-era policies
    assert 'DROP POLICY IF EXISTS "Users see own keys"' in text
    assert 'DROP POLICY IF EXISTS "Users insert own keys"' in text
    assert 'DROP POLICY IF EXISTS "Users update own keys"' in text

    # Adds / backfills key_id
    assert "ADD COLUMN key_id" in text
    assert "legacy_" in text  # backfill prefix

    # Adds revoked_at and translates is_active
    assert "ADD COLUMN revoked_at" in text
    assert "DROP COLUMN is_active" in text

    # Drops 012-era columns
    assert "DROP COLUMN key_prefix" in text
    assert "DROP COLUMN expires_at" in text


@pytest.mark.parametrize(
    "column",
    [
        # These are the exact keys src/api/auth.py::generate_api_key inserts.
        "key_id",
        "key_hash",
        "user_id",
        "name",
        "created_at",
    ],
)
def test_generate_api_key_contract_matches_017(column: str) -> None:
    """The column set 017 creates must include every key generate_api_key inserts.

    Guards against a future refactor in src/api/auth.py silently diverging
    from the schema contract.
    """
    text = (MIGRATIONS / "017_api_keys.sql").read_text(encoding="utf-8")
    assert column in text
