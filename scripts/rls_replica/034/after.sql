-- AFTER 034. Every probe runs as the consumer's role (authenticated, anon or
-- service_role) with the claims PostgREST would set, and is rolled back.

\echo == structure
SELECT pg_temp.expect('s01 policies reading memberships directly', 'OK 0',
    'OK ' || (SELECT count(*) FROM pg_policies WHERE schemaname = 'public'
              AND (coalesce(qual, '') || ' ' || coalesce(with_check, '')) ~ '\mmemberships\M'));
SELECT pg_temp.expect('s02 helper definer / stable / search_path empty / owner', 'OK true|s|true|postgres',
    'OK ' || (SELECT prosecdef::text || '|' || provolatile::text || '|' || (proconfig = ARRAY['search_path=""'])::text || '|' || pg_get_userbyid(proowner)
              FROM pg_proc WHERE oid = 'public.is_org_member(uuid, text[])'::regprocedure));
SELECT pg_temp.expect('s03 helper EXECUTE anon/authenticated/service_role', 'OK f/t/t',
    'OK ' || has_function_privilege('anon', 'public.is_org_member(uuid, text[])', 'EXECUTE')::text::char(1)
    || '/' || has_function_privilege('authenticated', 'public.is_org_member(uuid, text[])', 'EXECUTE')::text::char(1)
    || '/' || has_function_privilege('service_role', 'public.is_org_member(uuid, text[])', 'EXECUTE')::text::char(1));
