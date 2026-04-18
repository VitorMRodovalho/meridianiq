# 0012. Schedule persistence atomicity — compensating delete now, status lifecycle later

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-18
* Council review: `backend-reviewer` (pre-check, surfaced option (d) via FK topology audit); `devils-advocate` (P1 flag in Cycle 1 council); see `project_v40_cycle_1.md`

## Context and Problem Statement

ADR-0009 Wave 0 item #3 asked: "harden `_persist_schedule_data` against mid-persist failure" and listed three candidate approaches (transactional RPC, projects-row-last, status-column flip). A `backend-reviewer` pre-check of `src/database/store.py:726-986` surfaced that the prior framing ("pseudo-transaction") was optimistic. The actual code wraps all 13 child-table `_batch_insert` calls in a single `try/except Exception` that **logs a WARNING and swallows** — with an explicit comment justifying this as "the XER binary in Storage serves as fallback; the upload is never blocked by a persistence failure."

Consequence: any mid-persist failure (transient Supabase 5xx, constraint violation, network blip) leaves the `projects` row present and zero-or-some child rows populated, with no exception propagating to the caller. Downstream reads then operate on a silently truncated schedule. The pattern is not pseudo-atomic — it is silent partial-persist by design.

Two further discoveries reshaped the option space:

- **All 13 child tables already FK to `projects(id) ON DELETE CASCADE`.** A single `DELETE FROM projects WHERE id = :project_uuid` is a one-statement compensating action that cleans every partial write. This enables an unlisted fourth option with lower blast radius than any of the three originally considered.
- **`_persist_schedule_data` is about to compose with two larger Cycle 1 pieces**: migration 023 `schedule_derived_artifacts` (Wave 1, per ADR-0014) and the async materialization pipeline (Wave 2). Whatever atomicity contract we pick now must compose with "materialization runs after persist returns, in a background task, flipping state on completion." Any solution that blocks the HTTP path on a transactional boundary that includes materialization collapses into the Fly.io cold-start / 1-CPU problem (BUG-007 precedent).

## Decision Drivers

- **Correctness comes first.** Silent partial-persist is indefensible for a forensic / claims-grade analytics platform; the Consultant SME persona cannot audit a schedule that was truncated at upload time with no record.
- **Blast radius must fit Wave 0.** Wave 0 is 7 items; any one of them exceeding ~half-wave of effort pushes v4.0-proper work past the cycle budget.
- **Composition with Wave 1/2 is non-optional.** A solution that forces re-work at migration 023 or at async materialization time doubles the cost.
- **Do not over-build now what Wave 1/2 naturally requires anyway.** A `status` column (`pending | ready | failed`) is the natural surface for async materialization state. Adding it now, before the materializer exists, pays the read-path audit cost without the benefit. Adding it later, batched with a sibling migration 024 alongside migration 023, pays the same cost once.

## Considered Options

1. **Option (a) — Transactional RPC.** Author a Postgres function that takes the full parse result as JSONB; all 14 inserts (projects + 13 child tables) execute in one server-side transaction; Python side calls via `supabase.rpc()`.
2. **Option (b) — Projects-row-last.** Reorder so children persist first into a staging namespace; `projects` row inserts last and "activates" them. Requires either nullable FKs on 13 tables or a parallel staging schema.
3. **Option (c) — `status` column flip.** Add `status ENUM('pending', 'ready', 'failed')` to `projects`; write `pending` first, run inserts, flip to `ready` on success; read paths filter `WHERE status = 'ready'`.
4. **Option (d) — Compensating DELETE + re-raise.** Wrap the existing insert chain in an outer `try/except`. On failure, issue `DELETE FROM projects WHERE id = :uuid` (cascades via existing FK topology), log at ERROR, then re-raise so the HTTP caller sees a 500. Zero schema change, zero read-path audit.
5. **Option (d→c) — Phased: compensating DELETE in Wave 0; status lifecycle added in Wave 1/2 when migration 022 lands.**

## Decision Outcome

**Chosen: Option (d→c) — phased atomicity.**

