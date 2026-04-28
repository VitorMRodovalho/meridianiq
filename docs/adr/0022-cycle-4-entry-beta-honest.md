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

**Cycle 4 enters as Option β-honest — B-subset (auto-revision + project lifecycle, confirmation UX, RLS-first) + C-visualization (multi-rev overlay, slope + change-point detection) + W4 pre-registered calibration gate for optimism-pattern forecast.**

Plan: **5 mandatory wave-clusters (W0-W4) totaling ~8.5-10.5 sub-waves** + **W5 operator-paced parallel** (NOT cycle-blocking). Per-wave breakdown after DA exit-council adjustments (HB-C tombstone deliverables W2; HB-D fixture authoring W3; NFM-1 W0 decoupling; NFM-5 W4 compression):

| Wave | Budget | Notes |
|------|--------|-------|
| W0 | 1.5 | + L&A review for W5 (NFM-8) |
| W1 | 2 | B-subset core schema |
| W2 | 2-2.5 | + soft-tombstone deliverables (HB-C) |
| W3 | 2-2.5 | + W4 fixture authoring + hash lock (HB-D) |
| W4 | 0.5-1 | Compressed; path-A is expected outcome (NFM-5) |
| **Total** | **8-9.5 nominal** | Solo-dev historical 1.5× = 12-14 actual realistic |
| W5 | parallel | Operator-paced; not cycle-blocking |

**Cycle 4.5 patch is NOT pre-committed as routine escape hatch (DA NFM-2 fix)** — it triggers only if ALL of: (a) ≥2 W1-W4 sub-criteria fail to close, (b) >3 weeks elapse without close, (c) feature regression detected post-deploy. Without all three, Cycle 4 lands as ≥6/9 OR triggers honest cycle-extension ADR amendment without "patch" framing.

### Wave plan

**W0 — Cycle 4 entry + scope memo + ADR ratification + L&A review**

