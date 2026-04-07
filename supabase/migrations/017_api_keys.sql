-- Migration 017: API keys persistence table
-- Moves API key storage from in-memory to Supabase for durability.

CREATE TABLE IF NOT EXISTS api_keys (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key_id TEXT NOT NULL UNIQUE,
    key_hash TEXT NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'default',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

-- Index for fast key validation lookups
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);

-- RLS: users can only see/manage their own keys
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY api_keys_select ON api_keys
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY api_keys_insert ON api_keys
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY api_keys_delete ON api_keys
    FOR DELETE USING (auth.uid() = user_id);

COMMENT ON TABLE api_keys IS 'Persistent API key storage with RLS — migration 017';
