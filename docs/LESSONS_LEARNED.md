# MeridianIQ — Lessons Learned

Accumulated lessons from development, deployment, and cross-project experience.

---

## Architecture

### RLS with No Policies = Data Inaccessible
**Issue:** Migrations 003 and 005 enabled RLS on tables (float_snapshots, alerts, health_scores, reports, programs) but defined zero policies. With RLS enabled, zero policies means zero access — not open access.
**Fix:** Migration 011 adds proper owner-based SELECT/INSERT/UPDATE/DELETE policies.
**Lesson:** Always define at least one policy when enabling RLS. Use deny-all default pattern (learned from ai-pm-research-hub).

### In-Memory State Lost on Restart
**Issue:** Sandbox projects and API keys stored in Python dicts. Lost on server restart.
**Fix:** Migration 010 (is_sandbox column) and 012 (api_keys table) provide DB persistence. App-level tracking remains as dev-mode fallback.
**Lesson:** Never rely on in-memory state for production data. Always persist to DB.

### Service Role Key Bypasses RLS
**Issue:** Backend uses `SUPABASE_SERVICE_ROLE_KEY` which bypasses all RLS policies. Security depends entirely on application-layer auth.
**Future:** Migrate to SECURITY DEFINER RPCs (v2.1) — learned from ai-pm-research-hub which uses 189+ RPCs.

---

## Security

### CORS Wildcard + Credentials = Vulnerability
**Issue:** `allow_origins=["*"]` with `allow_credentials=True` allows any site to make authenticated requests.
**Fix:** Whitelisted specific origins (localhost:5173, meridianiq.vitormr.dev).
**Lesson:** Never use wildcard CORS with credentials in production.

### Schema Reload After Migrations
**Issue:** After adding RPCs or modifying tables, PostgREST cache may serve stale schema.
**Fix:** Run `NOTIFY pgrst, 'reload schema'` in SQL Editor after migrations.
**Source:** ai-pm-research-hub RUNBOOK.md.

---

## Frontend

### Hand-Crafted SVG Charts Work Well
**Pattern:** 6 reusable chart components using `$props()` + `$derived()` + SVG viewBox.
**Benefit:** Zero dependencies, SSR-compatible, responsive via viewBox.
**Lesson:** For data visualization in Svelte, hand-crafted SVG is simpler than pulling in chart libraries. TrendChart.svelte established the pattern.

### `{@const}` Placement in Svelte 5
**Issue:** `{@const}` must be inside control flow blocks (`{#each}`, `{#if}`), not directly inside HTML elements like `<g>`.
**Fix:** Move computed values to `$derived()` in the script section.

---

## Testing

### Smoke Test Catches Real Bugs
**Finding:** The forensic PDF report had two bugs (constructor args + attribute path) that 421 unit tests didn't catch — found only during the end-to-end smoke test.
**Lesson:** Always run persona-based journey tests before release, not just unit tests.

### Fixture XER Files Should Cover Edge Cases
**Gap:** sample.xer and sample_update.xer are simple (30 activities). Real XER files with 1000+ activities, special characters, and complex calendars are untested.
**Action:** Test with real XER files in production sandbox mode.

---

## Deployment

### Fly.io Cold Start
**Issue:** First request after idle period gets 502 + CORS error (~10s cold start).
**Fix:** Retry with exponential backoff + warm-up banner on frontend.
**Status:** Mitigated but not eliminated.

### Cloudflare Pages Cache
**Issue:** After deploy, users may get stale JavaScript bundles.
**Fix:** Added cache headers in Cloudflare Pages configuration.

### Supabase Port
**Gotcha:** Supabase uses port 6543 (connection pooler), NOT 5432 (direct connection).

---

## Cross-Project (ai-pm-research-hub)

### Patterns Worth Adopting
1. SECURITY DEFINER RPCs for all DB writes
2. Deny-all RLS default
3. 5-phase sprint closure: Execute → Audit → Fix → Docs → Deploy
4. Pre-commit validation hooks
5. Immutable event logging (audit trail)

### Gotchas to Avoid
1. Storage bucket must exist before upload (silent failure otherwise)
2. pg_cron jobs skip silently without configured secrets
3. Bot Fight Mode blocks .workers.dev domains
4. Auth binding drift between OAuth providers with different emails

---

*Last updated: 2026-04-02*
