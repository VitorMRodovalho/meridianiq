-- Migration 036: requests for AI access
--
-- The AI assistant is enabled per account by the operator's approval
-- (migration 035). This migration lets a signed-in user ask for it, and the
-- operator approve or dismiss the request.
--
-- 1. public.ai_access_requests: at most one row per account.
--      pending   -> waiting for the operator
--      approved  -> the operator granted access (any grant closes a pending
--                   request, see ai_grant below)
--      dismissed -> the operator declined it, or the user's data erasure
--                   withdrew a pending request (decided_by NULL)
--    The note (the user's optional reason) is cleared when the request is
--    decided: the operator reads it while it is pending, and nothing keeps it
--    afterwards.
-- 2. A new request is blocked for 30 days after a dismissal, and for 30
--    days after any revocation of access (whether or not it came from a
--    request): ai_request_cooldown_until. An account with active access
--    cannot ask.
-- 3. ai_request_access decides "created" in one statement
--    (INSERT ... SELECT ... WHERE ... ON CONFLICT ... DO UPDATE ... WHERE),
--    and the conflict condition reads the locked row's own columns, so
--    concurrent requests create one request and one notification, and a
--    dismissal or approval committed meanwhile is not undone.
-- 4. private.ai_pending_requests is the ONLY function that runs with its
--    owner's rights (SECURITY DEFINER): it reads the confirmed address of
--    pending requesters from auth.users, which service_role cannot read. It
--    is read-only (sql, STABLE), owned by postgres, returns PENDING
--    requesters only, and lives in schema private (not exposed by PostgREST;
--    only service_role has USAGE). public.ai_pending_requests is a plain
--    wrapper around it: a client role that somehow got EXECUTE on the wrapper
--    would still be stopped at schema private. The guard at the end aborts
--    the migration if any of this does not hold.
-- 5. ai_grant (migration 035) is replaced with the identical signature and
--    body plus one statement that closes a pending request. Re-applying 035
--    after 036 would silently drop that statement: apply 036 again after it
--    (scripts/rls_replica/036/postcheck.sql detects it).
-- 6. ai_forget_user supports the user's own data erasure: it clears the
--    request's note, withdraws a pending request (it becomes dismissed, so
--    the operator no longer sees it) and clears the address copied onto the
--    entitlement. The row's status and dates stay, as the record that keeps
--    the 30-day block: deleting it would let an account re-open requests
--    (and email the operator) at will. Deleting the account removes the row
--    (ON DELETE CASCADE). The spend ledger (035) keeps its pseudonymous rows.
--
-- Access: RLS on, nothing for client roles, service_role SELECT/INSERT/UPDATE
-- only (no DELETE: nothing in the API deletes a request); every function
-- executable by service_role only.
--
-- Apply BEFORE deploying the API that calls these functions; without them
-- the request routes answer ai_request_unavailable and /ai/status leaves the
-- request fields empty.
--
-- Idempotent: CREATE ... IF NOT EXISTS, CREATE OR REPLACE, REVOKE/GRANT
-- converge. Single transaction with a 5 s lock_timeout.

BEGIN;

SET LOCAL lock_timeout = '5s';

-- ================================================================
-- 1. Table
-- ================================================================

CREATE TABLE IF NOT EXISTS public.ai_access_requests (
    user_id      uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
    status       text NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'approved', 'dismissed')),
    note         text CHECK (note IS NULL OR char_length(note) <= 500),
    requested_at timestamptz NOT NULL DEFAULT now(),
    decided_at   timestamptz,
    decided_by   uuid,
    CHECK ((status = 'pending') = (decided_at IS NULL))
);

CREATE INDEX IF NOT EXISTS idx_ai_access_requests_pending
    ON public.ai_access_requests (requested_at) WHERE status = 'pending';

ALTER TABLE public.ai_access_requests ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.ai_access_requests FROM PUBLIC, anon, authenticated;
REVOKE ALL ON TABLE public.ai_access_requests FROM service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE public.ai_access_requests TO service_role;

-- ================================================================
-- 2. Functions
-- ================================================================

-- Until when a new request is blocked, or NULL if it is not: 30 days after
-- a dismissal, and 30 days after any revocation of access, whichever ends
-- later. Access that is active is not a block here; that case is "entitled".
CREATE OR REPLACE FUNCTION public.ai_request_cooldown_until(p_user_id uuid)
RETURNS timestamptz
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
    SELECT blocked_until
      FROM (
            SELECT greatest(
                       (SELECT r.decided_at
                          FROM public.ai_access_requests AS r
                         WHERE r.user_id = p_user_id AND r.status = 'dismissed'),
                       (SELECT e.revoked_at
                          FROM public.ai_entitlements AS e
                         WHERE e.user_id = p_user_id AND e.revoked_at IS NOT NULL)
                   ) + interval '30 days' AS blocked_until
           ) AS c
     WHERE c.blocked_until > now();
