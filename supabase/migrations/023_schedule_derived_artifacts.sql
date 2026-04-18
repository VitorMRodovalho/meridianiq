-- 023_schedule_derived_artifacts.sql
--
-- Cycle 1 v4.0 Wave 1 foundation for ingest-time materialization of
-- schedule derivatives (DCMA, health score, CPM paths, float trends,
-- lifecycle_health conditional on W4 gate).
--
-- Specification sources:
--   - ADR-0009 (Cycle 1 Lifecycle Intelligence — Wave 1 scope)
--   - ADR-0014 (derived-artifact provenance — hash canonicalization and
--               column shape; accepted 2026-04-18 post-Wave-1 council)
--
-- Composition with earlier migrations:
--   - 018 (schedule_persistence): RLS pattern template — SELECT/INSERT/
--     UPDATE/DELETE policies re-verify ownership via projects.user_id.
--     No `WITH CHECK (TRUE)` anywhere. Differs from 018 by adding an
--     UPDATE policy (ADR-0014 requirement for mark_stale under
--     authenticated role — closes the ADR-0012 amendment #2 silent-no-op
--     pattern class).
--   - ADR-0012 compensating DELETE on projects: schedule_derived_artifacts
--     declares ON DELETE CASCADE on project_id so that mid-persist failure
--     rollback composes cleanly with any artifact rows that Wave 2 would
--     write post-persist.
--
-- Forensic contract (ADR-0014):
--   input_hash = sha256_hex(canonical_json(project_scoped_parsed_schedule))
--   implementation: src/database/canonical_hash.py::compute_input_hash
--   DO NOT change that helper without authoring a superseding ADR —
--   changing the canonical-json algorithm silently invalidates every
--   historical hash and breaks forensic reproducibility.

-- ================================================================
-- 1. Table
-- ================================================================

CREATE TABLE IF NOT EXISTS public.schedule_derived_artifacts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    artifact_kind   TEXT NOT NULL CHECK (artifact_kind IN (
                        'dcma', 'health', 'cpm', 'float_trends', 'lifecycle_health'
                    )),
    payload         JSONB NOT NULL,
    engine_version  TEXT NOT NULL,
    ruleset_version TEXT NOT NULL,
    input_hash      TEXT NOT NULL
                        CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    effective_at    TIMESTAMPTZ NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    computed_by     UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    is_stale        BOOLEAN NOT NULL DEFAULT false,
    stale_reason    TEXT CHECK (stale_reason IN (
                        'input_changed', 'engine_upgraded', 'ruleset_upgraded', 'manual'
                    )),
    CONSTRAINT uq_artifact_identity UNIQUE NULLS NOT DISTINCT (
        project_id, artifact_kind, engine_version, ruleset_version, input_hash
    ),
    CONSTRAINT chk_stale_reason_consistency CHECK (
        (is_stale = false AND stale_reason IS NULL) OR
        (is_stale = true  AND stale_reason IS NOT NULL)
    )
);

COMMENT ON TABLE public.schedule_derived_artifacts IS
    'Materialized schedule-analysis artifacts (DCMA, health, CPM, float_trends, lifecycle_health) with forensic provenance. Added 2026-04-18 for Cycle 1 v4.0 Wave 1. See ADR-0009 + ADR-0014.';

COMMENT ON COLUMN public.schedule_derived_artifacts.effective_at IS
    'Effective date (data_date) of the underlying schedule that this artifact speaks to. Renamed from inferred_at per AACE RP 57R §4.1 effective-date naming hygiene. Disambiguates from W3 lifecycle_phase inference vocabulary.';

COMMENT ON COLUMN public.schedule_derived_artifacts.computed_by IS
    'auth.users(id) of the user who triggered materialization. NULL permitted in three cases: (a) system-triggered backfills (W2 engine/ruleset rollover worker); (b) post-user-deletion state where ON DELETE SET NULL cleared the reference to satisfy LGPD Art. 18 IV / GDPR Art. 17 erasure — the paired audit_log row retains the original user_id until a separate retention policy clears it. SCL Protocol 2nd ed §4 chain-of-custody is preserved within the retention window and correctly erased outside it.';

COMMENT ON COLUMN public.schedule_derived_artifacts.input_hash IS
    'sha256 hex digest of canonical JSON of the project-scoped slice of ParsedSchedule. Canonical algorithm defined in ADR-0014 (sorted keys at every nesting level, ISO-8601 UTC microseconds for datetimes, repr() for floats, separators=("," , ":")). Implementation: src/database/canonical_hash.py. Per-project scoping resolves multi-project XER task_id collisions (devils-advocate P1#7).';

COMMENT ON COLUMN public.schedule_derived_artifacts.stale_reason IS
    'Why this artifact became stale. NULL iff is_stale=false (enforced by chk_stale_reason_consistency). Distinguishes auto-recompute-mandatory (input_changed) from judgement-call recompute (engine_upgraded/ruleset_upgraded) per AACE RP 114R Monte Carlo determinism.';

COMMENT ON CONSTRAINT uq_artifact_identity ON public.schedule_derived_artifacts IS
    'Identity tuple for reproducibility. DO NOT add nullable columns into this constraint without thinking through NULLS NOT DISTINCT semantics. PG15+ NULLS NOT DISTINCT is defensive against a future nullable column being added to the tuple and silently creating duplicate rows. See ADR-0014.';

-- ================================================================
-- 2. Indices — two partial, no full-column is_stale
-- ================================================================

-- Hot read path: latest non-stale artifact per (project, kind).
-- get_latest_derived_artifact hits this index under WHERE is_stale=false.
CREATE INDEX IF NOT EXISTS idx_sda_latest_fresh
    ON public.schedule_derived_artifacts (project_id, artifact_kind, computed_at DESC)
    WHERE is_stale = false;

-- Program-level freshness aggregation (Program Director JTBD per ADR-0009).
-- Partial inverts — only stale rows indexed, keeps the index small.
CREATE INDEX IF NOT EXISTS idx_sda_project_stale
    ON public.schedule_derived_artifacts (project_id)
    WHERE is_stale = true;

-- ================================================================
-- 3. RLS quadruple — SELECT / INSERT / UPDATE / DELETE
-- ================================================================
--
-- Pattern mirrors migration 018 with UPDATE added. UPDATE is load-bearing
-- for mark_stale() under the `authenticated` role (MCP plugin HTTP surface
-- per ADR-0006; user-triggered force-recompute UI path). Without UPDATE,
-- PostgREST returns [] + HTTP 200 — silent-no-op (ADR-0012 amendment #2).
--
-- The W2 async materializer runs under `service_role` (background task,
-- no captured JWT) and therefore bypasses RLS for its own writes. The
-- policies below guard the authenticated path.

ALTER TABLE public.schedule_derived_artifacts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "sda_select_own" ON public.schedule_derived_artifacts;
CREATE POLICY "sda_select_own" ON public.schedule_derived_artifacts
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "sda_insert_own" ON public.schedule_derived_artifacts;
CREATE POLICY "sda_insert_own" ON public.schedule_derived_artifacts
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "sda_update_own" ON public.schedule_derived_artifacts;
CREATE POLICY "sda_update_own" ON public.schedule_derived_artifacts
    FOR UPDATE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    ) WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "sda_delete_own" ON public.schedule_derived_artifacts;
CREATE POLICY "sda_delete_own" ON public.schedule_derived_artifacts
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- ================================================================
-- 4. Reload PostgREST schema cache
-- ================================================================
NOTIFY pgrst, 'reload schema';
