# 0021. Cycle 3 entry — Floor + Field-surface shallow (Option α)

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-27
* Cites template: [ADR-0019](0019-cycle-2-entry-consolidation-primitive.md) §"Reversibility" + §"Scope of what this ADR does NOT do" (the gating language for the two pre-committed Cycle 3 deep candidates) and the 4-agent council protocol established in Cycle 2 (recorded in `project_v40_cycle_2.md` §"Roles + councils for Cycle 2"; the protocol itself is not yet in-repo — see §"Open process gap" below)
* Cites primitive: [ADR-0020](0020-calibration-harness-primitive.md) (the harness that opened the candidate-deep gates ADR-0019 §"Reversibility" pre-committed)

## Context and Problem Statement

Cycle 2 closed at `v4.1.0` (commit `aae1bb1`, 2026-04-26) as Option 4
"Consolidation + Primitive" per ADR-0019. The post-tag close-arc
(2026-04-27) shipped three additional PRs (#33 Cycle 2 close docs,
#35 D4 backend wiring un-dormants the WS recovery poller, #36
`engine_version` source-of-truth dedup) under the
devils-advocate-as-second-reviewer protocol, and PR #37 appended five
close-arc lessons to `docs/LESSONS_LEARNED.md`. Cycle 3 opens against
this state.

