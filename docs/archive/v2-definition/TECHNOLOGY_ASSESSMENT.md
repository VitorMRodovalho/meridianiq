# Technology Assessment — P6 XER Analytics v0.1

> Comprehensive evaluation of technology choices for the P6 XER Analytics platform, validated against the 2025-2026 ecosystem.

**Document Status:** Draft v0.1
**Last Updated:** 2026-03-25
**Author:** Vitor Rodovalho

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Architecture Options Evaluated](#architecture-options-evaluated)
3. [Key Libraries](#key-libraries)
4. [Recommendation for v0.1](#recommendation-for-v01)
5. [Custom XER Parser Requirements](#custom-xer-parser-requirements)

---

## Architecture Overview

The system is organized into five layers, each with distinct responsibilities and technology choices:

```
┌─────────────────────────────────────────────────────────────┐
│                    5. DATA PERSISTENCE + EXPORT              │
│              SQLite (dev) / PostgreSQL (prod) / PDF / Excel  │
├─────────────────────────────────────────────────────────────┤
│                    4. API LAYER                              │
│              FastAPI — REST endpoints, file upload, auth     │
├─────────────────────────────────────────────────────────────┤
│                    3. WEB FRONTEND                           │
│          SvelteKit — Dashboard, charts, tables, interactivity│
├─────────────────────────────────────────────────────────────┤
│              2. ANALYTICS ENGINE                             │
│     CPM (NetworkX), DCMA-14, Float Analysis, Comparison,     │
│     Manipulation Detection — Python                          │
├─────────────────────────────────────────────────────────────┤
│              1. XER PARSER ENGINE                            │
│     Custom MIT-licensed Python parser — tab-delimited text   │
│     to typed Pydantic models                                 │
└─────────────────────────────────────────────────────────────┘
```

### Layer 1: XER Parser Engine
Responsible for reading `.xer` files (tab-delimited text), parsing all Oracle P6 tables, validating structure, and producing typed Python data models. Must be custom-built under MIT license.

### Layer 2: Analytics Engine
Implements all schedule analysis algorithms: Critical Path Method (forward/backward pass), DCMA 14-Point Assessment, Total Float calculation, period-to-period comparison, and manipulation detection. Pure Python with NetworkX for graph operations.

### Layer 3: Web Frontend
Interactive browser-based dashboard for displaying validation results, comparison reports, charts, and tables. Must handle data-heavy views (500+ row tables, Gantt-like visualizations, float distribution charts).

### Layer 4: API Layer
RESTful API connecting frontend to backend engines. Handles file upload, triggers analysis pipelines, serves results as JSON. Must support async operations for long-running analyses.

### Layer 5: Data Persistence + Export
Storage of parsed schedules, analysis results, and user sessions. Export engines for PDF and Excel report generation.

---

## Architecture Options Evaluated

### Option A: Python Full-Stack (FastAPI + Jinja2/HTMX)

**Approach:** Single-language stack using FastAPI for the API, Jinja2 templates for HTML rendering, and HTMX for interactivity without a JavaScript framework.

**Pros:**
- Single language (Python) reduces context-switching and team skill requirements
- HTMX provides modern interactivity with minimal JavaScript — partial page updates, lazy loading, and server-sent events without a build step
- FastAPI + Jinja2 is a well-proven pattern with excellent documentation
- Fastest time-to-prototype since there is no frontend build pipeline to configure
- Server-side rendering is inherently good for SEO and initial load performance

**Cons:**
- Limited interactivity for complex dashboard components — HTMX cannot replicate the rich client-side state management needed for interactive Gantt charts, drag-and-drop, or complex filtering
- D3.js and Plotly still require JavaScript, so "no JavaScript" is not truly achievable for analytical dashboards
- Jinja2 templates become difficult to maintain as UI complexity grows beyond simple CRUD forms
- No component model — reusability requires manual template includes and macros
- Testing frontend logic is harder without a proper component framework

**Verdict:** Suitable for rapid prototyping and internal tools, but insufficient for the interactive, data-heavy dashboards required by schedule analysts. The float distribution charts, critical path visualizations, and comparison tables need client-side reactivity that HTMX alone cannot provide efficiently.

---

### Option B: TypeScript Full-Stack (NestJS + Next.js)

**Approach:** Single-language stack using TypeScript end-to-end. NestJS for the backend API, Next.js for the frontend with React components.

**Pros:**
- Single language (TypeScript) across the entire stack with shared type definitions
- Next.js 15 (stable as of late 2025) offers excellent React Server Components, streaming SSR, and the App Router — mature and battle-tested for dashboards
- Massive ecosystem — React has the largest component library ecosystem, including specialized charting (Recharts, Nivo, Victory) and table (TanStack Table) libraries
- Strong typing with TypeScript catches errors at compile time
- NestJS provides enterprise-grade backend architecture with dependency injection, guards, and interceptors

**Cons:**
- Python is the dominant language for schedule analysis, CPM algorithms, and scientific computing. Reimplementing NetworkX-equivalent graph algorithms in TypeScript would be wasteful and error-prone.
- No equivalent to Pandas, NumPy, SciPy in TypeScript — data manipulation would require verbose custom code
- The Python XER parsing community (xerparser, PyP6Xer) provides reference implementations. Starting from scratch in TypeScript loses this advantage.
- Next.js bundle sizes are larger than SvelteKit for equivalent functionality — a 2026 benchmark showed Next.js at 700kB vs SvelteKit at 300kB for a comparable dashboard
- NestJS adds significant boilerplate compared to FastAPI for the same API surface

**Verdict:** The wrong language for the core algorithms. CPM, DCMA-14, and float analysis are naturally expressed in Python with NetworkX and Pandas. Rewriting these in TypeScript would double development time without benefit. However, the React/Next.js frontend ecosystem is undeniably rich.

---

### Option C: Hybrid Python Backend + TypeScript Frontend (RECOMMENDED)

**Approach:** Python backend (FastAPI) handling XER parsing, analytics, and API. TypeScript frontend (SvelteKit) handling dashboard, charts, and user interaction. Communication via REST API with JSON.

**Pros:**
- Best tool for each job: Python excels at data processing, graph algorithms, and scientific computing; SvelteKit excels at reactive UI, small bundle sizes, and fast interactivity
- FastAPI (v0.128+ as of Feb 2026, ~94,800 GitHub stars) is the de facto standard for high-performance Python APIs, with automatic OpenAPI documentation, async support, and Pydantic validation
- SvelteKit (Svelte 5 with runes, SvelteKit 2.x) compiles to vanilla JavaScript with no runtime framework overhead — benchmarks show 41% higher RPS than Next.js and 50%+ smaller bundles
- Clean API boundary enables independent deployment, testing, and scaling of frontend and backend
- Both FastAPI and SvelteKit have excellent developer experience with hot reload, type safety, and minimal boilerplate
- Python 3.12+ offers significant performance improvements (faster interpreter, better error messages) relevant for computation-heavy analytics

**Cons:**
- Two languages require developer familiarity with both Python and TypeScript
- API boundary introduces network latency for every data request (mitigated by SSR and caching)
- Deployment requires orchestrating two services (mitigated by Docker Compose)
- Shared type definitions require manual synchronization or code generation (OpenAPI to TypeScript)

**Verdict:** The clear winner for this project. The analytics engine is inherently Pythonic (NetworkX, Pandas, NumPy), and the dashboard requirements demand a modern reactive frontend. SvelteKit's compile-time approach produces the smallest, fastest bundles — critical for data-heavy dashboards where users interact with 500+ activity tables and multiple chart types. FastAPI's automatic OpenAPI spec generation bridges the type gap between Python and TypeScript.

---

### Option D: Rust + TypeScript (Future Consideration)

**Approach:** Rust backend for XER parsing and CPM computation (maximum performance), TypeScript frontend (SvelteKit or Next.js).

**Pros:**
- Rust offers 10-100x performance over Python for CPU-bound tasks — relevant for Monte Carlo simulations (v0.5) and large-schedule CPM calculations
- Memory safety without garbage collector — predictable performance for long-running analysis
- WebAssembly compilation enables running the parser and CPM engine directly in the browser
- Excellent for the long-term vision of handling 50,000+ activity schedules in real-time

**Cons:**
- Significantly higher development time — Rust's learning curve is steep and the ecosystem for scientific computing is less mature than Python's
- No equivalent to NetworkX, Pandas, or Plotly in Rust — would require building from scratch or using immature libraries
- Overkill for v0.1 where schedules are typically 300-2,000 activities and Python performance is more than sufficient
- Smaller developer community for schedule analysis and construction project management
- Harder to attract contributors to an open-source project written in Rust vs Python

**Verdict:** Not appropriate for v0.1 through v0.5. Consider Rust for performance-critical components in v1.0+ (e.g., a WASM-compiled XER parser or Monte Carlo engine). For the foreseeable roadmap, Python's ecosystem advantages far outweigh Rust's performance advantages at the scale of typical P6 schedules.

---

## Key Libraries

### Python Backend Libraries

| Library | Version | Purpose | License | Notes |
|---------|---------|---------|---------|-------|
| **FastAPI** | 0.128+ | Web framework, REST API, OpenAPI docs | MIT | ~94,800 GitHub stars, de facto Python API standard in 2026. Handles 3,000+ RPS. Built on Starlette (approaching 1.0 stable) and Pydantic. |
| **Pydantic** | 2.x | Data validation, typed models | MIT | Core to FastAPI. XER table rows modeled as Pydantic models with automatic validation. V2 offers 5-50x speed improvement over V1. |
| **NetworkX** | 3.6+ | Graph algorithms, CPM calculation | BSD-3-Clause | Stable mature library for network analysis. Supports topological sort, shortest/longest path, centrality. Used for forward/backward pass CPM. Note: does not natively compute ES/EF/LS/LF — custom implementation required on top of graph traversal primitives. |
| **Pandas** | 2.2+ | Data manipulation, tabular analysis | BSD-3-Clause | XER tables as DataFrames for filtering, grouping, merging. Comparison engine uses DataFrame diffs. |
| **NumPy** | 2.x | Numerical computation | BSD-3-Clause | Underlying Pandas operations. Float calculations, statistical analysis of schedule metrics. |
| **Plotly** | 5.x | Interactive chart generation (server-side) | MIT | Generates JSON chart specs consumed by Plotly.js on the frontend. Float distribution, Gantt preview, S-curves. |
| **ReportLab** | 4.x | PDF generation | BSD | Programmatic PDF creation for validation reports. Full control over layout, tables, and charts. |
| **WeasyPrint** | 62+ | HTML-to-PDF conversion | BSD-3-Clause | Alternative to ReportLab — render HTML/CSS templates to PDF. Better for complex layouts matching web dashboard appearance. |
| **SQLAlchemy** | 2.x | ORM, database access | MIT | Async support with asyncpg. Models for persisting parsed schedules and analysis results. |
| **SciPy** | 1.14+ | Statistical functions | BSD-3-Clause | PERT probability calculations (v0.2), distribution fitting for Monte Carlo (v0.5). Not needed for v0.1 but included for forward compatibility. |
| **scikit-learn** | 1.6+ | Machine learning | BSD-3-Clause | Deferred to v2.0 for anomaly detection and schedule pattern classification. Not needed for v0.1. |
| **python-multipart** | 0.0.9+ | File upload handling | Apache-2.0 | Required by FastAPI for multipart form data (XER file upload). |
| **uvicorn** | 0.30+ | ASGI server | BSD-3-Clause | Production-grade async server for FastAPI. |
| **pytest** | 8.x | Testing framework | MIT | Unit and integration tests for parser, analytics, and API. |

### TypeScript Frontend Libraries

| Library | Version | Purpose | License | Notes |
|---------|---------|---------|---------|-------|
| **SvelteKit** | 2.x (Svelte 5) | Frontend framework | MIT | Compile-time framework producing minimal JS bundles. Svelte 5 runes provide fine-grained reactivity. 50%+ smaller bundles than Next.js. Built-in SSR, routing, and form actions. |
| **D3.js** | 7.x | Low-level data visualization | ISC | Required for custom Gantt chart visualization (no off-the-shelf Gantt library matches P6 scheduling semantics). D3 selections + scales + axes for the custom critical path viewer. |
| **Plotly.js** | 2.x | Interactive charts | MIT | Float distribution bar charts, S-curves, scatter plots. Receives JSON specs from Python Plotly backend. Rich interactivity (zoom, pan, hover tooltips) out of the box. |
| **TanStack Table** | 8.x | Headless table library | MIT | Powers the activity tables (500+ rows), comparison tables, and milestone tracking tables. Virtual scrolling for performance. Sorting, filtering, column resizing. Framework-agnostic with Svelte adapter. |
| **Tailwind CSS** | 4.x | Utility-first CSS | MIT | Consistent styling without custom CSS. Dark mode support. Responsive layouts for dashboard panels. |
| **Zustand** or **Svelte Stores** | Native | State management | MIT / MIT | SvelteKit's built-in stores (writable, readable, derived) handle most state needs. Zustand considered only if cross-component state becomes complex. Prefer native Svelte stores for v0.1. |
| **Lucide Icons** | Latest | Icon library | ISC | Consistent icon set for dashboard UI (upload, download, warning, check, etc.). |
| **date-fns** | 3.x | Date manipulation | MIT | Parsing P6 date formats, calculating day differences, formatting display dates. Lighter than Moment.js or Day.js. |

### Database Options

| Database | Use Case | License | Notes |
|----------|----------|---------|-------|
| **SQLite** | v0.1 prototype, development, single-user | Public Domain | Zero configuration, file-based. Sufficient for prototype where data is ephemeral (upload, analyze, discard). Bundled with Python. |
| **PostgreSQL** | v1.0+ production, multi-tenant | PostgreSQL License (permissive) | Full ACID, concurrent access, JSON columns for flexible schema. Required when persistent storage and multi-user access are needed. |
| **Redis** | v1.0+ caching, session management | BSD-3-Clause | Optional. Cache parsed XER data and analysis results to avoid re-computation. Job queue for async analysis tasks. |

---

## Recommendation for v0.1

### Backend: Python 3.12+ with FastAPI

**Why Python 3.12+:**
- Python 3.12 introduced a new specializing adaptive interpreter that provides 5-10% performance improvement for computational workloads — directly relevant for CPM calculations
- Improved error messages make debugging easier during rapid development
- Full support for modern typing features (`type` statement, `TypedDict`, `Protocol`) used extensively in the XER data model
- Python 3.13 (stable since Oct 2024) adds experimental free-threaded mode — future option for parallel analysis of multi-project XER files

**Why FastAPI:**
- As of February 2026, FastAPI has ~94,800 GitHub stars and is the most popular Python web framework for APIs
- 40% adoption increase in the past year with deployments across finance, healthcare, and ML platforms
- Automatic OpenAPI/Swagger documentation means the API is self-documenting from day one
- Native async/await support via Starlette (approaching 1.0 stable) handles concurrent file uploads efficiently
- Pydantic V2 integration provides automatic request/response validation with 5-50x speed improvement over V1
- Handles 3,000+ RPS — far exceeding v0.1 requirements

### Frontend: SvelteKit

**Why SvelteKit over Next.js:**

1. **Bundle size:** SvelteKit compiles components to vanilla JavaScript with no runtime framework. A fintech team documented reducing their dashboard bundle from 700kB (Next.js) to 300kB (SvelteKit) — a 57% reduction. For data-heavy dashboards with multiple charts and large tables, smaller bundles mean faster Time to Interactive.

2. **Server performance:** 2026 benchmarks show SvelteKit handling 1,200 RPS compared to Next.js at 850 RPS — a 41% increase in server capacity. This means SvelteKit can serve more concurrent users on the same infrastructure.

3. **Reactivity model:** Svelte 5's runes (`$state`, `$derived`, `$effect`) provide fine-grained reactivity that is more intuitive than React's `useState`/`useEffect`/`useMemo` hooks. For dashboards with many interdependent data views, fine-grained reactivity means fewer unnecessary re-renders.

4. **Learning curve:** Svelte's template syntax is closer to standard HTML/CSS/JS than JSX. Components are `.svelte` files with `<script>`, `<style>`, and markup sections — no virtual DOM concepts to learn.

5. **Growing adoption:** SvelteKit job growth is 300% year-over-year (vs 12% for Next.js), indicating strong market momentum. The Svelte 5 release (late 2024) with runes was a major maturity milestone.

6. **Built-in features:** SvelteKit provides SSR, routing, form actions, and hooks out of the box. No need for additional routing or state management libraries for most use cases.

**Trade-off acknowledged:** Next.js has a larger ecosystem of pre-built components and more enterprise deployment precedent. If the project needed complex pre-built components (e.g., rich text editors, complex form builders), Next.js would be preferred. For this project, the primary UI components are charts (Plotly/D3), tables (TanStack), and layout — all framework-agnostic.

### Database: SQLite (Prototype) to PostgreSQL (Production)

**v0.1 (SQLite):** Zero-configuration storage sufficient for the prototype. Parsed XER data can be stored as SQLite tables that mirror the XER structure. Analysis results stored as JSON blobs. Single-file database simplifies deployment and testing.

**v1.0+ (PostgreSQL):** Migration to PostgreSQL when multi-user access, persistent storage, and concurrent writes are needed. SQLAlchemy ORM used from v0.1 ensures the migration is a configuration change, not a rewrite.

### XER Parser: Custom Python, MIT Licensed

The existing Python XER parsers have licensing issues:
- **xerparser** is GPL-3.0 — viral license incompatible with MIT
- **PyP6Xer** has limited table support and uncertain license compliance
- **xer-reader** is focused on Power BI integration, not Python data models

A custom MIT-licensed parser is essential for the project's open-source goals.

### CPM Engine: NetworkX

NetworkX 3.6 (stable, BSD-3-Clause) provides the graph data structures and traversal algorithms needed for CPM:
- `DiGraph` for the activity-on-node network
- `topological_sort` for forward/backward pass ordering
- `dag_longest_path` for critical path identification
- Custom ES/EF/LS/LF calculation using topological traversal

Note: NetworkX does not natively compute CPM time parameters (ES, EF, LS, LF, Total Float, Free Float). A custom implementation layered on top of NetworkX's graph primitives is required. This is a deliberate design choice — it keeps the CPM algorithm explicit, testable, and publishable.

### Charts: Plotly + D3.js

- **Plotly.js** for standard charts (bar charts, pie charts, scatter plots, histograms) — float distribution, activity status breakdowns, validation scores
- **D3.js** for custom visualizations — critical path network diagram, Gantt chart view (no off-the-shelf Gantt library correctly represents P6 scheduling semantics including LOE, hammocks, and resource-dependent durations)

### Deployment: Docker

Docker Compose orchestrating:
- **Backend container:** Python 3.12 + FastAPI + Uvicorn
- **Frontend container:** Node.js + SvelteKit (or static build served by Nginx)
- **Database:** SQLite volume mount (v0.1) or PostgreSQL container (v1.0+)

Single `docker-compose up` for local development. Production deployment via Docker images pushed to a container registry.

---

## Custom XER Parser Requirements

### Rationale

Existing Python XER parsers cannot be used:

| Library | License | Issue |
|---------|---------|-------|
| xerparser | GPL-3.0 | Viral license — any code linking to it must also be GPL. Incompatible with MIT project license. |
| PyP6Xer | MIT (claimed) | Limited table support, inconsistent maintenance, ~759 weekly downloads. |
| xer-reader | Unknown | Power BI focused, not designed for Python data model output. |

A custom parser ensures MIT license compliance, full table coverage, and tight integration with our Pydantic data models.

### Input Format

The XER file format is a tab-delimited text file with four line types:

```
ERMHDR  <version>  <date>  <project_id>  <export_user>
%T  TABLE_NAME
%F  field1  field2  field3  ...
%R  value1  value2  value3  ...
%E
```

Full format specification: `docs/xer-format-reference.md`

### Parsing Strategy

```
1. Read file as UTF-8 text (handle BOM if present)
2. Split into lines
3. Parse ERMHDR line → extract P6 version, export date, project ID
4. For each line:
   a. If %T → start new table context (store table name)
   b. If %F → store field names for current table
   c. If %R → create row dict mapping field names to values
   d. If %E → finalize and return
5. For each table, validate:
   a. All required fields present
   b. Data types correct (dates, numbers, enums)
   c. Referential integrity (task_id references exist, wbs_id valid, etc.)
6. Build typed Pydantic models from validated data
7. Return XERFile object containing all parsed tables
```

### Output Model

```python
class XERFile(BaseModel):
    """Root model representing a parsed XER file."""
    header: XERHeader          # ERMHDR data
    projects: list[Project]    # PROJECT table rows
    calendars: list[Calendar]  # CALENDAR table rows
    wbs_nodes: list[WBSNode]   # PROJWBS table rows
    activities: list[Activity] # TASK table rows
    predecessors: list[Predecessor]  # TASKPRED table rows
    resources: list[Resource]  # RSRC table rows
    resource_assignments: list[ResourceAssignment]  # TASKRSRC rows
    activity_code_types: list[ActivityCodeType]  # ACTVTYPE rows
    activity_codes: list[ActivityCode]  # ACTVCODE rows
    udf_types: list[UDFType]   # UDFTYPE rows
    udf_values: list[UDFValue] # UDFVALUE rows
    # ... additional tables

class Activity(BaseModel):
    """Represents a TASK row with typed fields."""
    task_id: int
    proj_id: int
    wbs_id: int
    clndr_id: int
    task_code: str
    task_name: str
    status_code: ActivityStatus  # Enum: TK_NotStart, TK_Active, TK_Complete
    task_type: TaskType  # Enum: TT_Task, TT_LOE, TT_Mile, TT_FinMile
    total_float_hr_cnt: float | None
    free_float_hr_cnt: float | None
    early_start_date: datetime | None
    early_end_date: datetime | None
    late_start_date: datetime | None
    late_end_date: datetime | None
    target_start_date: datetime | None
    target_end_date: datetime | None
    remain_drtn_hr_cnt: float | None
    target_drtn_hr_cnt: float | None
    phys_complete_pct: float | None
    # ... all 55 TASK fields
```

### Tables to Support

All tables defined in the Oracle P6 XER Import/Export Data Map:

**Required for v0.1 (must parse and validate):**

| Table | Record Count (typical) | Purpose in v0.1 |
|-------|----------------------|-----------------|
| ERMHDR | 1 | File metadata, P6 version identification |
| CALENDAR | 1-10 | Work calendar definitions for duration calculations |
| PROJECT | 1-5 | Project master data, data date |
| PROJWBS | 10-200 | WBS hierarchy for activity grouping |
| TASK | 100-5,000 | Core activity data — all analysis starts here |
| TASKPRED | 200-10,000 | Predecessor relationships — CPM network |
| ACTVTYPE | 1-20 | Activity code type definitions |
| ACTVCODE | 10-200 | Activity code values |
| UDFTYPE | 0-50 | User-defined field definitions |
| UDFVALUE | 0-10,000 | User-defined field values |

**Parsed but not analyzed in v0.1 (stored for forward compatibility):**

| Table | Purpose (future version) |
|-------|-------------------------|
| TASKRSRC | Resource assignments (v0.4 EVM) |
| RSRC | Resource definitions (v0.4 EVM) |
| RSRCRATE | Resource cost rates (v0.4 EVM) |
| PCATTYPE | Project code types (v1.0 portfolio) |
| PCATVAL | Project code values (v1.0 portfolio) |
| FINDATES | Financial period dates (v0.4 cost) |
| TASKFIN | Task financial data (v0.4 cost) |
| TRSRCFIN | Resource financial data (v0.4 cost) |
| MEMOTYPE | Memo/notebook types |
| TASKMEMO | Activity notebook entries |
| CURRTYPE | Currency definitions |

### Validation Rules

The parser must validate the following rules and produce clear error messages:

**Structural Validation:**
1. File must start with ERMHDR line
2. File must end with %E line
3. Every %T must be followed by exactly one %F before any %R lines
4. Number of values in each %R must match number of fields in %F
5. Table names must be recognized Oracle P6 table names (warn on unknown tables, do not fail)

**Data Type Validation:**
1. Date fields must match format `YYYY-MM-DD HH:MM` or be empty
2. Numeric fields must be parseable as int or float
3. Enum fields must match known values (e.g., `status_code` in {`TK_NotStart`, `TK_Active`, `TK_Complete`})
4. ID fields must be positive integers

**Referential Integrity Validation:**
1. Every `TASK.proj_id` must reference an existing `PROJECT.proj_id`
2. Every `TASK.wbs_id` must reference an existing `PROJWBS.wbs_id`
3. Every `TASK.clndr_id` must reference an existing `CALENDAR.clndr_id`
4. Every `TASKPRED.task_id` must reference an existing `TASK.task_id`
5. Every `TASKPRED.pred_task_id` must reference an existing `TASK.task_id`
6. Every `PROJWBS.parent_wbs_id` must reference an existing `PROJWBS.wbs_id` or be null (root)

**Schedule Integrity Validation:**
1. Data date (`PROJECT.last_recalc_date`) must be present and valid
2. Completed activities must have `act_start_date` and `act_end_date`
3. In-progress activities must have `act_start_date` and no `act_end_date`
4. Not-started activities must have no `act_start_date` and no `act_end_date`
5. Early dates must be present for non-completed activities
6. Total float should be calculable (early and late dates present)

### Reference Documents

- `docs/xer-format-reference.md` — Full XER format specification with field-level documentation
- Oracle P6 XER Import/Export Data Map: https://docs.oracle.com/cd/F51303_01/English/Mapping_and_Schema/xer_import_export_data_map_project/index.htm
- DCMA 14-Point Assessment standard
- GAO Schedule Assessment Guide (GAO-16-89G)

---

## Technology Validation Sources

The technology choices in this document were validated against the following 2025-2026 sources:

- FastAPI: v0.128+ (Feb 2026), ~94,800 GitHub stars, 40% adoption increase year-over-year, 3,000+ RPS benchmark
- SvelteKit: Svelte 5 with runes (stable), SvelteKit 2.x, 41% RPS advantage over Next.js, 50%+ smaller bundles
- NetworkX: v3.6 (stable), BSD-3-Clause, optimized Dijkstra (50x faster), new centrality algorithms
- Next.js: v15+ (stable), React Server Components mature — strong but heavier than SvelteKit for dashboard use cases
- D3.js: v7.x, ISC license, remains the standard for custom data visualization. No viable Gantt alternative that handles P6 scheduling semantics.
- Plotly: v5.x, MIT license, best-in-class interactive charting for scientific/analytical dashboards
- xerparser: GPL-3.0 license confirmed on PyPI — incompatible with MIT project goals