**Wave 0 #3 (now):** Implement option (d). Replace the swallow-and-warn with outer `try/except` → compensating `DELETE FROM projects WHERE id = :uuid` → re-raise. Add a helper `_delete(table, filters)` on `SupabaseStore` to keep symmetry with `_insert` / `_batch_insert` / `_select`. Update the existing regression test `test_persistence_failure_does_not_raise` (which asserts the bug) to `test_persistence_failure_raises_and_rolls_back` asserting the new contract: exception propagates, `projects` row is absent afterwards.

**Wave 1/2 (later):** When migration 023 (`schedule_derived_artifacts`, per ADR-0014) lands, a sibling migration 024 adds `status` to `projects` and flips option (d)'s compensating delete into option (c)'s status transition. The 023/024 split keeps each migration semantically atomic: 023 = provenance surface, 024 = state machine + read-path audit. At that point the async materializer is the natural flipping agent: `pending` after upload persist, `ready` when materialization completes, `failed` when compensating cleanup runs. Read-path audit (~40 sites) happens once, at the point where it pays off.

### Rationale

- **(d) closes the P1 today with ~20 lines of code and zero schema churn.** The FK topology was already engineered for this — every child table has `ON DELETE CASCADE` on `project_id`. Adding the compensating delete is spending infrastructure that was already paid for.
- **(c) standalone in Wave 0 pays the read-path audit cost without a current beneficiary.** There is no materializer yet, no async pipeline, no place that would filter on `status='ready'` other than "belt-and-braces". A status column that only means "did persist succeed" is a synchronization variable, not a state machine — (d) expresses the same invariant more cheaply.
- **(a) is incompatible with 50k-activity payloads.** PostgREST defaults to ~1 MB request bodies; a 50k-activity XER serializes to 30–80 MB of JSONB. Raising the limit is an instance-level Supabase change with implications beyond this one RPC, and the RPC would still run synchronously under the HTTP timeout — the exact failure mode Wave 2 exists to avoid.
- **(b) fights the current schema.** All 13 FKs are `NOT NULL`. Making them nullable or building a staging schema is high blast radius for a correctness fix that can be achieved cheaper.
- **Phased commitment is the right granularity for an ADR.** "Compensating delete now" alone would fit in a commit message; the cross-wave commitment to evolve toward (c) is what deserves an ADR, because it touches the public contract (future API responses surfacing `status`) and is cross-referenced by ADR-0009 Wave 1/2.

### Rejected alternatives

- **Option (a)** — size and latency incompatibility with realistic XER payloads and with Wave 2 async pipeline.
- **Option (b)** — schema disruption disproportionate to the correctness win; 13-table nullable-FK or staging scheme touches every analytics read path.
- **Option (c) standalone in Wave 0** — premature; adds a status column and read-path audit cost before the async materializer that would benefit from it exists. Deferred, not rejected.

## Consequences

**Positive**:
- Silent partial-persist failure mode is closed. Callers observe honest 500s on persistence failure instead of apparent-success-with-truncated-data.
- Schema unchanged in Wave 0 — no migration, no RLS review, no backfill.
- FK `ON DELETE CASCADE` infrastructure (migration 018) now delivers end-to-end atomicity, which is what it was intended for.
- Read-path audit is deferred to when it pays off (Wave 1/2), not duplicated.

**Negative**:
- Compensating DELETE is not atomic with the original inserts — a narrow race window exists where concurrent RLS-governed reads see partial data before the DELETE fires. Observable only under concurrent access to the same `project_id`, which the upload flow's upload-id-keyed path effectively prevents.
- If the compensating DELETE itself fails (Supabase 5xx during cleanup), the partial data remains. Logged at ERROR with both exceptions; a future reaper job or the Wave 1/2 status column will provide the recovery path. Acceptable residual risk for Wave 0.
- Storage XER blob is not removed — it is the parse-source-of-truth and its retention is governed separately (upload-id-keyed). Out of scope for atomicity.
- The existing test `test_persistence_failure_does_not_raise` (line 357 of `tests/test_store_persistence.py`) is replaced, not deleted. The renamed test asserts the inverted contract. Anyone relying on the old contract (none expected — it was a bug) will see a test failure at upgrade.

