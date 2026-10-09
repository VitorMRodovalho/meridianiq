-- Migration 037: drop the two INSERT policies that admit any row
--
-- Migration 011 created "Users insert own alerts" and "Users insert own
-- health_scores" as FOR INSERT WITH CHECK (TRUE), for every role. Measured
-- in production on 2026-10-09: neither anon nor authenticated holds INSERT
-- on either table, so the policies admit nothing today, but a later GRANT
-- would let any signed-in user write rows against another user's project.
-- Both tables are empty and the backend does not write them; service_role
-- bypasses RLS and needs no policy.
--
-- With the policies gone, RLS denies INSERT from client roles whatever the
-- grants say. The SELECT policies stay as they are.
--
-- Apply by hand (psql -f), never `supabase db push` in production.

BEGIN;

DROP POLICY IF EXISTS "Users insert own alerts" ON public.alerts;
DROP POLICY IF EXISTS "Users insert own health_scores" ON public.health_scores;

COMMIT;

-- Postcheck: expect only the two SELECT policies.
--   select tablename, policyname, cmd from pg_policies
--   where tablename in ('alerts', 'health_scores') order by 1, 2;
