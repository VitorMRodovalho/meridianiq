# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the W3 lifecycle override log + lock flag (ADR-0016).

Covers:

* Store-layer parity for ``set_lifecycle_phase_lock`` /
  ``get_lifecycle_phase_lock`` / ``save_lifecycle_override`` /
  ``list_lifecycle_overrides`` / ``get_latest_lifecycle_override``.
* The append-only convention (no UPDATE / no DELETE policy at the RLS
  layer; the in-memory store has no policies but mirrors the API: there
  is no ``delete_lifecycle_override`` method).
* Audit log row written under ``action='lifecycle_override'`` per
  BR P1#8.
* Materializer skips ``lifecycle_phase_inference`` when the project is
  locked (Cost Engineer override stickiness).
* Backfill ``--kind=lifecycle_phase_inference`` selects only candidates
  missing the new artifact and skips locked ones (BR P1#1 mitigation).
"""

from __future__ import annotations

import asyncio
import os

import pytest

os.environ["ENVIRONMENT"] = "development"

from src.analytics.lifecycle_phase import RULESET_VERSION  # noqa: E402
from src.api.progress import _reset_for_tests  # noqa: E402
from src.database.store import InMemoryStore  # noqa: E402
from src.materializer.backfill import _candidate_project_ids  # noqa: E402
from src.materializer.runtime import Materializer  # noqa: E402
from src.parser.models import ParsedSchedule, Project, Task  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_progress_channels() -> None:
    _reset_for_tests()


def _seed(store: InMemoryStore) -> str:
    schedule = ParsedSchedule(
        projects=[Project(proj_id="P", proj_short_name="TestProj")],
        activities=[
            Task(
                task_id=f"T{i}",
                proj_id="P",
                task_code=f"A{i}",
                task_name=f"Activity {i}",
                task_type="TT_Task",
                status_code="TK_NotStart",
            )
            for i in range(3)
        ],
    )
    pid = store.add(schedule, b"")
    store.set_project_status(pid, "pending")
    return pid


# --------------------------------------------------------------------- #
# Lock flag                                                             #
# --------------------------------------------------------------------- #


class TestLockFlag:
    def test_default_is_false(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        assert store.get_lifecycle_phase_lock(pid) is False

    def test_set_true_sticks(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        ok = store.set_lifecycle_phase_lock(pid, True)
        assert ok is True
        assert store.get_lifecycle_phase_lock(pid) is True

    def test_unknown_project_returns_false_no_error(self) -> None:
        store = InMemoryStore()
        # Pre-W3 row never tracked — defaults to unlocked.
        assert store.get_lifecycle_phase_lock("ghost") is False

    def test_set_on_unknown_project_returns_false(self) -> None:
        store = InMemoryStore()
        ok = store.set_lifecycle_phase_lock("ghost", True)
        assert ok is False


# --------------------------------------------------------------------- #
# Override log writes                                                   #
# --------------------------------------------------------------------- #


class TestOverrideWrites:
    def test_save_appends_row_and_locks(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        row = store.save_lifecycle_override(
            pid,
            override_phase="construction",
            override_reason="ERP says construction now",
            inferred_phase="design",
            overridden_by="user-1",
            engine_version="4.0",
            ruleset_version=RULESET_VERSION,
        )
        assert row["override_phase"] == "construction"
        assert row["inferred_phase"] == "design"
        assert row["override_reason"] == "ERP says construction now"
        assert row["engine_version"] == "4.0"
        assert store.get_lifecycle_phase_lock(pid) is True

    def test_save_writes_audit_log_row(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        before_audit = len(store._audit_log)
        store.save_lifecycle_override(
            pid,
            override_phase="closeout",
            override_reason="Stakeholder direction final",
            overridden_by="user-2",
            engine_version="4.0",
            ruleset_version=RULESET_VERSION,
        )
        assert len(store._audit_log) == before_audit + 1
        last = store._audit_log[-1]
        assert last["action"] == "lifecycle_override"
        assert last["entity_id"] == pid
        assert last["details"]["override_phase"] == "closeout"
        assert "override_id" in last["details"]

    def test_invalid_phase_rejected(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        with pytest.raises(ValueError):
            store.save_lifecycle_override(
                pid,
                override_phase="not_a_phase",
                override_reason="too long",
                engine_version="4.0",
                ruleset_version=RULESET_VERSION,
            )

    def test_empty_reason_rejected(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        with pytest.raises(ValueError):
            store.save_lifecycle_override(
                pid,
                override_phase="construction",
                override_reason="   ",  # whitespace-only
                engine_version="4.0",
                ruleset_version=RULESET_VERSION,
            )

    def test_inferred_phase_nullable(self) -> None:
        """Override-before-inference is forensically valid at the store
        layer; the API guards 409 separately (BR P1#7)."""
        store = InMemoryStore()
        pid = _seed(store)
        row = store.save_lifecycle_override(
            pid,
            override_phase="planning",
            override_reason="No inference yet",
            inferred_phase=None,
            engine_version="4.0",
            ruleset_version=RULESET_VERSION,
        )
        assert row["inferred_phase"] is None


# --------------------------------------------------------------------- #
# Append-only convention                                                #
# --------------------------------------------------------------------- #


class TestAppendOnlyConvention:
    def test_no_delete_method_exists(self) -> None:
        """The append-only contract is enforced at the RLS + API layer
        (no UPDATE / no DELETE policies in migration 025; no delete
        method on the store). This test guards against a future store
        contributor adding a ``delete_lifecycle_override``."""
        assert not hasattr(InMemoryStore, "delete_lifecycle_override")

    def test_list_returns_newest_first(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        for i in range(3):
            store.save_lifecycle_override(
                pid,
                override_phase="construction",
                override_reason=f"Reason {i}",
                engine_version="4.0",
                ruleset_version=RULESET_VERSION,
            )
        rows = store.list_lifecycle_overrides(pid, limit=10)
        assert len(rows) == 3
        # Reverse chronological — most recent override first.
        assert rows[0]["override_reason"] == "Reason 2"
        assert rows[-1]["override_reason"] == "Reason 0"

    def test_get_latest_returns_top_row(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        store.save_lifecycle_override(
            pid,
            override_phase="design",
            override_reason="First override",
            engine_version="4.0",
            ruleset_version=RULESET_VERSION,
        )
        store.save_lifecycle_override(
            pid,
            override_phase="construction",
            override_reason="Second override",
            engine_version="4.0",
            ruleset_version=RULESET_VERSION,
        )
        latest = store.get_latest_lifecycle_override(pid)
        assert latest is not None
        assert latest["override_phase"] == "construction"

    def test_get_latest_returns_none_for_no_overrides(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        assert store.get_latest_lifecycle_override(pid) is None


# --------------------------------------------------------------------- #
# Materializer integration — lock skips engine                           #
# --------------------------------------------------------------------- #


class TestMaterializerLockSkip:
    def test_locked_project_skips_lifecycle_engine(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        # Pre-lock — simulate a prior override.
        store.set_lifecycle_phase_lock(pid, True)

        asyncio.run(Materializer(store).materialize(pid))

        kinds = {row["artifact_kind"] for row in store._derived_artifacts}
        # Lifecycle skipped; the rest still write.
        assert kinds == {"dcma", "health", "cpm"}

    def test_unlocked_project_writes_lifecycle_artifact(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        # Default unlocked — engine should run.
        asyncio.run(Materializer(store).materialize(pid))

        kinds = {row["artifact_kind"] for row in store._derived_artifacts}
        assert "lifecycle_phase_inference" in kinds

    def test_locked_status_still_flips_to_ready(self) -> None:
        """Lock only gates the lifecycle engine — overall materialization
        still completes successfully (DCMA + health + CPM all run)."""
        store = InMemoryStore()
        pid = _seed(store)
        store.set_lifecycle_phase_lock(pid, True)
        asyncio.run(Materializer(store).materialize(pid))
        assert store.get_project_status(pid) == "ready"


# --------------------------------------------------------------------- #
# Backfill --kind flag                                                  #
# --------------------------------------------------------------------- #


class TestBackfillKindFlag:
    def test_unknown_kind_raises(self) -> None:
        store = InMemoryStore()
        with pytest.raises(ValueError):
            _candidate_project_ids(store, limit=None, explicit_project_id=None, kind="bogus")

    def test_lifecycle_kind_skips_locked_projects(self) -> None:
        store = InMemoryStore()
        pid_locked = _seed(store)
        pid_unlocked = _seed(store)
        store.set_lifecycle_phase_lock(pid_locked, True)
        # Mark both ready so they appear in the candidate query.
        store.set_project_status(pid_locked, "ready")
        store.set_project_status(pid_unlocked, "ready")

        candidates = _candidate_project_ids(
            store,
            limit=None,
            explicit_project_id=None,
            kind="lifecycle_phase_inference",
        )
        assert pid_unlocked in candidates
        assert pid_locked not in candidates

    def test_dcma_default_kind_unchanged_w2_behaviour(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        store.set_project_status(pid, "ready")
        # No materializer ever ran — DCMA artifact missing.
        candidates = _candidate_project_ids(
            store, limit=None, explicit_project_id=None, kind="dcma"
        )
        assert pid in candidates
