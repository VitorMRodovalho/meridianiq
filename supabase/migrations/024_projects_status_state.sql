-- 024_projects_status_state.sql
--
-- Cycle 1 v4.0 Wave 2: projects.status state machine closing the phased
-- atomicity commitment of ADR-0012 (option d→c) and providing the state
-- surface the async materializer (ADR-0015) writes through.
--
-- Specification sources:
--   - ADR-0009 (Cycle 1 Lifecycle Intelligence — Wave 2 scope)
--   - ADR-0012 (schedule persistence atomicity — closing option (c))
--   - ADR-0015 (async materialization + state machine — canonical for Wave 2)
--
-- Composition with earlier migrations:
--   - 018 (schedule_persistence): FK topology with ON DELETE CASCADE per
--     child table; ADR-0012's compensating-DELETE relied on that topology.
--     Wave 2 retires the compensating DELETE in favour of UPDATE status;
--     CASCADE remains as defence-in-depth in case a future path reinstates
--     the delete semantics.
--   - 023 (schedule_derived_artifacts): the async materializer writes
--     per-engine artifact rows here and flips projects.status to 'ready'
--     on success or 'failed' on any persist/materialize failure. The
--     chk_stale_reason_consistency and input_hash contracts from 023
--     compose cleanly with the state flip — no cross-table CHECK needed.
--
-- Design notes (per ADR-0015):
--   - TEXT + CHECK, not Postgres ENUM. Matches the pattern already used
--     in schedule_derived_artifacts (artifact_kind, stale_reason). ENUM
--     value addition via `ALTER TYPE ... ADD VALUE` is transaction-
--     unfriendly and not justified for a three-value set.
--   - DEFAULT 'ready' backfills every existing row inside this migration
--     transaction. All projects present at apply time have already
--     survived the historical persist path, so 'ready' is the correct
--     initial value — they need no materialization to be trusted; the
--     backfill worker (ADR-0015 §6) is what fills in their artifact rows.
--   - Migration 024 and the code edits that pass status='pending' in
--     save_project + flip _persist_schedule_data from DELETE to UPDATE
--     are part of the SAME commit. A migration applied without the code
--     edit would leave new rows at DEFAULT 'ready' during the pending
--     window — which is wrong. A code edit applied without the migration
--     would reference a missing column. Atomic ship is the only safe
--     order.
--   - The partial index on (user_id, status) WHERE status='ready' is
--     load-bearing for the hot read path: every user-scoped project
--     listing filters to 'ready' by default. Owner-view and admin paths
--     pass include_all_statuses=True and accept a seq scan over the
--     small per-user subset.

-- ================================================================
-- 1. Status column with default + CHECK
-- ================================================================

ALTER TABLE public.projects
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL
        DEFAULT 'ready'
        CHECK (status IN ('pending', 'ready', 'failed'));

COMMENT ON COLUMN public.projects.status IS
    'Lifecycle state of the project. ''pending'' during upload + materialization; ''ready'' once the async materializer has persisted all expected artifact kinds (see schedule_derived_artifacts); ''failed'' if any step of the persist chain or materializer chain raised. Forensic: failed rows are retained (ADR-0012 d→c flip) so re-materialization is a recovery, not a re-upload. See ADR-0015 for the state machine and re-hash protection contract.';

-- ================================================================
-- 2. Hot-path partial index — default reads filter status='ready'
-- ================================================================

CREATE INDEX IF NOT EXISTS idx_projects_ready_by_user
    ON public.projects (user_id, created_at DESC)
    WHERE status = 'ready';

COMMENT ON INDEX public.idx_projects_ready_by_user IS
    'Hot path for user-scoped project listings filtered to status=ready. Owner-view and admin callers that need non-ready rows bypass this index with include_all_statuses=True.';

-- ================================================================
-- 3. Reload PostgREST schema cache
-- ================================================================
NOTIFY pgrst, 'reload schema';
