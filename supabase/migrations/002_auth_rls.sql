-- Migration: 002_auth_rls.sql
-- Description: Authentication, user profiles, RLS policies
-- Version: v0.7.0-dev

-- ================================================================
-- 1. User Profiles Table
-- ================================================================

CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    full_name TEXT,
    company TEXT,
    role TEXT NOT NULL DEFAULT 'scheduler',
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, email, full_name, avatar_url)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', ''),
        COALESCE(NEW.raw_user_meta_data->>'avatar_url', NEW.raw_user_meta_data->>'picture', '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ================================================================
-- 2. Add user_id column to all data tables
-- ================================================================

ALTER TABLE public.schedule_uploads ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
ALTER TABLE public.analysis_results ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
ALTER TABLE public.comparison_results ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
ALTER TABLE public.forensic_timelines ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
ALTER TABLE public.tia_analyses ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
ALTER TABLE public.evm_analyses ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
ALTER TABLE public.risk_simulations ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);

-- ================================================================
-- 3. Enable RLS on all tables
-- ================================================================

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.schedule_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.comparison_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.forensic_timelines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tia_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evm_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_simulations ENABLE ROW LEVEL SECURITY;

-- ================================================================
-- 4. RLS Policies — user_profiles
-- ================================================================

CREATE POLICY "Users can view own profile"
    ON public.user_profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.user_profiles FOR UPDATE
    USING (auth.uid() = id);

-- ================================================================
-- 5. RLS Policies — schedule_uploads
-- ================================================================

CREATE POLICY "Users can view own uploads"
    ON public.schedule_uploads FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own uploads"
    ON public.schedule_uploads FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own uploads"
    ON public.schedule_uploads FOR DELETE
    USING (auth.uid() = user_id);

-- ================================================================
-- 6. RLS Policies — projects
-- ================================================================

CREATE POLICY "Users can view own projects"
    ON public.projects FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own projects"
    ON public.projects FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own projects"
    ON public.projects FOR DELETE
    USING (auth.uid() = user_id);

-- ================================================================
-- 7. RLS Policies — analysis_results
-- ================================================================

CREATE POLICY "Users can view own analyses"
    ON public.analysis_results FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own analyses"
    ON public.analysis_results FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ================================================================
-- 8. RLS Policies — comparison_results
-- ================================================================

CREATE POLICY "Users can view own comparisons"
    ON public.comparison_results FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own comparisons"
    ON public.comparison_results FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ================================================================
-- 9. RLS Policies — forensic_timelines
-- ================================================================

CREATE POLICY "Users can view own timelines"
    ON public.forensic_timelines FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own timelines"
    ON public.forensic_timelines FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ================================================================
-- 10. RLS Policies — tia_analyses
-- ================================================================

CREATE POLICY "Users can view own TIA analyses"
    ON public.tia_analyses FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own TIA analyses"
    ON public.tia_analyses FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ================================================================
-- 11. RLS Policies — evm_analyses
-- ================================================================

CREATE POLICY "Users can view own EVM analyses"
    ON public.evm_analyses FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own EVM analyses"
    ON public.evm_analyses FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ================================================================
-- 12. RLS Policies — risk_simulations
-- ================================================================

CREATE POLICY "Users can view own risk simulations"
    ON public.risk_simulations FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own risk simulations"
    ON public.risk_simulations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ================================================================
-- 13. Service role bypass (for backend operations)
-- ================================================================
-- The service_role key bypasses RLS by default in Supabase.
-- No additional policies needed for backend admin access.

-- ================================================================
-- 14. Indexes for user_id lookups
-- ================================================================

CREATE INDEX IF NOT EXISTS idx_schedule_uploads_user_id ON public.schedule_uploads(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON public.projects(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_user_id ON public.analysis_results(user_id);
CREATE INDEX IF NOT EXISTS idx_comparison_results_user_id ON public.comparison_results(user_id);
CREATE INDEX IF NOT EXISTS idx_forensic_timelines_user_id ON public.forensic_timelines(user_id);
CREATE INDEX IF NOT EXISTS idx_tia_analyses_user_id ON public.tia_analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_evm_analyses_user_id ON public.evm_analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_risk_simulations_user_id ON public.risk_simulations(user_id);
