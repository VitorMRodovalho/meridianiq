-- Supabase-style roles, auth schema and default privileges for a throwaway
-- replica built from the stock postgres image. Run as the bootstrap
-- superuser (supabase_admin). Only objects that Supabase itself provides are
-- created here; everything in schema public comes from the repo migrations.

-- Roles, with the attributes Supabase gives them.
CREATE ROLE postgres LOGIN NOSUPERUSER CREATEDB CREATEROLE BYPASSRLS;
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE ROLE supabase_auth_admin LOGIN NOINHERIT CREATEROLE NOSUPERUSER;
GRANT anon, authenticated, service_role TO postgres;

-- Schema public is owned by postgres, and the client roles can use it.
ALTER SCHEMA public OWNER TO postgres;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

-- uuid-ossp lives in public here; in Supabase it lives in `extensions`,
-- which is on the default search_path. Either way uuid_generate_v4()
-- resolves unqualified.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA public;

-- Supabase's default privileges: every table, function and sequence that
-- postgres creates in public is granted to the three API roles.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON FUNCTIONS TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;

-- auth schema: owned by the auth service role, as in Supabase.
CREATE SCHEMA auth AUTHORIZATION supabase_auth_admin;
GRANT USAGE ON SCHEMA auth TO postgres, anon, authenticated, service_role;

CREATE TABLE auth.users (
    id                 uuid PRIMARY KEY,
    email              text,
    raw_user_meta_data jsonb DEFAULT '{}'::jsonb,
    raw_app_meta_data  jsonb DEFAULT '{}'::jsonb,
    created_at         timestamptz DEFAULT now(),
    email_confirmed_at timestamptz,
    deleted_at         timestamptz
);
ALTER TABLE auth.users OWNER TO supabase_auth_admin;
-- postgres needs these to add foreign keys to auth.users and to attach the
-- signup triggers, as it does in Supabase.
GRANT SELECT, REFERENCES, TRIGGER ON auth.users TO postgres;

-- auth.uid() / auth.role(), with Supabase's definitions: the subject of the
-- request's JWT claims, as PostgREST sets them per transaction.
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT coalesce(
        nullif(current_setting('request.jwt.claim.sub', true), ''),
        (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
    )::uuid
$$;
CREATE FUNCTION auth.role() RETURNS text LANGUAGE sql STABLE AS $$
    SELECT coalesce(
        nullif(current_setting('request.jwt.claim.role', true), ''),
        (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role')
    )::text
$$;
ALTER FUNCTION auth.uid() OWNER TO supabase_auth_admin;
ALTER FUNCTION auth.role() OWNER TO supabase_auth_admin;
GRANT EXECUTE ON FUNCTION auth.uid(), auth.role() TO PUBLIC;
