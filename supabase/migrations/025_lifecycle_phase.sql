-- 025_lifecycle_phase.sql
--
-- Cycle 1 v4.0 Wave 3: lifecycle_phase metadata + inference + override log.
--
-- Specification sources:
--   - ADR-0009 (Cycle 1 Lifecycle Intelligence — Wave 3 scope)
--   - ADR-0016 (W3 lifecycle_phase inference + override log + lock-flag contract)
--   - ADR-0014 (derived-artifact provenance — reused for the inference artifact
--               via a new artifact_kind value)
--
-- Composition with earlier migrations:
--   - 023 (schedule_derived_artifacts): the W3 inference engine writes its
--     output here as a NEW artifact_kind='lifecycle_phase_inference' row,
--     reusing the forensic provenance contract (engine_version,
--     ruleset_version, input_hash, computed_by, effective_at) without a
--     parallel table. ADR-0016 §1 rejects (b) per-column-on-projects and (c)
--     standalone-assignments-table on duplication grounds.
--   - 024 (projects.status state machine): the lifecycle_phase_locked flag
--     added below composes with status — when locked=true, the materializer
--     skips the lifecycle_phase_inference engine but still flips status to
--     'ready' as long as the other engines succeed (DCMA / health / CPM).
--
-- Design notes (per ADR-0016):
--
--   - The CHECK list on schedule_derived_artifacts.artifact_kind is extended
--     with 'lifecycle_phase_inference' (not 'lifecycle_phase' alone — the
--     '_inference' suffix is intentional to distinguish the W3 lightweight
--     phase label from the W5/W6 conditional 'lifecycle_health' deep engine
--     output that is already reserved in the CHECK list from migration 023).
--     CHECK constraint replacement requires DROP + ADD; ALTER CHECK is not a
--     PostgreSQL operation. The table is small at apply time (W2 just shipped),
--     so the validation pass is cheap.
--
--   - lifecycle_phase_locked BOOLEAN on projects: Cost Engineer JTBD —
--     when an override is recorded, this flag flips to true and the
--     materializer skips re-inference on subsequent uploads. Revert (DELETE
--     /override) flips it back to false and the next materializer run
--     re-emits an inference artifact. NOT NULL DEFAULT false makes every
--     existing row safe; the flag has no meaning for legacy rows.
--
--   - lifecycle_override_log is APPEND-ONLY by RLS convention: there is NO
--     UPDATE policy and NO DELETE policy. Under the authenticated path, all
--     mutation attempts on existing rows return [] / 200 OK silently
--     (PostgREST behaviour absent a matching policy), which is the desired
--     forensic property — the log records every override decision in
--     chronological order without retroactive editing. The service_role
--     bypasses RLS by design (background workers, CASCADE cleanup), so a
--     trigger-based EXCEPTION enforcement would over-engineer the threat
--     model and break the LGPD Art.18 IV erasure path.
--
--   - The override row carries engine_version + ruleset_version columns that
--     pin which inference algorithm version the user was looking at when
--     they overrode. Without these, an override from W3/v1 looks identical
--     to an override from a future W6/v2 — forensic ambiguity. AACE RP 14R
--     §3 + ISO 21502 §6.3 cited in ADR-0016 for the lifecycle taxonomy;
--     SCL Protocol §4 cited for the chain-of-custody on the override log.
--
--   - inferred_phase is NULLABLE: a user may override before any inference
--     has run (edge case — fresh project where the materializer is still
--     pending). The API layer guards against this by returning 409 (per BR
--     P1#7) but the schema does not enforce it; defending in two layers
--     would couple the schema to a UX policy that may evolve.
--
--   - override_phase + projects.lifecycle_phase_locked share the same
--     5-phase + unknown CHECK constraint vocabulary
--     ('planning','design','procurement','construction','closeout','unknown')
--     so engine ↔ UI ↔ DB cannot drift silently (PV P1#taxonomy-drift).
--
--   - ON DELETE CASCADE on lifecycle_override_log.project_id mirrors the
--     pattern from migration 023 schedule_derived_artifacts: the override
--     log is derived project data, not standalone evidence; LGPD project
--     erasure removes both. ON DELETE SET NULL on overridden_by
--     (auth.users FK) preserves the audit trail when a user account is
--     deleted but the project remains.

-- ================================================================
-- 1. CHECK list extension on schedule_derived_artifacts.artifact_kind
-- ================================================================

ALTER TABLE public.schedule_derived_artifacts
    DROP CONSTRAINT IF EXISTS schedule_derived_artifacts_artifact_kind_check;

ALTER TABLE public.schedule_derived_artifacts
    ADD CONSTRAINT schedule_derived_artifacts_artifact_kind_check
        CHECK (artifact_kind IN (
            'dcma',
            'health',
            'cpm',
            'float_trends',
            'lifecycle_health',
            'lifecycle_phase_inference'
        ));

COMMENT ON CONSTRAINT schedule_derived_artifacts_artifact_kind_check
    ON public.schedule_derived_artifacts IS
    'Valid artifact kinds. ''lifecycle_phase_inference'' added in migration 025 (Cycle 1 v4.0 W3, ADR-0016) for the lightweight phase-label inference engine. ''lifecycle_health'' remains reserved for the W5/W6 conditional deep engine (ADR-0009 W5-6 branch).';

-- ================================================================
-- 2. projects.lifecycle_phase_locked — Cost Engineer override-stickiness
-- ================================================================

ALTER TABLE public.projects
    ADD COLUMN IF NOT EXISTS lifecycle_phase_locked BOOLEAN NOT NULL
        DEFAULT false;

COMMENT ON COLUMN public.projects.lifecycle_phase_locked IS
    'When true, the async materializer (ADR-0015) skips the lifecycle_phase_inference engine for this project on subsequent uploads. Flipped to true by POST /api/v1/projects/{id}/lifecycle/override; flipped back to false by DELETE /api/v1/projects/{id}/lifecycle/override (which preserves the override log rows). Cost Engineer JTBD per ADR-0016: when ERP-reported phase is the source-of-truth, the inference must not silently overwrite the user''s decision on the next data-date refresh.';

-- ================================================================
-- 3. lifecycle_override_log — append-only manual override log
-- ================================================================

CREATE TABLE IF NOT EXISTS public.lifecycle_override_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    inferred_phase  TEXT
                        CHECK (inferred_phase IS NULL OR inferred_phase IN (
                            'planning', 'design', 'procurement',
                            'construction', 'closeout', 'unknown'
                        )),
    override_phase  TEXT NOT NULL
                        CHECK (override_phase IN (
                            'planning', 'design', 'procurement',
                            'construction', 'closeout', 'unknown'
                        )),
    override_reason TEXT NOT NULL
                        CHECK (length(override_reason) > 0),
    overridden_by   UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    overridden_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    engine_version  TEXT NOT NULL,
    ruleset_version TEXT NOT NULL
);

COMMENT ON TABLE public.lifecycle_override_log IS
    'Append-only manual override audit log for the W3 lifecycle_phase inference (ADR-0016). RLS allows SELECT/INSERT own; UPDATE/DELETE policies intentionally omitted to enforce append-only forensic discipline (SCL Protocol 2nd ed §4 chain-of-custody). engine_version + ruleset_version pin the inference algorithm version the user was looking at — so a future W6 algorithm bump cannot be confused with a W3 override post-hoc. inferred_phase nullable per ADR-0016 §3: the API layer (per BR P1#7) returns 409 if the user attempts override before any inference exists, but the schema does not enforce it.';

COMMENT ON COLUMN public.lifecycle_override_log.inferred_phase IS
    'The phase the inference engine emitted at the time of override. NULLABLE because the API layer permits override-before-inference in tightly-constrained recovery scenarios. The CHECK constraint mirrors override_phase to prevent drift with the engine vocabulary.';

COMMENT ON COLUMN public.lifecycle_override_log.override_reason IS
    'Free-text rationale. Schema enforces non-empty (length > 0); the API layer enforces a 10-character minimum per ADR-0016 §3 to prevent forensic-evasion via single-character noise. The schema''s lighter CHECK preserves freedom for future API policy changes without a migration.';

COMMENT ON COLUMN public.lifecycle_override_log.engine_version IS
    'Engine version string of the inference run the user was reviewing at override time. Mirrors schedule_derived_artifacts.engine_version vocabulary (e.g. ''4.0''). Allows post-hoc reconstruction of the inference state the user disagreed with.';

COMMENT ON COLUMN public.lifecycle_override_log.ruleset_version IS
    'Ruleset version string (e.g. ''lifecycle_phase-v1-2026-04''). Bumped on heuristic threshold changes per ADR-0014 / ADR-0016. Distinguishes overrides driven by genuinely-misclassified inference from overrides driven by an outdated ruleset.';

-- ================================================================
-- 4. Indices — hot-path latest override + per-user override history
-- ================================================================

CREATE INDEX IF NOT EXISTS idx_lifecycle_override_log_project_recent
    ON public.lifecycle_override_log (project_id, overridden_at DESC);

COMMENT ON INDEX public.idx_lifecycle_override_log_project_recent IS
    'Hot path: latest override for a given project. Used by GET /api/v1/projects/{id}/lifecycle to surface the active manual override to the UI when projects.lifecycle_phase_locked=true.';

CREATE INDEX IF NOT EXISTS idx_lifecycle_override_log_user_recent
    ON public.lifecycle_override_log (overridden_by, overridden_at DESC)
    WHERE overridden_by IS NOT NULL;

COMMENT ON INDEX public.idx_lifecycle_override_log_user_recent IS
    'Per-user override history for the Consultant SME forensic persona reviewing their own prior assertions. Partial index (skips rows where the user account was already erased per LGPD ON DELETE SET NULL) keeps the index small.';

-- ================================================================
-- 5. RLS quadruple — SELECT + INSERT only; UPDATE / DELETE intentionally omitted
-- ================================================================
--
-- Per ADR-0016 §3: the no-UPDATE / no-DELETE convention is the forensic
-- contract. Under the authenticated path, mutation attempts return [] / 200 OK
-- silently (PostgREST behaviour). Under service_role (background workers,
-- CASCADE cleanup, future LGPD project erasure), RLS is bypassed by design.
-- A trigger-based EXCEPTION enforcement was rejected because it would also
-- fire on service_role and break the LGPD ON DELETE SET NULL pattern.

ALTER TABLE public.lifecycle_override_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "lol_select_own" ON public.lifecycle_override_log;
CREATE POLICY "lol_select_own" ON public.lifecycle_override_log
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "lol_insert_own" ON public.lifecycle_override_log
;
CREATE POLICY "lol_insert_own" ON public.lifecycle_override_log
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- NO UPDATE POLICY — append-only contract (ADR-0016 §3).
-- NO DELETE POLICY — append-only contract (ADR-0016 §3).

-- ================================================================
-- 6. Reload PostgREST schema cache
-- ================================================================
NOTIFY pgrst, 'reload schema';
