# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for ``src/materializer/runtime.py`` — ADR-0015 async materialization.

Async coroutines are driven via ``asyncio.run`` so the suite does not depend
on pytest-asyncio. All fixtures use :class:`InMemoryStore` with a small
schedule so the sync fast-path runs inline (no ``ProcessPoolExecutor``
touched). Integration with ``SupabaseStore`` is validated via the
``set_project_status`` / ``save_derived_artifact`` parity tests in
``tests/test_projects_status_state.py`` and ``tests/test_store_derived_artifacts.py``.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import patch

import pytest

os.environ["ENVIRONMENT"] = "development"

from src.api.progress import _channels, _reset_for_tests, open_channel  # noqa: E402
from src.database.store import InMemoryStore  # noqa: E402
from src.materializer.runtime import (  # noqa: E402
    JobHandle,
    Materializer,
)
from src.parser.models import ParsedSchedule, Project, Task  # noqa: E402


def _make_schedule(activity_count: int = 3) -> ParsedSchedule:
    """Small schedule that runs under the sync-fast-path threshold."""
    return ParsedSchedule(
        projects=[Project(proj_id="P", proj_short_name="TestProj")],
        activities=[
            Task(
                task_id=f"T{i}",
                task_code=f"A{i}",
                task_name=f"Activity {i}",
                task_type="TT_Task",
                status_code="TK_NotStart",
                proj_id="P",
            )
            for i in range(activity_count)
        ],
    )


def _seed(store: InMemoryStore, activity_count: int = 3) -> str:
    pid = store.add(_make_schedule(activity_count), b"")
    # InMemoryStore sync-fast-path stamps 'ready'; flip to 'pending' so the
    # materializer exercises the real async contract.
    store.set_project_status(pid, "pending")
    return pid


@pytest.fixture(autouse=True)
def _reset_progress_channels() -> None:
    _reset_for_tests()


