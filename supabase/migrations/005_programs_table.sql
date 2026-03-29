-- Migration 005: Programs table — group uploads under programs with revision tracking
-- NOTE: Backfilling existing schedule_uploads into programs is a manual step.
--       Run a query like:
--         INSERT INTO programs (user_id, name, proj_short_name)
--         SELECT DISTINCT user_id, project_name, project_name
--         FROM schedule_uploads WHERE project_name IS NOT NULL;
--       Then UPDATE schedule_uploads to set program_id accordingly.

CREATE TABLE IF NOT EXISTS programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    proj_short_name TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE schedule_uploads ADD COLUMN IF NOT EXISTS program_id UUID REFERENCES programs(id);
ALTER TABLE schedule_uploads ADD COLUMN IF NOT EXISTS revision_number INTEGER;

ALTER TABLE programs ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS idx_programs_user_id ON programs(user_id);
CREATE INDEX IF NOT EXISTS idx_schedule_uploads_program_id ON schedule_uploads(program_id);
