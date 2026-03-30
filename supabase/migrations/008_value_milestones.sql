-- Migration 008: Value Milestones — business metadata on schedule milestones
-- Links schedule milestones to commercial values, payment triggers, and contract references.
-- Used by Owner and PM personas for payment forecasting and contract compliance.

CREATE TABLE IF NOT EXISTS value_milestones (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    org_id          UUID REFERENCES organizations(id),
    task_code       TEXT NOT NULL,  -- links to activity task_code
    task_name       TEXT,
    milestone_type  TEXT DEFAULT 'payment', -- payment, contractual, regulatory, substantial_completion, final_completion
    commercial_value DOUBLE PRECISION DEFAULT 0, -- dollar amount tied to this milestone
    currency        TEXT DEFAULT 'USD',
    payment_trigger TEXT DEFAULT '',  -- e.g., "Certificate of Substantial Completion"
    contract_ref    TEXT DEFAULT '',  -- e.g., "AIA A201 §9.8.1"
    notes           TEXT DEFAULT '',
    baseline_date   TIMESTAMPTZ,     -- contractual target date
    forecast_date   TIMESTAMPTZ,     -- current projected date
    actual_date     TIMESTAMPTZ,     -- when actually achieved
    status          TEXT DEFAULT 'pending', -- pending, at_risk, achieved, overdue
    created_by      UUID REFERENCES auth.users(id),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_value_milestones_project ON value_milestones(project_id);
CREATE INDEX IF NOT EXISTS idx_value_milestones_org ON value_milestones(org_id);
CREATE INDEX IF NOT EXISTS idx_value_milestones_task ON value_milestones(project_id, task_code);

ALTER TABLE value_milestones ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members can view value milestones"
    ON value_milestones FOR SELECT
    USING (
        org_id IN (SELECT org_id FROM memberships WHERE user_id = auth.uid())
        OR project_id IN (SELECT id FROM projects WHERE user_id = auth.uid())
    );

CREATE POLICY "Org admins can manage value milestones"
    ON value_milestones FOR INSERT
    WITH CHECK (
        org_id IN (
            SELECT org_id FROM memberships
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin', 'member')
        )
    );

CREATE POLICY "Org admins can update value milestones"
    ON value_milestones FOR UPDATE
    USING (
        org_id IN (
            SELECT org_id FROM memberships
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin', 'member')
        )
    );
