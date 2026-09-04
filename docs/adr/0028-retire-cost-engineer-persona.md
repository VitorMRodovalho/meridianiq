# 0028. Retire the Cost Engineer persona from active scope

* Status: **proposed** — pre-drafted 2026-09-03 against the automatic trigger in [ADR-0027](0027-park-maintenance-only.md) Amendment 1 §Decision item 3. **This ADR does not take effect on merge.** It takes effect on **2026-09-30**, and only if the condition in §"Trigger condition" below still holds on that date.
* Deciders: @VitorMRodovalho
* Date: 2026-09-03 (drafted) / 2026-09-30 (effective, conditionally)
* Cites: issue #134 (Cycle 6 W2 hard gate — Pathway B criteria), [ADR-0025](0025-cycle-6-entry-h-shape.md) (Pathway B HONEST evidence bar), [ADR-0027](0027-park-maintenance-only.md) Amendment 1 (the pre-registered trigger), issues #30 / #31 / #32 (the scope this closes), issue #196 (portfolio triage)

## Context and Problem Statement

The Cost Engineer persona has been carried as "under-served, deferred" for five consecutive cycles (`memory/project_v40_cycle_6.md` §"Personas under-served entering Cycle 6", cost recorded as *Medium*). Its named falsifier in that table is explicit: *"Named in next-cycle pool with concrete demand-validation evidence OR formally retired."* No demand-validation evidence has been produced in the five cycles since.

ADR-0027 Amendment 1 pre-registered the resolution so that it could not be re-argued from the inside once the number was known: if issue #134 carries fewer than 5 conversations substantive under ADR-0025 on 2026-09-30, the Cost Engineer persona is retired via ADR and #30/#31/#32 close as `not planned`.

This ADR is that ADR, drafted ahead of the date so that the fallback executes as a ratification rather than as a fresh decision made under deadline. **Drafting it early is deliberately not the same as firing it early** — see §"Trigger condition".

## Trigger condition

This ADR is inert until **2026-09-30**. On that date, exactly one of:

