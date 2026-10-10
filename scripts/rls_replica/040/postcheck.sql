-- Read AFTER applying migration 040, again the day after (rc07), and after
-- any later hand-applied migration. Read-only (SELECTs; writes nothing).
-- Detects, among others, a re-application of 036 that would restore
-- ai_forget_user without clearing the entitlement's note, a purge that never
-- runs (rc07) and decided requests left past their time (rc06).
-- Each row: "<PASS|FAIL|INFO> <id> <label> => <measured value>".
-- Run with psql (it uses \gset and \if).

SELECT to_regclass('cron.job') IS NOT NULL AS has_cron \gset

WITH checks(id, status, label, value) AS (
    SELECT 'rc01',
           CASE WHEN p.oid IS NOT NULL
                 AND NOT p.prosecdef
                 AND pg_get_userbyid(p.proowner) = 'postgres'
                 AND NOT has_function_privilege('anon', p.oid, 'EXECUTE')
                 AND NOT has_function_privilege('authenticated', p.oid, 'EXECUTE')
                 AND NOT has_function_privilege('service_role', p.oid, 'EXECUTE')
                 AND NOT (SELECT c.relforcerowsecurity FROM pg_class AS c
                           WHERE c.oid = 'public.ai_access_requests'::regclass)
                THEN 'PASS' ELSE 'FAIL' END,
           'ai_purge_decided_requests: invoker, owned by postgres, callable by no API role; no FORCE RLS on the table',
           CASE WHEN p.oid IS NULL THEN 'absent' ELSE 'present' END
      FROM (SELECT 1) AS one
      LEFT JOIN pg_proc AS p ON p.oid = to_regprocedure('public.ai_purge_decided_requests()')
    UNION ALL
    SELECT 'rc02',
           CASE WHEN md5(p.prosrc) = '10c2f987c6eb5637f1a4dbcc894591c1' THEN 'PASS' ELSE 'FAIL' END,
           'ai_forget_user is exactly 040''s (FAIL with 036''s md5 e6742565: 036 was re-applied, apply 040 again; any other md5: a later change, update this check)',
           'md5 ' || coalesce(md5(p.prosrc), 'ai_forget_user absent')
      FROM (SELECT 1) AS one
      LEFT JOIN pg_proc AS p ON p.oid = to_regprocedure('public.ai_forget_user(uuid)')
    UNION ALL
    SELECT 'rc06',
           CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'no decided request older than 31 days is left (the outcome, whatever runs the purge)',
           count(*)::text || ' left'
      FROM public.ai_access_requests AS r
     WHERE r.status <> 'pending' AND r.decided_at < now() - interval '31 days'
)
SELECT format('%-5s %s %s  =>  %s', status, id, label, value) FROM checks ORDER BY id;

\if :has_cron
WITH checks(id, status, label, value) AS (
    SELECT 'rc03',
           CASE WHEN count(*) = 2 THEN 'PASS' ELSE 'FAIL' END,
           'both meridianiq cron jobs active, as postgres, in this database, with their exact schedules and commands',
           count(*)::text || ' of 2 jobs match'
      FROM cron.job AS j
     WHERE j.active AND j.username = 'postgres' AND j.database = current_database()
       AND ((j.jobname = 'meridianiq-ai-requests-purge' AND j.schedule = '17 3 * * *'
             AND j.command = 'SELECT public.ai_purge_decided_requests()')
         OR (j.jobname = 'meridianiq-cron-history-cleanup' AND j.schedule = '27 3 * * *'
             AND j.command = $c$DELETE FROM cron.job_run_details WHERE coalesce(end_time, start_time) < now() - interval '7 days' AND jobid NOT IN (SELECT jobid FROM cron.job WHERE jobname NOT LIKE 'meridianiq-%')$c$))
    UNION ALL
    SELECT 'rc04',
           CASE WHEN NOT has_schema_privilege('anon', 'cron', 'USAGE')
                 AND NOT has_schema_privilege('authenticated', 'cron', 'USAGE')
                 AND NOT has_schema_privilege('service_role', 'cron', 'USAGE')
                THEN 'PASS' ELSE 'FAIL' END,
           'schema cron: no USAGE for anon, authenticated or service_role',
           'checked'
    UNION ALL
    SELECT 'rc05',
           CASE WHEN count(*) FILTER (WHERE r.status = 'failed') = 0 THEN 'PASS' ELSE 'FAIL' END,
           'no recorded run of a meridianiq job failed',
           count(*)::text || ' runs, ' || count(*) FILTER (WHERE r.status = 'failed')::text || ' failed'
      FROM cron.job_run_details AS r
     WHERE r.jobid IN (SELECT j.jobid FROM cron.job AS j WHERE j.jobname LIKE 'meridianiq-%')
    UNION ALL
    -- 0 runs is INFO (just applied: read again after the next 03:17 GMT);
    -- runs, but none succeeded in the last 26 hours, is a FAIL.
    SELECT 'rc07',
           CASE WHEN count(*) = 0 THEN 'INFO'
                WHEN max(r.end_time) FILTER (WHERE r.status = 'succeeded') > now() - interval '26 hours'
                THEN 'PASS' ELSE 'FAIL' END,
           'the purge job succeeded in the last 26 hours (INFO: no run yet, read again after 03:17 GMT)',
           count(*)::text || ' runs, last success '
               || coalesce(max(r.end_time) FILTER (WHERE r.status = 'succeeded')::text, 'never')
      FROM cron.job_run_details AS r
     WHERE r.jobid = (SELECT j.jobid FROM cron.job AS j WHERE j.jobname = 'meridianiq-ai-requests-purge')
)
SELECT format('%-5s %s %s  =>  %s', status, id, label, value) FROM checks ORDER BY id;
\else
SELECT 'FAIL  rc03 pg_cron is not installed (schema cron absent): 040 is not applied  =>  cron.job absent';
\endif
