-- Additions for Supabase's own postgres image, which ships the Supabase roles,
-- default privileges and auth.uid(), but a reduced auth.users table.
-- Migration 033 reads these two columns. Run as supabase_admin.
ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS email_confirmed_at timestamptz;
ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
