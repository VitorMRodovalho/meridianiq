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

#### Post-tag close-arc lessons (2026-04-27)

The following five lessons emerged in the post-`v4.1.0` close-arc session as three PRs landed under the devils-advocate-as-second-reviewer protocol established that day: PR #33 (Cycle 2 close docs per ADR-0018), PR #35 (D4 backend wiring un-dormants the WS recovery poller), PR #36 (engine_version source-of-truth dedup). They are recorded under Cycle 2 because the work was within the Cycle 2 close envelope — no new cycle had opened. Cycle 3 will record its own lessons in its own entry per ADR-0018 cadence.

##### ROADMAP self-corrections are themselves reviewable
PR #36's first commit "corrected" my own earlier ROADMAP framing about `engine_version` — and the correction was wrong (contradicted [ADR-0014 §"engine_version" line 44](adr/0014-derived-artifact-provenance-hash.md), which explicitly sources the version from `src/__about__.py::__version__`). Devils-advocate caught it on the same-day PR review.
**Lesson:** When reverting or correcting a ROADMAP entry, ground the new framing in the source ADR text directly, not a re-imagining of what the ADR "should" say. The ADR file is authoritative; the ROADMAP follows it.

##### Source-inspection regression tests are a smell
The first version of `TestEngineVersionSingleSource` (PR #36) used `inspect.getsource()` + string match against the literal `"4.0"`. It felt like it enforced a contract but only enforced a string match — any rename, refactor, or moved import would silently bypass the test. Devils-advocate caught it; the replacement uses `monkeypatch` + sentinel-value identity check, exercising the actual import path so a future literal-cache regression fails the test under any refactor shape.
**Lesson:** Source-text tests are a code smell. A test that drives the real import path costs a few extra LoC but catches refactor regressions a string-match test silently passes through.

##### The ADR-0014 implementation has been diverged for multiple cycles
`_ENGINE_VERSION = "4.0"` was hand-coded in `src/materializer/runtime.py` since Cycle 1; ADR-0014 says it should be sourced from `src/__about__.py::__version__`, which does not exist. The divergence rotted under the radar across four releases (v4.0.0 → v4.0.1 → v4.0.2 → v4.1.0) — only surfaced when devils-advocate re-read the ADR during PR #36 review.
**Lesson:** Read the ADR, don't re-derive its claims from memory. ADR drift between text and implementation is silent until a fresh reader (human or agent) does the cross-check. Pair with: any future ADR that pins a concrete file/line/symbol contract should ship a regression test that verifies the contract on every CI run.

##### Devils-advocate cost vs benefit pattern is now empirical
Across the three PRs of session 2026-04-27 (#33, #35, #36), devils-advocate caught **2 blocking + 4 substantive non-blocking findings per PR on average**. Time cost: ~2 min to dispatch + ~5–10 min to address. Sample categories: honesty-debt slippage (7/7 → 6+tag overclaim, ADR §5 silent weakening, "likely still running" overpromise), real bugs (line 310 hardcoded literal in same module as the dedup fix, source-inspection brittleness), and ROADMAP self-corrections that were themselves wrong (the ADR-0014 framing slip). Pair this with the earlier "council pair pays for itself" lesson on substantive WAVES — devils-advocate-as-second-reviewer is the same pattern at PR-level granularity.
**Lesson:** Devils-advocate is cheap insurance on every substantive PR. Skip only for truly mechanical work (Dependabot bumps, catalog regen, 1-line typo fixes). The ADR-0018 §"Negative / accepted costs" social-enforcement clause makes solo-maintainer self-merge acceptable when paired with a devils-advocate proxy review; the 3-for-3 hit rate this session validates the protocol.

##### Catalog drift is caught by CI but not by author
PR #35's first commit added the new `GET /api/v1/risk/simulations/by-job/{job_id}` endpoint without regen-ing `docs/api-reference.md`. CI's doc-sync workflow caught the drift; two follow-up commits brought CLAUDE.md (`docs: bump CLAUDE.md endpoint count 121→122`) and the api-reference catalog into stat consistency.
**Lesson:** Any new endpoint = regen catalogs in the same PR via `python3 scripts/generate_api_reference.py`. The CI workflow is the safety net, but the author-time cost of running the script once is much lower than the cost of two follow-up commits + the cognitive overhead of stat-consistency triage. Add the regen step to any "new endpoint" PR template / personal checklist.

#### What we would do differently
- Open Cycle 2 with a 1-day audit-prep wave (reading the previous cycle's W4 outcome, mapping every "deferred" item) before W0. The audit umbrella `#25` had 6 sub-issues and W0 ended up partly resolving them — would have been cleaner to scope explicitly.
- Author `docs/ROADMAP.md` at Cycle 2 *kickoff*, not Cycle 2 *close*. Issue #27 sat for the duration of the cycle. Future cycles: ROADMAP refresh is a W0 deliverable, not a close-time deliverable.

---

*Last updated: 2026-04-27 (Cycle 2 post-tag close-arc — 5 lessons appended from PRs #33 + #35 + #36)*

---

## Cycle 3 in-flight close-arc — 2026-04-27 night

The following lessons emerged in the Cycle 3 in-flight close-arc session (2026-04-27 evening + night) as **9 substantive PRs** landed under the [ADR-0018 Amendment 1](adr/0018-cycle-cadence-doc-artifacts.md) PR-level cadence: PR #38 (Cycle 3 entry), #39 (audit re-run), #48 (W3 reproduction test), #50 (engine_version migration), #52 (doc-drift), #53 (ADR-0018 Am.1), #55 (operator runbooks), #56 (rate-limit policy + Am.1 to ADR-0019), #58 (W4 operator-prep). Cycle 3 is **mid-cycle** at this writing (3/9 success criteria closed); these are *in-flight* lessons recorded before close to avoid memory-fade. Cycle close lessons authored separately at v4.2.0/v4.1.1 release per ADR-0018 §3 cadence.

##### Recursive validation: the protocol catches the protocol's own bugs

PR #53 codified the DA-as-second-reviewer protocol in ADR-0018 Amendment 1. DA review of that meta-PR caught 5 blocking + 5 non-blocking findings on the very PR codifying DA review — including ADR-citation drift on the `5+5 vs 5+4` empirical claim about PR #38's own DA findings (the same ADR-citation-drift class the protocol is designed to catch). PR #56 codified the rate-limit policy in ADR-0019 Amendment 1; DA review caught 3 blocking on that meta-PR including a **CRITICAL SECURITY ISSUE** that pre-existed the PR but would have been ADR-codified-as-acceptable without the review (`reconcile_ips` + `validate_recovery` were `optional_auth`/anonymous-callable + compute-heavy, but APPROVED_EXCEPTIONS labeled them "admin-scope auth gated"). PR #58 codified W4 operator-prep; DA caught 2 blocking including PostgREST silent row truncation (same regression class as ADR-0012 amendment 2).
**Lesson:** The protocol catches not just new bugs but pre-existing bugs that were about to get rubber-stamped into ADR-grade authoritative reference. The "rubber-stamp risk" is the load-bearing reason to NOT skip DA on meta-PRs even when they feel ouroboros. Catalog the recursive findings explicitly in the amendment text — they are the strongest evidence the protocol works.

##### Audit-driven tests pay multiple times across the cycle

`scripts/check_stats_consistency.py` was extended in PR #52 to validate README mermaid + ASCII tree + `docs/architecture.md` (3 forms) + migrations canonical count. PR #58's commit later tripped the same guard — caught my own drift mid-cycle (bumped 26 → 27 migrations). The guard caught the drift class it was authored to prevent, on the same author's same-cycle work.
**Lesson:** Audit-driven tests / linters self-pay even within a single author's session. The pattern is: audit finding → test → drift → test catches → fix → ship clean. Author finds it cheaper to bump the literal once than re-litigate the drift class. Future audits should always ship with their enforcement test in the same PR, not as deferred follow-up.

##### Pydantic body-name collision is a real CLI-flag-rollout cost

PR #56 added `request: Request` (slowapi-required) parameter to 8 router functions for rate-limit decorator addition. Six functions (whatif × 3 + forensics × 1 + analysis × 1 + schedule_ops × 1) had `request: <Pydantic>` body collisions — adding decorator requires renaming `request: <Pydantic>` → `body: <Pydantic>` AND adding separate `request: Request`. Mechanically safe (FastAPI auto-detects body via type annotation, parameter name irrelevant for routing) but touches every call-site. Deferred via `APPROVED_EXCEPTIONS` with explicit "deferred — request: <Pydantic> body collision" rationale + tracked in `#57`.
**Lesson:** When introducing a CLI-style decorator that requires a specific parameter name, audit ALL existing decorated functions for parameter-name collisions BEFORE deciding scope. The 8/14 fixable + 6/14 deferred ratio is a normal first-pass for retrofitting — but the deferred set needs its own tracking issue immediately, not buried in the test exception list.

##### Operator-runbook prep + diagnostic warnings prevent silent-success failure modes

PR #58 (W4 operator-prep) shipped `--re-materialize-version` CLI flag + migration 027 (tombstone) draft as the two operator paths. DA blocking #2 caught a class of failure that the runbook alone couldn't prevent: if migration 027 (Option B) runs FIRST, then `--re-materialize-version 4.0` returns 0 candidates with rc=0 — operator sees "0 candidates" + "nothing to materialize" + exit code 0 and concludes success. Fix: explicit `_diagnose_zero_candidates(store, old_engine_version)` helper that re-queries with `include_stale=True` and emits a multi-line WARNING when stale rows exist at the queried version. The warning explicitly references the runbook + migration 027.
**Lesson:** When operator paths are mutually exclusive (Option A vs Option B), the CLI MUST emit diagnostic warnings for the cross-path silent-failure modes — even if the runbook documents the correct order. Tired operators read CLI output, not runbooks. The diagnostic cost is one helper function + one log line; the missed-deploy cost is hours of "why are dashboards blank?" investigation.

##### Mid-cycle CHANGELOG `[Unreleased]` section with explicit pending-operator + pending-Claude tables

The Cycle 3 in-flight CHANGELOG entry tables what's pending. The two-column structure (criterion / status / action) makes the gap between "PR landed" and "criterion closed" visible. Without the table, a future reader scanning the changelog sees "lots of merged PRs" and presumes Cycle 3 is done — not "3/9 criteria closed; 4 operator-pending; 1 Claude-doable follow-up open".
**Lesson:** When mid-cycle changelog entries ship, separate "what merged" from "what closed". Operator-pending criteria need a visible table with action references to the runbook section. Without the explicit pending column, the changelog overclaims completion.

#### Pattern observation (not a lesson — early to claim)

Across Cycle 1 + 2 + 3 in-flight (so far), every meta-PR that codifies a policy has been DA-reviewed AND has had a substantive blocking finding. Sample size n=4 (PR #38 cycle entry, #53 ADR-0018 Am.1, #56 ADR-0019 Am.1, #58 W4 prep — though #58 wasn't strictly a "policy" PR). The pattern suggests "meta-PRs are denser per-line than feature PRs in catch surface." Too early to claim as a lesson; record for future cross-cycle synthesis.

---

*Last updated: 2026-04-27 night (Cycle 3 in-flight close-arc — 5 lessons appended from PRs #38, #39, #48, #50, #52, #53, #55, #56, #58)*
