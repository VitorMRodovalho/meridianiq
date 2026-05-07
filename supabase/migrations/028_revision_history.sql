-- 028_revision_history.sql
--
-- Cycle 4 v4.2 W1 — B-subset core schema (per ADR-0022 §"Wave plan W1").
--
-- Adds:
--   1. ``projects.revision_date`` (TIMESTAMPTZ, NULL-permissive) — wall-clock
--      upload-ordering hint, distinct from ``projects.data_date`` (which is
--      the schedule effective date sourced from XER ``proj.last_recalc_date``
--      or ``proj.sum_data_date``). Both can lag the other by months on a
--      stale-XER re-import.
--   2. ``revision_history`` table — append-only revision lifecycle for
--      projects. Each row models one schedule revision tied to a project.
--      Soft-tombstone columns (``tombstoned_at`` + ``tombstoned_reason``)
--      ship in this migration even though the W2 confirmation UX wires
--      detection / write contracts (HB-C: columns at W1, enforcement at W2).
--   3. ``revision_history`` cap enforcement via BEFORE INSERT trigger that
--      raises 23P01 when an insert would cross the per-project active-revision
--      cap. Cap value is hardcoded at 12 in this migration (per backend-
--      reviewer entry-council fix-up — Postgres ``ALTER DATABASE ... SET``
--      has zero precedent in this repo, so introducing a GUC pattern for an
--      app-policy concern is the wrong layer; bumping the cap requires a new
--      migration revising the trigger function — explicit and auditable).
--   4. Append-only mutation guard via BEFORE UPDATE trigger that blocks any
--      column change other than ``tombstoned_at`` / ``tombstoned_reason``
--      (ADR-0022 §"revision_history append-only" + backend-reviewer Q2).
--   5. RLS quadruple SELECT / INSERT / UPDATE / DELETE on ``revision_history``
--      mirroring migration 023 pattern. SELECT additionally filters
--      ``tombstoned_at IS NULL`` so RLS-respecting reads default-hide
--      tombstones (HB-C contract — no application-level filter needed).
--
-- ADR notes:
--   - ADR-0022 §W1 text describes a CHECK constraint enforcing the cap.
--     PostgreSQL CHECK constraints cannot reference subqueries on the same
--     table (or any other table) — the listed CHECK syntax is invalid SQL.
--     The substitute is a BEFORE INSERT trigger which DOES bind service_role
--     inserts (no ``session_replication_role`` precedent in repo, verified
--     clean). Same DB-level enforcement contract; correct mechanism.
--   - ADR-0022 §"Storage cap behavior at limit" originally specified
--     ``MAX_REVISIONS_PER_PROJECT`` as env-configurable. The cap value
--     in this trigger is hardcoded (``v_max_revisions CONSTANT INT := 12``)
--     instead — bumping the cap requires a new migration revising this
--     function. Codified as ADR-0022 Amendment 1 (this PR).
--
-- ⚠ STAGING-FIRST APPLY required (DA exit-council fix-up #P1-2):
--   This migration ships untested SQL — the AST regression test in
--   ``tests/test_rls_policy.py`` validates source-text shape, NOT actual
--   Postgres acceptance. A typo in the trigger function bodies would
--   surface only at production deploy time, mid-statement, leaving
--   ``projects.revision_date`` ADDED but ``revision_history`` half-created.
--   Operator MUST apply this migration to staging Supabase first, verify:
--     1. ``revision_history`` table exists with all 9 columns
--     2. RLS quadruple is in place (4 policies on revision_history)
--     3. Both triggers fire under test inserts
--     4. Cap enforcement works under concurrent inserts (advisory lock
--        per fix-up #P1-1)
--   Then promote to production. Integration-test framework is a Cycle 5+
--   structural deliverable (issue filed at PR open).
--
-- Scope NOT in this migration:
--   - W2 confirmation UX backend (POST /api/v1/projects/{id}/detect-revision-of)
--   - W2 soft-tombstone audit_log entry
--   - Backfill of revision_history rows for the existing ~88 production
--     projects: deferred. Backfill requires reading every XER blob from
--     Storage to compute ``content_hash``; operator-paced (Cycle 4 W5 or
--     Cycle 5+). Until then existing projects are "pre-history" — no
--     revision_history rows; W2 detection runs for NEW uploads only.
--
-- Composition with earlier migrations:
--   - 001 / 004: ``projects.data_date`` already exists; this migration only
--     adds ``revision_date``.
--   - 020: ``projects.program_id`` + ``projects.revision_number`` exist
--     since v3.5; ``revision_history.revision_number`` mirrors that
--     numbering for parity but is owned by this table thereafter.
--   - 022: ``programs UNIQUE(user_id, lower(name))`` + upsert RPC.
--   - 023: RLS quadruple pattern of reference; tombstone CHECK is a
--     point-in-time-event variant of 023's ``is_stale`` boolean state
--     (see chk_tombstone_consistency below).

-- ================================================================
-- 1. projects.revision_date
-- ================================================================

ALTER TABLE public.projects
    ADD COLUMN IF NOT EXISTS revision_date TIMESTAMPTZ;

COMMENT ON COLUMN public.projects.revision_date IS
    'Wall-clock at upload time when this project row was registered. Distinct from ``data_date`` (schedule effective date sourced from XER ``proj.last_recalc_date`` / ``proj.sum_data_date``); the two can diverge by months on stale-XER re-imports. Use ``revision_date`` for ordering successive uploads when ``data_date`` is unreliable. NULL permitted for legacy rows pre-Cycle-4-W1 (operator-paced backfill).';

-- B-tree index on (program_id, revision_date DESC NULLS LAST) supports the
-- W2 program-revisions-list query. Full index (no partial WHERE) per backend
-- reviewer entry-council recommendation: anonymous-upload row population is
-- not a measured hot path; partial-index gain isn't justified at W1 sizes.
CREATE INDEX IF NOT EXISTS idx_projects_revision_date
    ON public.projects (program_id, revision_date DESC NULLS LAST);

-- ================================================================
-- 2. revision_history table
-- ================================================================

CREATE TABLE IF NOT EXISTS public.revision_history (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    revision_number     INTEGER NOT NULL CHECK (revision_number >= 0),
    -- Schedule effective date snapshot — mirrors ``projects.data_date``
    -- nullability. Future dates are not forbidden (plan-only schedules with
    -- NTP-future data_date are legitimate).
    data_date           TIMESTAMPTZ,
    -- Promoted-to-baseline-of-record marker. Nullable. W1 ships the column
    -- unenforced; W2 confirmation UX writes the timestamp when a user
    -- promotes a revision. Documented here so a future reviewer doesn't
    -- mistake the absence of W2 logic for a missing W1 deliverable.
    baseline_lock_at    TIMESTAMPTZ,
    -- sha256 hex of project-scoped XER bytes. Same format as
    -- ``schedule_derived_artifacts.input_hash`` (ADR-0014) but the canonical
    -- semantics differ — that's a hash of canonical-JSON over the parsed
    -- schedule slice; this is a hash of the raw XER bytes for the project.
    -- Storage shape (sha256 hex 64 chars) and validating regex are identical.
    content_hash        TEXT NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    -- Soft-tombstone columns (HB-C). NULL active; non-null tombstoned. Both
    -- columns must move together (chk_tombstone_consistency below).
    -- ``tombstoned_reason`` length capped at 500 chars (DA exit-council
    -- fix-up #P2-5 — defends against write-amplification DoS via large
    -- TOAST'd payloads).
    tombstoned_at       TIMESTAMPTZ,
    tombstoned_reason   TEXT CHECK (tombstoned_reason IS NULL OR length(tombstoned_reason) <= 500),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Tombstone consistency: both NULL (active) or both non-NULL (tombstoned).
    -- Mirrors migration 023's ``chk_stale_reason_consistency`` pattern; here
    -- the trigger event is point-in-time (timestamp) rather than a state
    -- transition (boolean) — different vocabulary for different lifecycle
    -- semantics.
    CONSTRAINT chk_tombstone_consistency CHECK (
        (tombstoned_at IS NULL AND tombstoned_reason IS NULL) OR
        (tombstoned_at IS NOT NULL AND tombstoned_reason IS NOT NULL)
    ),

    -- Append-only identity tuple. NULLS NOT DISTINCT (PG15+, Supabase runs
    -- PG15) means two rows with the same (project_id, revision_number, NULL)
    -- collide — preventing two simultaneous active revisions with the same
    -- number. After tombstoning, a new revision can re-use the number because
    -- the tombstone timestamps differ, making the tuple distinct.
    --
    -- Caveat: if a caller ever tombstones twice in the same transaction at
    -- the cached ``now()`` timestamp, the timestamps would collide — use
    -- ``clock_timestamp()`` for multi-tombstone code paths to avoid this
    -- (W2 confirmation UX is single-tombstone-per-request, so safe; future
    -- bulk tombstone tooling must use ``clock_timestamp()``).
    CONSTRAINT uq_revision_active_identity UNIQUE NULLS NOT DISTINCT (
        project_id, revision_number, tombstoned_at
    )
);

COMMENT ON TABLE public.revision_history IS
    'Append-only revision lifecycle for projects. Cycle 4 v4.2 W1 per ADR-0022 §"B-subset core schema". One row per schedule revision tied to a project. ``tombstoned_at``/``tombstoned_reason`` enable soft-delete on mis-grouping (W2 confirmation UX); RLS SELECT policy filters ``tombstoned_at IS NULL`` so default reads are tombstone-hidden (no application-level filter needed).';

COMMENT ON COLUMN public.revision_history.baseline_lock_at IS
    'Promoted-to-baseline-of-record timestamp. NULL until W2 confirmation UX promotes this revision. W1 ships column unenforced.';

COMMENT ON COLUMN public.revision_history.content_hash IS
    'sha256 hex of project-scoped XER bytes (or canonical equivalent for non-XER inputs). Same storage shape as ``schedule_derived_artifacts.input_hash`` (ADR-0014) but the canonical semantics differ — that hash is over canonical-JSON of the parsed schedule; this hash is over the raw bytes. Use to detect that two uploads are byte-equivalent revisions of the same schedule.';

COMMENT ON CONSTRAINT uq_revision_active_identity ON public.revision_history IS
    'Append-only via NULLS NOT DISTINCT. Two rows can share (project_id, revision_number) only if tombstone timestamps differ. See migration prose for the multi-tombstone-in-one-transaction caveat (use clock_timestamp() not now()).';

-- ================================================================
-- 3. Indices
-- ================================================================

-- Hot read path: latest active revision per project.
CREATE INDEX IF NOT EXISTS idx_revision_history_project_active
    ON public.revision_history (project_id, revision_number DESC)
    WHERE tombstoned_at IS NULL;

-- Data-date timeline view: the W2/W3 multi-rev S-curve overlay reads
-- revisions ordered by data_date for the chart x-axis.
CREATE INDEX IF NOT EXISTS idx_revision_history_project_data_date
    ON public.revision_history (project_id, data_date DESC NULLS LAST)
    WHERE tombstoned_at IS NULL;

-- ================================================================
-- 4. Cap enforcement trigger
-- ================================================================
--
-- ADR-0022 §"Storage cap behavior at limit" + NFM-6/7: per-project cap on
-- active (non-tombstoned) revisions. Default 12. Enforced at the DB layer
-- so service_role inserts are bound (the materializer's background-task
-- writes go through the same path).
--
-- Postgres CHECK constraints cannot reference subqueries — the ADR text's
-- literal CHECK syntax is invalid SQL. Trigger is the correct substitute
-- and DOES fire under service_role (no ``session_replication_role``
-- precedent in this repo, verified across src/ and supabase/).
--
-- ``MAX_REVISIONS_PER_PROJECT`` env var on the app side is documented in
-- ``.env.example`` for backend reference; the DB-level value is hardcoded
-- here. Bumping the cap requires a new migration revising this function —
-- explicit, atomic, version-controlled. If runtime-tunability becomes a
-- demand-validated need, a ``system_settings`` table read by the trigger
-- is more idiomatic than a Postgres GUC (per backend-reviewer guidance).

CREATE OR REPLACE FUNCTION public.enforce_revision_cap()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_max_revisions CONSTANT INT := 12;
    v_active_count  INT;
BEGIN
    -- Only enforce on inserts of ACTIVE rows (tombstoned_at IS NULL).
    -- Inserting a pre-tombstoned row would be unusual but allowed (e.g.,
    -- migration backfill of historical record).
    IF NEW.tombstoned_at IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Per-project advisory lock to prevent TOCTOU race under concurrent
    -- INSERTs (DA exit-council fix-up #P1-1). Default isolation is
    -- READ COMMITTED — without serialization, two concurrent inserts at
    -- count=11 both observe 11, both pass the cap check, both INSERT,
    -- final count=13. The lock auto-releases at transaction end. Hash
    -- the project UUID to fit the bigint key space; collisions on
    -- different project UUIDs are harmless (just spurious serialization).
    PERFORM pg_advisory_xact_lock(hashtext('revision_history.cap.' || NEW.project_id::text));

    SELECT COUNT(*) INTO v_active_count
      FROM public.revision_history
     WHERE project_id = NEW.project_id
       AND tombstoned_at IS NULL;

    IF v_active_count >= v_max_revisions THEN
        RAISE EXCEPTION
            'Project % has reached revision cap (%). Tombstone an existing revision OR raise the cap via a new migration revising public.enforce_revision_cap (Cycle 5+ archive process not yet shipped).',
            NEW.project_id, v_max_revisions
            USING ERRCODE = '23P01';  -- invalid_state
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_revision_history_cap ON public.revision_history;
CREATE TRIGGER trg_revision_history_cap
    BEFORE INSERT ON public.revision_history
    FOR EACH ROW EXECUTE FUNCTION public.enforce_revision_cap();

COMMENT ON FUNCTION public.enforce_revision_cap IS
    'Per-project active-revision cap (default 12). Raises 23P01 invalid_state on cap violation. Binds service_role inserts. ADR-0022 §"Storage cap behavior at limit" + NFM-6/7.';

-- ================================================================
-- 5. Append-only mutation guard
-- ================================================================
--
-- Append-only contract: the only legitimate UPDATE on revision_history is
-- a tombstone transition (writing tombstoned_at + tombstoned_reason). Any
-- other column change indicates application-layer drift; surface as 23P01
-- so the offending code path fails loudly during the same cycle, not in a
-- forensic post-mortem six months later.
--
-- Allowed transitions:
--   - tombstoned_at NULL → non-NULL (with corresponding tombstoned_reason)
--   - tombstoned_at non-NULL → NULL (un-tombstone within grace window)
--   - tombstoned_reason text edits (allowed alongside the timestamp move)
-- Disallowed:
--   - mutating revision_number, data_date, baseline_lock_at, content_hash,
--     project_id, id, created_at on an existing row

CREATE OR REPLACE FUNCTION public.enforce_revision_history_append_only()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Tuple comparison for the immutable column set (DA exit-council
    -- fix-up #P2-6 — atomic check; harder for a future contributor to
    -- silently let a column slip through by dropping one IF guard).
    IF (NEW.id, NEW.project_id, NEW.revision_number, NEW.data_date, NEW.content_hash, NEW.created_at)
        IS DISTINCT FROM
       (OLD.id, OLD.project_id, OLD.revision_number, OLD.data_date, OLD.content_hash, OLD.created_at)
    THEN
        RAISE EXCEPTION
            'revision_history rows are append-only; only baseline_lock_at, tombstoned_at, tombstoned_reason are mutable'
            USING ERRCODE = '23P01';
    END IF;

    -- baseline_lock_at sanity (DA exit-council fix-up #P2-4). NULL is
    -- allowed (unset). Future-dated values would let a buggy or
    -- malicious caller fake a promotion to a date that hasn't arrived
    -- yet. clock_timestamp() (NOT cached now()) so a long-running
    -- transaction can't inadvertently set a baseline 30 minutes in
    -- the future.
    IF NEW.baseline_lock_at IS NOT NULL
       AND NEW.baseline_lock_at > clock_timestamp() THEN
        RAISE EXCEPTION
            'revision_history.baseline_lock_at cannot be in the future (baseline lock is wall-clock now)'
            USING ERRCODE = '23P01';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_revision_history_append_only ON public.revision_history;
CREATE TRIGGER trg_revision_history_append_only
    BEFORE UPDATE ON public.revision_history
    FOR EACH ROW EXECUTE FUNCTION public.enforce_revision_history_append_only();

COMMENT ON FUNCTION public.enforce_revision_history_append_only IS
    'Enforces append-only contract on revision_history. UPDATE may only mutate baseline_lock_at, tombstoned_at, tombstoned_reason. Any other column change raises 23P01. ADR-0022 §"revision_history append-only" + backend-reviewer entry-council Q2.';

-- ================================================================
-- 6. RLS quadruple
-- ================================================================
--
-- Pattern from migration 023. SELECT additionally filters
-- ``tombstoned_at IS NULL`` so default reads are tombstone-hidden — HB-C
-- contract enforced at the DB layer, not the application layer.
-- INSERT/UPDATE/DELETE policies do NOT filter tombstones (UPDATE on a
-- tombstoned row to edit ``tombstoned_reason`` is a legitimate W2 path).

ALTER TABLE public.revision_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "rh_select_own_active" ON public.revision_history;
CREATE POLICY "rh_select_own_active" ON public.revision_history
    FOR SELECT USING (
        tombstoned_at IS NULL
        AND project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "rh_insert_own" ON public.revision_history;
CREATE POLICY "rh_insert_own" ON public.revision_history
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "rh_update_own" ON public.revision_history;
CREATE POLICY "rh_update_own" ON public.revision_history
    FOR UPDATE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    ) WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "rh_delete_own" ON public.revision_history;
CREATE POLICY "rh_delete_own" ON public.revision_history
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- ================================================================
-- 7. Reload PostgREST schema cache
-- ================================================================
NOTIFY pgrst, 'reload schema';
