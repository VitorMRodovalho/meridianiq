-- Migration 014: SECURITY DEFINER RPCs + RLS policy fixes
--
-- Addresses:
-- 1. GDPR data deletion (cascade delete all user data)
-- 2. Programs table missing RLS policies (critical security gap)
-- 3. Sandbox flag persistence (replace in-memory tracking)
-- 4. Reports table missing RLS policies
-- 5. Benchmark contribution via RPC (enforces auth context)

-- ============================================================
-- 1. GDPR Data Deletion RPC
-- ============================================================
-- Cascade deletes all data owned by a user.
-- Must be called with the user's JWT (auth.uid() must match).

CREATE OR REPLACE FUNCTION delete_user_data(target_user_id UUID)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    deleted_uploads INT := 0;
    deleted_projects INT := 0;
    deleted_analyses INT := 0;
    deleted_benchmarks INT := 0;
BEGIN
    -- Verify caller is the target user or has service role
    IF auth.uid() IS NOT NULL AND auth.uid() != target_user_id THEN
        RAISE EXCEPTION 'Unauthorized: can only delete own data';
    END IF;

    -- Delete in dependency order (children first)
    DELETE FROM benchmark_projects WHERE contributed_by = target_user_id;
    GET DIAGNOSTICS deleted_benchmarks = ROW_COUNT;

    -- Analysis results cascade via project FK
    DELETE FROM analysis_results WHERE user_id = target_user_id;
    GET DIAGNOSTICS deleted_analyses = ROW_COUNT;

    DELETE FROM comparison_results WHERE user_id = target_user_id;
    DELETE FROM forensic_timelines WHERE user_id = target_user_id;
    DELETE FROM tia_analyses WHERE user_id = target_user_id;
    DELETE FROM evm_analyses WHERE user_id = target_user_id;
    DELETE FROM risk_simulations WHERE user_id = target_user_id;

    -- Projects and uploads
    DELETE FROM projects WHERE user_id = target_user_id;
    GET DIAGNOSTICS deleted_projects = ROW_COUNT;

    DELETE FROM schedule_uploads WHERE user_id = target_user_id;
    GET DIAGNOSTICS deleted_uploads = ROW_COUNT;

    -- Programs
    DELETE FROM programs WHERE user_id = target_user_id;

    -- API keys and user profiles: only delete if tables exist
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'api_keys') THEN
        EXECUTE 'DELETE FROM api_keys WHERE user_id = $1' USING target_user_id;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'user_profiles') THEN
        EXECUTE 'DELETE FROM user_profiles WHERE id = $1' USING target_user_id;
    END IF;

    RETURN json_build_object(
        'deleted_uploads', deleted_uploads,
        'deleted_projects', deleted_projects,
        'deleted_analyses', deleted_analyses,
        'deleted_benchmarks', deleted_benchmarks,
        'status', 'complete'
    );
END;
$$;

-- ============================================================
-- 2. Programs table — add missing RLS policies
-- ============================================================
-- programs table has RLS enabled (migration 005) but NO policies.

CREATE POLICY "Users see own programs" ON programs
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users insert own programs" ON programs
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users update own programs" ON programs
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users delete own programs" ON programs
  FOR DELETE USING (auth.uid() = user_id);

-- ============================================================
-- 3. Sandbox flag persistence RPC
-- ============================================================
-- Replaces in-memory _sandbox_projects set in app.py.

CREATE OR REPLACE FUNCTION set_project_sandbox(
    p_project_id UUID,
    p_is_sandbox BOOLEAN
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    upload_id_val UUID;
BEGIN
    -- Find the upload for this project and verify ownership
    SELECT su.id INTO upload_id_val
    FROM schedule_uploads su
    JOIN projects p ON p.upload_id = su.id
    WHERE p.id = p_project_id
      AND (auth.uid() IS NULL OR su.user_id = auth.uid());

    IF upload_id_val IS NULL THEN
        RAISE EXCEPTION 'Project not found or not owned by user';
    END IF;

    UPDATE schedule_uploads SET is_sandbox = p_is_sandbox WHERE id = upload_id_val;

    RETURN json_build_object('project_id', p_project_id, 'is_sandbox', p_is_sandbox);
END;
$$;

-- ============================================================
-- 4. Reports table — add missing RLS policies
-- ============================================================
-- reports table was created in migration 003 with RLS but no policies.

DO $$
BEGIN
    -- Only create if table exists and policies don't
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'reports') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'reports') THEN
            EXECUTE 'CREATE POLICY "Users see own reports" ON reports FOR SELECT USING (auth.uid() = user_id)';
            EXECUTE 'CREATE POLICY "Users insert own reports" ON reports FOR INSERT WITH CHECK (auth.uid() = user_id)';
        END IF;
    END IF;
END;
$$;

-- ============================================================
-- 5. Benchmark contribute RPC (enforces anonymization)
-- ============================================================

CREATE OR REPLACE FUNCTION contribute_benchmark(
    p_size_category TEXT,
    p_activity_count INT,
    p_relationship_count INT,
    p_wbs_depth INT,
    p_milestone_count INT,
    p_project_duration_days FLOAT,
    p_dcma_score FLOAT,
    p_logic_pct FLOAT,
    p_constraint_pct FLOAT,
    p_high_float_pct FLOAT,
    p_negative_float_pct FLOAT,
    p_high_duration_pct FLOAT,
    p_relationship_fs_pct FLOAT,
    p_lead_pct FLOAT,
    p_lag_pct FLOAT,
    p_bei FLOAT,
    p_cpli FLOAT,
    p_float_mean_days FLOAT,
    p_float_median_days FLOAT,
    p_float_stdev_days FLOAT,
    p_relationship_density FLOAT,
    p_critical_path_length INT,
    p_cp_percentage FLOAT,
    p_complete_pct FLOAT,
    p_active_pct FLOAT,
    p_not_started_pct FLOAT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    new_project_id UUID;
BEGIN
    -- Insert benchmark project (no identifying data)
    INSERT INTO benchmark_projects (
        contributed_by, size_category, activity_count, relationship_count,
        wbs_depth, milestone_count, project_duration_days
    )
    VALUES (
        auth.uid(), p_size_category, p_activity_count, p_relationship_count,
        p_wbs_depth, p_milestone_count, p_project_duration_days
    )
    RETURNING id INTO new_project_id;

    -- Insert metrics
    INSERT INTO benchmark_metrics (
        benchmark_project_id, dcma_score, logic_pct, constraint_pct,
        high_float_pct, negative_float_pct, high_duration_pct,
        relationship_fs_pct, lead_pct, lag_pct, bei, cpli,
        float_mean_days, float_median_days, float_stdev_days,
        relationship_density, critical_path_length, cp_percentage,
        complete_pct, active_pct, not_started_pct
    )
    VALUES (
        new_project_id, p_dcma_score, p_logic_pct, p_constraint_pct,
        p_high_float_pct, p_negative_float_pct, p_high_duration_pct,
        p_relationship_fs_pct, p_lead_pct, p_lag_pct, p_bei, p_cpli,
        p_float_mean_days, p_float_median_days, p_float_stdev_days,
        p_relationship_density, p_critical_path_length, p_cp_percentage,
        p_complete_pct, p_active_pct, p_not_started_pct
    );

    RETURN new_project_id;
END;
$$;

NOTIFY pgrst, 'reload schema';
