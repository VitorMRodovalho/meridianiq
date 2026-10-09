# 0031. Test the API contract from the data first; type it from the producer second

* Status: **proposed**. This is the second draft; the entry council's findings are folded in (see §"Council record").
* Deciders: @VitorMRodovalho
* Date: 2026-10-09
* Cites:
  * PR #293, the incident and its phase-0 fix. PR #294 corrects how that fix built its fixture.
  * PR #292, the production smoke test that found the incident.
  * `tests/test_dependency_caps.py`, which shows why a path-filtered job cannot guard a contract.
  * [ADR-0027](0027-park-maintenance-only.md) §"Order of work", which this ADR must fit.
  * `.claude/rules/backend.md` and `.claude/rules/frontend.md`, the two written rules this ADR enforces.

## Context and Problem Statement

`/anomalies` threw on every analysis from the day it was added (2026-04-05) until PR #293. The page declared the response by hand, with fields the route never returned:

* `summary`, `total_activities` and `activity_name`;
* severities `high` and `medium`, where the engine emits `critical`, `warning` and `info`.

Typecheck, unit tests, e2e and review all passed it, for two independent reasons:

1. **Nothing links the two descriptions of the payload.** The route returns `asdict(...)` under `-> dict`, and the page declares its own interface.
2. **No test renders the page with data the backend produces.** The Playwright suite visits `/anomalies` (`web/tests/pages.spec.ts:32`), but it runs against a static preview with no backend and checks only the heading.

The second reason is the cheaper one to close, and it is the more complete one. A generated type would not have caught the severity half of the bug, because the engine types `severity: str`, so `'high'` type-checks.

### Census

Measured on `main` at 2026-10-09 by walking the live app's routes (the walker in `scripts/generate_api_reference.py`). This supersedes the first draft's routers-only AST pass, which missed `src/api/organizations.py`.

| What | Count |
|---|---|
| API routes | 141 |
| Routes with a real model (a `BaseModel`, or a container of models) | 73 |
| Routes whose model is an untyped container (`-> dict`, `dict[str, Any]`) | 57 |
| Routes with no model at all | 11 |
| ...of those 68, not JSON payloads (6 file/stream, 1 returning 204, 1 hidden hook) | 8 |
| **Untyped JSON routes** (15 of them in `organizations.py`) | **~60** |
| Fields typed `dict[str, Any]` / `Any` inside the "real" models in `schemas.py` | 27 |
| `fetch(` outside `web/src/lib/api.ts`: 20 route files + 1 component | 21 files |
| Untyped `res.json()` call sites in `web/src` | 27 (25 outside `api.ts`) |
| Hand-written payload declarations: `lib/types.ts`, `lib/api.ts`, routes, `ScheduleViewer/types.ts` | ~96 / ~51 / ~43 (+28 aliases) / 6 |

A request-side case already exists. `contributeBenchmark` (`web/src/lib/api.ts:456`) sends the project id as a JSON body, while the route reads it as a query parameter. It is dead code (one reference: its own definition), and the page sends the id correctly.

**How serialization works today.** A route annotated `-> dict` gets `response_model=dict` and is serialized by pydantic, through `TypeAdapter(dict).dump_json`. Under that path a tz datetime ends in `Z` and NaN becomes `null`. Only the 11 unannotated routes go through `jsonable_encoder` and `JSONResponse(allow_nan=False)`, where a datetime ends in `+00:00` and NaN is a 500. Measured on FastAPI 0.143.0 with pydantic 2.13.5.

The anomalies page is the case that was found. No census of broken pages has been taken, and the absence of other reports is not evidence that there are none.

## Decision Drivers

* A renamed or missing field, or a value outside the expected set, must fail CI and not reach production.
* **A loud failure must not become a silent wrong number.** This is a forensic-scheduling product. A model whose fields all carry defaults would turn a rename into a plausible `0.0` on screen. That is worse than an error boundary. `schemas.py:1175-1180` already has models of that kind, for example `fei: float = 0.0` and `cp_stability: float = 100.0`.
* There should be one description per payload, owned by its producer. The engines already describe their output as dataclasses (138 `@dataclass` in `src/analytics/`), so a parallel hand-written model is a second copy, not a source of truth.
* Checks must run on every pull request, including dependency-only ones. They must also not go red on `main` because an upstream package released.
* External API-key clients read these routes, the BI connectors in `src/api/routers/bi.py` above all. A change must never silently alter what they receive.
* The cost must fit a solo-maintained repository whose order of work is fixed by ADR-0027.