ADR-0019 §"Reversibility" pre-committed two candidate deeps gated on
the calibration harness landing first — A1+A2 (auto-grouping +
baseline inference) and E1 (multi-discipline forensic methodology) —
and §"Scope of what this ADR does NOT do" explicitly deferred Cycle 3
deep selection to "the W3 calibration harness outputs as evidence
input." The harness shipped in Cycle 2 W3 (`tools/calibration_harness.py`,
ADR-0020). Both candidate-deep gates are formally open. The
maintainer can also choose Schedule Viewer Wave 7 (#23 sub-issues
#29-#32), Option 4 redux (no deep), or any hybrid.

This ADR records the Cycle 3 council round (4 agents over 2 rounds —
PV + strategist parallel in round 1, devils-advocate + investor-view
paired adversarially in round 2 per the protocol established in
Cycle 2 and documented in memory `project_v40_cycle_2.md` §"Roles +
councils for Cycle 2"), the synthesis that rejected both
pre-committed candidates plus the strategist-proposed hybrid, and the
chairman recommendation the maintainer accepted: **Option α — floor
work + a single Field-surface shallow at W5**.

## Decision Drivers

1. **Operator-block work is contractual cycle-gate, not parallel
   hygiene.** ADR-0018 §5 makes the audit re-run "cycle-close
   mandatory"; the previous cycle slipped it. ROADMAP §"Operator
   actions" tracks `#26` prod migration apply, `#28` ADR
   ratifications, and the W4 manifest archive as additional owed
   items. Round 1 councils sized the block at 0.5-1 wave; the round 2
   devils-advocate adversarial review verified this was 4-12×
   underestimated — honest budget is **4-6 wave-equivalents** once
   backup procedures, audit finding triage, and the W4 reproduction
   regression test are factored in. This block alone is most of the
   solo-maintainer Cycle 3 ceiling (6-8 waves observed in Cycle 1+2).

2. **A2 baseline inference is not separable from A1 grouping in this
   codebase.** Verified at `src/database/store.py:252-260` —
   `save_project` auto-creates programs from `proj_short_name`
   exact-match; there is no baseline modeling primitive at all.
   Strategist's hybrid Option E (ship A2 alone) collapses to "build
   baseline modeling on the artificially-narrow exact-name grouping",
   which doesn't unlock A1's promised typo-tolerance and re-introduces
   the A2-baseline-corruption failure mode ADR-0019 §"Option 1" #3
   already rejected.

3. **PV's "consultant's MIP 3.7 chronology objection wired as
   contract" is structurally unenforceable in one wave.** Round 2 DA
   verified the honest contract requires a state-machine constraint
   on the persistence layer (append-only baseline assignments + audit
   trail) — that's a migration + RLS policy + endpoint contract, not
   a wave-1 deliverable. Without it, the constraint degrades to a
   `Field(description=…)` marker (the W2 B2 pattern) — non-load-bearing,
   exactly the engine_version-style ADR drift documented in
   `docs/LESSONS_LEARNED.md` lines 187-198.

4. **E1 calibration corpus does not exist for forensic
   delay-attribution.** Forensic methodology calibration needs labeled
   gold-standard fixtures (ground-truth attribution outcomes from real
   arbitration records or expert reports), not just XER inputs. Round 2
   IV explicitly confronted its own ADR-0019 §"Option 3" caveat
   ("thinnest-but-real moat") as relative-not-absolute, and now
   underweighted: the harness ships the apparatus but
   ADR-0020 §"Decision" carries the explicit caveat that the demo
   does not reproduce W4 outcome numbers authoritatively. The 103-XER
   sandbox is private/CONFIDENTIAL per the maintainer's reference
   memory; LGPD/GDPR anonymization per ADR-0020 §"Engine-author
   contract" item 4 is unaddressed for E1's corpus shape (not the
   same shape as the lifecycle_phase fixtures).

5. **Workflow-data-gravity moat is fork-portable for MIT
   open-source.** Strategist round 1 surfaced this as a structural
   moat concern PV's persona-coverage framing missed. Round 2 IV
   concurred and sharpened: A1+A2 is "good product work, not moat
   work" because acquirer-relevant moat in this category requires
   either (a) hosted SaaS where data lives in the vendor's DB, (b)
   network effects between counterparties, (c) accumulated
   user-specific configuration. MeridianIQ MIT-licensed has none.

6. **Maintainer-as-moat single-key risk crosses ALL options.** Round 2
   IV named this as the load-bearing strategic finding — every option
   is implicitly priced on the solo maintainer shipping 3-4 more
   cycles. None of the candidate scopes buys down the single-key risk.
   Honest acknowledgement: Cycle 3 cannot make MeridianIQ
   acquirer-relevant by itself. The right framing is "Cycle 3 = floor
   + Cycle 4 setup", not "Cycle 3 = pretend to do moat work".

7. **Field Engineer + Subcontractor under-service is now 2 cycles
   deep and accelerating.** Round 1 PV flagged this as "structural
   in 12 months." Cycle 2 explicitly accepted it as a deferred
   negative. A 3rd cycle of total absence on field surface forecloses
   the largest pricing tier in construction software. A 1-2 wave
   shallow at W5 addresses **the Field Engineer surface specifically**
   (responsive Gantt OR 3-week look-ahead OR offline cache —
   Field-Engineer-primary JTBDs); the **Subcontractor surface**
   (AIA G702/G703 generation, sub workflow handoffs) is explicitly
   accepted as continuing under-service with a Cycle 5+ commitment
   per §"Considered Options" Option 6 deferral. Decision Driver 7
   addresses the bundle's Field-Engineer half, not both halves.

8. **Solo-maintainer reversibility maximum.** Cycle 1 was 7 waves at
   1.5× scope ratio; Cycle 2 was 4 planned + ~4.5 actual + 4
   close-arc PRs. The Option-4-style "no must-ship bundle, each wave
   independently valuable" pattern that worked Cycle 2 is the right
   shape for Cycle 3 too. Burnout-risk profile favors graceful
   per-wave landing over a deep-bet cycle.

## Considered Options

### Option 1 — A1+A2 deep (PV round 1 primary)

Auto-grouping + baseline inference deep, 5-6 wave budget per PV's
revised round 1 estimate (originally 5-5.5 in ADR-0019 §"Option 1",
honest budget 7-7.5 per the ADR). **Rejected.** Round 2
devils-advocate replayed all 5 ADR-0019 §"Option 1" rejection
rationales and verified two new findings:

1. The merge-cascade migration is 8-10 tables (DA enumerated at
   `src/database/store.py` lines 80-105), not 6+ as PV framed; the
   `ON DELETE CASCADE` on `schedule_derived_artifacts` (ADR-0014)
   means a wrong merge propagates artifact deletion silently. Rollback
   for "user undoes the merge" is undefined.
2. PV's "buffer-wave deliverable if calibration fails" (Owner-rep
   program list view + manual revision tagging) is **already shipped**
   at `store.py:137-206` and the existing compare picker. The buffer
   delivers nothing not already at v3.x.

Plus the calibration corpus for grouping/baseline doesn't exist —
ADR-0020 §"Engine-author contract" item 4 anonymization-or-sandbox
requirement is unmet for the 103-XER sandbox in any A1/A2 calibration
shape.

