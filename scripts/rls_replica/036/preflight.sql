-- Read BEFORE applying migration 036 (a single SELECT; writes nothing),
-- also before applying it AGAIN after a re-application of 035 (postcheck
-- qc05). Every row must be PASS; a FAIL means stop and look, never loosen the
-- migration's guard. Each row: "<PASS|FAIL> <id> <label> => <measured value>".
-- Expect exactly 6 rows; every check yields one row even when what it looks
-- for is missing.

WITH checks(id, status, label, value) AS (
    SELECT 'pf01',
           CASE WHEN count(*) FILTER (WHERE pg_get_userbyid(p.proowner) <> 'postgres') = 0
                THEN 'PASS' ELSE 'FAIL' END,
           'existing ai_* functions in public are owned by postgres (036 guard requires it)',
           coalesce(string_agg(p.proname || ':' || pg_get_userbyid(p.proowner), ', ' ORDER BY p.proname), 'none')
      FROM pg_proc AS p
     WHERE p.pronamespace = 'public'::regnamespace AND p.proname LIKE 'ai\_%'
    UNION ALL
    SELECT 'pf02',
           CASE WHEN to_regclass('public.ai_access_requests') IS NULL
                  OR (SELECT string_agg(a.attname || ':' || format_type(a.atttypid, a.atttypmod), ','
                                        ORDER BY a.attnum)
                        FROM pg_attribute AS a
                       WHERE a.attrelid = to_regclass('public.ai_access_requests')
                         AND a.attnum > 0 AND NOT a.attisdropped)
                     = 'user_id:uuid,status:text,note:text,requested_at:timestamp with time zone,'
                       'decided_at:timestamp with time zone,decided_by:uuid'
                THEN 'PASS' ELSE 'FAIL' END,
           'public.ai_access_requests is absent, or has 036''s columns (else CREATE ... IF NOT EXISTS keeps another shape)',
           coalesce((SELECT string_agg(a.attname, ',' ORDER BY a.attnum)
                       FROM pg_attribute AS a
                      WHERE a.attrelid = to_regclass('public.ai_access_requests')
                        AND a.attnum > 0 AND NOT a.attisdropped), 'absent')
    UNION ALL
    SELECT 'pf03',
           CASE md5(p.prosrc) WHEN '38c0bb1f7e99a5d6738655384f9bee3a' THEN 'PASS' WHEN '5c186fbedb6de58add81ea8a50ff1e86' THEN 'PASS' ELSE 'FAIL' END,
           'ai_grant is the 035 or the 036 version (036 replaces it; a local hot-fix would be overwritten)',
           'md5 ' || coalesce(md5(p.prosrc), 'ai_grant absent')
      FROM (SELECT 1) AS one
      LEFT JOIN pg_proc AS p
        ON p.oid = to_regprocedure('public.ai_grant(uuid,text,uuid,integer,numeric,text,text,text)')
    UNION ALL
    SELECT 'pf04',
           CASE WHEN has_column_privilege('postgres', 'auth.users', 'email', 'SELECT')
                 AND has_column_privilege('postgres', 'auth.users', 'email_confirmed_at', 'SELECT')
                 AND has_column_privilege('postgres', 'auth.users', 'deleted_at', 'SELECT')
                THEN 'PASS' ELSE 'FAIL' END,
           'postgres (owner of the definer) can read auth.users email, email_confirmed_at, deleted_at',
           'checked'
    UNION ALL
    SELECT 'pf05',
           CASE WHEN n.oid IS NOT NULL
                 AND pg_get_userbyid(n.nspowner) = 'postgres'
                 AND NOT has_schema_privilege('anon', n.oid, 'USAGE')
                 AND NOT has_schema_privilege('authenticated', n.oid, 'USAGE')
                THEN 'PASS' ELSE 'FAIL' END,
           'schema private exists, owned by postgres, no client USAGE (034)',
           coalesce('owner ' || pg_get_userbyid(n.nspowner), 'schema private absent')
      FROM (SELECT 1) AS one
      LEFT JOIN pg_namespace AS n ON n.nspname = 'private'
    UNION ALL
    SELECT 'pf06',
           CASE WHEN current_user = 'postgres' THEN 'PASS' ELSE 'FAIL' END,
           'connected as postgres (the owner the migration expects)',
           current_user::text
)
SELECT format('%-5s %s %s  =>  %s', status, id, label, value) FROM checks ORDER BY id;
