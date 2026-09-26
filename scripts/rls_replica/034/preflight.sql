-- Census to read BEFORE applying migration 034, and again after it.
--
-- A single SELECT: it writes nothing, takes no lock beyond a read, and can
-- run in any database, including production (SQL Editor or psql). Each row
-- is "<STATUS>  <id> <label>  =>  <measured value>":
--   PASS    the condition 034 relies on holds
--   FAIL    034 will abort, or its REVOKE would not take effect, until this
--           is resolved
--   REVIEW  rows or history a person should look at; 034 does not change them
--   INFO    a measurement with no expectation
-- The list of 56 tables is the one in section 4 of 034 (a test keeps the
-- two equal).

WITH expected(name) AS (
    SELECT unnest(ARRAY[
        'activities', 'activity_code_types', 'activity_codes', 'alerts',
        'analysis_results', 'api_keys', 'audit_log', 'benchmark_metrics',
        'benchmark_projects', 'calendars', 'cbs_elements', 'cbs_wbs_mappings',
        'change_orders', 'comparison_results', 'cost_accounts', 'cost_snapshots',
        'cost_time_phased', 'duration_predictions', 'erp_sources', 'evm_analyses',
        'exported_files', 'financial_periods', 'float_snapshots',
        'forensic_access_log', 'forensic_timelines', 'generated_schedules',
        'health_scores', 'lifecycle_override_log', 'memberships',
        'obs_cbs_assignments', 'obs_elements', 'optimization_runs',
        'organizations', 'predecessors', 'program_shares', 'programs',
        'project_shares', 'projects', 'reports', 'resource_assignments',
        'resources', 'revision_history', 'revision_skip_log', 'risk_register',
        'risk_simulations', 'schedule_derived_artifacts', 'schedule_uploads',
        'task_activity_codes', 'task_financials', 'tia_analyses', 'udf_types',
        'udf_values', 'user_profiles', 'value_milestones', 'wbs_elements',
        'what_if_scenarios'
    ])
),
rel AS (
    SELECT c.oid, c.relname, c.relkind, c.relowner, c.relacl, c.relrowsecurity, c.reloptions,
           e.name IS NOT NULL AS listed
      FROM pg_class AS c
      LEFT JOIN expected AS e ON e.name = c.relname
     WHERE c.relnamespace = 'public'::regnamespace
       AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
),
client(role) AS (VALUES ('anon'), ('authenticated')),
write_privs(privs) AS (
    SELECT 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'
           || CASE WHEN current_setting('server_version_num')::int >= 170000 THEN ', MAINTAIN' ELSE '' END
),
history AS (
    SELECT CASE WHEN to_regclass('supabase_migrations.schema_migrations') IS NULL THEN NULL
                ELSE (xpath('//v/text()', query_to_xml(
                          'SELECT string_agg(version, '','' ORDER BY version) AS v '
                          'FROM supabase_migrations.schema_migrations', false, false, '')))[1]::text
           END AS versions
),
checks(id, status, label, value) AS (
    SELECT 'pf01', 'INFO', 'server', current_setting('server_version')

    UNION ALL
    SELECT 'pf02', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'the 56 tables of 001-033 exist in public',
           'missing: ' || coalesce(string_agg(e.name, ', ' ORDER BY e.name), 'none')
      FROM expected AS e
     WHERE to_regclass(format('public.%I', e.name)) IS NULL

    UNION ALL
    SELECT 'pf03', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'REVIEW' END,
           'no other table, view, materialized view or foreign table in public',
           'others: ' || coalesce(string_agg(format('%s (kind %s, owner %s)', r.relname, r.relkind,
                                                    pg_get_userbyid(r.relowner)), ', ' ORDER BY r.relname), 'none')
      FROM rel AS r
     WHERE NOT r.listed

    UNION ALL
    SELECT 'pf04', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'the 56 tables are owned by postgres (else REVOKE only warns and CREATE POLICY fails)',
           'other owners: ' || coalesce(string_agg(format('%s (%s)', r.relname, pg_get_userbyid(r.relowner)),
                                                   ', ' ORDER BY r.relname), 'none')
      FROM rel AS r
     WHERE r.listed AND pg_get_userbyid(r.relowner) <> 'postgres'

    UNION ALL
    SELECT 'pf05', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'client ACL entries on the 56 tables were granted by the owner (else the REVOKE leaves them)',
           'other grantors: ' || coalesce(string_agg(DISTINCT format('%s (%s by %s)', r.relname,
                                                   CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
                                                   pg_get_userbyid(a.grantor)), ', '), 'none')
      FROM rel AS r
     CROSS JOIN LATERAL aclexplode(r.relacl) AS a
     WHERE r.listed
       AND a.grantor <> r.relowner
       AND (a.grantee = 0::oid OR a.grantee IN ('anon'::regrole::oid, 'authenticated'::regrole::oid))

    UNION ALL
    SELECT 'pf06', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'relations outside the list give clients no write privilege (else 034 aborts at check 5d)',
           'writable: ' || coalesce(string_agg(DISTINCT format('%s (%s)', r.relname, c.role), ', '), 'none')
      FROM rel AS r
     CROSS JOIN client AS c
     CROSS JOIN write_privs AS w
     WHERE NOT r.listed
       AND (has_table_privilege(c.role, r.oid, w.privs)
            OR has_any_column_privilege(c.role, r.oid, 'INSERT, UPDATE, REFERENCES'))

    UNION ALL
    SELECT 'pf07', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'clients read no relation whose rows RLS does not filter (else 034 aborts at check 5e)',
           'unfiltered: ' || coalesce(string_agg(DISTINCT format('%s (kind %s, %s)', r.relname, r.relkind, c.role), ', '), 'none')
      FROM rel AS r
     CROSS JOIN client AS c
     WHERE has_any_column_privilege(c.role, r.oid, 'SELECT')
       AND (   (r.relkind IN ('r', 'p') AND NOT r.relrowsecurity)
            OR (r.relkind = 'v'
                AND NOT coalesce((SELECT o.option_value::boolean
                                    FROM pg_options_to_table(r.reloptions) AS o
                                   WHERE o.option_name = 'security_invoker'), false))
            OR r.relkind IN ('m', 'f'))

    UNION ALL
    SELECT 'pf08', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'no default privilege of postgres for all schemas grants clients table writes (034 revokes only the public one)',
           'granted: ' || coalesce(string_agg(DISTINCT format('%s to %s', a.privilege_type,
                                              CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END), ', '), 'none')
      FROM pg_default_acl AS d
     CROSS JOIN LATERAL aclexplode(d.defaclacl) AS a
     WHERE d.defaclrole = 'postgres'::regrole
       AND d.defaclobjtype = 'r'
       AND d.defaclnamespace = 0::oid
       AND a.privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER', 'MAINTAIN')
       AND (a.grantee = 0::oid OR a.grantee IN ('anon'::regrole::oid, 'authenticated'::regrole::oid))

    UNION ALL
    SELECT 'pf09', 'INFO',
           'default privileges of other roles in public that grant clients table writes (postgres cannot change them)',
           coalesce(string_agg(DISTINCT format('%s: %s to %s', pg_get_userbyid(d.defaclrole), a.privilege_type,
                                              CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END), ', '), 'none')
      FROM pg_default_acl AS d
     CROSS JOIN LATERAL aclexplode(d.defaclacl) AS a
     WHERE d.defaclrole <> 'postgres'::regrole
       AND d.defaclobjtype = 'r'
       AND d.defaclnamespace IN (0::oid, 'public'::regnamespace::oid)
       AND a.privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')
       AND (a.grantee = 0::oid OR a.grantee IN ('anon'::regrole::oid, 'authenticated'::regrole::oid))

    UNION ALL
    SELECT 'pf10', CASE WHEN n.nspname IS NULL
                             OR (pg_get_userbyid(n.nspowner) = 'postgres'
                                 AND NOT has_schema_privilege('anon', n.oid, 'USAGE, CREATE')
                                 AND NOT has_schema_privilege('authenticated', n.oid, 'USAGE, CREATE'))
                        THEN 'PASS' ELSE 'FAIL' END,
           'schema private is absent, or owned by postgres with nothing granted to client roles',
           coalesce('owner ' || pg_get_userbyid(n.nspowner) || ', acl ' || coalesce(n.nspacl::text, 'default'), 'absent')
      FROM (SELECT 1) AS one
      LEFT JOIN pg_namespace AS n ON n.nspname = 'private'

    UNION ALL
    SELECT 'pf11', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'no other is_org_member in public or private',
           'found: ' || coalesce(string_agg(format('%s.is_org_member(%s)', n.nspname,
                                                   pg_get_function_identity_arguments(p.oid)), ', '), 'none')
      FROM pg_proc AS p
      JOIN pg_namespace AS n ON n.oid = p.pronamespace
     WHERE n.nspname IN ('public', 'private')
       AND p.proname = 'is_org_member'
       AND NOT (n.nspname = 'private'
                AND pg_get_function_identity_arguments(p.oid) = 'p_org_id uuid, p_roles text[]')

    UNION ALL
    SELECT 'pf12', CASE WHEN r.rolsuper OR r.rolbypassrls
                             OR (pg_get_userbyid(c.relowner) = 'postgres' AND NOT c.relforcerowsecurity)
                        THEN 'PASS' ELSE 'FAIL' END,
           'postgres (the helper owner) is exempt from RLS on memberships',
           format('super=%s bypassrls=%s memberships owner=%s force=%s', r.rolsuper, r.rolbypassrls,
                  pg_get_userbyid(c.relowner), c.relforcerowsecurity)
      FROM pg_roles AS r, pg_class AS c
     WHERE r.rolname = 'postgres'
       AND c.oid = to_regclass('public.memberships')

    UNION ALL
    SELECT 'pf13',
           CASE WHEN h.versions IS NULL THEN 'INFO'
                WHEN count(v.n) FILTER (WHERE NOT (to_char(v.n, 'FM000') = ANY (string_to_array(h.versions, ',')))) = 0
                THEN 'PASS' ELSE 'REVIEW' END,
           'migration history lists 001-033 (a missing version can be replayed by a later push)',
           CASE WHEN h.versions IS NULL THEN 'not measured: supabase_migrations.schema_migrations is absent'
                ELSE 'recorded ' || cardinality(string_to_array(h.versions, ','))
                     || ' (' || split_part(h.versions, ',', 1) || ' .. '
                     || reverse(split_part(reverse(h.versions), ',', 1)) || '), missing: ' || coalesce(string_agg(to_char(v.n, 'FM000'), ', ' ORDER BY v.n)
                                             FILTER (WHERE NOT (to_char(v.n, 'FM000') = ANY (string_to_array(h.versions, ',')))), 'none')
           END
      FROM history AS h
     CROSS JOIN generate_series(1, 33) AS v(n)
     GROUP BY h.versions

    -- Rows written by client roles before 034 remain after it. These list
    -- the ones the API would act on.
    UNION ALL
    SELECT 'pf20', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'REVIEW' END,
           'projects whose storage_path is outside the owner''s folder (the API downloads that path)',
           count(*) || ' ' || coalesce(string_agg(p.id::text, ', ' ORDER BY p.id) FILTER (WHERE p.rn <= 20), '')
      FROM (SELECT id, row_number() OVER (ORDER BY id) AS rn
              FROM public.projects
             WHERE coalesce(storage_path, '') <> ''
               AND split_part(storage_path, '/', 1) <> coalesce(user_id::text, 'anonymous')) AS p

    UNION ALL
    SELECT 'pf21', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'REVIEW' END,
           'projects that point at another user''s upload',
           count(*) || ' ' || coalesce(string_agg(p.id::text, ', ' ORDER BY p.id) FILTER (WHERE p.rn <= 20), '')
      FROM (SELECT p.id, row_number() OVER (ORDER BY p.id) AS rn
              FROM public.projects AS p
              JOIN public.schedule_uploads AS u ON u.id = p.upload_id
             WHERE u.user_id IS DISTINCT FROM p.user_id) AS p

    UNION ALL
    SELECT 'pf22', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'REVIEW' END,
           'organizations with no membership (includes workspaces of deleted accounts)',
           count(*) || ' ' || coalesce(string_agg(o.id::text, ', ' ORDER BY o.id) FILTER (WHERE o.rn <= 20), '')
      FROM (SELECT o.id, row_number() OVER (ORDER BY o.id) AS rn
              FROM public.organizations AS o
             WHERE NOT EXISTS (SELECT 1 FROM public.memberships AS m WHERE m.org_id = o.id)) AS o

    UNION ALL
    SELECT 'pf23', 'INFO',
           'benchmark_projects: total / no contributor / not exactly one metrics row (contribute_benchmark writes one)',
           (SELECT count(*) FROM public.benchmark_projects) || ' / '
           || (SELECT count(*) FROM public.benchmark_projects WHERE contributed_by IS NULL) || ' / '
           || (SELECT count(*) FROM public.benchmark_projects AS b
                WHERE (SELECT count(*) FROM public.benchmark_metrics AS m WHERE m.benchmark_project_id = b.id) <> 1)
)
SELECT format('%-6s %s %s  =>  %s', status, id, label, value)
  FROM checks
 ORDER BY id;
