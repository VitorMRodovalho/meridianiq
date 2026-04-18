-- 021_audit_trail_user_agent.sql
--
-- Adds user_agent column to audit_log.
--
-- Background: v3.8 wave 13 (commit f53a4a3) added user_agent capture to the
-- audit trail at the application layer (src/api/organizations.py), but the
-- corresponding migration was never authored. Supabase silently dropped the
-- column from INSERTs, so the feature shipped with a silent functional gap:
-- ip_address is captured, user_agent is not.
--
-- This migration closes that gap as part of Cycle 1 v4.0 Wave 0 governance
-- cleanup (see ADR-0009). No application-code change required — existing
-- inserts already write the key.
--
-- Reference: ADR-0009 Wave 0; BUGS.md (historical v3.8 wave 13 gap).

ALTER TABLE public.audit_log
    ADD COLUMN IF NOT EXISTS user_agent TEXT;

COMMENT ON COLUMN public.audit_log.user_agent IS
    'User-Agent header captured at action time. Added 2026-04-18 to close the v3.8 wave 13 gap where the application layer wrote this key but the column did not exist.';
