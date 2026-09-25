-- Migration 032: minimal new-account alert trigger
--
-- On INSERT into auth.users, post ONLY the sign-in provider and creation
-- time to the API's internal hook (src/api/routers/hooks.py), which emails
-- the operator. The stock Supabase webhook function would send the whole
-- auth.users row (email, metadata, credential material); this one sends
-- nothing personal.
--
-- Safety:
--   * pg_net is asynchronous: the INSERT never waits for the HTTP call.
--   * Any error (pg_net missing, Vault not configured) is swallowed with a
--     WARNING, so the alert can never break signup.
--   * The URL and shared secret live in Supabase Vault, not in this file:
--       select vault.create_secret('<url>',    'signup_webhook_url');
--       select vault.create_secret('<secret>', 'signup_webhook_secret');
--     Until both exist the trigger does nothing.
--   * search_path is pinned (see tests/test_migrations_security_definer.py).
--
-- Requires the pg_net extension (Database -> Extensions). Idempotent.

CREATE OR REPLACE FUNCTION public.notify_signup_alert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    hook_url text;
    hook_secret text;
BEGIN
    SELECT decrypted_secret INTO hook_url
      FROM vault.decrypted_secrets WHERE name = 'signup_webhook_url';
    SELECT decrypted_secret INTO hook_secret
      FROM vault.decrypted_secrets WHERE name = 'signup_webhook_secret';
    IF hook_url IS NULL OR hook_secret IS NULL THEN
        RETURN NEW;
    END IF;

    PERFORM net.http_post(
        url := hook_url,
        body := jsonb_build_object(
            'type', 'INSERT',
            'schema', 'auth',
            'table', 'users',
            'record', jsonb_build_object(
                'created_at', NEW.created_at,
                'raw_app_meta_data', jsonb_build_object(
                    'provider', NEW.raw_app_meta_data ->> 'provider'
                )
            )
        ),
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'X-Webhook-Secret', hook_secret
        ),
        timeout_milliseconds := 5000
    );
    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'notify_signup_alert skipped: %', SQLSTATE;
    RETURN NEW;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.notify_signup_alert() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS notify_signup_alert ON auth.users;
CREATE TRIGGER notify_signup_alert
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.notify_signup_alert();
