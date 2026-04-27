# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Async materialization runtime.

See ADR-0015 for the design rationale. Key commitments the implementation must
honour:

* Single ``asyncio.Semaphore(1)`` serialises materialization jobs on the
  worker. Concurrent uploads queue in memory on the Fly.io 1-CPU instance.
* CPU-bound engine work runs via ``loop.run_in_executor(ProcessPoolExecutor)``
  so the event loop stays responsive. Below ``MATERIALIZER_SYNC_THRESHOLD``
  activities the sync fast-path skips the executor entirely.
* Before each ``save_derived_artifact`` call the runtime re-reads the parsed
  schedule and re-computes ``input_hash``; if it diverged from the run-start
  hash the runtime raises :class:`StaleMaterializationError`, persists no
  further artifacts, and does NOT flip ``projects.status``. ADR-0014 P1#6
  stale-race closed via this pre-condition check (ADR-0015 §4).
* Engine execution cost budget: soft 120 s (UI flips to ``stuck`` — visual
  only; no DB state change), hard ``MATERIALIZER_TIMEOUT_HARD_S`` (600 s)
  which cancels the task and flips ``projects.status='failed'`` with
  ``audit_log.details.reason='timeout'`` (ADR-0015 §8).
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import uuid
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from typing import Any

from src.__about__ import __version__ as _ENGINE_VERSION
from src.database.canonical_hash import compute_input_hash
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)

# Schedules with fewer than this many activities materialise inline on the
# event loop — async overhead outweighs the benefit and the work completes
# in sub-second time anyway. Tunable via constructor for tests.
MATERIALIZER_SYNC_THRESHOLD = 100

# Hard timeout for a single materialization run. ADR-0015 §8 — soft
# 120s is a UI-only hint; this value is the hard cutoff that cancels the
# asyncio task and flips projects.status='failed'.
MATERIALIZER_TIMEOUT_HARD_S = 600

# ``_ENGINE_VERSION`` is imported from ``src/__about__.py::__version__`` per
# ADR-0014 §"Decision Outcome" line 44 (see top-of-file imports). Pre-Cycle-3-W4
# it was hardcoded as ``"4.0"`` (multi-cycle drift documented in
# ``AUDIT-2026-04-26-007`` + ``AUDIT-2026-04-26-011``); the migration is pinned
# by ``tests/test_engine_version_source.py``. Bump engine algorithm versions
# below when the corresponding engine's algorithm changes in a way that
# invalidates prior artifacts — ``get_latest_derived_artifact`` returns None on
# version mismatch, forcing re-materialization.
_RULESET_VERSIONS: dict[str, str] = {
    "dcma": "dcma-v1",
    "health": "health-v1",
    "cpm": "cpm-v1",
    # Reserved: float_trends registers here alongside the Shallow #1-W2
    # baseline-inference work.
    "float_trends": "float_trends-v1",
    # Cycle 1 v4.0 W3 (ADR-0016) — lifecycle phase label inference. Bump
    # the version when threshold tuning lands post-W4 calibration; the
    # bump triggers ``mark_stale(reason='ruleset_upgraded')`` per ADR-0014.
    "lifecycle_phase_inference": "lifecycle_phase-v1-2026-04",
}


class StaleMaterializationError(RuntimeError):
    """Raised when the input hash changes mid-materialization.

    The runtime catches this internally; callers see a WARN log and a
    skipped flip. A fresh upload enqueues a new job that supersedes the
    stale one via the uniqueness tuple in ``schedule_derived_artifacts``.
    """


@dataclass(frozen=True)
class JobHandle:
    """Return value of :meth:`Materializer.enqueue`.

    Wave 2 wiring: the upload handler returns ``project_id`` + ``job_id``
    to the client in a ``202 Accepted`` response so the frontend can
    subscribe to the WebSocket progress channel (ADR-0013).
    """

    project_id: str
    job_id: str
    task: asyncio.Task[None] | None


def _serialise_result(result: Any) -> dict[str, Any]:
    """Best-effort canonical JSON-ready dict of an engine result.

    DCMA / health_score / cpm / float_trends all return plain dataclass
    INSTANCES today; ``asdict`` is the cheap path. Fallback for
    non-dataclass results uses the instance ``__dict__`` or coerces to
    ``str``.
    """
    if is_dataclass(result) and not isinstance(result, type):
        return asdict(result)
    if hasattr(result, "model_dump"):
        return result.model_dump()  # type: ignore[no-any-return]
    if hasattr(result, "__dict__"):
        return dict(result.__dict__)
    return {"value": str(result)}


# Top-level functions so they are picklable for ProcessPoolExecutor. Keep
# imports inside each function to avoid eager engine imports in the parent
# process (some test contexts skip the analytics modules entirely).


