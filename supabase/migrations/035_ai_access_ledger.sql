-- Migration 035: AI access entitlements and a spend ledger
--
-- The AI feature ("Ask Your Schedule") calls a paid LLM API. It is available
-- only to accounts the operator approves, within per-account and global
-- limits (owner decision, 2026-09-27). This migration stores both halves:
--
-- 1. public.ai_entitlements: one row per approved account. Active while
--    revoked_at IS NULL. daily_questions / monthly_budget_usd override the
--    API's defaults when set. email is the address given at grant time, kept
--    for display only (identity is user_id).
-- 2. public.ai_usage: one row per LLM call, written BEFORE the call as a
--    reservation of its worst-case cost and settled after it:
--      reserved  -> call in flight (or the process died): counts at reserved_usd
--      completed -> real cost from the provider's usage
--      failed    -> the provider refused before generating: counts 0
--      unknown   -> timeout / connection loss: counts at reserved_usd
--    Every row carries the model and both prices it was costed with.
--    user_id and project_id have NO foreign key: deleting an account's data
--    (delete_user_data) must not erase the ledger and hand the quota back.
-- 3. public.ai_quota / ai_reserve / ai_settle / ai_admin_report: the only
--    place the limits are computed. ai_grant / ai_revoke change an
--    entitlement and write its audit_log row in the same transaction. Windows are UTC calendar day and month.
--    ai_reserve serialises every reservation on one transaction-level
--    advisory lock taken as its own statement, so the sums it reads include
--    every reservation committed before it (READ COMMITTED takes a fresh
--    snapshot per statement) and concurrent callers cannot all pass the same
--    remaining budget.
--
-- Access: RLS on with no policies, every privilege revoked from the client
-- roles, and the functions executable by service_role only (the API). The
-- functions are SECURITY INVOKER: service_role bypasses RLS and holds the
-- table privileges granted below, which are SELECT, INSERT and UPDATE only:
-- nothing in the API deletes from the ledger or the grants (a revoke is a
-- soft update), so DELETE and TRUNCATE are withheld even from service_role. Supabase's default privileges grant
-- EXECUTE on new functions to anon and authenticated, hence the explicit
-- REVOKEs (see migration 030).
--
-- Apply BEFORE deploying the API that calls these functions: without them
-- the AI routes report the feature as unavailable (fail closed).
--
-- Idempotent: CREATE ... IF NOT EXISTS, CREATE OR REPLACE, and REVOKE/GRANT
-- converge. Single transaction with a 5 s lock_timeout.

BEGIN;

SET LOCAL lock_timeout = '5s';

-- ================================================================
-- 1. Tables
-- ================================================================

CREATE TABLE IF NOT EXISTS public.ai_entitlements (
    user_id            uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
    email              text,
    granted_by         uuid,
    granted_at         timestamptz NOT NULL DEFAULT now(),
    revoked_at         timestamptz,
    revoked_by         uuid,
    daily_questions    integer CHECK (daily_questions IS NULL OR daily_questions >= 0),
    monthly_budget_usd numeric(12, 6) CHECK (monthly_budget_usd IS NULL OR monthly_budget_usd >= 0),
    note               text CHECK (note IS NULL OR length(note) <= 500)
);

