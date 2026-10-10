# MeridianIQ — Deploy Checklist

Formal deployment procedure. Every production deploy must complete all steps.
Learned from ai-pm-research-hub: 5-phase sprint closure (Execute -> Audit -> Fix -> Docs -> Deploy).

---

## Pre-Deploy

- [ ] All tests pass: `python3 -m pytest tests/ -q`
- [ ] Frontend type check: `cd web && npm run check`
- [ ] Frontend builds: `cd web && npm run build`
- [ ] No uncommitted changes: `git status` is clean
- [ ] Branch is up to date with main

## Database

- [ ] Review new migrations: `ls supabase/migrations/`
- [ ] Apply migrations via Supabase Dashboard or CLI
- [ ] After RPC changes: run `NOTIFY pgrst, 'reload schema'` in SQL Editor
- [ ] Verify storage buckets exist (xer-files, reports)
- [ ] Verify RLS policies on all tables (check Dashboard > Authentication > Policies)

## Secrets

- [ ] Fly.io secrets set: `fly secrets list`
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `SUPABASE_JWT_SECRET`
  - `SENTRY_DSN`
  - `ENVIRONMENT=production`
- [ ] Cloudflare Pages env vars set:
  - `VITE_SUPABASE_URL`
  - `VITE_SUPABASE_ANON_KEY`
  - `VITE_API_URL`

## Deploy

- [ ] Push to main: `git push origin main`
- [ ] Monitor CI: GitHub Actions all 3 jobs green
- [ ] Backend auto-deploys to Fly.io (check `fly status`)
- [ ] Frontend auto-deploys to Cloudflare Pages (check CF dashboard)

## Version Bump (pyproject `version`)

The stored analysis results (`schedule_derived_artifacts`) are read only at
the current engine version, which is the package version (ADR-0014). A bump
makes every stored result invisible until the projects are re-materialized:
program trends and the lifecycle card go blank.

- [ ] The CI deploy job's "Re-materialize stored results" step ran and ended
      with "Nothing to re-materialize" or "Left after the run: 0". It needs
      the `FLY_SSH_TOKEN` repository secret
      (`fly tokens create ssh -a meridianiq-api`); without it the step only
      warns.
- [ ] If the step was cut off or warned, run it by hand:
      `fly ssh console -a meridianiq-api -C "python -m src.materializer.backfill --dry-run"`,
      then without `--dry-run`. It is idempotent. Allow ~1.5–4 min per
      10k-activity schedule (measured 2026-10-10).
- [ ] A schedule whose stored data cannot be loaded is marked `failed` by
      the run; that is the true state, not a regression (re-upload it).

## Post-Deploy Smoke Test

- [ ] Visit https://getmeridianiq.com — landing page loads
- [ ] Login with Google OAuth — redirects correctly
- [ ] Upload a test XER file — parses successfully
- [ ] View project detail — health score, DCMA, charts render
- [ ] Generate a PDF report — downloads correctly
- [ ] Check Sentry — no new errors
- [ ] Check API health: `curl https://api.getmeridianiq.com/health`

## Rollback

If issues found:
1. `fly releases` — list recent releases
2. `fly deploy --image <previous-image>` — rollback to previous
3. For DB migrations: restore from Supabase PITR (requires Pro plan)

---

## Credential Rotation (Quarterly)

- [ ] Rotate Supabase JWT secret via Dashboard > Settings > API
- [ ] Update `SUPABASE_JWT_SECRET` on Fly.io
- [ ] Rotate database password via Dashboard > Settings > Database
- [ ] Update `DATABASE_URL` on Fly.io
- [ ] Verify all endpoints still work after rotation

---

*Checklist adapted from ai-pm-research-hub DEPLOY_CHECKLIST.md pattern.*
*Last updated: 2026-04-02*
