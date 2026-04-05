-- Migration 015: v3.0 persistence layer
-- Adds tables for what-if scenarios, generated schedules, optimization runs,
-- exported files, and duration predictions.

-- ================================================================
-- what_if_scenarios — save/compare scenario variants
-- ================================================================
CREATE TABLE IF NOT EXISTS what_if_scenarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'Scenario',
    config JSONB NOT NULL DEFAULT '{}',
    result JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_whatif_project ON what_if_scenarios(project_id);
CREATE INDEX IF NOT EXISTS idx_whatif_user ON what_if_scenarios(user_id);

ALTER TABLE what_if_scenarios ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own scenarios" ON what_if_scenarios;
CREATE POLICY "Users see own scenarios" ON what_if_scenarios
  FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users insert own scenarios" ON what_if_scenarios;
CREATE POLICY "Users insert own scenarios" ON what_if_scenarios
  FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users delete own scenarios" ON what_if_scenarios;
CREATE POLICY "Users delete own scenarios" ON what_if_scenarios
  FOR DELETE USING (auth.uid() = user_id);

-- ================================================================
-- generated_schedules — persist ML-generated schedules
-- ================================================================
CREATE TABLE IF NOT EXISTS generated_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    project_type TEXT NOT NULL DEFAULT 'commercial',
    size_category TEXT NOT NULL DEFAULT 'medium',
    project_name TEXT DEFAULT 'Generated Project',
    activity_count INT DEFAULT 0,
    relationship_count INT DEFAULT 0,
    predicted_duration_days FLOAT DEFAULT 0,
    config JSONB DEFAULT '{}',
    result JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_generated_user ON generated_schedules(user_id);
CREATE INDEX IF NOT EXISTS idx_generated_type ON generated_schedules(project_type);

ALTER TABLE generated_schedules ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own generated" ON generated_schedules;
CREATE POLICY "Users see own generated" ON generated_schedules
  FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users insert own generated" ON generated_schedules;
CREATE POLICY "Users insert own generated" ON generated_schedules
  FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users delete own generated" ON generated_schedules;
CREATE POLICY "Users delete own generated" ON generated_schedules
  FOR DELETE USING (auth.uid() = user_id);

-- ================================================================
-- optimization_runs — store ES optimizer results
-- ================================================================
CREATE TABLE IF NOT EXISTS optimization_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    config JSONB NOT NULL DEFAULT '{}',
    best_duration_days FLOAT DEFAULT 0,
    greedy_duration_days FLOAT DEFAULT 0,
    improvement_pct FLOAT DEFAULT 0,
    convergence_history JSONB DEFAULT '[]',
    result JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_optrun_project ON optimization_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_optrun_user ON optimization_runs(user_id);

ALTER TABLE optimization_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own optimization runs" ON optimization_runs;
CREATE POLICY "Users see own optimization runs" ON optimization_runs
  FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users insert own optimization runs" ON optimization_runs;
CREATE POLICY "Users insert own optimization runs" ON optimization_runs
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- ================================================================
-- exported_files — audit trail for XER/CSV/PDF exports
-- ================================================================
CREATE TABLE IF NOT EXISTS exported_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    export_type TEXT NOT NULL DEFAULT 'xer',
    file_size_bytes BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_export_project ON exported_files(project_id);
CREATE INDEX IF NOT EXISTS idx_export_user ON exported_files(user_id);

ALTER TABLE exported_files ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own exports" ON exported_files;
CREATE POLICY "Users see own exports" ON exported_files
  FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users insert own exports" ON exported_files;
CREATE POLICY "Users insert own exports" ON exported_files
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- ================================================================
-- duration_predictions — persist ML prediction results
-- ================================================================
CREATE TABLE IF NOT EXISTS duration_predictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    predicted_duration_days FLOAT DEFAULT 0,
    confidence_low FLOAT DEFAULT 0,
    confidence_high FLOAT DEFAULT 0,
    actual_duration_days FLOAT DEFAULT 0,
    model_r_squared FLOAT DEFAULT 0,
    training_samples INT DEFAULT 0,
    feature_importances JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_durpred_project ON duration_predictions(project_id);
CREATE INDEX IF NOT EXISTS idx_durpred_user ON duration_predictions(user_id);

ALTER TABLE duration_predictions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own predictions" ON duration_predictions;
CREATE POLICY "Users see own predictions" ON duration_predictions
  FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users insert own predictions" ON duration_predictions;
CREATE POLICY "Users insert own predictions" ON duration_predictions
  FOR INSERT WITH CHECK (auth.uid() = user_id);

NOTIFY pgrst, 'reload schema';
