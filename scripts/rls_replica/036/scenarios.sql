-- Access request scenarios for migration 036, run against the SQL functions
-- as the API's role (service_role). They mirror tests/test_ai_requests.py,
-- which runs the same rules against InMemoryStore. Each scenario is its own
-- transaction and rolls back. Prints PASS/FAIL lines (probe_lib.sql).
--
-- Fixture identities come from probe_lib.sql (:A .. :E are confirmed
-- auth.users rows created by 034/fixtures.sql).

\set VERBOSITY terse
\set ask 'SELECT outcome, coalesce(requested_at::text, $$$$) AS at, coalesce(retry_after::text, $$$$) AS retry FROM public.ai_request_access'
\set state 'SELECT state, coalesce(requested_at::text, $$$$) AS at, coalesce(retry_after::text, $$$$) AS retry FROM public.ai_access_state'

-- ---------------------------------------------------------------- q01-q02 create, then pending
BEGIN;
SET LOCAL ROLE service_role;
:state (:B) \gset s0_
:ask (:B, 'first') \gset r1_
:ask (:B, 'second') \gset r2_
:ask (:B, NULL) \gset r3_
:state (:B) \gset s1_
RESET ROLE;
SELECT pg_temp.expect('q01 none, then created, then pending (x2)', 'none created pending pending',
       :'s0_state' || ' ' || :'r1_outcome' || ' ' || :'r2_outcome' || ' ' || :'r3_outcome');
SELECT pg_temp.expect('q02 a repeat keeps the place in the queue and updates the note only when given',
       'same second pending',
       CASE WHEN :'r1_at' = :'r2_at' AND :'r2_at' = :'s1_at' THEN 'same' ELSE 'moved' END || ' '
       || (SELECT note FROM public.ai_access_requests WHERE user_id = :B) || ' ' || :'s1_state');
ROLLBACK;

-- ---------------------------------------------------------------- q03 entitled
BEGIN;
INSERT INTO public.ai_entitlements (user_id) VALUES (:B);
SET LOCAL ROLE service_role;
:ask (:B, 'x') \gset r_
:state (:B) \gset s_
RESET ROLE;
SELECT pg_temp.expect('q03 an entitled account is told so and no row is written', 'entitled entitled 0',
       :'r_outcome' || ' ' || :'s_state' || ' '
       || (SELECT count(*) FROM public.ai_access_requests WHERE user_id = :B));
ROLLBACK;

-- ---------------------------------------------------------------- q04 dismiss and the 30-day block
BEGIN;
SET LOCAL ROLE service_role;
:ask (:B, 'why') \gset
SELECT public.ai_dismiss_request(:B, :A, '1.2.3.4', 'ua') AS d1 \gset
SELECT public.ai_dismiss_request(:B, :A, NULL, NULL) AS d2 \gset
:state (:B) \gset s_
:ask (:B, 'again') \gset r_
RESET ROLE;
SELECT pg_temp.expect('q04 dismissed once, note cleared, blocked with a retry date, audited',
       't f dismissed dismissed yes yes NULL 1',
       :'d1' || ' ' || :'d2' || ' ' || :'s_state' || ' ' || :'r_outcome' || ' '
       || CASE WHEN :'s_retry' <> '' THEN 'yes' ELSE 'no' END || ' '
       || CASE WHEN :'s_retry'::timestamptz
                    BETWEEN now() + interval '29 days 23 hours' AND now() + interval '30 days 1 hour'
               THEN 'yes' ELSE 'no' END || ' '
       || coalesce((SELECT note FROM public.ai_access_requests WHERE user_id = :B), 'NULL') || ' '
       || (SELECT count(*) FROM public.audit_log WHERE action = 'ai_access_request_dismissed'
                                                  AND entity_id = :B));
UPDATE public.ai_access_requests SET decided_at = now() - interval '31 days' WHERE user_id = :B;
SET LOCAL ROLE service_role;
:ask (:B, 'later') \gset r2_
RESET ROLE;
SELECT pg_temp.expect('q04b after 30 days the account may ask again', 'created', :'r2_outcome');
ROLLBACK;

