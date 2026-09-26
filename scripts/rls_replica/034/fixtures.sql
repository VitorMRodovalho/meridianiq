-- Synthetic fixtures, loaded BEFORE migration 034 (as they would exist in a
-- live database). Run as the bootstrap superuser.
--
-- Users A-E sign up through the signup path (the auth service's role, with
-- search_path=auth), so the signup triggers create their profile and
-- personal workspace.
--   Org X: A owner, B member, E admin (accepted); C admin, pending.
--   Org Y: D owner (accepted).
--   Project PA (owner A, org X) is shared with Y and has one row in each
--   child table used below. Project PD belongs to D.

\set ON_ERROR_STOP on
\set A '''a0000000-0000-4000-8000-000000000001'''
\set B '''b0000000-0000-4000-8000-000000000002'''
\set C '''c0000000-0000-4000-8000-000000000003'''
\set D '''d0000000-0000-4000-8000-000000000004'''
\set E '''e0000000-0000-4000-8000-000000000005'''
\set X '''10000000-0000-4000-8000-0000000000a1'''
\set Y '''20000000-0000-4000-8000-0000000000a2'''
\set PA '''30000000-0000-4000-8000-0000000000b1'''
\set PD '''30000000-0000-4000-8000-0000000000b4'''
\set UA '''40000000-0000-4000-8000-0000000000c1'''
\set UD '''40000000-0000-4000-8000-0000000000c4'''

BEGIN;
SET LOCAL ROLE supabase_auth_admin;
SET LOCAL search_path = auth;
INSERT INTO users (id, email, raw_user_meta_data, raw_app_meta_data, email_confirmed_at) VALUES
    (:A, 'alice@example.test', '{"full_name": "Alice"}', '{"provider": "google"}', now()),
    (:B, 'bob@example.test',   '{"full_name": "Bob"}',   '{"provider": "google"}', now()),
    (:C, 'carol@example.test', '{"full_name": "Carol"}', '{"provider": "google"}', now()),
    (:D, 'dave@example.test',  '{"full_name": "Dave"}',  '{"provider": "google"}', now()),
    (:E, 'erin@example.test',  '{"full_name": "Erin"}',  '{"provider": "google"}', now());
COMMIT;

BEGIN;
INSERT INTO public.organizations (id, name, slug, created_by) VALUES
    (:X, 'Org X', 'org-x', :A),
    (:Y, 'Org Y', 'org-y', :D);
INSERT INTO public.memberships (org_id, user_id, role, accepted_at) VALUES
    (:X, :A, 'owner',  now()),
    (:X, :B, 'member', now()),
    (:X, :E, 'admin',  now()),
    (:X, :C, 'admin',  NULL),
    (:Y, :D, 'owner',  now());

INSERT INTO public.schedule_uploads (id, user_id, original_filename) VALUES
    (:UA, :A, 'alpha.xer'),
    (:UD, :D, 'delta.xer');
INSERT INTO public.projects (id, upload_id, user_id, org_id, project_name, storage_path) VALUES
    (:PA, :UA, :A, :X, 'Alpha', 'a0000000-0000-4000-8000-000000000001/40000000-0000-4000-8000-0000000000c1/alpha.xer'),
    (:PD, :UD, :D, :Y, 'Delta', 'd0000000-0000-4000-8000-000000000004/40000000-0000-4000-8000-0000000000c4/delta.xer');

INSERT INTO public.project_shares (project_id, shared_with_org, permission, shared_by)
    VALUES (:PA, :Y, 'viewer', :A);
INSERT INTO public.activities (project_id, task_id, task_code) VALUES (:PA, 'T1', 'A1000');
INSERT INTO public.value_milestones (project_id, org_id, task_code, created_by)
    VALUES (:PA, :X, 'A1000', :A);
INSERT INTO public.audit_log (org_id, user_id, action, entity_type)
    VALUES (:X, :A, 'invite', 'membership');
INSERT INTO public.forensic_access_log (timeline_id, user_id, org_id, action)
    VALUES ('tl-std', :A, :X, 'view');
INSERT INTO public.forensic_timelines (timeline_id, user_id, org_id, access_level) VALUES
    ('tl-std',  :A, :X, 'standard'),
    ('tl-priv', :A, :X, 'privileged');
INSERT INTO public.revision_history (project_id, revision_number, content_hash)
    VALUES (:PA, 0, repeat('a', 64));
INSERT INTO public.schedule_derived_artifacts
    (project_id, artifact_kind, payload, engine_version, ruleset_version, input_hash, effective_at)
    VALUES (:PA, 'dcma', '{}', 'e1', 'r1', repeat('b', 64), now());
COMMIT;

\pset footer off
\echo == fixture census
SELECT 'profiles', count(*) FROM public.user_profiles
UNION ALL SELECT 'organizations', count(*) FROM public.organizations
UNION ALL SELECT 'memberships (accepted)', count(*) FROM public.memberships WHERE accepted_at IS NOT NULL
UNION ALL SELECT 'memberships (pending)', count(*) FROM public.memberships WHERE accepted_at IS NULL
UNION ALL SELECT 'projects', count(*) FROM public.projects;
