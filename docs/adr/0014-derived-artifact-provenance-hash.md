# 0014. Schedule derived-artifact provenance — hash canonicalization and column shape

* Status: accepted — §RLS quadruple rationale (service_role premise) amended by ADR-0015
* Deciders: @VitorMRodovalho
* Date: 2026-04-18
* Council review: `backend-reviewer` (schema correctness, RLS UPDATE gap, partial-index strategy, PG17 `NULLS NOT DISTINCT`); `product-validator` (SCL Protocol 2nd ed §4 chain-of-custody, AACE RP 57R §4.1 effective-date naming, AACE RP 114R Monte Carlo determinism)

## Context and Problem Statement

ADR-0009 Wave 1 specifies `schedule_derived_artifacts` with provenance columns (`engine_version`, `ruleset_version`, `input_hash`, `inferred_at`, `computed_at`, `is_stale`), a uniqueness tuple `(project_id, artifact_kind, engine_version, ruleset_version, input_hash)`, and a migration-018-style RLS triplet. A Wave 1 pre-check by `backend-reviewer` + `product-validator` surfaced three load-bearing gaps in that specification that cannot be deferred without guaranteeing a migration-025 in the next 2-4 weeks:

1. **`input_hash` algorithm is undefined.** "sha256 over the canonical source" does not specify canonicalisation: XER raw bytes? `ParsedSchedule.model_dump_json()` with Python default key ordering? Sorted-keys JSON with what float repr? If engine A and engine B hash differently, reproducibility breaks silently and the forensic use case collapses. The hash is load-bearing for both the identity tuple (uniqueness) and the Consultant/Claims SME persona's re-verification claim under SCL Protocol 2nd ed §4.
2. **Column set is under-specified for the primary forensic persona.** Consultant/Claims SME cannot use a derivative as corroborative forensic evidence without an identifiable actor (`computed_by`). Risk Manager cannot distinguish "input changed" from "ruleset bumped" staleness causes — AACE RP 114R Monte Carlo determinism depends on it (re-run mandatory vs judgment call). Cost Engineer needs "effective date" (the `data_date` this artifact speaks to) explicit per AACE RP 57R §4.1 — the ADR-0009 name `inferred_at` is linguistically ambiguous and collides with the W3 `lifecycle_phase` inference vocabulary.
3. **RLS triplet omits UPDATE.** `mark_stale(project_id)` flips `is_stale=true` on every artifact; under the `authenticated` role (MCP plugin path per ADR-0006; any future user-triggered "force recompute" button), PostgREST silently returns `[]` with HTTP 200 when no UPDATE policy exists — the exact silent-no-op pattern ADR-0012 amendment #2 flagged as a P1.