-- ---------------------------------------------------------------- q05 approve
BEGIN;
SET LOCAL ROLE service_role;
:ask (:B, 'why') \gset
SELECT public.ai_approve_request(:B, :A, NULL, NULL) AS a1 \gset
SELECT public.ai_approve_request(:B, :A, NULL, NULL) AS a2 \gset
:state (:B) \gset s_
RESET ROLE;
SELECT pg_temp.expect('q05 approve once: default limits, address kept, request closed, note cleared, audited',
       't f entitled bob@example.test NULL NULL approved NULL 1',
       :'a1' || ' ' || :'a2' || ' ' || :'s_state' || ' '
       || (SELECT coalesce(email, 'NULL') || ' ' || coalesce(daily_questions::text, 'NULL') || ' '
                  || coalesce(monthly_budget_usd::text, 'NULL')
             FROM public.ai_entitlements WHERE user_id = :B AND revoked_at IS NULL) || ' '
       || (SELECT status || ' ' || coalesce(note, 'NULL') FROM public.ai_access_requests WHERE user_id = :B)
       || ' ' || (SELECT count(*) FROM public.audit_log WHERE action = 'ai_access_granted' AND entity_id = :B));
ROLLBACK;

-- ---------------------------------------------------------------- q06 any grant closes the request
BEGIN;
SET LOCAL ROLE service_role;
:ask (:B, 'why') \gset
SELECT public.ai_grant(:B, 'bob@example.test', :A, 3, NULL, NULL, NULL, NULL) AS g \gset
RESET ROLE;
SELECT pg_temp.expect('q06 a grant from the form closes the pending request', 'approved NULL 0',
       (SELECT status || ' ' || coalesce(note, 'NULL') FROM public.ai_access_requests WHERE user_id = :B)
       || ' ' || (public.ai_pending_requests() ->> 'total'));
ROLLBACK;

-- ---------------------------------------------------------------- q07 revoked waits 30 days
BEGIN;
SET LOCAL ROLE service_role;
:ask (:B, NULL) \gset
SELECT public.ai_approve_request(:B, :A, NULL, NULL) AS a \gset
SELECT public.ai_revoke(:B, :A, NULL, NULL) AS rv \gset
:ask (:B, NULL) \gset r1_
RESET ROLE;
-- Both moments in the past, in their real order: approved, then revoked.
UPDATE public.ai_access_requests SET decided_at = now() - interval '40 days' WHERE user_id = :B;
UPDATE public.ai_entitlements SET revoked_at = now() - interval '31 days' WHERE user_id = :B;
SET LOCAL ROLE service_role;
:ask (:B, NULL) \gset r2_
RESET ROLE;
SELECT pg_temp.expect('q07 revoked access blocks a new request for 30 days from the revocation',
       'dismissed created', :'r1_outcome' || ' ' || :'r2_outcome');
ROLLBACK;

-- ---------------------------------------------------------------- q08 the pending list
BEGIN;
SET LOCAL ROLE service_role;
:ask (:B, 'b note') \gset
:ask (:C, NULL) \gset
:ask (:D, NULL) \gset
SELECT public.ai_dismiss_request(:D, :A, NULL, NULL) AS d \gset
RESET ROLE;
UPDATE auth.users SET email_confirmed_at = NULL WHERE id = :C;
SET LOCAL ROLE service_role;
SELECT public.ai_pending_requests()::text AS all_ \gset
SELECT public.ai_pending_requests(NULL, 1)::text AS one_ \gset
SELECT public.ai_pending_requests(:D)::text AS dismissed_ \gset
RESET ROLE;
SELECT pg_temp.expect('q08 pending only, oldest first, confirmed addresses only, capped with the total',
       '2 bob@example.test b note NULL | 2 1 | 0',
       (SELECT (r ->> 'total') || ' ' || (r -> 'items' -> 0 ->> 'email') || ' '
               || (r -> 'items' -> 0 ->> 'note') || ' ' || coalesce(r -> 'items' -> 1 ->> 'email', 'NULL')
          FROM (SELECT :'all_'::jsonb AS r) AS x) || ' | '
       || (SELECT (r ->> 'total') || ' ' || jsonb_array_length(r -> 'items') FROM (SELECT :'one_'::jsonb AS r) AS x)
       || ' | ' || (SELECT r ->> 'total' FROM (SELECT :'dismissed_'::jsonb AS r) AS x));
ROLLBACK;

