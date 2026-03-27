-- MeridianIQ v0.8 Intelligence Phase 1 — Database Schema
-- Float snapshots, alerts, health scores, and reports tables.

-- Float snapshots (one per activity per upload)
CREATE TABLE IF NOT EXISTS float_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_id UUID REFERENCES activities(id),
    upload_id UUID REFERENCES schedule_uploads(id),
    total_float INTEGER,
    free_float INTEGER,
    is_critical BOOLEAN DEFAULT FALSE,
    captured_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_float_snapshots_upload
    ON float_snapshots(upload_id);
CREATE INDEX IF NOT EXISTS idx_float_snapshots_activity
    ON float_snapshots(activity_id);

-- Alerts (produced by early warning engine)
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    upload_id UUID REFERENCES schedule_uploads(id),
    rule_id TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    title TEXT NOT NULL,
    description TEXT,
    affected_activities TEXT[],
    projected_impact_days FLOAT,
    confidence FLOAT,
    alert_score FLOAT,
    dismissed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alerts_project
    ON alerts(project_id);
CREATE INDEX IF NOT EXISTS idx_alerts_severity
    ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_dismissed
    ON alerts(dismissed);

-- Health scores (one per project per upload)
CREATE TABLE IF NOT EXISTS health_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    upload_id UUID REFERENCES schedule_uploads(id),
    overall_score FLOAT NOT NULL,
    dcma_score FLOAT,
    float_health FLOAT,
    logic_integrity FLOAT,
    trend_direction FLOAT,
    rating TEXT CHECK (rating IN ('excellent', 'good', 'fair', 'poor')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_health_scores_project
    ON health_scores(project_id);

-- Generated reports (for future PDF export)
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    user_id UUID REFERENCES auth.users(id),
    report_type TEXT NOT NULL,
    title TEXT,
    file_path TEXT,
    file_size INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reports_project
    ON reports(project_id);
CREATE INDEX IF NOT EXISTS idx_reports_user
    ON reports(user_id);

-- Enable RLS on new tables
ALTER TABLE float_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
