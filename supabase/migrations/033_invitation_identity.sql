-- Migration 033: resolve invitation addresses from auth.users; lock profile identity columns
--
-- Organization invitations name the invited person by email address. From
-- this migration on, the API resolves that address against auth.users, the
-- address the auth service holds for the account. user_profiles is written
-- only by the signup trigger and the backend; no client role updates it.
--
-- 1. public.auth_user_id_for_email(text) returns the id of the single
--    confirmed, non-deleted auth.users row with that address (compared
--    case-insensitively), or NULL when there is none or more than one. It is
--    callable by the backend (service_role) only.
-- 2. UPDATE on public.user_profiles is revoked from the client roles
--    (a table-level REVOKE also removes any column-level UPDATE). Nothing in
--    the product writes profiles from the client; the signup trigger
--    (handle_new_user, SECURITY DEFINER) and service_role are unaffected.
--
-- Apply BEFORE deploying the API that calls auth_user_id_for_email: without
-- the function the invite and revoke routes answer 500.
--
-- Idempotent: CREATE OR REPLACE, and REVOKE/GRANT of an existing state are
-- no-ops.

CREATE OR REPLACE FUNCTION public.auth_user_id_for_email(p_email text)
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT CASE WHEN count(*) = 1 THEN (array_agg(u.id))[1] END
    FROM auth.users AS u
    WHERE lower(u.email) = lower(btrim(p_email))
      AND u.deleted_at IS NULL
      AND u.email_confirmed_at IS NOT NULL;
$$;

REVOKE ALL ON FUNCTION public.auth_user_id_for_email(text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.auth_user_id_for_email(text) TO service_role;

REVOKE UPDATE ON public.user_profiles FROM PUBLIC, anon, authenticated;

-- Make the new function visible to PostgREST without waiting for a reload.
NOTIFY pgrst, 'reload schema';
