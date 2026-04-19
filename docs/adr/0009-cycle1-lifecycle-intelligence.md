# 0009. Cycle 1 v4.0 — Lifecycle Intelligence on Materialized Analytics (with pre-committed fallback)

* Status: accepted — §"Wave 4" amended by **Amendment 1 (2026-04-19)** (pre-registration) and **Amendment 2 (2026-04-19)** (outcome + W5/W6 pre-committed fallback activated) at the bottom of this file. Companion artifact: `docs/adr/0009-w4-outcome.md`.
* Deciders: @VitorMRodovalho
* Date: 2026-04-18
* Council review: product-validator, strategist, legal-and-accountability, devils-advocate (see `project_v40_cycle_1.md` for anonymised synthesis). Amendment 1 adds a second round: product-validator + legal-and-accountability + devils-advocate (2026-04-18, anonymised synthesis in `project_v40_cycle_1.md`).

## Context and Problem Statement

v3.9.0 ("Real-Time + Extensibility") shipped on 2026-04-18 closing the P2 backlog and opening the v4.0 discovery cycle. During the v4.0 discovery session three gaps flagged by the maintainer surfaced as technically interdependent:

- **§1.1 Ingest-time materialization** — today the pipeline is lazy: upload persists the raw `ParsedSchedule`; every feature recomputes derivatives (KPI bundle, DCMA findings, float trends, health score, CPM paths) on first visit under a 120-second in-memory cache. Friction: each new session re-parses, and the engine proposed for §1.5 would inherit the same latency problem.
- **§1.4 Lifecycle phase metadata** — no annotation captures where in the project lifecycle a given schedule version sits (initiation, planning, design, procurement, construction early/mid/late, commissioning, closeout). Without it, "float erosion rate" cannot be interpreted context-aware.
- **§1.5 Phase-aware analytics engine** — a new `src/analytics/lifecycle_health.py` that combines (schedule, baseline, phase) into phase-aware findings, reusing existing `float_trends.py` + DCMA.

All three share the same architectural prerequisite: a durable surface for derivatives with provenance. Treating them as separate cycles duplicates the schema and invalidation work; bundling them as a single "Lifecycle Intelligence" deep delivers one coherent v4.0 wedge — provided scope is disciplined and the heuristic is calibrated before it ships.

Two Cycle 1 shallows accompany the deep:
- **§1.2 + §1.3 Auto-grouping + Baseline inference** (2 waves, ordered §1.2 → §1.3; baseline requires groups to exist)
- **§1.6 MS Project surfacing** (~0.5 wave; backend already parses `.xml`; frontend silent)

## Decision Drivers

- **Differentiation defensible under §1.10.** The strategic principle is "don't compete with ERPs — be the data-centric analytical layer on top". Lifecycle Intelligence is exactly that. Ingest-time materialization is performance enablement, not scope drift.
- **Provenance is the forensic contract.** Consultant / Claims SME personas (see `project_v40_planning.md §3.1`) need derivatives that carry `engine_version + ruleset_version + input_hash + inferred_at` or the output is inadmissible as even corroborative evidence under SCL Protocol 2nd ed.
- **Heuristic without calibration is worse than no heuristic.** A lifecycle phase classification that is wrong 30% of the time undermines the whole platform's credibility in the forensic use case — which is the premium use case.
- **Scope containment.** The naive estimate (7–8 waves) undercounts by roughly 3 waves (15 endpoints to refactor for read-through, backfill strategy for ~400 existing projects, confidence-score UI, calibration harness). A fallback must be pre-committed before wave 1 starts so a mid-cycle slip does not become a mid-cycle scope cut.
- **Synchronous materialization on a 1-CPU Fly.io worker is self-sabotage.** The upload path cannot block for 15–60 seconds on a 50k-activity XER without tripping the Fly.io health check (see BUG-007 precedent). Materialization must be asynchronous with a persisted `ready/computing/stale` state.
- **Governance debt must be paid before new debt is taken.** Three v3.9 decisions shipped without ADRs (plugin architecture, WebSocket progress, MCP HTTP — now backfilled as ADRs 0006/0007/0008). The `audit_log.user_agent` column promised in v3.8 wave 13 was silently dropped by Supabase because the migration never added it. These pre-existing gaps must close before Cycle 1 technical work starts.