**Deferred to Cycle 5+** with explicit gates: (a) merge-cascade
migration scoped + ADR; (b) labeled corpus for grouping
(programs-known-to-be-same and programs-known-to-be-different across
typos / version suffixes); (c) labeled corpus for baseline (ground-truth
"this revision is the baseline-of-record at this data date"
chronology). All three gates are corpus-build work that Cycle 3 does
not attempt.

### Option 2 — E1 deep (strategist round 1 conditional; IV round 2 conditional)

Multi-discipline forensic methodology, 8-10 wave budget. **Rejected
for Cycle 3 under most likely conditions.** Round 2 IV confronted its
own ADR-0019 §"Option 3" caveat and underweighted two preconditions:

1. The W4 manifest archive is still pending operator action; the
   harness reproduces shape, not numbers (ADR-0020 §"Decision"
   caveat). Running E1 through the harness on synthetic-only fixtures
   reproduces the same W3-demo-trivially-failed gate.
2. Forensic delay-attribution gold-standard fixtures do not exist in
   solo-maintainer scope. Procuring them requires expert-witness or
   anonymized arbitration records — neither cheap.

Plus litigation-risky surface ships without legal-on-payroll
(ADR-0019 §"Option 3" #2 still in force).

**Deferred to Cycle 4 with corpus-precondition gate** — once the W4
reproduction regression test passes (Cycle 3 W3 deliverable) AND a
labeled forensic gold-standard corpus is procurable, E1 reactivates
as the strongest deep candidate. The IV-recommended "ship outcome
record whether pass-or-fail" discipline (W4 path-A precedent) applies.

### Option 3 — Schedule Viewer Wave 7 deep

Cost-loading + EVM overlay + BVA + RCCP across #29-#32. **Rejected as
cycle commitment.** Round 1 strategist + round 2 IV converged: feature
category, no compounding mechanism, every quarter Smartsheet /
Procore-acquired-properties / GPT-wrapper-startups ship Gantt UX
improvements. DA additionally noted: cost-loading without CBS ingest
is theatre; with CBS ingest is its own cycle. Best as a SHALLOW
inside another cycle.

### Option 4 — Hybrid (strategist round 1 primary)

A2 baseline inference + plugin-sandbox ADR/prototype + audit re-run.
**Rejected.** Round 2 verified A2 is not separable from A1 in this
codebase (Decision Driver 2 above). Strategist's hybrid collapses to a
worse Option 1 (A1+A2 problems on a smaller, less-justifiable scope).
Plugin sandbox prototype is wave-by-itself (DA: 1-1.5 waves credible,
less is "we tried"). Hedging across thin bets is dominated by a
focused bet.

### Option 5 — Floor Only (DA round 2 primary; IV round 2 fallback) — selected as Option α

No deep. Five-wave plan addressing the contractual operator-block work
ADR-0018 §5 + ROADMAP §"Operator actions" track. Plus optional W5
single shallow.

**Selected with W5 = Field Engineer mobile look-ahead spike.**
Rationale per Decision Drivers 1, 6, 7, 8 above plus the chairman
recommendation: addresses the 2-cycle-deep persona under-service at
~1-2 wave cost without drifting into a moat-claim it can't defend.

### Option 6 — Field-surface Pivot

Mobile + look-ahead + offline + AIA G702/G703 generation as the
PRIMARY deliverable, compressing the operator-block floor by deferring
W4 manifest archive + reproduction test. **Rejected.** Deferring W4
archive + reproduction test by another cycle compounds the
silent-slip pattern DA flagged (engine_version drift, W4 manifest
deferral, audit re-run slip). Cycle 3's job is to close those, not
defer them again. Field surface ships as W5 shallow inside Option 5
instead.

## Decision

**Cycle 3 enters as Option α — Floor + Field-surface shallow.** Plan:
**5 mandatory waves + 1 optional (W5)**, no deep, with a graceful
per-wave landing pattern matching Cycle 2. Each wave independently
valuable; cycle ships a tagged release at whatever state lands at the
buffer point.

### Wave plan

**W0 — Cycle 3 entry + audit re-run kickoff**

- This ADR (ADR-0021) committed at W0.
- `docs/ROADMAP.md` refreshed with Cycle 3 plan (per LESSONS_LEARNED
  Cycle 2 §"What we would do differently" — ROADMAP at kickoff, not
  close).
- ADR-0022 + ADR-0023 numbers reserved for Cycle 4 deeps (matching
  the ADR-0010 / ADR-0011 reservation pattern: noted here, no stub
  files, ROADMAP "Engineering reservations" section tracks).
- 2026-04-26 audit re-run authored as `docs/audit/2026-04-26/`
  following the 6-layer structure of the 2026-04-22 baseline. Findings
  become GitHub issues with the `audit-2026-04-26` label.

W0 budget: ~1-1.5 waves (entry docs + audit run + finding triage).

**W0 fallback if audit re-run slips past W0 close:** ADR-0018
amendment authored at the slip moment — NOT at cycle close — honestly
disclosing the slip + committing to a new date (W3.5 contingency wave
or Cycle 3.5 patch). Pre-committing the slip-handling protocol here
prevents the next devils-advocate review from finding a fresh
honesty-debt accumulation; the "scheduled — Cycle 3 W0" wording in
ROADMAP §"Cadence" is a date-pegged contract, not an open obligation,
and this clause is its escape hatch.

**W1 — `#26` prod migration apply**

- Apply migration `026_api_keys_schema_align.sql` to production
  Supabase per `docs/audit/HANDOFF.md §H-01` (backup, apply, sample-row
  inspection, RLS policy verification, audit-log entry).
- Operator action; Claude prepares runbook.

W1 budget: ~0.5-1 wave (operator-paced).

**W2 — `#28` ADR ratifications + W4 manifest archive**

- Re-read ADR-0017 (api_keys dedup), ADR-0018 (cycle cadence),
  ADR-0019 (Cycle 2 entry), ADR-0020 (calibration harness primitive).
  Record ratifications via issue #28 closure.
- W4 manifest archive: move `/tmp/w4_*.json` artifacts to
  `meridianiq-private/calibration/cycle1-w4/` with content-hash
  verification. **Pre-W2 verification step**: as of 2026-04-27 ADR
  authoring time, `ls /tmp/w4_*.json` confirms the manifest +
  private + public payloads still exist (Apr 19 02:55, 8 days old,
  pre-`tmpfiles.d` rotation window). **If verification fails before
  W2 starts** (host reboot / `/tmp` rotation between ADR commit and
  W2 wave start), W2 must be re-budgeted to ~1.5-2 waves with the
  re-run W4 protocol as named W2.5 contingency wave — NOT a
  parenthetical clause. The re-run is itself one wave + a fresh
  `0009-w4-outcome.md` reauthorship cycle.

W2 budget: ~0.5-1 wave + operator coordination IF verification holds;
~1.5-2 waves IF re-run is needed. The contingency is a budget
expansion, not a hidden cost.

**W3 — W4 reproduction regression test**

- `tests/test_w4_reproduction.py` — pin equivalence between
  `scripts/calibration/run_w4_calibration.py` and
  `tools/calibration_harness.py` on the same input. Asserts
  byte-identical aggregate numbers for the W4 outcome.
- **This is the gate that unblocks every future calibration-dependent
  deep** (A1, A2, E1, ruleset v2). Without it, ADR-0020 §"Decision"
  caveat ("pipeline runs but doesn't reproduce numbers") stays
  load-bearing forever.

W3 budget: 1 wave.

**W4 — `_ENGINE_VERSION` → `__about__.py` per ADR-0014**

- Create `src/__about__.py` (or read via `importlib.metadata`).
- Point `src/materializer/runtime.py:54` at it.
- Migration-safe: existing `"4.0"` artifacts auto-stale +
  re-materialize on next access; or maintainer flips status='pending'
  on the 88 prod rows for a controlled re-materialize.
- Closes the multi-cycle ADR-0014 divergence documented in
  LESSONS_LEARNED Cycle 2 §"The ADR-0014 implementation has been
  diverged for multiple cycles".

W4 budget: 1 wave (code) + operator coordination on re-materialize
event.

**W5 (optional) — Field Engineer mobile look-ahead spike**

- Pick one of: (a) responsive Schedule Viewer pass (mobile-friendly
  Gantt + touch interactions in `web/src/lib/components/ScheduleViewer/`),
  (b) 3-week look-ahead view (Field Engineer JTBD, derived from
  existing Gantt data), (c) lighter offline cache for already-loaded
  schedules.
- Address the 2-cycle-deep Field Engineer + Subcontractor
  under-service (PV round 1 flag).
- Honest framing: this is a SPIKE, not a full Field-surface deep.
  The full surface (offline + AIA G702/G703 generation + sub
  workflows) is a Cycle 5+ deep candidate.

W5 budget: 1-2 waves.

### Total Cycle 3 budget

**Plan: 5 mandatory waves + 1 optional (W5).** With the observed 1.5×
scope ratio, **~7-9 waves realistic** including operator coordination
overhead and post-tag close-arc PRs (Cycle 2 close-arc was 4 PRs over
1 day per LESSONS_LEARNED 2026-04-27 entry).

**Buffer + tag-target SemVer rationale:**

- If W0-W5 all ship: tag **v4.2.0** — minor bump justified by the new
  Field-surface route (W5 sub-pick (b) 3-week look-ahead view) OR new
  responsive Schedule Viewer mode (W5 sub-pick (a)) OR new offline
  cache surface (W5 sub-pick (c)) — all three sub-picks add
  user-visible additive surface.
- If W5 drops and cycle ships at W4 close: tag **v4.1.1** — patch
  bump is the honest SemVer label for a consolidation-only cycle
  (audit re-run is docs; #26 prod migration is ops; W3 regression
  test is internal CI; W4 `_ENGINE_VERSION` migration is bug-fix-class
  per ADR-0014 divergence). Pre-asserting v4.2.0 for a docs+bug-fix
  cycle would be a wrong external SemVer signal.
- The Field-surface W5 shallow can re-slot into any Cycle 3.5 patch
  or Cycle 4 W0 with v4.2.0 tagged then. The cycle has no must-ship
  bundle.

### Round 2 devils-advocate preconditions adopted

Round 2 DA's adversarial review (2026-04-27, dispatched against the
chairman synthesis) named 5 non-negotiable preconditions before any
Cycle 3 deep should open. Cycle 3 enters as Option α specifically
*because* a deep was rejected, but the floor work itself must satisfy
these to avoid replaying the engine_version-style multi-cycle drift.
Mapped to wave / success-criterion adoption:

