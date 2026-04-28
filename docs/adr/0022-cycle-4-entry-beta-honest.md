# 0022. Cycle 4 entry — β-honest (auto-revision + multi-rev S-curve, calibration-gated forecast)

* Status: proposed
* Deciders: @VitorMRodovalho
* Date: 2026-04-28
* Cites template: [ADR-0019](0019-cycle-2-entry-consolidation-primitive.md) §"Reversibility" + [ADR-0021](0021-cycle-3-entry-floor-plus-field-shallow.md) (Cycle entry pattern); 4-agent council protocol established Cycle 2 (PV + strategist parallel round 1; devils-advocate + investor-view paired adversarial round 2)
* Cites primitive: [ADR-0020](0020-calibration-harness-primitive.md) (the calibration harness from Cycle 2 W3 — referenced as the gating primitive for Cycle 4 W4 forecast claim)
* Cites lessons: ADR-0009 §"W4 outcome" path-A precedent; Cycle 2 W2 B2 honesty-debt pattern; ADR-0018 Amendment 1 §"Skip protocol" on DA-as-second-reviewer

## Context and Problem Statement

Cycle 3 closed at `v4.1.0` (commit `c8e07b1`, 2026-04-28) with audit re-run, W3 reproduction regression test, W4 code-side `_ENGINE_VERSION` migration, plus close-arc PRs (#62 E2E flake, #63 N3 runtime test, #64 convention normalization, #65 frontend surface-errors fix, #66 Fly always-on BUG-007). Pre-registered success criteria 3/9 closed via Claude work; criteria 2/3/4/7 are operator-paced and pending `flyctl deploy` + maintainer execution per `docs/operator-runbooks/cycle3.md`. Cycle 4 opens against this state.

ADR-0021 §"Wave plan" reserved ADR-0022 + ADR-0023 numbers for Cycle 4 deep candidates without committing to which deeps. The 2026-04-28 user-feedback round surfaced two product gaps the maintainer expected to exist but found broken or absent:

**Gap B — Schema dimensional + revision lifecycle.** Maintainer described an intended hierarchy `Corporation → Portfolio → Project → Contract` with a per-project timeline of monthly schedule revisions and stored baselines. The actual schema is `Organizations → Programs → Projects` (3 layers): each XER upload becomes a separate row in `projects` with no `data_date`/`revision_date` columns, no automatic detection that two uploads represent successive revisions of the same physical project, and no append-only revision history. `programs.revision_number` exists since migration `005` but is manually populated. PMO Director and Consultant/Claims SME personas (per `project_v40_planning.md §3.1`) lose product without this.

**Gap C — Multi-revision S-curve overlay with optimism-pattern detection.** Maintainer described comparing planned-completion S-curves across N successive monthly schedule revisions to detect: (a) consistent rightward shift (delay), (b) stable pattern (on-track), (c) systematic optimism — past revisions repeatedly promised recovery that did not materialize, so the next revision should be discounted by the historical optimism factor. Existing analytics ship S-curves in isolation (`evm.py` PV/EV/AC, `cashflow.py` planned-vs-actual cumulative, `risk.py` Monte Carlo cumulative probability) but none overlay N revisions, none detect change-points in the trend slope, and none produce a forecast curve discounted by historical optimism.

C depends on B operationally: optimism detection requires revisions to be reliably grouped as "the same physical project across N months", which the schema currently doesn't model.

This ADR records the Cycle 4 council round (4 agents, 2 rounds — PV + strategist parallel round 1; devils-advocate + investor-view paired adversarial round 2 per the protocol established in Cycle 2 and codified in ADR-0018 Amendment 1), the synthesis that **rejected "B-completo"** (full 4-layer hierarchy), **rejected "β puro"** (C with monetizable optimism-pattern moat claim) but **accepted the chairman recommendation `β-honest`**: ship B-subset (auto-revision detection + project lifecycle store) + C-visualization (multi-rev overlay with slope detection) with a **pre-registered calibration gate** at W4 that the optimism-pattern forecast claim must pass before the feature is positioned as load-bearing.

## Decision Drivers

1. **Pattern-otimismo without corpus is mathematically vacuous.** Round 2 DA hard-blocker #1: optimism-bias detection requires Brier/calibration-honest validation, which requires outcome knowledge (project completion fact). The sandbox at `~/Downloads/A/` has 105 XERs total; ADR-0009 W4 found 4 multi-revision programs in that sandbox and 0 phase flips. Pattern-otimismo forecast needs N≥30 multi-revision-completed-projects with outcome data — and even more critically, a labeled optimism baseline (what was the planned curve at each revision; what was the actual outcome). Without this corpus, a forecast curve labeled "predictive" is W4-redux: harness passes shape, fails calibration gate, ships under path-A fallback. Same pattern, same trap.

2. **B-completo (4 layers) is table stakes, not moat.** Round 1 strategist + round 2 IV converged: Portfolio + Contract entities are PPM commodity. ERPs (incumbent and new) ship them; replicable in 6-12 weeks by any incumbent. Adding all 4 layers in Cycle 4 dilutes positioning ("schedule intelligence layer" → "another PPM tool"). Round 1 PV concurred at the persona level — PMO Director and GC personas value Portfolio, but their pull does not pay for the dilution. Defer Portfolio + Contract to Cycle 5+ on demand-validation evidence (≥3 prospects asking explicitly), per IV's standing demand-validation gap critique.

3. **B-subset (auto-revision + project lifecycle) addresses real UX pain regardless of moat.** The user-reported A1 bug ("schedules belonging to the same project but in different versions/months are treated as separate projects") is resolved by B-subset. Independent of GTM or moat, the maintainer cannot use the product end-to-end without it; this is functional debt, not feature speculation. PV scoped 6-8 waves; DA scoped soft-blocker risks (heuristic false-positives, append-only-vs-soft-delete contradiction, storage growth, RLS-first design) that expand the wave count to ~6-8 with explicit confirmation UX + incident-response runbook.

4. **C-visualization (multi-rev S-curve overlay) has standalone value without forecast claim.** Showing 5 revisions × 1 executed × change-point markers on one chart is diagnostic value at the visualization level. AACE RP 29R-03 §"Window analysis" covers the methodology. Personas Owner / Claims SME / Cost Engineer / Risk Manager all gain a defensible diagnostic. The forecast curve is the problematic addition — strip it from the W2-W3 deliverable; ship visualization + slope detection + change-point markers + CI bands, label preview without forecast.

5. **W4 calibration gate must be PRE-REGISTERED with explicit fail-handling.** Per ADR-0009 §"W4 outcome" path-A precedent: pre-commit success criteria + path-A fallback (fail honestly, ship limited feature, document outcome) before W4 starts. Without pre-registration, the gate becomes a post-hoc rationalization vehicle — exactly the trap ADR-0018 Amendment 1 §"Pre-registration discipline" exists to prevent. ADR-0020 §"Decision" caveat (manifest archive pending operator action since 2026-04-19) is also part of this gate's pre-conditions: harness reproducibility is verified, but the underlying corpus assembly is not.

6. **Solo-maintainer fatigue is the dominant operational constraint.** Cycle 1 + 2 + 3 each shipped 6-8 waves with 1.5× scope-ratio growth observed. Cycle 4 must size to that empirical reality, not aspiration. Round 2 DA + IV both flagged: B-subset (~6 waves) + C-visualization (~3 waves) + W4 honest-gate (~1 wave) + W5 operator-paced corpus assembly start (~0.5 waves) = 10-11 waves nominal, expects 12-15 actual. This is a deep-class cycle, not consolidation. Mitigations are explicitly declared (Cycle 4.5 patch reservation; per-wave graceful-landing pattern from Cycle 2).

7. **Acquisition-path claim is unverified and explicitly rejected as scope-validation evidence.** Round 2 IV confronted the strategist's "acquirer-premium for pattern-otimismo" thesis: no PPM incumbent has acquired a solo-maintained MIT open-source schedule-analytics tool in the last 5 years publicly. Pattern-match in construction-tech VC space points to vertical SaaS top-down (≥$10M ARR + ≥30 team) or proprietary-IP-with-patents — not solo-dev OSS. ADR-0022 explicitly does NOT presume venture-scale path; it sizes Cycle 4 as **lifestyle-product enhancement with research-grade primitive output** until demand-validation evidence (≥3 prospects design-partnering OR AACE reference-implementation citation) materializes. This reframes the acquisition-path claim from "premise" to "optionality"; the cycle ships value either way.

8. **Internal-driven scope is acknowledged honestly.** Round 2 IV: maintainer reported B+C because "pensei que tinha desenhado", which is N=1 self-validation, not customer pull. ADR-0022 records this honestly; the gap closes when contributor signal (issue-level requests) or paid-prospect feedback emerges. Until then, B-subset + C-visualization are the maintainer's own UX improvements + research framework — defensible scope, not market-validated demand.

## Considered Options

### Option α — B-completo (full 4-layer hierarchy + auto-revision)

Schema dimensional Corp/Portfolio/Project/Contract + revision_history + project lifecycle store + UI selectors + RLS multi-tenant policies for each new layer + migration plan for existing 88 prod rows.

**Rejected.** Estimated 15-20 waves. Round 2 DA + IV agreed: dilutes positioning, consumes 2-3 cycles, no moat, blast radius high (touches 27 migrations + RLS), reversibility low. Round 1 strategist explicitly: "drift risk ALTO" toward PPM territory. PV agreed at the strongest-need persona level (PMO Director values Portfolio, but the dilution cost outweighs that pull without demand-validation evidence). Acquirer pays commodity for B; not premium. Same 5 reasons ADR-0019 §"Why NOT A1+A2" enumerated reapply at the 4-layer scale.

### Option β puro — C primary + B-minimal (P6 `proj_id` only) — Strategist round 1 primary

Auto-revision via P6 `proj_id` exact-match only (B-minimal, ~3-5h) + multi-rev S-curve overlay + pattern-otimismo as load-bearing forecast feature with claimed moat.

**Rejected** by round 2 DA + IV synthesis. Pattern-otimismo as load-bearing forecast claim requires corpus that does not exist; shipping it as moat is theatrical. Strategist's "data accumulation effect" thesis collapses under DA's hard-blocker #1 (corpus reality) and IV's data-network-effect-for-solo-dev impossibility on the GTM timeline. Round 2 PV concurred reluctantly: "killer feature" framing presumes the calibration that hasn't been proven.

### Option β-honest — C-visualization + B-subset with confirmation UX + pre-registered W4 gate (chairman recommendation, accepted)

B-subset:
- `data_date` + `revision_date` columns in `projects` table
- Auto-revision detection with **confirmation card UX** (not silent grouping; user confirms "yes this is a revision of project X" before grouping commits)
- `revision_history` append-only table with baseline lock + **explicit incident-response runbook** for mis-grouped uploads (soft-tombstone with audit trail, not hard-delete)
- Storage growth budget: explicit cap (e.g., 12 revisions max per project, oldest archived to compressed offline; configurable via env)
- RLS-first design: every new table gets RLS policy authored in the same migration that creates it

C-visualization:
- Multi-rev S-curve overlay UI (planned curves × N revisions × executed)
- Slope detection with CI bands (heteroscedasticity-aware regression — variance grows with horizon)
- Change-point markers (CUSUM or PELT) so regime-change is visible to user, not silently averaged into trend
- Pattern marker visual ("the last 3 revisions shifted right by mean +X days/revision") **with explicit CI** — NOT a forecast point estimate

W4 honest gate (pre-registered):
- Optimism-pattern forecast feature is **gated** on corpus N≥30 multi-revision-completed-projects + Brier calibration ≤ pre-committed threshold
- **Path A fallback explicit**: if gate fails, ship visualization-only + change-point detection + label "preview, not for executive decisions" (matches Cycle 2 W2 B2 honesty-debt pattern)
- Outcome ADR amendment authored at gate-eval moment, not at cycle close

W5 operator-paced (deferred to corpus-side, not cycle-blocking):
- ADR-0020 manifest archive close (Cycle 1 W4 backlog)
- Corpus assembly start: collect outcome-knowledge from completed projects with LGPD-compliant labeling
- #54 W4 re-mat closure

**Selected.** Round 2 DA + IV both accept this framing as honest: C-visualization ships value without overselling; W4 gate makes the forecast claim falsifiable + escape-hatched; B-subset addresses functional debt. Round 1 PV + Strategist accept the de-scoped framing on the condition that "pattern-otimismo is a Cycle 5 closure on calibration evidence" is committed (this ADR commits it).

### Option γ — Defer B+C entirely; close-arc Cycle 3 carry-over

Continue close-arc primitives (operator runbook execution, BUG-007 deploy, manifest archive). No deep.

**Rejected as primary cycle commitment.** Round 1 strategist + round 2 IV both noted: third consecutive cycle without deep risks "honesty inflation" (technically impeccable, competitively flat). User-reported A1 functional bug forces some B-subset work regardless; γ pure is "do nothing about reported bug" which is not a defensible cycle plan. γ-elements are folded into Cycle 4 W5 (operator paced) instead of replacing the cycle.

### Option δ — C standalone with B-zero (manual revision grouping)

Multi-rev S-curve where user manually points "these 4 schedules are revisions of the same project". B not modified.

**Rejected.** PV: ignores the functional UX bug user reported. Strategist: friction limits adoption. DA: doesn't unblock corpus assembly. IV: doesn't change demand-validation gap. No agent prefers this.

## Decision

**Cycle 4 enters as Option β-honest — B-subset (auto-revision + project lifecycle, confirmation UX, RLS-first) + C-visualization (multi-rev overlay, slope + change-point detection) + W4 pre-registered calibration gate for optimism-pattern forecast.** Plan: **5 mandatory waves + 1 operator-paced (W5)**, with explicit Cycle 4.5 patch reservation if scope extends per the Cycle 1+2+3 pattern.

### Wave plan

**W0 — Cycle 4 entry + scope memo + ADR ratification**

- This ADR (ADR-0022) committed at W0
- `docs/ROADMAP.md` refreshed with Cycle 4 plan
- ADR-0023 number reserved for Cycle 4 W4 outcome amendment (per the ADR-0009-Amendment + ADR-0019-Amendment-1 + ADR-0021 W0-fallback precedent)
- Fly.toml `min_machines_running = 1` deploy verification (PR #66 follow-through)
- Operator runbook execution per `docs/operator-runbooks/cycle3.md` if not yet done (W1+W2-A+W2-B+W4 from Cycle 3)

W0 budget: ~1-1.5 waves.

**W1 — B-subset core schema**

- Migration `028`: add `data_date` + `revision_date` columns to `projects`; add `revision_history` table with `(project_id, revision_number, data_date, baseline_lock_at, content_hash)` + RLS policy
- Update `src/database/store.py` to populate `data_date`/`revision_date` from XER `proj.last_recalc_date` (and fall back to upload timestamp)
- Storage cap env: `MAX_REVISIONS_PER_PROJECT` default 12
- AST policy regression test mirror of `test_rate_limit_policy.py` style for RLS coverage (every new table has RLS policy)

W1 budget: ~2 waves. DA-flagged risks addressed inline: heuristic false-positive detection deferred to W2 (UX confirmation), storage cap explicit, RLS-first.

**W2 — B-subset auto-revision detection + confirmation UX**

- Backend endpoint: `POST /api/v1/projects/{id}/detect-revision-of` returns candidate parent project (heuristic: `proj_short_name` + `proj_id` + content_hash similarity), not committed until confirmed
- Frontend confirmation card: "This XER appears to be a revision of project X (uploaded 2025-09-15). Confirm? [Yes, link as revision] [No, treat as new project]"
- Append-only commit on confirm: writes `revision_history` row + sets `revision_date`
- Incident-response runbook: how to soft-tombstone a mis-grouped upload (audit-logged, append-only-compatible)
- DA-flagged risks addressed: silent grouping eliminated by UX gate; soft-tombstone preserves append-only contract

W2 budget: ~1.5-2 waves.

**W3 — C-visualization core**

- Backend endpoint: `GET /api/v1/projects/{id}/revision-trends` returns per-revision planned-curves + executed curve + change-point markers (CUSUM)
- Frontend: multi-rev S-curve overlay component with slope detection + CI bands (heteroscedasticity-aware: std grows ∝ √(horizon))
- UI markers: change-point flags rendered with explanation tooltip ("regime change detected at revision N — earlier slope discarded from trend")
- NO forecast curve in this wave; ship visualization-only

W3 budget: ~2 waves.

**W4 — Pre-registered calibration gate for optimism-pattern forecast**

- **Pre-registration (committed at W3 close, before W4 starts)**:
  - Sub-gate A: corpus census — count multi-revision-completed-projects in sandbox/lab; threshold N≥30 to proceed
  - Sub-gate B: heteroscedasticity-aware regression with CI passes Brier calibration ≤ X (X to be specified at pre-registration; recommended ≤ 0.20)
  - Sub-gate C: change-point detection F1 score ≥ Y on synthetic regime-change fixtures (Y ≥ 0.75)
  - **Pre-committed path A fallback**: if any sub-gate fails, ADR-0023 documents outcome honestly, optimism-pattern forecast ships as **preview** only (visualization-only with clear "not for executive decision" label), feature reactivates in Cycle 5+ on corpus growth
- W4 evaluation: run gates against actual corpus + harness from Cycle 2 W3
- Outcome ADR-0023 authored regardless of pass/fail per ADR-0009 §"W4 outcome" precedent

W4 budget: ~1-1.5 waves.

**W4 fallback if gate fails (path A explicit)**:
- C ships visualization + change-point markers + slope CI bands ONLY (no forecast curve)
- Optimism-pattern feature flagged as "preview, not load-bearing" (Cycle 2 W2 B2 honesty-debt pattern explicit reuse)
- Cycle 4 still ships at v4.2.0 with reduced C scope
- Corpus assembly continues as Cycle 5+ pre-condition

**W5 — Operator-paced (parallel, not cycle-blocking)**

- ADR-0020 manifest archive: operator archives `/tmp/w4_*.json` → `meridianiq-private` per cycle 3 runbook (Cycle 1 backlog from 2026-04-19)
- #54 W4 re-mat closure: operator chooses Option A bulk re-mat OR Option B tombstone per `docs/operator-runbooks/cycle3.md §W4`
- Corpus assembly start: identify completed projects with outcome data + LGPD/GDPR consent path; document in `meridianiq-private`
- Claude support: comment review, SQL validation, runbook fix-ups during operator execution

W5 budget: operator-paced, not cycle-blocking. **W4 gate can run with current corpus** (likely failing sub-gate A); W5 corpus assembly is preparation for Cycle 5+ re-evaluation.

### Pre-registered success criteria

| # | Criterion | Status |
|---|---|---|
| 1 | ADR-0022 committed + Cycle 4 ROADMAP refresh | OPEN — this ADR |
| 2 | Migration 028 (data_date + revision_date + revision_history table + RLS policy) applied to staging + production | OPEN |
| 3 | Auto-revision detection backend + confirmation UX shipped | OPEN |
| 4 | C-visualization (multi-rev overlay + slope + change-point) shipped without forecast claim | OPEN |
| 5 | W4 sub-gate A: corpus census documented (N counted, may fail threshold) | OPEN |
| 6 | W4 sub-gate B: heteroscedasticity regression Brier calibration evaluated (pass OR path-A fallback) | OPEN |
| 7 | W4 sub-gate C: change-point detection F1 evaluated on synthetic fixtures (pass OR path-A fallback) | OPEN |
| 8 | ADR-0023 authored documenting W4 outcome (pass OR path-A) | OPEN |
| 9 | Release tag v4.2.0 (or v4.2.0-rc if W4 path-A activated) | OPEN |

Cycle 4 ships gracefully if **≥6/9 close**. ≥7/9 with path-A activation is acceptable per ADR-0009 W4 precedent. <6/9 triggers Cycle 4.5 patch.

### Reversibility

- B-subset migrations (028) are forward-only but additive (new columns + new table). Rollback path: `ALTER TABLE projects DROP COLUMN data_date, DROP COLUMN revision_date; DROP TABLE revision_history CASCADE;` — destructive but recoverable from Supabase nightly backups.
- C-visualization is frontend + read-only backend endpoint; fully reversible.
- W4 gate is pre-registered; path-A fallback is explicit; outcome ADR is authored regardless. No silent feature rot.
- Confirmation UX prevents silent grouping; mis-grouping requires user click — auditable.

## Negative consequences / accepted costs

- **Solo-maintainer fatigue risk**: 10-11 wave nominal Cycle expects 12-15 actual. Mitigation: Cycle 4.5 patch reservation explicit; per-wave graceful landing per Cycle 2; W5 operator-paced not cycle-blocking.
- **Pattern-otimismo positioning constraint**: Cannot be claimed as load-bearing forecast or moat until W4 gate passes (which requires corpus that may not exist for ≥6 months). Marketing/positioning copy must reflect this — "research framework + visualization preview", not "predictive engine". CHANGELOG + LESSONS_LEARNED entries written honestly.
- **Portfolio + Contract layers deferred to Cycle 5+ on demand-validation evidence.** PMO Director and GC personas wait at least one more cycle. Acceptable per IV's demand-validation gap critique — these layers reactivate when ≥3 prospects ask explicitly OR contributor PR signals demand.
- **Storage growth cap (12 revisions/project default)**: older revisions get archived. Operational cost: archive process + retrieval UX must be designed (deferred to Cycle 4 W2 or Cycle 5 if scope extends).
- **Calibration corpus assembly is multi-cycle**: Cycle 4 W5 starts it; Cycle 5+ continues. Pattern-otimismo forecast feature reactivates when corpus reaches threshold + Brier calibration passes.

## Honest disclosures (per ADR-0018 Amendment 1 §"Pre-registration discipline" + IV demand-validation critique)

1. **Internal-driven scope**: B+C originated from maintainer self-validation ("pensei que tinha desenhado"). N=1. ADR-0022 ships scope on functional-debt grounds (UX bug user reported) + research-framework grounds (calibration harness reuse), NOT market-validated demand. Demand validation gap closes when ≥3 paid prospects design-partner OR AACE reference-implementation citation OR contributor PR signals.

2. **Acquisition-path optionality, not premise**: ADR-0022 does NOT presume venture-scale path. Pattern-otimismo as moat claim is rejected pending corpus + GTM evidence. If acquirer interest emerges, evidence updates. Until then, MeridianIQ is sized as lifestyle product + research framework primitive.

3. **Pattern-otimismo as moat claim is not falsifiable today** because corpus doesn't exist to test the claim. ADR-0022 makes the claim falsifiable via W4 pre-registered gate. Path-A fallback ships visualization-only if gate fails. This is the structural anti-theater commitment.

4. **AACE/PMI standards anchoring is not moat by itself**: standards by definition are non-proprietary. Anchoring democratizes implementation, not privatizes it. Strategist's "standards-anchoring as moat" framing is rejected. Standards-anchoring is positioning + credibility, not defensibility.

5. **Solo dev + MIT + no GTM = lifestyle/passion-project pattern, not venture-scale.** This is acknowledged. ADR-0022 is sized for this reality. If path changes (co-founder, seed round, dual-license), ADR-0022 amendments document the change.

6. **Corpus assembly is operator + LGPD-blocked**: outcome-knowledge labeled corpus needs (a) completed projects with completion fact, (b) LGPD/GDPR consent for use, (c) anonymization for any contributor-shared data. Cycle 4 W5 starts the operator side; Cycle 5+ continues. ADR-0020 manifest archive backlog (pending since 2026-04-19) is a related operator action that compounds this debt — closes in Cycle 4 W5 or Cycle 4.5.

## Scope of what this ADR does NOT do

- Does NOT add Portfolio entity. Programs serve as agglomeration today. Portfolio waits Cycle 5+ on demand evidence.
- Does NOT add Contract entity. `/contract/` page remains compliance analysis, not contract management.
- Does NOT ship pattern-otimismo as predictive forecast pre-W4 evaluation. Visualization-only until gate passes.
- Does NOT presume sandbox corpus is sufficient for W4 sub-gate A. W4 starts with corpus census; failure is expected; path-A fallback is pre-committed.
- Does NOT commit to Cycle 5 deep selection. Cycle 4 close evaluates outcomes + corpus state; Cycle 5 entry ADR (eventual) makes the decision.
- Does NOT claim acquisition target. IV explicitly rejected this presumption; ADR-0022 records that rejection.
- Does NOT modify ADR-0019 §"Reversibility" — both A1+A2 and E1 remain reserved for future cycles on calibration evidence per their original gating language.

## Cross-references

- [ADR-0009](0009-w4-outcome.md) — W4 path-A precedent (the reference for honest fallback discipline)
- [ADR-0014](0014-derived-artifact-provenance-hash.md) — `input_hash` canonical contract referenced by `revision_history` content_hash
- [ADR-0018 Amendment 1](0018-cycle-cadence-doc-artifacts.md) — DA-as-second-reviewer protocol applies to W1-W4 PRs
- [ADR-0019](0019-cycle-2-entry-consolidation-primitive.md) — Cycle 2 entry pattern + reversibility framing
- [ADR-0019 Amendment 1](0019-cycle-2-entry-consolidation-primitive.md#amendment-1) — Rate-limit policy contract referenced by W1-W2 endpoint additions
- [ADR-0020](0020-calibration-harness-primitive.md) — Calibration harness reused for W4 evaluation
- [ADR-0021](0021-cycle-3-entry-floor-plus-field-shallow.md) — Cycle 3 entry + ADR-0022/0023 number reservation
- ADR-0023 (reserved) — Cycle 4 W4 outcome amendment (pre-committed authorship per W4 plan above)
- `project_v40_planning.md §3.1` — persona roster, gap log
- `project_v40_cycle_3.md` — Cycle 3 scope memo precedent
- `docs/operator-runbooks/cycle3.md` §W4 — Cycle 3 operator carry-over, partial overlap with W5 corpus assembly
- `docs/LESSONS_LEARNED.md` — Cycle 1+2+3 lessons informing wave count + Cycle 4.5 patch reservation
- PR #65 (frontend surface-errors) + PR #66 (Fly always-on BUG-007) — Cycle 3 close-arc ops fixes, deploy verification is W0 prerequisite

## Open process gap

- **DA-as-second-reviewer protocol on this meta-ADR**: per ADR-0018 Amendment 1, ADR PRs with non-trivial code/scope changes get DA exit-council. This ADR is scope-only (no code), but the wave plan it locks in is non-trivial. Run DA exit-council on the PR opening this ADR.
- **Legal-and-accountability check on corpus assembly (Cycle 4 W5)**: LGPD/GDPR consent for outcome-labeled corpus is a separate question. Run `legal-and-accountability` agent on W5 prep before any corpus collection commences.
- **Investor-view paired check on positioning copy**: any user-facing CHANGELOG/README copy describing C-visualization should be reviewed by IV-paired-with-DA before merge to avoid sycophantic "predictive moat" framing.
