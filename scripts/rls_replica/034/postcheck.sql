-- Checks to read AFTER applying migration 034, and at any later time.
--
-- A single SELECT: it writes nothing and can run in any database, including
-- production (SQL Editor or psql). It repeats the catalog checks that 034
-- runs before its COMMIT (5a, 5b, 5d, 5e, 5f, 5g), so that a later change
-- is noticed: for example re-running 008 or 009, which recreates policies
-- that read memberships. Check 5c (planning a read as authenticated) needs
-- SET ROLE and is not repeated here. Each row is
-- "<PASS|FAIL|INFO>  <id> <label>  =>  <measured value>".
-- The expected policy list is the one in section 5 of 034 (a test keeps the
-- two equal).

WITH expected(name) AS (
    SELECT unnest(ARRAY[
        'organizations.organizations_select_accepted_member',
        'memberships.memberships_select_accepted_comember',
        'audit_log.audit_log_select_org_manager',
        'forensic_access_log.forensic_access_log_select_org_manager',
        'projects.projects_select_owner',
        'project_shares.project_shares_select_project_owner',
        'value_milestones.value_milestones_select_project_owner',
        'forensic_timelines.forensic_timelines_select_owner',
        'activities.activities_select_own',
        'activity_code_types.activity_code_types_select_own',
        'activity_codes.activity_codes_select_own',
        'alerts.Users see own alerts',
        'calendars.calendars_select_own',
        'cbs_elements.cbs_elements_select_own',
        'cbs_wbs_mappings.cbs_wbs_mappings_select_own',
        'change_orders.change_orders_select_own',
        'cost_accounts.cost_accounts_select_own',
        'cost_snapshots.cost_snapshots_select_own',
        'cost_time_phased.cost_time_phased_select_own',
        'erp_sources.erp_sources_select_own',
        'financial_periods.financial_periods_select_own',
        'health_scores.Users see own health_scores',
        'lifecycle_override_log.lol_select_own',
        'obs_cbs_assignments.obs_cbs_assignments_select_own',
        'obs_elements.obs_elements_select_own',
        'predecessors.predecessors_select_own',
        'resource_assignments.resource_assignments_select_own',
        'resources.resources_select_own',
        'revision_history.rh_select_own_active',
        'revision_skip_log.rsl_select_own',
        'schedule_derived_artifacts.sda_select_own',
        'task_activity_codes.task_activity_codes_select_own',
        'task_financials.task_financials_select_own',
        'udf_types.udf_types_select_own',
        'udf_values.udf_values_select_own',
        'wbs_elements.wbs_elements_select_own'
    ])
),
affected(t) AS (
    SELECT split_part(name, '.', 1) FROM expected
    UNION SELECT 'program_shares'
    UNION SELECT tablename
            FROM pg_policies
           WHERE schemaname = 'public'
             AND (coalesce(qual, '') || ' ' || coalesce(with_check, ''))
                 ~ '\m(projects|organizations|project_shares|is_org_member)\M'
),
rel AS (
    SELECT c.oid, c.relname, c.relkind, c.relowner, c.relrowsecurity, c.reloptions
      FROM pg_class AS c
     WHERE c.relnamespace = 'public'::regnamespace
       AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
),
client(role) AS (VALUES ('anon'), ('authenticated')),
write_privs(privs) AS (
    SELECT 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'
           || CASE WHEN current_setting('server_version_num')::int >= 170000 THEN ', MAINTAIN' ELSE '' END
),
org_tables(t) AS (
    VALUES ('organizations'), ('memberships'), ('project_shares'), ('program_shares'),
           ('audit_log'), ('forensic_access_log'), ('value_milestones')
),
checks(id, status, label, value) AS (
    SELECT 'pc01', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'no policy reads public.memberships directly (5a)',
           'found: ' || coalesce(string_agg(format('%s.%s', tablename, policyname), ', '
                                            ORDER BY tablename, policyname), 'none')
      FROM pg_policies
     WHERE schemaname = 'public'
       AND (coalesce(qual, '') || ' ' || coalesce(with_check, '')) ~ '\mmemberships\M'

    UNION ALL
    SELECT 'pc02', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'permissive read policies on the affected tables are the expected ones (5b)',
           'unexpected: ' || coalesce(string_agg(format('%s.%s', p.tablename, p.policyname), ', '
                                                 ORDER BY p.tablename, p.policyname), 'none')
      FROM pg_policies AS p
     WHERE p.schemaname = 'public'
       AND p.tablename IN (SELECT t FROM affected)
       AND p.permissive = 'PERMISSIVE'
       AND p.cmd IN ('SELECT', 'ALL')
       AND p.roles && ARRAY['public', 'anon', 'authenticated']::name[]
       AND format('%s.%s', p.tablename, p.policyname) NOT IN (SELECT name FROM expected)

    UNION ALL
    SELECT 'pc03', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'client roles cannot write to any relation in public (5d)',
           'writable: ' || coalesce(string_agg(DISTINCT format('%s (%s, owner %s)', r.relname, c.role,
                                                               pg_get_userbyid(r.relowner)), ', '), 'none')
      FROM rel AS r
     CROSS JOIN client AS c
     CROSS JOIN write_privs AS w
     WHERE has_table_privilege(c.role, r.oid, w.privs)
        OR has_any_column_privilege(c.role, r.oid, 'INSERT, UPDATE, REFERENCES')

    UNION ALL
    SELECT 'pc04', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'client roles read no relation whose rows RLS does not filter (5e)',
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
    SELECT 'pc05', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'organization tables: nothing for anon, nothing on program_shares for authenticated, memberships columns as granted (5f)',
           'unexpected: ' || coalesce(string_agg(x, ', ' ORDER BY x), 'none')
      FROM (
            SELECT format('%s (anon)', o.t) AS x
              FROM org_tables AS o
             WHERE has_any_column_privilege('anon', format('public.%I', o.t), 'SELECT, INSERT, UPDATE, REFERENCES')
            UNION ALL
            SELECT 'program_shares (authenticated)'
             WHERE has_any_column_privilege('authenticated', 'public.program_shares', 'SELECT, INSERT, UPDATE, REFERENCES')
            UNION ALL
            SELECT format('memberships.%s (authenticated)', a.attname)
              FROM pg_attribute AS a
             WHERE a.attrelid = 'public.memberships'::regclass
               AND a.attnum > 0
               AND NOT a.attisdropped
               AND a.attname NOT IN ('org_id', 'user_id', 'role', 'accepted_at')
               AND has_column_privilege('authenticated', a.attrelid, a.attnum, 'SELECT')
           ) AS s

    UNION ALL
    SELECT 'pc06', CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           'default privileges of postgres grant clients no table write (5g)',
           'granted: ' || coalesce(string_agg(DISTINCT format('%s %s to %s',
                                              CASE d.defaclnamespace WHEN 0 THEN 'all schemas'
                                                   ELSE d.defaclnamespace::regnamespace::text END,
                                              a.privilege_type,
                                              CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END), ', '), 'none')
      FROM pg_default_acl AS d
     CROSS JOIN LATERAL aclexplode(d.defaclacl) AS a
     WHERE d.defaclrole = 'postgres'::regrole
       AND d.defaclobjtype = 'r'
       AND d.defaclnamespace IN (0::oid, 'public'::regnamespace::oid)
       AND a.privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER', 'MAINTAIN')
       AND (a.grantee = 0::oid OR a.grantee IN ('anon'::regrole::oid, 'authenticated'::regrole::oid))

    UNION ALL
    SELECT 'pc07',
           CASE WHEN count(*) = 1
                     AND bool_and(n.nspname = 'private'
                                  AND pg_get_function_identity_arguments(p.oid) = 'p_org_id uuid, p_roles text[]'
                                  AND p.prosecdef
                                  AND pg_get_userbyid(p.proowner) = 'postgres'
                                  AND NOT has_function_privilege('anon', p.oid, 'EXECUTE')
                                  AND NOT has_schema_privilege('anon', n.oid, 'USAGE')
                                  AND NOT has_schema_privilege('authenticated', n.oid, 'USAGE'))
                THEN 'PASS' ELSE 'FAIL' END,
           'the helper is private.is_org_member only: SECURITY DEFINER, owner postgres, no anon EXECUTE, no client USAGE on private',
           coalesce(string_agg(format('%s.is_org_member(%s) definer=%s owner=%s', n.nspname,
                                      pg_get_function_identity_arguments(p.oid), p.prosecdef,
                                      pg_get_userbyid(p.proowner)), ', '), 'absent')
      FROM pg_proc AS p
      JOIN pg_namespace AS n ON n.oid = p.pronamespace
     WHERE p.proname = 'is_org_member'
       AND n.nspname IN ('public', 'private')

    UNION ALL
    SELECT 'pc08', 'INFO',
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
)
SELECT format('%-6s %s %s  =>  %s', status, id, label, value)
  FROM checks
 ORDER BY id;
