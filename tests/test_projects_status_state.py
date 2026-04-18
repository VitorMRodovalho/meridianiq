# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for ADR-0015 projects.status state machine — flip helpers and the
read-path filter semantics of ``get_projects``.

ADR reference: docs/adr/0015-async-materialization-state-machine.md (§2 state
machine, §3 read-path filter). Migration reference:
supabase/migrations/024_projects_status_state.sql.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import pytest

os.environ["ENVIRONMENT"] = "development"

from src.database.store import InMemoryStore  # noqa: E402
from src.parser.models import ParsedSchedule, Project  # noqa: E402
from tests.test_store_persistence import MockSupabaseStore  # noqa: E402


def _schedule(name: str = "X") -> ParsedSchedule:
    return ParsedSchedule(projects=[Project(proj_id="P", proj_short_name=name)])


# ------------------------------------------------------------------ #
# set_project_status                                                 #
# ------------------------------------------------------------------ #


class TestSetProjectStatusInMemory:
    def test_accepts_all_three_status_values(self) -> None:
        store = InMemoryStore()
        pid = store.add(_schedule("A"), b"", user_id="alice")
        for status in ("pending", "ready", "failed"):
            assert store.set_project_status(pid, status) is True
            assert store._project_statuses[pid] == status

    def test_rejects_invalid_status(self) -> None:
        store = InMemoryStore()
        pid = store.add(_schedule("A"), b"", user_id="alice")
        with pytest.raises(ValueError, match="invalid projects.status"):
            store.set_project_status(pid, "completed")

    def test_missing_project_returns_false(self) -> None:
        store = InMemoryStore()
        assert store.set_project_status("proj-ghost", "ready") is False


class TestSetProjectStatusSupabase:
    def test_accepts_all_three_status_values(self) -> None:
        store = MockSupabaseStore()
        store._insert("projects", {"id": "p1", "project_name": "A", "status": "pending"})
        for status in ("pending", "ready", "failed"):
            assert store.set_project_status("p1", status) is True
            assert store._tables["projects"][0]["status"] == status

    def test_rejects_invalid_status(self) -> None:
        store = MockSupabaseStore()
        with pytest.raises(ValueError, match="invalid projects.status"):
            store.set_project_status("p1", "computing")

    def test_silent_noop_logs_warning(self, caplog: Any) -> None:
        store = MockSupabaseStore()
        # No row — _update returns []; set_project_status must log WARN.
        with caplog.at_level(logging.WARNING, logger="src.database.store"):
            ok = store.set_project_status("p-ghost", "failed")
        assert ok is False
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("affected 0 rows" in r.getMessage() for r in warnings), (
            "expected a WARNING about silent-no-op on set_project_status"
        )


# ------------------------------------------------------------------ #
# get_projects filter semantics                                      #
# ------------------------------------------------------------------ #


class TestGetProjectsFilterInMemory:
    def test_owner_scope_sees_all_statuses(self) -> None:
        store = InMemoryStore()
        ok = store.add(_schedule("A"), b"", user_id="alice")
        pend = store.add(_schedule("B"), b"", user_id="alice")
        fail = store.add(_schedule("C"), b"", user_id="alice")
        store.set_project_status(pend, "pending")
        store.set_project_status(fail, "failed")

        rows = store.get_projects(user_id="alice")
        statuses = {r["project_id"]: r["status"] for r in rows}
        assert statuses[ok] == "ready"
        assert statuses[pend] == "pending"
        assert statuses[fail] == "failed"

    def test_anonymous_list_default_hides_non_ready(self) -> None:
        store = InMemoryStore()
        a = store.add(_schedule("A"), b"")
        b = store.add(_schedule("B"), b"")
        store.set_project_status(b, "pending")

        rows = store.get_projects()
        ids = {r["project_id"] for r in rows}
        assert a in ids
        assert b not in ids

    def test_anonymous_list_include_all_shows_non_ready(self) -> None:
        store = InMemoryStore()
        a = store.add(_schedule("A"), b"")
        b = store.add(_schedule("B"), b"")
        store.set_project_status(b, "failed")

        rows = store.get_projects(include_all_statuses=True)
        ids = {r["project_id"] for r in rows}
        assert {a, b} <= ids


