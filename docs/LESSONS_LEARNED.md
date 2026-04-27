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

## Cycle Lessons

Append-only. Per [ADR-0018](adr/0018-cycle-cadence-doc-artifacts.md), every
cycle close adds an entry: what shipped, what the gate found, what we would
do differently. Past entries are not edited — corrections become new entries
in later cycles.

### Cycle 1 — v4.0 Materialized Intelligence (closed 2026-04-19)

**What shipped:** 7 waves delivering ingest-time materialization, derived-artifact provenance, lifecycle-phase inference, and WebSocket progress hardening. Tag `v4.0.0` at commit `7262253`. v4.0.1 followed 2026-04-19 with Track 1 polish.

#### Calibration before claiming a behavior
ADR-0009 W4 pre-committed a 5+1 lifecycle phase classifier (deg / cont / closure / …) with a thresholded protocol. The gate **failed at every threshold for distinct sub-gate reasons**. Engine v1 was characterized as a reliable construction-vs-non-construction detector, not a 5+1 classifier; hysteresis was 0 phase flips across 4 multi-revision programs (with 1 confidence-band crossing — see [`docs/adr/0009-w4-outcome.md` §"Hysteresis report"](adr/0009-w4-outcome.md) line 72 for the band-flip count). The W4 outcome ADR is the canonical record.
**Lesson:** Pre-registered calibration before product claim is the only honest path. The protocol failing is a feature of pre-registration, not a bug.

#### Operational darkness lasts longer than you think
v4.0.0 RC-state had 24 ready prod projects with empty `schedule_derived_artifacts` despite the W2 DDL being applied — the backfill CLI had never been invoked. The first invocation surfaced a `_json_safe` regression at the store boundary (silent `datetime` serialization failure), which flipped 21 of those projects to `failed`. The post-fix run produced 88 derived-artifact rows (22 projects × 4 kinds) + 88 `action='materialize'` audit rows with a shared `backfill_id` (per [CHANGELOG v4.0.0 §"Prod operational darkness"](../CHANGELOG.md)). Discovered during the W4 backfill audit, not during regular monitoring.
**Lesson:** "Healthy in dev, silent in prod" is the worst failure mode. Dev fixtures are too clean — verify boundary serialization with prod-shape data, not curated samples.

#### `_json_safe` at the store boundary
Whenever Python → JSON serialization happens at a persistence boundary, the boundary is the contract. Centralizing the conversion in one place (`store._json_safe`) ensures all engines share the same shape and the same failure mode. The fix that made W4 backfill possible was a one-liner once the diagnosis was correct.

#### Explicit state machine over inferred state
Before ADR-0015: `projects` table had implicit "is it ready?" inferred from row presence in derived tables. After: explicit `status: pending | ready | failed`.
**Lesson:** Make state machines explicit and queryable, not implicit and inferred from joins.

#### WebSocket hardening — server-generated identifiers + close codes
Before ADR-0013: client-generated job IDs and undifferentiated WS closures. After: server generates `job_id` on `POST /jobs/progress/start` and returns it with `ws_url`; closures use `4401`/`4403`/`4404` to differentiate auth/authz/not-found.
**Lesson:** Don't trust client-side identifiers for resource keys. Differentiate close codes so the frontend can react correctly without parsing strings.

#### What we would do differently
- Run the W4 backfill audit **before** v4.0.0 tag, not after — it would have surfaced the `_json_safe` regression as a pre-release blocker rather than a same-day patch.
- Pre-register the W4 protocol with a hash pin from the start — Cycle 2 W3 added one in retrospect for the harness primitive (`TestProtocolDriftPin`); the W4 ADR could have shipped with one.

---

### Cycle 2 — v4.1 Consolidation + Primitive (closed 2026-04-26)

**What shipped:** 4 waves per ADR-0019 (Option 4 — no deep, three primitives every future deep depends on). Tag `v4.1.0` at commit `aae1bb1`. **6 of 7** pre-registered success criteria closed wave-by-wave; the 7th = the release tag itself (per [CHANGELOG.md §v4.1.0](../CHANGELOG.md)). Criterion 5 carries an honest caveat — [ADR-0020 §"Decision"](adr/0020-calibration-harness-primitive.md) explicitly notes the harness ships end-to-end but does NOT reproduce the W4 outcome numbers authoritatively until the private manifest is archived. Cycle close ships **4 of the 5** ADR-0018 artifacts; the 2026-04-26 audit re-run is owed and tracked as a separate operator work item before Cycle 3 W0 opens.

