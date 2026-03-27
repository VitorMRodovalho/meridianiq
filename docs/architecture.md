<!-- Last updated: 2026-03-26 -->
# MeridianIQ — System Architecture

## System Overview

MeridianIQ follows a **modular monolith** pattern: a single FastAPI application with clearly separated analysis engines, each implementing a specific published methodology. The frontend is a SvelteKit SPA communicating via REST API.

```mermaid
graph TB
    subgraph "Frontend — SvelteKit + Tailwind"
        UI[Browser Client]
        UI --> Dashboard[Dashboard]
        UI --> Upload[Upload]
        UI --> Projects[Projects + 5 Tabs]
        UI --> Compare[Compare]
        UI --> Forensic[Forensic / CPA]
        UI --> TIA[TIA]
        UI --> EVM[EVM]
        UI --> Risk[Risk / QSRA]
    end

    subgraph "API Layer — FastAPI"
        API[REST API Gateway<br/>32+ endpoints]
    end

    subgraph "Analysis Engines"
        direction LR
        P[XER Parser<br/>xer_reader.py]
        CPM[CPM Engine<br/>cpm.py · NetworkX]
        DCMA[DCMA 14-Point<br/>dcma14.py]
        COMP[Comparison<br/>comparison.py]
        FOR[Forensics / CPA<br/>forensics.py]
        TIA_E[TIA Engine<br/>tia.py]
        CON[Contract<br/>contract.py]
        EVM_E[EVM Engine<br/>evm.py]
        RISK[Monte Carlo<br/>risk.py · NumPy]
    end

    subgraph "Data Layer"
        MEM[(In-Memory Store<br/>v0.x)]
        DB[(SQLite → PostgreSQL<br/>v1.0 planned)]
    end

    Dashboard & Upload & Projects & Compare & Forensic & TIA & EVM & Risk <-->|HTTP| API
    API --> P
    API --> CPM
    API --> DCMA
    API --> COMP
    API --> FOR
    API --> TIA_E
    API --> CON
    API --> EVM_E
    API --> RISK
    P --> MEM
    CPM --> MEM
    COMP --> MEM

    style UI fill:#FF3E00,color:#fff
    style API fill:#009688,color:#fff
    style CPM fill:#4C9A2A,color:#fff
    style RISK fill:#013243,color:#fff
    style MEM fill:#3FCF8E,color:#fff
```

---

## Data Flow

### XER Upload → Analysis

```mermaid
sequenceDiagram
    participant B as Browser
    participant A as FastAPI
    participant P as XER Parser
    participant S as In-Memory Store
    participant E as Analysis Engines

    B->>A: POST /api/v1/upload (XER file)
    A->>P: Parse XER (streaming, encoding detection)
    P->>P: Detect encoding (UTF-8, Windows-1252, Latin-1)
    P->>P: Parse %T/%F/%R tables (TASK, PROJWBS, TASKPRED, etc.)
    P->>P: Build Pydantic models (17+ tables)
    P->>P: Generate composite keys (proj_id.task_id)
    P->>S: Store parsed project data
    A-->>B: 200 OK {project_id}

    B->>A: GET /api/v1/projects/{id}/validation
    A->>E: Run DCMA 14-Point
    E->>S: Read project data
    E-->>A: 14 check results + score
    A-->>B: DCMA results

    B->>A: GET /api/v1/projects/{id}/critical-path
    A->>E: Run CPM (NetworkX forward/backward pass)
    E->>S: Read activities + relationships
    E-->>A: Critical path + float values
    A-->>B: Critical path activities
```

### Schedule Comparison — Multi-Layer Matching

```mermaid
flowchart TD
    A[Baseline XER] --> C[Comparison Engine]
    B[Update XER] --> C

    C --> D{Match by task_id<br/>Tier 1}
    D -->|Matched| E[Detect Modifications]
    D -->|Unmatched| F{Match by task_code<br/>Tier 2}
    F -->|Matched| E
    F -->|Unmatched| G[Truly Added / Deleted]

    E --> H{task_code changed?}
    H -->|Yes| I[Code Restructuring Alert]
    H -->|No| J[Normal Modification]

    E --> K[Duration Changes]
    E --> L[Date Changes]
    E --> M[Float Changes]
    E --> N[Relationship Changes]
    E --> O[Constraint Changes]

    K & L & M & N & O --> P[Manipulation Detection]
    P --> Q[retroactive_date]
    P --> R[oos_progress]
    P --> S[constraint_masking]
    P --> T[duration_manipulation]

    style D fill:#009688,color:#fff
    style F fill:#FFA726,color:#fff
    style I fill:#EF5350,color:#fff
    style P fill:#D97757,color:#fff
```

### Forensic CPA — Window Analysis