| # | DA precondition | Cycle 3 wave | Success criterion |
|---|-----------------|--------------|-------------------|
| DA-1 | 2026-04-26 audit re-run completed and triaged, OR ADR-0018 amendment authored honestly disclosing the slip | W0 | #1 |
| DA-2 | W4 manifest archived AND `tests/test_w4_reproduction.py` in CI green (proves harness reproduces W4 outcome byte-identically) | W2 (archive) + W3 (test) | #4 + #5 |
| DA-3 | `#26` prod migration applied + post-apply verification (audit count, sample row inspection, RLS verification) | W1 | #2 |
| DA-4 | ADR-0021 (Cycle 3 entry strategic decision) authored BEFORE Cycle 3 W0 — citing this round's adversarial output and PV's revised position | W0 | #8 (this ADR) |
| DA-5 | Pre-allocated ADR-0022 + ADR-0023 — prevents collision with audit-spawned ADRs (the ADR-0019 §"Numbering note" lesson) | W0 | tracked in `docs/adr/README.md` index + ROADMAP §"Engineering reservations" |

All 5 are explicitly adopted as Cycle 3 floor work. Rephrasing
the success criteria in §"Pre-registered success criteria" below to
DA-1 through DA-5 enumeration would close the audit-transparency gap
DA's process meta-finding flagged; for now the cross-reference table
above is the primary record.

