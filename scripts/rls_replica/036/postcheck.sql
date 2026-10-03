-- Read AFTER applying migration 036, and after any later hand-applied
-- migration (a single SELECT; writes nothing). Detects, among others, a
-- re-application of 035 that would drop ai_grant's request-closing statement.
-- Each row: "<PASS|FAIL> <id> <label> => <measured value>".

WITH fns AS (
    SELECT p.oid, n.nspname, p.proname, p.prosecdef, pg_get_userbyid(p.proowner) AS owner
      FROM pg_proc AS p
      JOIN pg_namespace AS n ON n.oid = p.pronamespace
     WHERE (n.nspname = 'public' AND p.proname LIKE 'ai\_%')
        OR (n.nspname = 'private' AND p.proname = 'ai_pending_requests')
),
checks(id, status, label, value) AS (
    SELECT 'qc01',
           CASE WHEN count(*) FILTER (WHERE has_function_privilege('anon', f.oid, 'EXECUTE')
                                         OR has_function_privilege('authenticated', f.oid, 'EXECUTE')) = 0
                THEN 'PASS' ELSE 'FAIL' END,
           'no ai_* function (public or private) is callable by anon or authenticated',
           count(*)::text || ' functions checked'
      FROM fns AS f
    UNION ALL
    SELECT 'qc02',
           CASE WHEN string_agg(f.nspname || '.' || f.proname, ',') FILTER (WHERE f.prosecdef)
                     = 'private.ai_pending_requests'
                 AND bool_and(f.owner = 'postgres')
                THEN 'PASS' ELSE 'FAIL' END,
           'the only definer is private.ai_pending_requests; every function owned by postgres',
           coalesce(string_agg(f.nspname || '.' || f.proname, ',') FILTER (WHERE f.prosecdef), 'no definer')
      FROM fns AS f
    UNION ALL
    SELECT 'qc03',
           CASE WHEN NOT has_schema_privilege('anon', 'private', 'USAGE')
                 AND NOT has_schema_privilege('authenticated', 'private', 'USAGE')
                 AND has_schema_privilege('service_role', 'private', 'USAGE')
                THEN 'PASS' ELSE 'FAIL' END,
           'schema private: USAGE for service_role only among the API roles',
           'checked'
    UNION ALL
    SELECT 'qc04',
           CASE WHEN c.relrowsecurity
                 AND NOT has_table_privilege('anon', c.oid, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE')
                 AND NOT has_table_privilege('authenticated', c.oid, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE')
                 AND has_table_privilege('service_role', c.oid, 'SELECT, INSERT, UPDATE, DELETE')
                 AND NOT has_table_privilege('service_role', c.oid, 'TRUNCATE')
                THEN 'PASS' ELSE 'FAIL' END,
           'ai_access_requests: RLS on, nothing for clients, service_role S/I/U/D and no TRUNCATE',
           'rls=' || c.relrowsecurity
      FROM pg_class AS c
     WHERE c.oid = 'public.ai_access_requests'::regclass
    UNION ALL
    SELECT 'qc05',
           CASE WHEN position('ai_access_requests' IN p.prosrc) > 0 THEN 'PASS' ELSE 'FAIL' END,
           'ai_grant closes pending requests (FAIL: 035 was re-applied after 036; apply 036 again)',
           'md5 ' || md5(p.prosrc)
      FROM pg_proc AS p
     WHERE p.oid = 'public.ai_grant(uuid,text,uuid,integer,numeric,text,text,text)'::regprocedure
)
SELECT format('%-5s %s %s  =>  %s', status, id, label, value) FROM checks ORDER BY id;
