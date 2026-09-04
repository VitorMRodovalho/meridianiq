# MeridianIQ

Open-source P6 XER schedule intelligence platform. Python/FastAPI backend, SvelteKit frontend, Supabase PostgreSQL.

## Build & Run

```bash
# Backend
pip install -e ".[dev]"
python -m uvicorn src.api.app:app --reload --port 8080

# Frontend
cd web && npm install && npm run dev -- --port 5173

# Docker (API + web — `web/Dockerfile` builds a static Nginx image)
docker compose up
```

## Test

```bash
# Backend (1350+ tests)
python -m pytest tests/ -q

# Frontend type check
cd web && npm run check

# Full verification
python -m pytest tests/ -q && cd web && npm run build
```

## Lint & Format

```bash
ruff check src/ tests/          # lint
ruff format src/ tests/         # format
mypy src/ --strict              # type check
```

## Architecture

- **48 analysis engines** in `src/analytics/` + 1 export module in `src/export/` — each standalone, no cross-dependencies
- **API**: FastAPI with 129 endpoints under `/api/v1/` across 25 routers, rate-limited critical endpoints
- **Frontend**: SvelteKit + Tailwind v4, 55 pages, Svelte 5 runes ($state, $derived, $effect), dark mode, i18n (en/pt-BR/es), keyboard shortcuts (?)
- **Database**: Supabase PostgreSQL with RLS, 29 migrations in `supabase/migrations/`
- **Auth**: Supabase Auth (Google + LinkedIn + Microsoft OAuth), ES256 JWT
- **Storage**: Supabase Storage for XER files and PDFs
- **Deploy**: Fly.io (backend, port 8080) + Cloudflare Pages (frontend)

## Code Standards

- Python 3.14+, type hints on all public functions
- Pydantic v2 models for all API request/response schemas
- Every analysis methodology must cite its published standard (AACE RP, DCMA, etc.)
- No client names, proprietary data, or credentials in code
- Test fixtures must be synthetic — never commit real project data
- MIT license header awareness — no GPL dependencies

## Key Patterns

- Parser: `src/parser/xer_reader.py` — streaming, encoding detection, composite keys
- CPM: NetworkX digraph, forward/backward pass
- Store: `src/database/store.py` — Supabase client abstraction
- Auth: `src/api/auth.py` — JWT verification via JWKS, `optional_auth` decorator
- Frontend auth: `web/src/lib/stores/auth.ts` — lazy init to avoid circular deps
- Charts: `web/src/lib/components/charts/` — 11 reusable SVG components (BarChart, PieChart, GaugeChart, ScatterChart, WaterfallChart, TimelineChart, ResourceChart, HeatMapChart, MultiRevisionSCurveChart, GanttChart, EVMSCurveChart)
- ScheduleViewer: `web/src/lib/components/ScheduleViewer/` — Interactive Gantt with WBS tree, baseline bars, float, dependencies
- UI: Breadcrumb, Skeleton, AnalysisSkeleton, ToastContainer, ThemeToggle components
- Theme: `web/src/lib/stores/theme.ts` — dark mode with localStorage + system preference
- MCP Server: `src/mcp_server.py` — 22 tools for Claude integration via FastMCP
- NLP: `src/analytics/nlp_query.py` — Claude API integration, sends summary not raw data
- Root Cause: `src/analytics/root_cause.py` — backwards network trace via NetworkX

## Environment Variables

Required in `.env`:
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `FLY_API_TOKEN` (deploy only)

## Known Gotchas

- Supabase uses port 6543 (pooler), not 5432
- JWT algorithm is ES256 (not HS256/RS256) — JWKS auto-detects
- WeasyPrint needs system deps: libpango, libcairo (in Dockerfile)
- Fly.io cold start ~10s causes 502+CORS on first request (BUG-007)
- `web/src/lib/stores/auth.ts` uses dynamic import to break circular dependency
- CORS origins are configurable via `ALLOWED_ORIGINS` env (comma-separated); defaults cover localhost + `meridianiq.vitormr.dev`
- `api_keys` table schema: columns are `id` (bigint), `key_id`, `key_hash`, `user_id`, `name`, `created_at`, `revoked_at`. See ADR-0017 if you find legacy 012-style columns (`key_prefix`, `is_active`, `expires_at`).

