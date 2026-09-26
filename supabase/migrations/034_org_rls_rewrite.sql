-- Migration 034: organization reads through an accepted-membership helper,
-- owner-only project reads, and read-only table privileges for client roles
--
-- 1. public.is_org_member(p_org_id uuid, p_roles text[] DEFAULT NULL)
--    returns true when auth.uid() holds an ACCEPTED membership
--    (accepted_at IS NOT NULL) in p_org_id, with a role in p_roles when
--    p_roles is given (NULL means any role). It is SECURITY DEFINER, STABLE,
--    with an empty search_path and schema-qualified names, so a policy can
--    consult public.memberships without evaluating the memberships policies
--    again. EXECUTE: authenticated and service_role only. The parameters are
--    p_-prefixed because, in a LANGUAGE sql body, a column of the same name
--    takes precedence over an unprefixed parameter.
--    A guard aborts the migration unless the function owner is exempt from
--    RLS on public.memberships (superuser or BYPASSRLS, or the table owner
--    with FORCE ROW LEVEL SECURITY off).
--
-- 2. SELECT policies, all TO authenticated, replacing those of 007/008/009:
--      organizations        accepted member of the organization
--      memberships          accepted rows, visible to accepted co-members
--      audit_log            accepted owner or admin of the organization
--                           (the roles the audit route requires)
--      forensic_access_log  accepted owner or admin of the organization
--      projects             the project's owner (ADR-0030 §1)
--      project_shares       the owner of the shared project
--      value_milestones     the owner of the milestone's project
--      forensic_timelines   the owner, standard access level (the owner
--                           branch of 009, kept as it was)
--    Organization membership and shares grant no project access
--    (ADR-0030 §4). Policy names are new, so no earlier migration drops or
--    recreates them.
--
-- 3. Client write policies removed on tables written only by the API
--    (service_role) or the signup trigger: memberships INSERT,
--    organizations INSERT, value_milestones INSERT and UPDATE.
--
-- 4. Table privileges. INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES and
--    TRIGGER (and MAINTAIN on PostgreSQL 17+) are revoked from PUBLIC, anon
--    and authenticated on every table created by migrations 001-033. The
--    writers are the API with service_role (BYPASSRLS), SECURITY DEFINER
--    functions and triggers (run as their owner), and foreign-key cascades
--    (run as the table owner); the web client uses Supabase Auth only.
--    SELECT is unchanged, except on the organization tables, where only
--    authenticated keeps it (filtered by the policies above) and
--    program_shares keeps no client privilege. Client write policies on the
--    project tables stay defined; without the privilege they do not apply.
--
-- 5. Checks before COMMIT (any failure aborts the whole migration):
--      * no policy in schema public reads public.memberships directly;
--      * on every table whose policies read projects, organizations,
--        project_shares or the helper, each permissive SELECT/ALL policy for
--        a client role is one of the expected policies listed below;
--      * a read of each of those tables that authenticated may select from
--        is planned as authenticated without error (EXPLAIN only; no rows
--        are read).
--
-- Unchanged: handle_new_user, handle_new_user_org and notify_signup_alert
-- (SECURITY DEFINER triggers on auth.users); delete_user_data,
-- set_project_sandbox and contribute_benchmark (SECURITY DEFINER, grants
-- from 030). upsert_program is SECURITY INVOKER and is called by the API
-- with service_role.
--
-- Single transaction, with a 5 s lock_timeout so that a conflicting lock
-- makes the migration fail instead of queueing API queries behind it.
-- Idempotent: every policy is dropped by name before it is created, the
-- function is CREATE OR REPLACE, and REVOKE/GRANT converge.

BEGIN;

SET LOCAL lock_timeout = '5s';

-- ================================================================
-- 1. Accepted-membership helper
-- ================================================================

-- Another is_org_member in public (an overload, or the same types under
-- other parameter names) would make the policy calls below ambiguous or
-- block CREATE OR REPLACE.
DO $$
DECLARE
    v_other text;
BEGIN
    SELECT string_agg(
               format('public.is_org_member(%s)', pg_get_function_identity_arguments(p.oid)),
               ', ')
      INTO v_other
      FROM pg_proc AS p
      JOIN pg_namespace AS n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public'
       AND p.proname = 'is_org_member'
       AND pg_get_function_identity_arguments(p.oid) <> 'p_org_id uuid, p_roles text[]';
    IF v_other IS NOT NULL THEN
        RAISE EXCEPTION 'migration 034: unexpected function %, resolve before applying', v_other;
    END IF;
END
$$;

CREATE OR REPLACE FUNCTION public.is_org_member(p_org_id uuid, p_roles text[] DEFAULT NULL)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
          FROM public.memberships AS m
         WHERE m.org_id = p_org_id
           AND m.user_id = auth.uid()
           AND m.accepted_at IS NOT NULL
           AND (p_roles IS NULL OR m.role = ANY (p_roles))
    );
