# 0015. Async materialization pipeline, `projects.status` state machine, and backfill policy

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-18
* Council review: `product-validator` + `backend-reviewer` + `frontend-ux-reviewer` (Wave 2 pre-check); `devils-advocate` scheduled for end-of-wave close

## Context and Problem Statement

ADR-0009 Wave 2 specifies three composed deliverables:

1. An async materialization pipeline that runs the analysis engines (DCMA, health, CPM, float_trends) in the background after upload, writing rows into `schedule_derived_artifacts` (per ADR-0014).
2. Closure of ADR-0012's phased-atomicity commitment: flip `_persist_schedule_data` from option (d) "compensating DELETE" to option (c) "UPDATE `projects.status = 'failed'`".
3. A `ready / computing / failed / stale` state surface on the frontend, read through from `schedule_derived_artifacts` via a new `projects.status` column plus the existing `is_stale` flag.

The Wave 2 pre-check council surfaced two premises in the Wave 1 ADRs that Wave 2 cannot leave unresolved:

- **ADR-0014 §RLS quadruple rationale describes an "authenticated path" that does not exist in code today.** `src/database/client.py` initialises the Supabase client with `SUPABASE_SERVICE_ROLE_KEY` globally; every HTTP handler already bypasses RLS. The UPDATE policy shipped in migration 023 is forward-compatible with a future authenticated split (MCP plugin HTTP, user-triggered recompute) but it is not load-bearing today. Wave 2 must not pretend otherwise.
- **ADR-0014 P1#6 (devils-advocate) — stale-read race window.** The Wave 2 materializer must detect a newer upload arriving mid-materialization and abort, otherwise it can persist an artifact whose `input_hash` is already obsolete before it hits the table. ADR-0014 deferred the mitigation design to Wave 2; this ADR specifies it.

A third decision is required before any code lands: the runtime for the materializer. `asyncio.Task` inside the FastAPI process, a Redis-backed queue (`arq`), and Celery-style workers each have different ops surface. MeridianIQ runs on a single Fly.io instance with 1 CPU today; the correct choice must match that deployment shape and leave a clean migration path once volume justifies a separate worker fleet.

## Decision Drivers

- **Single-instance Fly.io today, queue-backed in the future.** Any runtime choice that forces a Redis addon or a second worker process now pays ops overhead for a volume that does not exist. Any runtime choice that makes a future migration difficult compounds debt.
- **Upload path must stay under the Fly.io health-check budget.** Synchronous materialization of a 50k-activity XER burns 20–60 CPU-seconds; BUG-007 already documents the cold-start 502 surface. The HTTP request cannot wait for materialization.
- **Forensic contract (ADR-0014) is irrevocable.** The `input_hash` tuple is the forensic identity for every artifact. Any stale-read race that persists an artifact with a hash that no longer matches the current `ParsedSchedule` silently violates the contract; the reproducibility promise breaks.
- **ADR-0012 phased commitment must close, not re-open.** Option (d→c) is an accepted cross-wave pointer. Wave 2 completes the flip in the same migration that adds the `status` column, so there is never a code state where (d) and (c) coexist in HEAD.
- **Admin / owner / BI visibility of `failed`.** SCL Protocol §4 chain-of-custody plus AACE MIP 3.6 audit-ready reporting both require that a materialization incident is visible in every view that enumerates the affected project. Ghost-filtering `failed` rows from reports is forensic-regression.
- **Persona latency expectations vary.** Field Engineer expects sub-5s feedback; Cost Engineer expects cutoff-date completeness; Risk Manager accepts 30–90s for Monte Carlo. The materializer must publish progress (ADR-0013 channel) so the UI can match each persona's mental model.

## Considered Options

### Runtime for the materializer

1. **Runtime A — Synchronous inline.** Upload handler runs engines before returning. Rejected upfront: BUG-007 regression at scale; contradicts ADR-0009 Wave 2 spec.
2. **Runtime B — `asyncio.Task` + `asyncio.Semaphore(1)` + `loop.run_in_executor(ProcessPoolExecutor)`.** Zero new dependency. Runs in-process. Semaphore caps concurrency at 1 (the 1-CPU reality). `ProcessPoolExecutor` isolates engine CPU from the event loop so HTTP handlers stay responsive. Migration path to queue-backed: replace `enqueue()` with queue publish; consumer stays the same.
3. **Runtime C — `arq` (Redis queue).** Isolated worker process. Requires Redis addon (Fly.io Upstash or Supabase-provided). Clean separation of HTTP and worker fleets; scales horizontally. Pays ops overhead today (deploy + health + TLS to Redis) for volume that does not yet justify it.
4. **Runtime D — Celery / RQ.** Larger ecosystem than `arq`, heavier ops footprint. No incremental benefit over C at current scale.

