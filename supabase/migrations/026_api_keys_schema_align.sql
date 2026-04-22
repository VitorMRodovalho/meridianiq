-- Migration 026: reconcile any legacy 012-style ``api_keys`` schema to the
-- canonical 017 shape.  Idempotent — safe to re-run on both fresh installs
-- (where 017's schema is already live) and legacy installs (where 012 was
-- applied first and 017's ``CREATE TABLE IF NOT EXISTS`` became a no-op).
--
-- See ADR-0017 for the decision context.  Audit AUDIT-001 (P0), issue #16.

-- ─────────────────────────────────────────────────────────────────
-- 1. Drop the 012-era policies if they still exist.
--    017's canonical policies are api_keys_select / _insert / _delete.
-- ─────────────────────────────────────────────────────────────────

DROP POLICY IF EXISTS "Users see own keys"    ON api_keys;
DROP POLICY IF EXISTS "Users insert own keys" ON api_keys;
DROP POLICY IF EXISTS "Users update own keys" ON api_keys;

-- ─────────────────────────────────────────────────────────────────
-- 2. Ensure ``key_id`` column exists (017 canonical).  Backfill any
--    legacy rows from ``id::text`` so the UNIQUE constraint is safe.
-- ─────────────────────────────────────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'api_keys' AND column_name = 'key_id'
    ) THEN
        ALTER TABLE api_keys ADD COLUMN key_id TEXT;
        UPDATE api_keys SET key_id = 'legacy_' || id::text WHERE key_id IS NULL;
        ALTER TABLE api_keys ALTER COLUMN key_id SET NOT NULL;
        BEGIN
            ALTER TABLE api_keys ADD CONSTRAINT api_keys_key_id_key UNIQUE (key_id);
        EXCEPTION WHEN duplicate_object THEN
            -- constraint already exists under a different name; leave it alone
            NULL;
        END;
    END IF;
END$$;

-- ─────────────────────────────────────────────────────────────────
-- 3. Ensure ``revoked_at`` exists (017 canonical).  If the legacy
--    ``is_active`` flag is present, translate is_active=FALSE rows
--    to revoked_at = now() before dropping is_active.
-- ─────────────────────────────────────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'api_keys' AND column_name = 'revoked_at'
    ) THEN
        ALTER TABLE api_keys ADD COLUMN revoked_at TIMESTAMPTZ;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'api_keys' AND column_name = 'is_active'
    ) THEN
        UPDATE api_keys
           SET revoked_at = COALESCE(revoked_at, now())
         WHERE is_active = FALSE AND revoked_at IS NULL;
        ALTER TABLE api_keys DROP COLUMN is_active;
    END IF;
END$$;

-- ─────────────────────────────────────────────────────────────────
-- 4. Drop unused 012-era columns if they exist.
-- ─────────────────────────────────────────────────────────────────

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'api_keys' AND column_name = 'key_prefix'
    ) THEN
        ALTER TABLE api_keys DROP COLUMN key_prefix;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'api_keys' AND column_name = 'expires_at'
    ) THEN
        ALTER TABLE api_keys DROP COLUMN expires_at;
    END IF;
END$$;

-- ─────────────────────────────────────────────────────────────────
-- 5. Reassert the canonical 017 policies (harmless if already present).
-- ─────────────────────────────────────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'api_keys'
          AND policyname = 'api_keys_select'
    ) THEN
        CREATE POLICY api_keys_select ON api_keys
            FOR SELECT USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'api_keys'
          AND policyname = 'api_keys_insert'
    ) THEN
        CREATE POLICY api_keys_insert ON api_keys
            FOR INSERT WITH CHECK (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'api_keys'
          AND policyname = 'api_keys_delete'
    ) THEN
        CREATE POLICY api_keys_delete ON api_keys
            FOR DELETE USING (auth.uid() = user_id);
    END IF;
END$$;

COMMENT ON TABLE api_keys IS
    'Persistent API key storage with RLS — canonical schema via 017 + 026 (ADR-0017)';