$$;

ALTER FUNCTION public.is_org_member(uuid, text[]) OWNER TO postgres;

COMMENT ON FUNCTION public.is_org_member(uuid, text[]) IS
    'True when auth.uid() holds an accepted membership (accepted_at IS NOT NULL) in p_org_id, with a role in p_roles when p_roles is not NULL. For RLS policies declared TO authenticated. Migration 034.';

REVOKE ALL ON FUNCTION public.is_org_member(uuid, text[]) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.is_org_member(uuid, text[]) TO authenticated, service_role;

-- The helper reads memberships as its owner. If RLS applied to the owner,
-- the memberships policy (which calls the helper) would recurse.
DO $$
DECLARE
    v_fn_owner  oid;
    v_tbl_owner oid;
    v_forced    boolean;
    v_exempt    boolean;
BEGIN
    SELECT p.proowner INTO v_fn_owner
      FROM pg_proc AS p
     WHERE p.oid = 'public.is_org_member(uuid, text[])'::regprocedure;
    SELECT c.relowner, c.relforcerowsecurity INTO v_tbl_owner, v_forced
      FROM pg_class AS c
     WHERE c.oid = 'public.memberships'::regclass;
    SELECT r.rolsuper OR r.rolbypassrls INTO v_exempt
      FROM pg_roles AS r
     WHERE r.oid = v_fn_owner;
    IF NOT (v_exempt OR (v_fn_owner = v_tbl_owner AND NOT v_forced)) THEN
        RAISE EXCEPTION
            'migration 034: owner % of public.is_org_member is subject to RLS on public.memberships',
            pg_get_userbyid(v_fn_owner);
    END IF;
END
$$;

-- ================================================================
-- 2. Organization tables: accepted membership
-- ================================================================

-- organizations
DROP POLICY IF EXISTS "Members can view their organizations" ON public.organizations;
DROP POLICY IF EXISTS "Anyone can create an organization" ON public.organizations;
DROP POLICY IF EXISTS organizations_select_accepted_member ON public.organizations;
CREATE POLICY organizations_select_accepted_member ON public.organizations
    FOR SELECT TO authenticated
    USING (public.is_org_member(id));

-- memberships: pending rows (accepted_at NULL) are not listed to anyone.
DROP POLICY IF EXISTS "Members can view org memberships" ON public.memberships;
DROP POLICY IF EXISTS "Admins can manage memberships" ON public.memberships;
DROP POLICY IF EXISTS memberships_select_accepted_comember ON public.memberships;
CREATE POLICY memberships_select_accepted_comember ON public.memberships
    FOR SELECT TO authenticated
    USING (accepted_at IS NOT NULL AND public.is_org_member(org_id));

-- audit_log
DROP POLICY IF EXISTS "Members can view org audit log" ON public.audit_log;
DROP POLICY IF EXISTS audit_log_select_org_manager ON public.audit_log;
CREATE POLICY audit_log_select_org_manager ON public.audit_log
    FOR SELECT TO authenticated
    USING (public.is_org_member(org_id, ARRAY['owner', 'admin']));

-- forensic_access_log
DROP POLICY IF EXISTS "Org admins can view forensic access logs" ON public.forensic_access_log;
DROP POLICY IF EXISTS forensic_access_log_select_org_manager ON public.forensic_access_log;
CREATE POLICY forensic_access_log_select_org_manager ON public.forensic_access_log
    FOR SELECT TO authenticated
    USING (public.is_org_member(org_id, ARRAY['owner', 'admin']));

-- ================================================================
-- 3. Project-scoped tables: owner only (ADR-0030)
-- ================================================================

-- projects
DROP POLICY IF EXISTS "Users can view accessible projects" ON public.projects;
DROP POLICY IF EXISTS "Users can view own projects" ON public.projects;
DROP POLICY IF EXISTS projects_select_owner ON public.projects;
CREATE POLICY projects_select_owner ON public.projects
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

-- project_shares
DROP POLICY IF EXISTS "Org members can view shares" ON public.project_shares;
DROP POLICY IF EXISTS project_shares_select_project_owner ON public.project_shares;
CREATE POLICY project_shares_select_project_owner ON public.project_shares
    FOR SELECT TO authenticated
    USING (project_id IN (SELECT p.id FROM public.projects AS p WHERE p.user_id = auth.uid()));

-- value_milestones
DROP POLICY IF EXISTS "Org members can view value milestones" ON public.value_milestones;
DROP POLICY IF EXISTS "Org admins can manage value milestones" ON public.value_milestones;
DROP POLICY IF EXISTS "Org admins can update value milestones" ON public.value_milestones;
DROP POLICY IF EXISTS value_milestones_select_project_owner ON public.value_milestones;
CREATE POLICY value_milestones_select_project_owner ON public.value_milestones
    FOR SELECT TO authenticated
    USING (project_id IN (SELECT p.id FROM public.projects AS p WHERE p.user_id = auth.uid()));

