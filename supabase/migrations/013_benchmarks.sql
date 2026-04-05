-- Migration 013: Benchmark database for cross-project comparison
-- Stores anonymized aggregate metrics (no activity names, WBS text, or identifying data).
-- All users can read benchmarks; authenticated users can contribute.

CREATE TABLE IF NOT EXISTS benchmark_projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contributed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    size_category TEXT NOT NULL CHECK (size_category IN ('small', 'medium', 'large', 'mega')),
    activity_count INT NOT NULL DEFAULT 0,
    relationship_count INT NOT NULL DEFAULT 0,
    wbs_depth INT DEFAULT 0,
    milestone_count INT DEFAULT 0,
    project_duration_days FLOAT DEFAULT 0,
    is_sandbox BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS benchmark_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    benchmark_project_id UUID REFERENCES benchmark_projects(id) ON DELETE CASCADE NOT NULL,
    -- DCMA metrics
    dcma_score FLOAT DEFAULT 0,
    logic_pct FLOAT DEFAULT 0,
    constraint_pct FLOAT DEFAULT 0,
    high_float_pct FLOAT DEFAULT 0,
    negative_float_pct FLOAT DEFAULT 0,
    high_duration_pct FLOAT DEFAULT 0,
    relationship_fs_pct FLOAT DEFAULT 0,
    lead_pct FLOAT DEFAULT 0,
    lag_pct FLOAT DEFAULT 0,
    bei FLOAT DEFAULT 0,
    cpli FLOAT DEFAULT 0,
    -- Float distribution
    float_mean_days FLOAT DEFAULT 0,
    float_median_days FLOAT DEFAULT 0,
    float_stdev_days FLOAT DEFAULT 0,
    -- Network metrics
    relationship_density FLOAT DEFAULT 0,
    critical_path_length INT DEFAULT 0,
    cp_percentage FLOAT DEFAULT 0,
    -- Progress
    complete_pct FLOAT DEFAULT 0,
    active_pct FLOAT DEFAULT 0,
    not_started_pct FLOAT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_benchmark_projects_size ON benchmark_projects (size_category);
CREATE INDEX IF NOT EXISTS idx_benchmark_projects_user ON benchmark_projects (contributed_by);
CREATE INDEX IF NOT EXISTS idx_benchmark_metrics_project ON benchmark_metrics (benchmark_project_id);

-- RLS: benchmarks are public-read, authenticated-write
ALTER TABLE benchmark_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE benchmark_metrics ENABLE ROW LEVEL SECURITY;

-- Anyone can read benchmarks (anonymized data)
CREATE POLICY "Benchmarks are publicly readable" ON benchmark_projects
  FOR SELECT USING (TRUE);

CREATE POLICY "Benchmark metrics are publicly readable" ON benchmark_metrics
  FOR SELECT USING (TRUE);

-- Authenticated users can contribute
CREATE POLICY "Authenticated users can contribute benchmarks" ON benchmark_projects
  FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can add metrics" ON benchmark_metrics
  FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- Users can delete their own contributions
CREATE POLICY "Users delete own benchmark contributions" ON benchmark_projects
  FOR DELETE USING (auth.uid() = contributed_by);

NOTIFY pgrst, 'reload schema';
