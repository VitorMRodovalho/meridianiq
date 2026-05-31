# MeridianIQ — Agent Context

Loaded automatically by Claude/Cursor/Cline/Aider (2025-2026 convention). **Read this before making changes.**

For project state (current version, cycle, in-flight work, release notes), see [`CLAUDE.md`](./CLAUDE.md). This file holds **how to operate**, not what's currently happening.

## Quick reference

| Need to… | Go to |
|---|---|
| Current version & cycle | `CLAUDE.md` |
| Known bugs | `BUGS.md` |
| Past lessons | `LESSONS_LEARNED.md` |
| Architectural decisions | `docs/adr/` |
| Pre-push validation | `python -m pytest tests/ -q && cd web && npm run build` |
| Security policy | `SECURITY.md`, `.gitleaks.toml` |
| Schedule analysis methodology | `src/analytics/` (each engine cites AACE/DCMA/etc.) |
| MCP tools | `src/mcp_server.py` (22 deployed) |

## What this is

P6 XER schedule intelligence platform. From validation (DCMA, AACE) to prediction (Monte Carlo, EVMS, root-cause). Python/FastAPI backend, SvelteKit frontend, Supabase PostgreSQL. MIT license — no GPL deps.

Scale: 48 analysis engines, 129 API endpoints across 25 routers, 55 SvelteKit pages, 22 MCP tools, 15 PDF report types, 1687 backend tests + 64 Vitest + 64 Playwright.

## Harness engineering principles (adopted 2026-05-19)

Anchored on Anthropic's three engineering posts:
- [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) — workflow patterns and when to escalate to an agent
- [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — context as a finite resource
- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — multi-session continuity, handoff artifacts

**1. Workflow first, agent second.** Analysis engines, API endpoints, chart components — these are deterministic pipelines. Reserve agentic flow for tasks that genuinely need dynamic routing (e.g., `src/analytics/nlp_query.py`).

**2. Context is finite.** Don't paste full schema dumps or release notes. Use `grep`/`glob` for code lookup. Load `BUGS.md` / `LESSONS_LEARNED.md` / ADRs only when relevant to the current task.

**3. Persist outside the model.** State of in-flight work lives in: ADRs (`docs/adr/`), `BUGS.md`, `LESSONS_LEARNED.md`, GitHub issues, git commits. Do not invent parallel "progress files" — extend the existing track.

**4. Validate, don't trust.** Every completion claim must be proven:
- `ruff check src/ tests/` + `ruff format --check src/ tests/`
- `mypy src/ --strict` (baseline tracked in #121 — known errors documented)
- `python -m pytest tests/ -q` (1687 tests must pass)
- `cd web && npm run check && npm run build` (frontend type + build)
- For DB changes: migration must apply cleanly against a fresh DB

No exceptions for "small changes" — gates run cheap, regressions are expensive.

**5. Plan for context reset.** Long tasks (cycle waves, multi-PR features) MUST write progress to an ADR or open a draft PR with a checklist BEFORE running out of context. The next session reads ADR/PR, picks up.

**6. The ACI is the product.** The 22 MCP tools and 129 API endpoints are user-facing. Tool descriptions, Pydantic schemas, and error messages are NOT internal — they are the public contract. Treat changes to `src/mcp_server.py` or any `src/api/` router with API-review rigor.

**7. Guardrails in layers:**
- Input validation: Pydantic v2 at every API boundary
- Permissions: Supabase RLS, API keys (ES256 JWT via JWKS)
- Risk-rating: rate limits on critical endpoints (slowapi)
- HITL for destructive: deletes, migrations — never auto-apply against production

## Agent lanes

An agent must NOT work outside its lane without explicit coordination.

| Agent | Scope | Can modify | Cannot touch |
|---|---|---|---|
| **Analytics** | Engines in `src/analytics/`, methodology, fixtures | `src/analytics/`, `tests/analytics/`, `samples/`, `xer-samples/` | API routing, frontend, DB schema |
| **API** | FastAPI endpoints, auth, rate limits | `src/api/`, `tests/api/` | Engine internals, frontend |
| **Frontend** | SvelteKit pages, components, i18n (en/pt-BR/es) | `web/src/`, `web/static/` | Backend logic, DB schema |
| **Database** | Supabase schema, migrations, RLS | `supabase/migrations/`, `src/database/store.py` | Engine code, frontend |
| **DevOps** | CI, Fly.io, Cloudflare Pages, Dockerfile | `.github/`, `fly.toml`, `Dockerfile`, `pyproject.toml` | Application code |
| **MCP** | 22 tools in `src/mcp_server.py` | `src/mcp_server.py`, MCP docs | Engine internals (call them, don't modify) |

## Cross-cutting rules

1. **Methodology citation mandatory.** Every analysis engine must cite its published standard (AACE RP, DCMA 14-point, etc.). Engines without citation don't merge.
2. **No proprietary data.** Test fixtures synthetic only — never commit real project data, client names, or credentials. `.gitleaks.toml` enforces.
3. **No GPL deps.** MIT-only license boundary. Check before `pip install` / `npm install`.
4. **Break the build = revert.** CI failure post-merge → revert before any other work.
5. **One concern per commit.** DB migrations don't ship with UI changes in the same commit.
6. **Cycle discipline.** Active phase is in `CLAUDE.md`. Wave gates are HARD — read ADR-0025 §"Honest GATE vs cosmetic GATE distinction" before claiming a gate passed.

## Validation gates (mandatory before merge to `main`)

```bash
# Backend
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/ --strict
python -m pytest tests/ -q

# Frontend
cd web && npm run check && npm run build && npm run test
```

CI additionally runs gitleaks + trivy.

## Known gotchas (consult before debugging)

See `BUGS.md` for the full catalog. Top-impact:

- Fly.io cold start ~10s → 502+CORS on first request (BUG-007)
- Supabase port 6543 (pooler), not 5432
- JWT algorithm is ES256, not HS256/RS256 — JWKS auto-detects
- `web/src/lib/stores/auth.ts` uses dynamic import to break circular dep
- Dockerfile pinned to Python 3.13-slim — pyiceberg transitive dep has no 3.14 wheel as of 2026-04-26

## When to consult external sources

- Anthropic harness/context/agent posts (linked above) — when designing a new agentic flow or MCP tool
- AACE Recommended Practices / DCMA — when modifying engine methodology
- Supabase docs — when changing RLS or auth flow
- **Do not search "how to fix [error]" before checking `BUGS.md` + `LESSONS_LEARNED.md` first.**

---

*Initial adoption: 2026-05-19. Maintenance: keep this file in sync with cycle decisions in `CLAUDE.md` and ADRs.*