## Workflow

- Run relevant tests after changes, not always the full suite
- Reference `BUGS.md` for known issues before investigating errors
- See `docs/archive/v06-planning/ROADMAP_v06_to_v20.md` for roadmap context
- Version: **v4.3.0 (released 2026-05-09)** — "Z-shape consolidation (Cycle 5 close per ADR-0024)". Current head `21871bb` is **Cycle 6 W3 wave 4 in-flight** per ADR-0025 (H-shape: forced Bucket B hygiene W0-W1 + W2 HARD GATE on demand-validation evidence + conditional W3-W5); next release tag will be v4.4.0 or v4.3.1. W2 GATE outcome: **cosmetic-met**, operator-declared outside the pre-registered Pathway A/B/C set (the label "Pathway D" is not defined by ADR-0025 and has been retired from the record); Cycle 7 inherits Cycle 6.5 obligations. ADR-0028 (PR #242, inert until 2026-09-30) would replace it with a real Pathway B discharge, still cosmetic. See ADR-0028 §"Prior record reconciliation". Cycle 6 PRs merged since v4.3.0: #129 (Bucket A pre-W0 floor bumps) / #135 + #136 (ADR-0025 + docs) / #137 (Bucket B floor bumps: `fastapi>=0.136.1`, `pydantic>=2.13.4`, `@sveltejs/kit>=2.59.1`, `vite>=8.0.5`, `svelte>=5.55.7`, `mcp<2`) / #142 (canonical-hash standalone CI step — partial #131) / #145 (fetch timeout + chart NaN guards — closes #144) / #147 (milestones HTML5 datalist picker) / #148 (recovery ad-hoc scenario upload) / #152 (direction-aware change-point markers — closes #105 + refs #110). Criterion-4 progress: 1/6 frontend a11y cluster items closed. Cycle 6 follow-ups filed: #138-#141 (P2) + #149/#150/#151 (P2 from PR #148) + #117/#119/#120/#121 (Cycle 5 carryover P3). Repo baseline at v4.3.0 + W3 wave 4: 48 analysis engines + 1 export module, 129 API endpoints across 25 routers, 55 SvelteKit pages, **11 hand-crafted SVG chart components** (dead-code ParetoChart.svelte deleted in the W2 viz wave; the live /pareto frontier renders via ScatterChart), 29 Supabase migrations, 22 MCP tools, 15 PDF report types, **1687 backend tests + 64 Vitest + 64 Playwright E2E**. mypy `--strict` baseline: 350 errors across 47 files (#121 tracks systematic cleanup). **Frontend dep floors current:** svelte 5.55.7, sveltekit 2.59.1, vite 8.0.11, vitest 4.1.5. **Backend dep floors current:** pydantic 2.13.4 (<2.14 cap), fastapi 0.136.1, mcp 1.27.1 (<2 cap), PyJWT 2.12.1 (CVE), weasyprint 68.0 (CVE), starlette 1.0.0 (transit). v4.2.0 baseline: "β-honest path-A discipline" (Cycle 3 close-arc + Cycle 4 close per ADR-0021 / 0022 / 0023). v4.1.0 (released 2026-04-26) — "Consolidation + Primitive (Cycle 2 close)" minor over v4.0.2. 4-wave consolidation cycle per ADR-0019: NO deep, ships three primitives every future deep depends on. **W0** hygiene — `RATE_LIMIT_READ` (30/min) on `POST /api/v1/jobs/progress/start`; slowapi added to `[dev]` extras (CI now exercises real `@limiter.limit`); `useWebSocketProgress.destroy()` helper closing the F1 latent listener-leak v4.0.1 deferred. **W1** WS resilience — server heartbeat at 30s opt-in via `?hb=1` (re-checks JWT `exp` AND validates API keys via `validate_api_key()`; closes 4401 on expiry/revocation; defensive `queue.get_nowait()` drain after timeout); composable `recoveryPoller` hook + `'recovering'` status + `recoveryAborted` cancellation flag (D4 composable contract; backend `job_id` index on `RiskStore` + by-job endpoint deferred — recoveryPoller hook is dormant for real users until that lands). **W2** B2 honesty-debt closure — authoritative `is_construction_active: bool|None` tri-state on `LifecyclePhaseInferenceSchema` and `LifecyclePhaseSummary`; `Field(description=...)` markers on legacy `phase`/`effective_phase` for non-UI consumers (MCP, OpenAPI, CLI); `LifecyclePhaseCard.svelte` split UI (chip ABOVE phase, phase demoted + `(preview)` marker); 6 new i18n keys × 3 locales; W4 calibration post-mortem at `docs/calibration/lifecycle-phase-w4-postmortem.md` (with §D failure 19.8% vs 20% disclosed, per-phase N counts incl. closeout=0, LGPD/GDPR contributor anonymization checklist). **W3** calibration harness primitive — `tools/calibration_harness.py` (~470 LoC) with 3 abstractions (`Observation` validating confidence ∈ [0.0, 1.0] at boundary, `EngineAdapter` Protocol, `CalibrationProtocol` frozen dataclass with §B-§E params); CLI `python -m tools.calibration_harness` (`--protocol` REQUIRED — no default per W3 council); ADR-0020 with §"Decision" caveat that pipeline runs end-to-end but does NOT reproduce W4 numbers authoritatively (manifest archive pending operator action); `*_private.json` glob in `.gitignore`; CI lint extended to `tools/`. New ADRs in v4.1: 0017 (api_keys dedup, v4.0.2), 0018 (cycle cadence, v4.0.2), 0019 (Cycle 2 entry), 0020 (calibration harness primitive). Pre-registered success criteria 7/7 closed (criterion 7 = this release tag). v4.0.2 baseline: "Audit remediation" patch over v4.0.1. Lands the post-v4.0.1 work from the 2026-04-22 structural audit (closes #14/#16/#17/#18/#19/#22/#24, #8 not_planned, ADR-0017 + ADR-0018 added, `docs/audit/` 8 docs published, 19 audit regression tests). Specific deliveries: `OptimizeResponse` Pydantic schema + 3 contract regression tests (#14); `ALLOWED_ORIGINS` env (#19); shared rate-limit buckets in `src/api/deps.py` (#18); fail-closed API key lookups in production (#17); migration `026_api_keys_schema_align.sql` (#16, prod apply tracked as P0 #26); `app.py` reads version from `importlib.metadata` (no more hard-coded "4.0.0"); WS optimize test stabilized (28da1fd dropped racy "progress arrived" assertion); Dockerfile bump 3.14 reverted (df672d9 — pyiceberg wheel block); Python deps refreshed to current latest stable (`networkx` 3.4→3.6, `numpy` 2.0→2.4, `supabase` 2.10→2.29, `sentry-sdk` 2.20→2.58, `fastapi` 0.115→0.136, `anthropic` 0.85→0.97, `scikit-learn` 1.6→1.8, `pydantic` 2.10→2.13 — `TestByteExactPin` held); frontend deps refreshed (`vitest` ^3→^4, `jsdom` ^26→^29, `@sveltejs/kit`, `tailwindcss`, `posthog-js`, `svelte`, `typescript`, `vite`); **#22 i18n closure** — all 15 previously under-i18n pages translated across en/pt-BR/es in 6 batches (~402 keys × 3 locales). Schedule page got `ColDef.label`→`labelKey` refactor; TIA `responsibleParties` switched to `$derived()`; `exportCSV()` reads `$t()` at click time. Pending human action: #26 P0 prod migration apply, #27 ROADMAP.md author, #28 ADR-0017/0018 ratification. v4.0.1 baseline: "Track 1 polish" (1338 tests). v4.0.0 baseline: "Materialized Intelligence" (47 engines + 1 export module, 22 MCP tools, 1350 tests, 11 chart components, 121 endpoints across 23 routers, 54 pages, 15 PDF report types, 25 Supabase migrations). Cycle 1 delivered in 7 waves: **W0** governance + hardening (migration 021 `audit_log.user_agent`; ADRs 0006–0008 backfilled; `defusedxml` XXE fix + UTF-16 BOM in `msp_reader.py`; `programs UNIQUE(user_id, lower(name))` + upsert; `_persist_schedule_data` transactional `status=pending|ready|failed`; ADR-0013 WebSocket hardening with server-generated `job_id` + 4401/4403/4404 close codes + 15-min reaper). **W1** materialization foundation (migration 023 `schedule_derived_artifacts` with 9-column provenance, quadruple RLS, `UNIQUE NULLS NOT DISTINCT`, `ON DELETE CASCADE`; ADR-0014 `input_hash` canonical contract). **W2** async materializer (asyncio.Task + Semaphore(1) + ProcessPoolExecutor spawn; upload returns `202 { job_id, ws_url }`; ADR-0015). **W3** lifecycle phase inference (`src/analytics/lifecycle_phase.py`, 5+1 taxonomy with numeric confidence; override + sticky lock; ADR-0016). **W4** calibration + gate (ADR-0009 Amendments 1+2 pre-registered + outcome; 103-XER sandbox; gate failed at every threshold for distinct sub-gate reasons; engine characterised as reliable construction-vs-non-construction detector; hysteresis 0 phase flips across 4 multi-revision programs; `docs/adr/0009-w4-outcome.md` published; path A fallback activated per the pre-committed branch). **W4 collateral** — `_json_safe` P1 fix at store boundary (datetime serialization gap that was silently flipping prod projects to `failed`); prod operational darkness closed (88 derived-artifact rows + 88 audit rows). **W5/W6** path A carry-over (v3.9 tail debt) — `progress_callback` wiring in `src/analytics/evolution_optimizer.py` (parity with `risk.MonteCarloSimulator.simulate`) + `web/src/lib/composables/useWebSocketProgress.ts` composable (Readable store + auto-close + `markDone/markError` for race-free terminal signaling) wired into `web/src/routes/risk/+page.svelte` with inline progress bar + 7 new i18n keys × 3 locales. **NOT shipped this cycle (pre-committed deferral)**: `src/analytics/lifecycle_health.py` — revisitable in a future cycle via ruleset v2 tuning (contributor dataset from issue #13) or binary-detector + preview-flag redesign; ADR-0010 stays reserved.
- CI: Python 3.14, Node 24, Vite 8, TypeScript 6, GitHub Actions v6
- Dockerfile: Python 3.13-slim — pinned because `supabase` pulls `storage3` → `pyiceberg` (transitive), and `pyiceberg` has no Python 3.14 wheel for slim Linux as of 2026-04-26 (build-from-source fails on missing system headers). Bump to 3.14 only after pyiceberg ships 3.14 wheels OR storage3 drops the dep. Revert history: bumped to 3.14 in `f1bd4e2`, broke deploy, reverted in `df672d9`.

## Portfolio PMO (knowledge loop)

- This repo lives under Vitor's portfolio PMO at `~/projects` (the parent
  `CLAUDE.md` there governs PMO mode; machine-global skills at
  `~/.claude/skills/`, SSOT = `AI-PMO-Framework/skills/`).
- It carries a standing `[LL]` lessons-learned-intake issue; at the end of
  meaningful work sessions, log reusable lessons there (what worked, what
  should change in the framework/skills/kits) so the PMO can harvest them
  (`pmo-sync.sh harvest`).
