# 0016. Lifecycle phase inference, override log, and lock-flag (W3 of Cycle 1 v4.0)

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-18
* Council review: `product-validator` + `backend-reviewer` + `frontend-ux-reviewer` (Wave 3 pre-check); `devils-advocate` scheduled for end-of-wave close

## Context and Problem Statement

ADR-0009 §"Wave 3" specifies three composed deliverables:

1. A `lifecycle_phase` metadata surface keyed per-revision so analytics can be interpreted in the right phase context.
2. An inference heuristic over `(data_date, plan_start, plan_end, phys_complete distribution, S-curve shape, baseline availability)` with a confidence score exposed in the UI as a numeric value (NOT just a label).
3. A manual override with an append-only audit trail in a separate `lifecycle_override_log` table.

The Wave 3 pre-check council surfaced four design decisions that ADR-0009 left intentionally open and a fifth premise that the bootstrap proposed but the council rejected on data-model grounds:

- **Schema surface (a / b / c).** The bootstrap listed three options. Option (a) — `schedule_versions.lifecycle_phase` — is dead on arrival because no `schedule_versions` table exists today; the `projects` table is the per-revision surface (each upload creates a new `projects` row; `programs` groups revisions of the same schedule). Option (b) adds a column to `projects`. Option (c) adds a dedicated `lifecycle_phase_assignments` table.
- **Phase taxonomy.** ADR-0009 listed 9 phases (initiation, planning, design, procurement, construction_early/mid/late, commissioning, closeout). The W4 calibration gate is "≥70% of 105 sandbox XERs at confidence ≥0.80". A 9-value classifier with the available signal density (one snapshot, no history at W3) cannot credibly distinguish construction sub-phases — the gate would collapse.
- **Override-log table shape.** Whether to keep `lifecycle_override_log` as a dedicated table or collapse it into a generic `lifecycle_phase_assignments` table that uses a `source ∈ {inferred, overridden, erp_synced}` discriminator.
- **Cost Engineer override stickiness.** ADR-0009 did not address whether subsequent uploads should re-infer over a manual override. The Cost Engineer JTBD requires sticky overrides until the user explicitly reverts.
- **ADR numbering.** The bootstrap referenced "ADR-0010" for this decision; ADR-0010 was reserved by ADR-0009 for the W5/W6 conditional `lifecycle_health.py` deep engine methodology — a distinct, larger concern that should not be coupled to the W3 lightweight label inference.

## Decision Drivers

- **The W4 gate is binding.** Any choice that makes "≥70% at ≥80% confidence on the 105-XER sandbox" unachievable is wrong even if it scores high on every other axis. A 9-value classifier with high overlap between adjacent buckets fails this constraint.
- **ADR-0014 forensic contract is the established surface for derived-artifact provenance.** Anything that bypasses it for an "inference" payload duplicates infrastructure (`engine_version`, `ruleset_version`, `input_hash`, `effective_at`, `computed_by`, `mark_stale`) and creates two parallel sources of truth.
- **ADR-0015 materialization runtime contract must not be re-opened.** The `_persist_schedule_data → status='ready'` flip and the stale-race re-hash protection were just shipped; W3 must compose with them, not amend them.
- **Append-only forensic audit trail under SCL §4 is non-negotiable for the override log.** The discipline that distinguishes an inferred phase from a manual override is the chain-of-custody that survives litigation. RLS-level no-UPDATE / no-DELETE is the operational expression of that discipline.
- **Cost Engineer JTBD (ERP as source-of-truth) requires sticky overrides.** Without a lock, every subsequent upload silently re-infers and competes with the user's authoritative decision — a UX antipattern that will train users to distrust the inference entirely.
- **Pareto wave-of-attack: order, don't exclude.** W3 ships a small surface that the W4 calibration gate can stress-test. Refinements (hysteresis, confidence band tuning, ERP-sync, multi-project rollup, dual-licensing of the engine) are deferred to W4+ and W5/W6 with explicit triggers.

## Considered Options

### Schema surface

1. **Option B — `projects.lifecycle_phase` columns.** Add `lifecycle_phase TEXT`, `lifecycle_phase_confidence NUMERIC`, `lifecycle_phase_inferred_at TIMESTAMPTZ` to `projects`. Single row per upload; simplest read path.
2. **Option C-standalone — dedicated `lifecycle_phase_assignments` table.** New table with FK to `projects`, plus `lifecycle_override_log` separate. Clean semantics; duplicates the 9-column ADR-0014 shape.
3. **Option C-piggyback — reuse `schedule_derived_artifacts` with a new `artifact_kind`.** Migration 025 ALTERs the CHECK list to add `'lifecycle_phase_inference'`. Inference output rides the existing forensic contract; no new table for the inference itself; `lifecycle_override_log` lives separately because it carries user intent (different access pattern, append-only RLS).

