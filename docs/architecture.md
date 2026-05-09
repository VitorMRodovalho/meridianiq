<!-- Last updated: 2026-04-27 (post-Cycle-3 W4 code-side close) -->
# MeridianIQ — System Architecture

## System Overview

MeridianIQ is a **modular monolith**: a single FastAPI application with clearly separated analysis engines, each implementing a specific published methodology and written to stay independent of every other engine. The frontend is a SvelteKit SPA served from Cloudflare Pages and talks to the backend via REST.

As of **v4.2.0** (β-honest path-A discipline — Cycle 3 close-arc + Cycle 4 close): 48 analysis engines + 1 export module, 127 API endpoints across 25 routers, 55 SvelteKit pages, 11 hand-crafted SVG chart components, 28 Supabase migrations, 22 MCP tools, 15 PDF report types, 1652 tests.

```mermaid
graph TB
    subgraph "Edge — Cloudflare Pages"
        UI[SvelteKit Frontend<br/>55 pages · Svelte 5 runes<br/>Tailwind v4 · dark mode · i18n<br/>StatusBadge — ready/computing/failed]
    end

    subgraph "Compute — Fly.io"
        API[FastAPI application<br/>127 endpoints · 25 routers<br/>Rate-limited · CORS whitelist<br/>Sentry telemetry]
        ENGINES[48 analysis engines<br/>+ 1 export module<br/>src/analytics/ + src/export/]
        MATERIALIZER[Async materializer<br/>asyncio.Task · Semaphore(1)<br/>ProcessPoolExecutor spawn<br/>src/materializer/]
        MCP[MCP server<br/>22 tools · stdio + http + sse<br/>src/mcp_server.py]
        API --> ENGINES
        API --> MATERIALIZER
        MATERIALIZER --> ENGINES
        MCP --> ENGINES
    end

    subgraph "Platform — Supabase"
        AUTH["Supabase Auth<br/>Google · LinkedIn · Microsoft<br/>ES256 JWT via JWKS"]
        DB[("PostgreSQL<br/>28 migrations · RLS enforced<br/>projects (pending/ready/failed)<br/>activities · WBS · revision_history<br/>schedule_derived_artifacts<br/>erp_sources · cbs_elements<br/>cost_snapshots · audit")]
        STORAGE["Supabase Storage<br/>xer-files bucket · RLS"]
    end

    subgraph "AI clients"
        CLAUDE[Claude Code / Desktop<br/>via MCP stdio]
    end

    UI <-->|REST + JWT| API
    CLAUDE <-->|stdio| MCP
    API <-->|SQL| DB
    API -->|Store / Read| STORAGE
    API -->|JWT verify| AUTH
    UI -->|OAuth flow| AUTH

    style UI fill:#F38020,color:#fff
    style API fill:#009688,color:#fff
    style ENGINES fill:#4C9A2A,color:#fff
    style MCP fill:#D97757,color:#fff
    style DB fill:#3FCF8E,color:#fff
    style AUTH fill:#3FCF8E,color:#fff
    style STORAGE fill:#3FCF8E,color:#fff
```

---

## Repository layout

```
src/
  parser/            XER / MS Project XML readers, Pydantic models (17+ tables),
                     structured P6 calendar_data parser (CalendarSchedule + exceptions)
  analytics/         48 analysis engines (see docs/methodologies.md)
  export/            XER round-trip writer
  database/          InMemoryStore + SupabaseStore abstraction, Supabase client
  api/
    app.py           FastAPI shell — all domain logic in routers/
    routers/         23 modular routers (see docs/api-reference.md)
    schemas.py       Pydantic v2 request/response models
    auth.py          JWT + optional_auth / require_auth dependencies
    deps.py          Shared store + limiter singletons
    cache.py         Namespace-scoped TTL cache (in-memory, single-process)
    kpi_helpers.py   Cached CPM+DCMA+Health bundle for /programs/rollup + /bi/projects
    progress.py      Per-job pub/sub channels for WebSocket progress streaming
  integrations/      ERP adapter protocols (cost, schedule, risk, reporting, resource)
                     + concrete adapters for Unifier, SAP PS, Kahua, eBuilder,
                       InEight, Procore, manual Excel
  plugins/           Third-party AnalysisEngine registry (entry-point discovery).
                     Reference plugin at samples/plugin-example/
  mcp_server.py      22 MCP tools (see docs/mcp-tools.md). Transports: stdio | http | sse
web/
  src/
    routes/          54 SvelteKit pages (file-based routing)
    lib/
      components/
        charts/      11 hand-crafted SVG chart components
        ScheduleViewer/  Interactive Gantt (WBS tree, baseline, float,
                         dependencies, resource histogram panel)
      stores/        auth (lazy init), theme, i18n
      api.ts         API client
supabase/
  migrations/        28 .sql files (RLS enforced on user-owned tables — see ADR-0017 for the deduplication of the 012/017 api_keys migrations; Cycle 3 W4 added the `_ENGINE_VERSION` sourcing chain via `src/__about__.py` per ADR-0014 §"Decision Outcome"; Cycle 4 W1 added `revision_history` per ADR-0022 + Amendment 1)
scripts/
  generate_api_reference.py       → docs/api-reference.md
  generate_mcp_catalog.py         → docs/mcp-tools.md
  generate_methodology_catalog.py → docs/methodologies.md
```