## Considered Options

1. **Status quo**, plus a fixture-backed page test written each time a page breaks. This is what #293 did.
2. **A data-driven page sweep.** Render every data page from payloads taken from the real routes, using the synthetic schedules. There is no backend change and no payload risk.
3. **Generated types.** Export OpenAPI, generate TypeScript from it, and check drift in CI. This needs typed routes in order to say anything.
4. **Hand-written runtime validation in the frontend.** This writes a third copy of each payload, on the consuming side.
5. **A different transport** (GraphQL, tRPC). Out of proportion for this app and its external REST clients.

## Decision Outcome

Options 2 and 3, in this order. Option 2 comes first because it is the cheapest, it carries no payload risk, and it would have caught both halves of the anomalies bug. Option 3 then makes renames fail at compile time.

### Phase 1: data-driven page sweep (Option 2)

**Fixtures come from the route.**
* Each data page gets one or more fixtures captured through `TestClient` from the real route: upload a synthetic XER, then GET or POST the route. Fixtures are never built by re-serializing engine output (see §Census on serialization). PR #294 is the reference.
* A pytest keeps every committed fixture byte-equal to the route's current output.
* Routes whose output carries `datetime.now`, `uuid4` or `random` (8 analytics modules use them) are generated with a frozen clock and a fixed seed, or with a documented normalization. A fixture test that flakes gets skipped, and a skipped test guards nothing.

**One shared render helper.** For example `renderPage(Page, { url, api: { 'GET /api/v1/...': fixture } })`. It:
* stubs `fetch` with a router keyed by path template;
* **throws** on an unmatched request. It never returns 502, because `api.ts` would retry a 502 for about 120 s;
* sets `page` from `$app/state` and the auth session;
* uses the **real** `lib/api.ts` (the `askSchedule.test.ts` pattern, not a mock of `$lib/api`).

**Assertions.** A page passes when it:
* renders with no error boundary;
* shows the values the fixture carries (KPIs, row counts);
* holds up against an empty-result fixture as well as a populated one.

**Order of the sweep.** Pages first, ordered by the route they read; `organizations.py` and `bi.py`-backed pages are included.

**What this phase delivers.** The census of broken pages that nobody has taken. Each page found broken gets its fix in its own pull request.

### Phase 2: generated types for routes that already have real models (Option 3, no payload change)

**OpenAPI export.**
* The document is exported from `app.openapi()` to a committed file, normalized: `info.version` stripped and `sort_keys=True`.
* It was measured deterministic across hash seeds, environments, optional extras, and FastAPI 0.136.1 / 0.141.1 / 0.143.0: 140 operations, 0 duplicate operation ids, no `-Input`/`-Output` splits.
* A pytest in the Backend job (not path-filtered) asserts that the committed file equals the export. On failure it prints the fastapi and pydantic versions.

**TypeScript generation.**
* TypeScript is generated **from the committed file** in the Frontend job, which has no Python. The generator is `openapi-typescript` (MIT).
* It is run isolated and pinned: `npx -p openapi-typescript@<exact> -p typescript@5.9.x`. Its 7.13.0 release declares `peer typescript ^5.x`. It fails `ERESOLVE` next to the app's TypeScript 6, and upstream issues #2723 (TS 6) and #2841 (TS 7) are open.
* The app consumes only the generated `.ts` file. If upstream lands TS 6/7 support, the generator moves into `devDependencies`. If it stalls, the fallback is `@hey-api/openapi-ts`, which declares TS 6.
* The generator version is pinned exactly and regenerated together with fastapi/pydantic bumps, not in the frontend minor/patch Dependabot group.

**How the types are consumed.** This is what makes drift an error:
* `lib/api.ts` gains a **type-only wrapper keyed by path** over the existing `request()`. The retry, cold-start, timeout, `ApiError` and `TimeoutError` behaviour stays. The wrapper's return type and its path/query parameter types come from `paths[P][method]`.
* A call site cannot choose its own `T`. Today `request<T>()` lets it, which is exactly how a hand-written type outlives the route.
* `components['schemas']` aliases are allowed for props and helpers, never as the declared return type of a call.