**Neutral**:
- Callers that previously ignored persist failures (because the warning was silent) now must handle exceptions. In practice the only caller is `save_project` at `src/database/store.py:722`, which runs inside the upload router and was already expected to propagate errors as 500s — the swallow was a design bug, not a design choice.
- The eventual `status` column rollout (Wave 1/2) will also require an ADR amendment or a superseding ADR, depending on how far the scope expands (e.g., whether it becomes the async materialization state machine or stays a persist-only flag).

## Links

- Supersedes-in-spirit: nothing — this is the first ADR on persistence atomicity.
- Related ADR: ADR-0009 (Cycle 1 v4.0, Wave 0 item #3).
- Anticipated follow-up: ADR amendment or successor when Wave 1/2 adds the `status` column and flips to (c).
- Code: `src/database/store.py:726-986` (method), `src/database/store.py:581-592` (helpers), `supabase/migrations/018_schedule_persistence.sql` (FK topology).
- Test: `tests/test_store_persistence.py` — replaced old swallow test, added rollback + silent-no-op + storage-blob-cleanup coverage.
- Schema guard: `tests/test_schema_fk_cascade.py` — lint-over-migration-SQL that fails CI if any FK to `projects(id)` lacks `ON DELETE CASCADE` (answers the devils-advocate concern about future child tables silently reintroducing partial-persist).

## Amendment — P1 red-team responses (same-day, 2026-04-18)

A `devils-advocate` review after the initial patch surfaced three P1 holes that the original draft dismissed as out of scope. The amendment below describes the fixes merged before the ADR was finalised; it is part of the accepted decision, not a deferred follow-up.

1. **Orphan XER blob in Storage.** The XER binary is uploaded to the Storage bucket by `save_project` *before* `_persist_schedule_data` runs. A compensating DELETE on the `projects` row leaves the blob unreachable by any query (no row carries its `storage_path` anymore), where it continues to hold confidential schedule content and accrue cost. **Fix:** the compensating `except` clause now reads `projects.storage_path` *before* the DELETE, then calls `self._client.storage.from_(self.BUCKET).remove([storage_path])` *after* the DELETE succeeds. Blob cleanup is best-effort: a failure is logged at WARNING; the original persist exception still propagates.

2. **RLS silent no-op on DELETE.** PostgREST returns `[]` with HTTP 200 when RLS denies a DELETE or when the target row does not exist — no exception raised. The original `_delete` helper discarded the result, so a policy misconfiguration would make the compensating DELETE a silent no-op and leave the P1 behaviour unchanged, only quieter. **Fix:** `_delete` now returns the list of deleted rows. The compensating block inspects the length; zero-affected-rows is logged at WARNING with an explicit "RLS denial, already gone, or FK topology missing CASCADE" hint so operators can reconcile. The backend uses the `service_role` key which bypasses RLS, so under normal operation this is defensive; the hint is for the degraded-auth path.

3. **No CI guard on CASCADE coverage for future child tables.** The whole rollback depends on every table that FKs into `projects(id)` declaring `ON DELETE CASCADE`. Migrations 001 and 018 honour this, but nothing prevents a future migration from adding a 14th child table that forgets the clause — silently reintroducing partial-persist. **Fix:** a new migration-SQL lint test `tests/test_schema_fk_cascade.py` parses every file under `supabase/migrations/` with a regex and fails CI if any `REFERENCES projects(id)` appears without a matching `ON DELETE CASCADE` in the same constraint clause.

Residual issues acknowledged but explicitly deferred to Wave 1/2 (where they compose naturally with the `status` column + async materializer):

- Mock-theater: `MockSupabaseStore._delete` models the projects DELETE and blob cleanup but does **not** emulate Postgres FK cascade on a real connection. Integration coverage against a live Supabase instance is a Wave 1/2 ADR-successor concern. The CASCADE-schema lint test (#3) is the cheap static partial-mitigation.
- Pooler timeout risk on 50k-activity cascade under port-6543 transaction mode.
- `schedule_uploads` orphan left when `projects` is deleted (FK direction is `projects → uploads`, so DELETE on projects does not cascade upward).
- `program_id` / `revision_number` autolink at `save_project:699-706` runs before persist and is not rolled back; a failed upload can leave a program row with no projects attached. Cosmetic; ticket for Wave 1/2.
