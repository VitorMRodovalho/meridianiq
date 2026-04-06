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
# Backend (710+ tests)
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

- **32 analysis engines** in `src/analytics/` + 1 export module in `src/export/` — each standalone, no cross-dependencies
- **API**: FastAPI with 79 endpoints under `/api/v1/`
- **Frontend**: SvelteKit + Tailwind v4, 41 pages, Svelte 5 runes ($state, $derived, $effect)
- **Database**: Supabase PostgreSQL with RLS, 16 migrations in `supabase/migrations/`
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
- Charts: `web/src/lib/components/charts/` — 6 reusable SVG components (BarChart, PieChart, GaugeChart, ScatterChart, WaterfallChart, TimelineChart)
- MCP Server: `src/mcp_server.py` — 19 tools for Claude integration via FastMCP
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
- See `docs/v06-planning/ROADMAP_v06_to_v20.md` for roadmap context
- Version: v3.0.1 — "Frontend Coverage" (32 engines, 19 MCP tools, 734+ tests)
- CI: Python 3.14, Node 24, Vite 8, TypeScript 6, GitHub Actions v6
- Dockerfile: Python 3.13-slim (pyiceberg lacks 3.14 wheel)
