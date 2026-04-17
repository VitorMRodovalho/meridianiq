# 0001. FastAPI for the backend API

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-17 (retroactive — decision made circa v0.1, 2024)

## Context and Problem Statement

MeridianIQ needs a Python HTTP API that serves:
- Synchronous analysis endpoints that call CPM / DCMA / EVM / Monte Carlo engines and return JSON.
- File upload endpoints for XER / Microsoft Project XML / CBS Excel.
- Rate-limited endpoints for NLP and heavy ML calls.
- An auto-generated OpenAPI schema so a SvelteKit frontend can consume it without drift.
- A realistic path to 100+ endpoints as the engine count grows.

The Python analysis stack (NetworkX, NumPy, Pydantic) was already chosen before the framework question arose.

## Decision Drivers

- **First-class Pydantic support** — the engines already model data as Pydantic; the API should inherit that validation for free.
- **OpenAPI schema out of the box** — frontend type-generation needs a trustworthy source of truth.
- **Async-capable** — Monte Carlo and optimizer endpoints can take minutes; non-blocking I/O matters.
- **Dependency-injection ergonomics** — clean way to plug the `Store` abstraction and `optional_auth` across all routers without repeating boilerplate.
- **Ecosystem maturity** — not a prototype framework; active maintenance, Sentry/slowapi/starlette integration story proven.

## Considered Options

1. **FastAPI**
2. **Django + Django REST Framework**
3. **Flask + Flask-RESTX or Marshmallow**
4. **Starlette directly** (FastAPI's underlying framework)
5. **Hand-rolled aiohttp / httpcore**

## Decision Outcome

**Chosen: FastAPI.**

### Rationale

- Pydantic v2 integration is native — the analysis engines already expose Pydantic models, and FastAPI uses them both for request validation and response serialisation with zero glue.
- The generated OpenAPI schema has been consumed daily by the SvelteKit frontend since v0.1 with no drift incidents.
- FastAPI's `Depends` dependency injection made it possible to evolve from a single-file app (pre-v0.4) to 20 routers (v3.7) without rewriting auth or store-access code.
- The async path was used in v2.x for Monte Carlo streaming and is available (unused) for future long-running endpoints.
- Sentry + slowapi + CORS middleware all plug in as FastAPI middleware without forking.

### Rejected alternatives

- **Django + DRF** — far heavier runtime and dev workflow for what is effectively a JSON-in / JSON-out analysis service. The ORM, admin, templates, and migrations layer are all overhead we never needed (Supabase handles the DB, and migrations live as SQL under `supabase/migrations/`). DRF's serializer model predates and is clunkier than Pydantic v2.
- **Flask + Flask-RESTX** — would have required hand-rolling Pydantic integration, Depends-style DI, and OpenAPI generation. Three wheels to reinvent per feature.
- **Starlette directly** — strictly more work than FastAPI for essentially the same runtime. FastAPI *is* Starlette plus the validation/DI/OpenAPI layer we wanted anyway.
- **Hand-rolled aiohttp** — no realistic path to an OpenAPI schema without building it from scratch.

## Consequences

**Positive**:
- Router-per-domain pattern (`src/api/routers/`) scaled from 4 routers (v0.4) to 20 routers (v3.7) without refactoring.
- Frontend type sync has been zero-cost — copy the OpenAPI JSON, generate TS types.
- Sub-millisecond request overhead; framework has never been on the hot path.

**Negative**:
- FastAPI's backwards-compatibility promises are weaker than Django's. The v0.1 upgrade path involved a few breaking changes (Pydantic v1→v2 migration was the worst).
- Testing async endpoints requires httpx/ASGI setup that isn't as ergonomic as Django's `Client`.

**Neutral**:
- Mounting a GraphQL layer or gRPC transport in the future would still be possible — Starlette allows additional ASGI apps to mount alongside FastAPI routes.
