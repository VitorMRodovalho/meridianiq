# 0007. WebSocket progress streaming for long-running analytics

* Status: superseded-by-0013 — authentication, server-generated ids, and the stale-channel reaper landed in Wave 0 #7 of v4.0 Cycle 1 (2026-04-18)
* Deciders: @VitorMRodovalho
* Date: 2026-04-18 (backfilled — decision shipped in v3.9.0 commit `8704be6`)

## Context and Problem Statement

Monte Carlo risk simulation with the default 1,000–10,000 iteration count is a seconds-to-minutes operation. Before v3.9, the frontend opened the request and waited — no intermediate feedback, no "estimated time remaining", no visible progress. Users reported two failure modes: (a) assumed the browser or server had hung and reloaded, losing the run; (b) walked away and came back to find the result had succeeded or failed silently.

The planning lens from `project_opportunity_log.md` listed real-time progress for heavy analytics as a v4.0 aspirational. Enough of the use case was obvious that it landed as the last wave of v3.9, with Monte Carlo as the first consumer. The transport choice constrains future consumers (optimizer, report generation), so it is worth a dedicated ADR.

## Decision Drivers

- **One-way fan-out is the dominant pattern** — the server produces progress events, the client consumes them. Bidirectional messaging is nice-to-have, not required.
- **Reconnect tolerance** — users close laptops, networks blip. Getting the final result must not depend on an uninterrupted channel.
- **Pattern reuse across engines** — the mechanism must extend to the ES optimizer and heavy report generators without re-architecting per engine.
- **Browser-native** — must work from standard SvelteKit frontend code without a polyfill.
- **Operational simplicity** — single-instance Fly.io; no message broker in the stack today.

## Considered Options

1. **HTTP polling** — frontend polls `/api/v1/jobs/{id}/progress` every N seconds.
2. **Server-Sent Events (SSE)** — one-way stream, HTTP-friendly, browser-native.
3. **WebSocket with in-memory channel registry** — bidirectional pipe, per-job `asyncio.Queue`, `thread_safe_publisher` bridging sync simulator threads via `loop.call_soon_threadsafe`.
4. **Chunked HTTP response** — server holds connection open and writes progress as chunks until done.

## Decision Outcome

**Chosen: Option 3 — WebSocket endpoint `/api/v1/ws/progress/{job_id}` with an in-memory channel registry in `src/api/progress.py`.**

### Rationale

- **Matches FastAPI's native primitives.** FastAPI's WebSocket support is first-class; no extra library.
- **In-memory channel registry avoids a broker.** With single-instance Fly.io, per-job `asyncio.Queue` is sufficient. If the deployment later becomes multi-instance, the registry becomes the one place to swap in Redis pub/sub.
- **Pattern generalises.** Any engine that has a synchronous thread (Monte Carlo today, optimizer next, report-gen after) plugs in via `thread_safe_publisher`. No per-engine transport concerns.
- **Bidirectional retained.** Though today's use is one-way, keeping WebSocket instead of SSE leaves the door open for client-side cancel signals without changing transport.

### Rejected alternatives

- **Option 1 (polling)** — wastes requests, introduces latency floor equal to poll interval, and the batch of already-produced events between polls is lossy unless queued server-side anyway.
- **Option 2 (SSE)** — simpler, but SSE reconnection semantics (`Last-Event-ID`) are awkward with the in-memory queue model, and the one-way limit removes the future option of client-side cancels.
- **Option 4 (chunked HTTP)** — fragile to proxies that buffer, and does not compose with SvelteKit's `fetch`-based patterns cleanly.

## Consequences

**Positive**:
- Monte Carlo page can show a progress bar grounded in actual simulator events.
- Pattern is ready for optimizer + report-generation follow-ups (P3 backlog).
- Single-file transport implementation (`src/api/progress.py`) that's easy to audit.

**Negative**:
- **Auth gap shipped.** The initial WebSocket endpoint does not require a Bearer token; `job_id` is assumed to be an unguessable UUID but is client-supplied. A red-team review flagged this as a P1 for the v4.0 cycle. See `project_v40_cycle_1.md` for the hardening plan (server-generated job_id + WS auth + TTL reaper).
- **No channel cleanup on dangling sessions** — a client that opens a WS and never calls `close_channel` leaves the queue live until process restart. Reaper coroutine deferred.
- **In-memory registry does not survive restarts.** On a Fly.io cold-start, any in-flight progress channel is lost. Client must reconnect; server must republish the current state — latter is not yet implemented.
- **Single-instance assumption.** If MeridianIQ ever scales horizontally, the registry must move to Redis or equivalent pub/sub; this ADR is not superseded by that move — the change is a swap of the registry implementation, not of the WebSocket contract.

**Neutral**:
- WebSocket is a new transport surface for the platform. Future endpoints may follow the pattern; deviations should reference this ADR.

## Links

- Commit: `8704be6`
- Tests: `tests/test_api_ws_progress.py`, `tests/test_progress.py`
- Reference: `src/api/progress.py`, `src/api/routers/ws.py`
- Closes: BUGS.md #14 (partial — Monte Carlo only; optimizer + reports deferred)
- Follow-up work: `project_v40_cycle_1.md` Wave 0 (auth + reaper + server-generated job_id)