### Phase taxonomy

1. **Taxonomy 9 (bootstrap)** — `{initiation, planning, design, procurement, construction_early/mid/late, commissioning, closeout}`.
2. **Taxonomy 5+unknown** — `{planning, design, procurement, construction, closeout, unknown}`.

### Override log shape

1. **Generic `lifecycle_phase_assignments`** with `source` discriminator. Single table for inference + override + future ERP-sync rows.
2. **Dedicated `lifecycle_override_log`** + reuse `schedule_derived_artifacts` for inferences. Two tables, each with one job; append-only RLS only on the override side.

### Cost Engineer stickiness

1. **No lock.** Materializer always re-infers on subsequent uploads. Override is a one-shot annotation.
2. **`projects.lifecycle_phase_locked` BOOLEAN.** Materializer skips the inference engine when locked. Override flips it to true; explicit revert flips back.

### ADR numbering

1. **Reuse ADR-0010** that was reserved for W5/W6.
2. **New ADR-0016** for W3; keep ADR-0010 reserved.

## Decision Outcome

### 1. Schema — Option C-piggyback + dedicated `lifecycle_override_log` + `projects.lifecycle_phase_locked` flag

- **Inference output** lands as `schedule_derived_artifacts` with `artifact_kind='lifecycle_phase_inference'`. Migration 025 ALTERs the CHECK list (DROP + ADD; PostgreSQL has no `ALTER CHECK`). Reuses ADR-0014's forensic contract: `engine_version`, `ruleset_version`, `input_hash`, `effective_at`, `computed_by`, the partial index `idx_sda_latest_fresh`, the uniqueness tuple `(project_id, artifact_kind, engine_version, ruleset_version, input_hash)`, and the `mark_stale` chain on engine/ruleset version bumps. Zero new infrastructure for the inference side.
- **Override log** is a new table `lifecycle_override_log` with `id UUID PK`, `project_id UUID FK ON DELETE CASCADE`, `inferred_phase TEXT NULL`, `override_phase TEXT NOT NULL`, `override_reason TEXT NOT NULL CHECK (length > 0)`, `overridden_by UUID FK auth.users(id) ON DELETE SET NULL`, `overridden_at TIMESTAMPTZ DEFAULT now()`, `engine_version TEXT NOT NULL`, `ruleset_version TEXT NOT NULL`. RLS quadruple is reduced to a SELECT/INSERT pair — UPDATE and DELETE policies are intentionally omitted. The `engine_version` + `ruleset_version` columns pin which inference algorithm version the user was looking at when they overrode (forensic disambiguation between W3/v1 and any future Wn/v2 override).
- **`projects.lifecycle_phase_locked BOOLEAN NOT NULL DEFAULT false`** flag. Cost Engineer JTBD: when an override exists, the materializer skips the `lifecycle_phase_inference` engine for that project on subsequent uploads. Revert flips it back; the next upload re-emits an inference.

Rejected — Option B (columns on `projects`): fails the ADR-0014 forensic contract (no `input_hash`, no `engine_version`, no `effective_at`, no `mark_stale` chain), and a separate override log would still be needed.

Rejected — Option C-standalone (dedicated `lifecycle_phase_assignments`): duplicates the 9-column ADR-0014 shape, the RLS quadruple, and the partial-index strategy for a row that is semantically "an inference artifact about the schedule".

Rejected — generic assignments table: collapsing inference + override into one table with a `source` discriminator confuses two distinct concerns: a system-emitted artifact under ADR-0014 forensic provenance versus an end-user intent record under SCL §4 audit-trail discipline. Two tables with one job each is the cleaner forensic boundary.

### 2. Taxonomy — 5 phases plus `unknown`

`LifecyclePhase = {planning, design, procurement, construction, closeout, unknown}` (Literal in Python, TEXT + CHECK in DB). The `unknown` value is the explicit guard the engine emits when the input lacks the minimum signal (no `data_date`, no activities, etc.). The materializer persists the `unknown` artifact rather than skipping — the distinction "inference has not run yet" (no artifact) vs "inference ran and could not classify" (artifact with phase=unknown) is load-bearing for the UI empty-state vs failure-state vocabulary.

The construction sub-phase split (`construction_early/mid/late`) is intentionally NOT a phase value in W3. ADR-0009's W5/W6 conditional ships a `lifecycle_health.py` engine if the W4 gate passes; that engine can introduce a *derived dimension* `construction_progress_band ∈ {early, mid, late}` from the phys_complete distribution at that time. Treating the band as a derived dimension rather than a phase value preserves the 5+1 taxonomy under a future expansion.

