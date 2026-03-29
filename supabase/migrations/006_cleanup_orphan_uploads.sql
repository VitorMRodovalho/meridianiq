-- Migration 006: Soft-delete orphan schedule uploads from pre-v0.8.1
-- These rows have NULL xer_storage_path and/or NULL user_id because they
-- were uploaded before the storage refactor (migration 004).
-- The dashboard guard already hides them; this migration marks them
-- as deleted so they don't accumulate.

-- Add a soft-delete column if it doesn't exist
ALTER TABLE schedule_uploads
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;

-- Mark orphan rows (no storage path or no user) as soft-deleted
UPDATE schedule_uploads
SET deleted_at = NOW()
WHERE deleted_at IS NULL
  AND (xer_storage_path IS NULL OR user_id IS NULL);

-- Update RLS policy to exclude soft-deleted rows
-- (only if the policy exists — this is idempotent)
DROP POLICY IF EXISTS "Users see own uploads" ON schedule_uploads;
CREATE POLICY "Users see own uploads" ON schedule_uploads
  FOR SELECT
  USING (auth.uid() = user_id AND deleted_at IS NULL);

DROP POLICY IF EXISTS "Users insert own uploads" ON schedule_uploads;
CREATE POLICY "Users insert own uploads" ON schedule_uploads
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users delete own uploads" ON schedule_uploads;
CREATE POLICY "Users delete own uploads" ON schedule_uploads
  FOR UPDATE
  USING (auth.uid() = user_id);
