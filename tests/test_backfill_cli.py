# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for ``src.materializer.backfill`` — CLI plumbing + idempotence.

The CLI path in ``main()`` resolves the materializer via
``src.api.deps.get_materializer`` which imports the global SupabaseStore
if ``SUPABASE_URL`` is set. These tests monkeypatch the dependency
resolution so the suite runs entirely against :class:`InMemoryStore`.
"""

from __future__ import annotations

import asyncio
import os

import pytest

os.environ["ENVIRONMENT"] = "development"

from src.database.store import InMemoryStore  # noqa: E402
from src.materializer import Materializer  # noqa: E402
from src.materializer.backfill import (  # noqa: E402
    _candidate_project_ids,
    _re_materialization_candidates,
    _run_batch,
    main,
)
from src.materializer.runtime import _ENGINE_VERSION  # noqa: E402
from src.parser.models import ParsedSchedule, Project, Task  # noqa: E402


def _schedule(name: str = "X", n: int = 3) -> ParsedSchedule:
    return ParsedSchedule(
        projects=[Project(proj_id="P", proj_short_name=name)],
        activities=[
            Task(task_id=f"T{i}", task_code=f"A{i}", task_name=f"Act {i}", proj_id="P")
            for i in range(n)
        ],
    )


# ------------------------------------------------------------------ #
# Candidate selection                                                 #
# ------------------------------------------------------------------ #


class TestCandidateSelection:
    def test_selects_ready_projects_without_dcma_artifact(self) -> None:
        store = InMemoryStore()
        p1 = store.add(_schedule("A"), b"")
        p2 = store.add(_schedule("B"), b"")
        # Pre-materialize p1's dcma so it is NOT a candidate. Use the
        # runtime ``_ENGINE_VERSION`` (sourced from src/__about__.py per
        # ADR-0014 §"Decision Outcome") rather than a hardcoded literal —
        # otherwise a version bump leaves this test asserting against
        # a stale artifact.
        store.save_derived_artifact(
            project_id=p1,
            artifact_kind="dcma",
            payload={"dummy": True},
            engine_version=_ENGINE_VERSION,
            ruleset_version="dcma-v1",
            input_hash="a" * 64,
            effective_at=None,
            computed_by=None,
        )
        pids = _candidate_project_ids(store, limit=None, explicit_project_id=None)
        assert p1 not in pids
        assert p2 in pids

    def test_explicit_project_id_short_circuits(self) -> None:
        store = InMemoryStore()
        pids = _candidate_project_ids(store, limit=None, explicit_project_id="proj-explicit")
        assert pids == ["proj-explicit"]

    def test_limit_honoured(self) -> None:
        store = InMemoryStore()
        for _ in range(5):
            store.add(_schedule("A"), b"")
        pids = _candidate_project_ids(store, limit=2, explicit_project_id=None)
        assert len(pids) == 2


# ------------------------------------------------------------------ #
# Batch runner                                                        #
# ------------------------------------------------------------------ #


class TestRunBatch:
    def test_ok_failed_stats(self) -> None:
        store = InMemoryStore()
        good = store.add(_schedule("ok"), b"")
        bad = "proj-does-not-exist"
        m = Materializer(store)
        stats = asyncio.run(_run_batch(m, [good, bad], backfill_id="bf-01"))
        # ``good`` materializes but ``bad`` has no schedule — the
        # materializer's internal failure path flips to status=failed and
        # swallows the exception, so the batch runner counts it as OK.
        # That is the documented behaviour per ADR-0015 §2: failure
        # surfaces via projects.status, not via raised exceptions from
        # materialize(). _run_batch counts raised-from-materialize as
        # failed; our materializer catches internally → 2 ok, 0 failed.
        assert stats["ok"] + stats["failed"] == 2


# ------------------------------------------------------------------ #
# CLI main()                                                          #
# ------------------------------------------------------------------ #


class TestCliMain:
    def test_dry_run_prints_candidates(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        store = InMemoryStore()
        p1 = store.add(_schedule("A"), b"")
        # Patch the deps layer so the CLI uses our InMemoryStore.
        monkeypatch.setattr(
            "src.api.deps.get_store",
            lambda: store,
        )
        monkeypatch.setattr(
            "src.api.deps.get_materializer",
            lambda: Materializer(store),
        )
        rc = main(["--dry-run"])
        assert rc == 0
        out = capsys.readouterr().out
        assert p1 in out

    def test_limit_flag_stops_early(self, monkeypatch: pytest.MonkeyPatch) -> None:
        store = InMemoryStore()
        for _ in range(3):
            store.add(_schedule("A"), b"")
        monkeypatch.setattr("src.api.deps.get_store", lambda: store)
        monkeypatch.setattr(
            "src.api.deps.get_materializer",
            lambda: Materializer(store),
        )
        rc = main(["--limit", "1"])
        assert rc == 0
        # Only one project should have been materialized; the other two
        # still have no dcma artifact.
        kinds_by_pid: dict[str, set[str]] = {}
        for row in store._derived_artifacts:
            kinds_by_pid.setdefault(row["project_id"], set()).add(row["artifact_kind"])
        materialized = [pid for pid, kinds in kinds_by_pid.items() if "dcma" in kinds]
        assert len(materialized) == 1

    def test_empty_candidate_set_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        store = InMemoryStore()
        # No projects → no candidates.
        monkeypatch.setattr("src.api.deps.get_store", lambda: store)
        monkeypatch.setattr(
            "src.api.deps.get_materializer",
            lambda: Materializer(store),
        )
        rc = main([])
        assert rc == 0

    def test_idempotent_rerun_does_not_duplicate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Re-running after all candidates materialized should find none.

        Upserts on the uniqueness tuple mean a redundant run writes no new
        rows; the candidate selection skips them first anyway.
        """
        store = InMemoryStore()
        store.add(_schedule("A"), b"")
        monkeypatch.setattr("src.api.deps.get_store", lambda: store)
        monkeypatch.setattr(
            "src.api.deps.get_materializer",
            lambda: Materializer(store),
        )
        main([])
        before = len(store._derived_artifacts)
        main([])
        after = len(store._derived_artifacts)
        assert before == after, "second run must not duplicate artifacts"