- This ADR (ADR-0022) committed at W0
- `docs/ROADMAP.md` refreshed with Cycle 4 plan
- ADR-0023 number reserved for Cycle 4 W4 outcome amendment (per the ADR-0009-Amendment + ADR-0019-Amendment-1 + ADR-0021 W0-fallback precedent)
- Fly.toml `min_machines_running = 1` deploy verification (PR #66 follow-through)
- **`legal-and-accountability` agent review on Cycle 4 W5 corpus collection prep** (DA NFM-8 fix — moved here from W5 because W5 runs parallel to W1-W4; if L&A review only runs at W5 prep, there's a window where operator collects corpus during Cycle 4 without legal review. L&A runs at W0 to gate W5 entry.)

**Cycle 3 operator carry-over decoupling (DA NFM-1 fix)**: Cycle 3 operator runbook items (`#26` migration apply, `#28` ADR ratifications, `#54` re-mat decision, manifest archive) **DO NOT block W0 close**. They run on operator schedule in parallel to Cycle 4 W0-W5. If W0 critical-path code work completes before operator action, W0 closes and W1 starts; operator backlog continues parallel as W5 corpus assembly precondition. This prevents the third-cycle-of-operator-paced-deferral pattern from blocking Cycle 4 entry on operator availability.

W0 budget: **1.5 waves** (was 1-1.5; bumped to accommodate L&A review).

**W1 — B-subset core schema**

- Migration `028`: add `data_date` + `revision_date` columns to `projects`; add `revision_history` table with `(project_id, revision_number, data_date, baseline_lock_at, content_hash)` + RLS policy
- Update `src/database/store.py` to populate `data_date`/`revision_date` from XER `proj.last_recalc_date` (and fall back to upload timestamp)
- Storage cap env: `MAX_REVISIONS_PER_PROJECT` default 12
- AST policy regression test mirror of `test_rate_limit_policy.py` style for RLS coverage (every new table has RLS policy)

W1 budget: ~2 waves. DA-flagged risks addressed inline: heuristic false-positive detection deferred to W2 (UX confirmation), storage cap explicit, RLS-first.

**W2 — B-subset auto-revision detection + confirmation UX + soft-tombstone deliverables**

- Backend endpoint: `POST /api/v1/projects/{id}/detect-revision-of` returns candidate parent project (heuristic: `proj_short_name` + `proj_id` + content_hash similarity), not committed until confirmed
- Frontend confirmation card: "This XER appears to be a revision of project X (uploaded 2025-09-15). Confirm? [Yes, link as revision] [No, treat as new project]"
- Append-only commit on confirm: writes `revision_history` row + sets `revision_date`

**Soft-tombstone deliverables (DA HB-C fix — promoted from "runbook bullet" to W2 wave deliverables with hard contracts)**:
- Migration `028` adds `revision_history.tombstoned_at TIMESTAMPTZ NULL` + `tombstoned_reason TEXT NULL` columns
- Default queries filter `WHERE tombstoned_at IS NULL` (RLS policy enforces this; no application-level filter)
- AST regression test (mirror of `test_rate_limit_policy.py`): assert that any `SELECT … FROM revision_history` in `src/database/store.py` includes the tombstone filter
- `audit_log` row written on tombstone with `event_type = 'revision_tombstoned'`, `metadata: {revision_id, reason, original_baseline_lock_at}`
- Incident-response runbook in `docs/operator-runbooks/cycle4.md` §"Revision mis-grouping incident" — stepwise tombstone procedure with rollback path (un-tombstone within 24h grace window)

DA-flagged risks addressed:
- Silent grouping eliminated by UX gate (HB2 round 2)
- Soft-tombstone preserves append-only contract via tombstone-not-delete (HB3 round 2 → HB-C exit-council)
- Tombstone filter enforced at SQL/RLS layer (cannot be bypassed by app-layer drift) — same pattern as `RE_MAT_MAX_ROWS` cap in materializer

W2 budget: **2-2.5 waves** (bumped from 1.5-2 to honestly accommodate the tombstone deliverables; per DA NFM-4 wave-count reconciliation).

**W3 — C-visualization core + W4 fixture authoring + W4 fixture-hash lock**

- Backend endpoint: `GET /api/v1/projects/{id}/revision-trends` returns per-revision planned-curves + executed curve + change-point markers (CUSUM)
- Frontend: multi-rev S-curve overlay component with slope detection + CI bands (heteroscedasticity-aware: std grows ∝ √(horizon))
- UI markers: change-point flags rendered with explanation tooltip ("regime change detected at revision N — earlier slope discarded from trend")
- NO forecast curve in this wave; ship visualization-only

**W4 fixture authoring (DA HB-D fix — moved here from W4 to prevent circular tuning)**:
- Author 8 synthetic schedule-revision sequences in `tools/calibration_harness/fixtures/optimism_synth/` with planted regime-changes
- Spec: 3 noise levels × 3 ground-truth-CP positions × 2 baseline patterns (8 total after dedup)
- Hash-lock: SHA256 of fixture set committed to `tools/calibration_harness/fixtures/optimism_synth.lock` at W3 close
- W4 evaluation MUST verify the hash matches before running sub-gate C — if hash drifts (fixtures retuned), evaluation aborts and ADR-0023 documents that the gate was tampered with

W3 budget: **2-2.5 waves** (bumped from 2 to accommodate fixture authoring + hash-lock per DA HB-D).

**W4 — Pre-registered calibration gate for optimism-pattern forecast**

- **Pre-registration (LOCKED in this ADR, not deferred to W3 close)**:
  - **Sub-gate A — corpus census**: count multi-revision-completed-projects in sandbox/lab. Threshold **N≥30** to proceed. **Honest framing**: this is a *minimum-viable demonstration threshold*, NOT a statistically-powered threshold. Brier calibration on N=30 has wide CIs (±0.10-0.15); production deployment requires N≥100-200 (deferred to Cycle 5+ on corpus growth). This is acknowledged here so a path-A fallback at N=4 cannot be retroactively framed as "we just barely missed"; the gate itself is structurally weak by design at this stage.
  - **Sub-gate B — Brier calibration**: heteroscedasticity-aware regression with CI passes **Brier ≤ 0.20** (LOCKED here; W3-close cannot relax this; W4 evaluation cannot tune fixtures to pass). Source for the 0.20 threshold: literature convention for "mediocre but informative" forecasts (well-calibrated < 0.10; useless ≈ 0.25 = always-50% guess on binary outcomes; 0.20 gives "directionally informative but not decision-grade"). At N=30 the 95% CI on Brier is ~±0.10, so even passing 0.20 leaves substantial uncertainty — also acknowledged here.
  - **Sub-gate C — change-point detection F1**: F1 ≥ **0.75** on synthetic regime-change fixtures. **Fixtures authored in W3 close, hash-locked in `tools/calibration_harness.py` fixture registry BEFORE W4 evaluation starts** (NOT authored at W4 — that would be circular). Fixture spec: 8 synthetic schedule sequences with planted regime-changes at known revisions (varying noise σ ∈ {0.1, 0.2, 0.4} × ground-truth-CP at revisions {3, 5, 7} × 2 baseline patterns). F1 computed against ground-truth labels.
  - **Pre-committed path A fallback** (this is the EXPECTED outcome at W4 given current corpus state, NOT a worst case): if any sub-gate fails, ADR-0023 documents outcome honestly. Optimism-pattern forecast ships as **preview** only (visualization-only with clear "not for executive decision" label, feature-flagged off-by-default). Feature reactivates in Cycle 5+ on corpus growth. **Path-A activation is NOT graceful failure framing — it is honest acknowledgment that the corpus that would validate the claim does not exist.**
- W4 evaluation: run all three sub-gates against actual corpus + harness from Cycle 2 W3 (ADR-0020).
- Outcome ADR-0023 authored regardless of pass/fail per ADR-0009 §"W4 outcome" precedent. **ADR-0023 receives DA + IV paired exit-council before merge** (NFM-9 fix; matches ADR-0018 Amendment 1 paired-adversarial protocol for outcome ADRs that document path-A activation, since path-A framing is most vulnerable to sycophantic optimism).

W4 budget: **0.5-1 wave** (compressed from initial 1-1.5 estimate per DA exit-council NFM-5: with corpus likely N=4, sub-gate A failure is the expected outcome, so W4 evaluation work is largely ceremonial — one focused day to run the gates + author ADR-0023 path-A documentation, freeing budget back to product-shipping waves W1-W3).

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
| 1 | ADR-0022 committed + Cycle 4 ROADMAP refresh + L&A review of W5 corpus prep | OPEN — this ADR (L&A review fires at PR #67 merge time per NFM-8 fix) |
| 2 | Migration 028 (data_date + revision_date + revision_history table + tombstone columns + CHECK constraint + RLS policy) applied to staging + production | OPEN |
| 3 | Auto-revision detection backend + confirmation UX + soft-tombstone deliverables (column + AST test + audit_log + runbook) shipped | OPEN |
| 4 | C-visualization (multi-rev overlay + slope + change-point) shipped without forecast claim + W4 synthetic fixtures authored + hash-locked | OPEN |
| 5 | W4 sub-gate A: corpus census documented (N counted; **N≥30 threshold acknowledged minimum-viable, not statistically powered** per HB-B framing) | OPEN |
| 6 | W4 sub-gate B: heteroscedasticity regression Brier calibration evaluated against **locked threshold ≤ 0.20** (pass OR path-A fallback) | OPEN |
| 7 | W4 sub-gate C: change-point detection F1 evaluated on **hash-locked synthetic fixtures** ≥ 0.75 (pass OR path-A fallback) | OPEN |
| 8 | ADR-0023 authored documenting W4 outcome (pass OR path-A) **+ DA + IV paired exit-council on the outcome ADR per NFM-9** | OPEN |
| 9 | Release tag v4.2.0 (or v4.2.0-rc if W4 path-A activated) | OPEN |

Cycle 4 ships gracefully if **≥7/9 close** (DA NFM-3 tightening from initial ≥6/9). Path-A activation on W4 sub-gates 5/6/7 counts as PARTIAL credit (each path-A logged as 0.5 credit), so a Cycle 4 with criteria 1+2+3+4+8+9 closed (=6) plus W4 sub-gates 5+6+7 all path-A (=1.5 partial) totals 7.5/9 — graceful with honest accounting. **&lt;7/9 triggers honest cycle-extension ADR amendment** (NOT "Cycle 4.5 patch" framing — see Cycle 4.5 trigger conditions in §"Decision" above).

**Storage cap behavior at limit (DA NFM-6/NFM-7 fix)**:
- `MAX_REVISIONS_PER_PROJECT` env default 12, configurable
- **Migration 028 includes a CHECK constraint** (DB-level, not app-level): `CHECK ((SELECT COUNT(*) FROM revision_history WHERE project_id = NEW.project_id AND tombstoned_at IS NULL) <= MAX_REVISIONS_PER_PROJECT)` — service-role-key inserts also bound
- At cap: insert returns 409 Conflict with explicit error message "Project has reached revision cap (12). Archive process not yet shipped (Cycle 5+); options: tombstone an existing revision, OR raise cap via env (operations team)."
- Archive process is Cycle 5 deliverable; cap behavior at limit is honest "soft-fail with clear message", not silent rejection or unbounded growth

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

- **DA-as-second-reviewer protocol on this meta-ADR**: per ADR-0018 Amendment 1, ADR PRs with non-trivial code/scope changes get DA exit-council. ✅ **CLOSED** — DA exit-council ran on PR #67 (this ADR's PR) and surfaced 4 hard-blockers (HB-A through HB-D) + 9 new failure modes (NFM-1 through NFM-9). All 4 HB and the merge-critical NFMs (1, 2, 3, 4, 5, 6/7, 8, 9) addressed inline in this ADR via fix-up commits before merge.
- **Legal-and-accountability check on corpus assembly (Cycle 4 W5)**: LGPD/GDPR consent for outcome-labeled corpus is a separate question. **Moved from W5 to W0 deliverable per DA NFM-8** — L&A review fires at this PR's merge time so corpus collection (operator-paced parallel to W1-W4) cannot start before legal review.
- **Investor-view paired check on positioning copy**: any user-facing CHANGELOG/README copy describing C-visualization should be reviewed by IV-paired-with-DA before merge to avoid sycophantic "predictive moat" framing. Required for: Cycle 4 W3 frontend PR + ADR-0023 outcome amendment + Cycle 4 release notes (v4.2.0 or v4.2.0-rc).
- **DA + IV paired exit-council on ADR-0023 (W4 outcome amendment)** per NFM-9: even though path-A activation is the expected outcome, the outcome ADR's framing is exactly what's most vulnerable to sycophantic "graceful failure" language. Pair the protocol explicitly so path-A is honestly framed as "the corpus that would validate the claim does not exist", not "the gate failed gracefully".
- **SB5 verification**: confirm `tests/test_lifecycle_phase.py` (or equivalent) covers construction-vs-non-construction distinction after migration 028 fixtures land. If not covered, add regression test in W1.

## DA exit-council fix-up summary (PR #67 fix-up commit)

This section records the DA-flagged issues addressed inline in this ADR before merge:

**HARD-BLOCKERS (must fix before merge)**:
- **HB-A** (Brier threshold pre-registered): ✅ Locked Brier ≤ 0.20 explicitly in W4 §"Sub-gate B"; W3-close cannot relax. Source citation added (literature convention "mediocre but informative" forecasts).
- **HB-B** (N≥30 statistical power): ✅ Acknowledged as "minimum-viable demonstration threshold, NOT statistically-powered". Production deployment threshold N≥100-200 deferred to Cycle 5+ on corpus growth. CIs at N=30 noted (~±0.10-0.15 on Brier).
- **HB-C** (soft-tombstone deliverables): ✅ Promoted from runbook bullet to W2 wave deliverables — column in migration 028, AST regression test, audit_log entry, RLS-enforced filter, runbook in `docs/operator-runbooks/cycle4.md`.
- **HB-D** (synthetic CUSUM fixtures): ✅ Moved authoring from W4 to W3 close. Fixture spec locked (8 sequences, 3 noise levels, 3 CP positions, 2 baselines). SHA256 hash-locked in `tools/calibration_harness/fixtures/optimism_synth.lock`.

**NEW FAILURE MODES (merge-blocking)**:
- **NFM-1** (Cycle 3 operator carry-over folded into W0 critical path): ✅ Decoupled. Cycle 3 operator runbook items run on operator schedule parallel to Cycle 4; do not block W0 close.
- **NFM-2** (Cycle 4.5 escape-hatch language): ✅ Trigger conditions defined: ALL of (≥2 W1-W4 sub-criteria fail; >3 weeks elapsed; feature regression detected). Without all three, Cycle 4 lands as-is with cycle-extension amendment instead of "patch" framing.
- **NFM-3** (≥6/9 graceful threshold below historical): ✅ Tightened to ≥7/9 with explicit partial-credit accounting for path-A on W4 sub-gates (each path-A = 0.5 credit).
- **NFM-4** (wave count contradiction): ✅ Reconciled via per-wave budget table in §"Decision". Total: 8-9.5 nominal sub-waves + W5 parallel; 12-14 actual under solo-dev 1.5× ratio.
- **NFM-5** (W4 ceremonial nature): ✅ W4 budget compressed from 1-1.5 to 0.5-1 wave acknowledging path-A is expected outcome with current corpus.
- **NFM-6/NFM-7** (storage cap behavior at limit): ✅ Migration 028 includes CHECK constraint (DB-level enforcement). At cap: 409 Conflict with explicit error message + ops options. Archive process Cycle 5+ deliverable.
- **NFM-8** (L&A review timing): ✅ Moved from W5 to W0 deliverable. Fires at this PR's merge time.
- **NFM-9** (ADR-0023 outcome DA review): ✅ Explicitly committed in W4 §"Outcome ADR-0023" — "DA + IV paired exit-council before merge".

**SOFT-BLOCKERS (acceptable)**:
- SB1, SB2, SB3, SB4, SB6: addressed inline per DA exit-council "Verified clean" list.
- SB5 (lifecycle phase regression): added to §"Open process gap" as W1 verification deliverable.

This fix-up represents the recursive validation pattern from PR #38/#56/#58/#60/#64: meta-ADR PRs with non-trivial scope receive their own DA exit-council, and the outcomes are codified inline in the ADR text rather than deferred to follow-up issues. Closes the structural gap that Cycle 3 close-arc lessons (`docs/LESSONS_LEARNED.md`) flagged.