class TestGetProjectsFilterSupabase:
    def _seed(self, store: MockSupabaseStore) -> None:
        for pid, name, status in [
            ("p-r", "Ready", "ready"),
            ("p-p", "Pending", "pending"),
            ("p-f", "Failed", "failed"),
        ]:
            store._insert(
                "projects",
                {
                    "id": pid,
                    "project_name": name,
                    "storage_path": f"u/{pid}/x.xer",
                    "status": status,
                    "activity_count": 10,
                    "relationship_count": 5,
                    "user_id": "alice",
                },
            )

    def test_owner_scope_sees_all_statuses(self) -> None:
        store = MockSupabaseStore()
        self._seed(store)
        rows = store.get_projects(user_id="alice")
        statuses = {r["status"] for r in rows}
        assert statuses == {"ready", "pending", "failed"}

    def test_anonymous_list_default_hides_non_ready(self) -> None:
        store = MockSupabaseStore()
        self._seed(store)
        rows = store.get_projects()
        statuses = {r["status"] for r in rows}
        assert statuses == {"ready"}

    def test_anonymous_list_include_all_shows_non_ready(self) -> None:
        store = MockSupabaseStore()
        self._seed(store)
        rows = store.get_projects(include_all_statuses=True)
        statuses = {r["status"] for r in rows}
        assert statuses == {"ready", "pending", "failed"}

    def test_status_column_exposed_in_dict(self) -> None:
        store = MockSupabaseStore()
        self._seed(store)
        rows = store.get_projects(user_id="alice")
        for r in rows:
            assert "status" in r
            assert r["status"] in {"pending", "ready", "failed"}

    def test_orphan_rows_without_storage_path_still_skipped(self) -> None:
        store = MockSupabaseStore()
        store._insert(
            "projects",
            {
                "id": "p-orphan",
                "project_name": "Orphan",
                "storage_path": "",  # orphan guard
                "status": "ready",
                "user_id": "alice",
            },
        )
        rows = store.get_projects(user_id="alice")
        assert rows == []

    def test_legacy_row_without_status_defaults_to_ready(self) -> None:
        """Migration 024 backfills existing rows with DEFAULT 'ready'; the
        Python read path must also tolerate rows that predate the column in
        test fixtures where status is omitted from _insert."""
        store = MockSupabaseStore()
        store._insert(
            "projects",
            {
                "id": "p-legacy",
                "project_name": "Legacy",
                "storage_path": "u/p-legacy/x.xer",
                "user_id": "alice",
                # no status key
            },
        )
        rows = store.get_projects(user_id="alice")
        assert len(rows) == 1
        assert rows[0]["status"] == "ready"


# ------------------------------------------------------------------ #
# save_project wires status='pending' (Supabase side)                 #
# ------------------------------------------------------------------ #


class TestSaveProjectSetsPendingStatus:
    def test_supabase_save_project_inserts_with_pending_status(self) -> None:
        """``save_project`` inserts the ``projects`` row with ``status='pending'``
        — the async materializer will flip to ``ready`` once the engines run.
        Migration 024 + this assignment ship in the same commit."""
        store = MockSupabaseStore()

        # Mock storage upload (happy-path, no exception)
        class _OkStorage:
            def from_(self, bucket: str) -> "_OkStorage":
                return self

            def upload(self, path: str, file: bytes, file_options: dict[str, str]) -> None:
                pass

        class _OkClient:
            def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
                self._inner = store._client
                self.storage = _OkStorage()

            def table(self, name: str):  # type: ignore[no-untyped-def]
                return self._inner.table(name)

            def rpc(self, fn: str, params: dict[str, Any]):  # type: ignore[no-untyped-def]
                # get_or_create_program takes this path — return a stub program id.
                class _R:
                    data = "prog-1"

                class _Q:
                    def execute(self) -> Any:
                        return _R()

                return _Q()

        store._client = _OkClient(store._tables)  # type: ignore[assignment]

        # Skip the revision lookup chain by also stubbing the uploads table.
        pid = store.save_project(
            upload_id="u-1",
            schedule=_schedule("New"),
            xer_bytes=b"dummy",
            user_id="alice",
        )

        rows = store._tables["projects"]
        assert len(rows) == 1
        assert rows[0]["id"] == pid
        assert rows[0]["status"] == "pending"
