-- CONTROL ARM: state after migrations 001-033, before 034.
-- It must reproduce the production measurement before anything after 034
-- is trusted: the same 11 policies read memberships, and reads of projects
-- and memberships as authenticated fail with infinite recursion (42P17).

\echo == control: policies that read memberships (expected: the 11 measured in production)
SELECT pg_temp.expect('c01 count of policies reading memberships', 'OK 11',
    'OK ' || (SELECT count(*) FROM pg_policies WHERE schemaname = 'public'
              AND (coalesce(qual, '') || ' ' || coalesce(with_check, '')) ~ '\mmemberships\M'));
SELECT pg_temp.expect('c02 names match production', 'OK true',
    'OK ' || (ARRAY(SELECT tablename || '|' || policyname
                    FROM pg_policies WHERE schemaname = 'public'
                    AND (coalesce(qual, '') || ' ' || coalesce(with_check, '')) ~ '\mmemberships\M'
                    ORDER BY 1)
              = ARRAY(SELECT unnest(ARRAY[
                'audit_log|Members can view org audit log',
                'forensic_access_log|Org admins can view forensic access logs',
                'forensic_timelines|Users can view accessible timelines',
                'memberships|Admins can manage memberships',
                'memberships|Members can view org memberships',
                'organizations|Members can view their organizations',
                'project_shares|Org members can view shares',
                'projects|Users can view accessible projects',
                'value_milestones|Org admins can manage value milestones',
                'value_milestones|Org admins can update value milestones',
                'value_milestones|Org members can view value milestones']::text[]) ORDER BY 1))::text);

\echo == control: reads as authenticated (A)
SELECT pg_temp.expect('c10 A select projects', 'ERR 42P17 infinite recursion detected in policy for relation "memberships"',
    pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.projects'));
SELECT pg_temp.expect('c11 A select memberships', 'ERR 42P17 infinite recursion detected in policy for relation "memberships"',
    pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.memberships'));
SELECT pg_temp.expect('c12 A select organizations', 'ERR 42P17 %',
    pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.organizations'));
SELECT pg_temp.expect('c13 A select activities (child of projects)', 'ERR 42P17 %',
    pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.activities'));
SELECT pg_temp.expect('c14 A select value_milestones', 'ERR 42P17 %',
    pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.value_milestones'));

\echo == control: client write paths before 034 (baseline for what 034 changes)
SELECT pg_temp.info('c20 A delete own revision_history (DELETE ... RETURNING)',
    pg_temp.run_as('authenticated', :A, format(
        'WITH d AS (DELETE FROM public.revision_history WHERE project_id = %L RETURNING 1) SELECT count(*)::text FROM d', :PA)));
SELECT pg_temp.info('c21 A insert lifecycle_override_log',
    pg_temp.run_as('authenticated', :A, format(
        $q$WITH i AS (INSERT INTO public.lifecycle_override_log (project_id, override_phase, override_reason, overridden_by, engine_version, ruleset_version)
            VALUES (%L, 'closeout', 'x', %L, 'e', 'r') RETURNING 1) SELECT count(*)::text FROM i$q$, :PA, :D)));
SELECT pg_temp.info('c22 A insert schedule_derived_artifacts',
    pg_temp.run_as('authenticated', :A, format(
        $q$WITH i AS (INSERT INTO public.schedule_derived_artifacts (project_id, artifact_kind, payload, engine_version, ruleset_version, input_hash, effective_at)
            VALUES (%L, 'health', '{}', 'e', 'r', repeat('c', 64), now()) RETURNING 1) SELECT count(*)::text FROM i$q$, :PA)));
SELECT pg_temp.info('c23 A insert projects row, no RETURNING',
    pg_temp.run_as('authenticated', :A, format(
        $q$INSERT INTO public.projects (user_id, storage_path, status) VALUES (%L, 'a0000000-0000-4000-8000-000000000001/new/new.xer', 'ready')$q$, :A)));
SELECT pg_temp.info('c24 A insert projects, RETURNING 1 (no column read)',
    pg_temp.run_as('authenticated', :A, format(
        $q$WITH i AS (INSERT INTO public.projects (user_id) VALUES (%L) RETURNING 1) SELECT count(*)::text FROM i$q$, :A)));
SELECT pg_temp.info('c24b A insert projects, RETURNING id (column read)',
    pg_temp.run_as('authenticated', :A, format(
        $q$WITH i AS (INSERT INTO public.projects (user_id) VALUES (%L) RETURNING id) SELECT count(*)::text FROM i$q$, :A)));
SELECT pg_temp.info('c25 anon insert alerts',
    pg_temp.run_as('anon', NULL,
        $q$INSERT INTO public.alerts (rule_id, severity, title) VALUES ('r', 'info', 't')$q$));
SELECT pg_temp.info('c26 A insert memberships into org X',
    pg_temp.run_as('authenticated', :A, format(
        $q$INSERT INTO public.memberships (org_id, user_id, role, accepted_at) VALUES (%L, %L, 'admin', now())$q$, :X, :D)));
SELECT pg_temp.info('c27 A insert schedule_uploads, no RETURNING',
    pg_temp.run_as('authenticated', :A, format(
        $q$INSERT INTO public.schedule_uploads (user_id, original_filename) VALUES (%L, 'x.xer')$q$, :A)));
SELECT pg_temp.info('c28 A insert organizations, no RETURNING',
    pg_temp.run_as('authenticated', :A, format(
        $q$INSERT INTO public.organizations (name, slug, created_by) VALUES ('n', 'taken-slug', %L)$q$, :A)));
SELECT pg_temp.info('c29 A delete own project (DELETE ... WHERE)',
    pg_temp.run_as('authenticated', :A, format(
        'WITH d AS (DELETE FROM public.projects WHERE id = %L RETURNING 1) SELECT count(*)::text FROM d', :PA)));