-- ---------------------------------------------------------------- q09 deleting the account removes its request
BEGIN;
\set X '''90000000-0000-4000-8000-0000000000e9'''
SET LOCAL session_replication_role = replica;
INSERT INTO auth.users (id, email, email_confirmed_at) VALUES (:X, 'x@example.test', now());
SET LOCAL session_replication_role = origin;
SET LOCAL ROLE service_role;
:ask (:X, 'note') \gset
RESET ROLE;
DELETE FROM auth.users WHERE id = :X;
SELECT pg_temp.expect('q09 the request goes with the account', '0',
       (SELECT count(*)::text FROM public.ai_access_requests WHERE user_id = :X));
ROLLBACK;

-- ---------------------------------------------------------------- q10 who can reach what
SELECT pg_temp.expect('q10 authenticated cannot call ai_pending_requests (the definer)',
       'ERR 42501 permission denied for function ai_pending_requests',
       pg_temp.run_as('authenticated', :A, 'SELECT public.ai_pending_requests()::text'));
SELECT pg_temp.expect('q10 anon cannot call ai_pending_requests (the definer)',
       'ERR 42501 permission denied for function ai_pending_requests',
       pg_temp.run_as('anon', NULL, 'SELECT public.ai_pending_requests()::text'));
SELECT pg_temp.expect('q10 authenticated cannot call ai_request_access',
       'ERR 42501 permission denied for function ai_request_access',
       pg_temp.run_as('authenticated', :A, format('SELECT outcome FROM public.ai_request_access(%L, NULL)', :A)));
SELECT pg_temp.expect('q10 authenticated cannot call ai_approve_request',
       'ERR 42501 permission denied for function ai_approve_request',
       pg_temp.run_as('authenticated', :A, format('SELECT public.ai_approve_request(%L, %L, NULL, NULL)::text', :A, :A)));
SELECT pg_temp.expect('q10 anon cannot call ai_dismiss_request',
       'ERR 42501 permission denied for function ai_dismiss_request',
       pg_temp.run_as('anon', NULL, format('SELECT public.ai_dismiss_request(%L, %L, NULL, NULL)::text', :A, :A)));
SELECT pg_temp.expect('q10 authenticated cannot call ai_access_state',
       'ERR 42501 permission denied for function ai_access_state',
       pg_temp.run_as('authenticated', :A, format('SELECT state FROM public.ai_access_state(%L)', :A)));
