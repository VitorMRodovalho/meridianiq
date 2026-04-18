# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Round-trip tests for the derived-artifact store API (ADR-0009 Wave 1 + ADR-0014).

Covers both ``InMemoryStore`` (dev / CI) and ``MockSupabaseStore`` (supabase-path
mocked) with parallel assertions to enforce backend parity. The actual Supabase
integration test (against a live DB) is out of scope for W1; this file is the
unit-level coverage that Wave 2's async materializer will consume.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, Protocol

import pytest

os.environ["ENVIRONMENT"] = "development"

from src.database.store import InMemoryStore  # noqa: E402
from tests.test_store_persistence import MockSupabaseStore  # noqa: E402


# --------------------------------------------------------------------- #
# Shared fixtures                                                       #
# --------------------------------------------------------------------- #


class _ArtifactStore(Protocol):
    """Subset of the store API this module exercises."""

    def save_derived_artifact(
        self,
        project_id: str,
        artifact_kind: str,
        payload: dict[str, Any],
        engine_version: str,
        ruleset_version: str,
        input_hash: str,
        effective_at: datetime,
        computed_by: str | None = ...,
        *,
        ip_address: str | None = ...,
        user_agent: str | None = ...,
    ) -> dict[str, Any]: ...

    def get_latest_derived_artifact(
        self,
        project_id: str,
        artifact_kind: str,
        current_engine_version: str,
        current_ruleset_version: str,
    ) -> dict[str, Any] | None: ...

    def mark_stale(
        self,
        project_id: str,
        stale_reason: str = ...,
    ) -> int: ...


def _audit_rows(store: _ArtifactStore) -> list[dict[str, Any]]:
    """Return the audit_log rows written through the store, regardless of backend."""
    if isinstance(store, InMemoryStore):
        return store._audit_log
    if isinstance(store, MockSupabaseStore):
        return store._tables.get("audit_log", [])
    raise TypeError(f"unknown store backend: {type(store).__name__}")


def _artifact_rows(store: _ArtifactStore) -> list[dict[str, Any]]:
    """Return the schedule_derived_artifacts rows, regardless of backend."""
    if isinstance(store, InMemoryStore):
        return store._derived_artifacts
    if isinstance(store, MockSupabaseStore):
        return store._tables.get("schedule_derived_artifacts", [])
    raise TypeError(f"unknown store backend: {type(store).__name__}")


@pytest.fixture(params=["in_memory", "mock_supabase"])
def store(request: pytest.FixtureRequest) -> _ArtifactStore:
    """Parameterized fixture providing each backend — enforces parity."""
    if request.param == "in_memory":
        return InMemoryStore()
    return MockSupabaseStore()


def _base_args(
    project_id: str = "P1",
    kind: str = "dcma",
    engine: str = "3.9.0",
    ruleset: str = "dcma-v1",
    input_hash: str = "a" * 64,
    user: str | None = "user-1",
) -> dict[str, Any]:
    """Baseline kwargs for save_derived_artifact."""
    return {
        "project_id": project_id,
        "artifact_kind": kind,
        "payload": {"score": 0.92},
        "engine_version": engine,
        "ruleset_version": ruleset,
        "input_hash": input_hash,
        "effective_at": datetime(2026, 4, 1, tzinfo=UTC),
        "computed_by": user,
    }


# --------------------------------------------------------------------- #
# save_derived_artifact                                                 #
# --------------------------------------------------------------------- #


