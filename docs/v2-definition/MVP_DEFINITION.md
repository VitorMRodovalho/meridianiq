# MVP Definition — v0.1 "Foundation"

> P6 XER Analytics — From reactive manual schedule analysis to automated schedule intelligence.

**Document Status:** Draft v0.1
**Last Updated:** 2026-03-25
**Author:** Vitor Rodovalho

---

## Table of Contents

1. [MVP Selection Criteria](#mvp-selection-criteria)
2. [v0.1 Scope — "Parse, Validate, Compare, Visualize"](#v01-scope--parse-validate-compare-visualize)
3. [Release Roadmap](#release-roadmap)
4. [Success Criteria for v0.1](#success-criteria-for-v01)
5. [User Flows for v0.1](#user-flows-for-v01)

---

## MVP Selection Criteria

The MVP scope was selected using a three-layer prioritization framework, applied in strict order:

### 1. Table Stakes First — What Users Expect Minimum

These are the features without which the product has **zero credibility** in the construction scheduling market. Every scheduler who downloads an XER analysis tool expects, at a bare minimum:

- **XER parsing** that handles all Oracle P6 tables correctly (not just TASK and TASKPRED)
- **DCMA 14-Point Assessment** — the industry-standard schedule health check. Any tool that cannot produce this is immediately dismissed by professionals.
- **Schedule counts and summary statistics** — activities by type and status, relationships by type, calendars, resources. This is the first thing a scheduler looks at.
- **Open-end detection and constraint analysis** — fundamental quality checks that even free tools provide.
- **PDF export** — schedulers need to attach reports to correspondence and submittals.

Without these, the tool is a toy. With them, it is a credible alternative to Schedule Validator and Acumen Fuse.

### 2. Blue Ocean Second — What Differentiates

These are features that go beyond what free tools offer but are not yet standard in expensive commercial tools:

- **Period-to-period schedule comparison** with change categorization — Schedule Validator offers this as a premium feature. Most free tools do not support it at all.
- **Schedule manipulation indicators** — flagging suspicious patterns like retroactive logic changes, unreasonable duration compressions, and float suppression. This is rare even in commercial tools.
- **Changed Percentage score** — a single number summarizing how much a schedule changed between two updates. Powerful for executive communication.
- **MIT-licensed open source** — no existing open-source tool covers XER parsing + DCMA-14 + comparison. This is a clear gap.

### 3. Academic Value — What Is Publishable

The tool doubles as research infrastructure. Features were prioritized that support publishable research:

- **DCMA 14-Point automated scoring** — well-documented methodology with clear benchmarks for validation studies.
- **Critical Path Method (CPM) engine** — foundational algorithm that supports multiple research directions (forensic delay analysis, window analysis, float analysis).
- **Comparison engine** — enables longitudinal studies of schedule evolution across project lifecycles.
- **Validation Score algorithm** — opportunity to publish a novel scoring methodology that improves upon existing heuristic approaches.

---

## v0.1 Scope — "Parse, Validate, Compare, Visualize"

### IN SCOPE (v0.1)

#### From Epic 1: XER Ingestion & Validation

| Feature | Description | Source Reference |
|---------|-------------|-----------------|
| **Custom MIT-licensed XER parser** | Parse all Oracle P6 XER tables per Oracle documentation. NOT xerparser (GPL) or PyP6Xer. Custom implementation to avoid license contamination. | xer-format-reference.md |
| **Full table parsing** | Support all XER tables: CALENDAR, PROJECT, PROJWBS, TASK, TASKPRED, TASKRSRC, RSRC, RSRCRATE, ACTVTYPE, ACTVCODE, PCATTYPE, PCATVAL, UDFTYPE, UDFVALUE, FINDATES, TASKFIN, TRSRCFIN | Oracle P6 XER Data Map |
| **DCMA 14-Point Assessment** | Automated scoring of all 14 checks: Logic, Leads, Lags, Relationship Types, Hard Constraints, High Float, Negative Float, High Duration, Invalid Dates, Resources, Missed Tasks, Critical Path Test, Critical Path Length Index (CPLI), Baseline Execution Index (BEI) | DCMA standard |
| **Schedule Counts Dashboard** | Activities (by type: Task, Milestone, LOE, WBS Summary; by status: Not Started, In Progress, Completed), Relationships (by type: FS, FF, SS, SF), Calendars, Resources, Resource Assignments | US-1.5 |
| **Open-end detection** | Activities missing predecessors, missing successors, open starts, open finishes | US-1.2 |
| **Out-of-sequence (OOS) detection** | Activities that started or progressed before their predecessors completed | US-1.3 |
| **Constraint analysis** | Hard constraints (Must Start On, Must Finish On), soft constraints, constraint count and percentage | US-1.6 |
| **Schedule Validation Score** | Composite score (0-100) with traffic-light indicators per metric, modeled after Schedule Validator's scoring standard | US-1.1 |
| **Quality Metrics Dashboard** | Traffic-light indicators for all quality checks: Date Constraints, Critical Path, Near-Critical Path, OOS, Negative Lags, FS Lags, Long Lags, High Float, High Duration, Invalid Dates, Duplicate Descriptions | US-1.6 |
| **Activity Relationships Quality** | Average Logic Ties, No Successors, No Predecessors, Open Finish, Open Start, Duplicates Present, Riding Data Date, Network Hotspots | US-1.7 |

#### From Epic 4: Schedule Comparison

| Feature | Description | Source Reference |
|---------|-------------|-----------------|
| **Two-XER upload** | Upload two XER files (baseline vs update, or update N vs update N+1) for period-to-period comparison | US-4.x |
| **Activities added/modified/deleted** | Detect activities that were added, modified (any field change), or deleted between two schedules | Schedule Comparison doc |
| **Relationships added/modified/deleted** | Detect predecessor relationships that were added, changed (type or lag), or removed | Schedule Comparison doc |
| **Duration changes** | Flag activities with original duration changes, remaining duration changes, and percentage change | Schedule Comparison doc |
| **Date changes** | Track start date changes, finish date changes, and baseline date modifications | Schedule Comparison doc |
| **Changed Percentage score** | Single metric (0-100%) quantifying overall schedule change magnitude between two versions | Schedule Comparison doc |
| **Suspicious change flags** | Flag schedule manipulation indicators: retroactive logic changes, unreasonable duration compression, float suppression patterns, constraint additions near data date | Epic 11 indicators |

#### From Epic 2: Baseline Review (Partial)

| Feature | Description | Source Reference |
|---------|-------------|-----------------|
| **Longest Critical Path identification** | Automatically identify and display the longest path through the network, listing every activity in sequence with durations and key dates | US-2.1 |
| **Total Float Distribution chart** | Categorize all activities by float range: Critical (0 days), Near-Critical (1-10 days), Moderate (11-20 days), Semi-Moderate (21-44 days), Not Critical (>44 days). Show percentages and contract compliance. | US-2.2 |
| **Milestone variance tracking table** | Compare milestone dates across baseline versions and calculate variance in calendar days | US-2.4 |

#### From Epic 10: Reporting (Partial)

| Feature | Description | Source Reference |
|---------|-------------|-----------------|
| **PDF export of validation report** | Generate professional PDF report containing all validation results, DCMA-14 scores, quality metrics, and recommendations | US-10.x |
| **Interactive web dashboard** | Browser-based dashboard with charts, tables, and drill-down capability for all validation and comparison results | US-10.x |

---

### OUT OF SCOPE (v0.1)

| Feature Area | Deferred To | Reason |
|-------------|-------------|--------|
| CPA / Window Analysis (Contemporaneous Period Analysis) | v0.2 | Requires mature CPM engine and multiple-baseline support |
| Time Impact Analysis (TIA) Support | v0.3 | Requires CPA foundation and claims expertise |
| EVM / WBS-CBS-BOQ cost integration | v0.4 | Requires resource-loaded schedules and cost mapping |
| Monte Carlo / QSRA (Quantitative Schedule Risk Analysis) | v0.5 | Requires statistical engine and risk register integration |
| Multi-tenant / portfolio management | v1.0 | Requires authentication, authorization, and database scaling |
| AI/ML schedule intelligence (anomaly detection, NLP) | v2.0 | Requires training data and model development |
| Earned Value metrics (SPI, CPI, BEI, SRI) | v0.3+ | Requires resource-loaded schedules with cost data |
| S-Curve generation | v0.3+ | Requires resource/cost loading |
| PERT probability analysis | v0.2 | Requires Monte Carlo or analytical distribution support |
| Multi-project support (inter-project links) | v1.0 | Requires portfolio-level data model |

---

## Release Roadmap

| Version | Codename | Epics | Key Deliverables | Target |
|---------|----------|-------|------------------|--------|
| **v0.1** | Foundation | 1 + 4 + 2 (partial) + 10 (partial) | XER Parser, DCMA-14, Comparison, Dashboard, PDF Export | Prototype |
| **v0.2** | Forensics | 5 + 3 + 11 | Window Analysis (CPA), Monthly Update Review, Manipulation Detection Engine | Academic paper #1 |
| **v0.3** | Claims | 6 + 7 + 9 | Time Impact Analysis (TIA), Delay Quantification, Claims Package Generation | Industry validation |
| **v0.4** | Controls | 13 + 8 | EVM Integration, WBS-CBS-BOQ Mapping, Cost-Schedule Integration | Cost integration |
| **v0.5** | Risk | 15 + 12 | Monte Carlo Simulation, QSRA, Risk Register, Probabilistic Scheduling | Risk paper |
| **v1.0** | Enterprise | 14 + 16 + Multi-tenant | User Management, Portfolio Dashboard, API Keys, SaaS Infrastructure | Platform launch |
| **v2.0** | Intelligence | AI/ML + NLP | Anomaly Detection, Natural Language Schedule Narratives, Predictive Analytics | PhD thesis |

### Version Dependencies

```
v0.1 Foundation ──► v0.2 Forensics ──► v0.3 Claims
                         │                    │
                         ▼                    ▼
                    v0.4 Controls ──► v0.5 Risk
                                          │
                                          ▼
                                     v1.0 Enterprise ──► v2.0 Intelligence
```

---

## Success Criteria for v0.1

### Performance Criteria

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| XER parse time (500-activity schedule) | < 5 seconds | Wall-clock time from file upload to parsed data model |
| XER parse time (5,000-activity schedule) | < 30 seconds | Wall-clock time from file upload to parsed data model |
| DCMA-14 report generation | < 10 seconds after parsing | Wall-clock time for full 14-point assessment |
| Comparison report (two 500-activity schedules) | < 15 seconds | Wall-clock time from upload of second file to comparison results |
| PDF export generation | < 20 seconds | Wall-clock time from report request to downloadable PDF |
| Dashboard initial load | < 3 seconds | Time to interactive (TTI) in browser |

### Accuracy Criteria

| Metric | Target | Validation Method |
|--------|--------|------------------|
| DCMA-14 scoring accuracy | Within 5% of Schedule Validator output | Side-by-side comparison using 10 reference XER files |
| Activity count accuracy | 100% match with P6 Professional | Compare parsed counts against P6 native view |
| Relationship count accuracy | 100% match with P6 Professional | Compare parsed counts against P6 native view |
| Critical path identification | Match P6 longest path output | Compare identified CP activities with P6 critical filter |
| Float calculation accuracy | Within 1 hour of P6 calculated values | Compare total float values for all activities |
| Comparison detection completeness | Detect all change categories from reference Schedule Comparison document | Verify against known change set using reference XER pair |

### Functional Criteria

| Criterion | Target |
|-----------|--------|
| Parse all 17+ standard XER tables | All tables listed in xer-format-reference.md parsed without error |
| Handle multi-project XER files | Correctly separate and label activities from multiple projects in a single XER |
| Handle XER files from P6 versions 15.1 through 24.12 | Tested against exported files from at least 3 different P6 versions |
| Graceful error handling | Invalid/corrupt XER files produce clear error messages, not crashes |
| Browser compatibility | Chrome 120+, Firefox 120+, Safari 17+, Edge 120+ |

### Quality Criteria

| Criterion | Target |
|-----------|--------|
| Unit test coverage | > 80% for parser and analytics modules |
| Integration test coverage | All API endpoints tested with reference XER files |
| Zero critical/high security vulnerabilities | Verified by dependency audit (pip audit, npm audit) |
| MIT license compliance | All dependencies MIT, BSD, Apache 2.0, or similarly permissive |

---

## User Flows for v0.1

### Flow 1: Single XER Upload, Validation, Report

**Actor:** Construction Scheduler or Project Controls Specialist

**Trigger:** Receives an XER file from the contractor (baseline submission or monthly update).

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌─────────────────┐
│  Upload XER  │────►│  Parse &     │────►│  Validation    │────►│  Interactive     │
│  File        │     │  Validate    │     │  Dashboard     │     │  Dashboard       │
└─────────────┘     └──────────────┘     └────────────────┘     └────────┬────────┘
                                                                          │
                    ┌──────────────┐     ┌────────────────┐               │
                    │  Download    │◄────│  Generate PDF  │◄──────────────┘
                    │  PDF Report  │     │  Report        │
                    └──────────────┘     └────────────────┘
```

**Step-by-step:**

1. **Upload:** User navigates to the dashboard home page and clicks "Upload XER". Selects a `.xer` file from their local filesystem. Maximum file size: 50 MB.
2. **Parse:** System reads the XER file, identifies all tables, and constructs the internal data model. Progress indicator shows parsing status. If the file is invalid or corrupt, a clear error message is displayed with the specific issue (e.g., "Missing ERMHDR line", "No TASK table found", "Invalid date format on line 1247").
3. **Validate:** System runs all DCMA 14-Point checks automatically. Calculates Schedule Validation Score (0-100). Generates quality metrics with traffic-light indicators.
4. **Dashboard:** User sees the interactive validation dashboard with:
   - **Header:** Project name, data date, schedule dates, validation score badge (color-coded)
   - **Schedule Counts panel:** Activities by type and status, relationships by type, calendars
   - **DCMA 14-Point panel:** Each check with score, threshold, and RED/YELLOW/GREEN indicator
   - **Quality Metrics panel:** Full list of quality checks with counts, percentages, and traffic lights
   - **Activity Relationships panel:** Open ends, OOS, riding data date, network hotspots
   - **Critical Path panel:** List of activities on the longest path with ID, name, duration, dates, float
   - **Float Distribution chart:** Bar chart showing activity count by float category
5. **Drill-down:** User clicks on any metric to see the list of specific activities contributing to that score. For example, clicking "No Successors: 3 (1%) RED" shows the 3 activities without successors.
6. **Export:** User clicks "Export PDF". System generates a professional PDF report matching the Schedule Diagnostic format. PDF is downloaded to the user's browser.

**Expected duration:** Upload to dashboard visible in < 15 seconds for a 500-activity schedule.

---

### Flow 2: Two XER Upload, Comparison, Change Report

**Actor:** Construction Scheduler performing monthly schedule review

**Trigger:** Receives a new schedule update and needs to compare against the previous version.

```
┌──────────────┐     ┌──────────────┐     ┌────────────────┐     ┌─────────────────┐
│  Upload XER  │────►│  Upload XER  │────►│  Compare       │────►│  Comparison      │
│  (Previous)  │     │  (Current)   │     │  Engine        │     │  Dashboard       │
└──────────────┘     └──────────────┘     └────────────────┘     └────────┬────────┘
                                                                          │
                    ┌──────────────┐     ┌────────────────┐               │
                    │  Download    │◄────│  Generate PDF  │◄──────────────┘
                    │  Change Rpt  │     │  Change Report │
                    └──────────────┘     └────────────────┘
```

**Step-by-step:**

1. **Upload Previous:** User uploads the previous schedule version (e.g., May 2024 update). System parses and stores in memory.
2. **Upload Current:** User uploads the current schedule version (e.g., June 2024 update). System parses and stores in memory.
3. **Compare:** System runs the comparison engine:
   - Matches activities across schedules by `task_id` (primary) and `task_code` (fallback)
   - Categorizes every activity as: **Unchanged**, **Modified**, **Added**, or **Deleted**
   - For modified activities: identifies which fields changed (dates, durations, logic, status, etc.)
   - Matches relationships by `task_id` + `pred_task_id` composite key
   - Categorizes relationships as: **Unchanged**, **Modified** (type or lag change), **Added**, or **Deleted**
   - Calculates **Changed Percentage** (0-100%) summarizing overall schedule change magnitude
   - Runs **manipulation detection** checks for suspicious patterns
4. **Dashboard:** User sees the comparison dashboard with:
   - **Summary panel:** Changed Percentage score, counts of added/modified/deleted activities and relationships
   - **Activities Changes table:** Sortable, filterable table of all changed activities with change type, old values, new values, and change magnitude
   - **Relationships Changes table:** All logic changes with predecessor, successor, old type/lag, new type/lag
   - **Duration Changes panel:** Activities with duration increases/decreases, percentage change
   - **Date Changes panel:** Activities with start/finish date shifts, days of change
   - **Suspicious Changes panel:** Flagged items with explanation (e.g., "Activity A1050: duration reduced from 45d to 10d without progress — possible schedule compression")
   - **Float Impact panel:** Activities whose total float changed significantly between versions
5. **Export:** User clicks "Export Change Report". PDF generated with all comparison data.

**Expected duration:** Both uploads + comparison + dashboard in < 30 seconds for two 500-activity schedules.

---

### Flow 3: Baseline Analysis, Critical Path, Float Distribution

**Actor:** Project Manager or Construction Manager reviewing a baseline submission

**Trigger:** Contractor submits a new baseline schedule for approval.

```
┌──────────────┐     ┌──────────────┐     ┌────────────────┐     ┌─────────────────┐
│  Upload      │────►│  Parse &     │────►│  CPM Engine    │────►│  Baseline        │
│  Baseline    │     │  Validate    │     │  Analysis      │     │  Review          │
│  XER         │     │              │     │                │     │  Dashboard       │
└──────────────┘     └──────────────┘     └────────────────┘     └────────┬────────┘
                                                                          │
         ┌──────────────────────────────────────┬─────────────────────────┘
         ▼                                      ▼
┌─────────────────┐                    ┌─────────────────┐
│  Critical Path  │                    │  Float           │
│  Viewer         │                    │  Distribution    │
└─────────────────┘                    └─────────────────┘
```

**Step-by-step:**

1. **Upload Baseline:** User uploads the baseline XER file. System parses all tables.
2. **Validate:** System runs DCMA 14-Point Assessment. Validation score and quality metrics are displayed (same as Flow 1).
3. **CPM Analysis:** System runs the Critical Path Method engine using NetworkX:
   - Builds the activity network graph from TASK and TASKPRED tables
   - Performs forward pass (ES, EF) and backward pass (LS, LF) calculations
   - Calculates Total Float and Free Float for every activity
   - Identifies the Longest Critical Path (sequence of activities with zero total float)
   - Identifies Near-Critical paths (activities with float < threshold, default 10 days)
4. **Critical Path Viewer:** User sees the longest critical path displayed as:
   - **Narrative format:** Sequential list of activities with durations and dates (matching BL03 Memo format: "NTP -> Mobilization/Site Prep -> Foundation -> ... -> Final Completion")
   - **Table format:** Activity ID, Activity Name, Duration, Early Start, Early Finish, Total Float, Free Float
   - **Path statistics:** Total path duration, number of activities, average activity duration
5. **Float Distribution:** User sees float distribution as:
   - **Bar chart:** Number of activities per float category (Critical, Near-Critical, Moderate, Semi-Moderate, Not Critical)
   - **Percentage breakdown:** Percentage of activities in each category
   - **Contract compliance check:** If contract specifies maximum critical+near-critical percentage (e.g., <= 25%), display PASS/FAIL
6. **Milestone Tracking:** User sees milestones extracted from the schedule with:
   - Activity ID, Milestone Name, Baseline Date
   - If multiple baselines exist in the XER, show variance across baseline versions
7. **Export:** All analysis results exportable as PDF.

**Expected duration:** Upload to full baseline review dashboard in < 20 seconds for a 500-activity schedule.

---

## Appendix: Feature Traceability Matrix

| Feature | Epic | User Story | Source Document |
|---------|------|-----------|-----------------|
| Custom XER Parser | Epic 1 | US-1.8 | xer-format-reference.md, Oracle P6 Data Map |
| DCMA 14-Point | Epic 1 | US-1.1 | DCMA 14-Point Assessment standard |
| Schedule Counts | Epic 1 | US-1.5 | Schedule Diagnostic |
| Open-End Detection | Epic 1 | US-1.2 | Schedule Diagnostic, June 2024 Review |
| OOS Detection | Epic 1 | US-1.3 | Schedule Diagnostic, June 2024 Review |
| Constraint Analysis | Epic 1 | US-1.6 | Schedule Diagnostic |
| Validation Score | Epic 1 | US-1.1 | Schedule Diagnostic |
| Quality Metrics | Epic 1 | US-1.6, US-1.7 | Schedule Diagnostic |
| Period Comparison | Epic 4 | US-4.x | Schedule Comparison doc |
| Changed Percentage | Epic 4 | US-4.x | Schedule Comparison doc |
| Manipulation Flags | Epic 11 | US-11.x | Expert Consultation Results |
| Critical Path | Epic 2 | US-2.1 | BL03 Baseline Review Memo |
| Float Distribution | Epic 2 | US-2.2 | BL03 Baseline Review Memo |
| Milestone Tracking | Epic 2 | US-2.4 | BL03 Baseline Review Memo |
| PDF Export | Epic 10 | US-10.x | All reference documents |
| Web Dashboard | Epic 10 | US-10.x | All reference documents |