---

## Deployment

| Layer | Service | Notes |
|---|---|---|
| Frontend | **Cloudflare Pages** (adapter-static, SSR off) | Global edge delivery. Auto-deploys on push to `main`. |
| Backend | **Fly.io** (Docker, Python 3.13 base) | Cold start ~10s — first request may 502 (BUG-007, documented). |
| Auth | **Supabase Auth** | Google + LinkedIn + Microsoft OAuth. Backend verifies ES256 JWT via JWKS auto-detect. |
| Database | **Supabase PostgreSQL** | Pooler on port 6543 (not 5432). RLS enforced on all user-owned tables. |
| Storage | **Supabase Storage** | `xer-files` bucket with RLS policies mirroring project ownership. |
| Observability | **Sentry** | Optional via `SENTRY_DSN` env var. |

---

## Data flow — XER upload → analysis

```mermaid
sequenceDiagram
    participant B as Browser
    participant A as FastAPI
    participant P as XER Parser
    participant S as Supabase (DB + Storage)
    participant E as Analysis Engine

    B->>A: POST /api/v1/upload (XER + JWT)
    A->>A: Rate limit (10/min) + auth check
    A->>P: Parse (streaming, encoding-aware)
    P->>P: Read %T/%F/%R tables, build 17+ Pydantic models, composite keys
    A->>S: Store XER bytes (Storage) + metadata (DB)
    A-->>B: 200 {project_id, activity_count, ...}

    B->>A: GET /api/v1/projects/{id}/validation
    A->>S: Reload ParsedSchedule
    A->>E: DCMA14Analyzer.analyze()
    E-->>A: 14 check results + composite score
    A-->>B: ValidationResponse

    B->>A: GET /api/v1/projects/{id}/critical-path
    A->>S: Cache lookup (analysis_results)
    alt cache hit
        S-->>A: Cached CPM result
    else cache miss
        A->>E: CPMCalculator.calculate() (NetworkX forward/backward pass)
        E->>S: Persist result to cache
    end
    A-->>B: CriticalPathResponse
```

---

## Schedule comparison — multi-layer matching

```mermaid
flowchart TD
    A[Baseline XER] --> C[Comparison engine]
    B[Update XER] --> C

    C --> D{Match by task_id<br/>Tier 1}
    D -->|Matched| E[Modification detection]
    D -->|Unmatched| F{Match by task_code<br/>Tier 2}
    F -->|Matched| E
    F -->|Unmatched| G[Truly added / deleted]

    E --> H{task_code changed?}
    H -->|Yes| I[Code restructuring alert]
    H -->|No| J[Normal modification]

    E --> K[Duration · Date · Float · Relationship · Constraint deltas]
    K --> P[Manipulation detection]
    P --> Q[Retroactive date]
    P --> R[Out-of-sequence progress]
    P --> S[Constraint masking]
    P --> T[Duration inflation]

    style D fill:#009688,color:#fff
    style F fill:#FFA726,color:#fff
    style I fill:#EF5350,color:#fff
    style P fill:#D97757,color:#fff
```

---

## Forensic CPA — window analysis

```mermaid
flowchart LR
    subgraph "Schedule updates"
        UP1[UP 01]
        UP2[UP 02]
        UP3[UP 03]
        UP4[UP 04]
    end

    subgraph "Analysis windows"
        W1[Window 1<br/>UP01→UP02]
        W2[Window 2<br/>UP02→UP03]
        W3[Window 3<br/>UP03→UP04]
    end

    UP1 & UP2 --> W1
    UP2 & UP3 --> W2
    UP3 & UP4 --> W3

    W1 & W2 & W3 --> COMP[Consecutive-pair compare<br/>+ delay calc<br/>+ CP evolution]
    COMP --> WF[Delay waterfall<br/>cumulative chart]

    style WF fill:#D97757,color:#fff
```

Per AACE RP 29R-03 §5.3 (Forensic Schedule Analysis) — see `src/analytics/forensics.py`.

---

## TIA — time impact analysis

```mermaid
flowchart TD
    BASE[Base schedule] --> CPM1[CPM → unimpacted completion]
    FRAG[Delay fragment<br/>activities + relationships] --> INSERT[Insert into network copy]
    BASE --> INSERT
    INSERT --> CPM2[CPM → impacted completion]
    CPM1 & CPM2 --> DELTA[Δ = impacted − unimpacted]

    DELTA --> CLASS{Classify}
    CLASS -->|Owner caused| EC[Excusable compensable]
    CLASS -->|Force majeure| ENC[Excusable non-compensable]
    CLASS -->|Contractor caused| NE[Non-excusable]
    CLASS -->|Multiple causes| CON[Concurrent]

    EC & ENC & NE & CON --> RESP[Responsibility waterfall]

    style FRAG fill:#EF5350,color:#fff
    style RESP fill:#D97757,color:#fff
```