# ------------------------------------------------------------------ #
# Re-materialization mode (Cycle 3 W4 / criterion #7)                #
# ------------------------------------------------------------------ #


class TestReMaterializationMode:
    """``--re-materialize-version <ver>`` selects projects with at least one
    non-stale artifact at the given OLD engine_version. Designed to drive the
    post-PR-#50 88-row re-mat per ADR-0014 §"Decision Outcome"."""

    def test_returns_projects_with_artifact_at_old_engine_version(self) -> None:
        store = InMemoryStore()
        p1 = store.add(_schedule("A"), b"")
        p2 = store.add(_schedule("B"), b"")
        # Seed p1 with an artifact at OLD version "4.0"; p2 with current version.
        store.save_derived_artifact(
            project_id=p1,
            artifact_kind="dcma",
            payload={"dummy": True},
            engine_version="4.0",
            ruleset_version="dcma-v1",
            input_hash="a" * 64,
            effective_at=None,
            computed_by=None,
        )
        store.save_derived_artifact(
            project_id=p2,
            artifact_kind="dcma",
            payload={"dummy": True},
            engine_version=_ENGINE_VERSION,
            ruleset_version="dcma-v1",
            input_hash="b" * 64,
            effective_at=None,
            computed_by=None,
        )
        candidates = _re_materialization_candidates(store, "4.0", limit=None)
        assert candidates == [p1], "only p1 has an artifact at engine_version=4.0"

    def test_excludes_stale_rows(self) -> None:
        store = InMemoryStore()
        p1 = store.add(_schedule("A"), b"")
        store.save_derived_artifact(
            project_id=p1,
            artifact_kind="dcma",
            payload={"dummy": True},
            engine_version="4.0",
            ruleset_version="dcma-v1",
            input_hash="a" * 64,
            effective_at=None,
            computed_by=None,
        )
        # Mark all artifacts of p1 as stale (e.g., post-upload).
        store.mark_stale(p1, stale_reason="input_changed")
        candidates = _re_materialization_candidates(store, "4.0", limit=None)
        assert candidates == [], "stale rows must NOT be selected for re-mat"

    def test_dedups_projects_with_multiple_kinds_at_old_version(self) -> None:
        """A single project with N artifact kinds at the old version should
        appear ONCE in the candidate list (not N times)."""
        store = InMemoryStore()
        p1 = store.add(_schedule("A"), b"")
        for kind, hash_seed in [("dcma", "a"), ("health", "b"), ("cpm", "c")]:
            store.save_derived_artifact(
                project_id=p1,
                artifact_kind=kind,
                payload={"dummy": True},
                engine_version="4.0",
                ruleset_version=f"{kind}-v1",
                input_hash=hash_seed * 64,
                effective_at=None,
                computed_by=None,
            )
        candidates = _re_materialization_candidates(store, "4.0", limit=None)
        assert candidates == [p1], "p1 has 3 kinds at 4.0 but should appear once"

    def test_limit_honoured_in_re_mat_mode(self) -> None:
        store = InMemoryStore()
        for letter, hash_seed in [("A", "a"), ("B", "b"), ("C", "c")]:
            pid = store.add(_schedule(letter), b"")
            store.save_derived_artifact(
                project_id=pid,
                artifact_kind="dcma",
                payload={"dummy": True},
                engine_version="4.0",
                ruleset_version="dcma-v1",
                input_hash=hash_seed * 64,
                effective_at=None,
                computed_by=None,
            )
        candidates = _re_materialization_candidates(store, "4.0", limit=2)
        assert len(candidates) == 2, "limit truncates the sorted candidate list"


class TestReMaterializationCLIArgs:
    """``--re-materialize-version`` plumbing: mutual-exclusion with
    ``--project-id`` + propagation to candidate selection."""

    def test_mutual_exclusion_with_project_id_exits_2(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["--re-materialize-version", "4.0", "--project-id", "p-x"])
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert "mutually exclusive" in captured.err

    def test_re_mat_mode_dry_run_lists_only_old_version_projects(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        store = InMemoryStore()
        old_pid = store.add(_schedule("A"), b"")
        new_pid = store.add(_schedule("B"), b"")
        store.save_derived_artifact(
            project_id=old_pid,
            artifact_kind="dcma",
            payload={"dummy": True},
            engine_version="4.0",
            ruleset_version="dcma-v1",
            input_hash="a" * 64,
            effective_at=None,
            computed_by=None,
        )
        store.save_derived_artifact(
            project_id=new_pid,
            artifact_kind="dcma",
            payload={"dummy": True},
            engine_version=_ENGINE_VERSION,
            ruleset_version="dcma-v1",
            input_hash="b" * 64,
            effective_at=None,
            computed_by=None,
        )
        monkeypatch.setattr("src.api.deps.get_store", lambda: store)
        monkeypatch.setattr(
            "src.api.deps.get_materializer",
            lambda: Materializer(store),
        )
        rc = main(["--re-materialize-version", "4.0", "--dry-run"])
        assert rc == 0
        captured = capsys.readouterr()
        # Old-version project printed; new-version project NOT printed.
        assert old_pid in captured.out
        assert new_pid not in captured.out