SELECT pg_temp.expect('s04 tables where anon or authenticated may INSERT/UPDATE/DELETE/TRUNCATE', 'OK 0 of 56',
    'OK ' || (SELECT count(*) FROM pg_class c CROSS JOIN (VALUES ('anon'), ('authenticated')) AS r(role)
              WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
                AND has_table_privilege(r.role, c.oid, 'INSERT, UPDATE, DELETE, TRUNCATE'))
    || ' of ' || (SELECT count(*) FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'));
SELECT pg_temp.expect('s05 tables where service_role keeps SELECT+INSERT+UPDATE+DELETE', 'OK 56',
    'OK ' || (SELECT count(*) FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
              AND has_table_privilege('service_role', c.oid, 'SELECT')
              AND has_table_privilege('service_role', c.oid, 'INSERT')
              AND has_table_privilege('service_role', c.oid, 'UPDATE')
              AND has_table_privilege('service_role', c.oid, 'DELETE')));
SELECT pg_temp.expect('s06 org tables readable by anon', 'OK 0',
    'OK ' || (SELECT count(*) FROM unnest(ARRAY['organizations','memberships','project_shares','program_shares','audit_log','forensic_access_log','value_milestones']) t
              WHERE has_table_privilege('anon', format('public.%I', t), 'SELECT')));
SELECT pg_temp.expect('s07 org tables readable by authenticated (program_shares excluded)', 'OK 6',
    'OK ' || (SELECT count(*) FROM unnest(ARRAY['organizations','memberships','project_shares','program_shares','audit_log','forensic_access_log','value_milestones']) t
              WHERE has_table_privilege('authenticated', format('public.%I', t), 'SELECT')));
SELECT pg_temp.expect('s08 other tables keep SELECT for anon', 'OK 49',
    'OK ' || (SELECT count(*) FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
              AND c.relname NOT IN ('organizations','memberships','project_shares','program_shares','audit_log','forensic_access_log','value_milestones')
              AND has_table_privilege('anon', c.oid, 'SELECT')));

\echo == reads as authenticated: organizations
SELECT pg_temp.expect('r01 A organizations', 'OK Alice''s Workspace,Org X',
    pg_temp.run_as('authenticated', :A, 'SELECT string_agg(name, '','' ORDER BY name) FROM public.organizations'));
SELECT pg_temp.expect('r02 B organizations', 'OK Bob''s Workspace,Org X',
    pg_temp.run_as('authenticated', :B, 'SELECT string_agg(name, '','' ORDER BY name) FROM public.organizations'));
SELECT pg_temp.expect('r03 C (pending in X) organizations', 'OK Carol''s Workspace',
    pg_temp.run_as('authenticated', :C, 'SELECT string_agg(name, '','' ORDER BY name) FROM public.organizations'));
SELECT pg_temp.expect('r04 D organizations', 'OK Dave''s Workspace,Org Y',
    pg_temp.run_as('authenticated', :D, 'SELECT string_agg(name, '','' ORDER BY name) FROM public.organizations'));
SELECT pg_temp.expect('r05 E organizations', 'OK Erin''s Workspace,Org X',
    pg_temp.run_as('authenticated', :E, 'SELECT string_agg(name, '','' ORDER BY name) FROM public.organizations'));

\echo == reads as authenticated: memberships of org X
SELECT pg_temp.expect('r10 A sees X members (pending row hidden)', 'OK admin,member,owner',
    pg_temp.run_as('authenticated', :A, format('SELECT string_agg(role, '','' ORDER BY role) FROM public.memberships WHERE org_id = %L', :X)));
SELECT pg_temp.expect('r11 B sees X members', 'OK admin,member,owner',
    pg_temp.run_as('authenticated', :B, format('SELECT string_agg(role, '','' ORDER BY role) FROM public.memberships WHERE org_id = %L', :X)));
SELECT pg_temp.expect('r12 E sees X members', 'OK admin,member,owner',
    pg_temp.run_as('authenticated', :E, format('SELECT string_agg(role, '','' ORDER BY role) FROM public.memberships WHERE org_id = %L', :X)));
SELECT pg_temp.expect('r13 C (pending) sees nothing of X', 'OK 0',
    pg_temp.run_as('authenticated', :C, format('SELECT count(*)::text FROM public.memberships WHERE org_id = %L', :X)));
SELECT pg_temp.expect('r14 C sees only own workspace row', 'OK 1',
    pg_temp.run_as('authenticated', :C, 'SELECT count(*)::text FROM public.memberships'));
SELECT pg_temp.expect('r15 D sees nothing of X', 'OK 0',
    pg_temp.run_as('authenticated', :D, format('SELECT count(*)::text FROM public.memberships WHERE org_id = %L', :X)));
SELECT pg_temp.expect('r16 no jwt subject sees no memberships', 'OK 0',
    pg_temp.run_as('authenticated', NULL, 'SELECT count(*)::text FROM public.memberships'));

\echo == reads as authenticated: audit and forensic logs (owner/admin of X)
SELECT pg_temp.expect('r20 A audit_log', 'OK 1', pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.audit_log'));
SELECT pg_temp.expect('r21 E audit_log', 'OK 1', pg_temp.run_as('authenticated', :E, 'SELECT count(*)::text FROM public.audit_log'));
SELECT pg_temp.expect('r22 B (member) audit_log', 'OK 0', pg_temp.run_as('authenticated', :B, 'SELECT count(*)::text FROM public.audit_log'));
SELECT pg_temp.expect('r23 C (pending admin) audit_log', 'OK 0', pg_temp.run_as('authenticated', :C, 'SELECT count(*)::text FROM public.audit_log'));
SELECT pg_temp.expect('r24 D audit_log', 'OK 0', pg_temp.run_as('authenticated', :D, 'SELECT count(*)::text FROM public.audit_log'));
SELECT pg_temp.expect('r25 A forensic_access_log', 'OK 1', pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.forensic_access_log'));
SELECT pg_temp.expect('r26 E forensic_access_log', 'OK 1', pg_temp.run_as('authenticated', :E, 'SELECT count(*)::text FROM public.forensic_access_log'));
SELECT pg_temp.expect('r27 B forensic_access_log', 'OK 0', pg_temp.run_as('authenticated', :B, 'SELECT count(*)::text FROM public.forensic_access_log'));
SELECT pg_temp.expect('r28 C (pending admin) forensic_access_log', 'OK 0', pg_temp.run_as('authenticated', :C, 'SELECT count(*)::text FROM public.forensic_access_log'));

\echo == reads as authenticated: project-scoped tables (owner only)
SELECT pg_temp.expect('r30 A projects', 'OK Alpha', pg_temp.run_as('authenticated', :A, 'SELECT string_agg(project_name, '','') FROM public.projects'));
SELECT pg_temp.expect('r31 D projects (PA is shared with Y; share grants nothing)', 'OK Delta', pg_temp.run_as('authenticated', :D, 'SELECT string_agg(project_name, '','') FROM public.projects'));
SELECT pg_temp.expect('r32 B projects (member of PA''s org)', 'OK 0', pg_temp.run_as('authenticated', :B, 'SELECT count(*)::text FROM public.projects'));
SELECT pg_temp.expect('r33 E projects (admin of PA''s org)', 'OK 0', pg_temp.run_as('authenticated', :E, 'SELECT count(*)::text FROM public.projects'));
SELECT pg_temp.expect('r34 A activities', 'OK 1', pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.activities'));
SELECT pg_temp.expect('r35 B activities', 'OK 0', pg_temp.run_as('authenticated', :B, 'SELECT count(*)::text FROM public.activities'));
SELECT pg_temp.expect('r36 D activities', 'OK 0', pg_temp.run_as('authenticated', :D, 'SELECT count(*)::text FROM public.activities'));
SELECT pg_temp.expect('r37 A project_shares', 'OK 1', pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.project_shares'));
SELECT pg_temp.expect('r38 D project_shares (target org)', 'OK 0', pg_temp.run_as('authenticated', :D, 'SELECT count(*)::text FROM public.project_shares'));
SELECT pg_temp.expect('r39 B project_shares', 'OK 0', pg_temp.run_as('authenticated', :B, 'SELECT count(*)::text FROM public.project_shares'));
SELECT pg_temp.expect('r40 A value_milestones', 'OK 1', pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.value_milestones'));
SELECT pg_temp.expect('r41 B value_milestones (member of milestone org)', 'OK 0', pg_temp.run_as('authenticated', :B, 'SELECT count(*)::text FROM public.value_milestones'));
SELECT pg_temp.expect('r42 E value_milestones (admin of milestone org)', 'OK 0', pg_temp.run_as('authenticated', :E, 'SELECT count(*)::text FROM public.value_milestones'));
SELECT pg_temp.expect('r43 A forensic_timelines (standard only)', 'OK tl-std', pg_temp.run_as('authenticated', :A, 'SELECT string_agg(timeline_id, '','') FROM public.forensic_timelines'));
SELECT pg_temp.expect('r44 E forensic_timelines (org admin)', 'OK 0', pg_temp.run_as('authenticated', :E, 'SELECT count(*)::text FROM public.forensic_timelines'));
SELECT pg_temp.expect('r45 A revision_history', 'OK 1', pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.revision_history'));
SELECT pg_temp.expect('r46 D revision_history', 'OK 0', pg_temp.run_as('authenticated', :D, 'SELECT count(*)::text FROM public.revision_history'));

\echo == helper answers (org X, org X as owner/admin)
SELECT pg_temp.expect('h01 A', 'OK t/t', pg_temp.run_as('authenticated', :A, format($q$SELECT public.is_org_member(%L)::text::char(1) || '/' || public.is_org_member(%L, ARRAY['owner','admin'])::text::char(1)$q$, :X, :X)));
SELECT pg_temp.expect('h02 B', 'OK t/f', pg_temp.run_as('authenticated', :B, format($q$SELECT public.is_org_member(%L)::text::char(1) || '/' || public.is_org_member(%L, ARRAY['owner','admin'])::text::char(1)$q$, :X, :X)));
SELECT pg_temp.expect('h03 C (pending admin)', 'OK f/f', pg_temp.run_as('authenticated', :C, format($q$SELECT public.is_org_member(%L)::text::char(1) || '/' || public.is_org_member(%L, ARRAY['owner','admin'])::text::char(1)$q$, :X, :X)));
SELECT pg_temp.expect('h04 D', 'OK f/f', pg_temp.run_as('authenticated', :D, format($q$SELECT public.is_org_member(%L)::text::char(1) || '/' || public.is_org_member(%L, ARRAY['owner','admin'])::text::char(1)$q$, :X, :X)));
SELECT pg_temp.expect('h05 E', 'OK t/t', pg_temp.run_as('authenticated', :E, format($q$SELECT public.is_org_member(%L)::text::char(1) || '/' || public.is_org_member(%L, ARRAY['owner','admin'])::text::char(1)$q$, :X, :X)));
SELECT pg_temp.expect('h06 A with NULL org', 'OK false', pg_temp.run_as('authenticated', :A, 'SELECT public.is_org_member(NULL)::text'));
SELECT pg_temp.expect('h07 no jwt subject', 'OK false', pg_temp.run_as('authenticated', NULL, format('SELECT public.is_org_member(%L)::text', :X)));

\echo == mutation control: a helper whose parameter is named like a column
SELECT pg_temp.expect('m01 shadowed helper answers true for outsider D on X', 'OK true',
    pg_temp.run_as('authenticated', :D, format('SELECT public.is_org_member_shadowed(%L)::text', :X),
        $s$CREATE FUNCTION public.is_org_member_shadowed(org_id uuid, roles text[] DEFAULT NULL)
           RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $b$
               SELECT EXISTS (SELECT 1 FROM public.memberships AS m
                              WHERE m.org_id = org_id AND m.user_id = auth.uid()
                                AND m.accepted_at IS NOT NULL
                                AND (roles IS NULL OR m.role = ANY (roles))) $b$;
           GRANT EXECUTE ON FUNCTION public.is_org_member_shadowed(uuid, text[]) TO authenticated$s$));
SELECT pg_temp.expect('m02 shadowed helper answers true for a random org id', 'OK true',
    pg_temp.run_as('authenticated', :D, 'SELECT public.is_org_member_shadowed(gen_random_uuid())::text',
        $s$CREATE FUNCTION public.is_org_member_shadowed(org_id uuid, roles text[] DEFAULT NULL)
           RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $b$
               SELECT EXISTS (SELECT 1 FROM public.memberships AS m
                              WHERE m.org_id = org_id AND m.user_id = auth.uid()
                                AND m.accepted_at IS NOT NULL
                                AND (roles IS NULL OR m.role = ANY (roles))) $b$;
           GRANT EXECUTE ON FUNCTION public.is_org_member_shadowed(uuid, text[]) TO authenticated$s$));
SELECT pg_temp.expect('m03 real helper for outsider D on X', 'OK false',
    pg_temp.run_as('authenticated', :D, format('SELECT public.is_org_member(%L)::text', :X)));
SELECT pg_temp.expect('m04 real helper for a random org id', 'OK false',
    pg_temp.run_as('authenticated', :A, 'SELECT public.is_org_member(gen_random_uuid())::text'));

\echo == writes as authenticated (the grant layer answers first)
SELECT pg_temp.expect('w01 A insert memberships into X', 'ERR 42501 permission denied for table memberships',
    pg_temp.run_as('authenticated', :A, format($q$INSERT INTO public.memberships (org_id, user_id, role, accepted_at) VALUES (%L, %L, 'admin', now())$q$, :X, :D)));
SELECT pg_temp.expect('w02 C self-accept pending membership', 'ERR 42501 permission denied for table memberships',
    pg_temp.run_as('authenticated', :C, format('UPDATE public.memberships SET accepted_at = now() WHERE org_id = %L AND user_id = %L', :X, :C)));
SELECT pg_temp.expect('w03 A insert organizations', 'ERR 42501 permission denied for table organizations',
    pg_temp.run_as('authenticated', :A, format($q$INSERT INTO public.organizations (name, slug, created_by) VALUES ('n', 'new-slug', %L)$q$, :A)));
SELECT pg_temp.expect('w04 A insert value_milestones', 'ERR 42501 permission denied for table value_milestones',
    pg_temp.run_as('authenticated', :A, format($q$INSERT INTO public.value_milestones (project_id, org_id, task_code) VALUES (%L, %L, 'A1')$q$, :PA, :X)));
SELECT pg_temp.expect('w05 A update value_milestones', 'ERR 42501 permission denied for table value_milestones',
    pg_temp.run_as('authenticated', :A, $q$UPDATE public.value_milestones SET notes = 'x'$q$));
SELECT pg_temp.expect('w06 A insert project_shares', 'ERR 42501 permission denied for table project_shares',
    pg_temp.run_as('authenticated', :A, format($q$INSERT INTO public.project_shares (project_id, shared_with_org) VALUES (%L, %L)$q$, :PA, :X)));
SELECT pg_temp.expect('w07 A insert audit_log', 'ERR 42501 permission denied for table audit_log',
    pg_temp.run_as('authenticated', :A, format($q$INSERT INTO public.audit_log (org_id, action, entity_type) VALUES (%L, 'x', 'y')$q$, :X)));

\echo == writes as authenticated: the control-arm write paths, after 034
SELECT pg_temp.expect('w20 A delete own revision_history', 'ERR 42501 permission denied for table revision_history',
    pg_temp.run_as('authenticated', :A, format(
        'WITH d AS (DELETE FROM public.revision_history WHERE project_id = %L RETURNING 1) SELECT count(*)::text FROM d', :PA)));
SELECT pg_temp.expect('w21 A insert lifecycle_override_log', 'ERR 42501 permission denied for table lifecycle_override_log',
    pg_temp.run_as('authenticated', :A, format(
        $q$WITH i AS (INSERT INTO public.lifecycle_override_log (project_id, override_phase, override_reason, overridden_by, engine_version, ruleset_version)
            VALUES (%L, 'closeout', 'x', %L, 'e', 'r') RETURNING 1) SELECT count(*)::text FROM i$q$, :PA, :D)));
SELECT pg_temp.expect('w22 A insert schedule_derived_artifacts', 'ERR 42501 permission denied for table schedule_derived_artifacts',
    pg_temp.run_as('authenticated', :A, format(
        $q$WITH i AS (INSERT INTO public.schedule_derived_artifacts (project_id, artifact_kind, payload, engine_version, ruleset_version, input_hash, effective_at)
            VALUES (%L, 'health', '{}', 'e', 'r', repeat('c', 64), now()) RETURNING 1) SELECT count(*)::text FROM i$q$, :PA)));
SELECT pg_temp.expect('w23 A insert projects row, no RETURNING', 'ERR 42501 permission denied for table projects',
    pg_temp.run_as('authenticated', :A, format(
        $q$INSERT INTO public.projects (user_id, storage_path, status) VALUES (%L, 'a0000000-0000-4000-8000-000000000001/new/new.xer', 'ready')$q$, :A)));
SELECT pg_temp.expect('w24 A insert projects, RETURNING 1', 'ERR 42501 permission denied for table projects',
    pg_temp.run_as('authenticated', :A, format(
        $q$WITH i AS (INSERT INTO public.projects (user_id) VALUES (%L) RETURNING 1) SELECT count(*)::text FROM i$q$, :A)));
SELECT pg_temp.expect('w25 anon insert alerts', 'ERR 42501 permission denied for table alerts',
    pg_temp.run_as('anon', NULL, $q$INSERT INTO public.alerts (rule_id, severity, title) VALUES ('r', 'info', 't')$q$));
SELECT pg_temp.expect('w26 A insert schedule_uploads', 'ERR 42501 permission denied for table schedule_uploads',
    pg_temp.run_as('authenticated', :A, format($q$INSERT INTO public.schedule_uploads (user_id, original_filename) VALUES (%L, 'x.xer')$q$, :A)));
SELECT pg_temp.expect('w27 A delete own project', 'ERR 42501 permission denied for table projects',
    pg_temp.run_as('authenticated', :A, format(
        'WITH d AS (DELETE FROM public.projects WHERE id = %L RETURNING 1) SELECT count(*)::text FROM d', :PA)));
SELECT pg_temp.expect('w28 A truncate activities', 'ERR 42501 permission denied for table activities',
    pg_temp.run_as('authenticated', :A, 'TRUNCATE public.activities'));
SELECT pg_temp.expect('w29 A insert benchmark_projects directly', 'ERR 42501 permission denied for table benchmark_projects',
    pg_temp.run_as('authenticated', :A, $q$INSERT INTO public.benchmark_projects (size_category) VALUES ('small')$q$));
SELECT pg_temp.expect('w30 A insert api_keys directly', 'ERR 42501 permission denied for table api_keys',
    pg_temp.run_as('authenticated', :A, format($q$INSERT INTO public.api_keys (key_id, key_hash, user_id, name) VALUES ('k', 'h', %L, 'n')$q$, :A)));

\echo == layer attribution: privileges granted back inside the probe, so only the policies answer
SELECT pg_temp.expect('l01 memberships insert, policy layer only', 'ERR 42501 new row violates row-level security policy for table "memberships"',
    pg_temp.run_as('authenticated', :A, format($q$INSERT INTO public.memberships (org_id, user_id, role, accepted_at) VALUES (%L, %L, 'admin', now())$q$, :X, :D),
        'GRANT INSERT, UPDATE ON public.memberships TO authenticated'));
SELECT pg_temp.expect('l02 C self-accept, policy layer only', 'OK rows=0',
    pg_temp.run_as('authenticated', :C, format('UPDATE public.memberships SET accepted_at = now() WHERE org_id = %L AND user_id = %L', :X, :C),
        'GRANT INSERT, UPDATE ON public.memberships TO authenticated'));
SELECT pg_temp.expect('l03 value_milestones insert, policy layer only', 'ERR 42501 new row violates row-level security policy for table "value_milestones"',
    pg_temp.run_as('authenticated', :A, format($q$INSERT INTO public.value_milestones (project_id, org_id, task_code) VALUES (%L, %L, 'A1')$q$, :PA, :X),
        'GRANT INSERT, UPDATE ON public.value_milestones TO authenticated'));
SELECT pg_temp.expect('l04 value_milestones update, policy layer only', 'OK rows=0',
    pg_temp.run_as('authenticated', :A, $q$UPDATE public.value_milestones SET notes = 'x'$q$,
        'GRANT INSERT, UPDATE ON public.value_milestones TO authenticated'));
SELECT pg_temp.expect('l05 organizations insert, policy layer only', 'ERR 42501 new row violates row-level security policy for table "organizations"',
    pg_temp.run_as('authenticated', :A, format($q$INSERT INTO public.organizations (name, slug, created_by) VALUES ('n', 'new-slug', %L)$q$, :A),
        'GRANT INSERT ON public.organizations TO authenticated'));
SELECT pg_temp.info('l06 revision_history owner delete, policy layer only (028 policy allows it; the privilege is what blocks it)',
    pg_temp.run_as('authenticated', :A, format(
        'WITH d AS (DELETE FROM public.revision_history WHERE project_id = %L RETURNING 1) SELECT count(*)::text FROM d', :PA),
        'GRANT DELETE ON public.revision_history TO authenticated'));

\echo == anon
SELECT pg_temp.expect('a01 anon select organizations', 'ERR 42501 permission denied for table organizations',
    pg_temp.run_as('anon', NULL, 'SELECT count(*)::text FROM public.organizations'));
SELECT pg_temp.expect('a02 anon select memberships', 'ERR 42501 permission denied for table memberships',
    pg_temp.run_as('anon', NULL, 'SELECT count(*)::text FROM public.memberships'));
SELECT pg_temp.expect('a03 anon select projects', 'OK 0',
    pg_temp.run_as('anon', NULL, 'SELECT count(*)::text FROM public.projects'));
SELECT pg_temp.expect('a04 anon call is_org_member', 'ERR 42501 permission denied for function is_org_member',
    pg_temp.run_as('anon', NULL, format('SELECT public.is_org_member(%L)::text', :X)));

\echo == RPCs for their callers
SELECT pg_temp.expect('p01 set_project_sandbox, owner A', 'OK {"project_id" : "30000000-0000-4000-8000-0000000000b1", "is_sandbox" : true}',
    pg_temp.run_as('authenticated', :A, format('SELECT public.set_project_sandbox(%L, true)::text', :PA)));
SELECT pg_temp.expect('p02 set_project_sandbox, non-owner B', 'ERR P0001 Project not found or not owned by user',
    pg_temp.run_as('authenticated', :B, format('SELECT public.set_project_sandbox(%L, true)::text', :PA)));
SELECT pg_temp.expect('p03 set_project_sandbox, service_role', 'OK {"project_id" : "30000000-0000-4000-8000-0000000000b1", "is_sandbox" : true}',
    pg_temp.run_as('service_role', NULL, format('SELECT public.set_project_sandbox(%L, true)::text', :PA)));
SELECT pg_temp.expect('p04 set_project_sandbox, anon', 'ERR 42501 permission denied for function set_project_sandbox',
    pg_temp.run_as('anon', NULL, format('SELECT public.set_project_sandbox(%L, true)::text', :PA)));
SELECT pg_temp.expect('p05 contribute_benchmark, authenticated A (row attributed to A)', 'OK ________-____-____-____-____________ | after: 1',
    pg_temp.run_as('authenticated', :A,
        'SELECT public.contribute_benchmark(''small'', 10, 9, 2, 1, 30, 90, 95, 1, 5, 0, 2, 90, 0, 1, 1, 1, 5, 4, 3, 1.1, 8, 20, 10, 40, 50)::text',
        NULL,
        format('SELECT count(*)::text FROM public.benchmark_projects WHERE contributed_by = %L', :A)));
SELECT pg_temp.expect('p06 contribute_benchmark, anon', 'ERR 42501 permission denied for function contribute_benchmark',
    pg_temp.run_as('anon', NULL,
        'SELECT public.contribute_benchmark(''small'', 10, 9, 2, 1, 30, 90, 95, 1, 5, 0, 2, 90, 0, 1, 1, 1, 5, 4, 3, 1.1, 8, 20, 10, 40, 50)::text'));
SELECT pg_temp.expect('p07 delete_user_data(A) as B', 'ERR P0001 Unauthorized: can only delete own data',
    pg_temp.run_as('authenticated', :B, format('SELECT public.delete_user_data(%L)::text', :A)));
SELECT pg_temp.expect('p08 delete_user_data(A) as A; cascade reaches org-model children',
    'OK {"deleted_uploads" : 1, "deleted_projects" : 1, "deleted_analyses" : 0, "deleted_benchmarks" : 0, "status" : "complete"} | after: 0/0/0/0/0',
    pg_temp.run_as('authenticated', :A, format('SELECT public.delete_user_data(%L)::text', :A), NULL,
        format($q$SELECT (SELECT count(*) FROM public.projects WHERE user_id = %1$L) || '/' ||
                         (SELECT count(*) FROM public.value_milestones WHERE project_id = %2$L) || '/' ||
                         (SELECT count(*) FROM public.project_shares WHERE project_id = %2$L) || '/' ||
                         (SELECT count(*) FROM public.activities WHERE project_id = %2$L) || '/' ||
                         (SELECT count(*) FROM public.user_profiles WHERE id = %1$L)$q$, :A, :PA)));
SELECT pg_temp.expect('p09 delete_user_data(A) as service_role', 'OK {"deleted_uploads" : 1, "deleted_projects" : 1, %"status" : "complete"}',
    pg_temp.run_as('service_role', NULL, format('SELECT public.delete_user_data(%L)::text', :A)));
SELECT pg_temp.expect('p10 delete_user_data, anon', 'ERR 42501 permission denied for function delete_user_data',
    pg_temp.run_as('anon', NULL, format('SELECT public.delete_user_data(%L)::text', :A)));
SELECT pg_temp.expect('p11 upsert_program, service_role (the API caller)', 'OK ________-____-____-____-____________',
    pg_temp.run_as('service_role', NULL, format($q$SELECT public.upsert_program(%L, 'Alpha')::text$q$, :A)));
SELECT pg_temp.info('p12 upsert_program, authenticated A (SECURITY INVOKER; no caller uses this path)',
    pg_temp.run_as('authenticated', :A, format($q$SELECT public.upsert_program(%L, 'Alpha')::text$q$, :A)));

\echo == service_role: the API write paths
SELECT pg_temp.expect('sr01 insert pending membership', 'OK rows=1',
    pg_temp.run_as('service_role', NULL, format($q$INSERT INTO public.memberships (org_id, user_id, role, invited_by) VALUES (%L, %L, 'member', %L)$q$, :X, :D, :A)));
SELECT pg_temp.expect('sr02 accept pending membership', 'OK rows=1',
    pg_temp.run_as('service_role', NULL, format('UPDATE public.memberships SET accepted_at = now() WHERE org_id = %L AND user_id = %L AND accepted_at IS NULL', :X, :C)));
SELECT pg_temp.expect('sr03 insert value_milestones', 'OK rows=1',
    pg_temp.run_as('service_role', NULL, format($q$INSERT INTO public.value_milestones (project_id, org_id, task_code) VALUES (%L, %L, 'A2')$q$, :PA, :X)));
SELECT pg_temp.expect('sr04 insert organizations', 'OK rows=1',
    pg_temp.run_as('service_role', NULL, format($q$INSERT INTO public.organizations (name, slug, created_by) VALUES ('Org Z', 'org-z', %L)$q$, :A)));
SELECT pg_temp.expect('sr05 insert audit_log', 'OK rows=1',
    pg_temp.run_as('service_role', NULL, format($q$INSERT INTO public.audit_log (org_id, user_id, action, entity_type) VALUES (%L, %L, 'share', 'project')$q$, :X, :A)));
SELECT pg_temp.expect('sr06 upsert project_shares ON CONFLICT', 'OK rows=1',
    pg_temp.run_as('service_role', NULL, format($q$INSERT INTO public.project_shares (project_id, shared_with_org, permission, shared_by) VALUES (%L, %L, 'editor', %L)
        ON CONFLICT (project_id, shared_with_org) DO UPDATE SET permission = EXCLUDED.permission$q$, :PA, :Y, :A)));
SELECT pg_temp.expect('sr07 C sees org X once the API accepts the invitation', 'OK 1',
    pg_temp.run_as('authenticated', :C, format('SELECT count(*)::text FROM public.organizations WHERE id = %L', :X),
        format('UPDATE public.memberships SET accepted_at = now() WHERE org_id = %L AND user_id = %L', :X, :C)));
SELECT pg_temp.expect('sr08 D does not see org X while the invitation is pending', 'OK 0',
    pg_temp.run_as('authenticated', :D, format('SELECT count(*)::text FROM public.organizations WHERE id = %L', :X),
        format($q$INSERT INTO public.memberships (org_id, user_id, role) VALUES (%L, %L, 'member')$q$, :X, :D)));
SELECT pg_temp.expect('sr09 service_role deletes PA; cascades run as table owner', 'OK rows=1 | after: 0/0/0/0',
    pg_temp.run_as('service_role', NULL, format('DELETE FROM public.projects WHERE id = %L', :PA), NULL,
        format($q$SELECT (SELECT count(*) FROM public.value_milestones WHERE project_id = %1$L) || '/' ||
                         (SELECT count(*) FROM public.project_shares WHERE project_id = %1$L) || '/' ||
                         (SELECT count(*) FROM public.activities WHERE project_id = %1$L) || '/' ||
                         (SELECT count(*) FROM public.revision_history WHERE project_id = %1$L)$q$, :PA)));

\echo == premise of the owner guard in 034: an owner subject to RLS makes the helper recurse
SELECT pg_temp.expect('g01 helper owner without BYPASSRLS, FORCE RLS on memberships: A reads memberships', 'ERR %',
    pg_temp.run_as('authenticated', :A, 'SELECT count(*)::text FROM public.memberships',
        'ALTER ROLE postgres NOBYPASSRLS; ALTER TABLE public.memberships FORCE ROW LEVEL SECURITY'));
SELECT pg_temp.expect('g02 helper owner without BYPASSRLS, FORCE off (table owner exempt): A reads X members', 'OK admin,member,owner',
    pg_temp.run_as('authenticated', :A, format('SELECT string_agg(role, '','' ORDER BY role) FROM public.memberships WHERE org_id = %L', :X),
        'ALTER ROLE postgres NOBYPASSRLS'));