**Rollout.**
* The check runs advisory for two weeks, then becomes blocking.
* `fastapi` stays uncapped. A red run after an upstream release is accepted, because the failure message names the versions.

### Phase 3: models for the untyped routes

Phase 3 runs one router per pull request, after Phase 1 has covered that router's pages.

**One description.** Prefer the engine's own dataclass as `response_model`. FastAPI accepts it, and the engine stays the single description. Where a pydantic model in `schemas.py` is needed, it follows three rules:
* **Required fields with no defaults.** A field the engine can omit or null is `X | None` without a default. A default that invents a value is not allowed.
* **`Literal`/enum types** for enumerated values such as severity, status and rating.
* A parity test against the engine dataclass.

**What adding a model changes.** All four effects below were measured:
1. Undeclared keys are dropped.
2. Defaulted fields add keys that were absent.
3. A wrong type or a `None` in a non-optional field raises `ResponseValidationError`, which the global handler turns into a production 500.
4. Lax coercion: `'7'` becomes `7`, and a Decimal changes from a string to a number.

**A permanent equality guard.** A parametrized pytest per migrated route checks before against after:
* "before" calls the endpoint function's raw return and serializes it with the route's former serializer;
* "after" calls the route through `TestClient`.

The guard runs over several fixtures, so the optional branches are exercised:
* `sample.xer`, `sample_update.xer` and `sample_update2.xer`;
* an empty or one-activity schedule;
* with and without a baseline.

Any difference must equal a committed, reviewed `expected_diff` for that route. Because the endpoint keeps returning its raw value, the guard stays as a regression test and is not a one-time checklist item.

**Cached and persisted payloads.** `schedule-view` (`analysis.py:390-395`) serves cached rows whose key has no engine version. Every route that reads cache or derived artifacts must do one of two things:
* test the cache-hit path, or
* invalidate the cache on deploy.

Otherwise a row older than a required field becomes a 500 for every user.

**Prerequisites and special cases.**
* File and stream routes first declare `response_class` and their `responses` content. `exports.py:174` is annotated `-> dict` but returns text. This lets the exemption be read from the declaration rather than kept as a list.
* `bi.py` routes are external contracts: each change needs an explicit review and a CHANGELOG "API change" entry.
* Performance on large routes is measured before and after, on a 50k-activity synthetic schedule. The routes are `schedule-view`, `schedule-view/resources`, `activities`, `bi/activities` and `visualization`. The baseline measured for `schedule-view` (38 MB) was 106 ms on the current path and 275 ms validating from a dict. Validation drops to 92 ms when the engine returns the model instance, so engines return instances rather than `Model.model_validate(asdict(x))`.

### Phase 4: one way to call the API

Route files and components call the API only through `lib/api.ts`, which is already the written rule. 21 files break it today.

**Converting a page means reconciling it.** Several pages duplicate a function that already exists in `api.ts`, and the shapes differ. For example, `pareto` posts `{}` while `runPareto` posts `{scenarios, base_cost}`. Conversion keeps one function and checks its request shape against `paths`.

**Downloads.** Blob downloads get a `requestBlob()` in `api.ts`.

**Each converted page must:**
* show errors through `ApiError`/`TimeoutError` and `$t`, never the raw `{"detail": ...}` body;
* keep its loading state through `request()`'s retries;
* have no `catch {}` that hides an error state (`projects/[id]` has 10 of them);
* key the toasts it touches in en/pt-BR/es. 14 English-only toasts sit in these files, and they also read payload fields.

### Ratchets

Each ratchet has a committed baseline that may only decrease, and each lands with a **negative control**: a planted violation that turns it red. A pull request may raise a baseline only with an explicit marker in the commit body naming the reason. A red ratchet is not a prompt to edit its number.

