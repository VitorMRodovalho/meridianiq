# Changelog

All notable changes to MeridianIQ are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [4.0.0] — 2026-04-19 — Materialized Intelligence (Cycle 1, 7 waves)

First release of the v4.0 line. Cycle 1 shipped ingest-time materialization with a full provenance contract, a lifecycle-phase inference surface (calibrated honestly as a preliminary construction-vs-non-construction indicator, not a full 5+1 classifier), WebSocket progress hardening, and governance backfill. Path A pre-committed fallback was activated at Wave 4 after the calibration gate failed at every pre-registered threshold — `src/analytics/lifecycle_health.py` is intentionally NOT shipped this cycle; W5/W6 closed v3.9 tail debt instead (progress_callback wiring + Svelte WebSocket composable on the risk-simulation page).

See `docs/adr/0009-cycle1-lifecycle-intelligence.md` (plus Amendments 1 + 2) for the full decision log, and `docs/adr/0009-w4-outcome.md` for the coarse-banded calibration result.

### Added — Infrastructure

- **`schedule_derived_artifacts` table** (W1, ADR-0014) — per-project cached engine outputs with full provenance (`engine_version`, `ruleset_version`, `input_hash`, `effective_at`, `computed_by`, `stale_reason`). Nine columns, quadruple RLS (SELECT / INSERT / UPDATE / DELETE), `ON DELETE CASCADE` on `project_id`, `UNIQUE NULLS NOT DISTINCT`. Canonical `input_hash` algorithm is the forensic reproducibility contract.
- **Async materializer pipeline** (W2, ADR-0015) — upload happy-path publishes a background materialization job (`asyncio.Task` + `Semaphore(1)` + `ProcessPoolExecutor` spawn) that writes CPM / DCMA / health / lifecycle artifacts. Project rows carry explicit `status = pending | ready | failed`. Upload returns `202 Accepted { job_id, ws_url }` immediately. Backfill CLI re-materializes existing projects with a shared `backfill_id`.
- **Lifecycle-phase inference surface** (W3, ADR-0016) — `src/analytics/lifecycle_phase.py` emits one of 5 phases (`planning / design / procurement / construction / closeout`) plus `unknown` with a numeric confidence. UI card in ProjectDetail with override + sticky lock; Cost Engineer persona has final-say authority. Override log is append-only by convention (no DELETE policy).
- **Server-generated WebSocket job_id** (W0, ADR-0013) — `POST /api/v1/jobs/progress/start` allocates a UUID-v4 bound to the caller. Bearer-JWT auth on the WS handshake in production (`?token=<jwt>`), with dev-mode anonymous fallback intentionally preserved. 15-minute stale-channel reaper invoked opportunistically from `open_channel`. Close codes 4401 / 4403 / 4404 for auth / ownership / invalid id.

### Added — Progress UX (W5/W6 carry-over, path A fallback)

- **`progress_callback`** in `src/analytics/evolution_optimizer.optimize_schedule` — pattern parity with `risk.MonteCarloSimulator.simulate`. Emission cadence `max(1, n // 100)` with final `(total, total)` guarantee. `total = len(priority_rules) + generations * population_size`; bookkeeping re-eval on new best is NOT counted. Future-proof for a router consumer.
- **`useWebSocketProgress` composable** (`web/src/lib/composables/useWebSocketProgress.ts`, NEW) — owns `POST /jobs/progress/start` + WebSocket lifecycle. Exposes a `Readable<WSProgressState>` store for template auto-subscribe. `markDone` / `markError` are authoritative terminal signals from the caller's HTTP response, eliminating the `close()` / WS race. No auto-reconnect (ADR-0013 missed-events contract — honest UX over pretend-retry). SSR-safe.
- **`risk/+page.svelte` wire-in** — `runSimulation()` now flows `progress.start()` → `createRiskSimulation(..., jobId)` → `progress.markDone(result.simulation_id)` → `progress.close()`. Inline progress bar with `role=progressbar` + `aria-live=polite` + i18n copy (connection lost vs failure vs cancelled). 7 new keys × 3 locales (en / pt-BR / es).

### Added — Governance

- **Provenance-hash contract** (ADR-0014) — canonical `input_hash` algorithm; every derived artifact reproducible from `(input_hash, engine_version, ruleset_version)`.
- **PRIVACY.md** — non-binding data-handling disclosure (Supabase region, retention defaults, deletion path).
- **Pre-registered calibration protocol** (ADR-0009 Amendment 1) — dedup rule pre-registered before engine output observed, unknown-denominator convention, phase-distribution sub-gate (no single phase > 60% of numerator), confidence-honesty sub-gate (≥20% of subset at confidence < 0.5), publication scope (coarse-banded aggregates only), filename leakage guard. W4 executed the protocol against 103 unique-hash XERs.
- **W4 outcome record** (ADR-0009 Amendment 2 + `docs/adr/0009-w4-outcome.md`) — fourth scenario not pre-registered (gate fails at every threshold for different sub-gate reasons). Engine behaves as a reliable construction-vs-non-construction detector. Hysteresis excellent: 0 phase flips across 4 multi-revision programs. Pre-committed fallback branch (path A) activated; `lifecycle_health.py` stays deferred.

### Added — ADRs this cycle

- ADR-0009 — Cycle 1 design + Amendments 1 and 2.
- ADR-0012 — derivatives-table specification.
- ADR-0013 — WebSocket progress authentication + server-generated id + reaper.
- ADR-0014 — derived-artifact provenance-hash contract.
- ADR-0015 — async materializer pipeline.
- ADR-0016 — lifecycle-phase inference rule cascade.
- ADR-0010 remains reserved, unused this cycle.
- ADR-0011 — fuzzy-match dependency category for shallow-1 auto-grouping.
- ADR-0006 / 0007 / 0008 backfilled for v3.9 silent-ship items (plugin architecture, minimum-viable progress WS, MCP HTTP/SSE transport).

### Fixed

- **Datetime JSON serialization at the store boundary** (W4) — engine payloads carrying `datetime` objects were rejected by Supabase PostgREST's `httpx` + stdlib `json` encoder, silently flipping projects to `status='failed'` without writing artifacts. `_json_safe` recursive helper applied at both `SupabaseStore.save_derived_artifact` and `InMemoryStore.save_derived_artifact`. Regression test added.
- **`defusedxml.ElementTree` swap in `src/parser/msp_reader.py`** (W0) — closes CWE-611 XXE vulnerability before any first-class MSP framing.
- **UTF-16 BOM detection in `msp_reader.parse`** (W0) — Microsoft tooling commonly emits UTF-16-LE with BOM; previous UTF-8-only path broke PT-BR / ES accented content.
- **`UNIQUE(user_id, lower(name))` + upsert on `programs`** (W0) — closes the race in `get_or_create_program`; prerequisite for shallow-1 fuzzy grouping.
- **`audit_log.user_agent` column** (W0, Migration 021) — closes the v3.8 wave-13 silent gap where the column was promised but the migration never shipped.
- **Prod operational darkness** (W4 collateral) — `schedule_derived_artifacts` was empty across 24 ready projects despite the W2 DDL being applied; the backfill CLI had never been invoked. First invocation surfaced the datetime P1 which flipped 21 projects to `failed`. Post-fix run produced `ok=21 failed=0` and 88 derived-artifact rows (22 projects × 4 kinds) + 88 `action='materialize'` audit rows with a shared `backfill_id`.

