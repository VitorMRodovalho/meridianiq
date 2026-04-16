-- Migration 020: Add program_id, revision_number, storage_path to projects table
-- These columns were added to the SupabaseStore.save_project() in v3.5 but
-- the corresponding schema migration was missing.

ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS program_id UUID REFERENCES public.programs(id);
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS revision_number INTEGER;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS storage_path TEXT DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_projects_program_id ON public.projects(program_id);
