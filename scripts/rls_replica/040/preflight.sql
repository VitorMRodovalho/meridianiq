-- Read BEFORE applying migration 040 (a single SELECT; writes nothing), as
-- postgres. Measured in prod on 2026-10-10: every row PASS (PostgreSQL 17.6,
-- pg_cron preloaded with its launcher running, cron.database_name postgres,
-- cron.timezone GMT, ai_forget_user at 036's md5).
-- Each row: "<PASS|FAIL> <id> <label> => <measured value>".

WITH checks(id, status, label, value) AS (
    SELECT 'pf01',
           CASE WHEN current_user = 'postgres' THEN 'PASS' ELSE 'FAIL' END,
           'connected as postgres (the owner the migration expects)',
           current_user::text
    UNION ALL
    SELECT 'pf02',
           CASE WHEN current_setting('shared_preload_libraries') ~ '(^|[ ,])pg_cron([ ,]|$)'
                 AND EXISTS (SELECT 1 FROM pg_available_extension_versions
                              WHERE name = 'pg_cron' AND version = '1.6.4')
                THEN 'PASS' ELSE 'FAIL' END,
           'pg_cron is preloaded and 1.6.4 is available',
           current_setting('shared_preload_libraries')
    UNION ALL
    SELECT 'pf03',
           CASE WHEN current_setting('cron.database_name', true) = current_database() THEN 'PASS' ELSE 'FAIL' END,
           'cron.database_name is this database (the jobs run here)',
           coalesce(current_setting('cron.database_name', true), '<unset>') || ', timezone '
               || coalesce(current_setting('cron.timezone', true), '<unset>')
    UNION ALL
    SELECT 'pf04',
           CASE WHEN (SELECT count(*) FROM pg_stat_activity WHERE backend_type ILIKE '%cron%') >= 1
                THEN 'PASS' ELSE 'FAIL' END,
           'the pg_cron launcher is running (else jobs would be scheduled and never run)',
           (SELECT count(*) FROM pg_stat_activity WHERE backend_type ILIKE '%cron%')::text || ' backend(s)'
    UNION ALL
    SELECT 'pf05',
           CASE WHEN md5(p.prosrc) IN ('e6742565f03a0d0c551817c169cef9ad', '10c2f987c6eb5637f1a4dbcc894591c1')
                THEN 'PASS' ELSE 'FAIL' END,
           'ai_forget_user is 036''s or 040''s (040 refuses anything else)',
           'md5 ' || coalesce(md5(p.prosrc), 'absent')
      FROM (SELECT 1) AS one
      LEFT JOIN pg_proc AS p ON p.oid = to_regprocedure('public.ai_forget_user(uuid)')
    UNION ALL
    SELECT 'pf06',
           CASE WHEN NOT c.relforcerowsecurity AND pg_get_userbyid(c.relowner) = 'postgres'
                 AND (SELECT r.rolbypassrls FROM pg_roles AS r WHERE r.rolname = 'postgres')
                THEN 'PASS' ELSE 'FAIL' END,
           'ai_access_requests owned by postgres, no FORCE RLS, postgres bypasses RLS (the purge sees every row)',
           'force=' || c.relforcerowsecurity
      FROM pg_class AS c
     WHERE c.oid = 'public.ai_access_requests'::regclass
)
SELECT format('%-5s %s %s  =>  %s', status, id, label, value) FROM checks ORDER BY id;
