# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""WebSocket + REST endpoints for streaming long-running job progress.

Security model (Wave 0 #7, ADR-0013):

- Clients MUST call ``POST /api/v1/jobs/progress/start`` to obtain a
  server-generated ``job_id`` (UUID v4) bound to their authenticated
  user. Client-picked job ids are rejected — the previous flow let an
  attacker who could guess a victim's id eavesdrop on their events.
- The WebSocket handshake requires a Bearer JWT via ``?token=<jwt>`` or
  an API key via ``?api_key=<key>`` in the query string. In production
  an unauthenticated handshake is closed with code 4401. In development
  unauthenticated handshakes are permitted to keep the test harness
  simple, but a channel owner recorded on POST is still enforced.
- The path param ``job_id`` is constrained to a UUID v4 regex at the
  router level — malformed values get 404 at routing time rather than
  leaking to the handler.
- Channels are evicted after 15 minutes of inactivity (see
  ``progress.reap_stale_channels``). A misbehaving client that opens
  jobs but never connects no longer leaks memory unbounded.

Flow:

1. Client: ``POST /api/v1/jobs/progress/start`` → ``{"job_id": "...",
   "ws_url": "/api/v1/ws/progress/<uuid>"}``. Server opens a channel
   bound to the current user.
2. Client: ``GET /api/v1/ws/progress/{job_id}?token=<jwt>`` (WebSocket
   upgrade). The handler authenticates, verifies ownership, and forwards
   events from the channel queue.
3. Client: ``POST /api/v1/risk/simulate/{project_id}?job_id=<uuid>``
   (or similar). The handler publishes progress events; the WebSocket
   relays them. On completion a ``{"type": "done"}`` frame closes the
   socket.

If the client disconnects early, the long-running op continues and
progress events drop silently; the reaper sweeps the channel later.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, status
from fastapi.websockets import WebSocketDisconnect

from ..auth import get_current_user, require_auth, validate_api_key
from ..deps import RATE_LIMIT_READ, limiter
from ..progress import (
    ChannelAuthError,
    close_channel,
    get_channel_owner,
    open_channel,
)
from src.database.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# UUID v4 regex — accepts both hex and hyphenated forms. Matches the format
# of ``uuid.uuid4()`` output. The WebSocket path param uses this at router
# level so non-UUID ids are rejected before reaching the handler.
_UUID_RE = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

# ADR-0019 §"W1 — D3" — heartbeat cadence. Every HEARTBEAT_INTERVAL
# seconds the WS handler ticks: re-checks the JWT ``exp`` claim and
# emits an ``auth_check`` keepalive frame. If the token has expired
# the handler closes with 4401 (frontend composable maps this to
# ``'auth_expired'`` per ADR-0013). The constant is module-scope so
# tests can monkeypatch it down to a fast value.
HEARTBEAT_INTERVAL_SECONDS = 30.0


def _decode_exp_unverified(token: Optional[str]) -> Optional[float]:
    """Extract the ``exp`` claim from a JWT without verifying signature.

    Safety: ``get_current_user`` already verified the signature at
    handshake, and the heartbeat re-reads the SAME ``?token=`` query
    param (the URL doesn't change mid-stream) — so this helper cannot
    be tricked into trusting a different payload via swap. A future
    refresh-token mechanism would need a different code path; do not
    reuse this helper for tokens that have NOT been signature-verified
    upstream. Audience and ``nbf`` re-checks are intentionally skipped
    for the same reason.

    Returns ``None`` if the token is missing, malformed, or has no
    ``exp`` claim.

    ADR-0019 §"W1 — D3": this powers the heartbeat-side token-validity
    check that triggers a 4401 close when the JWT expires mid-stream.
    """
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_aud": False},
        )
        exp = payload.get("exp")
        return float(exp) if exp is not None else None
    except (jwt.DecodeError, jwt.InvalidTokenError, ValueError, TypeError) as exc:
        logger.warning("Could not decode JWT exp claim: %s", exc)
        return None


def _auth_from_ws_query(ws: WebSocket) -> Optional[dict[str, object]]:
    """Authenticate a WebSocket handshake by query params.

    Accepts ``?token=<jwt>`` or ``?api_key=<key>``. Returns the user dict
    or ``None``. Does not raise — callers decide whether missing auth is
    a hard fail (production) or acceptable (dev).
    """
    api_key = ws.query_params.get("api_key")
    if api_key:
        user = validate_api_key(api_key)
        if user:
            return user

    token = ws.query_params.get("token")
    if token:
        try:
            from fastapi.security import HTTPAuthorizationCredentials

            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            return get_current_user(creds)
        except HTTPException:
            return None
        except Exception as exc:
            logger.warning("WS token decode failed: %s", exc)
            return None
    return None