$$;

-- The caller's own request state: entitled | pending | dismissed | none.
-- requested_at only when pending; retry_after only when dismissed.
CREATE OR REPLACE FUNCTION public.ai_access_state(p_user_id uuid)
RETURNS TABLE (state text, requested_at timestamptz, retry_after timestamptz)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
    WITH s AS (
        SELECT EXISTS (SELECT 1 FROM public.ai_entitlements AS e
                        WHERE e.user_id = p_user_id AND e.revoked_at IS NULL) AS entitled,
               (SELECT r.status FROM public.ai_access_requests AS r
                 WHERE r.user_id = p_user_id) AS status,
               (SELECT r.requested_at FROM public.ai_access_requests AS r
                 WHERE r.user_id = p_user_id) AS requested,
               public.ai_request_cooldown_until(p_user_id) AS blocked_until
    )
    SELECT CASE WHEN s.entitled THEN 'entitled'
                WHEN s.status = 'pending' THEN 'pending'
                WHEN s.blocked_until IS NOT NULL THEN 'dismissed'
                ELSE 'none' END,
           CASE WHEN NOT s.entitled AND s.status = 'pending' THEN s.requested END,
           CASE WHEN NOT s.entitled AND s.status IS DISTINCT FROM 'pending' THEN s.blocked_until END
      FROM s;
$$;

-- Ask for access. outcome: created (a new pending request: notify the
-- operator), pending (already waiting; the note is updated when given,
-- requested_at is not), entitled (access is active), dismissed (blocked
-- until retry_after).
CREATE OR REPLACE FUNCTION public.ai_request_access(p_user_id uuid, p_note text)
RETURNS TABLE (outcome text, requested_at timestamptz, retry_after timestamptz)
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
SET search_path = ''
AS $$
#variable_conflict use_column
DECLARE
    v_at timestamptz;
    v_status text;
BEGIN
    -- One statement decides. The SELECT's conditions cover an account with no
    -- row yet; on a conflict the DO UPDATE condition is re-checked against the
    -- locked row's latest version, so a dismissal or approval committed while
    -- this runs is not undone, and of concurrent callers exactly one wins.
    INSERT INTO public.ai_access_requests AS r (user_id, status, note, requested_at)
    SELECT p_user_id, 'pending', p_note, now()
     WHERE NOT EXISTS (SELECT 1 FROM public.ai_entitlements AS e
                        WHERE e.user_id = p_user_id AND e.revoked_at IS NULL)
       AND public.ai_request_cooldown_until(p_user_id) IS NULL
    ON CONFLICT (user_id) DO UPDATE
       SET status = 'pending',
           note = EXCLUDED.note,
           requested_at = EXCLUDED.requested_at,
           decided_at = NULL,
           decided_by = NULL
     WHERE r.status <> 'pending'
       AND r.decided_at <= now() - interval '30 days'
    RETURNING r.requested_at INTO v_at;
    IF FOUND THEN
        RETURN QUERY SELECT 'created'::text, v_at, NULL::timestamptz;
        RETURN;
    END IF;

    IF EXISTS (SELECT 1 FROM public.ai_entitlements AS e
                WHERE e.user_id = p_user_id AND e.revoked_at IS NULL) THEN
        RETURN QUERY SELECT 'entitled'::text, NULL::timestamptz, NULL::timestamptz;
        RETURN;
    END IF;
    SELECT r.status, r.requested_at INTO v_status, v_at
      FROM public.ai_access_requests AS r
     WHERE r.user_id = p_user_id;
    IF v_status = 'pending' THEN
        IF p_note IS NOT NULL THEN
            UPDATE public.ai_access_requests AS r
               SET note = p_note
             WHERE r.user_id = p_user_id AND r.status = 'pending';
        END IF;
        RETURN QUERY SELECT 'pending'::text, v_at, NULL::timestamptz;
        RETURN;
    END IF;
    RETURN QUERY SELECT 'dismissed'::text, NULL::timestamptz,
                        public.ai_request_cooldown_until(p_user_id);
END
$$;