def _drain(job_id: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    ch = _channels.get(job_id)
    if ch is None:
        return events
    while not ch.queue.empty():
        events.append(ch.queue.get_nowait())
    return events


# ------------------------------------------------------------------ #
# Happy path                                                          #
# ------------------------------------------------------------------ #


class TestMaterializerHappyPath:
    def test_writes_artifacts_for_each_registered_engine(self) -> None:
        """Wave 2 ships DCMA + health + CPM. ``float_trends`` is reserved
        (needs baseline-inference, Shallow #1-W2). Wave 3 (ADR-0016)
        registers ``lifecycle_phase_inference``. When ``float_trends``
        ships the assertion grows by one more kind."""
        store = InMemoryStore()
        pid = _seed(store)
        asyncio.run(Materializer(store).materialize(pid))

        kinds = {row["artifact_kind"] for row in store._derived_artifacts}
        assert kinds == {"dcma", "health", "cpm", "lifecycle_phase_inference"}

    def test_flips_status_to_ready(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        asyncio.run(Materializer(store).materialize(pid))
        assert store.get_project_status(pid) == "ready"

    def test_publishes_progress_and_done_events(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        job_id = "job-happy-01"

        async def driver() -> None:
            open_channel(job_id)
            await Materializer(store).materialize(pid, job_id=job_id)

        asyncio.run(driver())

        events = _drain(job_id)
        types = [e["type"] for e in events]
        # W3: 4 engines (DCMA + health + CPM + lifecycle_phase_inference)
        # × 2 events (engine_start + engine_done) = 8 progress events + 1 done.
        assert types.count("progress") == 8
        assert types.count("done") == 1
        assert events[-1]["project_id"] == pid

    def test_uses_sync_fast_path_below_threshold(self) -> None:
        """Below ``MATERIALIZER_SYNC_THRESHOLD`` the runtime never
        instantiates the ``ProcessPoolExecutor``."""
        store = InMemoryStore()
        pid = _seed(store, activity_count=3)  # well under 100
        m = Materializer(store)
        asyncio.run(m.materialize(pid))
        assert m._executor is None


# ------------------------------------------------------------------ #
# Stale-race protection                                               #
# ------------------------------------------------------------------ #


class _StaleStore(InMemoryStore):
    """InMemoryStore whose second ``get_parsed_schedule`` call returns a
    different schedule — simulates a newer upload that arrived
    mid-materialization, producing a divergent ``compute_input_hash``
    between pre-run and pre-save."""

    def __init__(self, original: ParsedSchedule, replacement: ParsedSchedule) -> None:
        super().__init__()
        self._original = original
        self._replacement = replacement
        self._calls = 0

    def get_parsed_schedule(self, project_id: str) -> ParsedSchedule | None:
        self._calls += 1
        return self._original if self._calls == 1 else self._replacement


class TestStaleRaceProtection:
    def _build(self) -> tuple[_StaleStore, str]:
        original = _make_schedule(3)
        replacement = _make_schedule(5)  # divergent hash
        store = _StaleStore(original, replacement)
        pid = store._projects.add(original, b"")
        store._project_statuses[pid] = "pending"
        return store, pid

    def test_stale_mid_run_does_not_flip_status(self) -> None:
        store, pid = self._build()
        asyncio.run(Materializer(store).materialize(pid))
        assert store._project_statuses[pid] == "pending", (
            "a stale run must NOT flip status — the fresh upload will"
        )
        assert store._derived_artifacts == []

    def test_stale_publishes_stale_event(self) -> None:
        store, pid = self._build()
        job_id = "job-stale-01"

        async def driver() -> None:
            open_channel(job_id)
            await Materializer(store).materialize(pid, job_id=job_id)

        asyncio.run(driver())
        stale_events = [e for e in _drain(job_id) if e["type"] == "stale"]
        assert len(stale_events) == 1
        assert stale_events[0]["project_id"] == pid


# ------------------------------------------------------------------ #
# Failure path                                                        #
# ------------------------------------------------------------------ #


class TestMaterializerFailurePath:
    def test_engine_failure_flips_status_failed(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        job_id = "job-fail-01"

        import src.materializer.runtime as runtime_mod

        def boom(_schedule: Any) -> Any:
            raise RuntimeError("engine exploded")

        original_runners = list(runtime_mod._ENGINE_RUNNERS)
        runtime_mod._ENGINE_RUNNERS = [("dcma", boom), *original_runners[1:]]
        try:

            async def driver() -> None:
                open_channel(job_id)
                await Materializer(store).materialize(pid, job_id=job_id)

            asyncio.run(driver())

            assert store.get_project_status(pid) == "failed"
            failed = [e for e in _drain(job_id) if e["type"] == "failed"]
            assert len(failed) == 1
            assert failed[0]["reason"] == "error"
        finally:
            runtime_mod._ENGINE_RUNNERS = original_runners

    def test_missing_schedule_flips_status_failed(self) -> None:
        """When ``get_parsed_schedule`` returns ``None`` the runtime raises
        internally and flips status to 'failed' without leaking the error."""
        store = InMemoryStore()
        pid = store.add(_make_schedule(2), b"")
        store.set_project_status(pid, "pending")

        # Monkey-patch the fetch to simulate the schedule disappearing.
        def empty_fetch(_self: Materializer, _pid: str) -> ParsedSchedule | None:
            return None

        with patch.object(Materializer, "_fetch_schedule", empty_fetch):
            asyncio.run(Materializer(store).materialize(pid))

        assert store.get_project_status(pid) == "failed"


# ------------------------------------------------------------------ #
# Enqueue behaviour                                                   #
# ------------------------------------------------------------------ #


class TestEnqueueBehaviour:
    def test_enqueue_without_running_loop_returns_handle_with_none_task(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        handle = Materializer(store).enqueue(pid, user_id="alice")
        assert isinstance(handle, JobHandle)
        assert handle.project_id == pid
        assert handle.job_id
        assert handle.task is None

    def test_enqueue_in_running_loop_schedules_task(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)

        async def driver() -> None:
            handle = Materializer(store).enqueue(pid)
            assert handle.task is not None
            await handle.task

        asyncio.run(driver())
        assert store.get_project_status(pid) == "ready"

    def test_enqueue_honours_caller_job_id(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        handle = Materializer(store).enqueue(pid, job_id="job-explicit")
        assert handle.job_id == "job-explicit"


# ------------------------------------------------------------------ #
# Timeout                                                             #
# ------------------------------------------------------------------ #


class TestTimeout:
    def test_hard_timeout_flips_status_failed(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        job_id = "job-timeout-01"

        async def stuck(
            self: Materializer,
            project_id: str,
            user_id: str | None,
            job_id: str,
            audit_details_extra: dict[str, Any] | None = None,
        ) -> None:
            await asyncio.sleep(10)

        with patch.object(Materializer, "_materialize_project", stuck):

            async def driver() -> None:
                open_channel(job_id)
                await Materializer(store, timeout_s=1).materialize(pid, job_id=job_id)

            asyncio.run(driver())

            assert store.get_project_status(pid) == "failed"
            failed = [e for e in _drain(job_id) if e["type"] == "failed"]
            assert failed
            assert failed[0]["reason"] == "timeout"


# ------------------------------------------------------------------ #
# Artifact content assertions                                         #
# ------------------------------------------------------------------ #


class TestArtifactContent:
    def test_saved_artifacts_carry_input_hash_and_versions(self) -> None:
        store = InMemoryStore()
        pid = _seed(store)
        asyncio.run(Materializer(store).materialize(pid))

        for row in store._derived_artifacts:
            assert row["engine_version"] == "4.0"
            assert row["input_hash"] and len(row["input_hash"]) == 64
            # W3 lifecycle_phase_inference ruleset is 'lifecycle_phase-v1-2026-04';
            # the W2 engines stay on '<name>-v1'. Both contain '-v1' so the
            # generic guard accepts either format.
            assert "-v1" in row["ruleset_version"]
            assert row["project_id"] == pid
            assert row["is_stale"] is False
            assert row["stale_reason"] is None
