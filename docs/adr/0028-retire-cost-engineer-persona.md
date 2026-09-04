# 0028. Retire the Cost Engineer persona from active scope

* Status: **proposed — conditionally effective 2026-09-30, and `cosmetic`-met if it fires.** Pre-drafted 2026-09-03 against the automatic trigger in [ADR-0027](0027-park-maintenance-only.md) Amendment 1 §Decision item 3, as corrected by Amendment 2. **This ADR does not take effect on merge**, and it does not take effect on the date either: it takes effect on the *outcome commit* described in §"Trigger condition". If it fires, it discharges the Cycle 6 W2 gate **cosmetically**, and Cycle 7 inherits the Cycle 6.5 obligations enumerated in §Consequences.
* Deciders: @VitorMRodovalho
* Date: 2026-09-03 (drafted) / 2026-09-04 (revised after council) / 2026-09-30 (conditionally effective)
* Cites: issue #134 (Cycle 6 W2 hard gate — Pathway A/B/C criteria), [ADR-0025](0025-cycle-6-entry-h-shape.md) (Pathway B HONEST evidence bar), [ADR-0027](0027-park-maintenance-only.md) Amendments 1 and 2 (the pre-registered trigger and its issue-set correction), issues #30 / #31 (the scope this closes), #32 (explicitly **not** closed), #215 (explicitly **not** closed), issue #196 (portfolio triage), [ADR-0016](0016-lifecycle-phase-inference.md) / [ADR-0015](0015-async-materialization-state-machine.md) / [ADR-0009](0009-cycle1-lifecycle-intelligence.md) (shipped behaviour justified by this persona)
* Process note: the devils-advocate exit council mandated for ADR-level decisions did not run on the first draft (2026-09-03) and is recorded here rather than only in the pull-request description, which is mutable and lives outside the tree. A three-lane council (devils-advocate, product-validator, legal-and-accountability) ran on 2026-09-04 and this revision is its output; §"Prior record reconciliation", §"Authority over co-claimed scope", the corrected §"Honest assessment" grades, and the §"Trigger condition" outcome commit are all council findings.

## Context and Problem Statement

The Cost Engineer persona has been carried as "under-served, deferred" for five consecutive cycles (`memory/project_v40_cycle_6.md` §"Personas under-served entering Cycle 6", cost recorded as *Medium*). Its named falsifier in that table is explicit: *"Named in next-cycle pool with concrete demand-validation evidence OR formally retired."* No demand-validation evidence has been **logged** in the five cycles since. (Logged, not produced: ADR-0027 Amendment 1 records that a 2026-08 showcase happened and that "the signal exists only as recollection." The distinction is the one the whole gate turns on and it is preserved here deliberately.)

ADR-0027 Amendment 1 pre-registered the resolution so that it could not be re-argued from the inside once the number was known: if issue #134 carries fewer than 5 conversations substantive under ADR-0025 on 2026-09-30, the Cost Engineer persona is retired via ADR and the enumerated issues close as `not planned`.

This ADR is that ADR, drafted ahead of the date so that the fallback executes as a ratification rather than as a fresh decision made under deadline. **Drafting it early is deliberately not the same as firing it early** — see §"Trigger condition".

## Prior record reconciliation — the "Pathway D" declaration

Three artifacts in this repository already record the Cycle 6 W2 gate as resolved, under a name the governing instrument does not contain:

* `CHANGELOG.md` — *"W2 GATE outcome: Pathway D (cosmetic-met per ADR-0025 §'Honest GATE vs cosmetic GATE distinction'); Cycle 7 inherits Cycle 6.5 obligations."*
* `README.md` (roadmap table, v4.4 row) — *"W2 HARD GATE outcome (Pathway D operator-declared)"* — **without the `cosmetic-met` qualifier.**
* `CLAUDE.md` — the same sentence as the CHANGELOG.

[ADR-0025](0025-cycle-6-entry-h-shape.md) and issue #134 define **Pathway A, Pathway B and Pathway C only**. There is no Pathway D.

**What "Pathway D" was:** an operator declaration that *none* of the three pre-registered pathways had been satisfied, combined with voluntary adoption of the cosmetic-met **consequence** (Cycle 7 inherits Cycle 6.5 obligations) so that the conditional W3-W5 waves could proceed without the gate being claimed as passed. It was an honest move recorded under a dishonest label: it invented a pathway name for what was in substance "gate not met, consequence accepted anyway." The conditional W3 waves shipped under it.

