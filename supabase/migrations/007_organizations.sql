-- Migration 007: Organizations, memberships, cross-org sharing, audit trail
-- v1.0 "Enterprise" — hybrid multi-org model
--
-- Model: Each company (Owner, PM, CM, GC) has its own organization.
-- Projects belong to an organization. Projects can be shared across orgs
-- with granular permissions (viewer, editor, admin).
-- Audit trail logs all significant actions for litigation traceability.

-- ================================================================
-- 1. Organizations
-- ================================================================
CREATE TABLE IF NOT EXISTS organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,  -- URL-friendly identifier
    org_type    TEXT DEFAULT 'general', -- owner, pm_firm, cm_firm, general_contractor, subcontractor, general
    description TEXT DEFAULT '',
    logo_url    TEXT,
    created_by  UUID REFERENCES auth.users(id),
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS idx_organizations_created_by ON organizations(created_by);

-- ================================================================
-- 2. Organization Memberships (user ↔ org)
-- ================================================================
CREATE TABLE IF NOT EXISTS memberships (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role        TEXT NOT NULL DEFAULT 'member', -- owner, admin, member, viewer
    invited_by  UUID REFERENCES auth.users(id),
    accepted_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(org_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_org ON memberships(org_id);

-- ================================================================
-- 3. Add org_id to projects and programs
-- ================================================================
ALTER TABLE projects ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);
ALTER TABLE programs ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);

CREATE INDEX IF NOT EXISTS idx_projects_org_id ON projects(org_id);
CREATE INDEX IF NOT EXISTS idx_programs_org_id ON programs(org_id);

-- ================================================================
-- 4. Cross-org project sharing
-- ================================================================
CREATE TABLE IF NOT EXISTS project_shares (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    shared_with_org UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    permission      TEXT NOT NULL DEFAULT 'viewer', -- viewer, editor, admin
    shared_by       UUID REFERENCES auth.users(id),
    expires_at      TIMESTAMPTZ, -- NULL = no expiry
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, shared_with_org)
);

CREATE INDEX IF NOT EXISTS idx_project_shares_project ON project_shares(project_id);
CREATE INDEX IF NOT EXISTS idx_project_shares_org ON project_shares(shared_with_org);

-- Program-level sharing (shares all revisions under a program)
CREATE TABLE IF NOT EXISTS program_shares (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id      UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    shared_with_org UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    permission      TEXT NOT NULL DEFAULT 'viewer',
    shared_by       UUID REFERENCES auth.users(id),
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(program_id, shared_with_org)
);

CREATE INDEX IF NOT EXISTS idx_program_shares_program ON program_shares(program_id);
CREATE INDEX IF NOT EXISTS idx_program_shares_org ON program_shares(shared_with_org);

-- ================================================================
-- 5. Audit Trail
-- ================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID REFERENCES organizations(id),
    user_id     UUID REFERENCES auth.users(id),
    action      TEXT NOT NULL, -- upload, analyze, share, compare, export, delete, invite, etc.
    entity_type TEXT NOT NULL, -- project, program, organization, membership, share
    entity_id   UUID,
    details     JSONB DEFAULT '{}',
    ip_address  TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_org ON audit_log(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);

-- ================================================================
-- 6. RLS Policies
-- ================================================================

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_shares ENABLE ROW LEVEL SECURITY;
ALTER TABLE program_shares ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- Organizations: members can see their orgs
CREATE POLICY "Members can view their organizations"
    ON organizations FOR SELECT
    USING (id IN (SELECT org_id FROM memberships WHERE user_id = auth.uid()));

CREATE POLICY "Anyone can create an organization"
    ON organizations FOR INSERT
    WITH CHECK (created_by = auth.uid());

-- Memberships: members can see co-members
CREATE POLICY "Members can view org memberships"
    ON memberships FOR SELECT
    USING (org_id IN (SELECT org_id FROM memberships m WHERE m.user_id = auth.uid()));

CREATE POLICY "Admins can manage memberships"
    ON memberships FOR INSERT
    WITH CHECK (org_id IN (
        SELECT org_id FROM memberships
        WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
    ));

-- Projects: owner org members + shared org members can see
-- (Update existing policies to include org-based access)
DROP POLICY IF EXISTS "Users can view own projects" ON projects;
CREATE POLICY "Users can view accessible projects"
    ON projects FOR SELECT
    USING (
        -- Own projects (backward compat for pre-org data)
        auth.uid() = user_id
        OR
        -- Projects in user's org
        org_id IN (SELECT org_id FROM memberships WHERE user_id = auth.uid())
        OR
        -- Projects shared with user's org
        id IN (
            SELECT ps.project_id FROM project_shares ps
            JOIN memberships m ON m.org_id = ps.shared_with_org
            WHERE m.user_id = auth.uid()
            AND (ps.expires_at IS NULL OR ps.expires_at > now())
        )
    );

DROP POLICY IF EXISTS "Users can insert own projects" ON projects;
CREATE POLICY "Users can insert projects"
    ON projects FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Project shares: viewable by source and target org members
CREATE POLICY "Org members can view shares"
    ON project_shares FOR SELECT
    USING (
        shared_with_org IN (SELECT org_id FROM memberships WHERE user_id = auth.uid())
        OR project_id IN (
            SELECT id FROM projects WHERE org_id IN (
                SELECT org_id FROM memberships WHERE user_id = auth.uid()
            )
        )
    );

-- Audit log: org members can view their org's logs
CREATE POLICY "Members can view org audit log"
    ON audit_log FOR SELECT
    USING (org_id IN (SELECT org_id FROM memberships WHERE user_id = auth.uid()));

-- Service role inserts audit log entries
-- (service_role bypasses RLS by default)

-- ================================================================
-- 7. Auto-create personal org on first signup
-- ================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user_org()
RETURNS TRIGGER AS $$
DECLARE
    new_org_id UUID;
    user_name TEXT;
    user_slug TEXT;
BEGIN
    user_name := COALESCE(
        NEW.raw_user_meta_data->>'full_name',
        NEW.raw_user_meta_data->>'name',
        split_part(NEW.email, '@', 1)
    );
    user_slug := lower(regexp_replace(user_name, '[^a-zA-Z0-9]', '-', 'g')) || '-' || substr(NEW.id::text, 1, 8);

    INSERT INTO organizations (name, slug, org_type, created_by)
    VALUES (user_name || '''s Workspace', user_slug, 'general', NEW.id)
    RETURNING id INTO new_org_id;

    INSERT INTO memberships (org_id, user_id, role, accepted_at)
    VALUES (new_org_id, NEW.id, 'owner', now());

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created_org ON auth.users;
CREATE TRIGGER on_auth_user_created_org
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user_org();
