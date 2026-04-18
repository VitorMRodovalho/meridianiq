# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""In-process pub/sub channels for streaming long-running job progress.

Used by the Monte Carlo simulator (and future ES-optimizer / heavy report
endpoints) to push progress events to a WebSocket subscriber. Each job has
its own ``asyncio.Queue`` keyed by ``job_id``; the WebSocket handler in
``routers/ws.py`` consumes events until it sees ``{"type": "done"}`` or
``{"type": "error"}``.

Single-process: state lives in this module's globals. Cross-process
streaming would need Redis pub/sub or similar; the current Fly.io single-
instance deploy doesn't need that.

Threading note: long-running ops run in starlette's threadpool (sync
handlers) so ``publish()`` must be safe to call from a worker thread. We
require callers to obtain a loop reference at request time and route every
``publish()`` through ``loop.call_soon_threadsafe`` — the
:func:`thread_safe_publisher` helper takes care of this.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_QUEUE_MAX = 256

_channels: dict[str, asyncio.Queue[dict[str, Any]]] = {}


def open_channel(job_id: str) -> asyncio.Queue[dict[str, Any]]:
    """Create or replace a channel for a job. Returns its queue.

    Idempotent — a second ``open_channel(job_id)`` for the same id swaps
    in a fresh queue (events on the old queue become unreachable). Use a
    unique ``job_id`` per logical job to avoid this.
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_QUEUE_MAX)
    _channels[job_id] = queue
    return queue


def get_channel(job_id: str) -> asyncio.Queue[dict[str, Any]] | None:
    """Look up an existing channel; ``None`` when the job isn't registered."""
    return _channels.get(job_id)


def close_channel(job_id: str) -> None:
    """Drop a channel from the registry. Safe to call on unknown ids."""
    _channels.pop(job_id, None)


def publish(job_id: str, event: dict[str, Any]) -> None:
    """Push an event onto a job's channel from the main event loop thread.

    For producers that run in worker threads (e.g. sync handlers calling
    Monte Carlo), use :func:`thread_safe_publisher` instead.
    """
    queue = _channels.get(job_id)
    if queue is None:
        return
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        logger.debug("Progress queue full for job %s — dropping event", job_id)


def thread_safe_publisher(job_id: str) -> Callable[[dict[str, Any]], None]:
    """Return a publisher callable safe to call from a worker thread.

    Captures the current event loop at call time so subsequent ``publish``
    invocations from any thread route their work back into the loop via
    ``call_soon_threadsafe``.
    """
    loop = asyncio.get_event_loop()

    def _publish(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(publish, job_id, event)

    return _publish


def channel_count() -> int:
    """Number of registered channels — useful for diagnostics + tests."""
    return len(_channels)
