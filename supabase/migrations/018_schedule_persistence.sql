-- Migration 018: Schedule persistence — RLS + schema gaps + missing tables
-- Enables full relational persistence of parsed schedule data.
-- Previously, schedule detail tables (activities, wbs_elements, etc.)
-- were created in 001 but never populated and had no RLS policies.
--
-- This migration:
-- 1. Adds missing columns to existing tables
-- 2. Creates 3 new tables (task_activity_codes, financial_periods, task_financials)
-- 3. Enables RLS on all schedule detail tables with project-ownership policies
-- 4. Backend (service_role key) bypasses RLS — no extra policies needed

-- ================================================================
-- 1. Schema Gaps — add missing columns
-- ================================================================

-- calendars: clndr_data is the raw calendar definition string used by CPM engine
ALTER TABLE public.calendars ADD COLUMN IF NOT EXISTS clndr_data TEXT;

-- resource_assignments: missing taskrsrc_id and proj_id from P6 TASKRSRC table
ALTER TABLE public.resource_assignments ADD COLUMN IF NOT EXISTS taskrsrc_id TEXT;
ALTER TABLE public.resource_assignments ADD COLUMN IF NOT EXISTS proj_id TEXT;

-- ================================================================
-- 2. New Tables — exist in Pydantic models but not in DB
-- ================================================================

-- task_activity_codes: P6 TASKACTV table — maps activities to activity code values
CREATE TABLE IF NOT EXISTS public.task_activity_codes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    task_id         TEXT NOT NULL,
    actv_code_id    TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_task_activity_codes_project
    ON public.task_activity_codes(project_id);
CREATE INDEX IF NOT EXISTS idx_task_activity_codes_task
    ON public.task_activity_codes(project_id, task_id);