def _run_dcma(schedule: ParsedSchedule) -> dict[str, Any]:
    from src.analytics.dcma14 import DCMA14Analyzer

    return _serialise_result(DCMA14Analyzer(schedule).analyze())


def _run_health(schedule: ParsedSchedule) -> dict[str, Any]:
    from src.analytics.health_score import HealthScoreCalculator

    return _serialise_result(HealthScoreCalculator(schedule).calculate())


def _run_cpm(schedule: ParsedSchedule) -> dict[str, Any]:
    from src.analytics.cpm import CPMCalculator

    return _serialise_result(CPMCalculator(schedule).calculate())


def _run_lifecycle_phase(schedule: ParsedSchedule) -> dict[str, Any]:
    """W3 lightweight lifecycle phase label inference (ADR-0016).

    Returns the LifecyclePhaseInference dataclass serialised to a dict.
    The frozen dataclass is pickleable for ProcessPoolExecutor; the
    rationale dict is JSON-friendly by construction (only primitives,
    floats, and strings).
    """
    from src.analytics.lifecycle_phase import infer_lifecycle_phase

    return _serialise_result(infer_lifecycle_phase(schedule))


# ``float_trends`` requires (baseline, update) — two schedules. Baseline
# inference ships as Shallow #1-W2 (per ADR-0009); until then the
# materializer skips this slot. The kind is still present in the
# ``schedule_derived_artifacts.artifact_kind`` CHECK list (migration 023)
# so the later addition is a one-line registration here with no schema
# change.
#
# ``lifecycle_phase_inference`` (W3) registers here. The engine is
# stateless and ProcessPoolExecutor-safe (its inputs are the picklable
# Pydantic ParsedSchedule). The materializer skips this runner when
# ``projects.lifecycle_phase_locked = true`` (Cost Engineer JTBD per
# ADR-0016 §2 — overrides stick across uploads).
_ENGINE_RUNNERS: list[tuple[str, Any]] = [
    ("dcma", _run_dcma),
    ("health", _run_health),
    ("cpm", _run_cpm),
    ("lifecycle_phase_inference", _run_lifecycle_phase),
]


