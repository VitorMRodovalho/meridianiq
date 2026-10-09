-- Migration 039: one atomic way to put a schedule in a program
--
-- A project's place in a program is (program_id, revision_number) on
-- public.projects. Until now the API computed MAX(revision_number) + 1 and
-- then wrote it in a second call, so two uploads into one program at the
-- same time could both get the same number (nothing in the schema stopped
-- it). Users will now choose the program at upload and move schedules
-- between programs, which makes that the normal case, not a corner one.
--
-- 1. place_project_in_program(user, project, program) does the whole move
--    in one transaction:
--      - checks that the caller owns both the project and the program
--        (the API runs as service_role, which bypasses RLS, so the check is
--        explicit; a foreign or missing row raises the same error);
--      - refuses a project that has active revision_history rows, whose
--        numbers belong to the program they were confirmed in (production
--        had none on 2026-10-09);
--      - locks the target program's row, which serialises numbering per
--        program, and gives the project MAX + 1 in the target;
--      - deletes the program the project left if it is now empty and not
--        shared, so moving schedules does not leave empty programs behind;
--      - returns the new revision number and whether the old program went.
--    Placing a project in the program it is already in is a no-op that
--    returns its current number.
-- 2. A partial UNIQUE index on (program_id, revision_number) makes a
--    duplicate number an error instead of an arbitrary tie. Production had
--    no duplicates on 2026-10-09; the index build fails, and the migration
--    rolls back, if any appear before it is applied.
--
-- Execute is granted to service_role only, as in migrations 030 and 035.
-- Apply by hand (psql -f), never `supabase db push` in production.

BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_program_revision_unique
    ON public.projects (program_id, revision_number)
    WHERE program_id IS NOT NULL AND revision_number IS NOT NULL;

CREATE OR REPLACE FUNCTION public.place_project_in_program(
    p_user_id uuid,
    p_project_id uuid,
    p_program_id uuid
) RETURNS TABLE (revision_number integer, source_program_deleted boolean)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
#variable_conflict use_column
DECLARE
    v_source uuid;
    v_current integer;
    v_next integer;
    v_deleted boolean := false;
BEGIN
    IF p_user_id IS NULL OR p_project_id IS NULL OR p_program_id IS NULL THEN
        RAISE EXCEPTION 'project or program not found' USING ERRCODE = 'P0002';
    END IF;

    PERFORM 1 FROM public.programs
     WHERE id = p_program_id AND user_id = p_user_id
       FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'project or program not found' USING ERRCODE = 'P0002';
    END IF;

    SELECT p.program_id, p.revision_number INTO v_source, v_current
      FROM public.projects p
     WHERE p.id = p_project_id AND p.user_id = p_user_id
       FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'project or program not found' USING ERRCODE = 'P0002';
    END IF;

    IF v_source IS NOT DISTINCT FROM p_program_id AND v_current IS NOT NULL THEN
        RETURN QUERY SELECT v_current, false;
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.revision_history rh
         WHERE rh.project_id = p_project_id AND rh.tombstoned_at IS NULL
    ) THEN
        RAISE EXCEPTION 'project has confirmed revision links; remove them first'
            USING ERRCODE = 'P0001';
    END IF;

    SELECT COALESCE(MAX(p.revision_number), 0) + 1 INTO v_next
      FROM public.projects p
     WHERE p.program_id = p_program_id;

    UPDATE public.projects p
       SET program_id = p_program_id, revision_number = v_next
     WHERE p.id = p_project_id;

    UPDATE public.programs SET updated_at = now() WHERE id = p_program_id;

    IF v_source IS NOT NULL AND v_source <> p_program_id
       AND NOT EXISTS (SELECT 1 FROM public.projects p WHERE p.program_id = v_source)
       AND NOT EXISTS (SELECT 1 FROM public.schedule_uploads su WHERE su.program_id = v_source)
       AND NOT EXISTS (SELECT 1 FROM public.program_shares ps WHERE ps.program_id = v_source)
    THEN
        DELETE FROM public.programs WHERE id = v_source AND user_id = p_user_id;
        v_deleted := FOUND;
    END IF;

    RETURN QUERY SELECT v_next, v_deleted;
END;
$$;

REVOKE ALL ON FUNCTION public.place_project_in_program(uuid, uuid, uuid)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.place_project_in_program(uuid, uuid, uuid)
    TO service_role;

COMMENT ON FUNCTION public.place_project_in_program(uuid, uuid, uuid) IS
    'Puts an owned project in an owned program as its next revision, atomically, '
    'and deletes the program it left if that is now empty and unshared. Migration 039.';

COMMIT;

NOTIFY pgrst, 'reload schema';
