# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Async materialization pipeline for schedule-derivative artifacts.

Canonical architectural record: ``docs/adr/0015-async-materialization-state-machine.md``.
Upstream dependencies: ADR-0009 (Cycle 1 v4.0 Wave 2), ADR-0012 (persistence
atomicity phased d→c, closed by 0015), ADR-0013 (WebSocket progress channel),
ADR-0014 (forensic-grade provenance and input-hash contract — see
``src/database/canonical_hash.py``).

The package exposes:

* :class:`Materializer` — runtime wrapper that enqueues per-project
  materialization jobs on an ``asyncio.Task`` bounded by a ``Semaphore(1)``.
  CPU-bound engine work runs in a ``ProcessPoolExecutor`` so the event loop
  stays responsive on Fly.io's 1-CPU single-instance deploy.
* :class:`JobHandle` — return value of :meth:`Materializer.enqueue`; exposes
  the ``project_id`` and ``job_id`` the upload handler forwards to the WS
  progress channel.
* :class:`StaleMaterializationError` — raised when the re-hash pre-condition
  (ADR-0015 §4) detects a newer upload mid-run. The error is handled by the
  runtime: no partial artifact is persisted and ``projects.status`` is NOT
  flipped — the newer upload's queued job takes over.

A small synchronous fast-path bypasses the queue when the parsed schedule has
fewer than :data:`MATERIALIZER_SYNC_THRESHOLD` activities (default 100); async
overhead outweighs the benefit below that threshold.
"""

from __future__ import annotations

from src.materializer.runtime import (
    MATERIALIZER_SYNC_THRESHOLD,
    MATERIALIZER_TIMEOUT_HARD_S,
    JobHandle,
    Materializer,
    StaleMaterializationError,
)

__all__ = [
    "MATERIALIZER_SYNC_THRESHOLD",
    "MATERIALIZER_TIMEOUT_HARD_S",
    "JobHandle",
    "Materializer",
    "StaleMaterializationError",
]