`initiation` and `commissioning` from the bootstrap's 9-value list are dropped: `initiation` is a PMI concept that pre-dates the schedule existing and rarely surfaces in a P6 XER; `commissioning` is subsumed into `closeout` for most schedules and rarely a distinct P6 phase tag. The dropped values can be reintroduced post-W4 if calibration data shows they carry signal.

Rejected — 9 phases: the W4 gate (`≥70% at ≥80% confidence`) cannot be met with the available signal density. Construction sub-phase distinction needs S-curve history across multiple uploads, not one snapshot.

### 3. Engine isolation — standalone `src/analytics/lifecycle_phase.py` + shared `src/analytics/lifecycle_types.py`

The 45 existing engines in `src/analytics/` have zero cross-imports today (each imports only from `src.parser.models` + stdlib + optional `networkx`). Lifecycle_phase preserves that invariant: the engine module imports only the shared types module. The future W5/W6 `lifecycle_health.py` would import `lifecycle_types` (the shared `LifecyclePhase` Literal + `LifecyclePhaseInference` dataclass) but never `lifecycle_phase` directly — composition happens at the materializer / API layer, not cross-engine. This preserves the ADR-0009 §Rationale promise that `lifecycle_health.py` ships as an isolated package without forcing a future licensing decision.

### 4. Materializer integration — through `_ENGINE_RUNNERS` (not on-demand at read)

The W3 inference engine registers in `_ENGINE_RUNNERS` after CPM and runs as part of the standard async materialization pipeline (ADR-0015). On-demand "compute-and-persist on first GET /lifecycle" was rejected: it violates the W2 "read is cheap" principle, creates a thundering-herd problem when N users open the same project, and the inference cost is O(activities) — trivial compared to DCMA/CPM. Stale-race re-hash from ADR-0015 §4 applies for free.

`_ENGINE_VERSION = "4.0"` (shared constant). `_RULESET_VERSIONS["lifecycle_phase_inference"] = "lifecycle_phase-v1-2026-04"` — bump on threshold tuning, which triggers `mark_stale(reason='ruleset_upgraded')` per ADR-0014 §`stale_reason`.

When `projects.lifecycle_phase_locked = true`, the materializer skips ONLY the `lifecycle_phase_inference` engine; DCMA / health / CPM still run. The runtime publishes an `engine_skipped` progress event with `reason='lifecycle_phase_locked'` so the UI surface is honest about the skip.

### 5. Backfill — `--kind` flag for retroactive lifecycle_phase materialization

Migration 025 lands AFTER W2 has already shipped with the materializer running DCMA / health / CPM for every upload since. The W2 backfill CLI uses `dcma` as a missing-proxy ("if DCMA is fresh we trust the rest") — a logic that breaks for the new `lifecycle_phase_inference` kind because already-materialized projects have fresh DCMA but missing lifecycle_phase. Migration 025 preserves the W2 backfill default (`--kind dcma`) and adds a `--kind` flag so operators can target the specific gap with `python -m src.materializer.backfill --kind lifecycle_phase_inference`. The candidate query also skips locked projects (the materializer would no-op them anyway; skipping at selection avoids per-run reselection noise in the operator logs).

### 6. Override API contract