* **JSON routes without a real model.** Counted from the live route walk. `response_model` in {`None`, `dict`, `list`} counts as untyped, and so does a container with no model argument. A route returning `JSONResponse` counts as untyped unless it is allowlisted with a reason.
* **Model fields typed `Any` / `dict[str, Any]`.**
* **`fetch(` anywhere in `web/src` outside `lib/api.ts`** (and outside a SvelteKit `load({ fetch })`, should that idiom be adopted).
* **Untyped API reads outside `lib/api.ts`:** `.json()`, `any`, `as unknown as`.

The first draft's "interfaces outside the generated file" ratchet is dropped. Whether an interface is an API payload cannot be decided mechanically, and that count can be lowered by moving declarations around.

### Sequencing

* **Placement in ADR-0027 §"Order of work": owner decision, recorded here once made.**
  * Phase 1 is detection of silent breakage in forensic output, the nearest category being forensic correctness. Its cost is small: the helper plus one fixture test per page.
  * Phases 2 to 4 are hygiene, sized at several cycles.
* The SvelteKit 3 migration (`sv migrate sveltekit-3`, planned as its own mechanical pull request) lands **before** the shared render helper, the generated-types wrapper, and any Phase 4 conversion. Those touch the same files and the same `$lib` → `#lib` imports.
* Backend fixture capture for Phase 1 and the Phase 2 export pytest can start at once.

**Budget and kill criterion.** Phase 1 is bounded to the data pages that exist today. If the Phase 1 census finds no further broken page, Phases 3 and 4 are re-decided by the owner instead of proceeding by default.

### Positive Consequences

* A page that cannot render what its route returns fails CI (Phase 1).
* A renamed field fails `svelte-check` on the pull request that renamed it (Phase 2 for typed routes, Phase 3 for the rest).
* Models without invented defaults keep a missing value visible instead of plausible.
* The OpenAPI document becomes an accurate description for external clients.

### Negative Consequences

* Volume: ~60 routes, ~200 hand-written declarations and 21 files over several pull requests. Phases 3 and 4 are the bulk, and they are the ones gated by the kill criterion.
* Generated and committed files show diffs in pull requests that change payloads, by design.
* A pinned generator run outside the app's dependencies is an unusual setup and needs a comment where it is invoked.
* Validation cost on large routes, kept down by returning model instances.

## Out of scope

* API versioning and a deprecation policy. Open question for the owner: should `/openapi.json` and `/docs` stay public in production once the document is the contract?
* WebSocket payloads (`useWebSocketProgress.ts:370` parses them with `as WSProgressEvent`). This is a later item, with the same approach.
* The MCP server's tool outputs.
* Request bodies and parameters are *in* scope at no extra cost: the path-keyed wrapper types them from the same `paths` map.

## Corrections to the first draft

* The census came from a routers-only AST pass and missed `src/api/organizations.py`: the counts were 126 routes and 50 untyped, against 141 and ~60 in fact.
* The "before" serializer was wrong. `-> dict` routes already go through pydantic.
* `docs/api-reference.md` was called "the OpenAPI document". It is a markdown index built by walking routes, and its generator does not use `app.openapi()`.
* Related, and not in the first draft: the `doc-sync-check.yml` path filter excludes `src/api/schemas.py`, `src/api/organizations.py`, `src/api/app.py` and `pyproject.toml`. A change to a response model alone already leaves that catalog stale without failing.

## Council record

The entry council ran on 2026-10-09 with three lanes: backend-reviewer (AMBER), frontend-ux-reviewer (AMBER) and devils-advocate. Each finding was checked against the repository before it was adopted.

The ones that changed this ADR:
* the census;
* the serialization path, which led to the correction in #294;
* defaults turning failures silent;
* the diagnosis, which put the data-driven page sweep first;
* the generator's TypeScript peer range;
* consumption keyed by path;
* the ratchet definitions and their gaming;
* cache-hit payloads;
* drift-check stability;
* sequencing with SvelteKit 3;
* fit with the ADR-0027 order.

## Validation

* Phase 0 (merged, #293, corrected by #294):
  * the anomalies page was fixed;
  * its route-captured fixture is in place;
  * a negative control showed the page test fails with the production error against the previous page;
  * a production check on 2026-10-09 rendered a real project with 6057 activities and 1053 anomalies with no error.
* Each later phase lands with its ratchets and their negative controls, and states the counts before and after.
