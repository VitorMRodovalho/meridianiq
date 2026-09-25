-- Migration 031: pin search_path on the signup trigger functions
--
-- handle_new_user (002) and handle_new_user_org (007) are SECURITY DEFINER
-- trigger functions on auth.users with no pinned search_path, so they resolve
-- unqualified names through the caller's search_path. The Supabase auth
-- service inserts into auth.users with search_path=auth, where the unqualified
-- `organizations` / `memberships` in handle_new_user_org do not resolve. The
-- insert then fails ("Database error saving new user"), and every new-user
-- signup has failed since migration 007 on 2026-03-29.
--
-- Pinning `public, pg_temp` fixes name resolution and follows the Supabase
-- linter guidance for SECURITY DEFINER functions (function_search_path_mutable).
-- tests/test_migrations_security_definer.py keeps this from regressing.
--
-- Idempotent.

ALTER FUNCTION public.handle_new_user() SET search_path = public, pg_temp;
ALTER FUNCTION public.handle_new_user_org() SET search_path = public, pg_temp;
