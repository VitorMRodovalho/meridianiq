-- 022_programs_unique_upsert.sql
--
-- Wave 0 #5 of v4.0 Cycle 1 (ADR-0009). Closes the race in
-- SupabaseStore.get_or_create_program where two concurrent uploads with the
-- same (user_id, project_name) can both SELECT no row and both INSERT,
-- yielding duplicate program rows that corrupt the program list and the
-- revision-number sequence.
--
-- Fix has two parts:
-- 1. Functional UNIQUE INDEX on (user_id, lower(name)) enforces
--    case-insensitive uniqueness at the DB level. Two programs named
--    "Project A" and "project a" under the same user are now rejected.
-- 2. An atomic RPC upsert_program(uuid, text) performs INSERT ... ON
--    CONFLICT (user_id, lower(name)) DO UPDATE. Under concurrency the two
--    callers resolve to the same row; display case is preserved from the
--    first insert.
--
-- Prerequisite for Cycle 1 Shallow #1 (auto-grouping with rapidfuzz). The
-- grouping pass assumes program identity is deterministic under a given
-- (user_id, name) pair.
--
-- Reference: ADR-0009 Wave 0 item #5; follow-up to migration 005 (programs
-- table) and 020 (projects.program_id FK).

-- Step 1: Consolidate pre-existing duplicates. Keep the oldest row per
-- (user_id, lower(name)); reassign dependent schedule_uploads and projects
-- FKs to the "winner" before deleting losers. organization_programs
-- (migration 007) FKs ON DELETE CASCADE — losers there clear automatically.
DO $$
DECLARE
    has_dupes boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM public.programs
        WHERE user_id IS NOT NULL
        GROUP BY user_id, lower(name)
        HAVING count(*) > 1
    ) INTO has_dupes;

    IF has_dupes THEN
        CREATE TEMP TABLE _program_dedupe ON COMMIT DROP AS
        WITH ranked AS (
            SELECT id,
                   user_id,
                   lower(name) AS lname,
                   row_number() OVER (
                       PARTITION BY user_id, lower(name)
                       ORDER BY created_at ASC NULLS LAST, id ASC
                   ) AS rn
            FROM public.programs
            WHERE user_id IS NOT NULL
        ),
        winners AS (
            SELECT user_id, lname, id AS winner_id FROM ranked WHERE rn = 1
        )
        SELECT r.id AS loser_id, w.winner_id
        FROM ranked r
        JOIN winners w ON r.user_id = w.user_id AND r.lname = w.lname
        WHERE r.rn > 1;

        UPDATE public.schedule_uploads su
        SET program_id = d.winner_id
        FROM _program_dedupe d
        WHERE su.program_id = d.loser_id;

        UPDATE public.projects p
        SET program_id = d.winner_id
        FROM _program_dedupe d
        WHERE p.program_id = d.loser_id;

        DELETE FROM public.programs p
        USING _program_dedupe d
        WHERE p.id = d.loser_id;
    END IF;
END $$;

-- Step 2: Enforce uniqueness at the DB level.
CREATE UNIQUE INDEX IF NOT EXISTS idx_programs_user_name_unique
    ON public.programs(user_id, lower(name))
    WHERE user_id IS NOT NULL;

-- Step 3: Atomic upsert RPC.
CREATE OR REPLACE FUNCTION public.upsert_program(
    p_user_id UUID,
    p_name TEXT
) RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO public.programs (user_id, name, proj_short_name)
    VALUES (p_user_id, p_name, p_name)
    ON CONFLICT (user_id, (lower(name)))
    WHERE user_id IS NOT NULL
    DO UPDATE SET updated_at = now()
    RETURNING id INTO v_id;
    RETURN v_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.upsert_program(UUID, TEXT)
    TO authenticated, service_role;

COMMENT ON FUNCTION public.upsert_program(UUID, TEXT) IS
    'Atomic upsert of programs by (user_id, lower(name)). Returns the id of either a newly-created or a pre-existing program row; display-case is preserved from the first insert. Added 2026-04-18 Wave 0 #5 (ADR-0009).';

NOTIFY pgrst, 'reload schema';
