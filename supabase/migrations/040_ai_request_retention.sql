-- Migration 040: retention of AI access requests
--
-- Migration 036 keeps a decided request row (status, times, who decided; the
-- note is cleared at the decision) because it blocks a new request for 30
-- days after a dismissal or a withdrawal. Once that block has ended the row
-- serves nothing, so this migration deletes it.
--
-- 1. public.ai_purge_decided_requests() deletes every approved or dismissed
--    request decided more than 30 days ago and returns how many. Pending
--    requests are never purged. It runs with its caller's rights and no API
--    role can call it: the only caller is the cron job below, which runs as
--    postgres (the table's owner). service_role still has no DELETE on the
--    table, so 036's "nothing in the API deletes a request" stays true; this
--    supersedes only 036's "the row's status and dates stay".
--      Safe for every reader: the block (ai_request_cooldown_until) reads a
--      dismissed row's decided_at + 30 days and the entitlement's revoked_at;
--      ai_access_state reads the status only for 'pending'; ai_request_access
--      re-opens a row decided 30 or more days ago (<=), and with the row gone
--      it inserts instead; the alert cap counts requests of the last hour.
--      Approved rows are read by nothing after the decision; they follow the
--      same 30 days so that one rule covers every decided row.
--      The decisions themselves stay in audit_log (036), as before.
-- 2. pg_cron (Supabase Cron) runs it daily at 03:17 UTC as
--    'meridianiq-ai-requests-purge', and 'meridianiq-cron-history-cleanup'
--    keeps 7 days of run history (cron.job_run_details) for meridianiq-*
--    jobs only; pg_cron never prunes it. Runs are skipped while the project
--    is paused, so a row is deleted on the first run after its 30 days.
--    The extension is created in pg_catalog, as the Supabase docs show. The
--    docs' two GRANTs on schema cron are NOT run here: Supabase's own
--    after-create script re-runs on every CREATE EXTENSION and revokes
--    privileges on cron.job from postgres, so a second apply would fail
--    with "dependent privileges exist". That script already gives postgres
--    USAGE on cron and DELETE on cron.job_run_details; the guard checks it.
--    cron.schedule replaces a job of the same name, so re-applying converges.
-- 3. ai_forget_user (036) is replaced with the identical signature and body
--    plus clearing the operator's note on the entitlement (free text about
--    the account), next to the address 036 already clears. Re-applying 036
--    after 040 would silently restore the old body: apply 040 again after it
--    (scripts/rls_replica/040/postcheck.sql detects it).
--
-- Apply after 036, as postgres via psql -f (never `supabase db push`).
-- Idempotent. Single transaction with a 5 s lock_timeout.

BEGIN;

SET LOCAL lock_timeout = '5s';

-- ================================================================
-- 1. Functions
-- ================================================================

-- Delete the decided requests whose 30-day block has ended. Returns the count
-- (logged, since pg_cron records only "1 row" for a SELECT).
CREATE OR REPLACE FUNCTION public.ai_purge_decided_requests()
RETURNS integer
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
    v_deleted integer;
BEGIN
    DELETE FROM public.ai_access_requests AS r
     WHERE r.status <> 'pending'
       AND r.decided_at < now() - interval '30 days';
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RAISE LOG 'ai_purge_decided_requests: % rows', v_deleted;
    RETURN v_deleted;
END
$$;

-- Migration 036's ai_forget_user, identical signature and statements, plus
-- clearing the operator's note on the entitlement.
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
    UPDATE public.ai_entitlements AS e SET email = NULL, note = NULL WHERE e.user_id = p_user_id;
END
$$;

-- ================================================================
-- 2. Privileges
-- ================================================================

REVOKE ALL ON FUNCTION public.ai_purge_decided_requests() FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.ai_forget_user(uuid) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.ai_forget_user(uuid) TO service_role;

-- ================================================================
-- 3. Schedule
-- ================================================================

CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog;

SELECT cron.schedule(
    'meridianiq-ai-requests-purge',
    '17 3 * * *',
    'SELECT public.ai_purge_decided_requests()'
);

SELECT cron.schedule(
    'meridianiq-cron-history-cleanup',
    '27 3 * * *',
    $cmd$DELETE FROM cron.job_run_details WHERE end_time < now() - interval '7 days' AND jobid IN (SELECT jobid FROM cron.job WHERE jobname LIKE 'meridianiq-%')$cmd$
);

-- ================================================================
-- 4. Guard: abort unless the purge is callable by no API role, ai_forget_user
--    by service_role only, both owned by postgres and run with the caller's
--    rights; postgres can use schema cron and no API role can; and both jobs
--    exist, active, as postgres in this database, with these commands.
-- ================================================================

DO $$
DECLARE
    v_purge regprocedure := 'public.ai_purge_decided_requests()'::regprocedure;
    v_forget regprocedure := 'public.ai_forget_user(uuid)'::regprocedure;
    v_role text;
BEGIN
    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF has_function_privilege(v_role, v_purge, 'EXECUTE') THEN
            RAISE EXCEPTION 'migration 040: % can call ai_purge_decided_requests', v_role;
        END IF;
        IF has_schema_privilege(v_role, 'cron', 'USAGE') THEN
            RAISE EXCEPTION 'migration 040: % has USAGE on schema cron', v_role;
        END IF;
    END LOOP;
    IF has_function_privilege('anon', v_forget, 'EXECUTE')
       OR has_function_privilege('authenticated', v_forget, 'EXECUTE')
       OR NOT has_function_privilege('service_role', v_forget, 'EXECUTE') THEN
        RAISE EXCEPTION 'migration 040: ai_forget_user is not service_role only';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_proc AS p
                WHERE p.oid IN (v_purge, v_forget)
                  AND (p.prosecdef OR pg_get_userbyid(p.proowner) <> 'postgres'))
       OR pg_get_userbyid((SELECT c.relowner FROM pg_class AS c
                            WHERE c.oid = 'public.ai_access_requests'::regclass)) <> 'postgres' THEN
        RAISE EXCEPTION 'migration 040: a function or ai_access_requests is not owned by postgres with invoker rights';
    END IF;
    IF NOT has_schema_privilege('postgres', 'cron', 'USAGE')
       OR NOT has_table_privilege('postgres', 'cron.job_run_details', 'DELETE') THEN
        RAISE EXCEPTION 'migration 040: postgres cannot use schema cron or prune its run history';
    END IF;
    IF (SELECT count(*) FROM cron.job AS j
         WHERE j.active AND j.username = 'postgres' AND j.database = current_database()
           AND ((j.jobname = 'meridianiq-ai-requests-purge' AND j.schedule = '17 3 * * *'
                 AND j.command = 'SELECT public.ai_purge_decided_requests()')
             OR (j.jobname = 'meridianiq-cron-history-cleanup' AND j.schedule = '27 3 * * *'
                 AND j.command LIKE 'DELETE FROM cron.job_run_details %'))) <> 2 THEN
        RAISE EXCEPTION 'migration 040: the two meridianiq cron jobs are not scheduled as expected';
    END IF;
END
$$;

COMMIT;
