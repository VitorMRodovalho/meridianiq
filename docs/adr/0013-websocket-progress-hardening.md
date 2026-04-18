# 0013. WebSocket progress streaming — authentication, server-generated ids, stale-channel reaper

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-18
* Council review: `backend-reviewer` (pre-check via Wave 0 #7 brief); `devils-advocate` (P1 surfaced via Cycle 1 council review of ADR-0009)

## Context and Problem Statement

v3.9.0 wave 10 shipped the WebSocket progress endpoint
(`GET /api/v1/ws/progress/{job_id}`) as a real-time transport for Monte Carlo progress. The v3.9 delivery explicitly deferred authentication and transport hardening as known debt in ADR-0007 ("Minimum viable surface — no auth on the socket, client-picked `job_id`").

The devils-advocate review at the open of Cycle 1 (2026-04-18) flagged three P1 issues against the v3.9 shape that Wave 0 of v4.0 must close before any further features build on the progress channel:

1. **No authentication on the WebSocket handshake.** Any browser session could connect to `/api/v1/ws/progress/{anything}` and, if it guessed a victim's `job_id`, eavesdrop on the victim's progress events.
2. **Client-supplied `job_id`.** The v3.9 contract was "client picks any string — UUID recommended." A client that uses a short or predictable id (timestamp, sequential counter, weak PRNG) exposes every other client on the platform to enumeration.
3. **No channel TTL reaper.** `open_channel(job_id)` allocates an `asyncio.Queue` that stays in the process registry until explicitly closed. A misbehaving or crashed client that opens channels but never completes them leaks memory without bound.

## Decision Drivers

- **Security posture must match the rest of the platform.** Every other write endpoint requires a Bearer JWT or API key under `optional_auth` / `require_auth`. The WebSocket inheriting a less-strict posture contradicts the system-wide contract.
- **Preserve backward compatibility in development.** The existing integration tests and the local dev loop use unauthenticated connections. Forcing auth in development would cost more than it saves at the current maturity level.
- **Minimum memory cost.** An in-process registry with opportunistic reaper avoids adding a lifecycle task, a background loop, or Redis. MeridianIQ deploys on a single Fly.io instance — complexity that assumes multi-worker state is premature.
- **Path forward for async materialization (Wave 1/2).** When Wave 2 makes the upload path async and issues real `202 Accepted {"job_id": ...}` responses, the server-generated `job_id` allocation path must already exist so the async upload flow is a drop-in consumer of the same endpoint.

## Considered Options

1. **A — Do nothing this cycle, log as P1, revisit in v4.1.** Inherit the v3.9 shape. Rejected — the devils-advocate review is explicit that "any progress endpoint that a v4.0 feature builds on inherits whatever security posture is in place today", and Wave 1/2 will build on this endpoint.

2. **B — Require auth, keep client-picked `job_id` with an enforced UUID-v4 format.** Add Bearer/API-key auth on the WS handshake. Validate `job_id` as UUID v4 at the router level. Bind `{job_id → user_id}` on first bind; reject cross-user re-binding. Does NOT introduce a server-generated-id endpoint.

3. **C — Require auth, server-generated `job_id` only.** Add `POST /api/v1/jobs/progress/start` that returns a UUID and pre-opens a channel bound to the caller. Reject client-supplied ids entirely. Maximum security; breaks the v3.9 test harness unless migrated.

4. **D — Option C's endpoint + backward-compatible client-picked fallback.** Add the server-generated endpoint. Keep accepting client-supplied UUID-v4 ids during v4.0 with a deprecation warning in the response header. Remove the fallback in v4.1.

## Decision Outcome

**Chosen: Option D — server-generated endpoint as the blessed path, client-picked UUIDs still accepted in development.**

### Shape of the implementation

- **New endpoint** `POST /api/v1/jobs/progress/start` (`require_auth`). Returns `201 Created` with `{"job_id": "<uuid4>", "ws_url": "/api/v1/ws/progress/<uuid4>"}`. Pre-opens a channel bound to the caller's `user_id`. This is the path that Wave 1/2 async uploads will use for their response body.
- **WebSocket authentication** via `?token=<jwt>` OR `?api_key=<key>` query parameters. In production an unauthenticated handshake closes with code `4401`. In development unauthenticated is permitted so the existing integration tests remain stable.
- **Ownership binding** enforced at three points:
  - `open_channel(job_id, owner_user_id)` records the first user; a different user calling `open_channel` with the same `job_id` raises `ChannelAuthError` (mapped to close code `4403` at the WebSocket layer).
  - The WS handshake calls `get_channel_owner(job_id)` and closes with `4403` on mismatch.
  - The POST endpoint that publishes events (currently `/api/v1/risk/simulate/{project}`) calls `get_channel_owner(job_id)` and returns HTTP 403 if the caller is not the channel owner.
- **Path-level UUID validation.** The `{job_id}` path param is validated against a UUID-v4 regex inside the handler before any further work. Non-UUID values close the socket with code `4404`.
- **Stale-channel reaper.** `reap_stale_channels()` is invoked opportunistically from every `open_channel` call and evicts channels whose `last_activity` is older than `_STALE_TTL_SECONDS` (15 minutes). No dedicated lifecycle task — the reaper piggybacks on the upload flow, which is the primary source of channel creation.
- **Admin observability.** `channel_count()` remains, and a future admin endpoint can surface it alongside the `cache_stats()` surface. Not shipped this wave.

Close codes returned by the WebSocket:

| Code | Meaning |
|---|---|
| 4401 | Production + no valid token |
| 4403 | Bound channel + caller is not the owner, or production + channel never bound |
| 4404 | `job_id` not a valid UUID v4 |

### Rationale

- **Option D is the cleanest migration.** Existing tests (`test_progress_ws.py::test_websocket_streams_done_event_when_simulation_finishes`) use UUID-v4 ids and no token, which works under dev-mode fallback. Option C would force us to rewrite every integration test and also migrate the MCP server's progress consumer in one shot — larger blast radius.
- **Server-generated endpoint unblocks Wave 1/2.** The async upload flow (per ADR-0009) needs to hand the client a `job_id` in its `202 Accepted` response. `POST /api/v1/jobs/progress/start` is that primitive, usable stand-alone today and usable as an internal call from the upload handler later.
- **Opportunistic reaping rather than a lifecycle task** is the right cost for v4.0. A dedicated background task requires FastAPI `lifespan` rewiring (the app currently has none), introduces a test-harness coupling (we'd need a way to suppress the task in tests), and costs more than the memory it saves on a single-instance deploy.
- **Dev-mode anonymous fallback preserved intentionally.** Forcing auth in development would force every test to include a JWT, or force the harness to mint one, which is more yak-shaving than is worth paying. In production the `ENVIRONMENT == "production"` gate turns the fallback off.

### Rejected alternatives

- **Option A** — rejected; deferring closes the escape hatch the council review explicitly flagged as blocking Wave 1/2 work.
- **Option B** — rejected as a standalone endpoint; it closes eavesdropping but not the client-side RNG dependency. An attacker who can predict a client's UUID generation still wins.
- **Option C** — rejected as standalone; too aggressive for Wave 0 scope. Re-introduced as the target for v4.1 when the dev fallback can be removed.

## Consequences

**Positive**:
- Unauthenticated WebSocket connections are refused in production.
- `job_id` values the server issues are unguessable (uuid4, 122-bit entropy).
- A client that crashes before closing its channel no longer leaks memory — the next opener's opportunistic reap clears it within 15 minutes.
- The `POST /api/v1/jobs/progress/start` endpoint is the async-upload primitive Wave 1/2 will reuse.

**Negative**:
- The WebSocket flow is now a 3-step handshake (allocate → connect → run the job). Older clients must migrate; the deprecation of the client-picked fallback will land in v4.1.
- Opportunistic reaping means a channel can live up to 15 minutes past its useful life if no other upload happens on the instance. Acceptable for the current deploy; a dedicated reaper task becomes required only when traffic per instance drops below the reap cadence.
- Dev-mode anonymous fallback is a latent foot-gun — a future contributor who debugs a prod bug locally won't reproduce the auth rejection. The ADR explicitly documents this trade; production environment gate is the only guard.

**Neutral**:
- `channel_count()` and the `ChannelAuthError` class become public surface of `src.api.progress`. Once published, changing their signatures requires an ADR-amendment.
- The `_UUID_RE` in the router is duplicative with Python's `uuid.UUID()` constructor; chose regex over try/except because it runs before `accept()` and is the cheapest way to keep non-UUID probes out of the log noise.

## Links

- Supersedes-in-spirit: ADR-0007 `minimum-viable-progress-ws` (status becomes `superseded-by-0013` after this lands).
- Related ADRs: ADR-0009 (Cycle 1 v4.0 Wave 0 #7 brief); ADR-0007 (original progress streaming decision — documented the deferred debt that Wave 0 #7 closes).
- Anticipated follow-up: v4.1 removes the dev-mode anonymous fallback; async upload in Wave 2 consumes the `/jobs/progress/start` endpoint.
- Code: `src/api/progress.py` (owner binding + reaper), `src/api/routers/ws.py` (WS auth + start_progress_job), `src/api/routers/risk.py:180-196` (caller-ownership enforcement on publish path).
- Tests: `tests/test_progress_ws.py` (pre-existing, updated to use UUID), `tests/test_progress_ws_hardening.py` (ownership + reaper + 4404 + endpoint).