```mermaid
flowchart LR
    subgraph "Schedule Updates"
        UP1[UP 01<br/>Jan 2025]
        UP2[UP 02<br/>Feb 2025]
        UP3[UP 03<br/>Mar 2025]
        UP4[UP 04<br/>Apr 2025]
    end

    subgraph "Analysis Windows"
        W1[Window 1<br/>UP01→UP02]
        W2[Window 2<br/>UP02→UP03]
        W3[Window 3<br/>UP03→UP04]
    end

    subgraph "Per Window"
        COMP2[Compare<br/>Consecutive Pair]
        DELAY[Delay<br/>Δ Completion Date]
        CP2[CP Evolution]
    end

    UP1 --> W1
    UP2 --> W1
    UP2 --> W2
    UP3 --> W2
    UP3 --> W3
    UP4 --> W3

    W1 & W2 & W3 --> COMP2
    COMP2 --> DELAY
    COMP2 --> CP2

    DELAY --> WF[Delay Waterfall<br/>Cumulative Chart]

    style WF fill:#D97757,color:#fff
```

### TIA — Time Impact Analysis

```mermaid
flowchart TD
    BASE[Base Schedule<br/>Unimpacted] --> CPM1[Run CPM<br/>Baseline Completion]

    FRAG[Delay Fragment<br/>Activities + Relationships] --> INSERT[Insert into<br/>Network Copy]
    BASE --> INSERT

    INSERT --> CPM2[Run CPM<br/>Impacted Completion]

    CPM1 --> DELTA[Δ = Impacted - Unimpacted]
    CPM2 --> DELTA

    DELTA --> CLASS{Classify}
    CLASS -->|Owner caused| EC[Excusable Compensable]
    CLASS -->|Force majeure| ENC[Excusable Non-Compensable]
    CLASS -->|Contractor caused| NE[Non-Excusable]
    CLASS -->|Multiple causes| CON[Concurrent]

    EC & ENC & NE & CON --> RESP[Responsibility<br/>Waterfall]

    style FRAG fill:#EF5350,color:#fff
    style RESP fill:#D97757,color:#fff
```

### Monte Carlo QSRA

```mermaid
flowchart TD
    SCHED[Parsed Schedule<br/>Activities + Relationships] --> ASSIGN[Assign Uncertainty<br/>min / likely / max]

    ASSIGN --> LOOP[For each iteration<br/>N = 1,000]

    LOOP --> SAMPLE[Sample durations<br/>PERT-Beta distribution]
    SAMPLE --> CPM3[Run CPM]
    CPM3 --> RECORD[Record completion date<br/>+ critical path]

    RECORD -->|Next iteration| LOOP

    RECORD --> AGG[Aggregate Results]
    AGG --> HIST[Histogram<br/>Completion Distribution]
    AGG --> PVAL[P-Values<br/>P10 · P50 · P80 · P90]
    AGG --> TORNADO[Tornado Diagram<br/>Spearman Sensitivity]
    AGG --> CRIT[Criticality Index<br/>% on CP per activity]
    AGG --> SCURVE[S-Curve<br/>Cumulative Probability]

    style LOOP fill:#013243,color:#fff
    style HIST fill:#1565C0,color:#fff
```

---

## Analysis Engines

| Engine | File | Lines | Standard | Key Dependencies |
|--------|------|-------|----------|-----------------|
| **XER Parser** | `src/parser/xer_reader.py` | 403 | — | Pydantic v2 |
| **CPM** | `src/analytics/cpm.py` | 405 | Kelly & Walker (1959) | NetworkX |
| **DCMA 14-Point** | `src/analytics/dcma14.py` | 651 | DCMA EVMS | — |
| **Comparison** | `src/analytics/comparison.py` | 916 | — | — |
| **Forensics (CPA)** | `src/analytics/forensics.py` | 435 | AACE RP 29R-03 | — |
| **TIA** | `src/analytics/tia.py` | 746 | AACE RP 52R-06 | NetworkX |
| **Contract** | `src/analytics/contract.py` | 671 | AIA A201, SCL Protocol | — |
| **EVM** | `src/analytics/evm.py` | 685 | ANSI/EIA-748 | — |
| **Monte Carlo** | `src/analytics/risk.py` | 723 | AACE RP 57R-09 | NumPy |

---

## API Endpoints

### Core (v0.1)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/upload` | Upload and parse XER file |
| GET | `/api/v1/projects` | List all parsed projects |
| GET | `/api/v1/projects/{id}` | Project detail with WBS stats |
| GET | `/api/v1/projects/{id}/validation` | DCMA 14-Point results |
| GET | `/api/v1/projects/{id}/critical-path` | Critical path activities |
| GET | `/api/v1/projects/{id}/float-distribution` | Float buckets |
| GET | `/api/v1/projects/{id}/milestones` | Milestone variance |
| POST | `/api/v1/compare` | Compare two schedules |

### Forensics (v0.2)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/forensic/create-timeline` | Create CPA timeline |
| GET | `/api/v1/forensic/timelines` | List timelines |
| GET | `/api/v1/forensic/timelines/{id}` | Timeline detail |
| GET | `/api/v1/forensic/timelines/{id}/delay-trend` | Delay waterfall data |