### Pre-registered success criteria

Cycle 3 ships successfully if at close:

1. **Audit re-run published** as `docs/audit/2026-04-26/` following
   the 6-layer structure of the 2026-04-22 baseline. Findings become
   GitHub issues with the `audit-2026-04-26` label. (W0)
2. **Migration `026_api_keys_schema_align.sql` applied in production**
   with verification audit-log entry. Diagnostic + backup + apply per
   `docs/audit/HANDOFF.md §H-01`. (W1)
3. **ADR-0017/0018/0019/0020 ratified** per #28 (re-read + recorded
   ratification). (W2)
4. **W4 manifest archived** in
   `meridianiq-private/calibration/cycle1-w4/` with content-hash
   verification. (W2)
5. **`tests/test_w4_reproduction.py` in CI green** — proves the
   harness reproduces the W4 outcome byte-identically. **This closes
   the ADR-0020 §"Decision" caveat outstanding since 2026-04-26 (the
   harness ships pipeline-shape but does NOT reproduce W4 numbers
   authoritatively until the regression test passes).** It is *a*
   load-bearing primitive of the cycle, not *the* one — Decision
   Driver 1 establishes that the multi-wave operator block is the
   actual cycle centre. (W3)
6. **`src/__about__.py::__version__` exists; `_ENGINE_VERSION` sourced
   from it; existing prod artifacts re-materialized OR explicitly
   marked-stale**. Closes the ADR-0014 multi-cycle divergence. (W4)
