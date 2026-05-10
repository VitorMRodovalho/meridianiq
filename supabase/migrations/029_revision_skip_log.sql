-- 029_revision_skip_log.sql
--
-- Cycle 5 W3-E — issue #84 (DA P2-3 from PR #83): persistent skip log
-- for revision-confirmation candidates.
--
-- Problem (per frontend-ux-reviewer entry-council on the W3 batch):
--   After the user clicks "Treat as new project" on the revision-
--   confirmation card, there's no UI to reconsider. The card lives only
--   on the upload result page; refresh kills the card. Worse, without
--   server-side skip persistence, every visit to the project surfaces
--   the SAME candidate suggestion forever — `detect_candidate_parent`
--   returns the same heuristic match on every re-detect.
--
-- Solution:
--   1. Persist the skip — one row per (project_id, candidate_project_id,
--      user_id) tuple. Detect endpoint filters out skipped candidates.
--   2. Project-detail page exposes "Confirm as revision of..." action
--      that clears skips for the current project + re-runs detect, so
--      the user can reconsider explicitly.
--
-- Adds:
--   1. ``revision_skip_log`` table — append-only skip ledger. UNIQUE
--      tuple prevents duplicate entries; clear-skips endpoint deletes
--      rows so reconsider is a destructive action (no soft-delete).
--   2. RLS quadruple SELECT / INSERT / UPDATE / DELETE on
--      ``revision_skip_log`` mirroring migration 028 pattern. UPDATE
--      policy is present for symmetry but practically unused — skips
--      are write-once / delete-on-reconsider; mutating ``skipped_at``
--      would be a data-integrity bug.
--   3. B-tree index on ``(project_id, user_id)`` supporting the
--      detect-endpoint filter ("is THIS candidate skipped FOR this
--      project + user").
--
-- Append-only? NOT in this table:
--   ``revision_skip_log`` is a transient ledger (not a domain history)
--   — clearing skips on reconsider is the documented user-facing path.
--   No append-only trigger; DELETE policy is the load-bearing
--   reconsider mechanism.
--
-- ⚠ STAGING-FIRST APPLY:
--   Apply to staging Supabase first per the migration 028 precedent.
--   Verify:
--     1. ``revision_skip_log`` table exists with all 5 columns
--     2. RLS quadruple is in place (4 policies)
--     3. UNIQUE constraint enforces dedup
--     4. RLS-bounded delete works under reconsider call

-- ================================================================
-- 1. revision_skip_log table
-- ================================================================

CREATE TABLE IF NOT EXISTS public.revision_skip_log (
    id                      BIGSERIAL PRIMARY KEY,
    project_id              UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    candidate_project_id    UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    user_id                 UUID NOT NULL,
    skipped_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Prevent duplicate skips for the same (project_id, candidate_id, user_id)
    -- triple. Repeated skip calls from the frontend are idempotent (UPSERT
    -- semantics handled at app layer; ON CONFLICT DO NOTHING in the store
    -- helper).
    CONSTRAINT uq_revision_skip_log_triple UNIQUE (project_id, candidate_project_id, user_id),

    -- Self-skip is meaningless (project cannot be its own revision parent).
    CONSTRAINT chk_revision_skip_not_self CHECK (project_id <> candidate_project_id)
);

COMMENT ON TABLE public.revision_skip_log IS
    'Per-user skip ledger for revision-confirmation candidates. Cycle 5 W3-E per issue #84. One row per (project_id, candidate_project_id, user_id) — detect endpoint filters skipped candidates so users are not nagged with the same suggestion forever. Reconsider clears rows for a project (no soft-delete; DELETE policy is the load-bearing reconsider mechanism).';

COMMENT ON CONSTRAINT chk_revision_skip_not_self ON public.revision_skip_log IS
    'A project cannot be its own revision parent — self-skip rows would be defects. Cheap defense-in-depth.';

-- ================================================================
-- 2. Indices
-- ================================================================

-- Hot read path: detect-endpoint filter ("is candidate skipped FOR this
-- project + user"). The UNIQUE constraint above also enforces
-- (project_id, candidate_project_id, user_id) which would serve queries
-- on the full triple, but the filter query reads (project_id, user_id)
-- to fetch ALL skipped candidates for a project. Separate B-tree index
-- on the partial key supports that read pattern at low write-amplification
-- cost (skip writes are rare — operator-paced UI clicks, not bulk).
CREATE INDEX IF NOT EXISTS idx_revision_skip_log_project_user
    ON public.revision_skip_log (project_id, user_id);

-- ================================================================
-- 3. RLS quadruple
-- ================================================================
--
-- Pattern from migrations 023 + 028. All four policies bind the
-- subject to projects.user_id = auth.uid() — skip rows are owned by
-- the user who skipped (NOT the project owner, in case future multi-
-- tenant features expose shared projects).

ALTER TABLE public.revision_skip_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rsl_select_own" ON public.revision_skip_log;
CREATE POLICY "rsl_select_own" ON public.revision_skip_log
    FOR SELECT USING (
        user_id = auth.uid()
        AND project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "rsl_insert_own" ON public.revision_skip_log;
CREATE POLICY "rsl_insert_own" ON public.revision_skip_log
    FOR INSERT WITH CHECK (
        user_id = auth.uid()
        AND project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
        AND candidate_project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "rsl_update_own" ON public.revision_skip_log;
CREATE POLICY "rsl_update_own" ON public.revision_skip_log
    FOR UPDATE USING (
        user_id = auth.uid()
        AND project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    ) WITH CHECK (
        user_id = auth.uid()
        AND project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "rsl_delete_own" ON public.revision_skip_log;
CREATE POLICY "rsl_delete_own" ON public.revision_skip_log
    FOR DELETE USING (
        user_id = auth.uid()
        AND project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- ================================================================
-- 4. Reload PostgREST schema cache
-- ================================================================
NOTIFY pgrst, 'reload schema';