A fourth concern from the Cycle 1 opening council (`devils-advocate` P1#7 — multi-project XER `task_id` vs `task_id_key` collision in `src/analytics/cpm.py:144` vs `src/parser/xer_reader.py:398`) is resolved by this ADR's hash-input scoping rule: hashing a project-scoped slice of `ParsedSchedule` makes cross-project `task_id` collisions structurally impossible to perturb the hash.

## Decision Drivers

- **Forensic reproducibility is the load-bearing promise of the table.** Any ambiguity in the hash algorithm or missing column (actor / staleness reason / effective date) invalidates that promise at the forensic audit stage.
- **Single-migration surface at Wave 1.** 023 is the only schema migration of Wave 1; any delta that would otherwise land as migration 025 is paid now at the same per-column cost, without the retrofit risk of backfilling rows written by the W2 async materializer between 023 and 025.
- **Conformance with accepted ADRs.** ADR-0009 column list is minimally extensible; ADR-0012 phased-atomicity pattern (option d→c) requires UPDATE policy support for the authenticated-role path to avoid re-introducing the silent-no-op bug.
- **Zero-row migration discipline.** Adding `computed_by`, `stale_reason`, and renaming `inferred_at`→`effective_at` after W2 lands requires a backfill policy for derivatives already materialized. Adding them now, before any row exists, is free.

## Considered Options

1. **Option 1 — Ship ADR-0009 literal.** Six columns as listed, RLS triplet, single composite index. Pros: minimum diff. Cons: hash algorithm undefined; migration 025 inevitable when Consultant/Claims or Risk Manager personas surface the gaps.
2. **Option 2 — Ship ADR-0009 + ADR-0014 extensions (this ADR).** Nine columns (including `computed_by`, `stale_reason`, renamed `effective_at`), RLS quadruple, two partial indices, `UNIQUE NULLS NOT DISTINCT`, canonical-hash helper + documented algorithm.
3. **Option 3 — Ship ADR-0009 + backend extensions only.** Six columns (no `computed_by` / `stale_reason` / rename), RLS quadruple, two partial indices, `NULLS NOT DISTINCT`. Pros: backend-correct. Cons: forensic/determinism gap remains.
4. **Option 4 — Ship ADR-0009 + product extensions only.** Nine columns, RLS triplet, single index. Pros: forensic/determinism-correct. Cons: silent-no-op under authenticated role.

## Decision Outcome

**Chosen: Option 2.** Ship ADR-0009 with the full column / RLS / index / hash-canonicalization extensions below.

### Column shape (9 columns + 2 constraints)

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PRIMARY KEY DEFAULT uuid_generate_v4()` | |
| `project_id` | `UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE` | Load-bearing for ADR-0012 compensating-delete contract. |
| `artifact_kind` | `TEXT NOT NULL CHECK IN ('dcma','health','cpm','float_trends','lifecycle_health')` | `lifecycle_health` included eagerly; W5-6 ships it conditional on gate — future-proofs against `ALTER TABLE DROP CONSTRAINT` at ship time. |
| `payload` | `JSONB NOT NULL` | Bundled per `artifact_kind`; forensic convention documented in the kind-specific producer. |
| `engine_version` | `TEXT NOT NULL` | Source: `src/__about__.py::__version__`. |
| `ruleset_version` | `TEXT NOT NULL` | Per-kind: `dcma-v1`, `health-v1`, etc. Bumped per AACE/DCMA/PMBOK rules change. |
| `input_hash` | `TEXT NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$')` | See hash algorithm below. The CHECK regex is defensive against a future code path emitting an empty string or an incorrectly-shaped value — `NULLS NOT DISTINCT` + bad data would silently collapse distinct analysis runs. |
| `effective_at` | `TIMESTAMPTZ NOT NULL` | Renamed from `inferred_at`. The `data_date` of the underlying schedule that this artifact speaks to. AACE RP 57R §4.1. |
| `computed_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Wall-clock at materialization time. |
| `computed_by` | `UUID REFERENCES auth.users(id) ON DELETE SET NULL` | `NULL` permitted in two cases: (a) system-triggered backfill (W2 engine/ruleset rollover worker); (b) post-user-deletion erasure state (`ON DELETE SET NULL` fires to satisfy LGPD Art. 18 IV / GDPR Art. 17 right-to-erasure while preserving the artifact row as project-derived data). The paired `audit_log.user_id` column retains the original UUID until a separate retention action clears it; SCL Protocol §4 chain-of-custody is preserved within the retention window and cleanly erased outside it. `ON DELETE CASCADE` would wrongly delete the derivative (which is about the project, not the user); `ON DELETE NO ACTION` (default) would break erasure by making user-deletion fail — both rejected. |
| `is_stale` | `BOOLEAN NOT NULL DEFAULT false` | |
| `stale_reason` | `TEXT CHECK IN ('input_changed','engine_upgraded','ruleset_upgraded','manual')` | `NULL` iff `is_stale=false`, enforced by CHECK below. AACE RP 114R Monte Carlo determinism. |
| `UNIQUE NULLS NOT DISTINCT (project_id, artifact_kind, engine_version, ruleset_version, input_hash)` | | Named `uq_artifact_identity`. `NULLS NOT DISTINCT` is defensive against future nullable column addition (PG15+, Supabase runs PG17). |
| `CHECK ((is_stale=false AND stale_reason IS NULL) OR (is_stale=true AND stale_reason IS NOT NULL))` | | Named `chk_stale_reason_consistency`. Prevents inconsistent staleness annotation. |

### RLS quadruple (SELECT / INSERT / UPDATE / DELETE)

All four policies re-verify ownership via `project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())`. No `WITH CHECK (TRUE)` anywhere. UPDATE is load-bearing for `mark_stale` from:

- MCP plugin HTTP surface (ADR-0006) running as `authenticated`.
- Future user-triggered "force recompute" UI path.
- Any third-party `FastMCP` plugin that legitimately re-stales derivatives for its own rules.

Without UPDATE policy, these paths hit the silent-no-op pattern (PostgREST returns `[]` with HTTP 200). ADR-0012 amendment #2 established this as a P1 class, not a defensive rarity.

The W2 async materializer is expected to run under `service_role` (background task, no captured JWT) and therefore bypasses RLS for its own writes — but other paths do not, and the UPDATE policy must exist for the shared-with-frontend path to function honestly.

### Index strategy (two partial indices, not one full)

```sql
CREATE INDEX idx_sda_latest_fresh
    ON public.schedule_derived_artifacts
    (project_id, artifact_kind, computed_at DESC)
    WHERE is_stale = false;