7. **Field Engineer mobile look-ahead surface ships** at user-visible
   quality (per W5 sub-pick: responsive Gantt OR 3-week look-ahead OR
   offline cache). Measurable by Lighthouse mobile score for the
   surface OR by user-acceptance smoke test. (W5; OPTIONAL — cycle
   passes without it if W0-W4 close)
8. **ADR-0021 + ADR-0024 (audit-spawned, if any P0/P1 finding warrants
   one) committed** with cross-link to ADR-0019 §"Reversibility" +
   §"Scope of what this ADR does NOT do" + the 2026-04-27 council
   round adversarial output (this ADR §"Considered Options" + the
   memory `project_v40_cycle_3.md` for the round-by-round detail).
9. **v4.2.0 tagged + GitHub release + CI green.**

Cycle 3 fails *gracefully* if ≥5 of the 9 criteria close and the rest
are cleanly documented for Cycle 3.5 or Cycle 4.

## Consequences

**Positive**

- Closes 4 contractual debts (audit re-run, prod migration, ADR
  ratifications, W4 archive) that have been compounding under the
  silent-slip pattern documented in Cycle 2 close-arc lessons (PR #37).
- Ships the W4 reproduction regression test — the load-bearing
  primitive that unblocks every future calibration-dependent deep
  (A1, A2, E1, ruleset v2). Without this, ADR-0020 §"Decision" caveat
  stays load-bearing forever and Cycle 4's deep inherits Cycle 1's W4
  uncertainty.
- Closes the multi-cycle ADR-0014 `engine_version` divergence that PR
  #36 surfaced and PR #37 lessons-appended.
- Addresses the 2-cycle-deep Field Engineer + Subcontractor
  under-service at the lowest credible cost (W5 spike), without
  drifting into an unfalsifiable persona-coverage moat-claim.
- Maintains Cycle 2's reversibility-maximum + solo-maintainer-fit
  pattern. No must-ship bundle; graceful failure mode pre-registered.
- Honors the Cycle 2 lesson "ROADMAP at kickoff, not close" — Cycle 3
  ROADMAP refreshed in W0 not W close.

**Negative / accepted costs**

- Three consolidation-flavoured cycles in a row (Cycle 1 was feature,
  Cycle 2 was Option 4, Cycle 3 is Option α). Round 2 IV explicitly
  flagged this as "velocity problem signal" to acquirer-class
  observers. Mitigation: ADR-0021 frames Cycle 4 candidate deeps as
  the calibration-gated A2 (corpus-conditional) AND E1
  (corpus-conditional) on the verified harness + corpus preconditions;
  selection happens at Cycle 4 W0 with its own council round, NOT
  pre-committed here. The cycle's external story is "shipping the
  apparatus + corpus + verification so the next moat play can't
  repeat W4 publicly". (Reconciles with §"Reversibility" framing
  below — Cycle 4 is candidate-shaped, not committed to a specific
  deep.)
- A1+A2 personas (Owner / Program Director / Cost Engineer) stay
  under-served for one more cycle. The Field-surface W5 partially
  addresses Cost Engineer if the W5 sub-pick is responsive Gantt;
  Owner + Program Director stay deferred.
- Subcontractor persona stays under-served (W5 addresses Field
  Engineer primarily). The Sub workflow + AIA G702/G703 generation
  surface is Cycle 5+.