### State machine for `projects.status`

1. **State machine A — `pending` → `ready`**, no explicit `failed`. Failures blow up to HTTP 500 and leave no row. Rejected: contradicts ADR-0012 d→c commitment; destroys forensic audit trail.
2. **State machine B — `pending` → `ready` / `failed`.** Three states, linear. Flipping from `failed` back to `pending` (retry) requires explicit transition. Chosen.
3. **State machine C — `pending` → `computing` → `ready` / `failed`.** Four states. `computing` distinct from `pending`. Adds complexity without a code path that needs to distinguish "we wrote the projects row" from "the engines are running". The `schedule_derived_artifacts` table is the correct surface for per-engine progress.

### Stale-race protection (ADR-0014 P1#6)

1. **Protection A — `updated_at` column on `projects` + trigger + materializer compares timestamps.** Clean, but requires migration 024 to add the column and a `BEFORE UPDATE` trigger. `projects` currently has no `updated_at`.
2. **Protection B — Re-compute `input_hash` at save time.** Materializer captures `input_hash_at_start = compute_input_hash(schedule, project_id)`; immediately before calling `save_derived_artifact`, re-reads the current `ParsedSchedule` from DB and recomputes `input_hash_at_save`; aborts with a `StaleMaterializationError` if the two differ. Zero schema change. Chosen.
3. **Protection C — Postgres advisory lock on `project_id` for the materializer span.** `pg_advisory_xact_lock` scoped to the UUID hash. Effective but the `supabase-py` client does not expose advisory locks cleanly; would require a custom RPC. Overkill for the current race frequency (<1% expected under normal upload cadence).

### Backfill delivery surface

1. **Delivery A — Admin-only HTTP endpoint `POST /api/v1/admin/backfill/materializer`.** Fast to ship; surfaces backfill state in logs/monitoring that the HTTP worker already emits. Rejected: a 400-project × 4-engine × ~2s backfill runs for ~55 minutes and monopolises the 1-CPU HTTP worker.
2. **Delivery B — CLI entry point `python -m src.materializer.backfill` invoked via `fly ssh console`.** Runs in a separate process on the Fly.io VM; HTTP workers stay responsive. Idempotent via `save_derived_artifact` upsert + uniqueness tuple. Chosen.
3. **Delivery C — Dedicated Fly.io machine.** Overkill for a one-shot backfill of ~400 projects.

## Decision Outcome

### 1. Runtime — Option B (`asyncio.Task` + `Semaphore(1)` + `ProcessPoolExecutor`)

- A single `asyncio.Semaphore(1)` serialises materialization jobs on the worker; concurrent uploads queue in memory.
- CPU-bound engine work (`DCMA14Analyzer`, `HealthAnalyzer`, `CPMEngine`, `FloatTrendsAnalyzer`) runs via `loop.run_in_executor(ProcessPoolExecutor(max_workers=1), ...)` so the event loop stays responsive.
- A small synchronous fast-path bypasses the queue when the parsed schedule has fewer than `MATERIALIZER_SYNC_THRESHOLD` activities (default 100). Latency budget under the threshold is trivially under 2 seconds; async overhead outweighs the benefit.
- Enqueue surface is an abstract `Materializer.enqueue(project_id: str) -> JobHandle` so the migration to `arq` in a future ADR requires replacing one class, not every call site.

### 2. `projects.status` state machine — Option B (`pending` / `ready` / `failed`)

- Migration 024 adds `status TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('pending','ready','failed'))`. `DEFAULT 'ready'` backfills all existing rows inside the migration transaction — they have already survived the historical persist path.
- `save_project` inserts new rows with `status = 'pending'`.
- On successful materialization, materializer flips to `'ready'`.
- On materializer failure, materializer flips to `'failed'`. The row stays. The Storage XER blob stays. `failed` is a forensic artefact, not a cleanup target.
- `_persist_schedule_data`'s outer `try/except` (store.py ~1193–1254) is refactored: `DELETE FROM projects` is replaced by `UPDATE projects SET status = 'failed'`; the Storage blob probe-and-remove path is removed. The original persist exception still propagates — HTTP callers still see 500s, but the row and blob are preserved for audit and re-materialization.
- Migration 024 and the `save_project` / `_persist_schedule_data` code edits ship in the **same commit**. No phased deploy; a migration applied without the code edit would leave new rows at the DEFAULT `'ready'` which is wrong during the pending window. A code edit applied without the migration would reference a column that does not exist.

