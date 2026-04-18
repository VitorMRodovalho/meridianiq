# 0009. Cycle 1 v4.0 — Lifecycle Intelligence on Materialized Analytics (with pre-committed fallback)

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-18
* Council review: product-validator, strategist, legal-and-accountability, devils-advocate (see `project_v40_cycle_1.md` for anonymised synthesis)

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
- Migration 022: `schedule_derived_artifacts` table with provenance columns (`engine_version`, `ruleset_version`, `input_hash`, `inferred_at`, `computed_at`, `is_stale`), `ON DELETE CASCADE` on `project_id`, and RLS triplet mirroring migration 018 pattern (no `WITH CHECK (TRUE)` — policy must re-verify project ownership).
- Audit: every materialization writes one `audit_log` row with `action = 'materialize'`.

**Wave 2 (deep — async materialization pipeline):**
- Hook post-parse in `upload.py` publishes a materialization job; materialization runs as a background task (arq or asyncio-Task with a bounded pool); upload returns `202 Accepted` with `job_id` immediately.
- Frontend shows `ready / computing / stale` state on project cards and analysis views.
- Backfill strategy: an off-peak worker job re-materializes existing projects; reads fall back to "compute-and-persist-then-return" on cache miss during the backfill window.

**Wave 3 (deep — lifecycle phase metadata):**
- `lifecycle_phase` enum + nullable column on `schedule_versions`.
- Inference heuristic (data_date vs plan_start/plan_end ratio + physical %-complete + S-curve shape) with a confidence score exposed in the UI, not just a label.
- Manual override with audit trail in a separate `lifecycle_override_log` table (append-only by convention, no DELETE policy).

**Wave 4 (deep — calibration + gate):**
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
- `PRIVACY.md` — non-binding factual data-handling disclosure (Supabase region, what is materialized, retention default, deletion path). Published alongside migration 022.

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