-- forensic_timelines: the owner branch of 009 as it was; the organization
-- branches are removed.
DROP POLICY IF EXISTS "Users can view accessible timelines" ON public.forensic_timelines;
DROP POLICY IF EXISTS "Users can view own timelines" ON public.forensic_timelines;
DROP POLICY IF EXISTS forensic_timelines_select_owner ON public.forensic_timelines;
CREATE POLICY forensic_timelines_select_owner ON public.forensic_timelines
    FOR SELECT TO authenticated
    USING (access_level = 'standard' AND auth.uid() = user_id);

-- ================================================================
-- 4. Table privileges: client roles read only
-- ================================================================

DO $$
DECLARE
    v_table text;
    v_privs text := 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER';
BEGIN
    IF current_setting('server_version_num')::int >= 170000 THEN
        v_privs := v_privs || ', MAINTAIN';
    END IF;
    FOREACH v_table IN ARRAY ARRAY[
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
    ] LOOP
        EXECUTE format('REVOKE %s ON TABLE public.%I FROM PUBLIC, anon, authenticated',
                       v_privs, v_table);
    END LOOP;
END
$$;

REVOKE ALL ON TABLE
    public.organizations, public.memberships, public.project_shares,
    public.program_shares, public.audit_log, public.forensic_access_log,
    public.value_milestones
FROM PUBLIC, anon, authenticated;

GRANT SELECT ON TABLE
    public.organizations, public.memberships, public.project_shares,
    public.audit_log, public.forensic_access_log, public.value_milestones
TO authenticated;

-- ================================================================
-- 5. Checks
-- ================================================================

DO $$
DECLARE
    -- Permissive SELECT policies expected on the tables whose policies read
    -- projects, organizations, project_shares or the helper.
    v_expected text[] := ARRAY[
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
    ];
    v_tables text[];
    v_table  text;
    v_bad    text;
BEGIN
    -- 5a. No policy reads public.memberships directly.
    SELECT string_agg(format('%s.%s', tablename, policyname), ', ' ORDER BY tablename, policyname)
      INTO v_bad
      FROM pg_policies
     WHERE schemaname = 'public'
       AND (coalesce(qual, '') || ' ' || coalesce(with_check, '')) ~ '\mmemberships\M';
    IF v_bad IS NOT NULL THEN
        RAISE EXCEPTION 'migration 034: policies still read public.memberships directly: %', v_bad;
    END IF;

    -- 5b. The affected tables: the expected ones, program_shares, and any
    --     table with a policy that reads projects, organizations,
    --     project_shares or the helper.
    SELECT array_agg(DISTINCT t ORDER BY t) INTO v_tables
      FROM (
            SELECT split_part(e, '.', 1) AS t FROM unnest(v_expected) AS e
            UNION SELECT 'program_shares'
            UNION
            SELECT tablename
              FROM pg_policies
             WHERE schemaname = 'public'
               AND (coalesce(qual, '') || ' ' || coalesce(with_check, ''))
                   ~ '\m(projects|organizations|project_shares|is_org_member)\M'
           ) AS s;

    SELECT string_agg(format('%s.%s', p.tablename, p.policyname), ', '
                      ORDER BY p.tablename, p.policyname)
      INTO v_bad
      FROM pg_policies AS p
     WHERE p.schemaname = 'public'
       AND p.tablename = ANY (v_tables)
       AND p.permissive = 'PERMISSIVE'
       AND p.cmd IN ('SELECT', 'ALL')
       AND p.roles && ARRAY['public', 'anon', 'authenticated']::name[]
       AND format('%s.%s', p.tablename, p.policyname) <> ALL (v_expected);
    IF v_bad IS NOT NULL THEN
        RAISE EXCEPTION 'migration 034: unexpected permissive read policies: %', v_bad;
    END IF;

    -- 5c. Plan a read of each affected table that authenticated may select
    --     from, as authenticated. Planning expands every policy on the
    --     table, so a recursive policy fails here. The sub-block always ends
    --     in an exception, which rolls back SET LOCAL ROLE with it.
    FOREACH v_table IN ARRAY v_tables LOOP
        CONTINUE WHEN NOT has_table_privilege('authenticated', format('public.%I', v_table), 'SELECT');
        BEGIN
            SET LOCAL ROLE authenticated;
            EXECUTE format('EXPLAIN SELECT 1 FROM public.%I', v_table);
            RAISE EXCEPTION USING ERRCODE = 'ZZ034';
        EXCEPTION
            WHEN SQLSTATE 'ZZ034' THEN
                NULL;
            WHEN OTHERS THEN
                RAISE EXCEPTION 'migration 034: planning a read of public.% as authenticated failed: % (SQLSTATE %)',
                    v_table, SQLERRM, SQLSTATE;
        END;
    END LOOP;
END
$$;

NOTIFY pgrst, 'reload schema';

COMMIT;
