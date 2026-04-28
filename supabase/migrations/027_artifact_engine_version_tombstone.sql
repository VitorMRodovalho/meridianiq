-- Migration 027: tombstone legacy engine_version='4.0' artifact rows.
--
-- Cycle 3 W4 OPERATOR-RUN ONLY (Option B per docs/operator-runbooks/cycle3.md §W4).
-- Per ADR-0014 §"Decision Outcome" provenance contract + AUDIT-2026-04-26-007 / -011.
--
-- Issue #54 (operator decision: A bulk re-mat vs B tombstone).
--
-- ⚠ This migration is OPERATOR-DECISION-GATED. It must NOT run automatically.
--   Apply ONLY when the maintainer chose Option B (tombstone) over Option A
--   (bulk re-mat). Option A path: run
--   `python -m src.materializer.backfill --re-materialize-version 4.0` instead.
--
-- ⚠ ORDER-OF-OPERATIONS TRAP (per DA exit-council on PR #58):
--   Option A and Option B silently neutralize each other if applied in
--   the wrong order:
--   - If THIS migration runs FIRST (tombstones rows), then `--re-materialize-
--     version 4.0` is run, the candidate list is EMPTY (filtered to
--     `is_stale=false`). The CLI returns "0 candidates" + rc=0; the
--     operator may think the re-mat succeeded when nothing happened.
--   - The CLI now emits a WARNING in this case via
--     `_diagnose_zero_candidates` pointing at this migration.
--   - PRO-TIP: choose ONE option per cycle. Don't mix.
--
-- ⚠ This migration is FORWARD-ONLY in semantics. The UPDATE flips
--   `is_stale=true` + `stale_reason='engine_upgraded'` on every row whose
--   `engine_version='4.0'` AND is currently fresh (`is_stale=false`).
--   Rollback is via the inverse UPDATE (see operator runbook §W4 →
--   §"Rollback for Option B"); the migration itself stays applied to
--   preserve the audit trail.
--
-- ⚠ Before applying, ensure PR #50 is deployed AND the production schema
--   audit (W1 — migration 026) is complete. Without #50 deployed, the
--   runtime is still writing engine_version='4.0' to new rows; tombstoning
--   them and then having #50 land would cause a brief window where the
--   read-path returns None for everyone.
--
-- Pre-flight diagnostic (run before applying):
--
--   SELECT COUNT(*) AS will_tombstone
--     FROM schedule_derived_artifacts
--    WHERE engine_version = '4.0' AND is_stale = false;
--   -- Expected: ~88 rows per the 2026-04-19 W4 collateral.
--
--   SELECT artifact_kind, COUNT(*)
--     FROM schedule_derived_artifacts
--    WHERE engine_version = '4.0' AND is_stale = false
--    GROUP BY artifact_kind ORDER BY 2 DESC;
--   -- Expected: kinds with ruleset versions matching `_RULESET_VERSIONS`
--   -- in `src/materializer/runtime.py`.

DO $$
DECLARE
    affected_rows INT;
BEGIN
    -- Defensive guard: skip if `is_stale` column doesn't exist (the
    -- ADR-0014 §"is_stale" column was added in migration 023; this guard
    -- handles instances that somehow skipped 023).
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'schedule_derived_artifacts'
          AND column_name = 'is_stale'
    ) THEN
        RAISE NOTICE 'Migration 027: schedule_derived_artifacts.is_stale missing; skipping (run migration 023 first).';
        RETURN;
    END IF;

    -- Tombstone every fresh row at the old engine_version.
    UPDATE schedule_derived_artifacts
       SET is_stale = TRUE,
           stale_reason = 'engine_upgraded'
     WHERE engine_version = '4.0'
       AND is_stale = FALSE;

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RAISE NOTICE 'Migration 027: tombstoned % row(s) at engine_version=4.0', affected_rows;
END $$;

-- Verification (run after applying):
--
--   SELECT engine_version, is_stale, stale_reason, COUNT(*)
--     FROM schedule_derived_artifacts
--    GROUP BY engine_version, is_stale, stale_reason
--    ORDER BY engine_version, is_stale, stale_reason;
--   -- Expected:
--   --   4.0 | true  | engine_upgraded | <88-ish>
--   --   <new>| false | NULL            | <new artifacts as they get materialized>
--
-- Rollback (Option B reversal — reverts the tombstone):
--
--   UPDATE schedule_derived_artifacts
--      SET is_stale = FALSE, stale_reason = NULL
--    WHERE engine_version = '4.0' AND stale_reason = 'engine_upgraded';
--
-- Post-tombstone behavior:
--
--   `get_latest_derived_artifact` already returns None on `is_stale=true`
--   (per `src/database/store.py:789`). Read endpoints will see "no
--   artifact" → trigger re-materialization on first read of every
--   affected project, which writes a fresh row at the current
--   engine_version. The tombstoned 4.0 rows are preserved indefinitely
--   for forensic reproducibility per ADR-0014.