### Not shipped this cycle (pre-committed deferral)

- **`src/analytics/lifecycle_health.py`** — the phase-aware analytics engine that would combine `(schedule, baseline, phase)` into phase-aware findings. Deferred per ADR-0009 Amendment 2 path A activation. Revisitable in a future cycle via either (B) ruleset v2 tuning from the calibration dataset (contributor contributions via issue #13), or (C) binary construction-detector + 5+1 preview flag. Either path lands with a new ADR, not by reclaiming ADR-0010.

### Stats

- 47 analysis engines (was 45) + 1 export module
- 121 API endpoints across 23 routers (was 115 × 21)
- 25 Supabase migrations (was 24)
- 1350 backend tests (was 1148) — +202
- 54 SvelteKit pages (unchanged)
- 22 MCP tools (unchanged)
- 11 chart components (unchanged)
- 15 PDF report types (unchanged)

## [3.9.0] — 2026-04-18 — Real-Time + Extensibility (10 waves)

10 waves on top of v3.8.0. Three tracks: P2 cleanup (waves 1-3, 5), P3 capability expansion (waves 4, 6-10), and one fix-up. Headline gains: WebSocket progress streaming for long-running ops, third-party plugin architecture, MCP server now reachable over HTTP, activity grouping by any field, structured P6 calendar exception parser, mobile responsiveness pass, in-memory KPI cache for hot endpoints.

### Changed

- **Sidebar regroup** (wave 1) — split the two 10-item sections (Risk, Prediction) so no section now exceeds 7 items. Risk drops to 7 (Health/Alerts/Scorecard/Monte Carlo/Risk Register/Contract/Anomalies) by extracting a new **Cost & Earned Value** section (EVM/Cashflow/Cost). Prediction splits into **AI Insights** (Ask/What-If/Delay Prediction/Duration ML/Benchmarks) and **Planning & Optimization** (Optimizer/Pareto/Resources/Builder/4D Visualization). 8 sections × ≤7 items each, in line with Miller's 7±2 chunking.
- **Sidebar search discoverability** (wave 1) — added a left-side search-icon glyph + a right-side `/` `<kbd>` hint inside the input, bumped to `text-sm` with `py-2` and a focus ring. The hint hides on focus / when text is present, so the affordance announces the existing `/` shortcut without cluttering active use.
- **Rate-limiter consolidation** (wave 2) — `app.py` no longer creates its own `Limiter` instance; it imports the shared one from `deps.py`. Previously two separate `Limiter` instances existed (one tracked by routers, one by `app.state`), so counter state could diverge. Now there is exactly one `Limiter` for both the `@limiter.limit(...)` decorators and the `RateLimitExceeded` exception handler.

### Added

- **i18n keys** (wave 1) — `nav.section.cost`, `nav.section.ai_insights`, `nav.section.planning` across en / pt-BR / es. Replaces the now-unused `nav.section.prediction` key. Section labels: "Cost & Earned Value" / "Custo e Valor Agregado" / "Costo y Valor Ganado", "AI Insights" (uniform across locales), "Planning & Optimization" / "Planejamento e Otimizacao" / "Planificacion y Optimizacion".

### Investigated / no-action

- **slowapi vs starlette-ratelimit** (wave 2, BUGS.md ticket #74) — evaluated migrating off `slowapi` after the BUGS.md "possibly unmaintained" flag. Findings: (1) slowapi 0.1.9 is the latest, last commit Aug 2025, repo not archived (1952 stars, 101 open issues — typical "stable enough" library); (2) `starlette-ratelimit` does not exist as a published PyPI package; (3) `fastapi-limiter` is async-Redis-backed (overkill for our 9 rate-limited endpoints, no Redis in stack); (4) rolling our own atop `limits` (the library slowapi already wraps) would duplicate slowapi's API for no gain. Decision: stay on slowapi, close ticket #74. Did consolidate the duplicate `Limiter` instance as a quality improvement (see Changed above).

### Performance

- **In-memory KPI cache for hot read endpoints** (wave 3) — `/api/v1/programs/{id}/rollup` and `/api/v1/bi/projects` both recomputed `CPMCalculator + DCMA14Analyzer + HealthScoreCalculator` on the latest schedule for every request. Repeated polls from BI dashboards (Power BI, Tableau) and program-director dashboards now coalesce to a single computation per 120 s window via `src/api/cache.py` (namespace-scoped TTL cache, single-process, no Redis). The shared `schedule_kpi_bundle()` helper in `src/api/kpi_helpers.py` collapses three previously-duplicated try/except CPM/DCMA/Health blocks into one. `cache_stats()` exposes per-namespace hit/miss/size for future observability wiring. 8 cache tests + existing 38 programs/bi tests pass.

### Added — Integrations

- **MCP server HTTP / SSE transports** (wave 4) — `python -m src.mcp_server` accepts `--transport stdio | http | sse` plus `--host` / `--port`. Default stays `stdio` (Claude Desktop / Code spawning). The new `http` mode (FastMCP "streamable-http") exposes the MCP endpoint at `/mcp`, enabling cloud-hosted MCP clients to reach the 22 MeridianIQ tools without spawning a local process. `sse` covers legacy MCP HTTP clients. Auth is intentionally not enforced at the MCP layer — terminate TLS + auth at a reverse proxy. New `tests/test_mcp_cli.py` (7 tests) exercises the parser without binding sockets. Closes the v3.9 P3 candidate "MCP over HTTP" from the v4.0 aspirational list.

### Mobile

- **Mobile responsiveness pass** (wave 5) — fixed 9 hot-spot pages where `grid-cols-3` / `grid-cols-4` KPI summaries collapsed into squashed cards on phones. Pattern: `grid-cols-3 → grid-cols-1 sm:grid-cols-3` (or `grid-cols-2 md:grid-cols-4` for 4-card panels). Pages touched: `/forensic/[id]`, `/tia/[id]`, `/builder`, `/contract`, `/risk/[id]`, `/evm`, `/pareto`, `/compare`. Five wide tables on `/projects/[id]` (critical-path / float-distribution / milestones) and `/org/[id]` (members / audit log) gained `overflow-x-auto` so they scroll horizontally instead of clipping. `GanttChart.svelte`'s SVG `min-width` dropped from 500 to 320 px to fit iPhone-SE-class viewports without forcing a large horizontal scroll. Sidebar already had a hamburger off-canvas pattern (no changes there).

### Parsing

- **Structured P6 calendar data parser** (wave 6, BUGS.md #12) — new `src/parser/calendar_data.py` parses the `clndr_data` blob into a `CalendarSchedule` with per-weekday working hours (1=Sunday..7=Saturday per P6 SDK) and a list of `CalendarException` entries that distinguish full holidays (`is_working=False`) from partial-working exception days (`is_working=True, hours=N`). Tolerant of malformed input — returns whatever it could decode without raising. The legacy `parse_calendar_holidays()` regex in `schedule_view.py` continues to work unchanged (only used for Gantt timeline shading). 9 tests cover empty input, weekly schedule extraction, both exception kinds, sort ordering + counters, malformed blobs, and over-large day numbers.

### Extensibility

- **Plugin architecture (initial)** (wave 7) — third-party packages can ship their own analysis engines via Python entry-points (`[project.entry-points."meridianiq.engines"]`). The `src/plugins` package defines an `AnalysisEngine` `Protocol` (runtime-checkable: `name`, `version`, `analyze(schedule)`) plus a registry with `discover_plugins()` / `list_plugins()` / `get_plugin(name)` / `register_plugin(instance)`. A broken plugin is logged and skipped — it can never take down host startup. A working reference plugin lives at `samples/plugin-example/` (`activity-counter` engine that buckets activities by status). 9 tests cover protocol checks, register / lookup / list, error paths, and the sample plugin shape. API exposure (`GET /api/v1/plugins`, `POST /api/v1/plugins/{name}/run`) deferred to a follow-up wave.

### Schedule Viewer

- **Activity grouping by any field** (wave 8, BUGS.md #13) — the `/schedule-view` endpoint accepts a new `group_by` query param. Default `wbs` keeps the project's real WBS hierarchy (zero-cost no-op). Other modes — `status`, `critical`, `task_type`, `calendar`, `float_bucket` — synthesise a flat WBS tree where each root is one bucket and activities are reassigned via `model_copy` so the original schedule stays untouched. The /schedule UI gains a "Group by" dropdown next to the baseline picker. Cache key now includes the grouping mode so different views are cached independently. 14 new tests + 11 cache tests still pass.

### Plugins

- **Plugin HTTP surface + startup discovery** (wave 9) — wave 7 shipped the in-process registry; this wave wires it through the API. New `src/api/routers/plugins.py` adds `GET /api/v1/plugins` (list registered) and `POST /api/v1/plugins/{name}/run/{project_id}` (invoke against a stored schedule). `discover_plugins()` is called once at FastAPI module load so the registry is populated before the first request. Plugin exceptions become HTTP 500 with the exception text — never propagate. 6 new HTTP tests. Stats: **115 endpoints** across **21 routers** (was 113 / 20).

### Real-time

- **WebSocket progress streaming for Monte Carlo** (wave 10, BUGS.md #14) — long-running QSRA simulations now emit progress events the frontend (or any MCP client) can subscribe to. New `src/api/progress.py` exposes a tiny per-job `asyncio.Queue` registry with `open_channel` / `publish` / `thread_safe_publisher` (the last bridges sync simulator threads back into the event loop via `loop.call_soon_threadsafe`). New WebSocket endpoint `GET /api/v1/ws/progress/{job_id}` streams `{"type": "progress", "done", "total", "pct"}` events ending with `{"type": "done", "simulation_id"}` (or `{"type": "error", "message"}`). `MonteCarloSimulator.simulate()` accepts an optional `progress_callback` fired roughly every 1 % of iterations — zero per-iteration cost when omitted. The risk endpoint takes a new `?job_id=` query param: open the WS first, then issue the POST with the same id. 5 tests including a full TestClient round-trip with a real Monte Carlo run. Optimizer + report-generation hooks deferred to follow-up waves.

## [3.8.0] — 2026-04-18 — Forensic MIP Expansion + Frontend Hardening (26 waves)

26 waves shipped across a single session on top of v3.7.0. Two tracks: forensic feature expansion (waves 1-9) and frontend hardening (waves 10-26 — P2 tech debt cleared).

### Added — Forensic & Reporting (waves 1-9)

- **BI connector templates** (wave 1) — `samples/bi-templates/` with Power Query M + DAX + Tableau .tds + LookML samples, plus `/docs/user-guide/bi-dashboards.md` walkthrough. 8 smoke tests.
- **AIA G702 Application and Certificate for Payment PDF** (wave 2) — 15th report type (`aia_g702`), `/cost/g702` page, `src/analytics/aia_g702.py`, 15 tests. Completes AIA billing pair (G702 cover + G703 continuation from v3.7).
- **AACE MIP 3.1 + 3.2** (wave 3) — Static Logic Gross Approach + Dynamic Logic As-Is. `src/analytics/mip_observational.py`, 20 tests.
- **Per-WBS Gantt print page split** (wave 4) — `exportPdfByWbs()` on ScheduleViewer, one table per top-level WBS separated by page-break-before, critical highlighting.
- **Stats-consistency CI validator** (wave 5) — `scripts/check_stats_consistency.py` parses catalog headers + counts pages, fails CI on CLAUDE.md drift. Also fixed pre-existing drift (40→43 engines, 98→109 endpoints, 52→54 pages) and a doc-sync `--exit-status` typo.
- **Submission deliverables user guide** (wave 6) — `/docs/user-guide/submission-deliverables.md` covers SCL Protocol, AACE §5.3, AIA G702, AIA G703. 11 smoke tests.
- **AACE MIP 3.6 Collapsed As-Built** (wave 7) — Modified Subtractive Single Simulation. `src/analytics/mip_subtractive.py`, `/forensic/mip-3-6`, 16 tests.
- **AACE MIP 3.7 Windowed Collapsed As-Built** (wave 8) — reuses 3.6 engine per window. +14 tests.
- **AACE MIP 3.5 Additive Multiple Base** (wave 9) — Impacted As-Planned. `src/analytics/mip_additive.py`, `/forensic/mip-3-5`, 19 tests. **7 of 9 AACE forensic MIPs now covered**; 3.8 + 3.9 are subjective reconstruction methods, deferred to future work.

### Added — Frontend hardening (waves 10-15)

- **a11y warnings cleared** (wave 10) — 12 warnings → 0. GanttCanvas `<g>` keyboard handlers, modal dialog a11y, label-for associations in cost/narrative/pareto/ask pages. Also bumped `overrides.cookie` to `^0.7.0` to close a Dependabot security update.
- **Schedule-view cache invalidation** (wave 11) — `invalidate_analysis()` on both stores (`InMemoryStore` + `SupabaseStore`), `force=true` purges sibling baseline variants, new `DELETE /schedule-view/cache`. Fixed `InMemoryStore.clear()` not wiping `_analyses` / `_comparisons`. 11 tests.
- **CBS compare picker filter** (wave 12) — hides `cbs_element_count == 0` snapshots on `/cost/compare`; amber warning when fewer than 2 comparable snapshots exist.
- **Audit-trail IP + User-Agent** (wave 13) — `_client_ip()` honours `X-Forwarded-For` leftmost, `_user_agent()` helper, `_audit()` accepts optional `request`. 5 audit-writing endpoints capture IP + UA automatically. 18 tests.
- **Type-safety sweep round 1** (wave 14) — Programs + EVM surfaces: 15+ `any` eliminated, EVM list/detail interface split, 6 typed `api.ts` functions.
- **Type-safety sweep round 2** (wave 15) — all remaining 19 `any` removed across `/risk`, `/milestones`, `/settings`, `/alerts`, `/health`, `/ips`, `/recovery`, `/org`, `/schedule`, `/demo`, `/ask`. 9 new type groups in `api.ts` (Risk*, Organization*, IPS, Recovery, ValueMilestone*, Demo*). Latent bugs surfaced + fixed: alerts page was rendering an array as a count; health page had `Record<string, any>` fighting the canonical `ScheduleHealthResponse`.

### Added — i18n wiring (waves 16-26)

Layout chrome (wave 16) + 22 feature pages fully translated to en / pt-BR / es. **~650 new translation keys** across sidebar nav, form labels, chart titles, error fallbacks, toast messages, table column headers, and workflow-specific copy. Collapsed sidebar state keyed by invariant `titleKey` so it survives locale switching; per-page helper maps (org types, risk categories, action labels, status keys) resolve dynamic data via `$t`.

Pages wired, by wave:
- Wave 16: layout (sidebar + chrome + error boundary + keyboard shortcuts modal), 63 keys
- Wave 17: login + programs + projects, 36 keys
- Wave 18: settings + org, 37 keys
- Wave 19: pareto + contract + forensic, 65 keys
- Wave 20: recovery + ips + risk-register, 93 keys
- Wave 21: builder + scorecard + narrative, 57 keys
- Wave 22: cost + trends, 61 keys
- Wave 23: demo + visualization + org/[id], 72 keys
- Wave 24: milestones (biggest form-heavy page), 60 keys
- Wave 25: compare (biggest overall), 76 keys
- Wave 26: docs navigation (prose stays English per MDN/React-docs convention), 32 keys

Date + currency formatting now reads `$locale` so numbers and timestamps render in the active language.

### Tests

- 943 → 1084 passing (+141). 6 skipped. All 26 waves pass `npm run check` with 0 errors / 0 warnings.

### CI + tooling

- All 26 waves pushed direct to `main`, every wave green on CI / gitleaks / doc-sync / deploy-web / deploy-api.
- Doc-sync workflow fixed (wave 5): `git diff --exit-code` flag, `mcp` optional extra installed. Stats-consistency step added.

## [3.7.0] — 2026-04-17 — KB + P1 Feature Wave (9 waves: CBS, Rollup, Exec PDF, Risk Linkage, CBS Rehydration, BI, SCL+AACE, AIA G703, Gantt Export)

### Added — P1 feature wave follow-up (2026-04-17, Waves 7-9)
- **SCL Protocol submission PDF** (`scl_protocol`) — 7-section format per SCL Delay and Disruption Protocol (2nd ed., 2017) Appendix B: factual narrative, contractual milestone status, CP evolution, contemporaneous period analysis windows, responsibility attribution, concurrency assessment, records appendix. Opportunistically fetches delay attribution, forensic timeline (when baseline_id supplied), and schedule narrative.
- **AACE RP 29R-03 §5.3 forensic report PDF** (`aace_29r03`) — 8-section format per AACE RP 29R-03 §5.3 Documentation Requirements. Supports MIP 3.3 (observational) by default and MIP 3.4 (bifurcated half-step) when `options.bifurcated=true`. Fetches scorecard for §5.3.1 executive summary.
- **AIA G703 Continuation Sheet Excel export** — `GET /api/v1/projects/{id}/export/aia-g703?snapshot_id=X&retainage_pct=0.10&application_number=N&period_to=YYYY-MM-DD`. Maps CBS elements to G703 line items with columns A-J (item no., description, scheduled value, from previous, this period, materials stored, total completed+stored, % complete, balance, retainage). Accepts previous/current completion % overlays keyed by cbs_code (monotonic clamp). Renders openpyxl workbook with AIA-style header block, grand totals, and methodology note.
- **Gantt SVG/PNG export + enhanced print preview** — Schedule Viewer toolbar gains SVG and PNG export buttons alongside existing PDF/Print. SVG export serializes the live Gantt with inlined CSS and proper `xmlns` so the file renders standalone in Illustrator or browser preview. PNG export rasterizes via canvas at 2× device pixel ratio with white background. Print flow updated with `@media print` rules (`page-break-before: always`, `color-adjust: exact`) so future per-WBS page splits have the CSS ready.

### Tests
- +18 additional tests across Waves 7-9 (4 SCL+AACE integration, 14 AIA G703 unit + endpoint; Wave 9 is frontend-only, no vitest available — compile-level verification via `svelte-check` + production build). 925 → 943 passing (total session +56).

### Added — P1 feature wave (2026-04-17)
- **CBS snapshot compare** — `compare_cost_snapshots(a, b)` computes per-CBS-element budget/estimate/contingency deltas, totals delta, variance %, and status (changed/unchanged/added/removed). Exposed via `GET /api/v1/projects/{id}/cost/compare?a=<id>&b=<id>`. New `/cost/compare` page with project + snapshot pickers, KPI cards, CBS-Lvl1 variance bar chart, and top-movers table. Pydantic schemas: `CBSElementDeltaSchema`, `CostCompareResponse`.
- **Program rollup endpoint** — `GET /api/v1/programs/{id}/rollup` computes CPM + DCMA + health on the latest revision on-the-fly, returning critical path length, negative-float count, DCMA pass/fail, health rating, and trend direction (improving/stable/degrading with ±2-point deadband) vs the previous revision. `compute_program_rollup()` helper is plain-callable for embedding in other reports. Frontend `/programs/[id]` page now renders 8 KPI cards above the existing trend charts with a color-coded trend badge.
- **Executive Summary PDF** — wired `executive_summary` in `available-reports` endpoint, fixed broken `_wrap_html` call (method was unreachable pre-Wave 3), and enriched composition with three new optional sections: delay attribution (responsible-party breakdown with excusable / non-excusable / concurrent days), CBS cost variance (from the latest two snapshots), and program context (rollup trend). Auto-selected when available.
- **Risk register persistence + simulation↔register linkage** — InMemoryStore gains CRUD for risk entries; `GET /api/v1/projects/{id}/risk-register` now returns real entries plus summary (was hardcoded empty). New POST/DELETE endpoints for upsert + removal. `GET /api/v1/risk/simulations/{id}/register-entries` links entries whose `affected_activities` intersect the simulation's top-N sensitivity / criticality — semantic linkage (not FK) since sim id is ephemeral. `/risk/[id]` detail page renders a Linked Register Entries table with driver activities and max sensitivity/criticality per row.
- **SupabaseStore CBS rehydration** — `get_cost_snapshot` now reconstructs a full `CostIntegrationResult` from persisted `erp_sources` + `cbs_elements` + `cost_snapshots` rows. `/cost/compare` works end-to-end on Supabase backend (previously 404'd on prod). Closes the known caveat from the Wave 1 entry.
- **BI connector** — new `/api/v1/bi/*` namespace with flat, paginated (limit/offset) surfaces for Power BI / Tableau / Looker: `/bi/projects` (per-project KPIs computed on-the-fly), `/bi/dcma-metrics` (one row per project × metric for pivot tables), `/bi/activities` (flat activity list with CPM float + criticality). Response envelope `{items, pagination: {limit, offset, total, returned, has_next}}`.

### Tests
- +38 tests across six waves — 887 → 925 passing.

### Added — auto-generated doc catalogs
- `docs/api-reference.md` — 98 endpoints × 18 routers, grouped by tag with method / path / summary / response model / auth tier. Generated by `scripts/generate_api_reference.py`.
- `docs/methodologies.md` — 40 engines with AACE RP 29/49/52/57/41/65, ANSI/EIA-748, DCMA 14-point, SCL Protocol, GAO guide, PMI PMBOK citations. Generated by `scripts/generate_methodology_catalog.py`.
- `docs/mcp-tools.md` — all 22 MCP tools with signatures + Google-style docstring parsing + Claude Desktop/Code install config. Generated by `scripts/generate_mcp_catalog.py`.
- `docs/architecture.md` — refreshed for v3.6.0 reality (40 engines / 98 endpoints / 20 migrations / ERP cost tables ER diagram) with pointers to the generated catalogs and regeneration commands.

### Added — governance & contributor assets
- `SECURITY.md` — private vulnerability reporting (GHSA + email), supported versions, scope, sensitive data handling.
- `CODE_OF_CONDUCT.md` — Contributor Covenant v2.1 + domain-specific expectations (synthetic fixtures only, cite standards, treat schedules as evidence).
- `CONTRIBUTING.md` — Python version bump (3.12 → 3.14) and explicit links to the new governance files.
- `.github/ISSUE_TEMPLATE/{bug,feature,config}.yml` — structured issue forms with component / standard / persona fields.
- `.github/pull_request_template.md` — summary / standards / test plan / docs-touched checklist covering the three doc generators.

### Added — user guide
- `docs/user-guide/` — six focused walkthroughs (611 lines): README index, getting-started quickstart, schedule-viewer feature tour, analysis-workflow forensic pipeline (DCMA → CPA → TIA → EVM → Monte Carlo → Narrative), cost-integration CBS flow, mcp-integration for Claude setup.

### Changed
- README header nav: now links the user guide, API reference, methodologies, MCP tools, Contributing, and Changelog (previously pointed Changelog to BUGS.md by mistake).
- `src/api/app.py` version string bumped to `3.7.0-dev` in FastAPI title and Sentry release — so the generated OpenAPI spec reflects the current branch.

### Stats
- Doc lines added: ~2,300 (catalogs + governance + user guide)
- Zero production code changes; CI green across all 7 commits

## [3.6.0] — 2026-04-16 — Gantt Stability + Intelligence Pages

### New Engines
- **health_score** (38th) — composite schedule health rating across DCMA/CPM/float/EVM dimensions
- **early_warning** (39th) — anomaly detection and proactive alerting across schedule updates
- **nlp_query** (40th) — natural-language query routing via Claude API (summary-based, no raw data egress)

### New Pages
- `/health` — schedule Health Score dashboard
- `/ask` — NLP Query page (conversational schedule intelligence)
- `/alerts` — Early Warning indicators (GAO 12-rule engine) with severity-sorted cards + impact chart

### Schedule Viewer — Stability
- Gantt stability refactor — eliminated re-render flicker, consolidated event wiring
- `schedule_view` cache — projects + baselines memoized per session, reduces refetches
- EVM S-Curve chart (11th chart component) — schedule + cost S-curve overlay with forecasts
- **Resource Histograms** (Wave 7) — collapsible panel below Gantt, as-scheduled demand curves per resource

### Architecture
- Multi-domain adapter protocols — cost, schedule, risk, reporting, resource interfaces (`src/integrations/`)
- API modularization complete — `app.py` 4870 → 166 lines across 18 routers
- 7 adapters + ERP-ready cost tables (3 new migrations, total 20)

### API hardening & persistence (P1 completion)
- **NLP /ask** — NLPQueryRequest/Response schemas, `@limiter.limit("5/minute")`, generic error in production, Claude Sonnet 4.6.
- **CBS upload persistence** — `save_cost_upload` / `list_cost_snapshots` / `get_cost_snapshot` on both InMemoryStore and SupabaseStore (writes to `erp_sources`, `cbs_elements`, `cost_snapshots`).
- **GET /api/v1/projects/{id}/cost/snapshots** — list prior CBS uploads with totals.
- **Narrative PDF report** — new report type: `generate_narrative_report` + WeasyPrint styling with severity badges.
- **GET /api/v1/projects/{id}/schedule-view/resources** — as-scheduled resource profiles for histogram rendering.

### Frontend Polish
- Dashboard quick actions (upload, view schedule, scorecard, trends, narrative)
- Dark mode extended to authenticated section (46/46 pages complete)
- New `ResourceHistogramPanel.svelte` in ScheduleViewer/ folder — lazy-fetch, per-resource ResourceChart.

### Testing & Tooling
- E2E tests use regex for version and engine count — no more hardcoded values
- npm deps bumped: svelte 5.55.2, @sveltejs/kit 2.57.0, vite 8.0.7
- Ruff format + lint cleanup across 17 files
- +17 tests across NLP (5), cost persistence (6), narrative PDF (3), resource profiles (7)

### Stats
- **40 engines + 1 export**, **98 endpoints**, **887 tests**, **52 pages**, 22 MCP tools, **20 migrations**, 11 chart components
- Version bump: pyproject.toml `3.0.0 → 3.6.0`, web/package.json `1.0.0-dev → 3.6.0`

## [3.5.0] — 2026-04-07 — Cost-Schedule Intelligence

### New Engines
- **schedule_metadata** (34th) — extract update#, revision, type (MPS/IMS/CMAR/baseline), scheduling options from filename + XER data
- **schedule_trends** (35th) — period-over-period evolution tracking with auto-insights (AACE RP 29R-03)
- **cost_integration** (36th) — CBS/WBS correlation from Excel budget files (AACE RP 10S-90)
- **narrative_report** (37th) — structured text generation for claims and status reports

### Schedule Viewer Enhancements
- Virtual scrolling — GanttCanvas + WBSTree + activity table render only visible rows (10K+ activities supported)
- Drag-to-pan — mouse drag scrolls Gantt both axes
- Weekend shading — Sat/Sun gray bands on timeline
- Holiday shading — P6 calendar exceptions (amber bands on weekday holidays)
- Baseline variance badges — +Xd/-Xd indicators on slipped activities
- PDF export — print dialog with full SVG Gantt
- Column configuration — 23 columns, show/hide panel (Type, LS, LF, BL Start/Finish, Constraint, Start/Finish Variance)
- WBS filter — dropdown in activity table for WBS path filtering
- WBS path tooltip — full hierarchy path, numeric-only codes filtered
- Date axis — min 48px spacing prevents label overlap, adaptive format

### New Pages
- `/trends` — 7 bar charts (scope, completion, float, CP, neg float, density, quality score) + insights panel
- `/narrative` — structured narrative report with severity-tagged sections + copy-to-clipboard
- `/pareto` — cost-duration trade-off scatter chart with Pareto frontier
- `/cost` — CBS Excel upload, KPI cards, WBS budget chart, CBS-WBS mapping table
- `/programs` — program index page with revision counts

### Security
- Fixed CORS wildcard bypass in global exception handler (was overriding whitelist on 5xx)
- API key persistence — Supabase `api_keys` table with RLS (migration 017), in-memory fallback
- Rate limiting — @limiter.limit() on 7 endpoints (upload 10/m, auth 5/m, compute 5-10/m)
- Error handler — generic message in production, detailed only in development
- Upload drop zone — keyboard accessible (Enter/Space)

### Frontend Polish
- Dark mode — 45/46 pages (batch fix with Tailwind dark: classes)
- 8 KPI summary cards (added avg float, constraint count)
- Cross-navigation links (Scorecard, Compare, Trends from schedule page)
- Clickable predecessors/successors in activity detail (network navigation)
- Metadata tags on upload page (color-coded: MPS, DRAFT, FINAL, BASELINE)
- Upload quality indicators (baseline coverage, retained logic, progress override)
- Dashboard updated (stats, capabilities, Trends quick action, project tags)
- Fixed 4 missing page titles (EVM, Risk)

### Bug Fixes
- BUG-020: WBS tree full path tooltip + numeric code filter
- BUG-021: Date axis label overlap on day zoom (min 48px spacing)
- BUG-022: Dependency lines to collapsed rows (fixed by virtual scrolling)
- BUG-023: /programs added to sidebar + index page
- BUG-024: /demo already in sidebar (false report)

### Documentation
- Gap assessment v3.3 (persona journeys, security audit, cost data exploration)
- BUGS.md fully updated (10+ items marked done)

### Stats
- **37 engines + 1 export**, 84 endpoints, **810+ tests**, 49 pages, 22 MCP, 17 migrations
- Tested with 83 sandbox schedules (21 MPS + 34 IMS + 28 CMAR) + CBS cost data ($3.6B)

## [3.2.0] — 2026-04-07 — Schedule Viewer

### Added
- **Interactive Schedule Viewer** — production-grade Gantt chart for P6 schedules
  - ScheduleViewer component suite (6 files in `web/src/lib/components/ScheduleViewer/`)
  - Collapsible WBS tree panel with activity counts and hierarchy navigation
  - SVG Gantt bars with status coloring (critical=red, active=blue, complete=green)
  - Progress overlay bars (% complete as filled portion)
  - Milestone diamond shapes for finish milestones
  - Date axis with Day/Week/Month zoom levels
  - Data date marker (amber dashed line)
  - Baseline comparison bars (gray dashed, below current bars)
  - Float bars (amber, extending from early finish to late finish)
  - Sliding right detection (amber arrow for delayed activities)
  - Negative float indicators (red dashed border)
  - SVG bezier dependency lines (FS/FF/SS/SF) with arrow heads
  - Critical Path Only filter toggle
  - Show Float / Show Baseline / Dependencies toggles
  - Interactive tooltip bar showing activity details on hover
  - Expand All / Collapse All controls
  - Summary KPI cards (activities, critical, complete%, neg float, milestones)
- `schedule_view` engine — WBS tree builder + activity flattener (`src/analytics/schedule_view.py`)
- `GET /api/v1/projects/{id}/schedule-view` endpoint with optional `?baseline_id=`
- `/schedule` frontend page with project + baseline selectors
- 13 backend tests for schedule view engine

### Polish (v3.2.0 continued)
- Cross-page "View Schedule" links on 7 analysis pages
- Schedule page auto-load from URL params (?project=&baseline=)
- Contextual quick links in Schedule toolbar (Project Detail, Scorecard, Anomalies)
- Enhanced lookahead: CSV export, completion rate KPI, inline progress bars
- Dashboard "Projects at a Glance" section (top 6 by health, sorted worst-first)
- Custom 404/error page with Go Back button, dark mode aware
- SEO meta tags (og:title, og:description, twitter:card)
- Keyboard shortcuts modal (press ?) — documents Ctrl+D, +/-, E, C, Esc
- Skip-to-content accessible link for screen readers
- robots.txt with API disallow and sitemap reference
- Sidebar version bumped to v3.2.0
- Landing page stats updated (33/80/761+)

### Schedule Viewer Enhancements (v3.2.0 continued)
- Fixed WBS tree: shows full name + short_name code with tooltip
- Fixed date axis: dynamic density (max 25 labels, adapts to schedule length)
- Standard columns added: WBS, Free Float (FF), Actual Start (AS), Actual Finish (AF), Remaining Duration
- Start/Finish variance vs baseline (color-coded late/early in detail panel)
- Activity detail panel: 18 fields + predecessors/successors + mini-timeline + progress bar
- Near-critical count (TF 1-10d) — summary card, filter, status pill
- Actual progress bars (green) for active + complete activities
- LOE activities: diagonal hatch pattern + dashed border
- Status filter: 9 options (All/Active/Not Started/Complete/Critical/Near-Crit/Neg Float/Milestones/Constrained)
- CSV export: 19 fields including WBS, Free Float, Constraint, Actual dates
- Enhanced SVG tooltips: remaining duration, free float, actual dates

### Platform Enhancements
- Sidebar reorganized: 6 sections matching scheduler workflow (Schedule→Claims→Risk→AI→Enterprise)
- EVM page: SPI/CPI gauge cards, inline S-Curve SVG, traffic light badges, EAC variance
- Compare page: visual diff bars (duration before/after, float erosion)
- Industry standards research: docs/SCHEDULE_SUBMISSION_STANDARDS.md (AIA/DCMA/AACE/SCL audit — 21/22 must-have columns)
- Dependencies updated: fastapi 0.135.3, uvicorn 0.44, sentry-sdk 2.57, vite 8.0.5

### Stats
- **33 analysis engines + 1 export module**, 22 MCP tools, **761+ tests**, 42 pages, ~95 session commits

### References
- AACE RP 49R-06 — Identifying Critical Activities
- GAO Schedule Assessment Guide
- DCMA 14-Point Assessment — Schedule structure

## [3.1.0] — 2026-04-06 — UX Polish

### Added
- Calendar validation engine — 9 checks, score 0-100, grade A-F (`src/analytics/calendar_validation.py`)
- `GET /api/v1/projects/{id}/calendar-validation` endpoint
- `/calendar-validation` frontend page with GaugeChart, PieChart, BarChart
- Delay attribution engine — party breakdown (Owner/Contractor/Shared/Third Party/Force Majeure)
- `GET /api/v1/projects/{id}/delay-attribution` endpoint with excusable/non-excusable totals
- `/delay-attribution` frontend page with PieChart, BarChart, stacked bar
- Dark mode with class-based toggling, localStorage persistence, system preference detection
- Global CSS overrides automatically darken all 41 pages without per-page edits
- Loading skeletons (Skeleton + AnalysisSkeleton components) on 24 analysis pages
- Breadcrumb navigation — global component, auto-inferred from URL path
- Collapsible sidebar sections (Analysis, Intelligence, Enterprise) with localStorage state
- Active link highlighting in sidebar (blue bg for current page)
- i18n expansion: 40+ new keys for PT-BR and ES (page titles, common UI labels)
- 2 new MCP tools: `validate_calendars_tool`, `compute_delay_attribution_tool` (21 total)
- 24 new backend tests (calendar validation 17, delay attribution 7)

### Stats
- **32 analysis engines + 1 export module**, 21 MCP tools, **734+ tests**, 41 pages

### References
- DCMA 14-Point Check #13 (calendar adequacy)
- AACE RP 29R-03, AACE RP 52R-06, SCL Protocol (delay attribution)
- AACE RP 49R-06 (calendar health assessment)

## [3.0.1] — 2026-04-06 — Frontend Coverage

### Added
- 8 new frontend pages closing all backend/frontend gaps:
  - `/anomalies` — Statistical outlier detection with ScatterChart + BarChart
  - `/root-cause` — Backwards network trace with dependency chain + TimelineChart
  - `/delay-prediction` — Activity risk scoring with ScatterChart + HeatMapChart
  - `/duration-prediction` — ML ensemble with GaugeChart + confidence range visual
  - `/benchmarks` — Cross-project percentile comparison with contribute flow
  - `/float-trends` — Shannon entropy + constraint accumulation analysis
  - `/reports` — PDF report hub with download cards for 7 report types
  - `/optimizer` — ES optimizer with convergence curve + activity shifts
- 5 new documentation sections (anomalies, root-cause, float-trends, optimizer, reports)
- 8 new E2E tests for interactive controls on new pages
- Landing page updated: 31 engines, 77 endpoints, 710+ tests, 15 capabilities
- Sidebar version bumped to v3.0.0

### Stats
- **39 frontend pages**, 10 SVG chart components, 67 E2E test cases

## [3.0.0] — 2026-04-05 — Full Lifecycle

### Added
- XER export/writer — round-trip fidelity, write modified/generated schedules back to P6 format (`src/export/xer_writer.py`)
- `GET /api/v1/projects/{id}/export/xer` download endpoint
- Benchmark-derived Monte Carlo priors — auto-generates PERT distributions from benchmark database (`src/analytics/benchmark_priors.py`)
- Evolution Strategies optimizer — (mu, lambda) ES for RCPSP optimization beyond greedy SGS (`src/analytics/evolution_optimizer.py`)
- `POST /api/v1/projects/{id}/optimize` endpoint with convergence history
- 4D visualization data engine — WBS spatial grouping x CPM temporal positioning (`src/analytics/visualization.py`)
- `GET /api/v1/projects/{id}/visualization` endpoint with color-coded activity grid
- MCP Server: 18th tool `export_xer`, 19th tool `optimize_schedule_es`
- 44 new tests (710 total)

### Stats
- **30 analysis engines + 1 export module**, 19 MCP tools, **710 tests**

### References
- Oracle Primavera P6 XER Format (round-trip export)
- AACE RP 57R-09 enhanced with Bayesian benchmark priors
- Loncar (2023) Evolution Strategies, Beyer & Schwefel (2002) ES Theory
- Hartmann & Kolisch (2000) RCPSP benchmarks

## [2.3.0] — 2026-04-05 — Schedule Optimization

### Added
- Resource leveling engine — RCPSP via Serial SGS with 4 priority rules (`src/analytics/resource_leveling.py`)
- `POST /api/v1/projects/{id}/resource-leveling` endpoint with activity shifts and resource profiles
- ML schedule generation — template-based with stochastic duration estimation (`src/analytics/schedule_generation.py`)
- `POST /api/v1/schedule/generate` endpoint for 4 project types (commercial, industrial, infrastructure, residential)
- Conversational schedule builder — NLP-driven generation with Claude API + keyword fallback (`src/analytics/schedule_builder.py`)
- Generated schedules fully compatible with all 22 analysis engines
- MCP Server: 15th tool `level_resources`, 16th tool `generate_schedule`, 17th tool `build_schedule_from_description`
- 53 new tests (666 total)

### Stats
- **22 analysis engines**, 17 MCP tools, **666 tests**

### References
- AACE RP 46R-11 (resource analysis), Kolisch (1996) Serial SGS
- Kelley & Walker (1959) CPM resource extension
- AbdElMottaleb (2025) ML for construction scheduling

## [2.2.0] — 2026-04-05 — Scenario Intelligence

### Added
- What-if simulator — deterministic + probabilistic scenario analysis with CPM re-runs (`src/analytics/whatif.py`)
- `POST /api/v1/projects/{id}/what-if` endpoint with % adjustments, WBS targeting, P-values
- Time-cost Pareto analysis — multi-scenario trade-off frontier identification (`src/analytics/pareto.py`)
- `POST /api/v1/projects/{id}/pareto` endpoint with Pareto-optimal frontier computation
- Schedule scorecard — 5-dimension weighted letter grades A-F (`src/analytics/scorecard.py`)
- `GET /api/v1/projects/{id}/scorecard` endpoint aggregating DCMA, health, risk, logic, completeness
- ML duration prediction — RF+GB trained on benchmark database for project duration forecasting (`src/analytics/duration_prediction.py`)
- `GET /api/v1/projects/{id}/duration-prediction` endpoint with confidence intervals
- MCP Server: 13th tool `run_what_if`, 14th tool `get_scorecard`
- 66 new tests (613 total)

### Stats
- **19 analysis engines**, 14 MCP tools, **613 tests**

### References
- AACE RP 57R-09 (scenario analysis), AACE RP 36R-06 (cost classification)
- PMI PMBOK 7 S4.6, Kelley & Walker (1959), AbdElMottaleb (2025)
- GAO Schedule Assessment Guide, DCMA 14-Point Assessment

## [2.1.0] — 2026-04-05 — Prediction & Benchmarks

### Added
- Half-step bifurcation analysis (AACE RP 29R-03 MIP 3.4) — separates delay into progress effect vs revision effect (`src/analytics/half_step.py`)
- `POST /api/v1/forensic/half-step` endpoint for standalone bifurcation analysis
- `ForensicAnalyzer(bifurcated=True)` mode for integrated MIP 3.4 CPA
- MCP Server: 10th tool `run_half_step` for Claude integration
- Forensic PDF report: bifurcation section with progress/revision table and KPIs
- Frontend: bifurcation chart (progress blue vs revision amber bars) on forensic timeline page
- Frontend: progress/revision columns in forensic window analysis table
- `HalfStepResponse` types and API client in frontend
- 32 new tests for half-step analysis (classification, schedule creation, full analysis, real XER files, edge cases, PDF rendering)
- Delay prediction engine — activity-level risk scoring with 35 features, weighted multi-factor model, SHAP-like explainable risk factors (`src/analytics/delay_prediction.py`)
- `GET /api/v1/projects/{id}/delay-prediction` endpoint with optional baseline enhancement
- **ML-enhanced delay prediction** — Random Forest + Gradient Boosting ensemble via `?model=ml` parameter (Gondia et al. 2021, Breiman 2001, Friedman 2001)
- `MLDelayModel` class with auto-training from rule-based teacher, batch prediction, and feature importance extraction
- `scikit-learn>=1.4` as optional `[ml]` dependency (`pip install meridianiq[ml]`)
- 20 new ML prediction tests (model training, ensemble scoring, feature importances, fallback behavior)
- MCP Server: 11th tool `predict_delays` for Claude integration
- Zero-Step analysis (Ron Winter PS-1197) — backward half-step for concurrent delay detection
- `analyze_half_step(include_zero_step=True)` with `concurrent_delay_indicator`
- Frontend: risk scatter chart (ScatterChart) on delay prediction tab
- 7 new zero-step tests
- Benchmark database — anonymized cross-project comparison with percentile ranking (`src/analytics/benchmarks.py`)
- Supabase migration 013: `benchmark_projects` + `benchmark_metrics` tables with public-read RLS
- `POST /api/v1/benchmarks/contribute`, `GET /benchmarks/compare/{id}`, `GET /benchmarks/summary` endpoints
- MCP Server: 12th tool `extract_benchmarks`
- 18 new benchmark tests
- SECURITY DEFINER RPCs: `delete_user_data`, `set_project_sandbox`, `contribute_benchmark`
- GDPR data deletion endpoint: `DELETE /api/v1/user/data` (cascade delete all user data)
- Programs table RLS policies (was missing — critical security gap fixed)
- Reports table RLS policies added
- Supabase migration 014: security RPCs + RLS fixes
- All 14 Supabase migrations verified and registered in production

### Stats
- **16 analysis engines**, 12 MCP tools, **547 tests**, 14 migrations, 100 benchmarks seeded

## [2.0.0] — 2026-04-02 — AI

### Added
- NLP schedule queries via Claude API (`POST /api/v1/projects/{id}/ask`)
- Anomaly detection engine — IQR/z-score outlier detection (`GET /api/v1/projects/{id}/anomalies`)
- Root cause analysis — backwards network trace to delay origin (`GET /api/v1/projects/{id}/root-cause`)
- MCP Server with 9 tools for Claude Code integration (`src/mcp_server.py`)
- API keys for programmatic access (self-service CRUD endpoints)
- Float entropy metric — Shannon entropy of float distribution
- Constraint accumulation rate — detect constraint growth between updates
- JSON/CSV export endpoints for structured data download
- Monthly review PDF report (6th report type)
- 6 reusable SVG chart components (BarChart, PieChart, GaugeChart, ScatterChart, WaterfallChart, TimelineChart)
- Charts integrated into 8 frontend pages (project detail, dashboard, compare, EVM, contract, IPS, recovery)
- Sandbox mode for test data isolation (upload toggle + API filter)
- CORS whitelist (replaced wildcard `*`)
- Security headers middleware (HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy)
- Rate limiting via slowapi (60 req/min default)
- Upload file size limit (50MB)
- RLS policy fixes for 5 tables that had zero policies (migration 011)
- API keys table with RLS (migration 012)
- Deploy checklist document (`docs/DEPLOY_CHECKLIST.md`)

### Fixed
- Forensic PDF report: ForensicAnalyzer constructor args + window attribute path
- Lint: removed unused imports across new modules

## [1.1.0] — 2026-03-30 — UX Maturity

### Added
- Value milestones frontend page with CRUD
- Compare page: manipulation scoring badges (Normal/Suspicious/Red Flag)
- Sidebar grouping (Analysis / Enterprise / Settings sections)
- Toast notification system (`$lib/toast.ts` + `ToastContainer.svelte`)
- i18n wiring connected to landing, upload, and dashboard pages
- Projects list: search, sort by name/activities/relationships, filter

## [1.0.0] — 2026-03-29 — Enterprise

### Added
- Organizations with roles and memberships
- Project sharing with granular permissions
- IPS Reconciliation (master + sub-schedule alignment per AACE RP 71R-12)
- Recovery schedule validation (compression analysis)
- Audit trail logging
- Multi-format support (Microsoft Project XML via native parser)
- Value milestones (commercial value, payment triggers)

## [0.9.0] — 2026-03-28 — Polish

### Added
- Responsive sidebar with mobile hamburger menu
- CI/CD pipeline (GitHub Actions: test, lint, build, deploy)
- E2E tests (Playwright, 25 tests)
- Sentry + PostHog integration
- Documentation site (/docs route, 10 sections)
- Onboarding flow (3-step guided)
- i18n infrastructure (EN, PT-BR, ES)
- Anonymous demo mode (/demo route)
- Account settings page
- Cold start fix (retry with backoff + warm-up banner)

## [0.8.0] — 2026-03-27 — Intelligence

### Added
- Float trend tracking across sequential uploads
- Early Warning System (12 configurable alert rules)
- Schedule Health Score (composite 0-100 metric)
- PDF Reports (5 types via WeasyPrint)
- Auto-pipeline (upload → parse → validate → compute → alert)

## [0.7.0] — 2026-03-26 — Identity

### Added
- Google + Microsoft + LinkedIn OAuth via Supabase Auth
- Row Level Security (RLS) policies
- API authentication (Bearer token)
- Frontend auth flow (login, OAuth redirect, session, logout)

## [0.6.0] — 2026-03-25 — Cloud

### Added
- Supabase PostgreSQL (persistent data, RLS)
- Supabase Storage (XER files, PDFs)
- Fly.io deployment (Docker container)
- Cloudflare Pages deployment (SvelteKit)

## [0.5.0] — 2026-03-24 — Risk

### Added
- Monte Carlo QSRA simulation (AACE RP 57R-09)

## [0.4.0] — 2026-03-23 — Controls

### Added
- Earned Value Management (SPI, CPI, EAC, S-Curve per ANSI/EIA-748)

## [0.3.0] — 2026-03-22 — Claims

### Added
- Time Impact Analysis (AACE RP 52R-06)
- Contract Compliance checking

## [0.2.0] — 2026-03-21 — Forensics

### Added
- Forensic CPA / Window Analysis (AACE RP 29R-03)

## [0.1.0] — 2026-03-20 — Foundation

### Added
- XER Parser (streaming, encoding detection, composite keys)
- CPM Calculator (NetworkX forward/backward pass)
- DCMA 14-Point Assessment
- Schedule Comparison engine
- SvelteKit frontend (initial routes)
