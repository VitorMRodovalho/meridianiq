# Architecture Draft — P6 XER Analytics v0.1

> System architecture for the "Foundation" release: Parse, Validate, Compare, Visualize.

**Document Status:** Draft v0.1
**Last Updated:** 2026-03-25
**Author:** Vitor Rodovalho

---

## Table of Contents

1. [System Context Diagram](#system-context-diagram)
2. [Data Model](#data-model)
3. [API Endpoints (v0.1)](#api-endpoints-v01)
4. [Module Structure](#module-structure)
5. [Technology Decisions Log](#technology-decisions-log)
6. [Development Phases](#development-phases)
7. [Security Considerations](#security-considerations)

---

## System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BROWSER (User)                                 │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Upload Page   │  │ Validation   │  │ Comparison   │  │ Baseline     │   │
│  │              │  │ Dashboard    │  │ Dashboard    │  │ Review       │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                  │                  │                  │           │
│         └──────────────────┴──────────────────┴──────────────────┘           │
│                                     │                                       │
│                           SvelteKit Frontend                                │
│                          (Svelte 5 + Tailwind)                              │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ HTTP/JSON (REST API)
                                      │
┌─────────────────────────────────────┴───────────────────────────────────────┐
│                          API LAYER (FastAPI)                                 │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ /api/upload   │  │ /api/        │  │ /api/compare │  │ /api/export  │   │
│  │              │  │ validation   │  │              │  │              │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                  │                  │                  │           │
│         └──────────────────┴──────────────────┴──────────────────┘           │
│                                     │                                       │
├─────────────────────────────────────┼───────────────────────────────────────┤
│                                     │                                       │
│  ┌──────────────────────────────────┴────────────────────────────────────┐  │
│  │                         CORE ENGINES                                  │  │
│  │                                                                       │  │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                │  │
│  │  │  XER Parser  │   │  Analytics   │   │  Export      │                │  │
│  │  │  Engine      │   │  Engine      │   │  Engine      │                │  │
│  │  │             │   │             │   │             │                │  │
│  │  │ - Parse XER  │   │ - CPM (NX)   │   │ - PDF Gen    │                │  │
│  │  │ - Validate   │   │ - DCMA-14    │   │ - Excel Gen  │                │  │
│  │  │ - Type XER   │   │ - Float Calc │   │ - Chart Img  │                │  │
│  │  │ - Build Model│   │ - Comparison │   │             │                │  │
│  │  │             │   │ - Manipulation│   │             │                │  │
│  │  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘                │  │
│  │         │                  │                  │                        │  │
│  └─────────┴──────────────────┴──────────────────┴────────────────────────┘  │
│                                     │                                       │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                          ┌───────────┴───────────┐
                          │                       │
                   ┌──────┴──────┐         ┌──────┴──────┐
                   │  SQLite     │         │  File       │
                   │  (v0.1)     │         │  Storage    │
                   │             │         │             │
                   │  Parsed     │         │  Uploaded   │
                   │  schedules, │         │  XER files, │
                   │  analysis   │         │  generated  │
                   │  results    │         │  PDFs       │
                   └─────────────┘         └─────────────┘
                          │
                   ┌──────┴──────┐
                   │ PostgreSQL  │
                   │  (v1.0+)    │
                   └─────────────┘
```

### Data Flow — Single XER Validation

```
User uploads .xer file
       │
       ▼
POST /api/upload (multipart/form-data)
       │
       ▼
XER Parser Engine
  ├── Read file as UTF-8
  ├── Parse ERMHDR
  ├── Parse all tables (%T, %F, %R)
  ├── Validate structure and types
  ├── Build Pydantic models
  └── Store in SQLite
       │
       ▼
Analytics Engine (triggered automatically)
  ├── CPM: Build NetworkX DiGraph
  │     ├── Forward pass (ES, EF)
  │     ├── Backward pass (LS, LF)
  │     ├── Calculate Total Float, Free Float
  │     └── Identify Critical Path
  ├── DCMA-14: Run 14-point checks
  │     ├── Logic completeness
  │     ├── Leads/lags
  │     ├── Relationship types
  │     ├── Constraints
  │     ├── High float
  │     ├── Negative float
  │     ├── High duration
  │     ├── Invalid dates
  │     ├── Resources
  │     ├── Missed tasks
  │     ├── Critical path test
  │     ├── CPLI
  │     └── BEI
  ├── Counts: Activities, relationships, calendars
  ├── Quality: Open ends, OOS, constraints
  └── Score: Composite validation score
       │
       ▼
Store AnalysisResult in SQLite
       │
       ▼
Return JSON → SvelteKit renders dashboard
```

---

## Data Model

### Entity Relationship Diagram

```
┌──────────────────┐       ┌──────────────────┐
│  ScheduleUpload  │       │  AnalysisResult   │
├──────────────────┤       ├──────────────────┤
│ PK upload_id     │──┐    │ PK result_id      │
│    filename      │  │    │ FK upload_id      │──┐
│    upload_date   │  │    │    analysis_type   │  │
│    file_size     │  │    │    score          │  │
│    file_hash     │  │    │    results_json   │  │
│    p6_version    │  │    │    created_at     │  │
│    status        │  │    └──────────────────┘  │
└──────────────────┘  │                           │
         │            │    ┌──────────────────┐   │
         │            └───►│ ValidationScore   │   │
         │                 ├──────────────────┤   │
         │                 │ PK score_id       │   │
         ▼                 │ FK upload_id      │◄──┘
┌──────────────────┐       │    total_score    │
│     Project      │       │    dcma_results   │
├──────────────────┤       │    quality_metrics│
│ PK proj_id       │       │    created_at     │
│ FK upload_id     │       └──────────────────┘
│    proj_short_name│
│    last_recalc_date│     ┌──────────────────┐
│    plan_start_date│      │ ComparisonResult  │
│    plan_end_date  │      ├──────────────────┤
│    data_date     │       │ PK comparison_id  │
└────────┬─────────┘       │ FK upload_id_prev │
         │                 │ FK upload_id_curr │
         │                 │    changed_pct    │
    ┌────┴────┐            │    activities_json│
    │         │            │    relations_json │
    ▼         ▼            │    flags_json     │
┌────────┐ ┌────────┐     │    created_at     │
│Calendar│ │  WBS   │     └──────────────────┘
├────────┤ ├────────┤
│PK clndr│ │PK wbs_id│
│  _id   │ │FK proj_id│
│  name  │ │FK parent │
│  type  │ │   _wbs_id│
│day_hr  │ │  wbs_name│
│week_hr │ │  proj_   │
└────────┘ │  node_flg│
     ▲     └────┬─────┘
     │          │
     │          ▼
     │   ┌──────────────────┐
     │   │    Activity       │
     │   │    (TASK)         │
     │   ├──────────────────┤
     └───│ PK task_id        │
         │ FK proj_id        │
         │ FK wbs_id         │
         │ FK clndr_id       │
         │    task_code      │
         │    task_name      │
         │    status_code    │───── Enum: TK_NotStart,
         │    task_type      │             TK_Active,
         │    early_start    │             TK_Complete
         │    early_end      │
         │    late_start     │
         │    late_end       │
         │    target_start   │
         │    target_end     │
         │    total_float_hr │
         │    free_float_hr  │
         │    remain_drtn_hr │
         │    target_drtn_hr │
         │    phys_complete  │
         │    cstr_type      │
         │    cstr_date      │
         └─────────┬────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
┌──────────────────┐  ┌──────────────────┐
│   Predecessor    │  │    Resource      │
│   (TASKPRED)     │  │   Assignment     │
├──────────────────┤  │   (TASKRSRC)     │
│ FK task_id       │  ├──────────────────┤
│ FK pred_task_id  │  │ FK task_id       │
│ FK proj_id       │  │ FK rsrc_id       │──►┌──────────┐
│ FK pred_proj_id  │  │    target_qty    │   │ Resource  │
│    pred_type     │  │    act_reg_qty   │   │ (RSRC)   │
│    lag_hr_cnt    │  │    remain_qty    │   ├──────────┤
└──────────────────┘  └──────────────────┘   │PK rsrc_id│
                                              │  name    │
         ┌──────────────────┐                 │  type    │
         │  ActivityCode    │                 └──────────┘
         ├──────────────────┤
         │ FK task_id       │──►┌──────────────────┐
         │ FK actv_code_id  │   │ ActivityCodeType  │
         │    code_value    │   │ (ACTVTYPE)        │
         └──────────────────┘   ├──────────────────┤
                                │ PK actv_code_     │
         ┌──────────────────┐   │    type_id        │
         │    UDFValue      │   │    name           │
         ├──────────────────┤   └──────────────────┘
         │ FK task_id       │
         │ FK udf_type_id   │──►┌──────────────────┐
         │    udf_text      │   │    UDFType        │
         │    udf_number    │   │   (UDFTYPE)       │
         │    udf_date      │   ├──────────────────┤
         └──────────────────┘   │ PK udf_type_id   │
                                │    table_name     │
         ┌──────────────────┐   │    label          │
         │    Baseline      │   │    data_type      │
         ├──────────────────┤   └──────────────────┘
         │ PK baseline_id   │
         │ FK proj_id       │
         │    name          │
         │    type          │
         │    last_update   │
         └──────────────────┘
```

### Core Entities Summary

| Entity | Source Table | v0.1 Role | Record Count (typical) |
|--------|-------------|-----------|----------------------|
| **ScheduleUpload** | Application | Root entity for each uploaded XER file | 1 per upload |
| **Project** | PROJECT | Project metadata, data date | 1-5 per XER |
| **Calendar** | CALENDAR | Work calendar for duration calculations | 1-10 per XER |
| **WBS** | PROJWBS | Work Breakdown Structure hierarchy | 10-200 per project |
| **Activity** | TASK | Core schedule data — all analysis operates on activities | 100-5,000 per project |
| **Predecessor** | TASKPRED | Activity relationships — defines the network for CPM | 200-10,000 per project |
| **Resource** | RSRC | Resource definitions (parsed, not analyzed in v0.1) | 0-100 per XER |
| **ResourceAssignment** | TASKRSRC | Task-resource links (parsed, not analyzed in v0.1) | 0-10,000 per project |
| **ActivityCode** | ACTVCODE | Activity classification codes | 10-200 per project |
| **ActivityCodeType** | ACTVTYPE | Activity code type definitions | 1-20 per XER |
| **UDFType** | UDFTYPE | User-defined field definitions | 0-50 per XER |
| **UDFValue** | UDFVALUE | User-defined field values | 0-10,000 per project |
| **Baseline** | Application | Baseline schedule reference (derived from XER data) | 0-5 per project |
| **AnalysisResult** | Application | Stored analysis output (DCMA-14, CPM, etc.) | 1+ per upload |
| **ValidationScore** | Application | Composite validation score with per-metric details | 1 per upload |
| **ComparisonResult** | Application | Period-to-period comparison results | 1 per comparison |

---

## API Endpoints (v0.1)

### POST /api/upload

**Description:** Upload a single XER file for parsing and automatic validation.

**Request:**
```
Content-Type: multipart/form-data

Body:
  file: <binary .xer file>  (required, max 50MB)
```

**Response (201 Created):**
```json
{
  "upload_id": "uuid-string",
  "filename": "Project_Update_Jun2024.xer",
  "file_size": 245760,
  "p6_version": "23.12",
  "projects": [
    {
      "proj_id": 12345,
      "proj_short_name": "LIBRARY-RENO",
      "data_date": "2024-06-01T00:00:00",
      "activity_count": 334,
      "relationship_count": 577
    }
  ],
  "parse_status": "success",
  "validation_status": "complete",
  "validation_score": 82,
  "links": {
    "validation": "/api/validation/uuid-string",
    "project": "/api/project/12345",
    "critical_path": "/api/critical-path/12345",
    "float_distribution": "/api/float-distribution/12345",
    "export_pdf": "/api/export/pdf/uuid-string"
  }
}
```

**Error Responses:**
- `400 Bad Request` — Invalid file format, not a .xer file, corrupt structure
- `413 Payload Too Large` — File exceeds 50MB limit
- `422 Unprocessable Entity` — XER file parsed but contains structural errors (missing required tables, referential integrity violations)

---

### GET /api/project/{proj_id}

**Description:** Retrieve parsed project data including schedule counts and summary statistics.

**Request:**
```
GET /api/project/12345
```

**Response (200 OK):**
```json
{
  "proj_id": 12345,
  "proj_short_name": "LIBRARY-RENO",
  "data_date": "2024-06-01T00:00:00",
  "schedule_start": "2023-02-06T00:00:00",
  "schedule_finish": "2024-07-29T00:00:00",
  "must_finish_by": "2024-06-30T00:00:00",
  "percent_complete": 55.0,
  "counts": {
    "activities": {
      "total": 334,
      "by_type": {
        "task": 315,
        "finish_milestone": 12,
        "level_of_effort": 7,
        "start_milestone": 0,
        "wbs_summary": 0
      },
      "by_status": {
        "not_started": 150,
        "in_progress": 19,
        "completed": 165
      }
    },
    "relationships": {
      "total": 577,
      "by_type": {
        "FS": 526,
        "FF": 45,
        "SS": 6,
        "SF": 0
      }
    },
    "calendars": {
      "project": 5,
      "linked": 2,
      "global": 1
    },
    "resources": 0,
    "resource_assignments": 0
  }
}
```

**Error Responses:**
- `404 Not Found` — Project ID not found in any uploaded XER

---

### GET /api/validation/{upload_id}

**Description:** Retrieve full DCMA 14-Point Assessment and quality metrics for an uploaded schedule.

**Request:**
```
GET /api/validation/uuid-string
```

**Response (200 OK):**
```json
{
  "upload_id": "uuid-string",
  "validation_score": 82,
  "scoring_standard": "2024",
  "dcma_14_point": {
    "logic": {"score": "GREEN", "value": 98, "threshold": 95, "description": "Activities with logic ties"},
    "leads": {"score": "GREEN", "value": 0, "threshold": 0, "description": "Negative lag count"},
    "lags": {"score": "GREEN", "value": 0, "threshold": 5, "description": "FS relationships with positive lag"},
    "relationship_types": {"score": "GREEN", "value": 0, "threshold": 0, "description": "SF relationships"},
    "hard_constraints": {"score": "GREEN", "value": 1, "threshold": 5, "description": "Activities with hard constraints"},
    "high_float": {"score": "RED", "value": 19, "threshold": 5, "description": "Activities with >44 day total float"},
    "negative_float": {"score": "GREEN", "value": 0, "threshold": 0, "description": "Activities with negative float"},
    "high_duration": {"score": "YELLOW", "value": 13, "threshold": 5, "description": "Activities with >44 day duration"},
    "invalid_dates": {"score": "GREEN", "value": 0, "threshold": 0, "description": "Activities with invalid date logic"},
    "resources": {"score": "YELLOW", "value": 0, "threshold": 50, "description": "Activities with resource assignments"},
    "missed_tasks": {"score": "GREEN", "value": 0, "threshold": 5, "description": "Completed tasks past data date without actuals"},
    "critical_path_test": {"score": "GREEN", "value": true, "threshold": true, "description": "Critical path reaches project end"},
    "cpli": {"score": "GREEN", "value": 1.02, "threshold": 0.95, "description": "Critical Path Length Index"},
    "bei": {"score": "GREEN", "value": 0.98, "threshold": 0.90, "description": "Baseline Execution Index"}
  },
  "quality_metrics": {
    "date_constraints": {"count": 1, "percent": 0.3, "score": "GREEN"},
    "critical_path": {"count": 79, "percent": 23.7, "score": "GREEN"},
    "near_critical_path": {"count": 253, "percent": 75.7, "score": "RED"},
    "out_of_sequence": {"count": 5, "percent": 1.5, "score": "YELLOW"},
    "negative_lags": {"count": 0, "percent": 0.0, "score": "GREEN"},
    "fs_lags": {"count": 0, "percent": 0.0, "score": "GREEN"},
    "long_lags": {"count": 1, "percent": 0.3, "score": "YELLOW"},
    "high_float": {"count": 19, "percent": 5.7, "score": "RED"},
    "high_duration": {"count": 13, "percent": 3.9, "score": "YELLOW"},
    "invalid_dates": {"count": 0, "percent": 0.0, "score": "GREEN"},
    "duplicate_descriptions": {"count": 178, "percent": 53.3, "score": "GREEN"}
  },
  "relationship_quality": {
    "avg_logic_ties": {"value": 4, "score": "YELLOW"},
    "no_successors": {"count": 3, "percent": 0.9, "score": "RED"},
    "no_predecessors": {"count": 3, "percent": 0.9, "score": "RED"},
    "open_finish": {"count": 2, "percent": 0.6, "score": "RED"},
    "open_start": {"count": 5, "percent": 1.5, "score": "RED"},
    "duplicates_present": {"count": 0, "percent": 0.0, "score": "GREEN"},
    "riding_data_date": {"count": 2, "percent": 0.6, "score": "YELLOW"},
    "network_hotspots": {"count": 0, "percent": 0.0, "score": "GREEN"}
  }
}
```

---

### POST /api/compare

**Description:** Compare two uploaded XER files and produce a change report.

**Request:**
```json
{
  "previous_upload_id": "uuid-previous",
  "current_upload_id": "uuid-current",
  "project_id": 12345
}
```

**Response (200 OK):**
```json
{
  "comparison_id": "uuid-comparison",
  "previous_upload_id": "uuid-previous",
  "current_upload_id": "uuid-current",
  "changed_percentage": 23.5,
  "summary": {
    "activities": {
      "added": 12,
      "modified": 45,
      "deleted": 3,
      "unchanged": 274
    },
    "relationships": {
      "added": 18,
      "modified": 8,
      "deleted": 5,
      "unchanged": 546
    }
  },
  "activity_changes": [
    {
      "task_code": "A1050",
      "task_name": "Install Electrical Conduit",
      "change_type": "modified",
      "changes": {
        "target_drtn_hr_cnt": {"old": 360, "new": 80, "change_pct": -77.8},
        "early_end_date": {"old": "2024-08-15T00:00:00", "new": "2024-07-01T00:00:00"}
      },
      "flags": ["SUSPICIOUS: Duration reduced 77.8% without progress update"]
    }
  ],
  "relationship_changes": [
    {
      "task_code": "A1050",
      "pred_task_code": "A1040",
      "change_type": "modified",
      "changes": {
        "pred_type": {"old": "PR_FS", "new": "PR_SS"},
        "lag_hr_cnt": {"old": 0, "new": -16}
      }
    }
  ],
  "suspicious_flags": [
    {
      "type": "duration_compression",
      "activity": "A1050",
      "description": "Duration reduced from 45d to 10d without corresponding progress",
      "severity": "HIGH"
    }
  ],
  "links": {
    "export_pdf": "/api/export/pdf/uuid-comparison"
  }
}
```

---

### GET /api/critical-path/{proj_id}

**Description:** Retrieve the longest critical path for a project.

**Request:**
```
GET /api/critical-path/12345
```

**Response (200 OK):**
```json
{
  "proj_id": 12345,
  "critical_path": {
    "total_duration_days": 540,
    "activity_count": 79,
    "path": [
      {
        "task_code": "PM1000",
        "task_name": "Notice to Proceed",
        "task_type": "TT_mile",
        "duration_days": 0,
        "early_start": "2023-02-06T00:00:00",
        "early_finish": "2023-02-06T00:00:00",
        "total_float_days": 0,
        "free_float_days": 0,
        "status": "TK_Complete"
      },
      {
        "task_code": "A1010",
        "task_name": "Mobilization & Site Prep",
        "task_type": "TT_Task",
        "duration_days": 30,
        "early_start": "2023-02-06T00:00:00",
        "early_finish": "2023-03-20T00:00:00",
        "total_float_days": 0,
        "free_float_days": 0,
        "status": "TK_Complete"
      }
    ],
    "narrative": "NTP (Feb-06-23) → Mobilization/Site Prep (Mar-20-23) → Foundation/Slab (Jun-23-23) → Exterior Wall Framing (Oct-19-23) → Library Interior/MEP (May-29-24) → Closeout/Punch List/Final Inspection (Jul-29-24)"
  },
  "near_critical_paths": {
    "threshold_days": 10,
    "count": 253,
    "paths": []
  }
}
```

---

### GET /api/float-distribution/{proj_id}

**Description:** Retrieve Total Float distribution categorized by standard ranges.

**Request:**
```
GET /api/float-distribution/12345
```

**Response (200 OK):**
```json
{
  "proj_id": 12345,
  "total_activities": 334,
  "distribution": {
    "critical": {"range": "0 days", "count": 64, "percent": 19.2},
    "near_critical": {"range": "1-10 days", "count": 23, "percent": 6.9},
    "moderate": {"range": "11-20 days", "count": 42, "percent": 12.6},
    "semi_moderate": {"range": "21-44 days", "count": 89, "percent": 26.6},
    "not_critical": {"range": ">44 days", "count": 116, "percent": 34.7}
  },
  "compliance": {
    "critical_plus_near_critical_pct": 26.1,
    "threshold_pct": 25.0,
    "status": "FAIL",
    "note": "Combined critical and near-critical percentage (26.1%) exceeds contract threshold (25%)"
  },
  "chart_data": {
    "type": "bar",
    "categories": ["Critical (0d)", "Near-Critical (1-10d)", "Moderate (11-20d)", "Semi-Moderate (21-44d)", "Not Critical (>44d)"],
    "values": [64, 23, 42, 89, 116],
    "colors": ["#dc2626", "#f97316", "#eab308", "#22c55e", "#3b82f6"]
  }
}
```

---

### GET /api/export/pdf/{upload_id}

**Description:** Generate and download a PDF validation report for an uploaded schedule, or a comparison report if the upload_id refers to a comparison.

**Request:**
```
GET /api/export/pdf/uuid-string
GET /api/export/pdf/uuid-comparison
```

**Query Parameters:**
- `report_type` (optional): `validation` (default), `comparison`, `baseline_review`
- `include_details` (optional): `true` (default) — include activity-level detail tables

**Response (200 OK):**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="Validation_Report_LIBRARY-RENO_2024-06-01.pdf"

<binary PDF data>
```

**Error Responses:**
- `404 Not Found` — Upload ID not found
- `409 Conflict` — Analysis still in progress, PDF cannot be generated yet

---

## Module Structure

```
p6-xer-analytics/
├── src/
│   ├── parser/                     # Custom XER Parser Engine
│   │   ├── __init__.py
│   │   ├── reader.py               # File I/O, line splitting, encoding handling
│   │   ├── tokenizer.py            # %T/%F/%R/%E line classification
│   │   ├── table_parser.py         # Table-level parsing (fields + rows → dicts)
│   │   ├── models.py               # Pydantic models (XERFile, Activity, Predecessor, etc.)
│   │   ├── validators.py           # Structural, type, and referential integrity validation
│   │   ├── enums.py                # ActivityStatus, TaskType, PredType, ConstraintType enums
│   │   └── exceptions.py           # XERParseError, XERValidationError custom exceptions
│   │
│   ├── analytics/                  # Analytics Engine
│   │   ├── __init__.py
│   │   ├── cpm.py                  # Critical Path Method (forward/backward pass, NetworkX)
│   │   ├── dcma14.py               # DCMA 14-Point Assessment (all 14 checks)
│   │   ├── float_analysis.py       # Total/Free Float calculation, distribution, categories
│   │   ├── comparison.py           # Period-to-period comparison engine
│   │   ├── manipulation.py         # Suspicious change detection (flags, heuristics)
│   │   ├── quality_metrics.py      # Quality metrics, traffic lights, scoring
│   │   ├── schedule_counts.py      # Activity/relationship/calendar counts by category
│   │   └── validation_score.py     # Composite score algorithm (0-100)
│   │
│   ├── api/                        # FastAPI API Layer
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app creation, middleware, CORS
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── upload.py           # POST /api/upload
│   │   │   ├── project.py          # GET /api/project/{id}
│   │   │   ├── validation.py       # GET /api/validation/{id}
│   │   │   ├── comparison.py       # POST /api/compare
│   │   │   ├── critical_path.py    # GET /api/critical-path/{id}
│   │   │   ├── float_dist.py       # GET /api/float-distribution/{id}
│   │   │   └── export.py           # GET /api/export/pdf/{id}
│   │   ├── schemas.py              # Pydantic request/response schemas for API
│   │   ├── dependencies.py         # Dependency injection (DB sessions, services)
│   │   └── errors.py               # Error handlers, HTTP exception mapping
│   │
│   ├── export/                     # Export Engine
│   │   ├── __init__.py
│   │   ├── pdf_generator.py        # PDF report generation (WeasyPrint or ReportLab)
│   │   ├── pdf_templates/          # HTML/CSS templates for PDF rendering
│   │   │   ├── validation_report.html
│   │   │   ├── comparison_report.html
│   │   │   └── baseline_review.html
│   │   └── excel_generator.py      # Excel export (future, placeholder)
│   │
│   ├── db/                         # Data Persistence
│   │   ├── __init__.py
│   │   ├── database.py             # SQLAlchemy engine, session factory
│   │   ├── models.py               # SQLAlchemy ORM models
│   │   └── migrations/             # Alembic migrations (v1.0+)
│   │
│   └── web/                        # SvelteKit Frontend
│       ├── src/
│       │   ├── routes/
│       │   │   ├── +page.svelte           # Home / Upload page
│       │   │   ├── validation/
│       │   │   │   └── [id]/+page.svelte  # Validation dashboard
│       │   │   ├── comparison/
│       │   │   │   └── [id]/+page.svelte  # Comparison dashboard
│       │   │   └── baseline/
│       │   │       └── [id]/+page.svelte  # Baseline review dashboard
│       │   ├── lib/
│       │   │   ├── components/            # Reusable Svelte components
│       │   │   │   ├── ScoreCard.svelte
│       │   │   │   ├── TrafficLight.svelte
│       │   │   │   ├── FloatChart.svelte
│       │   │   │   ├── ActivityTable.svelte
│       │   │   │   ├── CriticalPathViewer.svelte
│       │   │   │   ├── ComparisonTable.svelte
│       │   │   │   └── FileUpload.svelte
│       │   │   ├── api.ts                 # API client (fetch wrapper)
│       │   │   └── types.ts               # TypeScript interfaces matching API schemas
│       │   └── app.html
│       ├── static/
│       ├── svelte.config.js
│       ├── tailwind.config.js
│       └── package.json
│
├── tests/
│   ├── parser/
│   │   ├── test_reader.py
│   │   ├── test_tokenizer.py
│   │   ├── test_table_parser.py
│   │   ├── test_models.py
│   │   └── test_validators.py
│   ├── analytics/
│   │   ├── test_cpm.py
│   │   ├── test_dcma14.py
│   │   ├── test_float_analysis.py
│   │   ├── test_comparison.py
│   │   └── test_manipulation.py
│   ├── api/
│   │   ├── test_upload.py
│   │   ├── test_validation.py
│   │   └── test_comparison.py
│   ├── fixtures/                   # Reference XER files for testing
│   │   ├── sample_500_activities.xer
│   │   ├── sample_baseline.xer
│   │   ├── sample_update.xer
│   │   └── sample_corrupt.xer
│   └── conftest.py
│
├── docs/
│   ├── v2-definition/              # This directory
│   │   ├── MVP_DEFINITION.md
│   │   ├── TECHNOLOGY_ASSESSMENT.md
│   │   └── ARCHITECTURE_DRAFT.md
│   ├── v2-discovery/               # Discovery phase documents
│   ├── xer-format-reference.md
│   └── architecture.md             # Legacy architecture doc
│
├── docker-compose.yml              # Backend + Frontend + DB orchestration
├── Dockerfile.backend              # Python backend container
├── Dockerfile.frontend             # SvelteKit frontend container
├── pyproject.toml                  # Python project config (dependencies, tools)
├── README.md
├── LICENSE                         # MIT License
└── .github/
    └── workflows/
        ├── ci.yml                  # Run tests on push/PR
        └── release.yml             # Build and push Docker images
```

---

## Technology Decisions Log

| # | Decision | Choice | Rationale | Alternatives Considered |
|---|----------|--------|-----------|------------------------|
| TD-01 | Programming language (backend) | Python 3.12+ | Dominant language for schedule analysis, CPM algorithms, and scientific computing. NetworkX, Pandas, NumPy ecosystem. 5-10% performance improvement in 3.12 interpreter. | TypeScript (NestJS) — rejected: no NetworkX/Pandas equivalent. Rust — rejected: overkill for v0.1 schedule sizes. |
| TD-02 | Web framework (backend) | FastAPI 0.128+ | De facto Python API standard (94,800 GitHub stars). Automatic OpenAPI docs, async support, Pydantic V2 integration. 3,000+ RPS. | Django REST Framework — rejected: heavier, not async-native. Flask — rejected: no built-in validation or OpenAPI. |
| TD-03 | Frontend framework | SvelteKit 2.x (Svelte 5) | 50%+ smaller bundles than Next.js, 41% higher RPS, fine-grained reactivity with runes, minimal runtime overhead. Ideal for data-heavy dashboards. | Next.js — rejected: larger bundles, React runtime overhead. HTMX — rejected: insufficient for interactive charts/tables. |
| TD-04 | Graph library (CPM) | NetworkX 3.6 | Mature, BSD-3-Clause, DiGraph + topological sort + longest path. Python-native. Custom ES/EF/LS/LF layered on top. | igraph — rejected: C-based, harder to debug. graph-tool — rejected: GPL license. Custom from scratch — rejected: unnecessary when NetworkX provides graph primitives. |
| TD-05 | XER parser | Custom (MIT) | xerparser is GPL-3.0 (license incompatible). PyP6Xer has limited table support. Custom parser ensures MIT compliance and full Oracle P6 table coverage. | xerparser — rejected: GPL. PyP6Xer — rejected: incomplete. xer-reader — rejected: Power BI focused. |
| TD-06 | Data validation | Pydantic V2 | Native FastAPI integration. 5-50x faster than V1. Typed models for all XER tables. Automatic JSON serialization. | dataclasses — rejected: no validation. marshmallow — rejected: not integrated with FastAPI. attrs — rejected: less ecosystem support. |
| TD-07 | Database (v0.1) | SQLite | Zero configuration, file-based, sufficient for single-user prototype. Bundled with Python. SQLAlchemy ORM ensures painless migration to PostgreSQL. | PostgreSQL — deferred to v1.0 (overkill for prototype). |
| TD-08 | Database (v1.0+) | PostgreSQL | Full ACID, concurrent access, JSON columns, proven at scale. Required for multi-tenant SaaS. | MySQL — rejected: weaker JSON support. MongoDB — rejected: relational data model is better fit for XER structure. |
| TD-09 | Charting (interactive) | Plotly.js + D3.js | Plotly for standard charts (bar, pie, scatter) with rich interactivity. D3 for custom visualizations (Gantt, network diagram) where no off-the-shelf library handles P6 semantics. | Recharts — rejected: React-only. Chart.js — rejected: limited customization. Highcharts — rejected: commercial license. |
| TD-10 | PDF generation | WeasyPrint | HTML/CSS to PDF conversion matches web dashboard appearance. Easier to maintain than programmatic PDF (ReportLab). BSD-3-Clause license. | ReportLab — backup option if WeasyPrint layout proves insufficient. wkhtmltopdf — rejected: deprecated. |
| TD-11 | CSS framework | Tailwind CSS 4.x | Utility-first, consistent styling, dark mode, responsive. No custom CSS files to maintain. MIT license. | Bootstrap — rejected: heavier, less customizable. Plain CSS — rejected: maintenance overhead. |
| TD-12 | Table component | TanStack Table 8.x | Headless, framework-agnostic (Svelte adapter), virtual scrolling for 500+ rows, sorting, filtering, column resizing. MIT license. | AG Grid — rejected: commercial for advanced features. Custom — rejected: table requirements are complex. |
| TD-13 | Deployment | Docker Compose | Single command to run entire stack. Consistent across dev/staging/prod. Standard industry practice. | Bare metal — rejected: not reproducible. Kubernetes — deferred to v1.0 (overkill for prototype). |
| TD-14 | Testing | pytest + Vitest | pytest for Python backend (parser, analytics, API). Vitest for SvelteKit frontend. Both fast, modern, well-supported. | unittest — rejected: verbose. Jest — rejected: slower than Vitest. |

---

## Development Phases

### Phase 1: XER Parser + Basic Tests (2 weeks)

**Deliverables:**
- Custom MIT-licensed XER parser reading all line types (ERMHDR, %T, %F, %R, %E)
- Pydantic models for all 17+ XER tables
- Structural validation (line types, field counts, data types)
- Referential integrity validation
- Unit tests with sample XER files (minimum 3: small, medium, corrupt)
- Parse a reference 500-activity XER file in < 5 seconds

**Key files:** `src/parser/*.py`, `tests/parser/*.py`, `tests/fixtures/*.xer`

### Phase 2: CPM + DCMA-14 Engine (2 weeks)

**Deliverables:**
- NetworkX DiGraph construction from parsed TASK + TASKPRED data
- Forward pass (ES, EF) and backward pass (LS, LF) calculation
- Total Float and Free Float computation for all activities
- Longest Critical Path identification
- Float distribution categorization (5 categories)
- All 14 DCMA checks implemented and tested
- Composite Schedule Validation Score algorithm (0-100)
- Quality metrics with traffic-light thresholds
- Unit tests validating CPM output against P6 Professional reference values

**Key files:** `src/analytics/*.py`, `tests/analytics/*.py`

### Phase 3: Comparison Engine (1 week)

**Deliverables:**
- Activity matching across two parsed XER files (by task_id, fallback to task_code)
- Change detection: added, modified, deleted, unchanged for activities and relationships
- Field-level change tracking (dates, durations, logic, status)
- Changed Percentage calculation
- Manipulation detection heuristics (duration compression, retroactive logic changes, constraint additions)
- Unit tests with reference XER pair (known change set)

**Key files:** `src/analytics/comparison.py`, `src/analytics/manipulation.py`, `tests/analytics/test_comparison.py`

### Phase 4: FastAPI Endpoints (1 week)

**Deliverables:**
- All 7 API endpoints implemented and documented (automatic OpenAPI/Swagger)
- File upload handling with size and format validation
- JSON response schemas matching the API specification above
- Error handling with appropriate HTTP status codes
- CORS configuration for SvelteKit frontend
- Integration tests for all endpoints using httpx/TestClient

**Key files:** `src/api/*.py`, `tests/api/*.py`

### Phase 5: Frontend Dashboard (2 weeks)

**Deliverables:**
- SvelteKit project setup with Tailwind CSS, Plotly.js, D3.js, TanStack Table
- Upload page with drag-and-drop file upload
- Validation dashboard with score card, DCMA-14 panel, quality metrics, relationship quality
- Comparison dashboard with summary, activity changes table, relationship changes, flags
- Baseline review dashboard with critical path viewer, float distribution chart, milestone table
- Responsive layout, dark mode support
- API client connecting to FastAPI backend

**Key files:** `src/web/**`

### Phase 6: PDF Export + Polish (1 week)

**Deliverables:**
- WeasyPrint-based PDF generation for validation report
- PDF template matching web dashboard layout
- Comparison report PDF
- Baseline review report PDF
- Polish: loading states, error messages, empty states, edge cases
- End-to-end testing (upload XER -> view dashboard -> download PDF)

**Key files:** `src/export/*.py`, `src/export/pdf_templates/*.html`

### Phase 7: Docker + Deployment (1 week)

**Deliverables:**
- Dockerfile for Python backend (multi-stage build, slim image)
- Dockerfile for SvelteKit frontend (Node build + Nginx static serve)
- docker-compose.yml orchestrating backend + frontend + SQLite volume
- Environment variable configuration (.env.example)
- GitHub Actions CI pipeline (lint, test, build)
- README with setup instructions
- LICENSE file (MIT)

**Key files:** `Dockerfile.backend`, `Dockerfile.frontend`, `docker-compose.yml`, `.github/workflows/ci.yml`

### Total Estimated Duration: 10 weeks

```
Week 1-2:   Phase 1 — XER Parser
Week 3-4:   Phase 2 — CPM + DCMA-14
Week 5:     Phase 3 — Comparison Engine
Week 6:     Phase 4 — FastAPI Endpoints
Week 7-8:   Phase 5 — Frontend Dashboard
Week 9:     Phase 6 — PDF Export + Polish
Week 10:    Phase 7 — Docker + Deployment
```

---

## Security Considerations

### File Upload Security

| Threat | Mitigation |
|--------|-----------|
| Oversized files causing memory exhaustion | Enforce 50MB file size limit at the API layer (FastAPI UploadFile + nginx client_max_body_size) |
| Malicious file content (code injection) | XER files are pure tab-delimited text. Parser reads text only — no `eval()`, no `exec()`, no dynamic code execution. All values are parsed as strings first, then explicitly cast to typed Pydantic fields. |
| Path traversal via filename | Uploaded files are renamed to UUID-based names. Original filename is stored in metadata only, never used for filesystem operations. |
| Zip bombs / decompression attacks | XER files are not compressed. Reject any file that does not start with `ERMHDR`. |
| Concurrent upload abuse | Rate limiting: maximum 10 uploads per minute per IP (configurable). |

### Data Privacy

| Principle | Implementation |
|-----------|---------------|
| No permanent storage without consent | v0.1 stores parsed data in SQLite for the duration of the session only. Data is purged after 24 hours (configurable) or on explicit user action. |
| No data transmission to third parties | All processing is local. No external API calls. No telemetry. No analytics. |
| GDPR-friendly | No user accounts in v0.1. No cookies beyond session. No PII collected. |
| XER data sensitivity | XER files may contain proprietary project data (activity names, contractor names, resource names). All data is treated as confidential. Logs never contain XER content. |

### Application Security

| Measure | Implementation |
|---------|---------------|
| HTTPS required in production | Nginx reverse proxy with TLS termination. HTTP redirects to HTTPS. HSTS header. |
| CORS configuration | Whitelist frontend origin only. No wildcard (`*`) in production. |
| Input validation | All API inputs validated by Pydantic schemas. Unknown fields rejected. |
| Dependency security | Automated `pip audit` and `npm audit` in CI pipeline. Dependabot for automatic security updates. |
| No authentication in v0.1 | Single-user prototype. Authentication deferred to v1.0 (JWT + OAuth2). |
| Content Security Policy | CSP headers restricting script sources to self + CDN for Plotly/D3. No inline scripts. |

### XER-Specific Security

| Consideration | Approach |
|---------------|----------|
| XER files are text, not executable | Parser treats all content as data. No shell commands, no file system operations based on XER content. |
| Large XER files (10,000+ activities) | Streaming parser reads line-by-line. Memory-mapped file I/O for files > 10MB. Maximum activity count: 50,000 (configurable). |
| Multi-project XER files | Each project within an XER is isolated. Cross-project references validated but do not enable data leakage between projects. |
| Unicode handling | UTF-8 with BOM detection. Invalid characters replaced, not failed on, with warnings. |