- The audit re-run is reputation-exposing if it surfaces P0/P1
  findings on a tag that just shipped (`v4.1.0` 2026-04-26 → audit
  2026-04-26 → maintainer's own audit on own tag). Already accepted —
  the alternative (silently slipping the audit twice) is worse per
  ADR-0018 §5 cadence-broken-pattern reasoning.
- E1 (the only option round 2 IV flagged as moat-relevant) defers to
  Cycle 4 with the corpus-precondition gate. Costs ~1 quarter of
  moat-building. Accepted because the alternative (shipping E1 on
  synthetic-only fixtures) replays W4 publicly at higher reputational
  stakes.

**Reversibility**

- Maximum. No commitments to a specific Cycle 4 deep beyond stating
  E1 (corpus-conditional) AND A1+A2 (corpus-conditional) are the two
  candidate deeps for Cycle 4. ADR-0022 + ADR-0023 are reserved for
  whichever is selected. If Cycle 3 evidence (audit findings, corpus
  procurement progress, contributor signal on issue #13) reframes the
  strategic question, Cycle 4 chooses freely.

### Open process gap

The 4-agent council protocol (PV + strategist round 1 parallel;
devils-advocate + investor-view round 2 paired adversarially per
the documented sycophancy-counter pairing) is only documented in
maintainer memory `project_v40_cycle_2.md` §"Roles + councils for
Cycle 2" — not in any in-repo ADR or process doc. ADR-0019 followed
the same protocol but did not codify it; ADR-0021 follows the same
protocol but does not codify it either. **Future contributors
reading ADR-0021 cannot verify the "chairman synthesis was faithful
to the round outputs" claim without access to the maintainer's
memory directory.** This is the same opacity trade-off ADR-0019 made
silently. Addressing it would require either (a) a separate ADR
codifying the council protocol as part of the cycle-cadence cadence
(extending ADR-0018), or (b) committing the council outputs of each
cycle into `docs/adr/cycles/cycle-N/` as audit-grade record. Neither
is in Cycle 3 scope; flagged here as a known structural gap that a
future cycle should close.

## Scope of what this ADR does NOT do

- Does not assign a Cycle 4 deep. That decision waits for the W3
  reproduction regression test outcome + corpus procurement evidence
  + Cycle 3 audit findings.
- Does not commit to specific W5 Field-surface sub-pick (responsive
  Gantt vs 3-week look-ahead vs offline cache). Decision deferred to
  W4 close based on remaining capacity and the audit findings.
- Does not author ADR-0022 or ADR-0023. Those numbers are reserved
  for the Cycle 4 deeps; the actual ADRs land at Cycle 4 W0 with the
  specific scope.
- Does not commit to the dual-license trigger ADR (strategist round 1
  open question). That ADR can ship in Cycle 4 W0 alongside the deep
  decision OR independently in any cycle once T1/T2/T3 evidence
  accumulates.
- Does not commit to a plugin-sandbox ADR (strategist Option E
  component). Round 2 IV + DA verified the sandbox is wave-by-itself
  if shipped credibly; deferred until the marketplace decision (E3)
  reactivates per ADR-0019 §"Option 2" gates (none of which is
  satisfied).

## Related

- [ADR-0019](0019-cycle-2-entry-consolidation-primitive.md)
  §"Reversibility" + §"Scope of what this ADR does NOT do" — the
  gating language for the two pre-committed Cycle 3 candidate deeps
  (E1 + A1+A2). The 4-agent council protocol is documented in memory
  `project_v40_cycle_2.md` §"Roles + councils for Cycle 2"; ADR-0021
  honors the same protocol but does not codify it in-repo (open
  process gap — see §"Open process gap" below).
- [ADR-0020](0020-calibration-harness-primitive.md) — the harness
  primitive that opened the candidate-deep gates ADR-0019
  §"Reversibility" pre-committed; W3 reproduction regression test
  in this cycle finishes ADR-0020's work by closing its §"Decision"
  caveat.
- [ADR-0018](0018-cycle-cadence-doc-artifacts.md) §5 — audit re-run
  cycle-close mandate; W0 honors it.
- [ADR-0017](0017-deduplicate-api-keys-migration.md) — migration #26
  W1 applies to prod.
- [ADR-0014](0014-derived-artifact-provenance-hash.md) §"engine_version"
  — multi-cycle divergence that W4 closes.
- [ADR-0009 + Amendments 1, 2](0009-cycle1-lifecycle-intelligence.md)
  + [`0009-w4-outcome.md`](0009-w4-outcome.md) — the W4 calibration
  protocol that the W3 reproduction regression test pins.
- [`docs/LESSONS_LEARNED.md`](../LESSONS_LEARNED.md) Cycle 2 entry —
  in particular the post-tag close-arc lessons (2026-04-27 §) that
  motivated the 5 non-negotiable preconditions adopted as the cycle
  floor.
- `project_v40_cycle_3.md` (memory) — operating record of this
  ADR's selection plus the 4 council outputs from the 2026-04-27
  discovery round.
