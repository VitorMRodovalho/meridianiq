-- Read AFTER applying migration 040, and after any later hand-applied
-- migration (a single SELECT; writes nothing). Detects, among others, a
-- re-application of 036 that would restore ai_forget_user without clearing
-- the entitlement's note.
-- Each row: "<PASS|FAIL> <id> <label> => <measured value>".

WITH checks(id, status, label, value) AS (
    SELECT 'rc01',
           CASE WHEN p.oid IS NOT NULL
                 AND NOT p.prosecdef
                 AND pg_get_userbyid(p.proowner) = 'postgres'
                 AND NOT has_function_privilege('anon', p.oid, 'EXECUTE')
                 AND NOT has_function_privilege('authenticated', p.oid, 'EXECUTE')
                 AND NOT has_function_privilege('service_role', p.oid, 'EXECUTE')
                THEN 'PASS' ELSE 'FAIL' END,
           'ai_purge_decided_requests: invoker, owned by postgres, callable by no API role',
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
    SELECT 'rc03',
           CASE WHEN count(*) = 2 THEN 'PASS' ELSE 'FAIL' END,
           'both meridianiq cron jobs active, as postgres, in this database, with their schedules',
           count(*)::text || ' of 2 jobs match'
      FROM cron.job AS j
     WHERE j.active AND j.username = 'postgres' AND j.database = current_database()
       AND ((j.jobname = 'meridianiq-ai-requests-purge' AND j.schedule = '17 3 * * *'
             AND j.command = 'SELECT public.ai_purge_decided_requests()')
         OR (j.jobname = 'meridianiq-cron-history-cleanup' AND j.schedule = '27 3 * * *'))
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
           CASE WHEN count(*) FILTER (WHERE r.status = 'succeeded') = count(*) THEN 'PASS' ELSE 'FAIL' END,
           'every recorded run of the meridianiq jobs succeeded (0 runs is a PASS right after applying)',
           count(*)::text || ' runs, ' || count(*) FILTER (WHERE r.status <> 'succeeded')::text || ' not succeeded'
      FROM cron.job_run_details AS r
     WHERE r.jobid IN (SELECT j.jobid FROM cron.job AS j WHERE j.jobname LIKE 'meridianiq-%')
)
SELECT format('%-5s %s %s  =>  %s', status, id, label, value) FROM checks ORDER BY id;
