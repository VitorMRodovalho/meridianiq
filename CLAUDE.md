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
# Backend
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
- **API**: FastAPI with 144 endpoints under `/api/v1/` across 27 routers, rate-limited critical endpoints
- **Frontend**: SvelteKit + Tailwind v4, 56 pages, Svelte 5 runes ($state, $derived, $effect), dark mode, i18n (en/pt-BR/es), keyboard shortcuts (?)
- **Database**: Supabase PostgreSQL with RLS, 40 migrations in `supabase/migrations/`
- **Auth**: Supabase Auth (Google + LinkedIn + Microsoft OAuth), ES256 JWT
- **Storage**: Supabase Storage for XER files and PDFs
- **Deploy**: Fly.io (backend, port 8080) + Cloudflare Pages (frontend)

## Code Standards

- Python 3.12+ (`requires-python`; CI and the image run 3.15), type hints on all public functions
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
- Frontend auth: `web/src/lib/auth.ts` — lazy init to avoid circular deps
- Charts: `web/src/lib/components/charts/` — 11 reusable SVG components (BarChart, PieChart, GaugeChart, ScatterChart, WaterfallChart, TimelineChart, ResourceChart, HeatMapChart, MultiRevisionSCurveChart, GanttChart, EVMSCurveChart)
- ScheduleViewer: `web/src/lib/components/ScheduleViewer/` — Interactive Gantt with WBS tree, baseline bars, float, dependencies
- UI: Breadcrumb, Skeleton, AnalysisSkeleton, ToastContainer, ThemeToggle components
- Theme: `web/src/lib/stores/theme.ts` — dark mode with localStorage + system preference
- MCP Server: `src/mcp_server.py` — 22 tools for Claude integration via the mcp SDK 2.x `MCPServer` (ADR-0032)
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
- `web/src/lib/auth.ts` uses dynamic import to break circular dependency
- Supabase clients are only created when `ALLOW_REMOTE_SUPABASE=1` (set in `fly.toml`). `.env` is loaded at import and usually holds production credentials, so local scripts, tests and MCP sessions stay in-memory unless you opt in deliberately. Note: `env -u VAR` does not isolate, because `load_dotenv` re-reads the unset key from `.env`; blank it (`VAR=`) instead.
- Rate limits and the audit trail attribute a request to `deps.trusted_client_ip`: the header named in `TRUSTED_CLIENT_IP_HEADER` (`fly.toml` sets `fly-client-ip`; `x-forwarded-for` uses the rightmost hop), else the socket peer. Leave it unset when clients connect directly (e.g. `docker compose`), since the client writes those headers. Limits are per machine (in-memory) and IPv6 is keyed on its /64.
- AI ("Ask Your Schedule", the only LLM call) is off unless ALL of `AI_ENABLED=1`, `ANTHROPIC_API_KEY`, `AI_MODEL`, `AI_PRICED_MODEL` (= `AI_MODEL`), `AI_PRICE_INPUT_USD_PER_MTOK`, `AI_PRICE_OUTPUT_USD_PER_MTOK` (0.01-1000 USD/MTok), `AI_GLOBAL_MONTHLY_BUDGET_USD` are set, the image ships the `ai` extra, and migration 035 is applied. Even then only accounts granted by an operator in `SUPERADMIN_USER_IDS` (page `/admin/ai`) may ask, within per-account daily/monthly limits and the global budget. Users request access from the closed `/ask` panel (migration 036); the operator is emailed without the requester's details and approves or dismisses on `/admin/ai`. `src/api/ai_gate.py` is the only module allowed to import the SDK or build a client (AST test). A changed variable needs a Fly restart; the fastest stop is disabling the key in the Anthropic Console.
- CORS origins are configurable via `ALLOWED_ORIGINS` env (comma-separated); defaults cover localhost + `getmeridianiq.com` (+ `www.`) and the previous `meridianiq.vitormr.dev`
- `api_keys` table schema: columns are `id` (bigint), `key_id`, `key_hash`, `user_id`, `name`, `created_at`, `revoked_at`. See ADR-0017 if you find legacy 012-style columns (`key_prefix`, `is_active`, `expires_at`).

## Workflow

- Run relevant tests after changes, not always the full suite
- Reference `BUGS.md` for known issues before investigating errors
- See `docs/ROADMAP.md` for the roadmap (older plans are in `docs/archive/`)
- Version: **v4.3.0** (2026-05-09) is the latest release tag. `main` is in Cycle 6 (ADR-0025); the next tag is v4.4.0 or v4.3.1. What merged since the tag is in `CHANGELOG.md` under [Unreleased], and decisions are indexed in `docs/adr/README.md`. Version and test figures are not repeated here: `pyproject.toml` holds the dependency ranges and CI reports the test counts.
- CI: Python 3.15, Node 24, Vite 8, TypeScript 6, GitHub Actions v7
- Dockerfile: Python 3.15-slim, the same version CI tests on (3.13 → 3.14 in #329, 3.15 in #342). It was held at 3.13 because `supabase` pulled `storage3` → `pyiceberg`, which had no 3.14 wheel (bumped in `f1bd4e2`, broke deploy, reverted in `df672d9`). Since supabase/storage3 2.33, `pyiceberg` is only the optional `iceberg` extra, which the image does not install.

## Portfolio PMO (knowledge loop)

- This repo lives under Vitor's portfolio PMO at `~/projects` (the parent
  `CLAUDE.md` there governs PMO mode; machine-global skills at
  `~/.claude/skills/`, SSOT = `AI-PMO-Framework/skills/`).
- It carries a standing `[LL]` lessons-learned-intake issue; at the end of
  meaningful work sessions, log reusable lessons there (what worked, what
  should change in the framework/skills/kits) so the PMO can harvest them
  (`pmo-sync.sh harvest`).
