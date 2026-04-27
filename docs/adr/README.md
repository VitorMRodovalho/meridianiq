# Architectural Decision Records

This directory captures the architectural decisions behind MeridianIQ, using the [MADR](https://adr.github.io/madr/) (Markdown Architectural Decision Records) format.

## Why ADRs

An ADR records the **context**, **decision**, and **consequences** of an architectural choice at the moment it was made. Reading the repository tells you *what* the codebase does; reading the ADR tells you *why* it does it that way — including the trade-offs we accepted and the options we rejected.

Medium-sized projects accumulate decisions quickly. Without ADRs, the reasoning behind "why FastAPI instead of Django?" or "why Fly.io instead of AWS?" lives only in commit messages and the maintainer's memory. Both decay.

For the **active forward plan** (committed cycle scope, queued tech-debt, deferred items), see [`docs/ROADMAP.md`](../ROADMAP.md). This index records *architectural decisions*; the roadmap records *what is being worked on next*.

## Index

| # | Title | Status |
|---|---|---|
| [0000](0000-record-architecture-decisions.md) | Record architecture decisions | accepted |
| [0001](0001-fastapi-for-backend.md) | FastAPI for the backend API | accepted |
| [0002](0002-sveltekit-for-frontend.md) | SvelteKit + Tailwind v4 for the frontend | accepted |
| [0003](0003-supabase-for-auth-db-storage.md) | Supabase for auth, database, and storage | accepted |
| [0004](0004-flyio-for-backend-hosting.md) | Fly.io for backend hosting | accepted |
| [0005](0005-es256-jwt-algorithm.md) | ES256 JWT algorithm with JWKS | accepted |
| [0006](0006-plugin-architecture.md) | Third-party plugin architecture | accepted |
| [0007](0007-websocket-progress-streaming.md) | Minimum viable WebSocket progress | superseded by 0013 |
| [0008](0008-mcp-http-sse-transport.md) | MCP HTTP/SSE transport | accepted |
| [0009](0009-cycle1-lifecycle-intelligence.md) | Cycle 1 v4.0 — Lifecycle Intelligence | accepted |
| 0010 | _(reserved — lifecycle_health engine methodology)_ | reserved, not authored — see ADR-0009 §"Wave 4 outcome" and [`0009-w4-outcome.md`](0009-w4-outcome.md) |
| 0011 | _(reserved — fuzzy-match dep category)_ | reserved, not authored — see ADR-0009 §"Wave A" |
| [0012](0012-schedule-persistence-atomicity.md) | Schedule persistence atomicity (phased) | accepted, phase closed by 0015 |
| [0013](0013-websocket-progress-hardening.md) | WebSocket progress hardening | accepted |
| [0014](0014-derived-artifact-provenance-hash.md) | Derived-artifact provenance hash | accepted, amended by 0015 |
| [0015](0015-async-materialization-state-machine.md) | Async materializer + `projects.status` state machine | accepted |
| [0016](0016-lifecycle-phase-inference.md) | Lifecycle phase inference + override log + lock-flag | accepted |
| [0017](0017-deduplicate-api-keys-migration.md) | Deduplicate `api_keys` migration (012 vs 017) | accepted |
| [0018](0018-cycle-cadence-doc-artifacts.md) | Cycle cadence doc artifacts (roadmap, backlog, audit re-run) — Amendment 1 (2026-04-27) PR-level DA-as-second-reviewer | accepted (amended 2026-04-27) |
| [0019](0019-cycle-2-entry-consolidation-primitive.md) | Cycle 2 entry — Consolidation + Primitive (Option 4) | accepted |
| [0020](0020-calibration-harness-primitive.md) | Calibration harness as a reusable primitive for probabilistic-heuristic engines | accepted |
| [0021](0021-cycle-3-entry-floor-plus-field-shallow.md) | Cycle 3 entry — Floor + Field-surface shallow (Option α) | accepted |
| 0022 | _(reserved — Cycle 4 deep #1 per [ADR-0021](0021-cycle-3-entry-floor-plus-field-shallow.md) §"Decision")_ | reserved, not authored |
| 0023 | _(reserved — Cycle 4 deep #2 per [ADR-0021](0021-cycle-3-entry-floor-plus-field-shallow.md) §"Decision")_ | reserved, not authored |

## Adding a new ADR

1. Copy the most recent ADR as a starting template, or use the MADR template at https://adr.github.io/madr/.
2. Number it next in sequence.
3. Keep the title short and declarative: "Use X for Y".
4. Fill in Context, Decision Drivers, Considered Options, Decision Outcome, Consequences.
5. Status starts as `proposed` during discussion, `accepted` after merge, and can later become `deprecated` or `superseded by ADR-XXXX`.
6. Add the row to the index above.
7. Link from relevant code/docs when the decision is load-bearing.

## Superseding

ADRs are **immutable** once accepted. To change a decision, write a new ADR that supersedes the old one. Update the old ADR's status to `superseded by ADR-XXXX` but leave its content intact — the history matters.
