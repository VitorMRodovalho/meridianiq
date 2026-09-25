-- Migration 030: remove anon/PUBLIC EXECUTE from callable SECURITY DEFINER RPCs
--
-- The three RPCs below were created (014) without an explicit grant policy,
-- so PostgreSQL's default EXECUTE-to-PUBLIC applied and Supabase additionally
-- granted EXECUTE to `anon`. Their ownership guards only compare auth.uid()
-- when it is NOT NULL, so they must not be reachable without a user JWT.
--
-- Callers after this migration:
--   * backend (service_role client) — unchanged, keeps EXECUTE
--   * authenticated users            — unchanged, guards enforce own-rows
--   * anon / PUBLIC                  — no EXECUTE
--
-- Trigger / event-trigger functions (handle_new_user, handle_new_user_org,
-- rls_auto_enable) are not callable as RPC and are intentionally untouched.
--
-- Idempotent: REVOKE of an absent privilege is a no-op.

REVOKE EXECUTE ON FUNCTION public.delete_user_data(uuid) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.set_project_sandbox(uuid, boolean) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.contribute_benchmark(
    text, integer, integer, integer, integer, double precision, double precision,
    double precision, double precision, double precision, double precision,
    double precision, double precision, double precision, double precision,
    double precision, double precision, double precision, double precision,
    double precision, double precision, integer, double precision,
    double precision, double precision, double precision
) FROM PUBLIC, anon;

GRANT EXECUTE ON FUNCTION public.delete_user_data(uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.set_project_sandbox(uuid, boolean) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.contribute_benchmark(
    text, integer, integer, integer, integer, double precision, double precision,
    double precision, double precision, double precision, double precision,
    double precision, double precision, double precision, double precision,
    double precision, double precision, double precision, double precision,
    double precision, double precision, integer, double precision,
    double precision, double precision, double precision
) TO authenticated, service_role;
