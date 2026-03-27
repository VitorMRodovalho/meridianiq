-- MeridianIQ v0.6 — Initial Supabase schema
-- All user_id columns are nullable (auth will be added in v0.7).
-- JSONB columns are used for flexible / evolving data structures.

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ================================================================
-- schedule_uploads
-- ================================================================
CREATE TABLE IF NOT EXISTS schedule_uploads (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID,
    original_filename TEXT NOT NULL,
    file_size_bytes  BIGINT,
    parser_version   TEXT,
    status           TEXT DEFAULT 'uploaded',
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_schedule_uploads_user
    ON schedule_uploads (user_id);
CREATE INDEX IF NOT EXISTS idx_schedule_uploads_created
    ON schedule_uploads (created_at DESC);

-- ================================================================
-- projects
-- ================================================================
CREATE TABLE IF NOT EXISTS projects (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_id         UUID REFERENCES schedule_uploads (id) ON DELETE CASCADE,
    user_id           UUID,
    project_name      TEXT,
    data_date         TIMESTAMPTZ,
    activity_count    INTEGER DEFAULT 0,
    relationship_count INTEGER DEFAULT 0,
    calendar_count    INTEGER DEFAULT 0,
    wbs_count         INTEGER DEFAULT 0,
    schedule_data     JSONB,
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_projects_user
    ON projects (user_id);
CREATE INDEX IF NOT EXISTS idx_projects_upload
    ON projects (upload_id);
CREATE INDEX IF NOT EXISTS idx_projects_created
    ON projects (created_at DESC);

-- ================================================================
-- wbs_elements
-- ================================================================
CREATE TABLE IF NOT EXISTS wbs_elements (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects (id) ON DELETE CASCADE,
    wbs_id          TEXT NOT NULL,
    parent_wbs_id   TEXT,
    wbs_short_name  TEXT,
    wbs_name        TEXT,
    seq_num         INTEGER DEFAULT 0,
    proj_node_flag  TEXT DEFAULT 'N',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wbs_elements_project
    ON wbs_elements (project_id);

-- ================================================================
-- activities
-- ================================================================
CREATE TABLE IF NOT EXISTS activities (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID REFERENCES projects (id) ON DELETE CASCADE,
    task_id             TEXT NOT NULL,
    task_code           TEXT,
    task_name           TEXT,
    task_type           TEXT,
    status_code         TEXT,
    wbs_id              TEXT,
    clndr_id            TEXT,
    total_float_hr_cnt  DOUBLE PRECISION,
    free_float_hr_cnt   DOUBLE PRECISION,
    remain_drtn_hr_cnt  DOUBLE PRECISION DEFAULT 0,
    target_drtn_hr_cnt  DOUBLE PRECISION DEFAULT 0,
    act_start_date      TIMESTAMPTZ,
    act_end_date        TIMESTAMPTZ,
    early_start_date    TIMESTAMPTZ,
    early_end_date      TIMESTAMPTZ,
    late_start_date     TIMESTAMPTZ,
    late_end_date       TIMESTAMPTZ,
    target_start_date   TIMESTAMPTZ,
    target_end_date     TIMESTAMPTZ,
    phys_complete_pct   DOUBLE PRECISION DEFAULT 0,
    extra_data          JSONB,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_activities_project
    ON activities (project_id);
CREATE INDEX IF NOT EXISTS idx_activities_task_id
    ON activities (project_id, task_id);
CREATE INDEX IF NOT EXISTS idx_activities_status
    ON activities (project_id, status_code);

-- ================================================================
-- predecessors (relationships)
-- ================================================================
CREATE TABLE IF NOT EXISTS predecessors (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects (id) ON DELETE CASCADE,
    task_pred_id    TEXT,
    task_id         TEXT NOT NULL,
    pred_task_id    TEXT NOT NULL,
    pred_type       TEXT DEFAULT 'PR_FS',
    lag_hr_cnt      DOUBLE PRECISION DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_predecessors_project
    ON predecessors (project_id);
CREATE INDEX IF NOT EXISTS idx_predecessors_task
    ON predecessors (project_id, task_id);

-- ================================================================
-- calendars
-- ================================================================
CREATE TABLE IF NOT EXISTS calendars (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects (id) ON DELETE CASCADE,
    clndr_id        TEXT NOT NULL,
    clndr_name      TEXT,
    day_hr_cnt      DOUBLE PRECISION DEFAULT 8.0,
    week_hr_cnt     DOUBLE PRECISION DEFAULT 40.0,
    clndr_type      TEXT,
    default_flag    TEXT DEFAULT 'N',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_calendars_project
    ON calendars (project_id);

-- ================================================================
-- resources
-- ================================================================
CREATE TABLE IF NOT EXISTS resources (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects (id) ON DELETE CASCADE,
    rsrc_id         TEXT NOT NULL,
    rsrc_name       TEXT,
    rsrc_type       TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_resources_project
    ON resources (project_id);

-- ================================================================
-- resource_assignments
-- ================================================================
CREATE TABLE IF NOT EXISTS resource_assignments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects (id) ON DELETE CASCADE,
    task_id         TEXT NOT NULL,
    rsrc_id         TEXT,
    target_qty      DOUBLE PRECISION DEFAULT 0,
    act_reg_qty     DOUBLE PRECISION DEFAULT 0,
    remain_qty      DOUBLE PRECISION DEFAULT 0,
    target_cost     DOUBLE PRECISION DEFAULT 0,
    act_reg_cost    DOUBLE PRECISION DEFAULT 0,
    remain_cost     DOUBLE PRECISION DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_resource_assignments_project
    ON resource_assignments (project_id);
CREATE INDEX IF NOT EXISTS idx_resource_assignments_task
    ON resource_assignments (project_id, task_id);

-- ================================================================
-- cost_accounts
-- ================================================================
CREATE TABLE IF NOT EXISTS cost_accounts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects (id) ON DELETE CASCADE,
    acct_id         TEXT NOT NULL,
    acct_name       TEXT,
    parent_acct_id  TEXT,
    extra_data      JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cost_accounts_project
    ON cost_accounts (project_id);

-- ================================================================
-- activity_code_types
-- ================================================================
CREATE TABLE IF NOT EXISTS activity_code_types (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID REFERENCES projects (id) ON DELETE CASCADE,
    actv_code_type_id   TEXT NOT NULL,
    actv_code_type      TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_activity_code_types_project
    ON activity_code_types (project_id);

-- ================================================================
-- activity_codes
-- ================================================================
CREATE TABLE IF NOT EXISTS activity_codes (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID REFERENCES projects (id) ON DELETE CASCADE,
    actv_code_id        TEXT NOT NULL,
    actv_code_type_id   TEXT,
    actv_code_name      TEXT,
    short_name          TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_activity_codes_project
    ON activity_codes (project_id);

-- ================================================================
-- udf_types
-- ================================================================
CREATE TABLE IF NOT EXISTS udf_types (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects (id) ON DELETE CASCADE,
    udf_type_id     TEXT NOT NULL,
    table_name      TEXT,
    udf_type_label  TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_udf_types_project
    ON udf_types (project_id);

-- ================================================================
-- udf_values
-- ================================================================
CREATE TABLE IF NOT EXISTS udf_values (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects (id) ON DELETE CASCADE,
    udf_type_id     TEXT NOT NULL,
    fk_id           TEXT,
    udf_text        TEXT,
    udf_number      DOUBLE PRECISION,
    udf_date        TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_udf_values_project
    ON udf_values (project_id);
CREATE INDEX IF NOT EXISTS idx_udf_values_type
    ON udf_values (project_id, udf_type_id);

-- ================================================================
-- analysis_results (DCMA, CPM, generic analytics)
-- ================================================================
CREATE TABLE IF NOT EXISTS analysis_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID REFERENCES projects (id) ON DELETE CASCADE,
    user_id         UUID,
    analysis_type   TEXT NOT NULL,
    results         JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analysis_results_project
    ON analysis_results (project_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_type
    ON analysis_results (project_id, analysis_type);

-- ================================================================
-- comparison_results
-- ================================================================
CREATE TABLE IF NOT EXISTS comparison_results (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    baseline_project_id UUID REFERENCES projects (id) ON DELETE CASCADE,
    update_project_id   UUID REFERENCES projects (id) ON DELETE CASCADE,
    user_id             UUID,
    results             JSONB,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_comparison_results_baseline
    ON comparison_results (baseline_project_id);
CREATE INDEX IF NOT EXISTS idx_comparison_results_update
    ON comparison_results (update_project_id);

-- ================================================================
-- forensic_timelines
-- ================================================================
CREATE TABLE IF NOT EXISTS forensic_timelines (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timeline_id       TEXT UNIQUE,
    user_id           UUID,
    project_name      TEXT,
    schedule_count    INTEGER DEFAULT 0,
    total_delay_days  DOUBLE PRECISION DEFAULT 0,
    timeline_data     JSONB,
    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_forensic_timelines_tid
    ON forensic_timelines (timeline_id);

-- ================================================================
-- tia_analyses
-- ================================================================
CREATE TABLE IF NOT EXISTS tia_analyses (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id     TEXT UNIQUE,
    user_id         UUID,
    project_name    TEXT,
    analysis_data   JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tia_analyses_aid
    ON tia_analyses (analysis_id);

-- ================================================================
-- evm_analyses
-- ================================================================
CREATE TABLE IF NOT EXISTS evm_analyses (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id     TEXT UNIQUE,
    user_id         UUID,
    project_name    TEXT,
    analysis_data   JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evm_analyses_aid
    ON evm_analyses (analysis_id);

-- ================================================================
-- risk_simulations
-- ================================================================
CREATE TABLE IF NOT EXISTS risk_simulations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    simulation_id   TEXT UNIQUE,
    user_id         UUID,
    project_name    TEXT,
    simulation_data JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_risk_simulations_sid
    ON risk_simulations (simulation_id);
