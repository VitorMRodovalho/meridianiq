-- Migration 010: Add sandbox mode for test/development data isolation
-- Projects marked as sandbox are only visible to their owner,
-- never appear in organization views, and are hidden from other users.

-- Add sandbox flag to schedule_uploads
ALTER TABLE schedule_uploads
ADD COLUMN IF NOT EXISTS is_sandbox BOOLEAN DEFAULT FALSE;

-- Add sandbox flag to programs
ALTER TABLE programs
ADD COLUMN IF NOT EXISTS is_sandbox BOOLEAN DEFAULT FALSE;

-- Update RLS policy to respect sandbox flag:
-- Non-sandbox: visible per normal rules (owner or org member)
-- Sandbox: visible ONLY to the owner
DROP POLICY IF EXISTS "Users see own uploads" ON schedule_uploads;
CREATE POLICY "Users see own uploads" ON schedule_uploads
  FOR SELECT
  USING (
    auth.uid() = user_id
    AND deleted_at IS NULL
  );

-- Note: sandbox filtering is enforced at application level (API)
-- rather than RLS, because org-shared projects need different
-- logic. RLS ensures users only see their own data; the API
-- further filters out sandbox projects from org/shared views.