* **#134 carries ≥5 substantive conversations** (conversations flagged `cosmetic` excluded, per Amendment 1 §Decision item 3) → this ADR is closed as `rejected`, Path A is met, the gate discharges on Pathway A, and #30/#31/#32 stay open.
* **Any logged conversation carries a named next action with a real counterparty** (a pilot, someone's data, a scheduled meeting) → Amendment 1 §Decision item 4 overrides: the outcome is **unpark**, this ADR is closed as `rejected`, and Cycle 7 entry is reconsidered against real signal.
* **Neither** → this ADR's status flips to `accepted` and §"Decision" executes.

As of drafting (2026-09-03) the #134 log stands at **0 of 5**. The showcase of 2026-08 happened but produced no logged conversation.

## Decision drivers

* The falsifier for this persona was named five cycles ago and has come due.
* Perpetual "deferred" status is not a neutral holding state: it keeps scope nominally alive, which keeps it in every planning pool, which costs a re-derivation every cycle and produces nothing.
* ADR-0025 was explicit that the alternative to demand evidence is *closed scope*, not softer language.

## Considered options

1. **Retire the Cost Engineer persona.** (Chosen, conditionally.)
2. **Retire a different persona** — Owner/Sponsor, Program Director, Subcontractor, Field Engineer, Consultant/Claims SME, or PMO Director.
3. **Sixth deferral.** Rejected by Amendment 1 in advance; recorded here only because refusing to list it would misrepresent the decision space.

### Why the Cost Engineer over the other six

Not because it is the least valuable — it is not. The selection is on *falsifiability*, and the other six each have a named precondition that has not been tested, so retiring them would destroy information that has not yet been gathered:

| Persona | Named falsifier | Testable now? |
|---|---|---|
| Subcontractor | Sienge/UAU API spec landed AND ≥1 contact path documented | No — spec never attempted |
| Field Engineer | Logged design-partner conversation + G702/G703 audit-spike | No — spike never run |
| Consultant/Claims SME | E1 corpus precondition (`binding_count ≥ 8`) | No — corpus never assembled |
| PMO Director | ≥3 prospects explicit ask (ADR-0022) | No — no prospect channel |
| Owner / Sponsor | Demand-validation evidence OR retire | Same bar as Cost Engineer |
| Program Director | Demand-validation evidence OR retire | Same bar as Cost Engineer |
| **Cost Engineer** | **Demand-validation evidence OR retire** | **Yes — and it is the one whose blocked scope is enumerable today** |

Three personas share the identical bar (Cost Engineer, Owner/Sponsor, Program Director). The Cost Engineer is chosen among those three on a second criterion: it is the only one whose deferred scope is already **enumerated as discrete issues** (#30, #31), so retiring it produces genuinely closed scope rather than the retirement of an abstraction. Retiring Owner/Sponsor or Program Director would close no issue and change no plan — which is the definition of the cosmetic retirement ADR-0025 warns against.

## Decision

Effective **2026-09-30**, conditional on §"Trigger condition":

1. **The Cost Engineer is removed from the active persona scope.** It is no longer carried in cycle-entry planning pools, no longer counted in "personas under-served" tables, and no longer a justification for scope in any future cycle entry.
2. **Closed scope — issues to close as `not planned`:**
   * **#30** (Wave 7-B, P2) — cost-loading curve overlay on the timeline.
   * **#31** (Wave 7-C, P2) — budget vs actual cost per activity, together with its CBS-persistence pre-work (CBS-WBS mapping schema, CBS upload flow, ADR-0014 provenance contract for cost data). That pre-work was the single largest undelivered data-model commitment in the backlog and it dies with this decision.
3. **#32 is NOT closed by this ADR.** See §"Deviation from Amendment 1" below.
4. **No feature that exists today is removed or deprecated.** This retirement closes *planned* scope only. EVM, the S-curve engines, and the existing cost analytics stay exactly as they are; they were never Cost-Engineer-specific.

## Deviation from Amendment 1

Amendment 1 §Decision item 3 directs closing "#30/#31/#32". **#32 does not belong in that set, and this ADR does not close it.**

#32 (Wave 7-D, P3 — resource-constrained critical path highlighting) names its persona as **Scheduler**, not Cost Engineer. It was grouped with #30/#31 because all three are sub-issues of #23 (Schedule Viewer Wave 7), which is a *delivery-wave* grouping, not a persona grouping. Closing #32 under a Cost Engineer retirement would be closing scope this decision has no authority over — retiring a persona is not a licence to close whatever sat next to its issues in the tracker.

This is recorded as a deviation rather than silently executed because Amendment 1's own value comes from being pre-registered, and a pre-registered instruction that is quietly edited on execution is worth nothing. **#32 stays open with its `parked` label.** If it should close, it should close on its own merits (P3, algorithmically expensive, Scheduler persona untested) in a separate decision.

## Honest assessment against the ADR-0025 Pathway B bar

ADR-0025 requires, for Pathway B to be **HONEST** rather than cosmetic:

> * ≥1 actual outreach attempt made AND received no response OR explicit disinterest (NOT retire already-implicitly-dead persona to satisfy criterion)
> * Retirement creates closed scope (specific issues to close, specific features to deprecate)
> * Cycle 7+ reactivation pre-condition named OR explicit "no reactivation path"

**Criterion 2 (closed scope): MET.** #30 and #31 are specific, and the CBS-persistence pre-work is a specific commitment being withdrawn.

**Criterion 3 (reactivation): MET.** See §"Reactivation".

**Criterion 1 (outreach attempt): NOT MET.** This must be stated plainly. The outreach this project has actually documented is **broadcast, not targeted**, and none of it was addressed to a Cost Engineer:

* **Issue #13** — "Calibration dataset contributions wanted", public since 2026-04-19, **0 comments in the 4½ months since**. This is a real documented outreach attempt that genuinely received no response — but it solicits calibration data from schedule owners, not cost input from Cost Engineers.
* **The H0 demand instrument** (`/demo` + landing page) — live since 2026-05-29, no inbound.
* **The repository itself** — public since ~2026-03, currently **0 forks, 0 watchers, 1 star**. Empirically inert, as already recorded in ADR-0026.
* **The 2026-08 tool showcase** — a real outreach event, with real attendees. No conversation from it was logged, so it supplies no evidence either way.

Not one of these was aimed at a Cost Engineer and refused. The persona is being retired **because it was never engaged**, which is precisely the condition ADR-0025 named as disqualifying.

### Criterion 1 is still open until 2026-09-30

Recorded here so that the `cosmetic` grade below is understood as **the current state, not a settled one**. Criterion 1 is the only unmet criterion, and unlike a missing conversation it does not require anyone else's cooperation to satisfy — it requires the attempt, and the attempt has never been made.

**One documented, targeted outreach to a practising cost engineer or quantity surveyor, sent early enough to leave a defensible response window, satisfies criterion 1 on either outcome:** an explicit "not my problem" is *explicit disinterest* and satisfies it immediately; silence through 2026-09-30 is *no response* and satisfies it on the date. Either flips this ADR from `cosmetic`-met to **honest-met**, and the §Consequences inheritance of the Cycle 6.5 obligations by Cycle 7 falls away with it.

The send-by date is **2026-09-08**, not 2026-09-29: "received no response" is only evidence if there was time to respond, so an attempt sent days before the deadline proves nothing and is equivalent to no attempt. The outreach material (target definition, three messages, ranked channels, and the attempt-logging schema) is prepared and lives with the Path A field kit; see `memory/reference_cost_engineer_outreach.md`.

Attempts log to **#134 on the day they are sent** — an undated attempt cannot establish when the response window opened, which is the same evidence discipline Pathway A applies to conversations.

**As of this drafting no attempt has been made, so the assessment stands as written below.** If one is made and logged before 2026-09-30, this section is what a ratifier should check first, and the grade is re-read against the outcome rather than assumed.

**Therefore, on the record as it stands today: this gate is `cosmetic`-met, not honest-met.** Per ADR-0025 §"Cycle 7 entry council will judge W2 GATE outcome on the above distinction", and per ADR-0027 Amendment 1 §Consequences, the consequence follows automatically and is not negotiable at Cycle 7 entry:

> **Cycle 7 inherits the Cycle 6.5 obligations. The discovery-only pivot still applies, delayed one cycle.**

Retiring this persona discharges the *bookkeeping* of the gate. It does not discharge the gate's purpose, and this ADR must not be cited later as though it did.

## Reactivation

Not a "no reactivation path". The pre-condition is named, and it is deliberately the outreach attempt that was never made:

**The Cost Engineer persona reactivates on ≥1 documented conversation with a practising cost engineer or quantity surveyor** — logged to ADR-0025 Pathway A standard (date, role, company type, topic, quote-grade observation, next action) — **in which cost-schedule integration is raised by them, unprompted.**

On reactivation, #30 and #31 are reopened as-is rather than re-derived; this ADR is superseded by the ADR that records the reactivation. The bar is one conversation, not five, because the burden being lifted is "we never asked", not "we asked and were told no".

## Consequences

* The remaining active persona set is six: Owner/Sponsor, Program Director, Subcontractor, Field Engineer, Consultant/Claims SME, PMO Director. Two of those six (Owner/Sponsor, Program Director) sit on the identical untested bar and are the obvious next candidates if this pattern repeats in Cycle 7.
* **#30 and #31 also served other personas** — #30 lists *PM Director*, #31 lists *Owner Rep* and *Claims*. Closing them removes scope those personas wanted too. This is a real cost of the decision, not an accounting detail: the retirement is cleaner than the issue graph it is being applied to.
* Cost-schedule integration leaves the roadmap. If it returns it returns as new scope, re-argued from scratch, with whatever the intervening evidence says.
* The `parked` state of ADR-0027 is unaffected. Executing this ADR does not unpark anything; the repository remains maintenance-only, and Cycle 7 entry remains frozen and now additionally encumbered by the inherited Cycle 6.5 obligations.
* Issue #134 closes with the gate outcome recorded as **met via Pathway B, cosmetically** — with that qualifier in the closing comment, not omitted from it.

## Open questions for ratification

1. Confirm the §"Deviation from Amendment 1" handling of **#32** (stays open) rather than the literal "#30/#31/#32" instruction.
2. Confirm the reactivation bar of **one** unprompted conversation (§"Reactivation") is the intended asymmetry against Pathway A's five.
3. Confirm that the `cosmetic` self-assessment is recorded as-is. It is unflattering by construction; softening it would reproduce exactly the sycophancy failure ADR-0025 was written to prevent.
