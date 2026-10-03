-- Read BEFORE applying migration 036 (a single SELECT; writes nothing).
-- Every row must be PASS; a FAIL means stop and look, never loosen the
-- migration's guard. Each row: "<PASS|FAIL> <id> <label> => <measured value>".

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
           CASE WHEN to_regclass('public.ai_access_requests') IS NULL THEN 'PASS' ELSE 'FAIL' END,
           'public.ai_access_requests does not exist yet (else CREATE ... IF NOT EXISTS keeps an older shape)',
           coalesce(to_regclass('public.ai_access_requests')::text, 'absent')
    UNION ALL
    SELECT 'pf03',
           CASE WHEN position('ai_access_granted' IN p.prosrc) > 0
                 AND position('ai_access_requests' IN p.prosrc) = 0
                THEN 'PASS' ELSE 'FAIL' END,
           'ai_grant is the 035 version (036 replaces it; a local hot-fix would be overwritten)',
           'md5 ' || md5(p.prosrc)
      FROM pg_proc AS p
     WHERE p.oid = 'public.ai_grant(uuid,text,uuid,integer,numeric,text,text,text)'::regprocedure
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
           CASE WHEN pg_get_userbyid(n.nspowner) = 'postgres'
                 AND NOT has_schema_privilege('anon', n.oid, 'USAGE')
                 AND NOT has_schema_privilege('authenticated', n.oid, 'USAGE')
                THEN 'PASS' ELSE 'FAIL' END,
           'schema private exists, owned by postgres, no client USAGE (034)',
           'owner ' || pg_get_userbyid(n.nspowner)
      FROM pg_namespace AS n
     WHERE n.nspname = 'private'
    UNION ALL
    SELECT 'pf06',
           CASE WHEN current_user = 'postgres' THEN 'PASS' ELSE 'FAIL' END,
           'connected as postgres (the owner the migration expects)',
           current_user::text
)
SELECT format('%-5s %s %s  =>  %s', status, id, label, value) FROM checks ORDER BY id;