### Claims (v0.3)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/tia/analyze` | Run TIA with fragments |
| GET | `/api/v1/tia/analyses` | List TIA analyses |
| GET | `/api/v1/tia/analyses/{id}` | TIA detail |
| GET | `/api/v1/tia/analyses/{id}/summary` | Delay by responsibility |
| POST | `/api/v1/contract/check` | Run compliance checks |
| GET | `/api/v1/contract/provisions` | List provisions |

### Controls (v0.4)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/evm/analyze/{project_id}` | Run EVM analysis |
| GET | `/api/v1/evm/analyses` | List EVM analyses |
| GET | `/api/v1/evm/analyses/{id}` | EVM metrics detail |
| GET | `/api/v1/evm/analyses/{id}/s-curve` | S-curve data |
| GET | `/api/v1/evm/analyses/{id}/wbs-drill` | WBS cost breakdown |
| GET | `/api/v1/evm/analyses/{id}/forecast` | EAC scenarios |

### Risk (v0.5)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/risk/simulate/{project_id}` | Run Monte Carlo |
| GET | `/api/v1/risk/simulations` | List simulations |
| GET | `/api/v1/risk/simulations/{id}` | Simulation results |
| GET | `/api/v1/risk/simulations/{id}/histogram` | Completion histogram |
| GET | `/api/v1/risk/simulations/{id}/tornado` | Sensitivity data |
| GET | `/api/v1/risk/simulations/{id}/criticality` | Criticality index |
| GET | `/api/v1/risk/simulations/{id}/s-curve` | Cumulative probability |

---

## Data Model

### XER Tables Parsed

```mermaid
erDiagram
    PROJECT ||--o{ PROJWBS : "has"
    PROJECT ||--o{ TASK : "contains"
    PROJWBS ||--o{ TASK : "groups"
    TASK ||--o{ TASKPRED : "predecessor"
    TASK ||--o{ TASKRSRC : "resource assignment"
    TASK }o--|| CALENDAR : "uses"
    TASKRSRC }o--|| RSRC : "references"

    PROJECT {
        string proj_id PK
        string proj_short_name
        datetime last_recalc_date
    }

    PROJWBS {
        string wbs_id PK
        string parent_wbs_id FK
        string wbs_short_name
        string wbs_name
    }

    TASK {
        string task_id PK
        string task_code
        string task_name
        string task_type
        string status_code
        float total_float_hr_cnt
        float remain_drtn_hr_cnt
        datetime target_start_date
        datetime target_end_date
    }

    TASKPRED {
        string task_pred_id PK
        string task_id FK
        string pred_task_id FK
        string pred_type
        float lag_hr_cnt
    }
```

### In-Memory Store (v0.x)

All parsed data lives in Python dictionaries keyed by `project_id`. Each restart clears the store. Planned migration path:

```
v0.x: In-Memory (dict) → v1.0: SQLite → v1.x: PostgreSQL
```

---

## Frontend Pages

| Route | Description | API Dependency |
|-------|-------------|----------------|
| `/` | Dashboard — upload, project list | `GET /projects` |
| `/upload` | XER file upload | `POST /upload` |
| `/projects` | Project listing | `GET /projects` |
| `/projects/{id}` | 5-tab detail (Overview, DCMA, CP, Float, Milestones) | Multiple endpoints |
| `/compare` | Schedule comparison | `POST /compare` |
| `/forensic` | CPA timeline list + creation | Forensic endpoints |
| `/forensic/{id}` | Delay waterfall + window detail | Timeline endpoints |
| `/tia` | TIA analysis + fragment editor | TIA endpoints |
| `/tia/{id}` | TIA results + responsibility waterfall | TIA endpoints |
| `/evm` | EVM dashboard + S-curve | EVM endpoints |
| `/evm/{id}` | EVM detail + WBS drill-down | EVM endpoints |
| `/risk` | Monte Carlo setup + results | Risk endpoints |
| `/risk/{id}` | Histogram, tornado, criticality, S-curve | Risk endpoints |

---

## Design Principles

1. **Modular Engines** — Each analysis engine is a standalone Python module with no cross-dependencies. Engines communicate only through the data layer.
2. **Standards-First** — Every methodology traceable to a published standard. Code comments cite the relevant AACE RP, DCMA guideline, or academic reference.
3. **Progressive Complexity** — v0.x uses in-memory storage for rapid prototyping. Persistence (SQLite/PostgreSQL) planned for v1.0 without changing the API contract.
4. **Custom Parser** — MIT-licensed XER parser (cannot use GPL alternatives). Streaming, encoding-aware, handles real production files (8,000+ activities).
5. **Zero Cost** — No paid dependencies. All libraries are MIT/BSD compatible.

---

## Legacy v1 Architecture

The original v1 toolkit used Power Query (M Language) and DAX in Power BI for XER parsing and analysis. This approach is preserved in the `v1-reader/`, `v1-compare/`, and `v1-program-schedule/` directories.

For the legacy architecture documentation, see [`v1-architecture.md`](v1-architecture.md).

---

<div align="center">

**MeridianIQ** · MIT License · © 2025 Vitor Maia Rodovalho

</div>
