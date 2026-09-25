# Runbook: email alert when a new account is created

The `notify_signup_alert` trigger on `auth.users` (migration `032_signup_alert_trigger.sql`) posts **only the sign-in provider and the creation time** to `POST /api/v1/internal/hooks/auth-user-created`. The endpoint then emails the operator through Resend.

- The trigger posts through `pg_net`, which is asynchronous, and it swallows its own errors. The alert can never slow down or break a signup; at worst, an alert is lost.
- The stock Supabase "Database Webhook" is **not** used, because it would send the whole `auth.users` row, credential material included.

## 1. Resend (once)

1. Create a Resend account dedicated to this project.
2. Create an API key with **Sending access** only.
3. Until a sending domain is verified in Resend, the default sender `onboarding@resend.dev` delivers **only to the Resend account's own address**. Use that address as the recipient.

## 2. Secrets on Fly (once)

Run this in your own terminal, not through an assistant's shell, so the key never appears in a transcript. Never commit it.

```bash
SECRET=$(openssl rand -hex 32)
echo "$SECRET" > ~/.meridianiq-webhook-secret && chmod 600 ~/.meridianiq-webhook-secret
read -rs -p "Resend API key: " RK; echo
flyctl secrets set -a meridianiq-api --stage \
  RESEND_API_KEY="$RK" SIGNUP_WEBHOOK_SECRET="$SECRET" SIGNUP_ALERT_TO="you@example.com"
unset RK
```

The secrets take effect on the next deploy. The endpoint answers 404 until all three are set.

## 3. Database side (once, SQL Editor)

1. Enable the `pg_net` extension: Database → Extensions → `pg_net`.
2. Apply `supabase/migrations/032_signup_alert_trigger.sql`, the same way as other migrations.
3. Store the URL and the secret in Vault:

```sql
select vault.create_secret('https://meridianiq-api.fly.dev/api/v1/internal/hooks/auth-user-created', 'signup_webhook_url');
select vault.create_secret('<contents of ~/.meridianiq-webhook-secret>', 'signup_webhook_secret');
```

The trigger does nothing until both Vault secrets exist.

## 4. Verify

- `curl -s -o /dev/null -w "%{http_code}\n" -X POST https://meridianiq-api.fly.dev/api/v1/internal/hooks/auth-user-created` should print `401`. A `404` means the Fly secrets are not all set.
- Create a throwaway account with a Google account that has never signed in. The alert should arrive within a minute.
- If it does not arrive, run `flyctl logs -a meridianiq-api --no-tail | grep "signup alert"`. You should see `sent (status 200, id …)` or `failed: HTTP <code>`.

## 5. Weekly reconciliation (alerts can be lost silently)

`pg_net` never retries, so a deploy gap or a misconfiguration loses an alert without any signal. Once a week, compare new accounts with delivered calls:

```sql
select count(*) as accounts_last_7d from auth.users where created_at > now() - interval '7 days';
select status_code, count(*) from net._http_response
 where created > now() - interval '7 days' group by status_code;
```

A mismatch, or any non-2xx status, means some alerts were lost. Check the Supabase dashboard for the accounts.

## Personal data

By default the alert carries no personal data. `SIGNUP_ALERT_INCLUDE_EMAIL=1` adds the email address, but only if the trigger also sends it (add `'email', NEW.email` to the record in the function). It also sends the address to Resend, a processor outside Brazil, which is an LGPD international transfer. Record that choice in the privacy notice.

## Rotate or disable

- **Rotate:** set a new `SIGNUP_WEBHOOK_SECRET` on Fly, then run `select vault.update_secret((select id from vault.secrets where name = 'signup_webhook_secret'), '<new secret>');`.
- **Disable:** `drop trigger notify_signup_alert on auth.users;`, or unset `SIGNUP_WEBHOOK_SECRET` so the endpoint answers 404.
