# 0006. Third-party plugin architecture with entry-point discovery and HTTP surface

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-18 (backfilled — decision shipped in v3.9.0 commits `6917db1` and `a2579bf`)

## Context and Problem Statement

By v3.8.0, MeridianIQ had 45 analysis engines — all first-party, all living under `src/analytics/`. Extending the platform required a direct commit. For a platform whose long-term wedge is community-extensible construction-scheduling intelligence (see `project_opportunity_log.md`), shipping a supported way for third parties to plug in their own engines was a P3 for v4.0 that became feasible during v3.9.

The decision splits into two sub-decisions made together:

- **How are plugins discovered?** — packaging vs config vs runtime registration.
- **How are plugins invoked?** — library-only (Python import) vs an HTTP surface that any language can call.

Both had to converge before the feature shipped.

## Decision Drivers

- **Language-agnostic reach.** If plugins must be Python, the market of potential contributors is smaller than if any language can integrate.
- **Low ceremony for Python plugin authors.** Python packaging has a native mechanism (entry points) that is well-understood — inventing a new one loses the existing knowledge.
- **Isolation.** A broken plugin must never crash MeridianIQ core.
- **Auditability.** Plugins become part of the analysis chain of custody; registry must be introspectable.
- **Minimum viable surface.** Do not commit to a plugin sandbox, resource quotas, or trust tiers in the first cut — ship discovery + HTTP first, harden later.

## Considered Options

1. **No plugins.** Force every extension to land in `src/analytics/`.
2. **Monorepo plugins** — a `plugins/` subdirectory that is imported at startup.
3. **Entry-point discovery only** — plugins are regular Python packages that declare themselves via `[project.entry-points."meridianiq.engines"]`, discovered at startup with `importlib.metadata.entry_points()`.
4. **Entry-point discovery + HTTP invocation surface** — option 3 plus a REST endpoint (`GET /api/v1/plugins`, `POST /api/v1/plugins/{name}/run/{project_id}`) so callers do not need to be Python.
5. **HTTP-only plugins (no entry points)** — plugins are separate services, MeridianIQ calls them over HTTP.

## Decision Outcome

**Chosen: Option 4 — entry-point discovery for Python-side registration, plus a minimal HTTP surface for invocation.**

### Rationale

- **Entry points are the native Python idiom.** Anyone who has packaged a Python CLI or a `pytest` plugin already knows the mechanism. Zero learning curve.
- **Discovery at FastAPI startup** (`discover_plugins()` at module load) gives a single, auditable point where the registry is populated. Exceptions during discovery are logged and swallowed per plugin — one broken plugin does not prevent the others from loading or the server from starting.
- **HTTP invocation surface broadens the audience** beyond Python without forcing all plugin authors into an HTTP deployment model. Python authors still write normal Python code.
- **Keeps the sandboxing decision open.** The `AnalysisEngine` Protocol is a contract, not a sandbox. If later the project needs resource limits or process isolation, we wrap the invocation without changing the contract.

### Rejected alternatives

- **Option 1 (no plugins)** — closes the community-extensibility wedge for v4.0. Rejected on strategy grounds.
- **Option 2 (monorepo)** — still requires a PR to ship any new engine. No gain over the status quo.
- **Option 3 (discovery only)** — forces every consumer to be Python. Unacceptable for a platform that integrates with Claude (MCP) and ERPs (HTTP webhooks) in other languages.
- **Option 5 (HTTP-only)** — raises the bar to contribute; an author must package *and* host a service. Hostile to the solo-developer contribution pattern.

## Consequences

**Positive**:
- Extension is possible without a core PR.
- Sample plugin at `samples/plugin-example/` gives contributors a starting template.
- Broken plugins are isolated: logged, skipped, never propagated.
- Registry is introspectable (`GET /api/v1/plugins`).

**Negative**:
- Plugin execution shares the main FastAPI worker — a misbehaving plugin can block requests. Sandboxing + timeouts are P3 follow-up work, not in this ADR.
- Plugins run with the same credentials as the main app (no RBAC per plugin). Later additions must tighten this before multi-tenant plugin ecosystems are realistic.
- Entry-point-based discovery requires users to install plugins into the same Python environment as MeridianIQ — not a network-registered model.

**Neutral**:
- The `samples/plugin-example/` reference is published as a starting point, not a contract. Its structure may evolve; ADR-0006 covers only the discovery+HTTP mechanism.

## Links

- Commits: `6917db1` (registry + entry-point discovery), `a2579bf` (HTTP surface + startup discovery)
- Tests: `tests/test_plugins.py`, `tests/test_api_plugins.py`
- Reference: `src/plugins/__init__.py`, `src/api/routers/plugins.py`, `samples/plugin-example/`