@router.post("/api/v1/jobs/progress/start", status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_READ)
def start_progress_job(
    request: Request,
    user: dict[str, object] = Depends(require_auth),
) -> dict[str, str]:
    """Allocate a server-generated ``job_id`` bound to the caller.

    Clients must call this before opening a WebSocket or invoking a
    long-running endpoint with ``?job_id=<...>``. Rejecting client-
    supplied ids closes the pre-existing vulnerability where an
    attacker who guessed a victim's id could steal their progress
    events.

    Rate limit: ``RATE_LIMIT_READ`` (30/minute per remote IP). Each
    successful call allocates an in-memory queue (~20 KB); without a
    cap a single client could exhaust memory by opening channels in
    a tight loop. The 15-minute reaper bounds long-term leakage but
    does nothing against burst abuse — that is this decorator's job.

    Why ``READ`` (30/min) instead of ``MODERATE`` (10/min): slowapi
    keys on remote IP via ``get_remote_address``, not on
    authenticated user, and ``startProgressJob()`` is invoked by every
    page entry that uses the WS progress composable. A small
    enterprise team behind a single egress NAT can legitimately exceed
    10/min just from page-loads. Per-user keying (``key_func`` extracting
    user_id from the JWT) is the proper fix and is tracked as a
    follow-up; using the lighter bucket here is the W0 hygiene
    compromise. See ADR-0019 §"W0 — D1".

    Returns:
        ``{"job_id": "<uuid>", "ws_url": "/api/v1/ws/progress/<uuid>"}``
    """
    job_id = str(uuid.uuid4())
    user_id = str(user["id"])
    open_channel(job_id, owner_user_id=user_id)
    logger.info("Allocated progress job %s for user %s", job_id, user_id)
    return {
        "job_id": job_id,
        "ws_url": f"/api/v1/ws/progress/{job_id}",
    }


@router.websocket("/api/v1/ws/progress/{job_id:path}")
async def progress_socket(websocket: WebSocket, job_id: str) -> None:
    """Stream progress events for ``job_id`` until the producer signals done.

    Authentication:
        - ``?token=<jwt>`` Bearer JWT
        - or ``?api_key=<key>`` API key

    In production an unauthenticated handshake is closed with code 4401.
    If the caller is authenticated but does not own the channel, the
    handshake is closed with 4403.
    """
    # UUID validation — accept bare UUID v4 only.
    import re

    if not re.fullmatch(_UUID_RE, job_id):
        await websocket.close(code=4404, reason="Invalid job_id format")
        return

    user = _auth_from_ws_query(websocket)
    env_prod = settings.ENVIRONMENT == "production"
    if user is None and env_prod:
        await websocket.close(code=4401, reason="Authentication required")
        return

    # Ownership check: if the channel was bound to a user on POST, the
    # subscriber MUST match. Anonymous (unbound) channels are only
    # permitted in development.
    user_id = str(user["id"]) if user else None
    owner = get_channel_owner(job_id)
    if owner is not None and user_id is not None and owner != user_id:
        await websocket.close(code=4403, reason="Forbidden")
        return
    if owner is None and env_prod:
        # The only legitimate way to reach a channel in production is to
        # have gone through /jobs/progress/start, which binds owner.
        await websocket.close(code=4403, reason="Unbound channel")
        return

    try:
        queue = open_channel(job_id, owner_user_id=user_id)
    except ChannelAuthError:
        await websocket.close(code=4403, reason="Channel bound to another user")
        return

    await websocket.accept()

    # ADR-0019 §"W1 — D3" — heartbeat is opt-in via ``?hb=1`` so that
    # frontend bundles cached before this deploy (which have no
    # ``auth_check`` branch in ``_handleEvent`` and would mis-classify
    # the frame as ``error``) keep the v4.0.1 silent-streaming behavior
    # unchanged. The current frontend always sends ``hb=1``; legacy
    # tabs do not.
    heartbeat_enabled = websocket.query_params.get("hb") == "1"

    # Capture handshake-time auth state once. The heartbeat tick uses
    # these to re-validate the principal:
    #   - JWT token: re-check the (same) token's ``exp`` claim.
    #   - API key: re-validate the (same) key against the revocation
    #     surface. Without this, a key revoked mid-stream would
    #     continue receiving real-time progress until the producer
    #     terminates.
    # Dev-mode anonymous handshake (``user is None`` and not prod) is
    # deliberately skipped — there's nothing to re-check.
    token_query = websocket.query_params.get("token")
    api_key_query = websocket.query_params.get("api_key")
    token_exp: Optional[float] = None
    if token_query and user is not None:
        token_exp = _decode_exp_unverified(token_query)

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                # Defensive: if a producer published RIGHT as the
                # ``wait_for`` cancellation fired, the item may be in
                # the queue. Drain non-blockingly so we don't sandwich
                # a heartbeat between the producer's ``done`` event and
                # the next-iteration ``get()``. CPython 3.10+
                # ``asyncio.Queue.get`` cancellation is item-safe
                # (Python issue #46622 family fixed) but the explicit
                # drain costs nothing and makes the contract obvious.
                try:
                    pending_event = queue.get_nowait()
                except asyncio.QueueEmpty:
                    pending_event = None
                if pending_event is not None:
                    await websocket.send_json(pending_event)
                    if pending_event.get("type") in ("done", "error"):
                        break
                    continue

                if not heartbeat_enabled:
                    # Legacy client (no ``hb=1``) — preserve v4.0.1
                    # behavior: just block on the next event.
                    continue

                # Heartbeat tick — re-check the principal.
                if token_exp is not None and time.time() >= token_exp:
                    await websocket.close(code=4401, reason="Token expired")
                    return
                if api_key_query and validate_api_key(api_key_query) is None:
                    await websocket.close(code=4401, reason="API key revoked")
                    return
                # Server-initiated keepalive. Schema:
                #   ``{"type": "auth_check", "ts": <unix-seconds-float>}``.
                await websocket.send_json({"type": "auth_check", "ts": time.time()})
                continue

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