### 3. Read-path filter

- Surface is **~7 call sites** inside `src/database/store.py` (not ~40 as loosely estimated in the bootstrap). `_select("projects", ...)` and `.table("projects")...` are the only SQL surfaces; API-layer callers all go through `store.get_project` / `store.get_projects` / `store.get_parsed_schedule` / `store.get_programs` / `store.get_program_revisions` / `store.list_ids`.
- The filter is distributed explicitly per call site, not applied as a default in `_select`. Admin, owner-lists-own-failed, and the reports/BI enumerate-with-marker paths all need to bypass the filter.
- `store.get_projects(user_id, include_all_statuses=False)` grows the new flag; default hides only pure `failed` rows from non-owners. Owners of a project always see every status on their own list (badges do the discrimination). BI and reports iterate with `include_all_statuses=True` and render `failed` with an explicit marker per SCL §4.
- The three non-`store.py` call sites (`src/api/organizations.py:373`, `:501`, `src/api/routers/admin.py:136`) are ownership-probe or admin-delete, not analytic reads. They operate on every status unchanged.

### 4. Stale-race protection — Option B (re-hash at save)

- Materializer computes `input_hash_start` once at the beginning of the run.
- Immediately before each `save_derived_artifact` call (one per engine), materializer reloads the parsed schedule from DB (`store.get_parsed_schedule(project_id)`) and computes `input_hash_now`.
- If `input_hash_now != input_hash_start`, the materializer raises `StaleMaterializationError`, does NOT persist any further artifacts for this run, does NOT flip `projects.status`, and logs a structured WARN. The newer upload's materializer run (already queued behind the semaphore) takes over.
- The uniqueness tuple in migration 023 (`UNIQUE NULLS NOT DISTINCT (project_id, artifact_kind, engine_version, ruleset_version, input_hash)`) prevents double-persist as a defensive second line, but the race is resolved by the abort, not the constraint.

### 5. Service_role premise — amendment in this ADR

ADR-0014 §RLS quadruple rationale is amended by this ADR: the UPDATE policy shipped in migration 023 is **forward-compatible** with a future authenticated-path split but is **not load-bearing today**. `src/database/client.py` uses `SUPABASE_SERVICE_ROLE_KEY` globally; every backend caller bypasses RLS. When MCP plugins or a user-triggered "force recompute" UI path are wired to run under the `authenticated` role (future work, out of scope for Wave 2), the UPDATE policy activates without further schema change.

### 6. Backfill — Option B (CLI)

- Entry point `python -m src.materializer.backfill` accepts `--limit`, `--project-id`, `--dry-run` flags.
- Selects `projects` where `status = 'ready'` AND NOT EXISTS any artifact row for that project, orders by `created_at ASC`, materializes in serial batches.
- Each materialized artifact writes one `audit_log` row with `user_id = NULL`, `action = 'materialize'`, `details = {"trigger": "system_backfill_v2", "backfill_id": "<uuid>"}`. ADR-0014 §`computed_by` already permits the NULL case explicitly.
- Run via `fly ssh console` on the deployed Fly.io VM so it does not compete with the HTTP worker for CPU.
- Idempotent: re-running a batch that overlaps prior runs is harmless because `save_derived_artifact` upserts on the uniqueness tuple.

### 7. Progress surface — ADR-0013 WebSocket channel

- Upload response body carries `{project_id, status, job_id, ws_url}` so the frontend can subscribe to the materializer's progress events. The HTTP status code stays **200 OK** in v4.0: a ~50-test backward-compatibility surface currently asserts `200`, and flipping the status code globally has blast-radius disproportionate to the semantic win of `202`. The `202 Accepted` shape is the v4.1 target and will land with a coordinated client + test update; until then `status='pending'` in the body is the authoritative signal.
- Materializer publishes `{"type": "progress", "event": "engine_start", "engine": "dcma"}`, `{"type": "progress", "event": "engine_done", "engine": "dcma", "progress": 25}`, … through the existing channel.
- Final `{"type": "done"}` or `{"type": "failed", "reason": "..."}` closes the channel.
- The `job_id` is pre-registered on the channel inside `Materializer.enqueue` via `open_channel(job_id, owner_user_id=user_id)` so early publishes are not dropped. Council W2 end-of-wave (backend-reviewer + devils-advocate) surfaced this as a P1 — shipping without the pre-register means 100 % of progress events vanish silently and the WS handshake returns 4403 in production.
- Frontend polling at 3 s intervals is the default reliability path (see ADR-0013 cold-start caveat); WS is the opt-in enhancement.