CREATE INDEX idx_sda_project_stale
    ON public.schedule_derived_artifacts
    (project_id)
    WHERE is_stale = true;
```

- `idx_sda_latest_fresh` covers `get_latest_derived_artifact` hot path (latest non-stale per project+kind) with `computed_at DESC` as tail sort key. Partial clause drops stale rows from the index entirely.
- `idx_sda_project_stale` covers program-level freshness aggregation (Program Director JTBD per ADR-0009 persona analysis). Partial clause inverts — only stale rows indexed.

No full-column `is_stale` index; queries always scope by project or project+kind.

### `input_hash` canonical algorithm (forensic contract)

```
input_hash = sha256_hex( canonical_json( project_scoped_parsed_schedule ) )
```

Where:

- **`project_scoped_parsed_schedule`** = the subset of `ParsedSchedule` whose rows carry the given `project_id`. All rows (activities, predecessors, calendars, resources, WBS, UDFs, activity codes, cost accounts, financial periods, task_financials, task_activity_codes, schedule_options) whose `project_id` ≠ target are excluded. This resolves `devils-advocate` P1#7: `task_id` collisions across projects in a single multi-project XER cannot perturb the hash because each project hashes its own slice independently.

- **`canonical_json(obj)`** = UTF-8 bytes of the JSON serialization of `obj` with the following rules:
  - **Object keys:** sorted lexicographically at every nesting level.
  - **Arrays:** in document order (NEVER sorted — `activities[]`, `predecessors[]` order is semantically meaningful; sorting would erase dependency direction).
  - **`str` values:** normalized to Unicode NFC before serialization. Windows-native XER files typically emit NFC; macOS-native files typically emit NFD. Two human-identical project names `"Ação"` (NFC: `A c\u00e7 a\u0303 o`) and `"Ac\u0327ao\u0303"` (NFD: `A c U+0327 a U+0303 o`) MUST hash identically. Silent NFC/NFD divergence would produce two artifacts for one project.
  - **`datetime` values:** `datetime.isoformat(timespec='microseconds')` preserving source naivete (XER datetimes are naive local-project; forcing UTC would require a timezone we don't have).
  - **`float` values:** Python `json.dumps` default behavior (uses `float.__repr__` internally — guarantees round-trip).
  - **`None` / `null`:** JSON `null`.
  - **Separators:** `(",", ":")` — no whitespace.
  - **Non-finite floats** (NaN, +Inf, -Inf): raise `ValueError` (`allow_nan=False`) — a forensic hash over corrupted numeric data would be silently misleading.

- **`sha256_hex`** = `hashlib.sha256(canonical_bytes).hexdigest()`, lowercase 64-char hex string.

### Helper

```python
# src/database/canonical_hash.py
"""Canonical hash for derived-artifact provenance.

See ADR-0014 for algorithm definition. DO NOT change this implementation
without authoring a superseding ADR — changing the algo invalidates every
historical input_hash, which breaks forensic reproducibility.
"""
```

Round-trip regression pins in `tests/test_canonical_hash.py` assert that a fixed `(ParsedSchedule, project_id)` pair produces a fixed sha256 hex digest — across Python minor versions, OS endianness, and json-library versions.

## Rationale

Every extension in this ADR is one column or one policy line; total migration delta is ≤20 lines on top of ADR-0009. Each extension closes a gap that a named persona or accepted standard surfaces:

- `computed_by` — SCL Protocol 2nd ed §4 forensic actor identity.
- `stale_reason` — AACE RP 114R Monte Carlo determinism.
- `effective_at` rename — AACE RP 57R §4.1 effective-date naming hygiene; disambiguates from W3 lifecycle_phase.
- `lifecycle_health` in CHECK — W5-6 conditional ship without `ALTER TABLE DROP CONSTRAINT`.
- RLS UPDATE — ADR-0012 amendment #2 silent-no-op class.
- `NULLS NOT DISTINCT` — PG15+ defensive against future nullable column addition.
- Two partial indices — Program Director JTBD + hot read path, each with its own access pattern.
- Hash canonicalization — the load-bearing forensic contract without which reproducibility claims are void.

The hash algorithm is in a versioned governance document (this ADR) because it is forensic load-bearing. A future change to the algorithm would invalidate all historical `input_hash` values; the signalling channel for such a change is an ADR-0015 (not yet authored) + an explicit `engine_version` bump + a backfill worker that re-materializes every prior artifact with a new hash. Silent algorithm drift is forbidden.

## Rejected alternatives

- **Option 1 (ADR-0009 literal).** Skipped deltas become migration 025 within 2-4 weeks; the hash algorithm undefined is a ticking bomb — any producer engine change silently invalidates reproducibility.
- **Option 3 (backend-only extensions).** Leaves SCL §4 actor-identity and AACE RP 114R determinism gaps open. Consultant/Claims SME and Risk Manager are the two premium personas; shipping 023 without their minimum schema means shipping two waves of tech debt into the table that never has fewer rows.
- **Option 4 (product-only extensions).** Leaves the silent-no-op pattern under the authenticated role unaddressed. ADR-0012 amendment #2 explicitly classifies this as a P1 pattern; re-introducing it would be governance regression.

## Consequences

**Positive:**
- One-migration Wave 1 instead of migration 023+025. No backfill risk for rows W2 writes between.
- `input_hash` is a stable contract; re-materialization tests become byte-exact regression lints.
- Risk Manager Monte Carlo determinism (AACE RP 114R) is first-class in the schema, not ad-hoc.
- Consultant/Claims SME forensic reproducibility (SCL §4) is first-class via `computed_by` + audit_log row redundancy — redundant-by-design is the correct choice for forensic data.
- `devils-advocate` P1#7 (multi-project XER `task_id` collision) resolved structurally by project-scoped hash input.
- UPDATE policy closes the silent-no-op class of bug (ADR-0012 amendment #2) proactively for derived artifacts.

**Negative:**
- 3 more columns in the store API surface → 3 more Pydantic fields → 3 more test assertions per round-trip test.
- `canonical_json` implementation is now a public contract — any change requires ADR-0015 + full-table backfill. The burden of canonicalization bugs (e.g., a float precision edge case) is concentrated in one module.
- The `stale_reason` CHECK constraint makes `mark_stale` slightly more verbose at the API surface (caller must pass a reason); the store helper should default to `'input_changed'` on the upload happy-path to keep the common case ergonomic.

**Neutral:**
- `effective_at` rename requires no bootstrap back-compat because the table has zero rows at W1 open.
- `NULLS NOT DISTINCT` syntax requires PG15+; Supabase runs PG17 → safe today.
- The 5-value `artifact_kind` CHECK list includes `lifecycle_health` eagerly; if the W4 calibration gate fails and W5-6 drops `lifecycle_health.py`, the enum value is simply unused — no harm.

## Links

- Parent: ADR-0009 (Cycle 1 v4.0, Wave 1 scope — column list extended by this ADR).
- Related: ADR-0012 (persistence atomicity, amendment #2 silent-no-op pattern drove UPDATE policy decision); ADR-0006 (plugin architecture, authenticated role consumer of `mark_stale`).
- Anticipated successor: ADR-0015 — only if `compute_input_hash` contract ever changes; algorithm drift without an explicit superseding ADR is forbidden by this ADR.
- Code: `src/database/canonical_hash.py` (new helper — forensic contract), `src/database/store.py` (extended API: `save_derived_artifact`, `get_latest_derived_artifact`, `mark_stale`), `supabase/migrations/023_schedule_derived_artifacts.sql` (this ADR's schema).
- Tests: `tests/test_canonical_hash.py` (round-trip + byte-exact regression pins), `tests/test_store_derived_artifacts.py` (round-trip via MockSupabaseStore), `tests/test_schema_fk_cascade.py` (POST_PERSIST_TABLES extension).
- Standards cited: SCL Protocol 2nd ed §4; AACE RP 14R, 29R, 49R, 57R §4.1, 114R; DCMA 14-Point Assessment; PMI-CP MoP audit-ready reporting.
