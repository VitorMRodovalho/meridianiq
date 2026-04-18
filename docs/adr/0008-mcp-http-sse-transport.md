# 0008. MCP server supports stdio, HTTP, and SSE transports

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-18 (backfilled — decision shipped in v3.9.0 commit `3bf04d3`)

## Context and Problem Statement

MeridianIQ has shipped an MCP (Model Context Protocol) server since v3.6, exposing 22 analysis tools (`src/mcp_server.py`) for Claude integration. The initial implementation supported only `stdio` transport — the Claude desktop app launches the server as a subprocess and communicates over stdin/stdout.

As MCP adoption broadened through 2026, cloud-hosted MCP clients (hosted Claude, API-integrated consumers) began requiring HTTP transport. Some existing community clients still expect Server-Sent Events (SSE) as the legacy transport. Limiting MeridianIQ to stdio forced integrators to wrap the server in a bridge, which defeated the "first-class MCP integration" positioning.

## Decision Drivers

- **Reach.** Every transport unlocked is a set of MCP clients that can now integrate directly.
- **No duplication of server logic.** The 22 tools must behave identically across transports.
- **Operational portability.** Running the server on Fly.io (as an HTTP service) must be as simple as running it locally (as an stdio subprocess).
- **Respect the MCP spec.** The official FastMCP library already implements the three transports — writing our own would be a maintenance sink.
- **Backwards compatibility.** Existing stdio integrations must not break.

## Considered Options

1. **Stay stdio-only.** Let integrators bridge.
2. **HTTP-only** — add streamable-http, remove stdio.
3. **HTTP + stdio** — add HTTP, keep stdio, drop SSE as legacy.
4. **All three (stdio, streamable-http, SSE) behind a `--transport` CLI flag.**

## Decision Outcome

**Chosen: Option 4 — all three transports, selected via `--transport stdio|http|sse` at launch time.**

### Rationale

- **FastMCP already implements all three.** The cost of supporting them is a CLI argument and the routing of ASGI vs stdin/stdout. No bespoke protocol code.
- **`--transport stdio` stays the default.** Existing Claude desktop integrations keep working with no change.
- **`--transport http` enables cloud hosting.** The server binds to `--host` / `--port` and exposes `/mcp` as the JSON-RPC endpoint. Validated end-to-end with POST /mcp initialize returning 200 OK.
- **`--transport sse` is for legacy-compat clients.** Low cost to keep; removing it would force some integrators to wait on their own toolchain upgrades.
- **One process, three listening modes.** Each server instance picks one transport at launch; no attempt to multiplex. Keeps operational model simple (one Fly.io service = HTTP transport; local = stdio).

### Rejected alternatives

- **Option 1 (stdio-only)** — kills the cloud-hosted MCP integration story.
- **Option 2 (HTTP-only)** — breaks existing stdio integrations with no upside. Rejected on compatibility grounds.
- **Option 3 (HTTP + stdio, no SSE)** — marginal cost saving, real compatibility cost for the still-SSE-dependent portion of the MCP ecosystem.

## Consequences

**Positive**:
- Cloud-hosted MCP clients integrate without a bridge.
- Local development workflow (stdio subprocess) unchanged.
- Legacy SSE clients remain supported.
- Test surface is shared: the 22 tools are tested once at the tool layer, not per transport.

**Negative**:
- HTTP transport requires deciding on auth for the MCP endpoint. The initial implementation relies on network-level trust (bind to localhost, or put behind a reverse proxy). A dedicated MCP-auth ADR will be needed before the server is publicly hosted with cross-tenant access.
- The `--transport` flag is a single-pick — a server instance cannot serve multiple transports simultaneously. Multi-transport hosting requires multiple processes.
- SSE support adds a maintenance tail. If the MCP ecosystem finishes its SSE-to-HTTP migration, this transport can be deprecated in a later ADR.

**Neutral**:
- Future transport additions (e.g., WebSocket) would follow the same `--transport` flag pattern and can cite this ADR.

## Links

- Commit: `3bf04d3`
- Tests: `tests/test_mcp_server_cli.py`
- Reference: `src/mcp_server.py`
- Closes: v4.0 aspirational "MCP over HTTP" item from `project_backlog.md`
