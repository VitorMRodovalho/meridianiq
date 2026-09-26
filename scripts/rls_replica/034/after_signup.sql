\echo == signup after 034 (user F)
SELECT pg_temp.expect('u01 signup triggers on auth.users', 'OK notify_signup_alert,on_auth_user_created,on_auth_user_created_org',
    'OK ' || (SELECT string_agg(tgname, ',' ORDER BY tgname) FROM pg_trigger
              WHERE tgrelid = 'auth.users'::regclass AND NOT tgisinternal));
SELECT pg_temp.expect('u02 F profile, personal org, accepted owner membership', 'OK 1/1/1',
    'OK ' || (SELECT count(*) FROM public.user_profiles WHERE id = :F) || '/'
          || (SELECT count(*) FROM public.organizations WHERE created_by = :F) || '/'
          || (SELECT count(*) FROM public.memberships WHERE user_id = :F AND role = 'owner' AND accepted_at IS NOT NULL));
SELECT pg_temp.expect('u03 F sees own workspace through RLS', 'OK Frank''s Workspace',
    pg_temp.run_as('authenticated', :F, 'SELECT string_agg(name, '','') FROM public.organizations'));
SELECT pg_temp.expect('u04 F sees own membership through RLS', 'OK owner',
    pg_temp.run_as('authenticated', :F, 'SELECT string_agg(role, '','') FROM public.memberships'));
SELECT pg_temp.expect('u05 F sees own profile', 'OK 1',
    pg_temp.run_as('authenticated', :F, 'SELECT count(*)::text FROM public.user_profiles'));
