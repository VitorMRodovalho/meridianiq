-- Migration 019: ERP-ready cost tables
-- Provides a generic data model for cost management that supports
-- integration with major construction PMIS/ERP systems:
--   Oracle Primavera Unifier, SAP PS/PPM, Kahua, e-Builder/Trimble, InEight
--
-- Standards:
--   AACE RP 10S-90 (Cost Engineering Terminology)
--   ANSI/EIA-748 (Earned Value Management Systems)
--   ISO 21511 (Work Breakdown Structures)
--   UN/CEFACT (Project Data Exchange)
--   MasterFormat / UniFormat / OmniClass (Cost Coding Systems)
--
-- Design principles:
--   1. Universal fields present across all major PMIS/ERP systems
--   2. Self-referential hierarchies (CBS, OBS) for arbitrary depth
--   3. Data lineage tracking (source system, record version, sync status)
--   4. Time-phased cost snapshots for trending and S-curve generation
--   5. NUMERIC(18,2) for all monetary values (avoids float rounding)

-- ================================================================
-- 1. erp_sources — Data lineage registry
-- ================================================================
-- Tracks which external system provided cost data, when it was last
-- synced, and connection metadata (credentials stored externally).

CREATE TABLE IF NOT EXISTS public.erp_sources (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    source_system       TEXT NOT NULL,       -- 'primavera_unifier','sap_ps','kahua','ebuilder','ineight','manual'
    source_version      TEXT,                -- API version or module version
    display_name        TEXT,                -- Human-readable label
    connection_config   JSONB DEFAULT '{}',  -- Non-secret config (base URL, project codes)
    last_sync_at        TIMESTAMPTZ,
    sync_status         TEXT DEFAULT 'idle', -- 'idle','syncing','success','error'
    sync_error          TEXT,                -- Last error message (if any)
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_erp_sources_project
    ON public.erp_sources(project_id);

-- ================================================================
-- 2. cbs_elements — Cost Breakdown Structure hierarchy
-- ================================================================
-- Supports MasterFormat (01-49), UniFormat (A-G), OmniClass, and
-- custom coding systems.  Self-referential for arbitrary nesting.

CREATE TABLE IF NOT EXISTS public.cbs_elements (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    erp_source_id       UUID REFERENCES public.erp_sources(id) ON DELETE SET NULL,
    cbs_code            TEXT NOT NULL,
    cbs_description     TEXT,
    cbs_level           INTEGER DEFAULT 1,
    parent_cbs_id       UUID REFERENCES public.cbs_elements(id) ON DELETE SET NULL,
    -- Coding system classification
    coding_system       TEXT DEFAULT 'custom',  -- 'masterformat','uniformat','omniclass','custom'
    masterformat_code   TEXT,               -- MasterFormat division (01-49)
    uniformat_code      TEXT,               -- UniFormat classification (A-G)
    -- Metadata
    sort_order          INTEGER DEFAULT 0,
    is_active           BOOLEAN DEFAULT true,
    -- Data lineage
    source_record_id    TEXT,               -- Original ID in source ERP system
    record_version      INTEGER DEFAULT 1,
    last_sync_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cbs_elements_project
    ON public.cbs_elements(project_id);
CREATE INDEX IF NOT EXISTS idx_cbs_elements_parent
    ON public.cbs_elements(parent_cbs_id);
CREATE INDEX IF NOT EXISTS idx_cbs_elements_code
    ON public.cbs_elements(project_id, cbs_code);

-- ================================================================
-- 3. cost_snapshots — Point-in-time financial data per CBS element
-- ================================================================
-- Each row captures the full financial picture of a CBS element at a
-- specific date.  Unique constraint on (project, CBS, date) prevents
-- duplicate snapshots.
--
-- Terminology follows AACE RP 10S-90 and ANSI/EIA-748 (EVM).

CREATE TABLE IF NOT EXISTS public.cost_snapshots (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id              UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    cbs_element_id          UUID NOT NULL REFERENCES public.cbs_elements(id) ON DELETE CASCADE,
    erp_source_id           UUID REFERENCES public.erp_sources(id) ON DELETE SET NULL,
    snapshot_date           DATE NOT NULL,
    -- Budget (AACE RP 10S-90)
    original_budget         NUMERIC(18,2) DEFAULT 0,  -- BAC before changes
    approved_changes        NUMERIC(18,2) DEFAULT 0,  -- Sum of approved change orders
    current_budget          NUMERIC(18,2) DEFAULT 0,  -- original + approved changes
    management_reserve      NUMERIC(18,2) DEFAULT 0,
    -- Actuals
    committed_cost          NUMERIC(18,2) DEFAULT 0,  -- POs, subcontracts
    actual_cost             NUMERIC(18,2) DEFAULT 0,  -- Invoiced/paid
    -- Forecast
    estimate_to_complete    NUMERIC(18,2) DEFAULT 0,  -- ETC
    estimate_at_completion  NUMERIC(18,2) DEFAULT 0,  -- EAC
    -- Earned Value (ANSI/EIA-748)
    bcws                    NUMERIC(18,2) DEFAULT 0,  -- Planned Value (PV)
    bcwp                    NUMERIC(18,2) DEFAULT 0,  -- Earned Value (EV)
    acwp                    NUMERIC(18,2) DEFAULT 0,  -- Actual Cost (AC)
    -- Contingency & escalation
    contingency_original    NUMERIC(18,2) DEFAULT 0,
    contingency_remaining   NUMERIC(18,2) DEFAULT 0,
    escalation              NUMERIC(18,2) DEFAULT 0,
    -- Data lineage
    source_record_id        TEXT,
    record_version          INTEGER DEFAULT 1,
    created_at              TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT uq_cost_snapshot UNIQUE (project_id, cbs_element_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_cost_snapshots_project
    ON public.cost_snapshots(project_id);
CREATE INDEX IF NOT EXISTS idx_cost_snapshots_cbs
    ON public.cost_snapshots(cbs_element_id);
CREATE INDEX IF NOT EXISTS idx_cost_snapshots_date
    ON public.cost_snapshots(project_id, snapshot_date);

-- ================================================================
-- 4. cost_time_phased — Period-level cost distribution
-- ================================================================
-- Monthly (or custom period) breakdown of budget, actuals, forecast,
-- and commitments.  Supports resource-type segmentation.

CREATE TABLE IF NOT EXISTS public.cost_time_phased (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id              UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    cbs_element_id          UUID NOT NULL REFERENCES public.cbs_elements(id) ON DELETE CASCADE,
    period_start            DATE NOT NULL,
    period_end              DATE NOT NULL,
    -- This-period values
    budget_this_period      NUMERIC(18,2) DEFAULT 0,
    actual_this_period      NUMERIC(18,2) DEFAULT 0,
    forecast_this_period    NUMERIC(18,2) DEFAULT 0,
    committed_this_period   NUMERIC(18,2) DEFAULT 0,
    -- Cumulative values (denormalized for fast queries)
    cumulative_budget       NUMERIC(18,2) DEFAULT 0,
    cumulative_actual       NUMERIC(18,2) DEFAULT 0,
    cumulative_forecast     NUMERIC(18,2) DEFAULT 0,
    -- Resource segmentation
    resource_type           TEXT,            -- 'labor','material','equipment','subcontract','other'
    created_at              TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cost_time_phased_project
    ON public.cost_time_phased(project_id);
CREATE INDEX IF NOT EXISTS idx_cost_time_phased_cbs
    ON public.cost_time_phased(cbs_element_id);
CREATE INDEX IF NOT EXISTS idx_cost_time_phased_period
    ON public.cost_time_phased(project_id, period_start);

-- ================================================================
-- 5. cbs_wbs_mappings — Cost-to-schedule structure linkage
-- ================================================================
-- Maps CBS elements to WBS elements.  Supports split allocations
-- (one CBS element funding multiple WBS elements proportionally).

CREATE TABLE IF NOT EXISTS public.cbs_wbs_mappings (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    cbs_element_id      UUID NOT NULL REFERENCES public.cbs_elements(id) ON DELETE CASCADE,
    wbs_element_id      UUID NOT NULL REFERENCES public.wbs_elements(id) ON DELETE CASCADE,
    allocation_pct      NUMERIC(5,2) DEFAULT 100.00,  -- % of CBS cost allocated to this WBS
    mapping_type        TEXT DEFAULT 'direct',         -- 'direct','proportional','manual'
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cbs_wbs_mappings_project
    ON public.cbs_wbs_mappings(project_id);
CREATE INDEX IF NOT EXISTS idx_cbs_wbs_mappings_cbs
    ON public.cbs_wbs_mappings(cbs_element_id);
CREATE INDEX IF NOT EXISTS idx_cbs_wbs_mappings_wbs
    ON public.cbs_wbs_mappings(wbs_element_id);

-- ================================================================
-- 6. change_orders — Scope/schedule/cost change tracking
-- ================================================================

CREATE TABLE IF NOT EXISTS public.change_orders (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    erp_source_id       UUID REFERENCES public.erp_sources(id) ON DELETE SET NULL,
    change_id           TEXT NOT NULL,           -- External change order number
    change_type         TEXT NOT NULL,           -- 'scope','schedule','cost','combined'
    status              TEXT DEFAULT 'pending',  -- 'pending','approved','rejected','void'
    title               TEXT,
    description         TEXT,
    requested_amount    NUMERIC(18,2) DEFAULT 0,
    approved_amount     NUMERIC(18,2) DEFAULT 0,
    effective_date      DATE,
    submitted_date      DATE,
    approved_date       DATE,
    cbs_element_id      UUID REFERENCES public.cbs_elements(id) ON DELETE SET NULL,
    -- Data lineage
    source_record_id    TEXT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_change_orders_project
    ON public.change_orders(project_id);
CREATE INDEX IF NOT EXISTS idx_change_orders_cbs
    ON public.change_orders(cbs_element_id);
CREATE INDEX IF NOT EXISTS idx_change_orders_status
    ON public.change_orders(project_id, status);

-- ================================================================
-- 7. obs_elements — Organization Breakdown Structure
-- ================================================================
-- Self-referential hierarchy of responsible organizations/departments.

CREATE TABLE IF NOT EXISTS public.obs_elements (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    obs_code            TEXT NOT NULL,
    obs_name            TEXT,
    obs_level           INTEGER DEFAULT 1,
    parent_obs_id       UUID REFERENCES public.obs_elements(id) ON DELETE SET NULL,
    responsible_party   TEXT,
    department          TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_obs_elements_project
    ON public.obs_elements(project_id);
CREATE INDEX IF NOT EXISTS idx_obs_elements_parent
    ON public.obs_elements(parent_obs_id);

-- ================================================================
-- 8. obs_cbs_assignments — OBS-to-CBS responsibility mapping
-- ================================================================
-- Tracks which organization is responsible for which cost element.

CREATE TABLE IF NOT EXISTS public.obs_cbs_assignments (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    obs_element_id      UUID NOT NULL REFERENCES public.obs_elements(id) ON DELETE CASCADE,
    cbs_element_id      UUID NOT NULL REFERENCES public.cbs_elements(id) ON DELETE CASCADE,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_obs_cbs_assignments_project
    ON public.obs_cbs_assignments(project_id);

-- ================================================================
-- 9. RLS Policies — all new tables
-- ================================================================
-- Same pattern as migration 018: project_id ownership check.
-- Service role key bypasses RLS for backend operations.

-- erp_sources
ALTER TABLE public.erp_sources ENABLE ROW LEVEL SECURITY;

CREATE POLICY "erp_sources_select_own" ON public.erp_sources
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "erp_sources_insert_own" ON public.erp_sources
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "erp_sources_delete_own" ON public.erp_sources
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "erp_sources_update_own" ON public.erp_sources
    FOR UPDATE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- cbs_elements
ALTER TABLE public.cbs_elements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "cbs_elements_select_own" ON public.cbs_elements
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "cbs_elements_insert_own" ON public.cbs_elements
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "cbs_elements_delete_own" ON public.cbs_elements
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- cost_snapshots
ALTER TABLE public.cost_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "cost_snapshots_select_own" ON public.cost_snapshots
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "cost_snapshots_insert_own" ON public.cost_snapshots
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "cost_snapshots_delete_own" ON public.cost_snapshots
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- cost_time_phased
ALTER TABLE public.cost_time_phased ENABLE ROW LEVEL SECURITY;

CREATE POLICY "cost_time_phased_select_own" ON public.cost_time_phased
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "cost_time_phased_insert_own" ON public.cost_time_phased
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "cost_time_phased_delete_own" ON public.cost_time_phased
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- cbs_wbs_mappings
ALTER TABLE public.cbs_wbs_mappings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "cbs_wbs_mappings_select_own" ON public.cbs_wbs_mappings
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "cbs_wbs_mappings_insert_own" ON public.cbs_wbs_mappings
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "cbs_wbs_mappings_delete_own" ON public.cbs_wbs_mappings
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- change_orders
ALTER TABLE public.change_orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "change_orders_select_own" ON public.change_orders
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "change_orders_insert_own" ON public.change_orders
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "change_orders_delete_own" ON public.change_orders
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "change_orders_update_own" ON public.change_orders
    FOR UPDATE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- obs_elements
ALTER TABLE public.obs_elements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "obs_elements_select_own" ON public.obs_elements
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "obs_elements_insert_own" ON public.obs_elements
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "obs_elements_delete_own" ON public.obs_elements
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- obs_cbs_assignments
ALTER TABLE public.obs_cbs_assignments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "obs_cbs_assignments_select_own" ON public.obs_cbs_assignments
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "obs_cbs_assignments_insert_own" ON public.obs_cbs_assignments
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );
CREATE POLICY "obs_cbs_assignments_delete_own" ON public.obs_cbs_assignments
    FOR DELETE USING (
        project_id IN (SELECT id FROM public.projects WHERE user_id = auth.uid())
    );

-- ================================================================
-- 10. Reload PostgREST schema cache
-- ================================================================
NOTIFY pgrst, 'reload schema';
