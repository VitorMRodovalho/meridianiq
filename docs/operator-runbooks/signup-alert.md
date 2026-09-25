# Runbook: email alert when a new account is created

The API exposes `POST /api/v1/internal/hooks/auth-user-created`. A Supabase Database Webhook on `INSERT` into `auth.users` calls it, and it emails the operator through Resend. The webhook runs through `pg_net`, which is asynchronous: if the API is down, signup still succeeds and only the alert is lost.

By default the alert contains the sign-in provider and the creation time, but no personal data. Set `SIGNUP_ALERT_INCLUDE_EMAIL=1` to include the new user's email address.

## 1. Resend (once)

1. Create a Resend account dedicated to this project.
2. Create an API key with **Sending access** only.
3. Until a sending domain is verified in Resend, the default sender `onboarding@resend.dev` delivers **only to the Resend account's own address**. Use that address as the recipient.

## 2. Secrets on Fly (once)

Run these from your own terminal. Never paste secrets into chat or into this repository.

```bash
SECRET=$(openssl rand -hex 32); echo "$SECRET"   # keep it for step 3
flyctl secrets set -a meridianiq-api \
  SIGNUP_WEBHOOK_SECRET="$SECRET" \
  RESEND_API_KEY="re_..." \
  SIGNUP_ALERT_TO="you@example.com"
# optional, once a domain is verified in Resend:
# flyctl secrets set -a meridianiq-api SIGNUP_ALERT_FROM="MeridianIQ <alerts@your-domain>"
```

The endpoint answers 404 until `SIGNUP_WEBHOOK_SECRET`, `RESEND_API_KEY` and `SIGNUP_ALERT_TO` are all set.

## 3. Database Webhook (once)

Supabase dashboard → Database → Webhooks → Create a new hook:

- Table: `auth.users`. Events: `Insert`.
- Type: HTTP Request, `POST`, URL `https://meridianiq-api.fly.dev/api/v1/internal/hooks/auth-user-created`
- HTTP header: `X-Webhook-Secret: <the SECRET from step 2>`. Timeout: 5000 ms.

If the dashboard does not offer the `auth` schema, the equivalent SQL (run in the SQL Editor) is:

```sql
create trigger notify_signup_alert
after insert on auth.users
for each row execute function supabase_functions.http_request(
  'https://meridianiq-api.fly.dev/api/v1/internal/hooks/auth-user-created',
  'POST',
  '{"Content-Type":"application/json","X-Webhook-Secret":"<SECRET>"}',
  '{}',
  '5000'
);
```

## 4. Verify

- `curl -s -o /dev/null -w "%{http_code}\n" -X POST https://meridianiq-api.fly.dev/api/v1/internal/hooks/auth-user-created` must print `401`. A `404` means the secrets are not all set.
- Create a throwaway account with a Google account that has never signed in. The alert should arrive within a minute.
- If it does not arrive, `flyctl logs -a meridianiq-api --no-tail | grep "signup alert"` shows `sent (status 200)` or `failed: <error class>`.

## Rotate or disable

- Rotate: set a new `SIGNUP_WEBHOOK_SECRET` on Fly, then update the webhook header in Supabase.
- Disable: delete the webhook in Supabase, or unset `SIGNUP_WEBHOOK_SECRET`. The endpoint then answers 404.
