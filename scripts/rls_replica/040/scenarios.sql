-- Migration 040 scenarios, each in a rolled-back transaction. Run after
-- probe_lib.sql as supabase_admin. Accounts are synthetic and inserted with
-- triggers off (session_replication_role = replica), as in 036/scenarios.sql.

\set U1 '''40000000-0000-4000-8000-0000000004a1'''
\set U2 '''40000000-0000-4000-8000-0000000004a2'''
\set U3 '''40000000-0000-4000-8000-0000000004a3'''
\set U4 '''40000000-0000-4000-8000-0000000004a4'''
\set U5 '''40000000-0000-4000-8000-0000000004a5'''

-- ---------------------------------------------------------------- r01 the purge removes only decided rows past 30 days
BEGIN;
SET LOCAL session_replication_role = replica;
INSERT INTO auth.users (id, email) VALUES
    (:U1, 'u1@example.test'), (:U2, 'u2@example.test'), (:U3, 'u3@example.test'),
    (:U4, 'u4@example.test'), (:U5, 'u5@example.test');
SET LOCAL session_replication_role = origin;
INSERT INTO public.ai_access_requests (user_id, status, requested_at, decided_at) VALUES
    (:U1, 'dismissed', now() - interval '40 days', now() - interval '31 days'),
    (:U2, 'dismissed', now() - interval '40 days', now() - interval '29 days'),
    (:U3, 'dismissed', now() - interval '40 days', now() - interval '30 days'),
    (:U4, 'approved',  now() - interval '40 days', now() - interval '31 days'),
    (:U5, 'pending',   now() - interval '90 days', NULL);
SET LOCAL ROLE postgres;
SELECT pg_temp.expect('r01 the purge (as postgres) deletes 2 rows', '2',
       public.ai_purge_decided_requests()::text);
RESET ROLE;
SELECT pg_temp.expect('r01 left: the 29-day and 30-day dismissals and the old pending request',
       '40000000-0000-4000-8000-0000000004a2,40000000-0000-4000-8000-0000000004a3,40000000-0000-4000-8000-0000000004a5',
       (SELECT string_agg(user_id::text, ',' ORDER BY user_id) FROM public.ai_access_requests
         WHERE user_id IN (:U1, :U2, :U3, :U4, :U5)));
-- r02 the purged account can ask again; the 29-day one is still blocked
SET LOCAL ROLE service_role;
SELECT pg_temp.expect('r02 a purged account asks again: created', 'created',
       (SELECT outcome FROM public.ai_request_access(:U1, NULL)));
SELECT pg_temp.expect('r02 a 29-day dismissal is still blocked', 'dismissed',
       (SELECT outcome FROM public.ai_request_access(:U2, NULL)));
RESET ROLE;
ROLLBACK;

-- ---------------------------------------------------------------- r03 erasure clears the entitlement's note and address
BEGIN;
SET LOCAL session_replication_role = replica;
INSERT INTO auth.users (id, email) VALUES (:U1, 'u1@example.test');
SET LOCAL session_replication_role = origin;
INSERT INTO public.ai_entitlements (user_id, email, note) VALUES (:U1, 'u1@example.test', 'operator note');
SET LOCAL ROLE service_role;
SELECT public.ai_forget_user(:U1);
RESET ROLE;
SELECT pg_temp.expect('r03 email and note cleared, access kept', 'NULL NULL active',
       (SELECT coalesce(email, 'NULL') || ' ' || coalesce(note, 'NULL') || ' '
               || CASE WHEN revoked_at IS NULL THEN 'active' ELSE 'revoked' END
          FROM public.ai_entitlements WHERE user_id = :U1));
ROLLBACK;

-- ---------------------------------------------------------------- r04 no API role can purge
SELECT pg_temp.expect('r04 service_role cannot call the purge',
       'ERR 42501 permission denied for function ai_purge_decided_requests',
       pg_temp.run_as('service_role', NULL, 'SELECT public.ai_purge_decided_requests()::text'));
SELECT pg_temp.expect('r04 authenticated cannot call the purge',
       'ERR 42501 permission denied for function ai_purge_decided_requests',
       pg_temp.run_as('authenticated', :U1, 'SELECT public.ai_purge_decided_requests()::text'));
SELECT pg_temp.expect('r04 service_role still cannot delete a request',
       'ERR 42501 permission denied for table ai_access_requests',
       pg_temp.run_as('service_role', NULL, 'DELETE FROM public.ai_access_requests RETURNING 1'));
SELECT pg_temp.expect('r04 authenticated cannot schedule a cron job',
       'ERR 42501 %',
       pg_temp.run_as('authenticated', :U1, 'SELECT cron.schedule(''x'', ''* * * * *'', ''SELECT 1'')::text'));