### 8. Timeout contract

- Soft timeout: 120 seconds. The materializer continues running but the UI flips the badge to `"stuck"` (visual only; not a DB state).
- Hard timeout: 600 seconds. The materializer cancels its own task and flips `projects.status = 'failed'` with `audit_log.details.reason = 'timeout'`.

### 9. Rationale summary

Each element of this decision is the lowest-cost option that satisfies a named persona or accepted standard:

- `asyncio.Task + ProcessPoolExecutor` matches the 1-CPU single-instance deployment without foreclosing the queue-backed future.
- Three-state machine closes ADR-0012 and matches the forensic requirement that `failed` is visible, not erased.
- Same-commit deploy of migration 024 + code edits removes the half-state window.
- Re-hash stale protection costs zero schema and uses the already-canonical `input_hash` as the tamper-evident witness.
- CLI backfill keeps the HTTP worker responsive; `audit_log` NULL-user + trigger-tag keeps SCL §4 chain-of-custody intact.
- WS + polling fallback matches ADR-0013 and the BUG-007 reality.

## Rejected alternatives

- **Runtime C (`arq`)** — deferred to a future ADR when upload cadence justifies the ops addition.
- **State machine C (`pending → computing → ready/failed`)** — the `computing` distinction belongs in `schedule_derived_artifacts.computed_at` granularity, not in `projects.status`.
- **Protection A (`updated_at` column)** — requires another column + trigger; the re-hash path uses existing infrastructure.
- **Delivery A (admin HTTP backfill)** — single-CPU contention against HTTP worker.

## Consequences

**Positive:**
- ADR-0012 phased-atomicity commitment closes cleanly in the same wave that introduces the state column.
- `failed` projects preserve forensic provenance; re-materialization is a routine recovery, not a re-upload.
- Upload latency drops to parse-and-persist time (~1–2s typical) regardless of engine runtime.
- Read-path audit touches ~7 store-layer call sites, not the 40 feared in the Wave 2 bootstrap.
- The materializer's abstract `enqueue()` surface is a clean migration seam to `arq` when volume warrants.

**Negative:**
- `ProcessPoolExecutor` serialises materializations on a 1-CPU host; concurrent uploads queue behind the semaphore. Under a burst of 10 uploads, the 10th waits ~(9 × avg_materialize_seconds). UI must communicate the queue depth honestly.
- `pending` projects visible in owner lists require frontend badges — a new UI contract on every enumeration view.
- Re-hashing at save doubles the DB read traffic of the materializer (one read at start, one read per save). Trade cost is a 4–5× over no-check baseline; acceptable at current volumes.
- Stale reconciliation for projects backfilled by W2 but later invalidated by a W3+ `lifecycle_phase` rollout will require a separate `mark_stale` run. Policy is: each engine/ruleset version bump emits a bulk `mark_stale` on its affected kind. Out of scope for Wave 2.

**Neutral:**
- The `ADR-0014` amendment re: service_role is documentational; migration 023's UPDATE policy stays on disk without runtime effect today.
- The `MATERIALIZER_SYNC_THRESHOLD` constant is a single-line tunable, future-proof against profiling.

## Links

- Parent: ADR-0009 (Cycle 1 v4.0, Wave 2).
- Closes: ADR-0012 phased atomicity (option (d) → option (c)).
- Amends: ADR-0014 §RLS quadruple rationale re: service_role scope.
- Companion: ADR-0013 (WebSocket progress channel — the materializer is a consumer).
- Code:
  - `supabase/migrations/024_projects_status_state.sql` — the `status` column + CHECK + partial index.
  - `src/database/store.py` — `save_project` sets `status='pending'`; `_persist_schedule_data` replaces compensating DELETE with UPDATE; `get_projects` grows `include_all_statuses` flag.
  - `src/materializer/__init__.py`, `src/materializer/runtime.py`, `src/materializer/backfill.py` — async runtime, enqueue surface, backfill CLI.
  - `src/api/routers/upload.py` — returns `202 Accepted` + `job_id`; hooks `Materializer.enqueue`.
- Tests: `tests/test_projects_status_column.py`, `tests/test_materializer_runtime.py`, `tests/test_store_persistence.py` (rewritten), `tests/test_backfill_cli.py`.
- Standards cited: SCL Protocol 2nd ed §4; AACE MIP 3.4, 3.6; AACE RP 14R, 29R, 57R §4.1, 114R; PMI-CP audit-ready reporting.
