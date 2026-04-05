-- Migration 016: Risk register for discrete risk event management
-- Stores risk events with probability, impact, responsible party, and
-- linked activities. Feeds into Monte Carlo simulation (AACE RP 57R-09).

CREATE TABLE IF NOT EXISTS risk_register (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    risk_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT 'schedule',
    probability FLOAT NOT NULL DEFAULT 0.5,
    impact_days FLOAT NOT NULL DEFAULT 0.0,
    impact_cost FLOAT DEFAULT 0.0,
    status TEXT DEFAULT 'open',
    responsible_party TEXT DEFAULT '',
    mitigation TEXT DEFAULT '',
    affected_activities JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_risk_reg_project ON risk_register(project_id);
CREATE INDEX IF NOT EXISTS idx_risk_reg_user ON risk_register(user_id);
CREATE INDEX IF NOT EXISTS idx_risk_reg_status ON risk_register(status);

ALTER TABLE risk_register ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own risks" ON risk_register;
CREATE POLICY "Users see own risks" ON risk_register
  FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users insert own risks" ON risk_register;
CREATE POLICY "Users insert own risks" ON risk_register
  FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users update own risks" ON risk_register;
CREATE POLICY "Users update own risks" ON risk_register
  FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users delete own risks" ON risk_register;
CREATE POLICY "Users delete own risks" ON risk_register
  FOR DELETE USING (auth.uid() = user_id);

NOTIFY pgrst, 'reload schema';