**How this ADR relates to it.** This ADR does not supersede that declaration and does not retroactively authorise the W3 work; W3 shipped under the operator's acceptance of the cosmetic-met consequence, which is the same consequence this ADR carries. What this ADR does is **replace the invented label with a real pathway**: if it fires, the gate is discharged on **Pathway B, cosmetically**, and the Cycle 6.5 inheritance that "Pathway D" had already accepted is carried forward unchanged, now with an ADR behind it.

**Two corrections ship with this ADR** (see the same pull request): the `Pathway D` label is replaced in `CHANGELOG.md`, `README.md` and `CLAUDE.md` with an accurate description pointing here, and the `README.md` occurrence regains the `cosmetic-met` qualifier it lost. That qualifier detached from the claim in a single propagation step, inside this repository, on this exact sentence — which is the empirical answer to whether such a qualifier survives on its own. It does not. See §Consequences for the structural devices used instead of prose.

## Trigger condition

This ADR is inert until an **outcome commit** is made on or after **2026-09-30**. The date alone does not make it effective; nothing in a parked repository fires on a date. On that date, exactly one of:

* **#134 carries ≥5 substantive conversations** (conversations flagged `cosmetic` excluded, per Amendment 1 §Decision item 3) → the headcount condition for Pathway A is satisfied, this ADR is closed as `rejected`, and #30/#31 stay open. Whether Pathway A discharges the gate *honestly* remains the Cycle 7 entry council's judgment per ADR-0025 §"Cycle 7 entry council will judge W2 GATE outcome on the above distinction" — headcount is not discharge, and this ADR does not pre-empt that judgment.
* **Any logged conversation carries a named next action with a real counterparty** (a pilot, someone's data, a scheduled meeting) → Amendment 1 §Decision item 4 overrides: the outcome is **unpark**, this ADR is closed as `rejected`, and Cycle 7 entry is reconsidered against real signal.
* **#134 carries 1-4 substantive conversations** → this is **Pathway C** (issue #134 §"Pathway C — Mix"; partial CDs plus partial persona-retirement evidence, judged on aggregate substantive rigor). This ADR does **not** auto-accept. Pathway C is a judgment, and §"Honest assessment" below would be factually wrong on its face if it fired in this state, because it asserts the persona was never engaged in this window. Amendment 1 omitted this branch; recording it here is the last opportunity to catch the omission.
* **Neither, and no conversation logged** → this ADR's status flips to `accepted` and §"Decision" executes.

As of this revision (2026-09-04) the #134 log stands at **0 of 5**.

### The outcome commit

This repository has never once completed a manual ADR status flip. ADR-0022, ADR-0024 and **ADR-0025 itself** are all still `proposed` in both their headers and `docs/adr/README.md`, months after being ratified and executed, against this project's own convention (`docs/adr/README.md` §"Adding a new ADR" step 5: *"`accepted` after merge"*). Issue #28 tracks the 0017-0021 batch and has been open since April. A decision that hinges on that mechanism hinges on the one mechanism with a documented 0% completion rate.

Therefore the status flips on a **commit**, not on a date. One commit, on or after 2026-09-30, doing all of the following atomically:

1. Append §"Outcome" to this ADR: date evaluated, who evaluated, the observed conversation count, and the counts **transcribed** with permalinks to the #134 comments that are the evidence. Transcribed, not linked-only — #134 is a public GitHub issue whose comments the author can edit or delete, and an ADR that outsources its dispositive evidence to a mutable surface has no audit trail.
2. Flip the status line **in this file and in the `docs/adr/README.md` index row**. Two places. The index is the one that has drifted every previous time.
3. Post the #134 comment recording the outcome, retitle #134 per §Consequences, close #30/#31 as `not planned`, and open the Cycle 7 successor issue.

**Absent this outcome commit, this ADR remains `proposed`, nothing has been decided, and #30/#31 stay open.** This makes the mechanism fail *safe* (scope survives an unattended date) rather than fail *silent* (scope closed by a date nobody witnessed). It also makes the three otherwise-indistinguishable states — Path A fired / the operator declined to execute / nobody looked — distinguishable in the record.

**Timezone:** 2026-09-30 means end of day in `America/Sao_Paulo`, the operator's timezone. Stated because this ADR's own evidence rule is that an undated attempt cannot establish when a response window opened; a deadline undated to the hour has the same defect.

## Decision drivers

* The falsifier for this persona was named five cycles ago and has come due.
* Perpetual "deferred" status is not a neutral holding state — **for the persona row.** It is re-derived at every cycle entry, five times so far, verbatim. (For the *issues*, this is not true: a `parked`-labelled issue in a parked repository costs one row in a triage count and triggers no re-derivation. The recurring cost the driver names attaches to the persona, not to #30/#31. This distinction is stated because §Decision closes the issues on it, and the council found the original conflation load-bearing.)
* ADR-0025 was explicit that the alternative to demand evidence is *closed scope*, not softer language.

## Considered options

Amendment 1 pre-registered the choice: it names the Cost Engineer. Both alternatives below were therefore foreclosed before this ADR was drafted, and are recorded so that refusing to list them does not misrepresent the decision space. The table that follows is **not a fresh selection** — it is why Amendment 1's pre-registered choice was the right one, kept here because it is the reasoning Cycle 7 will need when this pattern recurs.

1. **Retire the Cost Engineer persona.** (Chosen by Amendment 1, executed conditionally here.)
2. **Retire a different persona** — Owner/Sponsor, Program Director, Subcontractor, Field Engineer, Consultant/Claims SME, or PMO Director. Foreclosed by Amendment 1.
3. **Sixth deferral.** Foreclosed by Amendment 1.

### Why the Cost Engineer over the other six

Not because it is the least valuable. The selection is on *falsifiability*, and the other six each have a named precondition that has not been tested, so retiring them would destroy information that has not yet been gathered:

| Persona | Named falsifier | Testable now? |
|---|---|---|
| Subcontractor | Sienge/UAU API spec landed AND ≥1 contact path documented | No — spec never attempted |
| Field Engineer | Logged design-partner conversation + G702/G703 audit-spike | No — spike never run |
| Consultant/Claims SME | E1 corpus precondition (`binding_count ≥ 8`) | No — corpus never assembled |
| PMO Director | ≥3 prospects explicit ask (ADR-0022) | No — no prospect channel |
| Owner / Sponsor | Demand-validation evidence OR retire | Same bar as Cost Engineer |
| Program Director | Demand-validation evidence OR retire | Same bar as Cost Engineer |
| **Cost Engineer** | **Demand-validation evidence OR retire** | **Yes — and it is the one whose blocked scope is enumerable today** |

Three personas share the identical bar (Cost Engineer, Owner/Sponsor, Program Director). The Cost Engineer is chosen among those three on a second criterion: it is the only one whose deferred scope is **enumerated as discrete issues** (#30, #31), so retiring it produces genuinely closed scope rather than the retirement of an abstraction. Retiring Owner/Sponsor or Program Director would close no issue and change no plan — which is the definition of the cosmetic retirement ADR-0025 warns against.

**Two admissions this criterion owes.** First, it rewards documentation debt: the optimal strategy for protecting a persona under this rule is to never file issues for it, and Owner/Sponsor and Program Director survive this cycle partly because they are vaguer. Second, §Consequences names those same two as the next candidates if the pattern repeats — which the criterion above disqualifies in advance. **Cycle 7 therefore inherits a selection rule with no legal move, and must replace it rather than apply it.**

**The choice is also over-determined, and the second determinant is less flattering.** The 2026-05-29 strategy verdict puts this project's only defensible moat in longitudinal portfolio intelligence, whose personas are Owner/Sponsor, Program Director and PMO Director. The Cost Engineer is the persona furthest from that moat — so it is also the cheapest to lose. A retirement that costs nothing strategically is weaker evidence of discipline than one that costs something, and this ADR does not get to claim the stronger reading.

## Decision

Effective on the outcome commit described in §"Trigger condition":

1. **The Cost Engineer is removed from the active persona scope.** It is no longer carried in cycle-entry planning pools, no longer counted in "personas under-served" tables, and no longer a justification for *new* scope in any future cycle entry. (The register itself, `memory/project_v40_cycle_6.md` §"Personas under-served", lives outside this repository and no commit here can edit it; the outcome commit's checklist includes updating it, and §Consequences records that the retirement is otherwise invisible where the persona set is actually defined.)

2. **Closed scope — issues to close as `not planned`:**
   * **#30** (Wave 7-B, P2) — cost-loading curve overlay on the timeline.
   * **#31** (Wave 7-C, P2) — budget vs actual cost per activity.

   **What actually closes, stated accurately.** The first draft of this ADR claimed #31 carried "the single largest undelivered data-model commitment in the backlog" and that it "dies with this decision." That was false, and the correction cuts against this ADR's own grade. The CBS persistence layer **shipped**: `supabase/migrations/019_erp_cost_tables.sql` creates `cbs_elements`, `cbs_wbs_mappings` (with `allocation_pct` for split allocations), `cost_snapshots`, `cost_time_phased`, `change_orders` and `obs_cbs_assignments`, all with RLS; `POST /api/v1/cost/upload` persists through `save_cost_upload`; `/cost`, `/cost/compare`, `/cost/g702`, `/evm` and `/cashflow` are live pages. The per-activity computation also exists — `src/analytics/evm.py` builds `_task_budgets` / `_task_actuals` from `target_cost` / `act_reg_cost` and computes `_compute_activity_ev(task, budget)` per activity; it is aggregated away at the API boundary, not absent.

   So what closes is **one presentation feature (#30), one Gantt-table surface (the front half of #31), and one un-started provenance extension** — materially smaller than the original claim. This is recorded because the Cycle 7 council judges the honest-versus-cosmetic distinction on this enumeration, and an overstated withdrawal would have it judging a fiction. It also means a future reactivation must not re-derive a schema that already exists.

3. **Carved out of #31 before closure, because it is a defect in shipped code rather than planned scope:** `save_cost_upload` keys cost snapshots on `project_id` only — no `input_hash`, no link to a schedule revision. A cost figure quoted in a forensic narrative therefore cannot be tied to the revision that produced it. That is a chain-of-custody gap on the **Consultant/Claims SME**'s surface, not the Cost Engineer's, and it does not die with this persona. It is re-filed as its own `parked` issue before #31 closes.

4. **#32 is NOT closed by this ADR**, and **#215 is not closed or foreclosed by it.** See §"Scope note on #32" and §"Authority over co-claimed scope".

5. **No feature that exists today is removed or deprecated — and specifically, the following survive with new justification.** This retirement closes *planned* scope only. But the persona is the justification of record for live behaviour, and a retirement with no disposition clause would orphan it:
   * **`projects.lifecycle_phase_locked`** — the override sticky-lock. Justified on Cost Engineer JTBD across [ADR-0016](0016-lifecycle-phase-inference.md) (§"Cost Engineer stickiness" and six further references), load-bearing in `src/materializer/runtime.py`, `src/materializer/backfill.py`, `src/database/store.py`, `src/api/schemas.py` and `src/api/routers/lifecycle.py`, and pinned by `tests/test_lifecycle_override_log.py` and `tests/test_lifecycle_summary_b2.py`. **It is retained on the general merit that an explicit user override beats an inference**, and the surviving seat that inherits it is the **Scheduler** (the seat that owns the schedule the phase is inferred from). The ADR-0016 citations stand as historical justification and are not invalidated.
   * **[ADR-0009](0009-cycle1-lifecycle-intelligence.md)'s production mitigation** — *"The Cost Engineer override + sticky lock remains the final answer for users who disagree."* The phase engine is defensible in production only because some seat can override it. That mitigation now reads to the Scheduler seat; it is not withdrawn.
   * **[ADR-0015](0015-async-materialization-state-machine.md)** — Cost Engineer latency expectation as a materializer design input. Historical justification, unchanged.
   * **The cost engines and surfaces** — EVM, cashflow, `cost_integration`, the AIA G702/G703 engines, the eight cost tables and five cost pages. These were never Cost-Engineer-exclusive and are untouched.
   * **`docs/user-guide/README.md`'s persona row**, pinned by `tests/test_user_guide_submission.py`. A cleanup session that finds a persona-named surface belonging to a retired persona must not delete it; that is why this list exists.

6. **`BUGS.md` item 15** ("Earned value overlay on timeline | Cost Engineer | High") is a near-duplicate of #30 and is struck in the outcome commit. Left standing, it regenerates the closed scope at the next planning pass and weakens the closed-scope criterion it is supposed to support.

## Scope note on #32 (per ADR-0027 Amendment 2)

Amendment 1 §Decision item 3 directed closing "#30/#31/#32". **#32 does not belong in that set.** #32 (Wave 7-D, P3 — resource-constrained critical path highlighting) names its persona as **Scheduler**, not Cost Engineer; it was grouped with #30/#31 because all three are sub-issues of #23 (Schedule Viewer Wave 7), which is a *delivery-wave* grouping, not a persona grouping. `BUGS.md` independently lists the same item under Scheduler.

The first draft of this ADR handled that as a **deviation recorded by the executor**. That was the wrong instrument, and the council was right to reject it: disclosure is not authority. The force of a pre-registered instruction comes from its not being editable by the executor at execution time, after the number is known; a narrowing edit is still an edit, and "recorded rather than silent" only makes it a visible one. A bad-faith executor would record a deviation too.

**The correction is therefore made where corrections belong — in the instruction.** [ADR-0027](0027-park-maintenance-only.md) **Amendment 2** (2026-09-04) corrects the issue set to #30/#31 on an **outcome-independent** ground: #32's persona membership was true and knowable on 2026-09-01, is identical under every branch of §"Trigger condition", and the correction closes *less* scope, so it cannot serve the executor's interest. This ADR now executes its instruction **exactly, with no deviation**.

This also fixes a defect the deviation form carried: if Path A fires, this ADR closes as `rejected` and the #32 correction would have died with it, leaving Amendment 1 standing on the record still instructing wrongly. Amendment 2 lives in ADR-0027 and survives every branch.

**#32 stays open with its `parked` label.** If it should close, it closes on its own merits in a separate decision.

## Authority over co-claimed scope

**A persona-retirement ADR has authority to remove the retired persona's claim on scope. It has no authority to extinguish a non-retired persona's claim on the same scope.** This is the same principle that spares #32, applied consistently — the first draft applied it to #32 and was silent about #30/#31, which was the council's central finding.

Per the issue bodies: **#30** names *Cost Engineer · PM Director*; **#31** names *Cost Engineer · Owner Rep · Claims*. Three still-active personas hold recorded claims on the scope being closed. Two of them (Owner's Rep/PMO, GC PM) are not even tracked in the seven-persona cycle-entry table, though they appear in the ten-persona roster in `memory/project_v40_planning.md` — a register drift that produced this mis-attribution and will produce the next one.

**The closure is nonetheless executed, on an explicit finding rather than by silence:** the surviving personas' claims rest on the same footing as the retired one's — no PM Director, Owner Rep or Claims demand evidence has ever been logged either. Their claims are extinguished for want of evidence, not for want of a persona. Recording it this way means a future reader can see that a judgment was made, and on what.

**Two consequences follow, and both are binding on this ADR:**

* The closed-scope credit is smaller than a flat count of two issues suggests, because neither issue was Cost-Engineer-exclusive. §"Honest assessment" grades criterion 2 **PARTIAL** accordingly, not MET.
* §"Reactivation" carries a **second, scope-keyed trigger** alongside the persona-keyed one. Without it, a PM Director asking for cost-loading curves next month would find no path to reopen #30, because the only trigger was keyed to a persona irrelevant to their request. That is a near-term, checkable failure and it is closed here.
* **#215** ("Explore: FinOps Framework structural patterns for the CBS↔WBS cost layer", open, P3, `parked`) belongs to Program Director / Owner's Rep, not to the Cost Engineer, and is **not** closed or foreclosed by this ADR. It is cross-referenced from this ADR and from the #134 closing comment so that this decision cannot later be cited against it. This matters concretely: all three copy-ready messages in the prepared outreach kit lead with #215's question.
* **#23** (the Wave 7 umbrella) stays open — it still carries #29 (P1) and #32. The outcome commit records on #23 that two of its four sub-issues closed on a Cost-Engineer retirement plus a no-evidence finding for the co-claiming personas.

## Honest assessment against the ADR-0025 Pathway B bar

The bar exists in three non-identical forms: ADR-0025's prose (3 bullets), issue #134's ratified tracking table (**4 rows** — adding "NOT already-implicitly-dead" as its own row), and #134's issue body (which also asks for an irreversibility caveat and a statement of what the retirement unblocks). **The 4-row ratified table governs**, being the form the operator actually ratified at PR #135; the first draft graded against the 3-bullet prose without noting the conflict existed.

| # | Criterion | Grade | Basis |
|---|---|---|---|
| 1 | ≥1 actual outreach attempt made AND received no response OR explicit disinterest | **NOT MET** | See below. This is the only criterion that fails. |
| 2 | Retirement creates closed scope | **PARTIAL** | Genuine (#30, the front half of #31, an un-started provenance extension) but smaller than first claimed (§Decision item 2), and neither issue was Cost-Engineer-exclusive (§"Authority over co-claimed scope"). |
| 3 | Cycle 7+ reactivation pre-condition named | **MET** | §"Reactivation", dual-keyed. |
| 4 | NOT already-implicitly-dead — persona had at least surface-level activity in prior cycles | **MET** | See below. |

**Criterion 4 is MET, and the first draft got this wrong against itself.** It asserted the persona was being retired "because it was never engaged, which is precisely the condition ADR-0025 named as disqualifying." That is false on this repository's record. By delivered surface the Cost Engineer is among the **best-served** personas in the product: the ADR-0016 override and sticky lock exist for its JTBD and are pinned by tests; the EVM S-Curve inline visualization shipped under it in v3.6.0-dev (`BUGS.md` item 9); it has a persona row in the user guide, pinned by `tests/test_user_guide_submission.py`; ADR-0015 records its latency expectation as a design input; and it is served by the EVM, cashflow, `cost_integration` and G702/G703 engines across five live pages. This is a real, under-served-on-the-backlog persona with a large shipped footprint — not a phantom added to be retired.

Being harder on itself than the evidence supports is not honesty; it is a different error with the same sign, and it hands a future reader a cheap way to discount the parts of this assessment that *are* unflattering. The correct statement is narrower and worse: **exactly one criterion fails, and one is partial.**

**Criterion 1 (outreach attempt): NOT MET.** The outreach this project has documented is **broadcast, not targeted**, and none of it was addressed to a Cost Engineer:

* **Issue #13** — "Calibration dataset contributions wanted", public since 2026-04-19, **0 comments in the 4½ months since**. A real documented outreach attempt that genuinely received no response — but it solicits calibration data from schedule owners, not cost input from Cost Engineers.
* **The H0 demand instrument** (`/demo` + landing page) — live since 2026-05-29, no inbound.
* **The repository itself** — public since ~2026-03, currently **0 forks, 0 watchers, 1 star**. Empirically inert, as already recorded in ADR-0026.
* **The 2026-08 tool showcase** — a real outreach event with real attendees. No conversation from it was logged, so it supplies no evidence either way.

Not one was aimed at a Cost Engineer and refused. The persona is being retired **because it was never asked** — which is a different and lesser defect than never having existed in the product, and it is the one that makes this `cosmetic`.

### Criterion 1 is still open until 2026-09-30

Criterion 1 is the only failing criterion, and unlike a missing conversation it does not require anyone else's cooperation to satisfy — it requires the attempt, and the attempt has never been made.

**Documented, targeted outreach to practising cost engineers, quantity surveyors or planning-and-cost controllers, sent early enough to leave a defensible response window, satisfies criterion 1 on either outcome:** explicit disinterest satisfies it immediately; silence through 2026-09-30 satisfies it on the date. The send-by date is **2026-09-08**, not 2026-09-29 — "received no response" is only evidence if there was time to respond, and an attempt sent days before the deadline is equivalent to no attempt. The outreach material lives with the Path-A field kit (`memory/reference_cost_engineer_outreach.md`); attempts log to **#134 on the day they are sent**, by role and company type only, never by name, per Amendment 1 §Decision item 2.

**Two bounds on what satisfying criterion 1 buys, both added by the council:**

1. **A single message is not a sample.** N=1 silence over 22 days is evidence about one person, not about a persona, and the prepared kit already models the compliance-minimum behaviour it warns against ("send one to be safe, send eight to have a real chance"). To be read as evidence about the persona rather than about one inbox, an attempt must reach **≥5 seats across ≥2 channels, each logged individually**. One message satisfies the letter of criterion 1; it does not satisfy its purpose, and this ADR will not pretend otherwise.
2. **Satisfying criterion 1 flips criterion 1 — not the gate's grade.** With criterion 2 PARTIAL and the closed-scope enumeration materially smaller than first claimed, curing criterion 1 does not by itself make this an honest-met Pathway B, and **this ADR cannot pre-grant itself that finding.** ADR-0025 reserves the honest-versus-cosmetic judgment to the Cycle 7 entry council. What a logged outreach campaign does is give that council something real to judge instead of a blank.

**As of this revision no attempt has been made.** If one is made and logged before 2026-09-30, this section is what a ratifier checks first, and §"Honest assessment" must be **re-derived** at the outcome commit rather than assumed — it is a dated snapshot of 2026-09-04, and it becomes operative 26 days later.

**Therefore, on the record as it stands: this gate is `cosmetic`-met, not honest-met.** Per ADR-0025 §"Cycle 7 entry council will judge W2 GATE outcome on the above distinction", and per ADR-0027 Amendment 1 §Consequences, the consequence follows automatically and is not negotiable at Cycle 7 entry. Retiring this persona discharges the *bookkeeping* of the gate. It does not discharge the gate's purpose, and this ADR must not be cited later as though it did.

## Reactivation

Not a "no reactivation path". Two independent triggers, because the scope being closed and the persona being retired are not the same object.

**Trigger 1 — persona-keyed (reactivates the persona).** ≥1 documented conversation, logged to ADR-0025 Pathway A standard (date, role, company type, topic, quote-grade observation, next action), with **someone accountable for cost outcomes on a construction project** — a cost engineer, quantity surveyor, planning-and-cost controller, or a PM who owns the cost report — in which they describe **a problem they already have** whose resolution requires joining budget or actual cost data to schedule activities.

The wording is deliberate on three points the council found self-defeating in the first draft:

* **The phrase "cost-schedule integration" is not required.** Practitioners say *"o avanço físico não bate com o financeiro"*, *"a medição não fecha com o cronograma"*, *"my S-curve doesn't match the ERP"*, *"unallocated budget"*. A filter on the term of art screens out the demand it is meant to detect.
* **The topic may be raised in response to a direct question.** The first draft required it to be raised *unprompted*, which made the reactivation trigger and the criterion-1 outreach **mutually exclusive**: every message in the prepared kit leads with #215's question, so any reply to it is prompted by construction. What "unprompted" was actually proxying for — do not lead the witness — is preserved instead by a **past-behaviour** test: the observation must be quote-grade, in past or present tense, and name a concrete artifact (a report they produce, a reconciliation they do by hand, a number that does not match). Hypothetical or future-tense enthusiasm ("that would be great") does not count.
* **"Cost engineer or QS" alone is too narrow for the operator's primary market**, where the seat is *engenheiro de planejamento e controle*. The role list above is written to the accountability, not the job title.

**Trigger 2 — scope-keyed (reopens the issues without reactivating the persona).** #30 and #31 reopen on ≥1 documented conversation meeting the same evidentiary standard with **any active persona** — the PM Director, Owner's Rep and Claims claims recorded in §"Authority over co-claimed scope" do not require the Cost Engineer to come back for their scope to return.

On either trigger, **#30 and #31 are reopened as-is rather than re-derived**, and the shipped CBS persistence layer (§Decision item 2) is not rebuilt. On Trigger 1 this ADR is superseded by the ADR recording the reactivation.

**The irreversibility caveat #134 asks for, stated plainly:** ADR-0025 §Consequences priced persona retirement as *irreversible* scope contraction. This ADR is **not** irreversible, by construction, and that is a genuine weakening of the Pathway B evidence — a decision that can be undone by one conversation closed less than the bar imagined. It is graded accordingly: criterion 2 is PARTIAL, not MET, and this is one of the reasons why. The alternative — irreversible contraction requiring a fresh ADR and re-derived scope — was rejected because re-deriving a schema that already exists is waste, and because the burden being lifted is "we never asked", not "we asked and were told no".

## Consequences

* **Cycle 7 inherits the Cycle 6.5 obligations.** Enumerated here rather than referenced, because every other place they are written is conditional ("IF the gate is met cosmetically…") and the one artifact that tracked them as a live item is closed by this decision:
  1. **Cycle 7 pivots to discovery-only** (ADR-0025 §Decision W2 branch: *"IF NOT MET → BLOCK + amend this ADR → Cycle 6.5 pivot to discovery-only"*; operator decision 5 at PR #135). No feature waves at Cycle 7 entry.
  2. **The Cycle 6.5 amendment ADR is still owed.** Operator runbook `docs/operator-runbooks/cycle6.md` §W2-OPS-04 triggers it on *"W2 GATE fails OR cosmetic-met"*. This ADR is the **Pathway B retirement ADR** (§W2-OPS-02), a different artifact with a different trigger; it does **not** discharge W2-OPS-04. Both W2-OPS-02 and W2-OPS-04 reserved slot ADR-0026, and both reservations were consumed by unrelated decisions (ADR-0026 open-core, ADR-0027 park). The Cycle 6.5 amendment ADR therefore claims **ADR-0029**; `docs/ROADMAP.md`'s dangling "ADR-0026 reserved" pointer is corrected in the same pull request as this ADR.
  3. **The Cycle 6 release tag** (v4.4.0 or v4.3.1) stays frozen per ADR-0027, unchanged by this decision.
* **#134 is NOT closed.** The first draft closed it, which would have removed the only live artifact tracking the inherited obligation at the exact moment the obligation became real. Instead the outcome commit **retitles** it to carry the qualifier in the title — where GitHub renders it on every cross-reference, hovercard and backlink — and it is re-labelled as the Cycle 7 entry blocker:
  > *"Cycle 6 W2 HARD GATE — met via Pathway B, COSMETICALLY (Cycle 7 inherits Cycle 6.5 discovery-only obligations)"*

  A qualifier attached to a closed artifact is archaeology; a qualifier that is itself a live open issue is an obligation. This is the only device in this ADR that converts the claim from something a future reader must remember to check into something they must actively close.
* **The `parked` state of ADR-0027 is unaffected.** Executing this ADR unparks nothing; the repository remains maintenance-only, and Cycle 7 entry remains frozen and now additionally encumbered.
* **The remaining active persona set is six** by the cycle-entry table's reckoning: Owner/Sponsor, Program Director, Subcontractor, Field Engineer, Consultant/Claims SME, PMO Director. Note that #134's own Pathway A field and the Cycle 6 runbook enumerate **nine** persona-pertinence values (adding GC PM and Risk Manager), and `memory/project_v40_planning.md` carries ten. "Six" is the cycle-entry table's count and must not be read as the canonical roster; reconciling the three registers is Cycle 7 work.
* **Two of the six** (Owner/Sponsor, Program Director) sit on the identical untested bar and are the obvious next candidates if this pattern repeats — but see §"Considered options": the selection rule that picked the Cost Engineer disqualifies both, so Cycle 7 must replace the rule rather than apply it.
* **The cost lane keeps shipping without an accountable seat.** Five cost surfaces stay live citing AACE RP 10S-90 and the PMI EVM practice standard, and `cost_integration.py` will continue to claim CBS/WBS conformance, with no persona accountable for verifying cost-data quality. AACE TCM 7.2 — cited by #30's own acceptance criteria, and the tracker's only TCM 7.2 anchor — leaves the roadmap with it. ISO 21502 §7.6 expects cost and schedule controlled as an integrated system *with defined roles*; retiring the role while keeping the function is precisely the unowned control that standard flags. This is a real cost of the decision, recorded rather than minimised.
* **The retirement is invisible where the persona set is actually defined.** `memory/project_v40_cycle_6.md` §"Personas under-served" lives outside this repository; no commit here can edit it. The outcome commit's checklist includes it, and this is noted so a future session does not mistake the memory file's stale row for a live claim.

## Open questions for ratification

1. Confirm **ADR-0027 Amendment 2** (correcting Amendment 1's issue set to #30/#31) as the instrument for the #32 correction, in place of the executor-recorded deviation the first draft used.
2. Confirm the **reactivation design**: the bar of one conversation (unchanged), with the past-behaviour wording replacing "unprompted", and the addition of the scope-keyed Trigger 2 for #30/#31.
3. Confirm the `cosmetic` self-assessment **as corrected** — one criterion failing rather than the two the first draft implied, criterion 2 downgraded to PARTIAL, and the closed-scope enumeration reduced to what is actually undelivered. The corrections cut in both directions and the net grade is unchanged.
4. Confirm the **outcome-commit mechanism** (§"Trigger condition") as the thing that makes this ADR effective, in place of a date, and the decision **not to close #134**.
