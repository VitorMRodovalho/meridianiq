-- Migration 009: Secure Forensic Workspace
-- Access-controlled environment for litigation-sensitive schedule analysis.
-- Forensic timelines can be placed on "litigation hold" with restricted access.

-- Add workspace and access control columns to forensic_timelines
ALTER TABLE forensic_timelines ADD COLUMN IF NOT EXISTS is_privileged BOOLEAN DEFAULT FALSE;
ALTER TABLE forensic_timelines ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);
ALTER TABLE forensic_timelines ADD COLUMN IF NOT EXISTS access_level TEXT DEFAULT 'standard'; -- standard, privileged, litigation_hold

CREATE INDEX IF NOT EXISTS idx_forensic_timelines_org ON forensic_timelines(org_id);

-- Forensic workspace access log (who viewed what, when — litigation chain of custody)
CREATE TABLE IF NOT EXISTS forensic_access_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timeline_id     TEXT NOT NULL,
    user_id         UUID NOT NULL REFERENCES auth.users(id),
    org_id          UUID REFERENCES organizations(id),
    action          TEXT NOT NULL, -- view, export, modify, share
    details         JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_forensic_access_log_timeline ON forensic_access_log(timeline_id, created_at DESC);

ALTER TABLE forensic_access_log ENABLE ROW LEVEL SECURITY;

-- Only org admins/owners can see forensic access logs
CREATE POLICY "Org admins can view forensic access logs"
    ON forensic_access_log FOR SELECT
    USING (org_id IN (
        SELECT org_id FROM memberships
        WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
    ));

-- Update forensic_timelines RLS: privileged timelines only visible to org admins
DROP POLICY IF EXISTS "Users can view own timelines" ON forensic_timelines;
CREATE POLICY "Users can view accessible timelines"
    ON forensic_timelines FOR SELECT
    USING (
        -- Standard timelines: owner can view
        (access_level = 'standard' AND auth.uid() = user_id)
        OR
        -- Org timelines: org members can view
        (access_level = 'standard' AND org_id IN (
            SELECT org_id FROM memberships WHERE user_id = auth.uid()
        ))
        OR
        -- Privileged/litigation timelines: only org admin/owner
        (access_level IN ('privileged', 'litigation_hold') AND org_id IN (
            SELECT org_id FROM memberships
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        ))
    );
