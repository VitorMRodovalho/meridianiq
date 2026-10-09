-- Migration 038: an account can be deleted
--
-- Nine foreign keys to auth.users had no ON DELETE rule, so Postgres
-- refused to delete any account still referenced by one of them. Measured
-- in production on 2026-10-09: an account whose data had been erased
-- through DELETE /api/v1/user/data (which deletes rows, not the account)
-- still had 2 audit_log rows and 1 organization it had created, enough
-- to make the account undeletable. Every upload writes audit_log, so
-- in practice no user could have their account deleted.
--
-- The rule per column follows what the row is:
--   CASCADE   the row belongs to the user and goes with them
--             (programs.user_id, reports.user_id; the erasure already
--             deletes programs)
--   SET NULL  the row records an act that outlives the actor, and keeps
--             its record without the link to the person
--             (audit_log.user_id, forensic_access_log.user_id,
--             organizations.created_by, memberships.invited_by,
--             project_shares.shared_by, program_shares.shared_by,
--             value_milestones.created_by)
--
-- forensic_access_log.user_id was NOT NULL; it becomes nullable so the
-- access trail survives, unlinked, as PRIVACY.md says of audit_log.
--
-- Constraint names are the Postgres defaults, the same in production and
-- in a fresh install (migrations 003, 005, 007, 008, 009). Migration 002's
-- REFERENCES on projects, schedule_uploads and the analysis tables are
-- out of scope: production has no such constraints (the columns predated
-- 002), and the erasure deletes those rows first.
--
-- Apply by hand (psql -f), never `supabase db push` in production.

BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER TABLE public.programs
  DROP CONSTRAINT IF EXISTS programs_user_id_fkey,
  ADD CONSTRAINT programs_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.reports
  DROP CONSTRAINT IF EXISTS reports_user_id_fkey,
  ADD CONSTRAINT reports_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.audit_log
  DROP CONSTRAINT IF EXISTS audit_log_user_id_fkey,
  ADD CONSTRAINT audit_log_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE SET NULL;

ALTER TABLE public.forensic_access_log ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE public.forensic_access_log
  DROP CONSTRAINT IF EXISTS forensic_access_log_user_id_fkey,
  ADD CONSTRAINT forensic_access_log_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE SET NULL;

ALTER TABLE public.organizations
  DROP CONSTRAINT IF EXISTS organizations_created_by_fkey,
  ADD CONSTRAINT organizations_created_by_fkey
    FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE SET NULL;

ALTER TABLE public.memberships
  DROP CONSTRAINT IF EXISTS memberships_invited_by_fkey,
  ADD CONSTRAINT memberships_invited_by_fkey
    FOREIGN KEY (invited_by) REFERENCES auth.users(id) ON DELETE SET NULL;

ALTER TABLE public.project_shares
  DROP CONSTRAINT IF EXISTS project_shares_shared_by_fkey,
  ADD CONSTRAINT project_shares_shared_by_fkey
    FOREIGN KEY (shared_by) REFERENCES auth.users(id) ON DELETE SET NULL;

ALTER TABLE public.program_shares
  DROP CONSTRAINT IF EXISTS program_shares_shared_by_fkey,
  ADD CONSTRAINT program_shares_shared_by_fkey
    FOREIGN KEY (shared_by) REFERENCES auth.users(id) ON DELETE SET NULL;

ALTER TABLE public.value_milestones
  DROP CONSTRAINT IF EXISTS value_milestones_created_by_fkey,
  ADD CONSTRAINT value_milestones_created_by_fkey
    FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE SET NULL;

COMMIT;

-- Postcheck: expect 0 rows (no foreign key to auth.users without a rule).
--   select conrelid::regclass, conname from pg_constraint
--   where contype = 'f' and confrelid = 'auth.users'::regclass
--     and confdeltype = 'a';