class Materializer:
    """Async materialization pipeline.

    Usage::

        m = Materializer(store)
        handle = m.enqueue(project_id, user_id=current_user_id)
        # handle.job_id is the ADR-0013 progress channel identifier.

    The materializer is safe to instantiate per-request or as an app-level
    singleton; the ``asyncio.Semaphore`` and ``ProcessPoolExecutor`` are
    lazily created on first use so test contexts without a running loop
    can still import the module.

    Migration path (ADR-0015 §1): replacing ``enqueue`` with a queue
    publish (``arq`` / Redis) swaps this single class. Consumers downstream
    of ``save_derived_artifact`` are unchanged.
    """

    def __init__(
        self,
        store: Any,
        *,
        max_concurrency: int = 1,
        sync_threshold: int = MATERIALIZER_SYNC_THRESHOLD,
        timeout_s: int = MATERIALIZER_TIMEOUT_HARD_S,
        engine_version: str = _ENGINE_VERSION,
    ) -> None:
        self._store = store
        self._max_concurrency = max_concurrency
        self._sync_threshold = sync_threshold
        self._timeout_s = timeout_s
        self._engine_version = engine_version
        self._sem: asyncio.Semaphore | None = None
        self._executor: ProcessPoolExecutor | None = None

    # -- public API ------------------------------------------------------

    def enqueue(
        self,
        project_id: str,
        user_id: str | None = None,
        job_id: str | None = None,
    ) -> JobHandle:
        """Schedule a materialization job.

        Returns immediately with a :class:`JobHandle`. The actual work
        runs on the current event loop via ``asyncio.create_task``; callers
        do not need to await. When no running loop is available (sync test
        context) the method returns a handle whose ``task`` is ``None``
        and logs a WARNING — the caller is expected to drive the
        ``materialize`` coroutine explicitly.

        The ``job_id`` is pre-registered on the ADR-0013 progress channel
        before ``create_task`` fires so early ``engine_start`` events are
        not dropped. Without this step the materializer's publishes would
        arrive before any ``open_channel`` call — queue lookup returns
        ``None`` and events silently vanish (see ``src/api/progress.py``).
        """
        jid = job_id or str(uuid.uuid4())

        # Pre-register the channel bound to the owner so WebSocket
        # subscribers can authorise and publishes are not dropped on the
        # floor. Failure here is non-fatal — materialization can still
        # complete; progress stream simply degrades to no-op.
        try:
            from src.api.progress import open_channel

            open_channel(jid, owner_user_id=user_id)
        except Exception:
            logger.exception(
                "Materializer.enqueue(%s): failed to open progress channel %s",
                project_id,
                jid,
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "Materializer.enqueue(%s): no running event loop; "
                "call materialize() directly from a sync test harness",
                project_id,
            )
            return JobHandle(project_id=project_id, job_id=jid, task=None)

        task = loop.create_task(self._run(project_id, user_id, jid))
        return JobHandle(project_id=project_id, job_id=jid, task=task)

    async def materialize(
        self,
        project_id: str,
        user_id: str | None = None,
        job_id: str | None = None,
        *,
        audit_details_extra: dict[str, Any] | None = None,
    ) -> None:
        """Synchronously-awaitable materialization driver.

        Used by tests and the backfill CLI. The upload handler calls
        :meth:`enqueue` instead so the HTTP request returns immediately.

        ``audit_details_extra`` is merged into the ``audit_log.details``
        JSON for every ``save_derived_artifact`` written during this run.
        Backfill callers supply ``{"trigger": "system_backfill_v2",
        "backfill_id": "<uuid>"}`` per ADR-0015 §6 so SCL §4 chain-of-
        custody remains intact for system-initiated runs.
        """
        jid = job_id or str(uuid.uuid4())
        await self._run(project_id, user_id, jid, audit_details_extra)

    # -- internals -------------------------------------------------------

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._sem is None:
            self._sem = asyncio.Semaphore(self._max_concurrency)
        return self._sem

    async def _run(
        self,
        project_id: str,
        user_id: str | None,
        job_id: str,
        audit_details_extra: dict[str, Any] | None = None,
    ) -> None:
        sem = self._get_semaphore()
        async with sem:
            try:
                await asyncio.wait_for(
                    self._materialize_project(project_id, user_id, job_id, audit_details_extra),
                    timeout=self._timeout_s,
                )
            except StaleMaterializationError:
                logger.warning(
                    "Materializer: input hash changed for project %s; "
                    "aborting in favour of a newer upload",
                    project_id,
                )
                # Intentional: do NOT flip projects.status. The fresher
                # upload's materializer run is the authoritative one.
                self._publish_event(
                    job_id,
                    {"type": "stale", "project_id": project_id},
                )
                return
            except asyncio.TimeoutError:
                logger.error(
                    "Materializer: hard timeout (%ss) for project %s",
                    self._timeout_s,
                    project_id,
                )
                self._safe_set_status(project_id, "failed")
                self._publish_event(
                    job_id,
                    {"type": "failed", "project_id": project_id, "reason": "timeout"},
                )
                return
            except Exception:
                logger.exception("Materializer: unhandled failure for %s", project_id)
                self._safe_set_status(project_id, "failed")
                self._publish_event(
                    job_id,
                    {"type": "failed", "project_id": project_id, "reason": "error"},
                )
                return

            # Success — flip to ready and broadcast the completion event.
            self._safe_set_status(project_id, "ready")
            self._publish_event(
                job_id,
                {"type": "done", "project_id": project_id},
            )

    async def _materialize_project(
        self,
        project_id: str,
        user_id: str | None,
        job_id: str,
        audit_details_extra: dict[str, Any] | None = None,
    ) -> None:
        schedule = self._fetch_schedule(project_id)
        if schedule is None:
            raise RuntimeError(f"No parsed schedule for project {project_id}")

        # ``compute_input_hash`` scopes the ParsedSchedule slice by the
        # XER-level ``proj_id``, not the Supabase/InMemoryStore uuid —
        # ADR-0014 ``project_id`` is the canonicalization filter, not the
        # storage identifier. For single-project XERs (the common case)
        # we take the first project's ``proj_id``; multi-project XERs are
        # Wave 3+ scope and will iterate per-project.
        hash_scope_id = schedule.projects[0].proj_id if schedule.projects else project_id
        input_hash_start = compute_input_hash(schedule, hash_scope_id)
        effective_at = self._effective_at(schedule)

        loop = asyncio.get_running_loop()

        # Per ADR-0016 §2 the lifecycle_phase_inference engine is skipped
        # when the project is locked (manual override stickiness). The
        # other engines (DCMA / health / CPM) always run — the lock only
        # gates the inference, not the rest of the materialization. We
        # compute the runner subset upfront so progress percentage stays
        # accurate.
        lock_locked = self._lifecycle_phase_locked(project_id)
        runners_to_run = [
            (kind, runner)
            for (kind, runner) in _ENGINE_RUNNERS
            if not (kind == "lifecycle_phase_inference" and lock_locked)
        ]
        total = len(runners_to_run)
        if lock_locked:
            # Council P1 (devils-advocate): keep the event payload shape
            # consistent with engine_done — same keys (type/event/engine
            # /progress) so frontend ProgressIndicator code that
            # destructures ``event.progress`` does not crash on the skip
            # path. ``progress: 0`` because the engine never started.
            self._publish_event(
                job_id,
                {
                    "type": "progress",
                    "event": "engine_skipped",
                    "engine": "lifecycle_phase_inference",
                    "reason": "lifecycle_phase_locked",
                    "progress": 0,
                },
            )

        for idx, (kind, runner) in enumerate(runners_to_run):
            self._publish_event(
                job_id,
                {"type": "progress", "event": "engine_start", "engine": kind},
            )

            if len(schedule.activities) < self._sync_threshold:
                payload = runner(schedule)
            else:
                executor = self._get_executor()
                payload = await loop.run_in_executor(executor, runner, schedule)

            # ADR-0015 §4 stale-race protection: re-hash before each save.
            # If the input moved, a new upload is already queued behind
            # the semaphore — abort without persisting this run's artifacts.
            schedule_now = self._fetch_schedule(project_id)
            if schedule_now is None:
                raise RuntimeError(f"Project {project_id} disappeared mid-materialization")
            hash_scope_now = (
                schedule_now.projects[0].proj_id if schedule_now.projects else project_id
            )
            input_hash_now = compute_input_hash(schedule_now, hash_scope_now)
            if input_hash_now != input_hash_start:
                raise StaleMaterializationError(
                    f"input_hash changed mid-run for project {project_id}"
                )

            self._store.save_derived_artifact(
                project_id=project_id,
                artifact_kind=kind,
                payload=payload,
                engine_version=self._engine_version,
                ruleset_version=_RULESET_VERSIONS[kind],
                input_hash=input_hash_start,
                effective_at=effective_at,
                computed_by=user_id,
                audit_details_extra=audit_details_extra,
            )

            progress_pct = int((idx + 1) * 100 / total)
            self._publish_event(
                job_id,
                {
                    "type": "progress",
                    "event": "engine_done",
                    "engine": kind,
                    "progress": progress_pct,
                },
            )

    # -- helpers ---------------------------------------------------------

    def _get_executor(self) -> ProcessPoolExecutor:
        if self._executor is None:
            # Lazy instantiation keeps module import side-effect-free on
            # hosts where forking after asyncio started is unsafe.
            # ``spawn`` start method is explicitly requested (default on
            # Linux is ``fork`` which inherits the uvicorn event loop's
            # file descriptors, locks, and signal handlers — leading to
            # deadlocks on Supabase HTTP pool + logging). Council
            # (backend-reviewer + devils-advocate) W2 P2 follow-up.
            spawn_ctx = multiprocessing.get_context("spawn")
            self._executor = ProcessPoolExecutor(
                max_workers=self._max_concurrency,
                mp_context=spawn_ctx,
            )
        return self._executor

    def _fetch_schedule(self, project_id: str) -> ParsedSchedule | None:
        getter = getattr(self._store, "get_parsed_schedule", None)
        if getter is None:
            getter = getattr(self._store, "get_project", None)
        if getter is None:
            return None
        result = getter(project_id)
        if isinstance(result, ParsedSchedule) or result is None:
            return result
        # Some stores return a plain dict for get_project metadata; ignore
        # that surface here — the materializer only consumes ParsedSchedule.
        return None

    @staticmethod
    def _effective_at(schedule: ParsedSchedule) -> datetime:
        """Pick the schedule's effective data_date for artifact provenance."""
        if schedule.projects:
            dd = schedule.projects[0].last_recalc_date or schedule.projects[0].sum_data_date
            if dd is not None:
                return dd if dd.tzinfo is not None else dd.replace(tzinfo=UTC)
        return datetime.now(UTC)

    def _safe_set_status(self, project_id: str, status: str) -> None:
        try:
            setter = getattr(self._store, "set_project_status", None)
            if setter is not None:
                setter(project_id, status)
        except Exception:
            logger.exception("Materializer: failed to set status=%s on %s", status, project_id)

    def _lifecycle_phase_locked(self, project_id: str) -> bool:
        """Return True when the project carries a manual lifecycle_phase override.

        Best-effort: a store that does not implement the W3 lock surface
        (legacy InMemoryStore in older test fixtures, partial mocks) is
        treated as unlocked. The lock skip is non-load-bearing if it
        misses — the inference will run and the override write path
        re-establishes the lock on the next user action.
        """
        try:
            getter = getattr(self._store, "get_lifecycle_phase_lock", None)
            if getter is None:
                return False
            return bool(getter(project_id))
        except Exception:
            logger.exception(
                "Materializer: failed to read lifecycle_phase_locked for %s", project_id
            )
            return False

    @staticmethod
    def _publish_event(job_id: str, event: dict[str, Any]) -> None:
        """Best-effort progress publish — never raise out of here."""
        try:
            from src.api.progress import publish

            publish(job_id, event)
        except Exception:
            logger.exception("Materializer: failed to publish progress event for job %s", job_id)