class TestSaveDerivedArtifact:
    def test_creates_row(self, store: _ArtifactStore) -> None:
        saved = store.save_derived_artifact(**_base_args())
        assert saved["project_id"] == "P1"
        assert saved["artifact_kind"] == "dcma"
        assert saved["payload"] == {"score": 0.92}
        assert saved["engine_version"] == "3.9.0"
        assert saved["ruleset_version"] == "dcma-v1"
        assert saved["is_stale"] is False
        assert saved["stale_reason"] is None

    def test_writes_paired_audit_row(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args(user="user-xyz"))
        rows = _audit_rows(store)
        assert len(rows) == 1
        row = rows[0]
        assert row["action"] == "materialize"
        assert row["entity_type"] == "project"
        assert row["entity_id"] == "P1"
        assert row["user_id"] == "user-xyz"
        assert row["details"]["artifact_kind"] == "dcma"
        assert row["details"]["engine_version"] == "3.9.0"
        assert row["details"]["ruleset_version"] == "dcma-v1"
        assert row["details"]["input_hash"] == "a" * 64

    def test_audit_row_captures_request_context(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(
            **_base_args(),
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0 (test)",
        )
        row = _audit_rows(store)[0]
        assert row["ip_address"] == "203.0.113.7"
        assert row["user_agent"] == "Mozilla/5.0 (test)"

    def test_upsert_on_identity_tuple(self, store: _ArtifactStore) -> None:
        """Same (project, kind, engine, ruleset, hash) → one row, refreshed."""
        store.save_derived_artifact(**_base_args())
        store.save_derived_artifact(**{**_base_args(), "payload": {"score": 0.99}})
        artifacts = _artifact_rows(store)
        assert len(artifacts) == 1
        assert artifacts[0]["payload"] == {"score": 0.99}

    def test_upsert_writes_two_audit_rows(self, store: _ArtifactStore) -> None:
        """Each materialization attempt is an auditable event (ADR-0014 SCL §4)."""
        store.save_derived_artifact(**_base_args())
        store.save_derived_artifact(**_base_args())
        assert len(_audit_rows(store)) == 2

    def test_different_kind_same_project_creates_second_row(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args(kind="dcma"))
        store.save_derived_artifact(**_base_args(kind="health"))
        assert len(_artifact_rows(store)) == 2

    def test_different_engine_version_creates_second_row(self, store: _ArtifactStore) -> None:
        """engine_version is part of the identity tuple."""
        store.save_derived_artifact(**_base_args(engine="3.9.0"))
        store.save_derived_artifact(**_base_args(engine="4.0.0"))
        assert len(_artifact_rows(store)) == 2

    def test_different_input_hash_creates_second_row(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args(input_hash="a" * 64))
        store.save_derived_artifact(**_base_args(input_hash="b" * 64))
        assert len(_artifact_rows(store)) == 2

    def test_invalid_kind_raises(self, store: _ArtifactStore) -> None:
        """Both backends pre-validate artifact_kind (backend parity)."""
        with pytest.raises(ValueError):
            store.save_derived_artifact(**{**_base_args(), "artifact_kind": "invalid"})

    def test_refresh_clears_stale(self, store: _ArtifactStore) -> None:
        """Re-materialization after mark_stale must un-stale the row (idempotent refresh)."""
        store.save_derived_artifact(**_base_args())
        store.mark_stale("P1")
        store.save_derived_artifact(**_base_args())
        artifacts = _artifact_rows(store)
        assert len(artifacts) == 1
        assert artifacts[0]["is_stale"] is False
        assert artifacts[0]["stale_reason"] is None


# --------------------------------------------------------------------- #
# get_latest_derived_artifact                                           #
# --------------------------------------------------------------------- #


class TestGetLatestDerivedArtifact:
    def test_returns_none_when_empty(self, store: _ArtifactStore) -> None:
        assert store.get_latest_derived_artifact("P1", "dcma", "3.9.0", "dcma-v1") is None

    def test_returns_saved_row(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args())
        got = store.get_latest_derived_artifact("P1", "dcma", "3.9.0", "dcma-v1")
        assert got is not None
        assert got["payload"] == {"score": 0.92}

    def test_engine_version_mismatch_returns_none(self, store: _ArtifactStore) -> None:
        """Stored 3.9.0 but caller asks for 4.0.0 → forces re-materialization."""
        store.save_derived_artifact(**_base_args(engine="3.9.0"))
        assert store.get_latest_derived_artifact("P1", "dcma", "4.0.0", "dcma-v1") is None

    def test_ruleset_version_mismatch_returns_none(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args(ruleset="dcma-v1"))
        assert store.get_latest_derived_artifact("P1", "dcma", "3.9.0", "dcma-v2") is None

    def test_stale_row_excluded(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args())
        store.mark_stale("P1")
        assert store.get_latest_derived_artifact("P1", "dcma", "3.9.0", "dcma-v1") is None

    def test_multiple_rows_returns_newest(self, store: _ArtifactStore) -> None:
        """When multiple non-stale rows exist (different input_hash), return newest."""
        store.save_derived_artifact(**_base_args(input_hash="a" * 64))
        store.save_derived_artifact(
            **{**_base_args(input_hash="b" * 64), "payload": {"score": 0.80}}
        )
        got = store.get_latest_derived_artifact("P1", "dcma", "3.9.0", "dcma-v1")
        assert got is not None
        assert got["payload"] == {"score": 0.80}

    def test_other_project_isolated(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args(project_id="P1"))
        assert store.get_latest_derived_artifact("P2", "dcma", "3.9.0", "dcma-v1") is None

    def test_other_kind_isolated(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args(kind="dcma"))
        assert store.get_latest_derived_artifact("P1", "health", "3.9.0", "health-v1") is None


# --------------------------------------------------------------------- #
# mark_stale                                                            #
# --------------------------------------------------------------------- #


class TestMarkStale:
    def test_flips_all_rows_of_project(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args(kind="dcma"))
        store.save_derived_artifact(**_base_args(kind="health", input_hash="c" * 64))
        n = store.mark_stale("P1")
        assert n == 2
        for r in _artifact_rows(store):
            if r["project_id"] == "P1":
                assert r["is_stale"] is True

    def test_default_reason_input_changed(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args())
        store.mark_stale("P1")
        rows = [r for r in _artifact_rows(store) if r["project_id"] == "P1"]
        assert rows[0]["stale_reason"] == "input_changed"

    def test_explicit_reason_engine_upgraded(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args())
        store.mark_stale("P1", stale_reason="engine_upgraded")
        rows = [r for r in _artifact_rows(store) if r["project_id"] == "P1"]
        assert rows[0]["stale_reason"] == "engine_upgraded"

    def test_invalid_reason_raises(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args())
        with pytest.raises(ValueError):
            store.mark_stale("P1", stale_reason="garbage")

    def test_only_affects_target_project(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args(project_id="P1"))
        store.save_derived_artifact(**_base_args(project_id="P2", input_hash="d" * 64))
        store.mark_stale("P1")
        rows = _artifact_rows(store)
        p2_rows = [r for r in rows if r["project_id"] == "P2"]
        assert all(r["is_stale"] is False for r in p2_rows)

    def test_returns_zero_when_no_rows(self, store: _ArtifactStore) -> None:
        assert store.mark_stale("P_nonexistent") == 0

    def test_marking_twice_idempotent(self, store: _ArtifactStore) -> None:
        store.save_derived_artifact(**_base_args())
        store.mark_stale("P1", stale_reason="input_changed")
        # second call with a different reason overwrites — see ADR-0014 discussion
        store.mark_stale("P1", stale_reason="engine_upgraded")
        rows = [r for r in _artifact_rows(store) if r["project_id"] == "P1"]
        assert rows[0]["stale_reason"] == "engine_upgraded"
