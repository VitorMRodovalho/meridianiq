# 0032. Move the MCP server to the mcp SDK 2.x (`MCPServer`)

* Status: accepted (merged in #327, 2026-10-31)
* Deciders: @VitorMRodovalho
* Date: 2026-10-30
* Cites: [ADR-0025](0025-cycle-6-entry-h-shape.md) (where the `mcp<2` cap was set), issue #139 (the migration trigger), #227 / #244 / #245 (the regression the cap test exists for), `src/mcp_server.py`, `tests/test_dependency_caps.py`

## Context and Problem Statement

`mcp` was capped `<2` in Cycle 6 W1 because the 2.x SDK removes the module the server imports (`mcp.server.fastmcp`) and renames `FastMCP` to `MCPServer`. Issue #139 set the trigger: when 2.0.0 reaches PyPI, draft the migration within 30 days. 2.0.0 was published on 2026-07-28; the current release is 2.3.0 (2026-10-02). The server still ran on the 1.x line (1.30.0 installed, last 1.x release 2026-09-07).

The SDK's migration guide says the 1.x maintenance line keeps receiving critical fixes and security patches, so staying was possible. It also means every fix that is not critical ships only on 2.x, and the gap grows with each minor.

## Decision Drivers

* The cap was a hold until a deliberate migration, not a permanent pin (#139).
* The server is used through the SDK's public surface only: the constructor, `@mcp.tool()` on 22 synchronous functions that return JSON strings, and `run()` for stdio, streamable HTTP and SSE.
* A major SDK release has already broken this server at import once (#227); whatever lands has to be checked by running the server, not by reading the diff.

## Considered Options

1. Stay on 1.x until a 2.x feature is needed.
2. Migrate to 2.x now and cap at `<3`.

## Decision Outcome

Option 2.

The changes the guide requires, and what this server needed from each:

| 2.x change (vendor migration guide) | Effect here |
|---|---|
| `FastMCP` → `MCPServer`, imported from `mcp.server.mcpserver`; `mcp.server.fastmcp` raises `ModuleNotFoundError` | import and constructor changed |
| Constructor: second positional parameter is `title`; pass the rest by keyword | `instructions` was already a keyword |
| A server without `version` reports an empty string | the server now passes the package version |
| Transport settings moved from the server to `run()` | `--host`/`--port` go to `run()` instead of `mcp.settings`, which no longer has them |
| Synchronous tools run on a worker thread | no tool touches the event loop |
| Raising `MCPError` from a tool becomes a JSON-RPC error | no tool raises it |
| `Context` is injected, `get_context()` removed | `Context` is not used |

The cap becomes `mcp>=2.3,<3`, with the same contract test, and the Dependabot ignore rule for `mcp` majors is lifted, as #139 planned: a widened cap now fails `tests/test_dependency_caps.py` like the other three capped dependencies do.

### Verification

* `tests/test_mcp_cli.py` asserts what `run()` receives for stdio, HTTP and SSE, and that the server reports the package version.
* `tests/test_dependency_caps.py::test_mcp_server_imports_under_the_capped_sdk` imports the server for real under 2.3.0.
* A stdio client from the SDK starts `python -m src.mcp_server`, completes `initialize` (server `MeridianIQ`, version `4.3.0`), lists 22 tools, and calls `upload_xer` on the bundled synthetic sample and `get_health_score` on the result.
* `--transport http --host 127.0.0.1 --port 18765` binds that address and answers `initialize` with 200.

## Consequences

* The production API image does not install the `mcp` extra; the change reaches only people who run the MCP server themselves.
* Clients that read `serverInfo.version` now see the package version instead of an empty string (2.x) or the SDK's version (1.x).
* The next major is a deliberate bump again, behind its own migration review.
* Rollback: revert the change; the 1.x line stays installable under `<2`.
