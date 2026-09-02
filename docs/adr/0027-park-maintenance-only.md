# 0027. Park repository as maintenance-only (portfolio triage 2026-07)

* Status: accepted (owner decision routed from the parent portfolio PMO, 2026-07-08) — §"Decision" item 5 amended by **Amendment 1 (2026-09-01)** (revisit outcome: bounded extension + pre-registered auto-trigger) at the bottom of this file.
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
5. **Revisit trigger:** the 2026-08 portfolio review, or earlier if a user/pilot shows up (which would also reopen the #134 demand gate on real terms). *[AMENDED: see Amendment 1 — the trigger fired on 2026-09-01 and resolved to a bounded extension to 2026-09-30 with a pre-registered automatic Path-B fallback.]*

## Consequences

* The Cycle 6 close-out (release v4.4.0 or v4.3.1 per ADR-0025) is frozen, not cancelled; the next active session inherits it.
* The backend dependency-floor drift measured 2026-07-07 (fastapi/anthropic/uvicorn et al. behind PyPI) is accepted while parked; only security-driven bumps land. The #131 floor-verify CI step remains the first hygiene item on unpark.
* Frontend/CI stay green via Dependabot flow; the 2026-07-07 hygiene wave (0 open security alerts at park time) is the parked baseline.

---

## Amendment 1 (2026-09-01) — revisit outcome: bounded extension with a pre-registered fallback

**Status:** accepted (owner decision, 2026-09-01). Amends §"Decision" item 5 above, which remains
unedited per append-only decision-log discipline; the inline *[AMENDED]* pointer delegates authority
to this section.

### What triggered this

§"Decision" item 5 named two triggers. The second (a user or pilot showing up) never fired. The
first — the 2026-08 portfolio review — fired late, on 2026-09-01. A tool showcase did happen in the
interim, which is the closest thing to demand signal this project has ever generated, but **no
conversation from it has been logged to #134**, so the signal exists only as recollection.

That is the whole difficulty: the gate cannot be judged, because the evidence was never written
down, and ADR-0025's Pathway A criteria reject reconstructed evidence by design.

### Decision

1. **The park is extended, bounded, to 2026-09-30.** Maintenance-only continues on exactly the terms
   of §"Decision" item 1. This is an extension, not a re-decision — nothing about scope changes.
2. **One deliverable in the window:** log the showcase conversations to #134 as comments, per the
   Pathway A/B HONEST criteria pre-registered in that issue (date, party by role and company type,
   persona pertinence, topic, quote-grade observation, next action), and convert any named next
   actions. #134 is public; attribution by role and company type only, never by name.
3. **Pre-registered automatic fallback.** If on **2026-09-30** the #134 log carries **fewer than 5
   conversations that are substantive under ADR-0025** — conversations flagged `cosmetic` do not
   count toward this threshold — then **Path B executes automatically**: retire the Cost Engineer
   persona via its own ADR, and close #30/#31/#32 as `not planned`. No further deliberation, no
   fourth deferral. The point of pre-registering is that the decision cannot be re-argued from the
   inside once the number is known.
4. **Single exception that overrides item 3.** If any logged conversation carries a named next action
   with a real counterparty (a pilot, someone's data, a scheduled meeting), then §"Decision" item 5's
   own unpark trigger has fired on its own terms, and the decision becomes **unpark** — Path B is off
   the table and Cycle 7 entry is reconsidered against real signal.

### Why this and not the alternatives

**Not unpark now.** There is no measured demand. Unparking on unmeasured signal is precisely the
binding risk named in the 2026-05-29 strategy verdict ($0 validated demand, not code quality). The
showcase may have produced signal, but "may have" is not a basis for resuming feature work.

**Not Path B now.** The 2026-07-08 decision brief conditioned Path B on the 2026-08 review "arriving
without capacity for A". Capacity existed — the showcase happened. Executing B the week after the one
event most likely to have generated conversations would discard evidence before anyone looked at it.

**Not an open-ended extension.** Path A has now been deferred three times (2026-07-08, 2026-08-27,
and this record). The 2026-07-08 brief already warned that "an indefinitely deferred A corrodes the
ADR discipline" while "a genuine B preserves it". Item 3 is what stops this from becoming a fourth
deferral: the fallback is automatic, and the operator's remaining choice is whether to log
conversations, not whether to decide again.

### Consequences

* Everything frozen by the original record stays frozen: Cycle 7 entry, feature waves, and the
  v4.4.0 / v4.3.1 release tag.
* #26 remains the only *funded exception* under §"Decision" item 2. Separately, the
  production-incident-response clause of §"Decision" item 1 was exercised for the first time on
  2026-09-01 (issue #222, PR #234) — recorded as a comment on #196, and explicitly not a second
  funded exception.
* On the Path-B branch, the Cost Engineer retirement ADR is itself ~1h of drafting and must satisfy
  ADR-0025's Pathway B evidence bar (documented outreach attempt, enumerated closed scope,
  reactivation pathway, and not-already-implicitly-dead). Retiring a never-engaged persona is
  cosmetic-met and does not discharge the gate.
* This amendment does not alter ADR-0025. A cosmetically-met gate still leaves Cycle 7 inheriting
  Cycle 6.5 obligations, whichever branch is taken.
