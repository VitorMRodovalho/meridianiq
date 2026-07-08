# 0027. Park repository as maintenance-only (portfolio triage 2026-07)

* Status: accepted (owner decision routed from the parent portfolio PMO, 2026-07-08)
* Deciders: @VitorMRodovalho
* Date: 2026-07-08
* Cites: issue #196 (triage record + acceptance criteria), issue #26 (funded exception), [ADR-0025](0025-cycle-6-entry-h-shape.md) (Cycle 6 gate state this decision freezes), [ADR-0026](0026-stay-public-open-core-boundary.md) (repo stays public while parked)

## Context and Problem Statement

Portfolio-level triage (2026-07-07/08) found: 48 open issues, no feature activity since late May, and the owner's active lanes fully book capacity through July. Nothing in this repo has an external deadline, a user, or a pilot. Leaving the repo's state implicit ("silence") makes every future session re-derive whether work is expected here; recording the park makes the state explicit and cheap to resume from.

## Decision

1. **The repository is parked as maintenance-only.** No feature waves, no Cycle 7 entry, no release tagging while parked. Maintenance-only means: security-relevant dependency updates (Dependabot), CI keep-alive fixes, and production-incident response continue; everything else waits.
2. **Funded exception: #26** (P0 — apply migration 026 to production Supabase, `api_keys` schema dedup). Production schema debt does not improve with time. It executes standalone with the usual pre-apply checks: backup, and re-verification that prod actually still diverges before applying (the diagnosis is from April and may be stale).
3. **The open backlog carries the `parked` label** so issue-level state matches this record.
4. **`requires-human-decision` items are explicitly deferred with dated notes:** #134 (Cycle 6 hard gate — the gate branch choice remains unresolved and still blocks any Cycle 7 entry), #54 (re-materialize decision of 2026-07-07 stands; execution deferred), #28 (ADR 0017–0021 batch ratification).
5. **Revisit trigger:** the 2026-08 portfolio review, or earlier if a user/pilot shows up (which would also reopen the #134 demand gate on real terms).

## Consequences

* The Cycle 6 close-out (release v4.4.0 or v4.3.1 per ADR-0025) is frozen, not cancelled; the next active session inherits it.
* The backend dependency-floor drift measured 2026-07-07 (fastapi/anthropic/uvicorn et al. behind PyPI) is accepted while parked; only security-driven bumps land. The #131 floor-verify CI step remains the first hygiene item on unpark.
* Frontend/CI stay green via Dependabot flow; the 2026-07-07 hygiene wave (0 open security alerts at park time) is the parked baseline.
