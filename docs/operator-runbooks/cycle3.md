<!-- Authored 2026-04-27 (Cycle 3 W4 code-side close) — operator-paced runbooks for W1 / W2 / W4 -->
# Cycle 3 — Operator Runbooks (W1 + W2 + W4)

This document collects the **operator-paced** items committed in [ADR-0021 §"Wave plan"](../adr/0021-cycle-3-entry-floor-plus-field-shallow.md) that Claude prepares but **only the maintainer can execute** (production credentials, council judgement, or operator decisions on data state).

Closing all four runbooks closes Cycle 3 success criteria #2, #3, #4, and #7 simultaneously — the bulk of the cycle's reversibility budget. Per ADR-0021 graceful-success threshold (≥5/9 criteria), executing this document plus the already-closed #1 (audit re-run), #5 (W3 reproduction test), #6 code-side (engine_version migration) puts the cycle at **7/9 closed**.

| # | Title | Closes | Estimated time | Difficulty | Section |
|---|---|---|---|---|---|
| W1 | Apply migration `026_api_keys_schema_align.sql` to production | #26 + criterion #2 | 30–45 min | Operations | [§W1](#w1--apply-migration-026-to-production) |
| W2-A | Ratify 5 ADRs (0017, 0018, 0019, 0020, 0021) | #28 + criterion #3 | 60–90 min | Council review | [§W2-A](#w2-a--ratify-adrs-0017-0021-five-adrs) |
| W2-B | Archive W4 manifest to `meridianiq-private` | criterion #4 | 15–30 min | Operations | [§W2-B](#w2-b--archive-w4-manifest-to-private-repo) |
| W4 | Re-materialize OR tombstone 88 production derived-artifact rows | criterion #7 | 30–60 min | Decision + ops | [§W4](#w4--re-materialize-or-tombstone-88-prod-rows) |

