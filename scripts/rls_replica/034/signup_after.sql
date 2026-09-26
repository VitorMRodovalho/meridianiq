-- A signup AFTER 034, through the auth service's role and search_path, as
-- the auth service performs it. Run as the bootstrap superuser.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL ROLE supabase_auth_admin;
SET LOCAL search_path = auth;
INSERT INTO users (id, email, raw_user_meta_data, raw_app_meta_data, email_confirmed_at)
VALUES ('f0000000-0000-4000-8000-000000000006', 'frank@example.test',
        '{"full_name": "Frank"}', '{"provider": "google"}', now());
COMMIT;
