# 0021. Cycle 3 entry — Floor + Field-surface shallow (Option α)

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-27
* Cites template: [ADR-0019](0019-cycle-2-entry-consolidation-primitive.md) §"Process" (council protocol) and §"Cycle 3 status" (pre-committed candidates)
* Cites primitive: [ADR-0020](0020-calibration-harness-primitive.md) (the harness that opened the §"Cycle 3 status" gates)

## Context and Problem Statement

Cycle 2 closed at `v4.1.0` (commit `aae1bb1`, 2026-04-26) as Option 4
"Consolidation + Primitive" per ADR-0019. The post-tag close-arc
(2026-04-27) shipped three additional PRs (#33 Cycle 2 close docs,
#35 D4 backend wiring un-dormants the WS recovery poller, #36
`engine_version` source-of-truth dedup) under the
devils-advocate-as-second-reviewer protocol, and PR #37 appended five
close-arc lessons to `docs/LESSONS_LEARNED.md`. Cycle 3 opens against
this state.

ADR-0019 §"Cycle 3 status" pre-committed two candidate deeps gated on
the calibration harness landing first — A1+A2 (auto-grouping +
baseline inference) and E1 (multi-discipline forensic methodology).
The harness shipped in Cycle 2 W3 (`tools/calibration_harness.py`,
ADR-0020). Both gates are formally open. The maintainer can also
choose Schedule Viewer Wave 7 (#23 sub-issues #29-#32), Option 4
redux (no deep), or any hybrid.

This ADR records the Cycle 3 council round (4 agents over 2 rounds
per ADR-0019 §"Process"), the synthesis that rejected both
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
   shallow at W5 addresses it without overclaiming.

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
5+1 waves, no deep, with a graceful per-wave landing pattern matching
Cycle 2. Each wave independently valuable; cycle ships a tagged
release at whatever state lands at the buffer point.

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
- W4 manifest archive: move `/tmp/w4_*.json` artifacts (if extant) to
  `meridianiq-private/calibration/cycle1-w4/` with content-hash
  verification. **If `/tmp` was rotated and the manifest is gone**:
  re-run W4 protocol against the harness as the archive material, then
  archive.

W2 budget: ~0.5-1 wave + operator coordination.

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

**Plan: 5-6 waves.** With the observed 1.5× scope ratio,
**~7-9 waves realistic** including operator coordination overhead and
post-tag close-arc PRs (Cycle 2 close-arc was 4 PRs over 1 day per
LESSONS_LEARNED 2026-04-27 entry).

**Buffer:** if W5 cannot fit, the cycle ships v4.2.0 at W4 close. The
Field-surface shallow can re-slot into any Cycle 3.5 patch or Cycle 4
W0. The cycle has no must-ship bundle.

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
   harness reproduces the W4 outcome byte-identically. **This is the
   load-bearing primitive of the cycle.** (W3)
6. **`src/__about__.py::__version__` exists; `_ENGINE_VERSION` sourced
   from it; existing prod artifacts re-materialized OR explicitly
   marked-stale**. Closes the ADR-0014 multi-cycle divergence. (W4)
7. **Field Engineer mobile look-ahead surface ships** at user-visible
   quality (per W5 sub-pick: responsive Gantt OR 3-week look-ahead OR
   offline cache). Measurable by Lighthouse mobile score for the
   surface OR by user-acceptance smoke test. (W5; OPTIONAL — cycle
   passes without it if W0-W4 close)
8. **ADR-0021 + ADR-0024 (audit-spawned, if any P0/P1 finding warrants
   one) committed** with cross-link to ADR-0019 §"Cycle 3 status" + the
   2026-04-27 council round adversarial output (this ADR §Considered
   Options).
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
  observers. Mitigation: ADR-0021 explicitly commits Cycle 4 to the
  calibration-gated A2 OR E1 deep on the verified harness + corpus
  preconditions; the cycle's external story is "shipping the
  apparatus + corpus + verification so the next moat play can't
  repeat W4 publicly".
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

- [ADR-0019](0019-cycle-2-entry-consolidation-primitive.md) §"Cycle 3
  status" + §"Process" — the gating language and council protocol
  this ADR honors.
- [ADR-0020](0020-calibration-harness-primitive.md) — the harness
  primitive that opened the §"Cycle 3 status" gates; W3 reproduction
  regression test in this cycle finishes ADR-0020's work by closing
  its §"Decision" caveat.
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