- `GET /api/v1/projects/{project_id}/lifecycle` — returns `LifecyclePhaseSummary` (latest inference + latest override + locked flag + effective phase + effective confidence + source discriminator).
- `POST /api/v1/projects/{project_id}/lifecycle/override` — writes the override row + flips `lifecycle_phase_locked=true` + writes one `audit_log` row with `action='lifecycle_override'`. Returns 409 when `projects.status='pending'` or when no inference artifact exists yet (BR P1#7 — override-before-inference is almost always user confusion, not forensic). Reason text minimum 10 characters at the API layer (the DB CHECK enforces only `length > 0` so future API policy changes do not require a schema migration).
- `DELETE /api/v1/projects/{project_id}/lifecycle/override` — flips `lifecycle_phase_locked=false`. Does NOT delete history (append-only contract). The existing inference artifact resumes as the authoritative source — no recompute needed.
- `GET /api/v1/projects/{project_id}/lifecycle/overrides` — paginated history (newest first).

### 7. Pending statuses aggregator — single endpoint per user, not per project

`GET /api/v1/projects/pending-statuses` is introduced in W3 to power the sticky `ComputingBanner` without N pollers per N projects (FE pre-check P1). One poll per logged-in user is enough to power both the banner AND the per-project `LifecyclePhaseCard` re-fetch hook (which subscribes to the global `computingProjects` store and triggers a summary reload when the project leaves the pending set). The endpoint excludes terminal `status='ready'` rows; an empty list is the signal to hide the banner.

### 8. ADR numbering — ADR-0016

ADR-0010 stays reserved for the W5/W6 `lifecycle_health.py` engine methodology. The W3 lifecycle phase label inference is a distinct, smaller concern (one engine + one override log + one lock flag) that earns its own ADR. Coupling it to ADR-0010 would conflate the W3 ship-decision with the W5 engine-methodology decision.

### 9. Rationale summary

Each element is the lowest-cost option that satisfies a named persona, an accepted standard, OR a forensic invariant set by an earlier ADR:

- Piggyback on `schedule_derived_artifacts` reuses the ADR-0014 forensic contract instead of duplicating it.
- 5 phases + unknown ships under the W4 gate without overclaiming distinguishability.
- Dedicated `lifecycle_override_log` with append-only RLS keeps the user-intent surface forensically separable from the system-emitted artifact surface (SCL §4).
- `projects.lifecycle_phase_locked` honours the Cost Engineer JTBD without coupling to ERP-sync (which is W4+ scope).
- Materializer integration reuses the ADR-0015 stale-race re-hash and progress channel.
- `--kind` backfill flag is the cheapest path to retroactively materialize for the W2-era ready projects.
- Single aggregate `/pending-statuses` endpoint avoids the per-project poll-storm flagged by frontend-ux-reviewer.
- ADR-0016 separates the W3 ship-decision from the W5 engine-methodology decision still pending behind the W4 gate.

## Rejected alternatives

- **Schema option B (columns on projects)** — fails the ADR-0014 forensic contract; would require a parallel override-log table anyway.
- **Schema option C-standalone (dedicated `lifecycle_phase_assignments`)** — duplicates ADR-0014 infrastructure for negligible benefit.
- **Generic assignments table with `source` discriminator** — collapses inference and override into one table when they have different access patterns (artifact = upsert-on-input-hash, override = strict append) and different RLS contracts (artifact = quadruple, override = SELECT/INSERT only).
- **9-phase taxonomy** — fails the W4 gate. Construction sub-phases need history; we only have one snapshot.
- **No lock flag** — Cost Engineer's manual override would be silently overwritten on every subsequent upload, training users to distrust the inference.
- **On-demand inference at read** — violates W2 "read is cheap" principle, creates thundering-herd risk on the 1-CPU Fly instance.
- **DB trigger for "no UPDATE / no DELETE" enforcement** — would also fire on `service_role`, breaking LGPD `ON DELETE SET NULL` cleanup. RLS no-policy convention is the honest middle.
- **Hysteresis in the engine** — pre-absorbs a problem we have no calibration data for. The engine is stateless per CLAUDE.md `Code Standards`; hysteresis belongs at the materializer layer (which has access to prior artifacts) and ships in W4+ if the sandbox calibration shows real flip-flop frequency.

## Consequences

**Positive:**

- The forensic contract from ADR-0014 carries through to the W3 inference; reproducibility from `(input_hash, engine_version, ruleset_version)` is preserved.
- The 5+1 taxonomy can plausibly satisfy the W4 gate. If sandbox calibration justifies, it can be extended in W4+ (each new phase = one CHECK constraint update + one `LifecyclePhase` Literal addition).
- Cost Engineer's mental model holds: their override sticks until they explicitly revert; the materializer never silently second-guesses them.
- Backfill CLI scales to future artifact kinds via the `--kind` flag — W4/W5 additions don't need new CLI plumbing.
- The single aggregate `/pending-statuses` endpoint scales: 1 user with 100 pending projects = 1 poll per 3s, not 100. The frontend banner + per-project card are decoupled from the polling cost.
- ADR-0010 stays reserved for the W5/W6 engine methodology, preserving optionality.
- The `lifecycle_health` reservation in migration 023's `artifact_kind` CHECK list is untouched — W5/W6 can ship without further migration.

**Negative:**

- Two tables instead of one for the lifecycle concern (`schedule_derived_artifacts` + `lifecycle_override_log`). Cognitive overhead is real but the forensic separation is worth the cost.
- The `projects.lifecycle_phase_locked` flag is a third coordinate (alongside `status` and `lifecycle_phase` derivable from the inference artifact) that consumers must consider when computing the effective phase. The `LifecyclePhaseSummary.source` field collapses this for API consumers but the underlying state surface is more complex than a single column.
- Multi-project XER lifecycle inference is deferred to W3+ (the materializer still picks `schedule.projects[0].proj_id` as the hash scope per ADR-0015 §1). Multi-project XERs in the wild are rare today; if they become common the per-project iteration belongs in the materializer, not in the engine itself.
- The W4 gate criterion may surface that the 5-phase taxonomy is too coarse OR that confidence thresholds are miscalibrated. Either feedback triggers a `RULESET_VERSION` bump and a `mark_stale(reason='ruleset_upgraded')` chain — the cost of which is bounded but real.

**Neutral:**

- The override log carries `engine_version` + `ruleset_version` even though most overrides under the W3 algorithm will all show `4.0` / `lifecycle_phase-v1-2026-04`. The columns become load-bearing as future algorithm versions land; including them now avoids a future ALTER TABLE on a forensic table.
- The `lifecycle_phase_inference` artifact rows ride the `idx_sda_latest_fresh` partial index from migration 023 — no new index needed.
- Hysteresis is not in the engine. If post-W4 calibration shows real flip-flop frequency, hysteresis lands at the materializer layer (which has access to prior artifacts) without touching the engine — the engine stays stateless per `Code Standards`.

## Links

- Parent: ADR-0009 (Cycle 1 v4.0, Wave 3).
- Forensic contract: ADR-0014 (canonical_hash + 9-column shape) — reused.
- Runtime contract: ADR-0015 (async materialization + state machine) — composed with.
- Reservation note: ADR-0010 stays reserved for W5/W6 `lifecycle_health.py` engine methodology (anticipated, conditional on W4 gate).
- Code:
  - `supabase/migrations/025_lifecycle_phase.sql` — CHECK ALTER + `projects.lifecycle_phase_locked` + `lifecycle_override_log` + RLS pair + indices. APPLIED to prod 2026-04-18.
  - `src/analytics/lifecycle_types.py` — `LifecyclePhase` Literal + `LifecyclePhaseInference` dataclass + `confidence_band` helper.
  - `src/analytics/lifecycle_phase.py` — engine. `ENGINE_NAME = 'lifecycle_phase'`, `RULESET_VERSION = 'lifecycle_phase-v1-2026-04'`.
  - `src/database/store.py` — `_VALID_ARTIFACT_KINDS` extension, `set_lifecycle_phase_lock` / `get_lifecycle_phase_lock` / `save_lifecycle_override` / `list_lifecycle_overrides` / `get_latest_lifecycle_override` on both backends.
  - `src/materializer/runtime.py` — `_run_lifecycle_phase` runner registered in `_ENGINE_RUNNERS`; `_lifecycle_phase_locked` lock skip helper; `_RULESET_VERSIONS` extension.
  - `src/materializer/backfill.py` — `--kind` flag + locked-project skip in `_candidate_project_ids`.
  - `src/api/routers/lifecycle.py` — `GET/POST/DELETE/GET history` endpoints.
  - `src/api/routers/projects.py` — `GET /api/v1/projects/pending-statuses` aggregate.
  - `src/api/schemas.py` — Pydantic v2 schemas for the wire surface.
  - `web/src/lib/types.ts` — TypeScript mirror of the wire shapes.
  - `web/src/lib/api.ts` — `getLifecycleSummary` / `postLifecycleOverride` / `deleteLifecycleOverride` / `getLifecycleOverrides` / `getPendingStatuses`.
  - `web/src/lib/stores/computing.ts` — global `computingProjects` store + Visibility-API-aware polling lifecycle.
  - `web/src/lib/composables/useProjectStatusPolling.ts` — Svelte 5 runes wrapper.
  - `web/src/lib/components/ComputingBanner.svelte` — sticky banner below `Breadcrumb`.
  - `web/src/lib/components/LifecyclePhaseCard.svelte` — phase + 4-dot meter + numeric confidence + band + rationale disclosure + override / revert.
  - `web/src/lib/components/LifecycleOverrideDialog.svelte` — modal / bottom-sheet, focus trap, Escape closes, quickpicks + free-text reason.
  - `web/src/lib/components/AnalysisSkeleton.svelte` — `mode: 'loading' | 'materializing'` + optional `progressPct`.
  - `web/src/lib/i18n/{en,pt-BR,es}.ts` — 36 lifecycle.* keys.
- Tests: `tests/test_lifecycle_phase_inference.py` (engine fixtures across 6 phases), `tests/test_lifecycle_override_log.py` (override + lock + materializer skip + backfill --kind).
- Standards cited: AACE RP 14R §3 (planning-phase ownership), ISO 21502 §6.3 (lifecycle as first-class metadata), SCL Protocol 2nd ed §4 (chain-of-custody on the override log), ADR-0014 reproducibility contract.