**Standing protocol:** each runbook ends with a §"Registry" step. Comment the result on the relevant issue (#26 / #28 / #25 meta / a new issue for W4). Update the cycle 3 success-criteria scoreboard in `docs/ROADMAP.md` and the maintainer memory after each closure.

---

## W1 — Apply migration `026_api_keys_schema_align.sql` to production

**Issue:** [#26](https://github.com/VitorMRodovalho/meridianiq/issues/26)
**ADR:** [ADR-0017](../adr/0017-deduplicate-api-keys-migration.md)
**Cycle 3 success criterion:** #2

### Context

Migration 026 was authored 2026-04-22 (audit Wave B4) and merged in `cd3b907`. It's idempotent — safe to re-run on a Supabase instance that already has the canonical 017 schema (no-op) AND on instances where the legacy 012 schema is still live (in-place reconciliation: backfill `key_id` from `id::text`, translate `is_active=FALSE → revoked_at=now()`, drop `key_prefix`/`is_active`/`expires_at`, re-emit canonical policies).

The migration has been merged in code for **5+ days** without prod apply. Per [ADR-0014 §"is_stale"](../adr/0014-derived-artifact-provenance-hash.md#decision-outcome) read-path semantics, *any production instance still on the 012-shape schema* fails silently when the runtime tries to insert a new API key (column-mismatch error caught by [`06fa945`](https://github.com/VitorMRodovalho/meridianiq/commit/06fa945) fail-closed → 503).

### Pre-flight diagnostics (read-only, run any time)

Connect to the production Supabase project at `tuswqzeytiobqfkxgkbe` (per `project_supabase_projects.md` user memory) via the Supabase SQL Editor:

```sql
-- 1. Inspect current api_keys schema.
\d api_keys

SELECT column_name, data_type, is_nullable
  FROM information_schema.columns
 WHERE table_name = 'api_keys'
 ORDER BY ordinal_position;

-- 2. Check which migrations have run.
SELECT name, executed_at
  FROM supabase_migrations.schema_migrations
 WHERE name LIKE '%api_keys%'
 ORDER BY executed_at;

-- 3. Row count baseline.
SELECT COUNT(*) AS total_rows,
       COUNT(*) FILTER (WHERE revoked_at IS NULL) AS active_rows
  FROM api_keys;
```

**Decision tree based on output:**

| Schema observed | Indicator | 026 effect |
|---|---|---|
| Canonical 017 only | `key_id` + `key_hash` + `revoked_at` columns present; **no** `key_prefix` / `is_active` / `expires_at` | **No-op** — script runs idempotently, drops nothing, asserts policies, exits clean |
| Legacy 012 only | `key_prefix` + `is_active` + `expires_at` present; no `key_id` | **In-place reconciliation** — adds `key_id` (backfilled from `id::text`), translates `is_active=FALSE → revoked_at=now()`, drops legacy columns |
| Mixed (rare) | Some legacy + some canonical columns | Migration 026 detects per-column via `information_schema` — handles each independently |

Paste the diagnostic output as a comment on issue #26 *before* proceeding to the apply step.

### Backup (mandatory)

Before any DDL touches production:

```sql
CREATE TABLE api_keys_backup_20260427 AS SELECT * FROM api_keys;
SELECT COUNT(*) FROM api_keys_backup_20260427;  -- should equal pre-flight #3
```

**Update the date suffix to the actual day of execution.** Preserve the backup for **≥30 days** before dropping.

### Apply

**Option A — Supabase CLI (preferred):**

```bash
supabase link --project-ref tuswqzeytiobqfkxgkbe
supabase db push supabase/migrations/026_api_keys_schema_align.sql
```

**Option B — SQL Editor manual paste:**

Copy the entire content of `supabase/migrations/026_api_keys_schema_align.sql` into the Supabase SQL Editor and execute. The migration has 5 numbered steps (drop legacy policies → ensure `key_id` column → translate `is_active` to `revoked_at` → drop legacy columns → re-emit canonical policies). Each step uses `IF NOT EXISTS` / `IF EXISTS` guards.

### Post-apply verification

```sql
-- 1. Confirm canonical schema.
\d api_keys
-- Expected columns: id (bigint), key_id (text unique), key_hash (text unique),
--                   user_id (uuid), name (text), created_at, revoked_at, last_used_at.

-- 2. Row count preserved (no data loss).
SELECT COUNT(*) FROM api_keys;
-- Expected: equal to backup count.

-- 3. Backfilled rows count (if migration did real work).
SELECT COUNT(*) FROM api_keys WHERE key_id LIKE 'legacy_%';
-- Zero on canonical-only instances; equal to original 012-row count on legacy.

-- 4. Confirm canonical policies are present.
SELECT policyname FROM pg_policies WHERE tablename = 'api_keys' ORDER BY policyname;
-- Expected: api_keys_delete, api_keys_insert, api_keys_select.
```

### Smoke test runtime

If staging is available, run the smoke test there first; otherwise carefully against production with a short-lived test key:

```bash
# Generate a test API key via authenticated user session.
curl -X POST https://api.meridianiq.vitormr.dev/api/v1/api-keys \
  -H "Authorization: Bearer <user-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "post-026-apply-smoke-test"}'
# Expected 200 with {"key_id": ..., "key": "mk_..."}

# Validate the new key on a public-with-optional-auth endpoint.
curl https://api.meridianiq.vitormr.dev/api/v1/health \
  -H "X-API-Key: mk_..."
# Expected 200 with body indicating authenticated identity.

# Revoke the test key.
curl -X DELETE https://api.meridianiq.vitormr.dev/api/v1/api-keys/{key_id} \
  -H "Authorization: Bearer <user-jwt>"
# Expected 204.
```

### Rollback

If verification fails OR an unexpected `pg_advisory_lock` deadlock surfaces:

```sql
-- Disconnect any concurrent connections holding api_keys reads.
-- Then:
DROP TABLE api_keys;
ALTER TABLE api_keys_backup_20260427 RENAME TO api_keys;

-- Re-apply RLS + policies from migration 017 manually.
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
-- Copy the policy DDL from supabase/migrations/017_api_keys.sql.
```

The backup table preserves all rows and column types. Only the policies need re-applying — they live in 017 verbatim.

### Registry

Comment on issue #26 with:

1. Diagnostic output from §Pre-flight (passes 1, 2, 3 SQL blocks).
2. Backup table name + row count.
3. `\d api_keys` output post-apply.
4. Smoke test results (3 curl invocations).
5. Operator + reviewer names + apply timestamp (UTC).
6. Link to this runbook section.

After commenting, **close #26** with `state_reason: completed`. Update [`docs/ROADMAP.md`](../ROADMAP.md) §"Cycle 3" wave table W1 row from "OPEN — operator-paced" to "DONE at YYYY-MM-DD".

---

## W2-A — Ratify ADRs 0017–0021 (five ADRs)

**Issue:** [#28](https://github.com/VitorMRodovalho/meridianiq/issues/28)
**ADR-0000:** [recording architecture decisions](../adr/0000-record-architecture-decisions.md)
**Cycle 3 success criterion:** #3

### Context

Per ADR-0000 governance, an ADR's status `accepted` *presupposes human council review*. The audit-remediation agent and (in Cycle 2 + Cycle 3 entry) Claude marked five ADRs as `accepted` without a separate human ratification round:

- ADR-0017 — Deduplicate api_keys migration (audit Wave A, 2026-04-22)
- ADR-0018 — Cycle cadence doc artifacts (audit Wave A, 2026-04-22) **+ Amendment 1 (2026-04-27)**
- ADR-0019 — Cycle 2 entry: Consolidation + Primitive (Cycle 2 W0, 2026-04-25)
- ADR-0020 — Calibration harness primitive (Cycle 2 W3, 2026-04-26)
- ADR-0021 — Cycle 3 entry: Floor + Field-surface shallow (Cycle 3 W0, 2026-04-27)

Issue #28's original body listed only ADR-0017 + ADR-0018 (the audit-remediation pair). [AUDIT-2026-04-26-009](../audit/2026-04-26/06-planned-vs-implemented.md) flags the scope expansion to 5 ADRs; **the issue body needs updating before this runbook starts**. The PR shipping this runbook also updates the issue body via `gh issue edit 28 --body-file ...` (operator can also do it manually).

### Council process (solo-maintainer adaptation)

ADR-0000 expects "council review" but the project is solo-maintained today. The adapted process:

1. **Re-read each ADR end-to-end** (~5–10 min per ADR). Treat the re-read as adversarial — a **fresh** reader who hasn't seen the decision document. Catch self-citation drift, missing alternatives, vague language.
2. **For Amendment 1 to ADR-0018**, the recursive context is unique: the amendment was authored under the protocol it codifies. Pay attention to whether the empirical claims are independently verifiable (per the §"Self-pressure-test bias" disclosure) and whether the protocol it describes matches what's actually been observed across PRs #33–#52.
3. **Per-ADR outcome (one of three):**
   - **Ratify as-is** — ADR text stays; no edit. Comment "ratified by @VitorMRodovalho on YYYY-MM-DD".
   - **Reopen as `proposed`** — edit ADR header `Status: proposed`; specify the structural objection in a new §"Open question" appended to the ADR.
   - **Supersede** — author a new ADR-NNNN that supersedes this one; edit the old ADR header `Status: superseded by ADR-NNNN`; **never** edit the old ADR body (per ADR-0000 immutability rule).

### Per-ADR ratification checklist

#### ADR-0017 — Deduplicate api_keys migration

- [ ] Read [ADR-0017](../adr/0017-deduplicate-api-keys-migration.md) end-to-end
- [ ] Verify §"Considered Options" rejects (a) delete 012 + (b) rewrite 012 with rationale matching what shipped in `cd3b907`
- [ ] Decision: **option 3** (012 → no-op + 026 idempotent reconcile). Confirm this matches operator decision still desired.
- [ ] Outcome:
  - [ ] Ratify as-is
  - [ ] Reopen as proposed (state objection)
  - [ ] Supersede (link to new ADR)

#### ADR-0018 — Cycle cadence doc artifacts (+ Amendment 1)

- [ ] Read [ADR-0018](../adr/0018-cycle-cadence-doc-artifacts.md) **including Amendment 1 (lines 104+)**
- [ ] Verify §"Decision" 5 doc artifacts match what's actually authored each cycle close (audit re-run, ROADMAP, BUGS, LESSONS, catalog regen)
- [ ] **Amendment 1 specific** — the recursive bias disclosure: empirical claims (8 substantive PRs, 2+4 average from original 3-PR sample) are self-collected. Decision: do you accept the disclosed bias, or want external validation before ratifying?
- [ ] **Amendment 1 trigger commitment** — Amendment 2 (4-agent council protocol codification) lands at Cycle 4 W0 OR by Cycle 5 W0. Confirm this is acceptable scope; alternative is to widen Amendment 1 NOW to include the 4-agent council.
- [ ] Outcome:
  - [ ] Ratify as-is (both base + Amendment 1)
  - [ ] Reopen Amendment 1 as proposed (specify which sub-clause)
  - [ ] Supersede Amendment 1 with a fresh standalone ADR-0024

#### ADR-0019 — Cycle 2 entry: Consolidation + Primitive

- [ ] Read [ADR-0019](../adr/0019-cycle-2-entry-consolidation-primitive.md) end-to-end
- [ ] Verify Cycle 2 closed at v4.1.0 with 7/7 pre-registered success criteria (per CHANGELOG.md v4.1.0 entry)
- [ ] **Backward-looking ratification** — the cycle is closed; the ratification is "we agreed in retrospect this was the right call". Strange but consistent with ADR-0000's "decision-records-not-decision-permits" framing.
- [ ] Outcome:
  - [ ] Ratify as-is
  - [ ] Reopen as proposed (state objection — rare for a closed cycle's entry ADR)
  - [ ] Supersede (would require re-running Cycle 2 — not realistic)

#### ADR-0020 — Calibration harness primitive

- [ ] Read [ADR-0020](../adr/0020-calibration-harness-primitive.md) end-to-end
- [ ] Verify §"Decision" caveat about W4 reproduction is now closed by PR #48 (test_w4_reproduction.py)
- [ ] Outcome:
  - [ ] Ratify as-is
  - [ ] Reopen as proposed
  - [ ] Supersede

#### ADR-0021 — Cycle 3 entry: Floor + Field-surface shallow (Option α)

- [ ] Read [ADR-0021](../adr/0021-cycle-3-entry-floor-plus-field-shallow.md) end-to-end (~25 min — longest ADR)
- [ ] §"Open process gap" — the Amendment 1 of ADR-0018 closes the PR-level half. Confirm the cycle-entry-council half remains as-flagged (4-agent protocol still uncodified — Amendment 2 trigger).
- [ ] §"Pre-registered success criteria" — verify scoreboard in `docs/ROADMAP.md` matches:
  - #1 audit ✅ #2 prod migration OPEN #3 ratification (this) #4 manifest archive (W2-B below) #5 reproduction test ✅ #6 engine_version code-side ✅ #7 88-row re-mat (W4 below) #8 W5 spike (optional) #9 release tag
- [ ] §"Why NOT" rejected options (PV deep, E1, E3, Field-surface as primary, Schedule Viewer Wave 7 as cycle commit) — the rejection rationales are the load-bearing risk-mitigation. Pay attention.
- [ ] §"Hidden moat-erosion mechanism" — the maintainer-as-the-moat finding from IV. Acceptable as recorded structural risk?
- [ ] Outcome:
  - [ ] Ratify as-is
  - [ ] Reopen as proposed (specify objection)
  - [ ] Supersede (would require re-deciding Cycle 3 mid-cycle — disruptive)

### Registry

For each ADR, comment on issue #28 with:

1. Outcome (ratify / reopen / supersede)
2. Date + reviewer names
3. Link to ADR file
4. (If reopen/supersede) link to follow-up commit/PR

When all 5 are ratified, comment "All 5 ADRs ratified" + close issue #28 with `state_reason: completed`. Update [`docs/ROADMAP.md`](../ROADMAP.md) §"Cycle 3" wave table W2 row.

---

## W2-B — Archive W4 manifest to private repo

**No issue tracking — operator action only.**
**ADR:** [ADR-0009 §"Wave 4 outcome"](../adr/0009-w4-outcome.md), [ADR-0020 §"Decision"](../adr/0020-calibration-harness-primitive.md) caveat
**Cycle 3 success criterion:** #4

### Context

The 2026-04-19 W4 calibration run produced three artifacts (per [`scripts/calibration/run_w4_calibration.py`](../../scripts/calibration/run_w4_calibration.py)):

- `/tmp/w4_manifest.json` — content-hash-only dedup manifest. **Public-safe** (no filenames, no rationale text).
- `/tmp/w4_calibration_public.json` — coarse-banded aggregates. **Public-safe** (already published in [`docs/calibration/lifecycle-phase-w4-postmortem.md`](../calibration/lifecycle-phase-w4-postmortem.md)).
- `/tmp/w4_calibration_private.json` — per-observation detail with program-key-hashes + rules_fired. **Private only**.

Per ADR-0020 §"Publication scope", private artifacts must NEVER land in the public repo. The canonical home is `meridianiq-private/calibration/cycle1-w4/`.

The `/tmp/` filesystem is volatile across reboots. As of 2026-04-27 these files **are extant** with the timestamps below — but a reboot or a `tmpfs` rotation would lose them.

### Pre-flight verification (run as soon as possible)

```bash
ls -la /tmp/w4_*.json
```

**If files are missing**: re-run the W4 calibration per ADR-0021 §"Wave plan" W2 explicit fallback. Set `XER_SANDBOX_DIR` to the private 103-XER corpus and execute `python -m scripts.calibration.run_w4_calibration`. The new run will produce content-equivalent files (within the corpus + engine determinism) but the timestamps + run identifiers will differ. Document the re-run in the archive commit message.

**If files are extant** (current state confirmed 2026-04-27 23:00 UTC):

| File | sha256 | Size |
|---|---|---|
| `/tmp/w4_manifest.json` | `59764671a432498483fc8165e7e3cecf77c27f2e27eca7b8ec6571ed4c1927cf` | 7785 B |
| `/tmp/w4_calibration_public.json` | `16c7e490c9ae3b7c7c5fa852df73b95f0beab83261649805d91c20234c37bba2` | 2411 B |
| `/tmp/w4_calibration_private.json` | `65910f42f6b339c196bf831999994b96f8301cbdacb54f4c9fede133b6684a5b` | 42987 B |

These hashes are the **expected content-fingerprint** at archive time. If `sha256sum` returns different values, either the files were touched after 2026-04-27 OR the operator is on a different machine — investigate before archiving.

### Archive procedure

```bash
cd /path/to/meridianiq-private  # private repo clone

# 1. Create the canonical destination.
mkdir -p calibration/cycle1-w4

# 2. Copy + verify hashes match.
cp /tmp/w4_manifest.json calibration/cycle1-w4/
cp /tmp/w4_calibration_public.json calibration/cycle1-w4/
cp /tmp/w4_calibration_private.json calibration/cycle1-w4/

cd calibration/cycle1-w4
sha256sum w4_manifest.json w4_calibration_public.json w4_calibration_private.json > sha256sums.txt
cat sha256sums.txt
# Verify each hash matches the table above (or the values from a fresh re-run).

# 3. Commit with explicit reference.
cd ../..
git add calibration/cycle1-w4/
git commit -m "$(cat <<'EOF'
archive(calibration): Cycle 1 W4 lifecycle_phase calibration manifest

Per ADR-0020 §"Publication scope" — private observations never land
in the public repo. Source files were on /tmp/ on the maintainer's
host since 2026-04-19. Archive timestamp + sha256 verification
recorded in sha256sums.txt.

Cycle 3 W2 success criterion #4 closure (per ADR-0021 §"Wave plan").
EOF
)"
git push
```

### Smoke test (optional but recommended)

The harness has an end-to-end equivalence test against the W4 script. After archive, run a smoke that proves the harness can reproduce the manifest content from the archived input fixtures:

```bash
# In the public repo, with XER_SANDBOX_DIR pointing at the private corpus:
XER_SANDBOX_DIR=/path/to/private/corpus python -m tools.calibration_harness \
  --engine=lifecycle_phase \
  --protocol=lifecycle_phase-w4-v1 \
  --fixtures=/path/to/private/corpus \
  --output-dir=/tmp/w4_smoke_2026_04_27

# Compare aggregate counts to the archived public.
diff <(jq -S '.counts, .gate_evaluations_by_threshold' \
       /tmp/w4_smoke_2026_04_27/lifecycle_phase-w4-v1_public.json) \
     <(jq -S '.counts, .gate_evaluations_by_threshold' \
       /path/to/meridianiq-private/calibration/cycle1-w4/w4_calibration_public.json)
```

A clean diff confirms the harness reproduces the W4 numbers authoritatively — closing the [ADR-0020 §"Decision" caveat](../adr/0020-calibration-harness-primitive.md) at the **content level**, not just the equivalence-on-synthetic-fixtures level the W3 regression test pinned.

### Registry

Comment on the meta-issue [#25](https://github.com/VitorMRodovalho/meridianiq/issues/25) (audit baseline tracking) with:

1. Archive commit SHA in `meridianiq-private`
2. sha256 verification log
3. (Optional) smoke test diff result
4. Operator + reviewer names + timestamp

Update [`docs/ROADMAP.md`](../ROADMAP.md) §"Cycle 3" wave table W2 row to mark "manifest archive done".

---

## W4 — Re-materialize OR tombstone 88 prod rows

**Suggested issue:** open a new tracking issue `Cycle 3 W4 operator: re-materialize OR tombstone 88 prod rows` with label `audit-2026-04-26` + `priority:P1` + `ops` + `requires-human-decision`.
**ADR:** [ADR-0014 §"Decision Outcome"](../adr/0014-derived-artifact-provenance-hash.md#decision-outcome) provenance contract; PR #50 code-side migration
**Cycle 3 success criterion:** #7

### Context

PR #50 migrated `_ENGINE_VERSION` from hardcoded `"4.0"` to source from `src/__about__.py::__version__` (currently `"4.1.0"`). After PR #50 deploys to production, `get_latest_derived_artifact` does an **exact `engine_version` equality match** (`src/database/store.py:795`). The 88 production derived-artifact rows currently at `engine_version="4.0"` will:

- Return `None` from `get_latest_derived_artifact` calls — **invisible to read endpoints**
- Trigger re-materialization on first read of every affected project (forced via the lifecycle router)
- Coexist with new `engine_version="4.1.0"` rows under the `UNIQUE NULLS NOT DISTINCT (project_id, artifact_kind, engine_version, ruleset_version, input_hash)` constraint

This is *intentional ADR-0014 behavior* (version mismatch → forced re-mat) but it produces a **brief window of blank dashboards** until either:

- **Option A — Bulk re-mat:** Operator runs the materializer offline for every affected project; new rows are written at `engine_version="4.1.0"`. Old rows can be deleted post-verification.
- **Option B — Tombstone migration:** A new migration `027_artifact_engine_version_tombstone.sql` adds `is_stale=true` flag explicitly to the 88 old rows + retains them for forensic reproducibility per ADR-0014. Read path stays "return None on mismatch" but the audit trail is explicit.

### Decision criteria

| Criterion | Favors Option A (re-mat) | Favors Option B (tombstone) |
|---|---|---|
| Old rows have legitimate forensic value | — | ✅ |
| Re-mat compute cost is small (88 rows × small schedules) | ✅ | — |
| Maintainer wants a clean read-path post-deploy | ✅ | — |
| Maintainer wants ADR-0014 reproducibility chain preserved | — | ✅ |
| Time to execute | 30–45 min compute | 15–20 min DDL + verification |
| Reversibility | Old rows can be restored from backup | Migration is forward-only (would need new ADR to re-stale-flag) |

**Default recommendation: Option A (bulk re-mat)** — the 88 rows are from synthetic / sandbox / early-production data + the engine itself hasn't changed materially between `4.0` and `4.1.0`; re-mat produces equivalent content under different version label. The forensic value of old rows is low for v4.0 → v4.1 transition. Reserve Option B for major-version transitions where the engine's algorithm substantively changed.

### Pre-flight diagnostics

```sql
-- 1. Count affected rows.
SELECT COUNT(*) AS legacy_rows,
       COUNT(DISTINCT project_id) AS legacy_projects,
       COUNT(DISTINCT artifact_kind) AS legacy_kinds
  FROM schedule_derived_artifacts
 WHERE engine_version = '4.0';

-- 2. Row distribution by artifact kind.
SELECT artifact_kind, COUNT(*)
  FROM schedule_derived_artifacts
 WHERE engine_version = '4.0'
 GROUP BY artifact_kind
 ORDER BY 2 DESC;

-- 3. Project ownership for re-mat planning.
SELECT user_id, COUNT(DISTINCT project_id) AS projects
  FROM schedule_derived_artifacts
 WHERE engine_version = '4.0'
 GROUP BY user_id;
```

### Backup (mandatory before either option)

```sql
CREATE TABLE schedule_derived_artifacts_backup_20260427 AS
SELECT * FROM schedule_derived_artifacts WHERE engine_version = '4.0';

SELECT COUNT(*) FROM schedule_derived_artifacts_backup_20260427;
-- Expected: 88 (or whatever pre-flight #1 returned).
```

### Option A — Bulk re-materialize

```bash
# In a Python REPL or one-shot script on a host with DATABASE_URL set:
python -m src.materializer.backfill --limit 0 --re-materialize-version 4.0
```

The `backfill` CLI accepts a `--re-materialize-version` flag (which would need to be added if not present — implementation pre-step). The script:

1. Selects every project with at least one `engine_version='4.0'` artifact
2. For each project, runs `Materializer.materialize(project_id)` end-to-end
3. New rows at `engine_version='4.1.0'` are written; the `UNIQUE` constraint allows coexistence
4. Logs each project's outcome to stdout + `audit_log`

**If `--re-materialize-version` flag does NOT exist:** the script needs to be patched first. This is a 10–20 line change in `src/materializer/backfill.py` adding a `WHERE engine_version = ?` filter to `_candidate_project_ids`. Implement, test, commit, deploy, then run.

Post re-mat, optionally drop the old rows:

```sql
DELETE FROM schedule_derived_artifacts
 WHERE engine_version = '4.0';
-- OR keep them indefinitely as forensic record (no cost — 88 rows is trivial).
```

### Option B — Tombstone migration

Author a new migration `027_artifact_engine_version_tombstone.sql`:

```sql
-- Migration 027: tombstone legacy engine_version='4.0' artifact rows.
-- Per ADR-0014 §"is_stale" semantics + Cycle 3 W4 operator decision.
-- Reverse-able by re-running the materializer (Option A).

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'schedule_derived_artifacts' AND column_name = 'is_stale'
    ) THEN
        UPDATE schedule_derived_artifacts
           SET is_stale = TRUE,
               stale_reason = 'engine_version_predates_about_py_migration_pr_50'
         WHERE engine_version = '4.0' AND is_stale = FALSE;
    END IF;
END $$;
```

Apply via Supabase CLI or SQL Editor. Backfill is idempotent — re-running is no-op.

### Post-execution verification

For Option A:

```sql
SELECT engine_version, COUNT(*)
  FROM schedule_derived_artifacts
 GROUP BY engine_version
 ORDER BY engine_version;
-- Expected: only '4.1.0' rows (or '4.1.0' AND '4.0' if old rows retained).
```

For Option B:

```sql
SELECT engine_version, is_stale, COUNT(*)
  FROM schedule_derived_artifacts
 GROUP BY engine_version, is_stale
 ORDER BY engine_version;
-- Expected: 4.0 / TRUE / 88; new rows arrive at 4.1.0 / FALSE.
```

### Smoke test runtime

After either option:

```bash
# Pick one project from pre-flight #3.
curl https://api.meridianiq.vitormr.dev/api/v1/lifecycle/<project_id> \
  -H "Authorization: Bearer <user-jwt>"
# Expected 200 with payload (re-materialized OR served-from-stale-allowed-flag).
```

### Rollback

For Option A: restore from `schedule_derived_artifacts_backup_20260427`:

```sql
INSERT INTO schedule_derived_artifacts
SELECT * FROM schedule_derived_artifacts_backup_20260427
   ON CONFLICT DO NOTHING;
```

For Option B: rollback the UPDATE:

```sql
UPDATE schedule_derived_artifacts
   SET is_stale = FALSE, stale_reason = NULL
 WHERE engine_version = '4.0';
```

### Registry

Comment on the new tracking issue (or [#25](https://github.com/VitorMRodovalho/meridianiq/issues/25) meta) with:

1. Pre-flight diagnostics output
2. Backup table name + row count
3. Choice: A vs B + rationale
4. Execution log (re-mat stdout OR migration apply log)
5. Post-execution verification output
6. Operator + reviewer names + timestamp

Close the new tracking issue with `state_reason: completed`. Update [`docs/ROADMAP.md`](../ROADMAP.md) §"Cycle 3" wave table W4 row from "OPEN — operator decision" to "DONE at YYYY-MM-DD (option A/B)".

---

## Common appendix

### Where to log results

| Item | Primary | Secondary |
|---|---|---|
| W1 prod migration | Comment on #26 + close it | Update ROADMAP W1 row |
| W2-A ratification | Comment on #28 (per ADR) + close after all 5 | Update ROADMAP W2 row |
| W2-B manifest archive | Comment on #25 (meta-tracking) | Update ROADMAP W2 row |
| W4 re-mat / tombstone | Comment on new tracking issue + close it | Update ROADMAP W4 row |

After each closure, also update:

- `docs/ROADMAP.md` §"Last refreshed" header with new date + criterion-count
- `project_resume_next_session.md` user memory pointing at the next deliverable
- `project_v40_cycle_3.md` user memory criterion-scoreboard

### Failure modes shared across runbooks

- **`pg_advisory_lock` deadlock during DDL:** kill long-running connections via Supabase dashboard → "Database" → "Query Performance" → terminate offenders. Re-attempt apply.
- **Supabase rate-limit on SQL editor:** wait 60 s, re-attempt. CLI path (`supabase db push`) bypasses the editor rate-limit.
- **Backup table consumes pooler connection budget:** `DROP TABLE` the backup after the 30-day retention period; Supabase free tier has a small connection pool.

### Cycle 3 success criteria scoreboard (post-execution)

If all four runbooks execute successfully:

| # | Criterion | Pre-runbook | Post-runbook |
|---|---|---|---|
| 1 | Audit re-run | ✅ | ✅ |
| 2 | #26 prod migration | OPEN | ✅ |
| 3 | #28 ratification | OPEN | ✅ |
| 4 | W4 manifest archive | OPEN | ✅ |
| 5 | W3 reproduction test | ✅ | ✅ |
| 6 | _ENGINE_VERSION → __about__ | ✅ code-side | ✅ |
| 7 | 88-row re-mat | OPEN | ✅ |
| 8 | (optional) W5 spike | NOT STARTED | NOT STARTED |
| 9 | Release tag | NOT STARTED | next session |

**3/9 → 7/9 closed.** Past the ADR-0021 graceful threshold (≥5/9). Ready for v4.2.0 release tag (or v4.1.1 if W5 drops).

### Standing protocol for runbook updates

If during execution the operator discovers the runbook is wrong, incomplete, or misleading:

1. Open a small PR with the correction.
2. Per ADR-0018 Amendment 1 (PR-level cadence), this PR invokes the protocol if the change is substantive (e.g., a SQL command was wrong). Skip-exception applies if the change is purely cosmetic (e.g., typo).
3. Comment on the closure issue with a link to the corrective PR so the audit trail is complete.

— End of Cycle 3 operator runbooks.
