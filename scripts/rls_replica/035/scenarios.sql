-- Ledger scenarios for migration 035, run against the SQL functions as the
-- API's role (service_role). They mirror tests/test_ai_gate.py, which runs
-- the same rules against InMemoryStore. Each scenario is its own
-- transaction and rolls back. Prints PASS/FAIL lines (probe_lib.sql).
--
-- Fixture identities come from probe_lib.sql (:A, :B are auth.users rows
-- created by 034/fixtures.sql).

\set VERBOSITY terse

-- Reserve as service_role; result in :rid (empty when refused) and :why.
\set reserve 'SELECT coalesce(reservation_id::text, $$$$) AS rid, coalesce(reason, $$$$) AS why FROM public.ai_reserve'

-- ---------------------------------------------------------------- s01-s02
BEGIN;
SET LOCAL ROLE service_role;
:reserve (:A, NULL, 0.02, 20, 5, 50, 'm', 3, 15) \gset
RESET ROLE;
SELECT pg_temp.expect('s01 not entitled is refused', 'ai_not_entitled', :'why');
INSERT INTO public.ai_entitlements (user_id, email) VALUES (:A, 'a@example.test');
SET LOCAL ROLE service_role;
:reserve (:A, NULL, 0.02, 20, 5, 50, 'm', 3, 15) \gset
RESET ROLE;
SELECT pg_temp.expect('s02 entitled reserves', 'yes', CASE WHEN :'rid' <> '' THEN 'yes' ELSE 'no: ' || :'why' END);
SELECT pg_temp.expect('s02 row is reserved with model and prices', 'reserved m 3.000000 15.000000 0.020000',
       (SELECT status || ' ' || model || ' ' || price_input_usd_per_mtok || ' ' || price_output_usd_per_mtok
               || ' ' || reserved_usd FROM public.ai_usage WHERE id = :'rid'::bigint));
ROLLBACK;

-- ---------------------------------------------------------------- s03 daily
BEGIN;
INSERT INTO public.ai_entitlements (user_id, daily_questions) VALUES (:A, 2);
SET LOCAL ROLE service_role;
:reserve (:A, NULL, 0.01, 20, 5, 50, 'm', 3, 15) \gset r1_
:reserve (:A, NULL, 0.01, 20, 5, 50, 'm', 3, 15) \gset r2_
:reserve (:A, NULL, 0.01, 20, 5, 50, 'm', 3, 15) \gset r3_
RESET ROLE;
SELECT pg_temp.expect('s03 daily override: two reservations, then refused', 'ok ok ai_daily_quota',
       CASE WHEN :'r1_rid' <> '' THEN 'ok' ELSE :'r1_why' END || ' '
       || CASE WHEN :'r2_rid' <> '' THEN 'ok' ELSE :'r2_why' END || ' ' || :'r3_why');
ROLLBACK;

-- ---------------------------------------------------------------- s04 failed does not count
BEGIN;
INSERT INTO public.ai_entitlements (user_id, daily_questions) VALUES (:A, 1);
SET LOCAL ROLE service_role;
:reserve (:A, NULL, 0.01, 20, 5, 50, 'm', 3, 15) \gset
SELECT public.ai_settle(:'rid'::bigint, 'failed', NULL, NULL, NULL) AS settled \gset
:reserve (:A, NULL, 0.01, 20, 5, 50, 'm', 3, 15) \gset again_
SELECT used_today, account_spent_usd FROM public.ai_quota(:A, 20, 5) \gset q_
RESET ROLE;
SELECT pg_temp.expect('s04 a failed call frees the daily slot and costs nothing', 't yes 1 0.010000',
       :'settled' || ' ' || CASE WHEN :'again_rid' <> '' THEN 'yes' ELSE :'again_why' END
       || ' ' || :'q_used_today' || ' ' || :'q_account_spent_usd');
ROLLBACK;

-- ---------------------------------------------------------------- s05 account budget
BEGIN;
INSERT INTO public.ai_entitlements (user_id, monthly_budget_usd) VALUES (:A, 0.03);
SET LOCAL ROLE service_role;
:reserve (:A, NULL, 0.02, 20, 5, 50, 'm', 3, 15) \gset r1_
SELECT public.ai_settle(:'r1_rid'::bigint, 'completed', 100, 10, 0.005) AS s1 \gset
:reserve (:A, NULL, 0.02, 20, 5, 50, 'm', 3, 15) \gset r2_
:reserve (:A, NULL, 0.02, 20, 5, 50, 'm', 3, 15) \gset r3_
RESET ROLE;
SELECT pg_temp.expect('s05 account budget counts completed cost + open reservations', 'ok ai_account_budget',
       CASE WHEN :'r2_rid' <> '' THEN 'ok' ELSE :'r2_why' END || ' ' || :'r3_why');
