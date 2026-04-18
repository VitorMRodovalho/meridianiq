# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""WebSocket endpoints for streaming long-running job progress.

The flow is intentionally pull-then-push:

1. Client picks a unique ``job_id`` (any string — UUID recommended).
2. Client connects ``GET /api/v1/ws/progress/{job_id}`` (WebSocket upgrade).
   The handler opens a channel and starts forwarding events.
3. Client makes the long-running request (e.g.
   ``POST /api/v1/risk/simulate/{project}?job_id=...``). The handler
   publishes ``{"type": "progress", ...}`` events via ``progress.publish``.
4. After the request completes, the handler emits ``{"type": "done"}``;
   the WebSocket sees it, sends a final frame, and closes.

If the client disconnects early, the long-running op continues — progress
events just get dropped (queue overflow handled silently by ``publish``).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket
from fastapi.websockets import WebSocketDisconnect

from ..progress import close_channel, open_channel

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/api/v1/ws/progress/{job_id}")
async def progress_socket(websocket: WebSocket, job_id: str) -> None:
    """Stream progress events for ``job_id`` until the producer signals done."""
    await websocket.accept()
    queue = open_channel(job_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event.get("type") in ("done", "error"):
                break
    except WebSocketDisconnect:
        logger.debug("Progress WS for job %s disconnected by client", job_id)
    finally:
        close_channel(job_id)
        try:
            await websocket.close()
        except RuntimeError:
            # Client already closed the socket — ignore.
            pass
