-- Migration 033: resolve invitation addresses from auth.users; lock profile identity columns
--
-- Organization invitations name the invited person by email address. From
-- this migration on, the API resolves that address against auth.users, the
-- address the auth service holds for the account, and user_profiles keeps
-- only its display columns user-editable.
--
-- 1. public.auth_user_id_for_email(text) returns the id of the single
--    confirmed, non-deleted auth.users row with that address (compared
--    case-insensitively), or NULL when there is none or more than one. It is
--    callable by the backend (service_role) only.
-- 2. Signed-in users keep UPDATE on their own profile row, but only on the
--    display columns. email and role are written by the signup trigger
--    (handle_new_user, SECURITY DEFINER) and are no longer user-writable.
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
GRANT UPDATE (full_name, company, avatar_url, updated_at) ON public.user_profiles TO authenticated;
