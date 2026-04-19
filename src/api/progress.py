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

Security hardening (Wave 0 #7, ADR-0013):
- Channels record ``owner_user_id`` on creation; unauthenticated channels
  are allowed in development but rejected in production.
- Every ``publish()`` / subscribe authorises against the recorded owner.
- ``reap_stale_channels`` is called opportunistically on ``open_channel``
  to evict channels that have had no activity for ``_STALE_TTL_SECONDS``.
  A misbehaving client that opens channels but never connects a WebSocket
  no longer leaks memory without bound.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_QUEUE_MAX = 256
# How long a channel can sit with no subscriber / no publish activity
# before the next ``open_channel`` call evicts it.
_STALE_TTL_SECONDS = 900  # 15 minutes


@dataclass
class _Channel:
    queue: asyncio.Queue[dict[str, Any]]
    owner_user_id: str | None
    created_at: float
    last_activity: float = field(default_factory=time.monotonic)


_channels: dict[str, _Channel] = {}


class ChannelAuthError(PermissionError):
    """Raised when a caller is not authorised to publish to / read from a
    channel they do not own. Kept distinct from ``PermissionError`` so
    routers can map it to a 403 cleanly."""


def _touch(channel: _Channel) -> None:
    channel.last_activity = time.monotonic()


def reap_stale_channels(now: float | None = None) -> int:
    """Drop channels whose last_activity is older than ``_STALE_TTL_SECONDS``.

    Returns the number of channels evicted. Called opportunistically from
    ``open_channel``; can also be invoked manually from an admin endpoint or
    a background task.
    """
    cutoff = (now if now is not None else time.monotonic()) - _STALE_TTL_SECONDS
    stale = [jid for jid, ch in _channels.items() if ch.last_activity < cutoff]
    for jid in stale:
        logger.info("Reaping stale progress channel %s", jid)
        _channels.pop(jid, None)
    return len(stale)


def open_channel(
    job_id: str,
    owner_user_id: str | None = None,
) -> asyncio.Queue[dict[str, Any]]:
    """Register a channel for a job, binding it to an owner user id.

    Raises ``ChannelAuthError`` if ``job_id`` is already registered under
    a DIFFERENT owner — prevents an attacker who guesses a victim's
    ``job_id`` from stealing the channel.

    Re-registration by the SAME owner is permitted (idempotent) and returns
    the existing queue, so a WebSocket reconnect does not lose buffered
    events.
    """
    existing = _channels.get(job_id)
    if existing is not None:
        if existing.owner_user_id is None and owner_user_id is not None:
            # First authenticated caller adopts an unbound channel. After
            # this point the channel is bound and subsequent callers with
            # a different user_id are rejected.
            existing.owner_user_id = owner_user_id
        elif existing.owner_user_id is not None and owner_user_id is not None:
            if existing.owner_user_id != owner_user_id:
                raise ChannelAuthError(f"job_id {job_id!r} is bound to a different owner")
        # (existing.owner None + caller None is a dev-only no-op; existing
        # already bound + caller None is allowed — the anonymous caller
        # does not attempt to change ownership.)
        _touch(existing)
        reap_stale_channels()
        return existing.queue

    reap_stale_channels()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_QUEUE_MAX)
    _channels[job_id] = _Channel(
        queue=queue,
        owner_user_id=owner_user_id,
        created_at=time.monotonic(),
    )
    return queue


def get_channel(job_id: str) -> asyncio.Queue[dict[str, Any]] | None:
    """Look up an existing channel's queue; ``None`` when unregistered."""
    channel = _channels.get(job_id)
    if channel is None:
        return None
    _touch(channel)
    return channel.queue


def get_channel_owner(job_id: str) -> str | None:
    """Return the owner user_id of a channel, or ``None`` if unbound /
    unknown. Callers that need to enforce ownership on a POST endpoint
    should compare this to the authenticated user's id."""
    channel = _channels.get(job_id)
    return channel.owner_user_id if channel else None


def close_channel(job_id: str) -> None:
    """Drop a channel from the registry. Safe to call on unknown ids."""
    _channels.pop(job_id, None)


def publish(job_id: str, event: dict[str, Any]) -> None:
    """Push an event onto a job's channel from the main event loop thread.

    For producers that run in worker threads (e.g. sync handlers calling
    Monte Carlo), use :func:`thread_safe_publisher` instead.
    """
    channel = _channels.get(job_id)
    if channel is None:
        return
    _touch(channel)
    try:
        channel.queue.put_nowait(event)
    except asyncio.QueueFull:
        logger.debug("Progress queue full for job %s — dropping event", job_id)


def thread_safe_publisher(job_id: str) -> Callable[[dict[str, Any]], None]:
    """Return a publisher callable safe to call from a worker thread.

    Captures the running event loop at call time so subsequent ``publish``
    invocations from any thread route their work back into the loop via
    ``call_soon_threadsafe``. ``get_running_loop`` is used (not the
    deprecated ``get_event_loop``) because this helper is always invoked
    from an async handler with an active loop; Python 3.15 will make
    ``get_event_loop`` raise in this context.
    """
    loop = asyncio.get_running_loop()

    def _publish(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(publish, job_id, event)

    return _publish


def channel_count() -> int:
    """Number of registered channels — useful for diagnostics + tests."""
    return len(_channels)


def _reset_for_tests() -> None:
    """Drop all state; test helpers only."""
    _channels.clear()