#### Wave-level honesty contract — the council pair pays for itself
Every wave's exit council pair (backend + frontend + devils-advocate) caught load-bearing P1s. W3 council found 3 P1s the implementation alone missed (`Observation` boundary validation, CLI default footgun, protocol drift hash-pin). W0 entry council was skipped — right call there because W0 was hygiene-only, but skipping it on substantive waves would have shipped real bugs.
**Lesson:** Council pair is cheap insurance on substantive waves. Skip only when truly mechanical.

#### Wire vs UI honesty divergence
W2 B2 originally fixed only the UI — split chip above phase, demoted phase to `(preview)`. Devils-advocate caught that non-UI consumers (MCP tools, OpenAPI clients, CLI users) saw the legacy `phase` field as equally weighted via `Field()` description and example values. Fix: `Field(description=...)` markers on the schema closed the gap at the API boundary.
**Lesson:** UI honesty is half the contract. Schema-level honesty is the other half. Fix both.

#### Half-shipped features need explicit "dormant" framing
W1 D4 shipped the `recoveryPoller` composable hook with no risk-page wiring. Backend `RiskStore.job_id` index and `GET /risk/simulations/by-job/{id}` deferred. Honest framing went into the commit body, memory, ADR, and ROADMAP — all explicitly say "dormant for users until backend wires up".
**Lesson:** Half-shipped is fine if framed as such. The failure mode is leaving it implicit — readers infer "shipped" and stale code accumulates.

#### Pre-registration discipline cost vs benefit
Adding a SHA-256 hash pin to the W4 protocol (`TestProtocolDriftPin`) cost ~10 minutes. Benefit: any future protocol drift fails the test immediately, with the original protocol bytes verifiable. For any future protocol shipping against an Amendment-style ADR, the hash pin is worth the cost.

#### Lazy import for heavy adapter dependencies
`tools/calibration_harness.py` lazy-imports `src.analytics.lifecycle_phase` only on adapter use. Operators running the harness on a slim Docker image without analytics deps don't get an `ImportError` on module load. Surprise: missing-deps errors still surface as bare `ImportError`, not as a typed "missing optional adapter" error. Wrap in a future iteration.

#### Transitive deps lurk in obvious places
Bumped Dockerfile to Python 3.14 (commit `f1bd4e2`), broke deploy. Root cause: `supabase ≥ 2.10 → storage3 → pyiceberg`, and pyiceberg has no 3.14 wheel for Debian slim. Direct dep audit (`pyproject.toml`) showed nothing pyiceberg-related — required `pip show <pkg>` Required-by chain to find the transitive.
**Lesson:** Always check transitive (`pip show storage3 | grep Required-by`, then walk the graph) before bumping Python in Dockerfile.

#### Dockerfile != CI Python parity
Wrong rationale: "CI runs on 3.14, so Dockerfile should match for parity." Reality: CI installs deps for tests (subset). Deploy installs for runtime (full). Dep trees differ.
**Lesson:** Validate on the Deploy job, not just the CI test job. Dockerfile pin and CI matrix pin are different decisions.

#### Loose dep ranges → ecosystem drift
`pyproject.toml` had `>=` floors several majors behind. Local dev / CI / deploy ended up on subtly different versions. Fix: floor at `>=` current-latest helps Dependabot maintain freshness without bumping past breaking majors.
**Lesson:** Floors are not just minimum compatibility — they're freshness signals. Lift them at every cycle close.

#### Local ↔ CI ruff version drift
Symptom: Dependabot PRs failing format check that passed locally. Diagnosis: local `ruff` was newer than CI's `pyproject` floor; CI ran old ruff with old format rules and mismatched. Fix: pin `ruff>=0.15.12` in `[dev]` extras.
**Lesson:** Format tools are exception cases for "loose floors are fine" — pin them tighter so format conventions stay reproducible across environments.

#### Defensive Dependabot ignore for transitive deps
Even though pyiceberg comes via the supabase chain (not a direct dep), blocking its majors via `version-update:semver-major` ignore prevents future deploy breaks if pyiceberg drops 3.13 support.
**Lesson:** Defensive ignore on transitive deps is rarely wrong. Cost is low (Dependabot just doesn't propose); benefit is preventing a repeat of the 3.14 incident.

#### What we would do differently
- Open Cycle 2 with a 1-day audit-prep wave (reading the previous cycle's W4 outcome, mapping every "deferred" item) before W0. The audit umbrella `#25` had 6 sub-issues and W0 ended up partly resolving them — would have been cleaner to scope explicitly.
- Author `docs/ROADMAP.md` at Cycle 2 *kickoff*, not Cycle 2 *close*. Issue #27 sat for the duration of the cycle. Future cycles: ROADMAP refresh is a W0 deliverable, not a close-time deliverable.

---

*Last updated: 2026-04-26 (Cycle 2 close)*