-- financial_periods: P6 FINDATES table — cost period definitions
CREATE TABLE IF NOT EXISTS public.financial_periods (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    fin_dates_id    TEXT NOT NULL,
    fin_dates_name  TEXT,
    start_date      TIMESTAMPTZ,
    end_date        TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_financial_periods_project
    ON public.financial_periods(project_id);

-- task_financials: P6 TASKFIN table — per-activity cost data by period
CREATE TABLE IF NOT EXISTS public.task_financials (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    task_id         TEXT NOT NULL,
    fin_dates_id    TEXT,
    target_cost     DOUBLE PRECISION DEFAULT 0,
    act_cost        DOUBLE PRECISION DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_task_financials_project
    ON public.task_financials(project_id);
CREATE INDEX IF NOT EXISTS idx_task_financials_task
    ON public.task_financials(project_id, task_id);

-- ================================================================
-- 3. Enable RLS on all schedule detail tables
-- ================================================================
-- These tables use project_id FK to projects, which has user_id.
-- Policy pattern: access rows whose project belongs to the current user.
-- The service_role key (used by the Python backend) bypasses RLS.

-- activities
ALTER TABLE public.activities ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "activities_select_own" ON public.activities;
CREATE POLICY "activities_select_own" ON public.activities
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "activities_insert_own" ON public.activities;
CREATE POLICY "activities_insert_own" ON public.activities
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "activities_delete_own" ON public.activities;
CREATE POLICY "activities_delete_own" ON public.activities
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- wbs_elements
ALTER TABLE public.wbs_elements ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "wbs_elements_select_own" ON public.wbs_elements;
CREATE POLICY "wbs_elements_select_own" ON public.wbs_elements
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "wbs_elements_insert_own" ON public.wbs_elements;
CREATE POLICY "wbs_elements_insert_own" ON public.wbs_elements
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "wbs_elements_delete_own" ON public.wbs_elements;
CREATE POLICY "wbs_elements_delete_own" ON public.wbs_elements
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- predecessors
ALTER TABLE public.predecessors ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "predecessors_select_own" ON public.predecessors;
CREATE POLICY "predecessors_select_own" ON public.predecessors
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "predecessors_insert_own" ON public.predecessors;
CREATE POLICY "predecessors_insert_own" ON public.predecessors
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "predecessors_delete_own" ON public.predecessors;
CREATE POLICY "predecessors_delete_own" ON public.predecessors
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- calendars
ALTER TABLE public.calendars ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "calendars_select_own" ON public.calendars;
CREATE POLICY "calendars_select_own" ON public.calendars
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "calendars_insert_own" ON public.calendars;
CREATE POLICY "calendars_insert_own" ON public.calendars
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "calendars_delete_own" ON public.calendars;
CREATE POLICY "calendars_delete_own" ON public.calendars
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- resources
ALTER TABLE public.resources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "resources_select_own" ON public.resources;
CREATE POLICY "resources_select_own" ON public.resources
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "resources_insert_own" ON public.resources;
CREATE POLICY "resources_insert_own" ON public.resources
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "resources_delete_own" ON public.resources;
CREATE POLICY "resources_delete_own" ON public.resources
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- resource_assignments
ALTER TABLE public.resource_assignments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "resource_assignments_select_own" ON public.resource_assignments;
CREATE POLICY "resource_assignments_select_own" ON public.resource_assignments
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "resource_assignments_insert_own" ON public.resource_assignments;
CREATE POLICY "resource_assignments_insert_own" ON public.resource_assignments
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "resource_assignments_delete_own" ON public.resource_assignments;
CREATE POLICY "resource_assignments_delete_own" ON public.resource_assignments
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- cost_accounts
ALTER TABLE public.cost_accounts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "cost_accounts_select_own" ON public.cost_accounts;
CREATE POLICY "cost_accounts_select_own" ON public.cost_accounts
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "cost_accounts_insert_own" ON public.cost_accounts;
CREATE POLICY "cost_accounts_insert_own" ON public.cost_accounts
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "cost_accounts_delete_own" ON public.cost_accounts;
CREATE POLICY "cost_accounts_delete_own" ON public.cost_accounts
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- activity_code_types
ALTER TABLE public.activity_code_types ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "activity_code_types_select_own" ON public.activity_code_types;
CREATE POLICY "activity_code_types_select_own" ON public.activity_code_types
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "activity_code_types_insert_own" ON public.activity_code_types;
CREATE POLICY "activity_code_types_insert_own" ON public.activity_code_types
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "activity_code_types_delete_own" ON public.activity_code_types;
CREATE POLICY "activity_code_types_delete_own" ON public.activity_code_types
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- activity_codes
ALTER TABLE public.activity_codes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "activity_codes_select_own" ON public.activity_codes;
CREATE POLICY "activity_codes_select_own" ON public.activity_codes
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "activity_codes_insert_own" ON public.activity_codes;
CREATE POLICY "activity_codes_insert_own" ON public.activity_codes
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "activity_codes_delete_own" ON public.activity_codes;
CREATE POLICY "activity_codes_delete_own" ON public.activity_codes
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- udf_types
ALTER TABLE public.udf_types ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "udf_types_select_own" ON public.udf_types;
CREATE POLICY "udf_types_select_own" ON public.udf_types
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "udf_types_insert_own" ON public.udf_types;
CREATE POLICY "udf_types_insert_own" ON public.udf_types
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "udf_types_delete_own" ON public.udf_types;
CREATE POLICY "udf_types_delete_own" ON public.udf_types
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- udf_values
ALTER TABLE public.udf_values ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "udf_values_select_own" ON public.udf_values;
CREATE POLICY "udf_values_select_own" ON public.udf_values
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "udf_values_insert_own" ON public.udf_values;
CREATE POLICY "udf_values_insert_own" ON public.udf_values
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "udf_values_delete_own" ON public.udf_values;
CREATE POLICY "udf_values_delete_own" ON public.udf_values
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- task_activity_codes (new table)
ALTER TABLE public.task_activity_codes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "task_activity_codes_select_own" ON public.task_activity_codes;
CREATE POLICY "task_activity_codes_select_own" ON public.task_activity_codes
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "task_activity_codes_insert_own" ON public.task_activity_codes;
CREATE POLICY "task_activity_codes_insert_own" ON public.task_activity_codes
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "task_activity_codes_delete_own" ON public.task_activity_codes;
CREATE POLICY "task_activity_codes_delete_own" ON public.task_activity_codes
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- financial_periods (new table)
ALTER TABLE public.financial_periods ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "financial_periods_select_own" ON public.financial_periods;
CREATE POLICY "financial_periods_select_own" ON public.financial_periods
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "financial_periods_insert_own" ON public.financial_periods;
CREATE POLICY "financial_periods_insert_own" ON public.financial_periods
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "financial_periods_delete_own" ON public.financial_periods;
CREATE POLICY "financial_periods_delete_own" ON public.financial_periods
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- task_financials (new table)
ALTER TABLE public.task_financials ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "task_financials_select_own" ON public.task_financials;
CREATE POLICY "task_financials_select_own" ON public.task_financials
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "task_financials_insert_own" ON public.task_financials;
CREATE POLICY "task_financials_insert_own" ON public.task_financials
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "task_financials_delete_own" ON public.task_financials;
CREATE POLICY "task_financials_delete_own" ON public.task_financials
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- ================================================================
-- 4. Reload PostgREST schema cache
-- ================================================================
NOTIFY pgrst, 'reload schema';