## Considered Options

1. **Option A — Ship the fused scope (§1.1 + §1.4 + §1.5) as originally proposed, 7–8 waves, single release.**
2. **Option B — Surgical deep with pre-committed fallback.** Fuse §1.1 + §1.4 + §1.5 but with (i) provenance baked into the schema from wave 1, (ii) an explicit calibration gate at end of wave 4, and (iii) a pre-committed fallback: if the gate fails (<70% of sandbox XERs classified at confidence ≥80%), §1.5 slips to v4.1 and the remaining waves pick up optimizer + Svelte-composable WS progress hooks from the carry-over P3.
3. **Option C — Shallows first, deep second.** Ship auto-grouping + baseline + MSP surfacing in waves 1–3, then tackle the deep. Quick wins early; momentum risk on the ambitious piece.
4. **Option D — Split into v4.0 (materialization only) and v4.1 (lifecycle).** Two releases, two talking points, lower per-release risk, longer time to the differentiation story.

## Decision Outcome

**Chosen: Option B — surgical deep with pre-committed fallback and provenance guaranteed from wave 1, preceded by a Wave 0 governance-and-hardening cleanup.**

### Wave plan

**Wave 0 (governance + foundational hardening — before any v4.0 technical work):**
- Migration 021: add `user_agent TEXT` to `audit_log` (closes v3.8 wave 13 silent gap).
- Backfill ADRs 0006 (plugin architecture), 0007 (WebSocket progress), 0008 (MCP HTTP/SSE) — now shipped.
- Harden `_persist_schedule_data` against mid-persist failure: either transactional RPC, or write `projects` row last, or add a `status` column that flips to `ready` only after all children succeed.
- Add `invalidate_namespace("schedule:kpis")` call to the upload happy-path (documented but never called as of v3.9.0).
- Add `UNIQUE(user_id, lower(name))` index on `programs` and convert `get_or_create_program` to Postgres upsert (prerequisite for shallow #1 fuzzy grouping).
- Replace `xml.etree.ElementTree` with `defusedxml.ElementTree` in `src/parser/msp_reader.py` (prerequisite for shallow #2; closes CWE-611 XXE vulnerability before "first-class MSP" marketing).
- Harden `/api/v1/ws/progress/{job_id}`: require Bearer token, server-generate `job_id` and return in upload response, add TTL reaper for abandoned channels (closes P1 from v3.9 wave 10).

**Wave 1 (deep — materialization foundation):**
- Migration 023 [renumbered from 022 after Wave 0 #5 consumed 022]: `schedule_derived_artifacts` table with provenance columns. Full column shape (9 columns including `computed_by`, `stale_reason`, `effective_at` renamed from `inferred_at`), RLS **quadruple** (SELECT/INSERT/UPDATE/DELETE — UPDATE added to close the silent-no-op class ADR-0012 amendment #2 identified), partial index strategy, `UNIQUE NULLS NOT DISTINCT`, and the `input_hash` canonical algorithm are specified in **ADR-0014**. `ON DELETE CASCADE` on `project_id` preserved; RLS policies re-verify ownership via `projects.user_id = auth.uid()` (no `WITH CHECK (TRUE)`).
- Audit: every materialization writes one `audit_log` row with `action = 'materialize'`.

**Wave 2 (deep — async materialization pipeline):**
- Hook post-parse in `upload.py` publishes a materialization job; materialization runs as a background task (arq or asyncio-Task with a bounded pool); upload returns `202 Accepted` with `job_id` immediately.
- Frontend shows `ready / computing / stale` state on project cards and analysis views.
- Backfill strategy: an off-peak worker job re-materializes existing projects; reads fall back to "compute-and-persist-then-return" on cache miss during the backfill window.

**Wave 3 (deep — lifecycle phase metadata):**
- `lifecycle_phase` enum + nullable column on `schedule_versions`.
- Inference heuristic (data_date vs plan_start/plan_end ratio + physical %-complete + S-curve shape) with a confidence score exposed in the UI, not just a label.
- Manual override with audit trail in a separate `lifecycle_override_log` table (append-only by convention, no DELETE policy).

**Wave 4 (deep — calibration + gate):**  *[AMENDED: see Amendment 1 — n=103 recovered sandbox split into gate subset (n≈23, dedup'd) + hysteresis subset (n≈80); `unknown` denominator convention pre-registered; phase-distribution sub-gate added; publication scope reduced to coarse-banded aggregates.]*
- Run the inference against the sandbox of 105 XERs (`reference_sandbox_dataset.md`) under confidential off-CI process.
- Gate criterion: ≥70% of sandbox XERs classified with confidence ≥80%, and manual spot-check of 20 projects shows ≤5% obviously-wrong classifications.
- Also: open a public GitHub issue titled "Calibration dataset contributions wanted — phase-aware analytics" as the first community-contribution hook. Publish the heuristic methodology and the anonymised confusion matrix from the sandbox so external contributors can extend.

**Wave 5–6 (deep — conditional branch):**
- **If gate passes:** ship `src/analytics/lifecycle_health.py` as an isolated package (zero circular imports from the rest of the codebase — preserves the option for a future licensing / packaging split without forcing that decision now), plus the UI panel at `/analysis/lifecycle`, plus PDF report integration. Author ADR-0010 covering the engine's methodology and ruleset version 1.
- **If gate fails:** §1.5 slides to v4.1. Waves 5–6 instead deliver two carry-over P3 items: `progress_callback` wiring in `evolution_optimizer.py` + heavy report generators (≈30 minutes each once the wave 10 pattern is in hand), and a Svelte composable for the WebSocket progress bar wired to the risk-simulation page. Both close tail debt from v3.9 wave 10.

**Shallow #1 (2 waves, parallel where possible):**
- Wave A: auto-grouping via `rapidfuzz` (MIT) under a new `[grouping]` optional extra; Levenshtein over `proj_short_name` + exact match on XER `project_id`; confirmation card at second upload shows diff of `proj_short_name`, total activity count, `data_date` delta, duration delta — a yes/no prompt alone is insufficient signal. ADR-0011 covers the dep category.
- Wave B: baseline inference (earliest `data_date` within group) + pre-fill in compare picker + override.
- Prerequisite: Wave 0 `UNIQUE` index and upsert refactor of `get_or_create_program`.

**Shallow #2 (~0.5 wave):**
- Copy, i18n, dropzone, docs, FAQ, README for MS Project (XML) first-class support.
- Prerequisite: Wave 0 `defusedxml` swap.
- Also add UTF-16 BOM detection to `msp_reader.parse` (Microsoft tooling commonly emits UTF-16-LE with BOM; current UTF-8-only path breaks PT-BR / ES-LATAM content with accented strings).

**Governance artefacts landing in the same cycle:**
- `PRIVACY.md` — non-binding factual data-handling disclosure (Supabase region, what is materialized, retention default, deletion path). Published alongside migration 023.

### Rationale

- **Provenance from wave 1 is the only non-replayable decision in the cycle.** Omitting it and adding it later would require re-materializing every artifact — painful with 400+ projects. Adding columns to a new empty table has zero cost.
- **The calibration gate at W4 is the discipline that converts scope ambition into schedule reliability.** Without it, the cycle runs until the deep "feels done", which historically over-runs. With it, the slip has a named landing pad (the two carry-over P3 items).
- **Isolating `lifecycle_health.py` as a package is free optionality.** If the MIT-pure path remains the right long-term call, nothing is lost. If a future dual-license decision becomes relevant (for example, a premium benchmark-federated tier), the architecture is already ready. Deferring the licensing decision while preserving the architecture is the responsible move.
- **Wave 0 governance cleanup pays interest on v3.9's debt.** Silent functional gaps (user_agent, missing ADRs, XXE in the parser surface, race in program creation, absent cache invalidation, unauthenticated WebSocket) cannot be allowed to compound under the new work. Each of the Wave 0 items is either a ~30-minute fix or a conceptual "write a doc that should have been written". The total cost is under a full wave; the cost of skipping is scoping hell in later waves.
- **Community calibration hook is a strategic signal.** MeridianIQ has no external contributors today. A public, honest "we need calibration data from diverse project types" invitation converts a methodological weakness into the first visible open-source hook. If it draws even two external project datasets, the product has a seed of network effect that no competitor can retroactively build.

### Rejected alternatives

- **Option A (fused as proposed)** — rejected because (i) the 7–8 wave estimate is demonstrably light by 3 waves without a scope-disciplined approach, (ii) without provenance from wave 1 the migration becomes irreversible and any future engine version change corrupts historical artifacts, (iii) the council red-team identified seven P1 pre-existing bugs that Option A would compound.
- **Option C (shallows first)** — rejected because "conservative first" has a failure mode: a next shallow always looks more urgent, and the ambitious piece keeps sliding. The product already shipped 45 engines in v3.9; credibility gains from one more shallow quick win are marginal. Credibility gains from the deep done well are large.
- **Option D (split v4.0/v4.1)** — kept in mind as a graceful degradation target, not chosen upfront. If the W4 calibration gate fails, Option B collapses gracefully into something close to Option D (v4.0 ships §1.1 + §1.4 + shallows; §1.5 becomes v4.1 with the calibration dataset already in hand). That flexibility is not available under Option A or C without rewrite.

## Consequences

**Positive**:
- Architecture with provenance is reversible and auditable: any derived artifact can be reproduced from `input_hash` + `engine_version` + `ruleset_version`. Forensic use case credibility increases.
- Asynchronous materialization removes the upload path from the single-worker bottleneck; BUG-007 surface narrows rather than expands.
- Wave 0 closes 6 known pre-existing bugs (user_agent gap, ADR gaps, persist race, cache invalidation gap, program race, XXE parser) that would otherwise compound.
- Calibration gate produces a publishable methodology note (AACE MIP-cite-able) whether the gate passes or not.
- `lifecycle_health.py` as an isolated package is ready for any future packaging decision without rework.
- `PRIVACY.md` closes the data-handling disclosure gap before the first enterprise conversation.

**Negative**:
- Wave 0 adds ~0.5–1 wave of up-front cost that does not ship user-visible features.
- Calibration against the sandbox risks overfitting to the sandbox's distribution (confidential, BR-heavy). Community calibration issue is the hedge; no guarantee it succeeds in time.
- Asynchronous materialization introduces a new operational surface (`computing` state, backfill worker). Support burden rises modestly.
- The fallback branch (W5–W6 carry-over P3 instead of §1.5) is a pre-committed graceful degradation, but it does trade the differentiation story for tail-debt payment. Marketing narrative for v4.0 changes materially between the two branches.

**Neutral**:
- Shallow #1 and shallow #2 can run in parallel to the deep once their Wave 0 prerequisites are in place.
- The decision to keep `lifecycle_health.py` as an isolated package does not commit to dual-licensing. That decision is explicitly deferred and requires its own ADR if ever taken.

## Links

- Related planning memory: `project_v40_planning.md`, `project_v40_cycle_1.md`
- Related ADRs: 0006 (plugin architecture), 0007 (WebSocket progress), 0008 (MCP HTTP/SSE) — all backfilled in the same cycle
- Anticipated ADRs authored during Cycle 1: ADR-0010 (lifecycle engine methodology, if W4 gate passes), ADR-0011 (fuzzy-match dep category)
- Deferred ADRs: dual-licensing of `lifecycle_health.py`, multi-discipline security (§1.8, candidate for Cycle 2 or 3 deep), ERP connectors (§1.9, candidate for Cycle 3)
- Community hook: public GitHub issue "Calibration dataset contributions wanted — phase-aware analytics" (opens Wave 4)

---

## Amendment 1 (2026-04-19) — Wave 4 calibration protocol pre-registration

**Status:** accepted — pre-registered before any calibration runs, so operator discretion cannot inflate the gate post-hoc. Amends §"Wave 4" and §"Gate criteria" bullets above (which remain unedited per append-only decision-log discipline; the inline *[AMENDED: see Amendment 1]* pointers delegate authority to this section).

**Trigger.** Wave 4 opened with a dataset integrity check that surfaced three findings invalidating the assumptions the original §"Wave 4" encoded. Pre-registration of the revised protocol is required so the gate remains falsifiable.

### Findings

**1. Sandbox recovered to n=103 unique (not 105, not 5, not 23).** The 105-XER sandbox was thought lost after an earlier off-CI cleanup deleted all but 5 files. Recursive extraction of the surviving source zips (`04-Schedule.zip`, `07-Reporting.zip`) produced 106 XERs in staging; sha256 content-hash deduplication (eight near-duplicates collapsed) yielded **103 unique-hash XERs + 5 unique XMLs** at the canonical off-Git path (see `reference_sandbox_dataset.md`, updated 2026-04-19). The 5 XMLs are plausible MSP-XML / P6-XML exports; they are not part of the lifecycle_phase inference corpus but feed the `src/parser/msp_reader.py` surface when §1.6 first-class MSP surfacing ships.

**2. Prod operational darkness closed, not open.** Before the first Wave 2 backfill invocation on 2026-04-19, `schedule_derived_artifacts` in prod was empty across 24 `ready` projects despite the cycle log marking W2 and W3 "APPLIED TO PROD". The DDL was applied; the backfill worker had never been triggered. The first invocation surfaced a P1 bug at the store boundary (engine payloads containing `datetime` objects were passed to Supabase PostgREST which uses httpx + stdlib `json`, raising `TypeError: Object of type datetime is not JSON serializable`) that flipped every touched project to `status='failed'` per ADR-0015 §7 without writing artifacts. All 21 affected projects were restored to `ready` before the bug fix ran; the fix landed as commit `d0df3e3` ("fix(store): datetime-safe payload serialization in save_derived_artifact") with a regression test asserting `json.dumps` of the saved row. Re-run produced `ok=21 failed=0` and 88 artifact rows (22 projects × 4 kinds — CPM / DCMA / health / lifecycle_phase_inference). Two projects with null/empty `storage_path` remain intentionally un-materializable (upload orphans; §"Wave 2" orphan-guard path took effect as designed). Devils-advocate pre-check P1#5 — ADR-0010 authorship blocked on prod darkness — is **closed**.

**3. First empirical phase distribution of the W3 engine (22 prod projects, not the sandbox).**

| Phase | Confidence band | Count | % |
|---|---|---|---|
| `unknown` | 0.00 (engine emits when signal absent) | 17 | 77% |
| `construction` | 0.74–0.77 (ceiling 0.85 at `lifecycle_phase.py:263`) | 4 | 18% |
| `design` | 0.40 | 1 | 5% |

Under the original §"Gate criteria" wording "≥70% classified at confidence ≥0.80", the empirical pass rate on prod is **0 of 22 (0%)**. The engine is conservative by construction — a forensic-defensibility asset under AACE RP 29R §5 — but the 0.80 bar cannot be cleared even by the highest-confidence band the current rule cascade is capable of emitting. Devils-advocate pre-check P1#2 (construction-rule rubber-stamp risk) inverts: the concern was an over-confident engine; the empirical concern is the opposite.

### Amendments

**A. Dataset split strategy — pre-registered before engine runs.** The 103 XERs include serial updates of the same program (e.g. "UP 03 / UP 04 / UP 05"). Serial updates are **not** independent classification observations (confirms devils-advocate W3 end-of-wave P1#3 selection-effect concern).

- **Gate subset (n≈23):** dedup by program using this **pre-registered rule**, applied mechanically in `scripts/calibration/run_w4_calibration.py` before any engine output is observed:
  > For each program group, keep the revision with the **largest `activity_count`**. Tie-broken by **most-recent `data_date`**. Top-level standalone XERs (no sibling revisions) each count as their own program.
  The candidate list MUST be emitted and committed (as a hash-only manifest, no filenames) before the gate runs.
- **Hysteresis subset (n≈80):** the remaining serial updates, preserved with program-level grouping. The calibration emits a flip-flop-frequency report across consecutive revisions per program — addresses devils-advocate W3 end-of-wave P2#8 ("can't test hysteresis on the same dataset we gate on").

**B. Unknown-phase denominator convention.** `unknown` artifacts count toward the primary-gate **denominator** but cannot contribute to the **numerator** (confidence 0.0 < any positive threshold). This closes devils-advocate W3 end-of-wave P1#1 (denominator ambiguity post-hoc).

**C. Phase-distribution sub-gate.** No single phase may account for more than **60% of the numerator passes**. If 15 of 17 passes are `construction`, the gate fails regardless of the raw ratio. Reframes the gate from "does the engine emit confidence" to "does the engine discriminate" (devils-advocate W3 end-of-wave P1#2).

**D. Confidence-honesty sub-gate (carried forward).** ≥20% of the gate subset must receive confidence <0.5. Prevents over-confident engine from rubber-stamping; devils-advocate W3 end-of-wave P1#4 — original formulation preserved.

**E. Primary threshold — retained formally, recorded at three bands.** The original "≥70% at ≥0.80 confidence" threshold is retained as pre-registered. The calibration MUST ALSO record the pass rate at 0.70 and 0.60 bands in the same run, so the Chairman synthesis can select the effective threshold with evidence rather than post-hoc rationalisation. Any threshold adjustment below 0.80 lands as **a new ADR that cites this Amendment**, not as an edit to this text.

**F. Publication scope — coarse-banded aggregates only.** Public GitHub issue publishes a phase histogram, a confidence histogram bucketed at `[0.0, 0.5, 0.7, 0.8, 1.0]`, and the gate pass/fail boolean per sub-gate. Per-project rows, the 23-program mapping, and the per-observation confusion matrix stay in `meridianiq-private/calibration/cycle1-w4/`. Rationale: legal-and-accountability council synthesis (2026-04-18) flagged re-identification risk on small-n derived statistics through pattern uniqueness (GDPR Recital 26 singling-out analog; LGPD Art.5 VI anonimização) as MEDIUM-HIGH at n=23.

**G. Filename leakage guard — harness contract.** `scripts/calibration/run_w4_calibration.py` MUST read the XER directory via the `XER_SANDBOX_DIR` environment variable. No hardcoded path; no committed file may reference a real project identifier. `/tmp/w4_calibration*.json` goes in `.gitignore`. Any calibration artefact landing in the repo outside `docs/adr/` or `meridianiq-private/` submodule is a governance violation under `feedback_confidentiality.md`.

**H. Execution ordering.** The Wave 4 open-sequence:

1. Commit this Amendment as the **pre-registration artifact** (this commit).
2. Ship the harness + filename guard + `.gitignore` entry (Task #2).
3. Run the calibration off-CI against `XER_SANDBOX_DIR` (Task #5).
4. Land outcome as **Amendment 2** on this file + a committed `docs/adr/0009-w4-outcome.md` calibration_result sibling, recording (phase histogram, confidence histogram, gate pass/fail per sub-gate) in coarse-banded form (Task #6).
5. Branch W5/W6 scope per the three distinct outcomes documented in (J) below.
6. Open the public GitHub issue only after (4) — framing depends on (5) (Task #4).

**I. Chairman synthesis (anonymised, 2026-04-18 pre-check round).** Product-validator + legal-and-accountability + devils-advocate converged on:

- Stratified sampling (AACE RP 114R §4) at ≥10/phase × 6 phases is achievable on n=103 but is **not the right gate for the dedup'd n≈23 subset** — acknowledged as a sample-size constraint, not a protocol weakness. Amendment accepts the constraint and handles it with (A) split strategy + (B)(C) sub-gates.
- Cohen's κ on n≈5 inter-rater subset has CI width ≈ ±0.35; report κ with explicit CI, never a point estimate. W4 executes this discipline.
- Forensic defensibility bar under AACE RP 29R §5 is sample-representativeness + method-reproducibility, not sample-size alone. The pre-registered dedup rule + the denominator convention + the phase-distribution sub-gate together address both.
- Prod darkness (finding 2 above) was a **separate P1** that had to close before ADR-0010 could be authored; it is now closed.

**J. W5/W6 branch decision — three distinct outcomes recorded honestly in Amendment 2.**

- **Gate passes at ≥0.80 pre-registered threshold** → W5/W6 ships `lifecycle_health.py` per §"Wave 5–6 (conditional)"; ADR-0010 is authored citing this Amendment.
- **Gate fails at 0.80 but passes at a lower band (0.70 / 0.60) AND phase-distribution sub-gate passes** → a new ADR (0017 or next available) proposes the lowered threshold with the evidence; ADR-0010 either follows with the lowered threshold or defers to v4.1. Does not silently amend this ADR.
- **Gate not meaningfully runnable (e.g., >90% `unknown` on the dedup'd subset mirrors prod's 77%)** → pre-committed fallback branch: W5/W6 delivers carry-over P3 items (`progress_callback` wiring + Svelte WS composable). Chairman synthesis records "gate not meaningful" distinctly from "gate failed" — the former is an **engine-signal finding**, the latter is a classifier-performance finding. ADR-0010 stays unused in both sub-cases.

This three-way distinction is load-bearing: an external forensic reviewer must be able to tell, from the committed record, whether the engine discriminated-but-underperformed versus did-not-discriminate-at-all. Devils-advocate W3 end-of-wave P3#12 absorbed — gate-unrun vs gate-failed is now separable in the log.

### Rejected alternatives

- **Silently rewrite §Wave 4 / §Gate criteria bullets above.** Rejected — destroys decision-log append-only integrity. Inline `[AMENDED]` pointers plus this Amendment is the honest discipline (precedent: ADR-0014 header "amended by ADR-0015").
- **New ADR-0017 that supersedes §Wave 4 of ADR-0009.** Rejected — the chosen option (B) has not changed; only the input dataset and the empirically-observed engine distribution have. A superseding ADR would overstate the delta. Amendment in place with explicit header + pointer is proportionate.
- **Lower the primary threshold silently to 0.70 before running.** Rejected — post-hoc threshold adjustment is the exact failure mode devils-advocate P1#4 anticipated. Threshold stays at 0.80 for the pre-registered gate; Amendment 2 (post-calibration) may propose a lowered threshold in a distinct new ADR if evidence warrants.
- **Skip the hysteresis subset.** Rejected — absorbing devils-advocate W3 P2#8 costs nothing and produces falsifiable evidence for a claim ADR-0016 currently punts ("hysteresis deferred to W4+ because no calibration data"). The data exists; compute the answer.

---

## Amendment 2 (2026-04-19) — Wave 4 outcome + pre-committed fallback activated

**Status:** accepted — Wave 4 calibration ran 2026-04-19 against the Amendment 1 pre-registered protocol. The gate fails at every pre-registered threshold. Per ADR-0009 §"Wave 5–6 (conditional branch) — If gate fails", the pre-committed fallback branch is activated. ADR-0010 stays reserved. Companion record: `docs/adr/0009-w4-outcome.md`.

### Outcome — fourth scenario, not pre-registered

Amendment 1 §J anticipated three outcomes. The calibration produced a fourth: the engine runs meaningfully (99% non-`unknown` on n=96 gate subset) but fails every pre-registered threshold for different sub-gate reasons.

| Threshold | Primary pass (≥70%) | Phase-dist (≤60%) | Honesty (≥20% <0.5) | Overall |
|---|---|---|---|---|
| 0.80 | FAIL (10.4%, 10/96) | PASS (50.0%) | FAIL (19.8% — 0.2pp tie) | FAIL |
| 0.70 | PASS (74.0%, 71/96) | FAIL (84.5%) | FAIL (19.8%) | FAIL |
| 0.60 | PASS (80.2%, 77/96) | FAIL (77.9%) | FAIL (19.8%) | FAIL |

Interpretation: the engine is a reliable **construction-vs-non-construction detector**. The `meaningful_actuals_mid_progress` rule at `lifecycle_phase.py:258-264` supplies the bulk of classifications at confidence 0.74-0.77 — below 0.80 primary gate, but well above 0.60/0.70 lower bands — and those classifications cluster on `construction`, tripping the phase-distribution sub-gate whenever the primary pass-rate is cleared. Devils-advocate W3 end-of-wave P1#2 anticipated this exact failure mode; evidence confirms. Amendment 1 §C sub-gate (no single phase > 60% of numerator) did its job — caught the rubber-stamp behaviour that the primary metric alone would have masked.

### Positive findings

- **Hysteresis excellent (Amendment 1 §A hysteresis subset):** 4 multi-revision programs, **0 phase flips**, 1 confidence-band flip across a 0.5 edge. Engine is stable across consecutive serial updates — a forensic-defensibility asset that closes devils-advocate W3 end-of-wave P2#8 as positive empirical evidence rather than deferred conjecture.
- **99% classification coverage on real-schedule input.** Unlike prod's 77% `unknown` (22 projects, mostly sparse pre-launch test uploads), the sandbox showed 1% `unknown`. Rich-signal schedules get classified; the engine's reluctance in prod is a signal-sparsity concern, not an engine defect.
- **Prod operational darkness closed as collateral** (Amendment 1 Finding #2). Backfill CLI run + datetime-serialization P1 bug fix + 22-project re-materialization = 88 derived-artifact rows in prod where there had been zero.

### W5/W6 branch — pre-committed fallback (path A)

Per ADR-0009 §"Wave 5–6 (conditional branch) — If gate fails" and Amendment 1 §J scenario #3 re-interpreted (gate failed on empirical evidence, not on being-never-run):

- **W5/W6 delivers the P3 carry-over from v3.9:**
  - `progress_callback` wiring in `src/analytics/evolution_optimizer.py` plus the heavy report generators that share the wave-10 pattern.
  - Svelte composable for the WebSocket progress bar, wired to the risk-simulation page.
- **ADR-0010 stays reserved.** No `lifecycle_health.py` authorship this cycle. If a future cycle revisits lifecycle intelligence with a ruleset v2 (or a narrower construction-detector engine), it authors a new ADR citing this Amendment rather than reclaiming 0010.
- **Engine v1 remains in prod as an informative label surface.** UI card continues rendering phase + confidence band per ADR-0016. The Cost Engineer override + sticky lock remains the final answer for users who disagree. Engine version / ruleset version are NOT bumped; no `mark_stale` chain is triggered. Existing 22 prod artifacts remain valid.
- **Honest framing in user-visible copy.** README, public issue, UI help text document the label as a "preliminary phase indicator" — the `construction` label means "this schedule has the shape of active construction progress"; other labels are best-effort hints whose reliability the calibration did not establish at 0.80. Forensic use case (Consultant / Claims SME persona) MUST treat the label as a hypothesis to verify, not a derivative to cite.

### Rejected alternatives at Amendment 2 (deliberately catalogued — legitimate v4.1+ paths)

- **B. Ruleset v2 with tuned thresholds.** Defensible and evidence-backed — the calibration data is exactly what a v2 design would need. Out of Cycle 1 scope; forcing it into W5/W6 adds a wave and delays v4.0. Preserved as a v4.1 candidate; the data in `meridianiq-private/calibration/cycle1-w4/` is the starting point.
- **C. Binary construction-detector shipped now + 5+1 full classifier behind a preview flag.** Architecturally the cleanest answer to what the engine actually is — the calibration proved it's a construction detector. Rejected here because it requires a UI split (two surface labels instead of one) and documentation updates beyond W5/W6 fallback scope. Cost Engineer persona already has override authority over the single label; the binary split does not add persona value proportional to the work in this cycle. Kept explicitly in this Amendment as a legitimate v4.1 option — the maintainer's first preference at Amendment 2 synthesis was C; the decision to ship A was a Chairman recommendation, accepted by the maintainer on the argument that A is pre-committed discipline plus W5/W6 closes real v3.9 tail debt.

### Cycle 1 closure

Wave 4 done. Wave 5/6 opens with the P3 carry-over deliverables. Cycle 1 concludes with v4.0 shipping:
- Lifecycle phase label surface (ADR-0016 shipped at W3, validated as construction-detector at W4).
- Materialization pipeline (ADR-0015 shipped W2, operationally validated post-W4 via the backfill CLI).
- Provenance chain (ADR-0014 shipped W1, enforces forensic reproducibility for every derived artifact).
- WebSocket progress hardening (ADR-0013, shipped W0).
- Governance artefacts: PRIVACY.md, Amendments 1 + 2, backfill CLI, pre-registered calibration harness.

**No** lifecycle_health.py, no phase-aware analytics beyond the W3 label, no ADR-0010. That deferral is explicit per this Amendment and is the correct outcome of the pre-registered gate discipline — not a scope concession.
