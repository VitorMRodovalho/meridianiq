# MeridianIQ

Open-source P6 XER schedule intelligence platform. Python/FastAPI backend, SvelteKit frontend, Supabase PostgreSQL.

## Build & Run

```bash
# Backend
pip install -e ".[dev]"
python -m uvicorn src.api.app:app --reload --port 8080

# Frontend
cd web && npm install && npm run dev -- --port 5173

# Docker (API only — no web/Dockerfile yet)
docker compose up meridianiq-api
```

## Test

```bash
# Backend (870+ tests)
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

- **47 analysis engines** in `src/analytics/` + 1 export module in `src/export/` — each standalone, no cross-dependencies
- **API**: FastAPI with 121 endpoints under `/api/v1/` across 23 routers, rate-limited critical endpoints
- **Frontend**: SvelteKit + Tailwind v4, 54 pages, Svelte 5 runes ($state, $derived, $effect), dark mode, i18n (en/pt-BR/es), keyboard shortcuts (?)
- **Database**: Supabase PostgreSQL with RLS, 24 migrations in `supabase/migrations/`
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
- Charts: `web/src/lib/components/charts/` — 11 reusable SVG components (BarChart, PieChart, GaugeChart, ScatterChart, WaterfallChart, TimelineChart, ResourceChart, HeatMapChart, ParetoChart, GanttChart, EVMSCurveChart)
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

## Workflow

- Run relevant tests after changes, not always the full suite
- Reference `BUGS.md` for known issues before investigating errors
- See `docs/archive/v06-planning/ROADMAP_v06_to_v20.md` for roadmap context
- Version: v4.0.0 (released 2026-04-19) — "Materialized Intelligence" (47 engines + 1 export module, 22 MCP tools, 1350 tests, 11 chart components, 121 endpoints across 23 routers, 54 pages, 15 PDF report types, 25 Supabase migrations). Cycle 1 delivered in 7 waves: **W0** governance + hardening (migration 021 `audit_log.user_agent`; ADRs 0006–0008 backfilled; `defusedxml` XXE fix + UTF-16 BOM in `msp_reader.py`; `programs UNIQUE(user_id, lower(name))` + upsert; `_persist_schedule_data` transactional `status=pending|ready|failed`; ADR-0013 WebSocket hardening with server-generated `job_id` + 4401/4403/4404 close codes + 15-min reaper). **W1** materialization foundation (migration 023 `schedule_derived_artifacts` with 9-column provenance, quadruple RLS, `UNIQUE NULLS NOT DISTINCT`, `ON DELETE CASCADE`; ADR-0014 `input_hash` canonical contract). **W2** async materializer (asyncio.Task + Semaphore(1) + ProcessPoolExecutor spawn; upload returns `202 { job_id, ws_url }`; ADR-0015). **W3** lifecycle phase inference (`src/analytics/lifecycle_phase.py`, 5+1 taxonomy with numeric confidence; override + sticky lock; ADR-0016). **W4** calibration + gate (ADR-0009 Amendments 1+2 pre-registered + outcome; 103-XER sandbox; gate failed at every threshold for distinct sub-gate reasons; engine characterised as reliable construction-vs-non-construction detector; hysteresis 0 phase flips across 4 multi-revision programs; `docs/adr/0009-w4-outcome.md` published; path A fallback activated per the pre-committed branch). **W4 collateral** — `_json_safe` P1 fix at store boundary (datetime serialization gap that was silently flipping prod projects to `failed`); prod operational darkness closed (88 derived-artifact rows + 88 audit rows). **W5/W6** path A carry-over (v3.9 tail debt) — `progress_callback` wiring in `src/analytics/evolution_optimizer.py` (parity with `risk.MonteCarloSimulator.simulate`) + `web/src/lib/composables/useWebSocketProgress.ts` composable (Readable store + auto-close + `markDone/markError` for race-free terminal signaling) wired into `web/src/routes/risk/+page.svelte` with inline progress bar + 7 new i18n keys × 3 locales. **NOT shipped this cycle (pre-committed deferral)**: `src/analytics/lifecycle_health.py` — revisitable in a future cycle via ruleset v2 tuning (contributor dataset from issue #13) or binary-detector + preview-flag redesign; ADR-0010 stays reserved.
- CI: Python 3.14, Node 24, Vite 8, TypeScript 6, GitHub Actions v6
- Dockerfile: Python 3.13-slim (pyiceberg lacks 3.14 wheel)