CREATE TABLE IF NOT EXISTS public.ai_usage (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id          uuid NOT NULL,
    project_id       uuid,
    created_at       timestamptz NOT NULL DEFAULT now(),
    settled_at       timestamptz,
    status           text NOT NULL DEFAULT 'reserved'
                     CHECK (status IN ('reserved', 'completed', 'failed', 'unknown')),
    model            text NOT NULL,
    price_input_usd_per_mtok  numeric(12, 6) NOT NULL CHECK (price_input_usd_per_mtok > 0),
    price_output_usd_per_mtok numeric(12, 6) NOT NULL CHECK (price_output_usd_per_mtok > 0),
    reserved_usd     numeric(12, 6) NOT NULL CHECK (reserved_usd > 0),
    input_tokens     integer CHECK (input_tokens IS NULL OR input_tokens >= 0),
    output_tokens    integer CHECK (output_tokens IS NULL OR output_tokens >= 0),
    cost_usd         numeric(12, 6) CHECK (cost_usd IS NULL OR cost_usd >= 0),
    CHECK (status <> 'completed' OR cost_usd IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_user_created ON public.ai_usage (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_usage_created ON public.ai_usage (created_at);

ALTER TABLE public.ai_entitlements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_usage ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.ai_entitlements, public.ai_usage FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE public.ai_usage_id_seq FROM PUBLIC, anon, authenticated;
REVOKE ALL ON TABLE public.ai_entitlements, public.ai_usage FROM service_role;

GRANT SELECT, INSERT, UPDATE ON TABLE public.ai_entitlements TO service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE public.ai_usage TO service_role;
GRANT USAGE ON SEQUENCE public.ai_usage_id_seq TO service_role;

-- ================================================================
-- 2. Limits
-- ================================================================

-- What one account has used in the current UTC day and month, and what all
-- accounts have spent this UTC month. Money is returned as text so it
-- crosses PostgREST and supabase-py without a float.
CREATE OR REPLACE FUNCTION public.ai_quota(
    p_user_id uuid,
    p_default_daily integer,
    p_default_account_usd numeric
)
RETURNS TABLE (
    entitled boolean,
    daily_limit integer,
    used_today integer,
    account_budget_usd text,
    account_spent_usd text,
    global_spent_usd text
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
    WITH ent AS (
        SELECT e.daily_questions, e.monthly_budget_usd
          FROM public.ai_entitlements AS e
         WHERE e.user_id = p_user_id
           AND e.revoked_at IS NULL
    ),
    mine AS (
        SELECT
            count(*) FILTER (WHERE u.status <> 'failed'
                               AND u.created_at >= date_trunc('day', now(), 'UTC')) AS used_today,
            coalesce(sum(CASE u.status WHEN 'completed' THEN u.cost_usd
                                       WHEN 'failed' THEN 0
                                       ELSE u.reserved_usd END), 0) AS spent_month
          FROM public.ai_usage AS u
         WHERE u.user_id = p_user_id
           AND u.created_at >= date_trunc('month', now(), 'UTC')
    ),
    everyone AS (
        SELECT coalesce(sum(CASE u.status WHEN 'completed' THEN u.cost_usd
                                          WHEN 'failed' THEN 0
                                          ELSE u.reserved_usd END), 0) AS spent_month
          FROM public.ai_usage AS u
         WHERE u.created_at >= date_trunc('month', now(), 'UTC')
    )
    SELECT EXISTS (SELECT 1 FROM ent),
           coalesce((SELECT daily_questions FROM ent), p_default_daily),
           (SELECT used_today FROM mine)::integer,
           coalesce((SELECT monthly_budget_usd FROM ent), p_default_account_usd)::text,
           (SELECT spent_month FROM mine)::text,
           (SELECT spent_month FROM everyone)::text;
$$;

-- Reserve the worst-case cost of one call, or say why not. Checks, in order:
-- active entitlement, daily questions, account month budget, global month
-- budget. Returns (reservation_id, NULL) or (NULL, reason).
CREATE OR REPLACE FUNCTION public.ai_reserve(
    p_user_id uuid,
    p_project_id uuid,
    p_reserve_usd numeric,
    p_default_daily integer,
    p_default_account_usd numeric,
    p_global_budget_usd numeric,
    p_model text,
    p_price_input numeric,
    p_price_output numeric
)
RETURNS TABLE (reservation_id bigint, reason text)
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
    v_q record;
    v_id bigint;
BEGIN
    IF p_reserve_usd IS NULL OR p_reserve_usd <= 0
       OR p_global_budget_usd IS NULL OR p_global_budget_usd <= 0 THEN
        RAISE EXCEPTION 'ai_reserve: reserve and global budget must be positive';
    END IF;

    -- Its own statement, before any read below: every later statement sees
    -- the reservations committed by whoever held the lock before.
    PERFORM pg_advisory_xact_lock(hashtext('meridianiq'), hashtext('ai_budget'));

    SELECT * INTO v_q
      FROM public.ai_quota(p_user_id, p_default_daily, p_default_account_usd);

    IF NOT v_q.entitled THEN
        RETURN QUERY SELECT NULL::bigint, 'ai_not_entitled'::text;
        RETURN;
    END IF;
    IF v_q.used_today >= v_q.daily_limit THEN
        RETURN QUERY SELECT NULL::bigint, 'ai_daily_quota'::text;
        RETURN;
    END IF;
    IF v_q.account_spent_usd::numeric + p_reserve_usd > v_q.account_budget_usd::numeric THEN
        RETURN QUERY SELECT NULL::bigint, 'ai_account_budget'::text;
        RETURN;
    END IF;
    IF v_q.global_spent_usd::numeric + p_reserve_usd > p_global_budget_usd THEN
        RETURN QUERY SELECT NULL::bigint, 'ai_global_budget'::text;
        RETURN;
    END IF;

    INSERT INTO public.ai_usage (user_id, project_id, model, price_input_usd_per_mtok,
                                 price_output_usd_per_mtok, reserved_usd)
    VALUES (p_user_id, p_project_id, p_model, p_price_input, p_price_output, p_reserve_usd)
    RETURNING id INTO v_id;

    RETURN QUERY SELECT v_id, NULL::text;
END
$$;

-- Settle a reservation once. Returns true if it was still reserved.
CREATE OR REPLACE FUNCTION public.ai_settle(
    p_reservation_id bigint,
    p_status text,
    p_input_tokens integer,
    p_output_tokens integer,
    p_cost_usd numeric
)
RETURNS boolean
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
    IF p_status NOT IN ('completed', 'failed', 'unknown') THEN
        RAISE EXCEPTION 'ai_settle: invalid status %', p_status;
    END IF;
    UPDATE public.ai_usage
       SET status = p_status,
           settled_at = now(),
           input_tokens = p_input_tokens,
           output_tokens = p_output_tokens,
           cost_usd = p_cost_usd
     WHERE id = p_reservation_id
       AND status = 'reserved';
    RETURN FOUND;
END
$$;

-- Grant (or re-grant, replacing the limits) AI access, and audit it, in one
-- transaction. Re-granting reactivates a revoked entitlement.
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
END
$$;

-- Revoke an active entitlement and audit it. Returns false when none was active.
CREATE OR REPLACE FUNCTION public.ai_revoke(
    p_user_id uuid,
    p_revoked_by uuid,
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
    UPDATE public.ai_entitlements
       SET revoked_at = now(),
           revoked_by = p_revoked_by
     WHERE user_id = p_user_id
       AND revoked_at IS NULL;
    IF NOT FOUND THEN
        RETURN false;
    END IF;

    INSERT INTO public.audit_log (user_id, action, entity_type, entity_id, details,
                                  ip_address, user_agent)
    VALUES (p_revoked_by, 'ai_access_revoked', 'ai_entitlement', p_user_id, '{}'::jsonb,
            p_ip_address, p_user_agent);
    RETURN true;
END
$$;

-- Operator view: this month's global spend and calls by outcome, the last
-- failed or unknown call, reservations left unsettled for more than 10
-- minutes, and every entitlement with its usage.
CREATE OR REPLACE FUNCTION public.ai_admin_report(
    p_default_daily integer,
    p_default_account_usd numeric
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
    SELECT jsonb_build_object(
        'global_spent_month_usd',
        (SELECT coalesce(sum(CASE u.status WHEN 'completed' THEN u.cost_usd
                                           WHEN 'failed' THEN 0
                                           ELSE u.reserved_usd END), 0)::text
           FROM public.ai_usage AS u
          WHERE u.created_at >= date_trunc('month', now(), 'UTC')),
        'stale_reservations',
        (SELECT count(*)
           FROM public.ai_usage AS u
          WHERE u.status = 'reserved'
            AND u.created_at < now() - interval '10 minutes'),
        'month_calls',
        (SELECT jsonb_build_object(
                    'reserved', count(*) FILTER (WHERE u.status = 'reserved'),
                    'completed', count(*) FILTER (WHERE u.status = 'completed'),
                    'failed', count(*) FILTER (WHERE u.status = 'failed'),
                    'unknown', count(*) FILTER (WHERE u.status = 'unknown'))
           FROM public.ai_usage AS u
          WHERE u.created_at >= date_trunc('month', now(), 'UTC')),
        'last_failure_at',
        (SELECT max(coalesce(u.settled_at, u.created_at))
           FROM public.ai_usage AS u
          WHERE u.status IN ('failed', 'unknown')),
        'entitlements',
        coalesce((
            SELECT jsonb_agg(jsonb_build_object(
                       'user_id', e.user_id,
                       'email', e.email,
                       'active', e.revoked_at IS NULL,
                       'granted_at', e.granted_at,
                       'revoked_at', e.revoked_at,
                       'daily_questions', e.daily_questions,
                       'monthly_budget_usd', e.monthly_budget_usd::text,
                       'note', e.note,
                       'used_today', q.used_today,
                       'spent_month_usd', q.account_spent_usd)
                   ORDER BY e.granted_at DESC)
              FROM public.ai_entitlements AS e
             CROSS JOIN LATERAL public.ai_quota(e.user_id, p_default_daily, p_default_account_usd) AS q
        ), '[]'::jsonb)
    );
$$;

REVOKE ALL ON FUNCTION public.ai_quota(uuid, integer, numeric) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.ai_reserve(uuid, uuid, numeric, integer, numeric, numeric, text, numeric, numeric)
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.ai_settle(bigint, text, integer, integer, numeric) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.ai_admin_report(integer, numeric) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.ai_grant(uuid, text, uuid, integer, numeric, text, text, text)
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.ai_revoke(uuid, uuid, text, text) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.ai_quota(uuid, integer, numeric) TO service_role;
GRANT EXECUTE ON FUNCTION public.ai_reserve(uuid, uuid, numeric, integer, numeric, numeric, text, numeric, numeric)
    TO service_role;
GRANT EXECUTE ON FUNCTION public.ai_settle(bigint, text, integer, integer, numeric) TO service_role;
GRANT EXECUTE ON FUNCTION public.ai_admin_report(integer, numeric) TO service_role;
GRANT EXECUTE ON FUNCTION public.ai_grant(uuid, text, uuid, integer, numeric, text, text, text)
    TO service_role;
GRANT EXECUTE ON FUNCTION public.ai_revoke(uuid, uuid, text, text) TO service_role;

-- Make the new functions visible to PostgREST without waiting for a reload.
NOTIFY pgrst, 'reload schema';

COMMIT;
