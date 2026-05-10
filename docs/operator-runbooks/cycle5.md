<!-- Authored 2026-05-09 evening (Cycle 5 release-arc) — operator-paced runbooks for migration 029 + post-v4.3.0 housekeeping -->

# Cycle 5 — Operator Runbooks

This document collects the **operator-paced** items relevant to Cycle 5 close at `v4.3.0` (commit `89e0f53`).

| # | Title | Trigger | Estimated time | Difficulty | Section |
|---|---|---|---|---|---|
| W3-OPS-01 | Apply migration 029 (`revision_skip_log`) — STAGING-FIRST | One-time post-v4.3.0 release | 10–15 min | Ops + manual SQL | [§W3-OPS-01](#w3-ops-01--apply-migration-029-revision_skip_log) |
| W3-OPS-02 | Engine_version 4.2.0 → 4.3.0 derived-artifact re-mat coordination | One-time post-v4.3.0 release | 15–30 min | Ops + audit_log review | [§W3-OPS-02](#w3-ops-02--engine_version-43-re-mat-coordination) |

**Standing protocol:** each ops action ends with a "Registry" step. Comment on the relevant tracking issue (or open one if novel) and append a one-line entry to the audit log if not auto-paired by the API.

---

## W3-OPS-01 — Apply migration 029 (`revision_skip_log`) — ✅ DONE 2026-05-09

**Status: APPLIED to production** at 2026-05-09 ~03:35 UTC via `supabase db query --linked --file supabase/migrations/029_revision_skip_log.sql`. Verification:
- `to_regclass('public.revision_skip_log')` returns the table
- 5 constraints (PK + UNIQUE triple + CHECK self-skip + 2 FKs)
- 4 RLS policies (SELECT / INSERT / UPDATE / DELETE — all owner-bound)
- 3 indexes (PK + UNIQUE + B-tree on `project_id, user_id`)

The runbook below is preserved as historical record for the discipline pattern. Future migrations (e.g., #117 / #119 typed-exception or audit_log paired writes) follow the same shape.

**Trigger:** One-time post-`v4.3.0` release. Migration 029 shipped in commit `89e0f53`. Per the `STAGING-FIRST APPLY` discipline carried forward from migration 028, this was operator-paced.

**ADR/PR:** [PR #118](https://github.com/VitorMRodovalho/meridianiq/pull/118) (closes #84) + ADR-0024 (Cycle 5 entry — Z-shape consolidation).

### Why this is operator-paced (not auto-applied by CI)

- The Cycle 4 W1 precedent (migration 028, [PR #76](https://github.com/VitorMRodovalho/meridianiq/pull/76)) established that schema-additive migrations DO NOT run in CI on `main` push. The repo has no automated migration runner; the operator runs the SQL via Supabase Dashboard or `supabase db push` against staging first, then production.
- Migration 029 is schema-additive only (new table + RLS + indexes; no destructive DDL on existing rows). Risk profile is low, but the STAGING-FIRST gate is the blanket discipline, not a per-migration risk-tier judgement.

### What the migration does

1. Creates `public.revision_skip_log` table (5 columns, 2 constraints).
2. Adds B-tree index `idx_revision_skip_log_project_user` on `(project_id, user_id)`.
3. Enables RLS + 4 policies (SELECT/INSERT/UPDATE/DELETE — all owner-bound).
4. Issues `NOTIFY pgrst, 'reload schema'` for PostgREST cache invalidation.

See `supabase/migrations/029_revision_skip_log.sql` for the canonical SQL.

### Pre-apply checklist

- [ ] Confirm Supabase project ID = `tuswqzeytiobqfkxgkbe` (MeridianIQ canonical)
- [ ] Confirm `gh release view v4.3.0` shows the release as published
- [ ] Confirm latest `main` is `89e0f53` or descendant
- [ ] Verify no app-side calls to `record_revision_skip` / `clear_revision_skips` are exercising paths that depend on the table existing (the runtime SDK handles `relation does not exist` as a transient error today via `# noqa: BLE001` log-and-continue, but applying-then-rolling-back would be untested)

### Apply (staging)

> **Note**: MeridianIQ uses a SINGLE Supabase project (`tuswqzeytiobqfkxgkbe`); there is no formal staging schema split. The "staging-first" pattern in this repo means applying to a dev branch (Supabase Branching) OR to a temp schema first to verify SQL semantics, then to the real `public` schema.

**Option A — Supabase Dashboard SQL Editor**

1. Go to https://supabase.com/dashboard/project/tuswqzeytiobqfkxgkbe/sql/new
2. Paste the contents of `supabase/migrations/029_revision_skip_log.sql`
3. Click "Run". Expected output: 7 successful statements + 1 NOTIFY.
4. Verify under "Database → Tables" that `revision_skip_log` exists with 5 columns + 1 unique index + 1 b-tree index.
5. Verify under "Database → Policies" that 4 policies exist on `revision_skip_log`.

**Option B — `supabase` CLI (if linked locally)**

```bash
# from repo root
supabase db push                     # applies all pending migrations
# OR for surgical apply:
supabase db push --include-all       # equivalent
```

(Note: `supabase db push` requires `supabase login` + `supabase link` to the MeridianIQ project. As of v4.3.0 close, the repo's `supabase/config.toml` is configured for project `tuswqzeytiobqfkxgkbe`.)

### Post-apply verification

```sql
-- 1. Table exists with the expected shape
\d+ public.revision_skip_log

-- 2. Constraints in place
SELECT conname, contype FROM pg_constraint
 WHERE conrelid = 'public.revision_skip_log'::regclass;
-- Expected: pkey + uq_revision_skip_log_triple + chk_revision_skip_not_self
--           + 2 FK constraints (project_id, candidate_project_id)

-- 3. RLS quadruple in place
SELECT policyname, cmd FROM pg_policies
 WHERE tablename = 'revision_skip_log';
-- Expected: rsl_select_own, rsl_insert_own, rsl_update_own, rsl_delete_own

-- 4. PostgREST schema cache reloaded (call any endpoint that touches the table)
-- POST /api/v1/projects/{any}/skip-revision-of with a real candidate_id;
-- expect 200 with recorded:true OR a meaningful 4xx (NOT a relation-does-not-exist 500).
```

### Rollback (if needed)

```sql
-- Hard rollback: drops the table + all policies + indexes
DROP TABLE IF EXISTS public.revision_skip_log CASCADE;
NOTIFY pgrst, 'reload schema';
```

The `ON DELETE CASCADE` from `revision_history.project_id`/`candidate_project_id` to `projects.id` means dropping the table does NOT cascade up; safe to drop. Frontend SDK handles a missing table via the existing `# noqa: BLE001` log-and-continue pattern (the skip endpoints would surface a 5xx temporarily until you re-apply).

### Registry

After applying:
- [ ] Comment on [#84](https://github.com/VitorMRodovalho/meridianiq/issues/84) (closed by PR #118): "Migration 029 applied to production at `<timestamp>`."
- [ ] Update `project_state.md` memory file: change "29 Supabase migrations (added `029_revision_skip_log.sql` in Cycle 5 W3-E — STAGING-FIRST apply still pending operator)" → "29 Supabase migrations (latest: `029_revision_skip_log.sql` applied `<timestamp>`)".
- [ ] Update `project_resume_next_session.md` to remove the STAGING-FIRST item from "Pending operator action items".

---

## W3-OPS-02 — Engine_version 4.3 re-mat coordination

**Trigger:** One-time post-v4.3.0 release.

Per [ADR-0014 §"Decision Outcome"](../adr/0014-derived-artifact-provenance-hash.md), the `engine_version` provenance contract means: when `src/__about__.py::__version__` bumps from 4.2.0 → 4.3.0, all rows in `schedule_derived_artifacts` written under `engine_version='4.2.0'` will return `None` on read (the materializer's read path filters by `engine_version` and a mismatch yields no row). Forced re-mat happens lazily on next access.

### Two paths

**Path 1 — Lazy re-mat (default, no operator action)**

- Users who access derived artifacts will trigger fresh materialization in the background.
- Cost: O(N) on the first access per project per derived artifact type. The async materializer (Cycle 1 W2) handles concurrent re-mat without blocking the foreground UI.
- Risk: read-during-rebuild surfaces stale-but-consistent data (the prior v4.2.0 row is invalidated, the new v4.3.0 row is not yet written → "no data yet" UI state). Already handled via `StatusBadge` `computing` state.

**Path 2 — Bulk pre-emptive re-mat (operator-paced)**

- Trigger via Supabase Dashboard SQL or a one-off Python script invoking the materializer. NOT shipped as a CLI; would need scaffolding.
- Cost: O(N) ALL projects upfront. Fly.io free-tier compute window matters; could exceed the per-day cycle budget on heavy projects.
- Risk: `engine_version` audit_log churn. Each re-mat writes an audit row.

### Recommendation

**Default to Path 1 (lazy)** unless you have a specific user complaint about stale data. The lifecycle / DCMA / EVM / risk pages all handle the "no v4.3.0 row yet" state gracefully.

If a user does complain, surface the path-2 option as a per-project re-mat invocation (existing materialize-now button on project detail page).

### Registry

- [ ] Decision recorded in handoff memory `project_resume_next_session.md` (current default = Path 1)
- [ ] If Path 2 chosen, comment on the operator's ticket / PR with cost analysis + scaffolding plan