ROLLBACK;

-- ---------------------------------------------------------------- s06 global budget
BEGIN;
INSERT INTO public.ai_entitlements (user_id) VALUES (:A), (:B);
SET LOCAL ROLE service_role;
:reserve (:A, NULL, 0.02, 20, 5, 0.03, 'm', 3, 15) \gset a_
:reserve (:B, NULL, 0.02, 20, 5, 0.03, 'm', 3, 15) \gset b_
RESET ROLE;
SELECT pg_temp.expect('s06 global budget stops another account', 'ok ai_global_budget',
       CASE WHEN :'a_rid' <> '' THEN 'ok' ELSE :'a_why' END || ' ' || :'b_why');
ROLLBACK;

-- ---------------------------------------------------------------- s07-s09 settle
BEGIN;
INSERT INTO public.ai_entitlements (user_id) VALUES (:A);
SET LOCAL ROLE service_role;
:reserve (:A, NULL, 0.02, 20, 5, 50, 'm', 3, 15) \gset
SELECT public.ai_settle(:'rid'::bigint, 'unknown', NULL, NULL, NULL) AS first \gset
SELECT public.ai_settle(:'rid'::bigint, 'completed', 1, 1, 0.001) AS second \gset
SELECT account_spent_usd FROM public.ai_quota(:A, 20, 5) \gset q_
RESET ROLE;
SELECT pg_temp.expect('s07 unknown counts at its reservation', '0.020000', :'q_account_spent_usd');
SELECT pg_temp.expect('s08 a reservation settles once', 't f', :'first' || ' ' || :'second');
SELECT pg_temp.expect('s09 invalid status is rejected', 'ERR P0001 ai_settle: invalid status bogus',
       pg_temp.run_as('service_role', NULL,
                      format('SELECT public.ai_settle(%s, %L, NULL, NULL, NULL)::text', :'rid', 'bogus')));
SELECT pg_temp.expect('s09b completed without a cost is rejected', 'ERR 23514%',
       pg_temp.run_as('service_role', NULL,
                      'SELECT public.ai_settle(id, ''completed'', 1, 1, NULL)::text FROM public.ai_usage ORDER BY id DESC LIMIT 1',
                      format('INSERT INTO public.ai_usage (user_id, model, price_input_usd_per_mtok, price_output_usd_per_mtok, reserved_usd) VALUES (%L, ''m'', 3, 15, 0.01)', :A)));
ROLLBACK;

-- ---------------------------------------------------------------- s10 windows
BEGIN;
INSERT INTO public.ai_entitlements (user_id) VALUES (:A);
INSERT INTO public.ai_usage (user_id, model, price_input_usd_per_mtok, price_output_usd_per_mtok,
                             reserved_usd, status, cost_usd, created_at)
VALUES (:A, 'm', 3, 15, 0.02, 'completed', 0.004, date_trunc('month', now(), 'UTC') - interval '1 second'),
       (:A, 'm', 3, 15, 0.02, 'completed', 0.004, date_trunc('day', now(), 'UTC') - interval '1 second'),
       (:A, 'm', 3, 15, 0.02, 'completed', 0.004, now());
SET LOCAL ROLE service_role;
SELECT used_today, account_spent_usd, global_spent_usd FROM public.ai_quota(:A, 20, 5) \gset q_
RESET ROLE;
-- Yesterday is in this month unless today is the 1st (UTC).
SELECT pg_temp.expect('s10 UTC day and month windows', '1 ' ||
       CASE WHEN date_trunc('day', now(), 'UTC') = date_trunc('month', now(), 'UTC')
            THEN '0.004000' ELSE '0.008000' END,
       :'q_used_today' || ' ' || :'q_account_spent_usd');
ROLLBACK;

-- ---------------------------------------------------------------- s11-s12 revoke, defaults
BEGIN;
INSERT INTO public.ai_entitlements (user_id, revoked_at) VALUES (:A, now());
INSERT INTO public.ai_entitlements (user_id, daily_questions) VALUES (:B, 0);
SET LOCAL ROLE service_role;
:reserve (:A, NULL, 0.01, 20, 5, 50, 'm', 3, 15) \gset a_
:reserve (:B, NULL, 0.01, 20, 5, 50, 'm', 3, 15) \gset b_
SELECT daily_limit, account_budget_usd FROM public.ai_quota(:B, 7, 2.5) \gset qb_
RESET ROLE;
SELECT pg_temp.expect('s11 revoked is not entitled', 'ai_not_entitled', :'a_why');
SELECT pg_temp.expect('s12 a zero override denies; unset limits take the defaults', 'ai_daily_quota 0 2.5',
       :'b_why' || ' ' || :'qb_daily_limit' || ' ' || :'qb_account_budget_usd');
