-- Migration 011: Fix missing RLS policies
-- Several tables had RLS enabled but no policies defined, making them
-- completely inaccessible. This migration adds proper owner-based policies.
-- Cross-referenced with ai-pm-research-hub lessons (deny-all default pattern).

-- ================================================================
-- Tables with RLS enabled but ZERO policies (created in 003/005)
-- ================================================================

-- float_snapshots (003_intelligence.sql)
DROP POLICY IF EXISTS "Users see own float_snapshots" ON float_snapshots;
CREATE POLICY "Users see own float_snapshots" ON float_snapshots
  FOR SELECT USING (
    upload_id IN (SELECT id FROM schedule_uploads WHERE user_id = auth.uid())
  );
DROP POLICY IF EXISTS "Users insert own float_snapshots" ON float_snapshots;
CREATE POLICY "Users insert own float_snapshots" ON float_snapshots
  FOR INSERT WITH CHECK (
    upload_id IN (SELECT id FROM schedule_uploads WHERE user_id = auth.uid())
  );

-- alerts (003_intelligence.sql)
DROP POLICY IF EXISTS "Users see own alerts" ON alerts;
CREATE POLICY "Users see own alerts" ON alerts
  FOR SELECT USING (
    project_id IN (
      SELECT p.id FROM projects p
      JOIN schedule_uploads u ON u.id = p.upload_id
      WHERE u.user_id = auth.uid()
    )
  );
DROP POLICY IF EXISTS "Users insert own alerts" ON alerts;
CREATE POLICY "Users insert own alerts" ON alerts
  FOR INSERT WITH CHECK (TRUE);  -- Service role inserts via backend

-- health_scores (003_intelligence.sql)
DROP POLICY IF EXISTS "Users see own health_scores" ON health_scores;
CREATE POLICY "Users see own health_scores" ON health_scores
  FOR SELECT USING (
    project_id IN (
      SELECT p.id FROM projects p
      JOIN schedule_uploads u ON u.id = p.upload_id
      WHERE u.user_id = auth.uid()
    )
  );
DROP POLICY IF EXISTS "Users insert own health_scores" ON health_scores;
CREATE POLICY "Users insert own health_scores" ON health_scores
  FOR INSERT WITH CHECK (TRUE);

-- reports (003_intelligence.sql)
DROP POLICY IF EXISTS "Users see own reports" ON reports;
CREATE POLICY "Users see own reports" ON reports
  FOR SELECT USING (user_id = auth.uid());
DROP POLICY IF EXISTS "Users insert own reports" ON reports;
CREATE POLICY "Users insert own reports" ON reports
  FOR INSERT WITH CHECK (user_id = auth.uid());
DROP POLICY IF EXISTS "Users delete own reports" ON reports;
CREATE POLICY "Users delete own reports" ON reports
  FOR DELETE USING (user_id = auth.uid());

-- programs (005_programs_table.sql)
DROP POLICY IF EXISTS "Users see own programs" ON programs;
CREATE POLICY "Users see own programs" ON programs
  FOR SELECT USING (user_id = auth.uid());
DROP POLICY IF EXISTS "Users insert own programs" ON programs;
CREATE POLICY "Users insert own programs" ON programs
  FOR INSERT WITH CHECK (user_id = auth.uid());
DROP POLICY IF EXISTS "Users update own programs" ON programs;
CREATE POLICY "Users update own programs" ON programs
  FOR UPDATE USING (user_id = auth.uid());

-- ================================================================
-- Tables missing UPDATE/DELETE policies (created in 001, RLS in 002)
-- ================================================================

-- analysis_results
DROP POLICY IF EXISTS "Users update own analysis_results" ON analysis_results;
CREATE POLICY "Users update own analysis_results" ON analysis_results
  FOR UPDATE USING (user_id = auth.uid());
DROP POLICY IF EXISTS "Users delete own analysis_results" ON analysis_results;
CREATE POLICY "Users delete own analysis_results" ON analysis_results
  FOR DELETE USING (user_id = auth.uid());

-- comparison_results
DROP POLICY IF EXISTS "Users update own comparison_results" ON comparison_results;
CREATE POLICY "Users update own comparison_results" ON comparison_results
  FOR UPDATE USING (user_id = auth.uid());
DROP POLICY IF EXISTS "Users delete own comparison_results" ON comparison_results;
CREATE POLICY "Users delete own comparison_results" ON comparison_results
  FOR DELETE USING (user_id = auth.uid());

-- forensic_timelines
DROP POLICY IF EXISTS "Users delete own forensic_timelines" ON forensic_timelines;
CREATE POLICY "Users delete own forensic_timelines" ON forensic_timelines
  FOR DELETE USING (user_id = auth.uid());

-- tia_analyses
DROP POLICY IF EXISTS "Users delete own tia_analyses" ON tia_analyses;
CREATE POLICY "Users delete own tia_analyses" ON tia_analyses
  FOR DELETE USING (user_id = auth.uid());

-- evm_analyses
DROP POLICY IF EXISTS "Users delete own evm_analyses" ON evm_analyses;
CREATE POLICY "Users delete own evm_analyses" ON evm_analyses
  FOR DELETE USING (user_id = auth.uid());

-- risk_simulations
DROP POLICY IF EXISTS "Users delete own risk_simulations" ON risk_simulations;
CREATE POLICY "Users delete own risk_simulations" ON risk_simulations
  FOR DELETE USING (user_id = auth.uid());

-- Reload PostgREST schema cache to pick up changes
NOTIFY pgrst, 'reload schema';
