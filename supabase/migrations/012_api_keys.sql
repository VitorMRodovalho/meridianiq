-- Migration 012: SUPERSEDED BY 017 + 026 (see ADR-0017).
--
-- This migration previously created an ``api_keys`` table with columns
-- (id UUID, key_prefix, is_active, expires_at) that did NOT match the
-- runtime contract in src/api/auth.py.  The canonical schema is in
-- 017_api_keys.sql; migration 026 reconciles any legacy 012-style live
-- table to the 017 shape in a single idempotent pass.
--
-- The file is retained as a no-op so migration history stays intact on
-- instances that already recorded 012 in supabase_migrations.schema_migrations.
-- Do NOT rewrite historical migrations — add a forward-fix (026) instead.
--
-- Related: ADR-0017, audit AUDIT-001 (P0), GitHub issue #16.

-- intentionally empty
SELECT 1 AS migration_012_noop;