Per AACE RP 52R-06 — see `src/analytics/tia.py`.

---

## Monte Carlo QSRA

```mermaid
flowchart TD
    SCHED[Parsed schedule] --> ASSIGN[Assign uncertainty<br/>min / likely / max<br/>or benchmark priors]
    ASSIGN --> LOOP[Iterate N = 1000]
    LOOP --> SAMPLE[Sample durations<br/>PERT-Beta]
    SAMPLE --> CPM3[Run CPM]
    CPM3 --> RECORD[Record completion + CP]
    RECORD -->|Next| LOOP

    RECORD --> AGG[Aggregate]
    AGG --> HIST[Histogram]
    AGG --> PVAL[P10 · P50 · P80 · P90]
    AGG --> TORNADO[Tornado<br/>Spearman sensitivity]
    AGG --> CRIT[Criticality index]
    AGG --> SCURVE[Completion S-curve]

    style LOOP fill:#013243,color:#fff
    style HIST fill:#1565C0,color:#fff
```

Per AACE RP 57R-09 — see `src/analytics/risk.py`. Benchmark-derived priors available via `benchmark_priors.py`.

---

## Data model

### Scheduling entities (from XER)

```mermaid
erDiagram
    PROJECT ||--o{ PROJWBS : "has"
    PROJECT ||--o{ TASK : "contains"
    PROJWBS ||--o{ TASK : "groups"
    TASK ||--o{ TASKPRED : "predecessor"
    TASK ||--o{ TASKRSRC : "resource assignment"
    TASK }o--|| CALENDAR : "uses"
    TASKRSRC }o--|| RSRC : "references"
```

### ERP-ready cost tables (migration 019)

```mermaid
erDiagram
    PROJECTS ||--o{ ERP_SOURCES : "origin of"
    ERP_SOURCES ||--o{ CBS_ELEMENTS : "registers"
    CBS_ELEMENTS ||--o{ COST_SNAPSHOTS : "point-in-time"
    CBS_ELEMENTS ||--o{ CBS_WBS_MAPPINGS : "maps to"
    WBS_ELEMENTS ||--o{ CBS_WBS_MAPPINGS : "funded by"
    CBS_ELEMENTS ||--o{ COST_TIME_PHASED : "period buckets"
    CBS_ELEMENTS ||--o{ CHANGE_ORDERS : "affected by"
    OBS_ELEMENTS ||--o{ OBS_CBS_ASSIGNMENTS : "responsible for"
    CBS_ELEMENTS ||--o{ OBS_CBS_ASSIGNMENTS : "owned by"
```

Supports universal ERP fields per AACE RP 10S-90, ANSI/EIA-748, ISO 21511, with NUMERIC(18,2) precision for all monetary values.

---

## Catalogs & references

- [API Reference](api-reference.md) — auto-generated from FastAPI app (127 endpoints × 25 routers)
- [Methodologies](methodologies.md) — auto-generated from engine docstrings (48 engines + citations)
- [MCP Tools](mcp-tools.md) — auto-generated from `@mcp.tool()` decorators (22 tools)
- [Deploy Checklist](DEPLOY_CHECKLIST.md) — 5-phase procedure
- [Schedule Submission Standards](SCHEDULE_SUBMISSION_STANDARDS.md)
- [Schedule Viewer Roadmap](SCHEDULE_VIEWER_ROADMAP.md)
- [XER Format Reference](xer-format-reference.md)

Regenerate catalogs whenever the underlying code changes:

```bash
python3 scripts/generate_api_reference.py
python3 scripts/generate_methodology_catalog.py
python3 scripts/generate_mcp_catalog.py
```

---

## Design principles

1. **Modular engines** — Each engine in `src/analytics/` is a standalone module with no cross-dependencies. Engines receive parsed data and return results; orchestration lives in routers.
2. **Standards-first** — Every methodology traceable to a published standard (AACE RP, DCMA, ANSI/EIA, SCL Protocol, GAO, PMI). Docstring References sections are the source of truth for `docs/methodologies.md`.
3. **Cloud-native, zero-cost** — Supabase (free tier) + Fly.io (free shared VM) + Cloudflare Pages (free). No paid dependencies; all libraries MIT/BSD/Apache.
4. **Custom parser** — MIT-licensed XER reader (GPL alternatives excluded). Streaming, encoding-aware, composite keys.
5. **Defence in depth** — RLS on every user-owned table, CORS whitelist with credentials, `@limiter.limit()` on expensive/paid endpoints, generic error detail in production, audit trail on security-relevant writes.
6. **Self-describing** — The three generator scripts are the contract: if you add an endpoint / engine / MCP tool, regenerating is how the doc lands.

---

## Legacy v1 architecture

The original v1 toolkit used Power Query (M) + DAX in Power BI for XER parsing and analysis. Preserved at [`../archive/v1-power-bi-models/`](../archive/v1-power-bi-models/). Not maintained — kept for attribution and DAX measures reference.

See [`archive/v1-architecture.md`](archive/v1-architecture.md).

---

<div align="center">

**MeridianIQ** · MIT License · © 2025–2026 Vitor Maia Rodovalho

</div>