SELECT pg_temp.expect('q10 authenticated cannot read ai_access_requests',
       'ERR 42501 permission denied for table ai_access_requests',
       pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.ai_access_requests'));
SELECT pg_temp.expect('q10 authenticated cannot write a request itself',
       'ERR 42501 permission denied for table ai_access_requests',
       pg_temp.run_as('authenticated', :A, format('INSERT INTO public.ai_access_requests (user_id) VALUES (%L)', :A)));
SELECT pg_temp.expect('q10 authenticated cannot call ai_forget_user',
       'ERR 42501 permission denied for function ai_forget_user',
       pg_temp.run_as('authenticated', :A, format('SELECT public.ai_forget_user(%L)::text', :A)));
SELECT pg_temp.expect('q10 authenticated cannot call the private definer',
       'ERR 42501 permission denied for schema private',
       pg_temp.run_as('authenticated', :A, 'SELECT private.ai_pending_requests()::text'));
-- Second barrier: even with EXECUTE on the public wrapper, a client role is
-- stopped at schema private.
SELECT pg_temp.expect('q10 a client granted the wrapper is still stopped at schema private',
       'ERR 42501 permission denied for schema private',
       pg_temp.run_as('authenticated', :A, 'SELECT public.ai_pending_requests()::text',
                      'GRANT EXECUTE ON FUNCTION public.ai_pending_requests(uuid, integer) TO authenticated'));
-- Control: service_role cannot read auth.users itself, so the definer is
-- what reaches the addresses, and the probe above can tell denied from allowed.
SELECT pg_temp.expect('q10 control: service_role cannot read auth.users directly',
       'ERR 42501 permission denied for table users',
       pg_temp.run_as('service_role', NULL, 'SELECT count(*)::text FROM auth.users'));
SELECT pg_temp.expect('q10 control: service_role reaches addresses through the definer', 'OK 0',
       pg_temp.run_as('service_role', NULL, 'SELECT public.ai_pending_requests() ->> ''total'''));

-- ---------------------------------------------------------------- q11 erasure
BEGIN;
SET LOCAL ROLE service_role;
:ask (:B, 'a private note') \gset
SELECT public.ai_grant(:C, 'carol@example.test', :A, 7, NULL, NULL, NULL, NULL) AS g \gset
SELECT public.ai_forget_user(:B) AS f1 \gset
SELECT public.ai_forget_user(:C) AS f2 \gset
:ask (:B, 'again') \gset r_
RESET ROLE;
SELECT pg_temp.expect('q11 erasure withdraws the pending request and clears its note and the address copy; access stays',
       'dismissed NULL NULL dismissed yes 0 NULL 7 active',
       (SELECT status || ' ' || coalesce(note, 'NULL') || ' ' || coalesce(decided_by::text, 'NULL')
          FROM public.ai_access_requests WHERE user_id = :B) || ' '
       || :'r_outcome' || ' ' || CASE WHEN :'r_retry' <> '' THEN 'yes' ELSE 'no' END || ' '
       || (SELECT count(*) FROM public.ai_access_requests WHERE user_id = :B AND status = 'pending') || ' '
       || (SELECT coalesce(email, 'NULL') || ' ' || daily_questions || ' '
                  || CASE WHEN revoked_at IS NULL THEN 'active' ELSE 'revoked' END
             FROM public.ai_entitlements WHERE user_id = :C));
ROLLBACK;

-- ---------------------------------------------------------------- q11b erasure does not lift a dismissal
BEGIN;
SET LOCAL ROLE service_role;
:ask (:B, NULL) \gset
SELECT public.ai_dismiss_request(:B, :A, NULL, NULL) AS d \gset
SELECT public.ai_forget_user(:B) AS f \gset
:ask (:B, NULL) \gset r_
RESET ROLE;
SELECT pg_temp.expect('q11b request, dismissal, erasure, request: still dismissed, the operator''s decision kept',
       'dismissed dismissed a0000000-0000-4000-8000-000000000001',
       :'r_outcome' || ' '
       || (SELECT status || ' ' || decided_by FROM public.ai_access_requests WHERE user_id = :B));
ROLLBACK;

-- ---------------------------------------------------------------- q11c the API role cannot delete a request
SELECT pg_temp.expect('q11c service_role cannot DELETE from ai_access_requests',
       'ERR 42501 permission denied for table ai_access_requests',
       pg_temp.run_as('service_role', NULL, 'DELETE FROM public.ai_access_requests RETURNING 1'));

-- ---------------------------------------------------------------- q12 any revocation blocks for 30 days
BEGIN;
SET LOCAL ROLE service_role;
SELECT public.ai_grant(:C, 'carol@example.test', :A, NULL, NULL, NULL, NULL, NULL) AS g \gset
SELECT public.ai_revoke(:C, :A, NULL, NULL) AS rv \gset
:ask (:C, NULL) \gset r1_
RESET ROLE;
SELECT pg_temp.expect('q12 access granted from the form, then revoked: blocked, with a retry date',
       'dismissed yes 0', :'r1_outcome' || ' ' || CASE WHEN :'r1_retry' <> '' THEN 'yes' ELSE 'no' END || ' '
       || (SELECT count(*) FROM public.ai_access_requests WHERE user_id = :C));
ROLLBACK;

-- ---------------------------------------------------------------- q13 approving keeps custom limits
BEGIN;
SET LOCAL ROLE service_role;
:ask (:B, 'why') \gset
RESET ROLE;
-- An entitlement written directly, as a grant racing the request would leave it.
INSERT INTO public.ai_entitlements (user_id, email, daily_questions, note)
VALUES (:B, 'bob@example.test', 200, 'custom');
SET LOCAL ROLE service_role;
SELECT public.ai_approve_request(:B, :A, NULL, NULL) AS a \gset
RESET ROLE;
SELECT pg_temp.expect('q13 approving a request of an account with active access keeps its limits',
       't approved 200 custom',
       :'a' || ' ' || (SELECT status FROM public.ai_access_requests WHERE user_id = :B) || ' '
       || (SELECT daily_questions || ' ' || note FROM public.ai_entitlements WHERE user_id = :B));
SELECT pg_temp.expect('q13 closing it is audited', '1',
       (SELECT count(*)::text FROM public.audit_log
         WHERE action = 'ai_access_request_approved' AND entity_id = :B));
ROLLBACK;