-- Pending requests with each requester's confirmed address, oldest first.
-- The one SECURITY DEFINER function: see the header. p_user_id narrows it to
-- one pending requester (the approve path).
CREATE OR REPLACE FUNCTION private.ai_pending_requests(
    p_user_id uuid DEFAULT NULL,
    p_limit integer DEFAULT 200
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    WITH pending AS (
        SELECT r.user_id, r.note, r.requested_at
          FROM public.ai_access_requests AS r
         WHERE r.status = 'pending'
           AND (p_user_id IS NULL OR r.user_id = p_user_id)
    ),
    page AS (
        SELECT p.user_id, p.note, p.requested_at
          FROM pending AS p
         ORDER BY p.requested_at, p.user_id
         LIMIT greatest(least(coalesce(p_limit, 200), 500), 0)
    )
    SELECT jsonb_build_object(
        'total', (SELECT count(*) FROM pending),
        'items', coalesce((
            SELECT jsonb_agg(jsonb_build_object('user_id', g.user_id,
                                                'email', u.email,
                                                'note', g.note,
                                                'requested_at', g.requested_at)
                             ORDER BY g.requested_at, g.user_id)
              FROM page AS g
              LEFT JOIN auth.users AS u
                ON u.id = g.user_id
               AND u.deleted_at IS NULL
               AND u.email_confirmed_at IS NOT NULL
        ), '[]'::jsonb)
    );
$$;

ALTER FUNCTION private.ai_pending_requests(uuid, integer) OWNER TO postgres;

-- The API's entry point (PostgREST exposes public only): a plain wrapper.
CREATE OR REPLACE FUNCTION public.ai_pending_requests(
    p_user_id uuid DEFAULT NULL,
    p_limit integer DEFAULT 200
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
    SELECT private.ai_pending_requests(p_user_id, p_limit);
$$;

-- Approve a pending request: grant the default limits (ai_grant, which also
-- writes the audit row) in the same transaction. False when it is not pending.
CREATE OR REPLACE FUNCTION public.ai_approve_request(
    p_user_id uuid,
    p_approved_by uuid,
    p_ip_address text,
    p_user_agent text
)
RETURNS boolean
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
    v_email text;
BEGIN
    v_email := private.ai_pending_requests(p_user_id, 1) -> 'items' -> 0 ->> 'email';
    UPDATE public.ai_access_requests AS r
       SET status = 'approved', decided_at = now(), decided_by = p_approved_by, note = NULL
     WHERE r.user_id = p_user_id AND r.status = 'pending';
    IF NOT FOUND THEN
        RETURN false;
    END IF;
    -- Access already active (granted from the form meanwhile): keep its
    -- limits and note; the request is closed, audited, and nothing else
    -- changes.
    IF EXISTS (SELECT 1 FROM public.ai_entitlements AS e
                WHERE e.user_id = p_user_id AND e.revoked_at IS NULL) THEN
        INSERT INTO public.audit_log (user_id, action, entity_type, entity_id, details,
                                      ip_address, user_agent)
        VALUES (p_approved_by, 'ai_access_request_approved', 'ai_access_request', p_user_id,
                '{}'::jsonb, p_ip_address, p_user_agent);
        RETURN true;
    END IF;
    PERFORM public.ai_grant(p_user_id, v_email, p_approved_by, NULL, NULL, NULL,
                            p_ip_address, p_user_agent);
    RETURN true;
END
$$;

-- Dismiss a pending request and audit it. False when it is not pending.
CREATE OR REPLACE FUNCTION public.ai_dismiss_request(
    p_user_id uuid,
    p_dismissed_by uuid,
    p_ip_address text,
    p_user_agent text
)
RETURNS boolean
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
    UPDATE public.ai_access_requests AS r
       SET status = 'dismissed', decided_at = now(), decided_by = p_dismissed_by, note = NULL
     WHERE r.user_id = p_user_id AND r.status = 'pending';
    IF NOT FOUND THEN
        RETURN false;
    END IF;
    INSERT INTO public.audit_log (user_id, action, entity_type, entity_id, details,
                                  ip_address, user_agent)
    VALUES (p_dismissed_by, 'ai_access_request_dismissed', 'ai_access_request', p_user_id,
            '{}'::jsonb, p_ip_address, p_user_agent);
    RETURN true;
END
$$;

-- The user's own data erasure: clear the request's note, withdraw a pending
-- request (dismissed, decided_by NULL, which starts the 30-day block) and
-- clear the address copied onto the entitlement. The row's status and dates,
-- access itself and the pseudonymous spend ledger stay (see the header).
CREATE OR REPLACE FUNCTION public.ai_forget_user(p_user_id uuid)
RETURNS void
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
    UPDATE public.ai_access_requests AS r
       SET status = CASE WHEN r.status = 'pending' THEN 'dismissed' ELSE r.status END,
           decided_at = coalesce(r.decided_at, now()),
           note = NULL
     WHERE r.user_id = p_user_id;
    UPDATE public.ai_entitlements AS e SET email = NULL WHERE e.user_id = p_user_id;
END
$$;

-- Migration 035's ai_grant, identical signature and statements, plus the
-- last UPDATE: any grant (from a request or from the operator's form) closes
-- the account's pending request.
CREATE OR REPLACE FUNCTION public.ai_grant(
    p_user_id uuid,
    p_email text,
    p_granted_by uuid,
    p_daily_questions integer,
    p_monthly_budget_usd numeric,
    p_note text,
    p_ip_address text,
    p_user_agent text
)
RETURNS void
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
    INSERT INTO public.ai_entitlements (user_id, email, granted_by, granted_at, revoked_at,
                                        revoked_by, daily_questions, monthly_budget_usd, note)
    VALUES (p_user_id, p_email, p_granted_by, now(), NULL, NULL, p_daily_questions,
            p_monthly_budget_usd, p_note)
    ON CONFLICT (user_id) DO UPDATE
       SET email = EXCLUDED.email,
           granted_by = EXCLUDED.granted_by,
           granted_at = EXCLUDED.granted_at,
           revoked_at = NULL,
           revoked_by = NULL,
           daily_questions = EXCLUDED.daily_questions,
           monthly_budget_usd = EXCLUDED.monthly_budget_usd,
           note = EXCLUDED.note;

    INSERT INTO public.audit_log (user_id, action, entity_type, entity_id, details,
                                  ip_address, user_agent)
    VALUES (p_granted_by, 'ai_access_granted', 'ai_entitlement', p_user_id,
            jsonb_build_object('daily_questions', p_daily_questions,
                               'monthly_budget_usd', p_monthly_budget_usd::text),
            p_ip_address, p_user_agent);

    UPDATE public.ai_access_requests AS r
       SET status = 'approved', decided_at = now(), decided_by = p_granted_by, note = NULL
     WHERE r.user_id = p_user_id AND r.status = 'pending';
END
$$;

-- ================================================================
-- 3. Privileges
-- ================================================================

REVOKE ALL ON FUNCTION public.ai_request_cooldown_until(uuid) FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.ai_access_state(uuid) FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.ai_request_access(uuid, text) FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION private.ai_pending_requests(uuid, integer) FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.ai_pending_requests(uuid, integer) FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.ai_forget_user(uuid) FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.ai_approve_request(uuid, uuid, text, text) FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.ai_dismiss_request(uuid, uuid, text, text) FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.ai_grant(uuid, text, uuid, integer, numeric, text, text, text)
    FROM PUBLIC, anon, authenticated, service_role;

GRANT EXECUTE ON FUNCTION public.ai_request_cooldown_until(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.ai_access_state(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.ai_request_access(uuid, text) TO service_role;
GRANT USAGE ON SCHEMA private TO service_role;
GRANT EXECUTE ON FUNCTION private.ai_pending_requests(uuid, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.ai_pending_requests(uuid, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.ai_forget_user(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.ai_approve_request(uuid, uuid, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.ai_dismiss_request(uuid, uuid, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.ai_grant(uuid, text, uuid, integer, numeric, text, text, text)
    TO service_role;

-- ================================================================
-- 4. Guard: abort unless every ai_* function in public is owned by postgres,
--    runs with its caller's rights and is not callable by a client role, and
--    private.ai_pending_requests is the one definer, owned by postgres, not
--    callable by a client role, in a schema client roles cannot use.
-- ================================================================

DO $$
DECLARE
    v_bad text;
    v_definer regprocedure := 'private.ai_pending_requests(uuid, integer)'::regprocedure;
BEGIN
    SELECT string_agg(format('%s(%s)', p.proname, pg_get_function_identity_arguments(p.oid)), ', ')
      INTO v_bad
      FROM pg_proc AS p
     WHERE p.pronamespace = 'public'::regnamespace
       AND p.proname LIKE 'ai\_%'
       AND (has_function_privilege('anon', p.oid, 'EXECUTE')
            OR has_function_privilege('authenticated', p.oid, 'EXECUTE')
            OR pg_get_userbyid(p.proowner) <> 'postgres'
            OR p.prosecdef);
    IF v_bad IS NOT NULL THEN
        RAISE EXCEPTION 'migration 036: unsafe ai_* functions in public: %', v_bad;
    END IF;

    IF (SELECT pg_get_userbyid(p.proowner) FROM pg_proc AS p WHERE p.oid = v_definer) <> 'postgres'
       OR NOT (SELECT p.prosecdef FROM pg_proc AS p WHERE p.oid = v_definer)
       OR has_function_privilege('anon', v_definer, 'EXECUTE')
       OR has_function_privilege('authenticated', v_definer, 'EXECUTE')
       OR has_schema_privilege('anon', 'private', 'USAGE')
       OR has_schema_privilege('authenticated', 'private', 'USAGE') THEN
        RAISE EXCEPTION 'migration 036: private.ai_pending_requests is not safely owned and confined';
    END IF;
END
$$;

-- Make the new functions visible to PostgREST (delivered at COMMIT).
NOTIFY pgrst, 'reload schema';

COMMIT;
