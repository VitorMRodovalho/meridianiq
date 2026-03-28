-- MeridianIQ v0.8 — Storage refactor: XER files to bucket, metadata-only DB rows
-- Adds storage_path column and ensures metadata columns exist on the projects table.
-- The schedule_data JSONB column is no longer written to (kept for backward compat
-- with any existing rows but new inserts will not populate it).

ALTER TABLE projects ADD COLUMN IF NOT EXISTS storage_path TEXT;

-- Ensure metadata columns exist (they should from 001, but be safe)
ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_name TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS data_date TIMESTAMPTZ;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS activity_count INTEGER DEFAULT 0;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS relationship_count INTEGER DEFAULT 0;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS calendar_count INTEGER DEFAULT 0;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS wbs_count INTEGER DEFAULT 0;

-- Index on storage_path for quick lookups
CREATE INDEX IF NOT EXISTS idx_projects_storage_path
    ON projects (storage_path);