ROLLBACK;

-- ---------------------------------------------------------------- s13 operator report
BEGIN;
INSERT INTO public.ai_entitlements (user_id, email) VALUES (:A, 'a@example.test'), (:B, 'b@example.test');
INSERT INTO public.ai_usage (user_id, model, price_input_usd_per_mtok, price_output_usd_per_mtok,
                             reserved_usd, created_at)
VALUES (:A, 'm', 3, 15, 0.02, now() - interval '11 minutes');
SET LOCAL ROLE service_role;
SELECT public.ai_admin_report(20, 5)::text AS report \gset
RESET ROLE;
SELECT pg_temp.expect('s13 report: 2 entitlements, 1 stale, spend as text', '2 1 0.020000',
       (SELECT jsonb_array_length(r -> 'entitlements') || ' ' || (r ->> 'stale_reservations') || ' '
               || (r ->> 'global_spent_month_usd') FROM (SELECT :'report'::jsonb AS r) AS x));
ROLLBACK;

-- ---------------------------------------------------------------- s14 deletion keeps the ledger
-- A fresh account with no other rows, so deleting it is not blocked by
-- the organization fixtures.
\set X '''90000000-0000-4000-8000-0000000000e9'''
BEGIN;
-- Signup triggers off for this insert only (they would create an
-- organization referencing the account); FKs and cascades stay on below.
SET LOCAL session_replication_role = replica;
INSERT INTO auth.users (id, email) VALUES (:X, 'x@example.test');
SET LOCAL session_replication_role = origin;
INSERT INTO public.ai_entitlements (user_id) VALUES (:X);
SET LOCAL ROLE service_role;
:reserve (:X, :PA, 0.02, 20, 5, 50, 'm', 3, 15) \gset
RESET ROLE;
DELETE FROM public.projects WHERE id = :PA;
DELETE FROM auth.users WHERE id = :X;
SELECT pg_temp.expect('s14 deleting the account and project keeps usage, drops the entitlement', '1 0',
       (SELECT count(*) FROM public.ai_usage WHERE user_id = :X) || ' '
       || (SELECT count(*) FROM public.ai_entitlements WHERE user_id = :X));
ROLLBACK;

-- ---------------------------------------------------------------- s15 guards on inputs
SELECT pg_temp.expect('s15 a non-positive reservation is rejected', 'ERR P0001 ai_reserve: reserve and global budget must be positive',
       pg_temp.run_as('service_role', NULL,
                      format('SELECT reason FROM public.ai_reserve(%L, NULL, 0, 20, 5, 50, ''m'', 3, 15)', :A)));

-- ---------------------------------------------------------------- s16 client roles reach nothing
SELECT pg_temp.expect('s16 authenticated cannot call ai_reserve', 'ERR 42501 permission denied for function ai_reserve',
       pg_temp.run_as('authenticated', :A,
                      format('SELECT reason FROM public.ai_reserve(%L, NULL, 0.01, 20, 5, 50, ''m'', 3, 15)', :A)));
SELECT pg_temp.expect('s16 anon cannot call ai_quota', 'ERR 42501 permission denied for function ai_quota',
       pg_temp.run_as('anon', NULL, format('SELECT used_today::text FROM public.ai_quota(%L, 20, 5)', :A)));
SELECT pg_temp.expect('s16 authenticated cannot call ai_settle', 'ERR 42501 permission denied for function ai_settle',
       pg_temp.run_as('authenticated', :A, 'SELECT public.ai_settle(1, ''failed'', NULL, NULL, NULL)::text'));
SELECT pg_temp.expect('s16 authenticated cannot call ai_admin_report', 'ERR 42501 permission denied for function ai_admin_report',
       pg_temp.run_as('authenticated', :A, 'SELECT public.ai_admin_report(20, 5)::text'));
SELECT pg_temp.expect('s16 authenticated cannot read ai_usage', 'ERR 42501 permission denied for table ai_usage',
       pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.ai_usage'));
SELECT pg_temp.expect('s16 anon cannot read ai_entitlements', 'ERR 42501 permission denied for table ai_entitlements',
       pg_temp.run_as('anon', NULL, 'SELECT count(*)::text FROM public.ai_entitlements'));
SELECT pg_temp.expect('s16 authenticated cannot grant itself access', 'ERR 42501 permission denied for table ai_entitlements',
       pg_temp.run_as('authenticated', :A, format('INSERT INTO public.ai_entitlements (user_id) VALUES (%L)', :A)));
SELECT pg_temp.expect('s16 service_role can call ai_quota (positive control)', 'OK 0',
       pg_temp.run_as('service_role', NULL, format('SELECT used_today::text FROM public.ai_quota(%L, 20, 5)', :A)));
