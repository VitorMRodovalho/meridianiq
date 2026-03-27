# Discovery Review for v0.6+ Planning

> Compiled: 2026-03-27
> Source: 12 discovery/definition documents, ~273K words of analysis
> Current state: v0.5.0 released, 222 tests passing, rebranded as MeridianIQ

---

## 1. Decisions Already Made

Concrete decisions extracted from discovery and definition documents:

1. **License: MIT** — Fully open-source, no freemium, no paywalled features. The entire platform is free. (VISION_EVOLUTION.md, Section 8)
2. **Architecture: Hybrid Python + TypeScript** — Python backend (FastAPI) + SvelteKit frontend, chosen over full Python (HTMX), full TypeScript (NestJS+Next.js), and Rust options. (TECHNOLOGY_ASSESSMENT.md, Option C)
3. **Frontend framework: SvelteKit** — Selected over Next.js for 50%+ smaller bundles, 41% higher RPS, and Svelte 5 runes reactivity model. (TECHNOLOGY_ASSESSMENT.md)
4. **Backend framework: FastAPI** — Selected as de facto Python API standard (~94,800 GitHub stars), with Pydantic v2 for data validation. (TECHNOLOGY_ASSESSMENT.md)
5. **Custom XER parser: MIT-licensed** — Cannot use xerparser (GPL-3.0, viral license) or PyP6Xer (uncertain license). Custom parser built from Oracle specs. (GAP_ASSESSMENT.md, TECHNOLOGY_ASSESSMENT.md)
6. **CPM engine: NetworkX** — BSD-3-Clause licensed. Custom ES/EF/LS/LF implementation layered on top. (TECHNOLOGY_ASSESSMENT.md)
7. **Database strategy: SQLite (prototype) to PostgreSQL (production)** — SQLAlchemy ORM from v0.1 ensures migration is a config change. Current v0.x uses in-memory store. (ARCHITECTURE_DRAFT.md, architecture.md)
8. **Charts: Plotly + D3.js** — Plotly for standard charts, D3.js for custom Gantt visualization (no off-the-shelf lib handles P6 scheduling semantics). (TECHNOLOGY_ASSESSMENT.md)
9. **Deployment: Docker Compose** — Backend container + Frontend container + DB volume. (TECHNOLOGY_ASSESSMENT.md)
10. **No commercial intent** — Platform designed as academic/community contribution, with PhD thesis as primary output. (VISION_EVOLUTION.md, Section 8)
11. **Academic rigor required** — Every methodology must be traceable to published standards, peer-reviewed papers, or recognized RPs. No black-box logic. (VISION_EVOLUTION.md, Section 1)
12. **AI attribution model** — Claude acknowledged as development tool, never listed as co-author. Human retains full intellectual responsibility. (CLAUDE_ATTRIBUTION.md)
13. **DCMA 14-Point Assessment** — Implemented as core validation with all 14 checks and standard thresholds. (PRODUCT_BACKLOG.md, MVP_DEFINITION.md)
14. **Schedule comparison matching strategy** — Tier 1: match by task_id, Tier 2: fallback to task_code. (architecture.md)
15. **Modular monolith pattern** — Single FastAPI application with separated analysis engines, no cross-dependencies between engines. (architecture.md)
16. **Open-core model preferred for adoption** — Community edition (all analytics) + Enterprise edition (SSO, RBAC, audit trail, SLA) based on expert consultation synthesis. (EXPERT_CONSULTATION_RESULTS.md, Q15)
17. **Data center construction as first market** — Sector-specific focus as proving ground before generalizing. (EXPERT_CONSULTATION_RESULTS.md, Q19)
18. **Rebrand to MeridianIQ** — Completed in v0.5 cycle. (git log)
19. **Forensic methodology: AACE RP 29R-03** — Windows Analysis (MIP 3.6) and Time Impact Analysis (MIP 3.9) as primary methods. (PRODUCT_BACKLOG.md, Epic 5)
20. **CSS framework: Tailwind CSS 4.x** — Utility-first styling with dark mode support. (TECHNOLOGY_ASSESSMENT.md)
21. **Table library: TanStack Table 8.x** — Headless, virtual scrolling for 500+ row activity tables. (TECHNOLOGY_ASSESSMENT.md)
22. **PDF generation: ReportLab or WeasyPrint** — Both BSD-licensed options evaluated. (TECHNOLOGY_ASSESSMENT.md)
23. **Manipulation detection as P0** — Elevated from general backlog to P0 priority based on expert consultation (all personas confirmed schedule manipulation is widespread). (DISCOVERY_STATUS.md)
24. **Seven scheduling hierarchy levels recognized** — From Program Level down to Work Package. (VISION_EVOLUTION.md, Section 2)

---

## 2. Open Questions

Issues discussed but never resolved with a final decision:

1. **Open-core vs. pure open-source licensing** — VISION_EVOLUTION.md says "fully open-source, no freemium, no paywalled features." But EXPERT_CONSULTATION_RESULTS.md Q15 synthesis recommends the open-core model (free community + commercial enterprise). **These contradict.** Which model is final?

2. **PDF generation library** — ReportLab vs. WeasyPrint evaluated but no final selection made. (TECHNOLOGY_ASSESSMENT.md)

3. **Rust migration for performance-critical components** — Identified as a v1.0+ consideration for Monte Carlo and large-schedule CPM. No threshold defined for when Python becomes insufficient. (TECHNOLOGY_ASSESSMENT.md, Option D)

4. **QSRA validation** — Risk Manager persona questioned whether Monte Carlo results are actually predictive. The platform now has QSRA (v0.5) but no plan to validate predictions against outcomes. (EXPERT_CONSULTATION_RESULTS.md, Q16)

5. **DCMA threshold validation** — CM Professor and Owner Rep both asked whether DCMA 5% thresholds are statistically justified. No plan to address this. (EXPERT_CONSULTATION_RESULTS.md, Q17)

6. **Optimal WBS depth by project type** — Identified as research gap, no decision on platform support. (EXPERT_CONSULTATION_RESULTS.md, Q3)

7. **GraphQL vs. REST** — Platform Architect suggested GraphQL or graph database for WBS-CBS-risk relationships. Current decision is REST. No formal trade-off documented. (EXPERT_CONSULTATION_RESULTS.md, Q1)

8. **Federated learning for privacy** — AI/ML Researcher proposed federated learning for cross-org model training without centralizing data. No decision on feasibility or priority. (EXPERT_CONSULTATION_RESULTS.md, Q14)

9. **Value milestone entity** — Expert consultation recommends a "value milestone" or "value event" entity with business metadata. Not yet in the data model. (EXPERT_CONSULTATION_RESULTS.md, Q2)

10. **Multi-format support (MSP, Asta, Phoenix)** — GAP_ASSESSMENT.md recommends MPXJ for format expansion, but MPXJ is Java (LGPL) requiring interop from Python. No decision on whether/when to support non-XER formats.

11. **Data anonymization and opt-in sharing** — Expert consultation recommends designing data anonymization from the start for benchmark collection. No technical design exists. (EXPERT_CONSULTATION_RESULTS.md, Q17)

12. **Secure Forensic Workspace** — Expert consultation recommends isolated, access-controlled, audit-trailed workspace for litigation. No design exists. (EXPERT_CONSULTATION_RESULTS.md, Q14)

13. **Recovery schedule validation** — Contract requires recovery schedules within 20 days. No design for evaluating recovery schedule quality. (PRODUCT_BACKLOG.md, US-7.3)

14. **Float trend metrics definition** — CM Professor proposed "float velocity" and "float entropy" as novel metrics. No formal definition or implementation plan. (EXPERT_CONSULTATION_RESULTS.md, Q13)

---

## 3. Gaps Found

Topics NOT covered in any discovery or definition document:

| Gap | Severity | Notes |
|-----|----------|-------|
| **CI/CD pipeline** | High | No GitHub Actions, no automated testing on PR, no deployment automation documented anywhere |
| **Testing strategy beyond unit tests** | High | 222 tests exist, MVP_DEFINITION.md mentions >80% coverage target, but no integration test strategy, no E2E test plan, no performance test plan |
| **Monitoring/observability** | High | No mention of logging framework, metrics collection, APM, health checks, or error tracking in any document |
| **Error handling strategy** | Medium | ARCHITECTURE_DRAFT.md shows error responses per endpoint but no global error handling pattern, no retry strategy, no circuit breaker pattern |
| **Logging** | Medium | No structured logging plan, no log levels defined, no log aggregation |
| **API versioning** | Medium | architecture.md shows `/api/v1/` prefix but no strategy for breaking changes, deprecation, or version coexistence |
| **Migration path: in-memory to DB** | High | architecture.md says `v0.x: In-Memory (dict) -> v1.0: SQLite -> v1.x: PostgreSQL` but no migration script plan, no data migration tooling |
| **User authentication** | Medium | Deferred to v1.0 per MVP_DEFINITION.md. No auth design exists. No evaluation of auth providers (Auth0, Clerk, Supabase Auth, etc.) |
| **File storage** | Medium | architecture.md mentions "File Storage" for uploaded XER files and generated PDFs, but no strategy (local filesystem vs. S3 vs. MinIO) |
| **Rate limiting** | Low | No mention. Relevant for future SaaS/multi-tenant |
| **Internationalization (i18n)** | Low | No mention. All docs assume English. Platform targets global construction industry. |
| **Accessibility (a11y)** | Low | No mention. Web dashboard has no accessibility requirements defined. |
| **Data backup and recovery** | Medium | No strategy for protecting uploaded XER files and analysis results |
| **Performance benchmarks for larger schedules** | Medium | MVP targets 500-activity schedules. Real data center schedules can be 8,000+ activities. No load testing plan. |
| **Offline/PWA capability** | Low | Construction Manager persona requested offline capability for field use. Not addressed. |
| **PMXML support** | Low | Mentioned as "redundancy" format but no design or timeline |
| **Contribution guidelines** | Medium | VISION_EVOLUTION.md mentions "clear contribution guidelines" but none exist |
| **Browser testing matrix** | Low | MVP_DEFINITION.md lists Chrome 120+/Firefox 120+/Safari 17+/Edge 120+ but no test plan |
| **State management between page loads** | Low | No discussion of session persistence — currently in-memory means data lost on server restart |

---

## 4. Personas Defined

14 personas defined in PERSONAS_AND_CONSULTATION.md with expert consultation responses in EXPERT_CONSULTATION_RESULTS.md:

| # | Name | Role | Primary Needs | Relevant Epics |
|---|------|------|---------------|----------------|
| 1 | PSP-Certified Scheduler | Daily P6 practitioner, builds/maintains/updates schedules | Accuracy, AACE compliance, automated DCMA checks, float analysis, logic quality | E1, E2, E3, E4, E5, E6, E8 |
| 2 | Forensic Schedule Analyst | AACE RP 29R-03 specialist, delay claims and disputes | Defensible CPA/TIA, transparent methodology, audit trail, schedule manipulation detection | E5, E6, E7, E11 |
| 3 | Program Scheduler (IPS) | Maintains IPS across multiple contractors and disciplines | Multi-schedule integration, IPS reconciliation, cross-contract critical path, batch XER processing | E1, E4, E14 |
| 4 | Project Manager (PMP) | Decision-maker for overall project delivery | Executive dashboards, milestone tracking, proactive alerts, performance scores, recovery potential | E3, E7, E8, E10 |
| 5 | Construction Manager (CCM) | Bridges schedule and field execution | Field-verified progress, 3-week look-ahead, area readiness, mobile/tablet access | E2, E3, E5, E7 |
| 6 | Cost Manager / Cost Engineer | EVM, WBS-CBS integration, financial progress | WBS-CBS alignment, SPI/CPI/EAC, cost-of-delay calculation, resource-loaded S-curves | E3, E13 |
| 7 | Risk Manager | Monte Carlo/QSRA, risk registers | P50/P80 dates, tornado diagrams, risk velocity, QSRA calibration from historical data | E15 |
| 8 | Owner Representative | Client-side oversight, contractor performance | Schedule submission compliance, DCMA pass/fail enforcement, benchmarking, entitlement tracking | E1, E7, E8 |
| 9 | Program Director | Portfolio-level decisions across capital program ($100M+) | Portfolio heatmap, cross-project dependencies, resource conflicts, value delivery progress | E8, E14, E16 |
| 10 | CM Professor (PhD Advisor) | Academic research, doctoral supervision | Research data infrastructure, reproducible analysis, Python API, benchmark datasets, publishable novelty | E-all (research) |
| 11 | AACE Board Member | Standards author, RP development | AACE RP compliance, transparent methodology, extensible quality rules, standards-based validation | E1, E5, E6 |
| 12 | PMI Practice Standard Author | PMBOK contributor | PMBOK 8 domain alignment, value delivery framing, principle-based metrics | E3, E10 |
| 13 | Open-Source Platform Architect | Scalable architecture, open-source governance | API-first, modular architecture, plugin extensibility, multi-tenant data model, Docker deployment | E-all (platform) |
| 14 | AI/ML for Construction Researcher | ML models for schedule prediction | Python API, Jupyter integration, training data pipeline, XER features as ML datasets, explainable AI | E-all (AI/ML) |

**Additional backlog personas from PRODUCT_BACKLOG.md:**

| Persona | Role | Primary Epics | Key Needs |
|---------|------|---------------|-----------|
| GC Scheduler | Prepares compliant TIA submissions | E1, E2, E6 | Validation before submission, methodology guidance |

---

## 5. User Stories by Priority

Based on the PRODUCT_BACKLOG.md priority matrix, MVP_DEFINITION.md roadmap, expert consultation synthesis, and current release state (v0.5.0 shipped with QSRA):

### v0.6 — Natural Next Step After v0.5

The roadmap shows v0.5 = Risk (Monte Carlo/QSRA). The gap between v0.5 and v1.0 (Enterprise) is large. v0.6 should consolidate existing engines and add the capabilities identified as P0 by expert consultation.

| Story | Source | Rationale |
|-------|--------|-----------|
| **Historical XER Archive & Versioning** — Store every uploaded XER with timestamp, enable chronological retrieval | Epic 12 (new from consultation) | Foundation for trend analysis, forensic workbench, and benchmark collection. Currently in-memory = lost on restart. |
| **Schedule Review Pipeline** — Automated: upload XER -> validation -> comparison to prior -> anomaly flags -> review report | EXPERT_CONSULTATION_RESULTS.md Q6 synthesis (P0) | "Killer feature" per all personas. Automates the monthly 4-8 hour review. |
| **Float Trend Analysis** — Float by path over time, float velocity, projected zero-float date, deterioration alerts | EXPERT_CONSULTATION_RESULTS.md Q13 (P1) | Universal demand. Transforms reactive to proactive management. |
| **Early Warning System** — Float erosion rate, BEI trend, critical path stability, completion date drift, configurable thresholds | EXPERT_CONSULTATION_RESULTS.md Q11 | All personas trust float erosion + BEI as leading indicators. |
| **Schedule Manipulation Detection Engine enhancements** — Classify changes by risk level (normal/needs-justification/red-flag), retroactive date detection, logic change patterns | Epic 11 (P0 from consultation) | Comparison engine exists. Needs classification layer and historical tracking. |
| **Persistent storage (SQLite)** — Migrate from in-memory dict to SQLite for session persistence | ARCHITECTURE_DRAFT.md, architecture.md | Required for XER archive, trend analysis, and any multi-session use. |
| **PDF export for all analysis types** — Validation report, comparison report, CPA waterfall, TIA summary, EVM dashboard, QSRA results | Epic 10 (ongoing) | Schedulers need PDF attachment capability for all report types. |

### v0.7-v0.9 — Medium Term

| Version | Stories | Source |
|---------|---------|--------|
| **v0.7** | WBS Analysis Module — hierarchy visualization, quality metrics (depth/breadth/distribution), WBS-to-WBS comparison between schedules | EXPERT_CONSULTATION_RESULTS.md Q3, Epic 13 |
| **v0.7** | Value Delivery Dashboard — tag milestones with business metadata (revenue, contractual significance), alternative view alongside technical analytics | EXPERT_CONSULTATION_RESULTS.md Q2 |
| **v0.7** | Configurable Dashboard — Library of 20+ metrics, user-customizable views, default "consensus five" (BEI, completion variance, CP, float distribution, DCMA) | EXPERT_CONSULTATION_RESULTS.md Q12 |
| **v0.8** | Contract Compliance Monitoring — NOD tracking, PCO submission tracking, recovery schedule tracking, entitlement status dashboard | Epic 7 (P3) |
| **v0.8** | Submittal/RFI Timeline Integration — Import logs, cycle time tracking, combined timeline view with schedule | Epic 9 (P4) |
| **v0.8** | Professional Memo Generation — Auto-populated templates in CM firm format | US-2.7 |
| **v0.9** | IPS-Contractor Schedule Reconciliation — Multi-XER milestone mapping, vertical consistency checking, cross-schedule critical path | Epic 14 (new from consultation) |
| **v0.9** | Data Center Program Template — Long-lead equipment tracking, commissioning scheduling, campus hierarchy, template libraries | Epic 16 (new from consultation) |
| **v0.9** | Benchmarking — Anonymized schedule metric collection, benchmark reports by project type | EXPERT_CONSULTATION_RESULTS.md Q17 |

### v1.0 — Enterprise/Multi-Tenant

| Story | Source |
|-------|--------|
| User management, authentication (SSO), role-based access control | VISION_EVOLUTION.md Section 7, EXPERT_CONSULTATION_RESULTS.md Q14 |
| Multi-tenant data isolation — firm > client > campus > project hierarchy | VISION_EVOLUTION.md Section 7 |
| PostgreSQL migration with full data migration tooling | ARCHITECTURE_DRAFT.md |
| Portfolio dashboard — cross-project heatmap, inter-project dependencies, resource conflicts | VISION_EVOLUTION.md Section 7 |
| API keys for external integration | MVP_DEFINITION.md roadmap |
| Secure Forensic Workspace — isolated, access-controlled, audit-trailed | EXPERT_CONSULTATION_RESULTS.md Q14 |
| Cross-project benchmarking — compare schedule performance across similar projects | VISION_EVOLUTION.md Section 7 |
| SOC 2 compliance, encryption at rest/in transit | EXPERT_CONSULTATION_RESULTS.md Q14 |
| Self-hosted deployment option (Docker/Kubernetes) | EXPERT_CONSULTATION_RESULTS.md Q14 |

### v2.0 — AI/ML

| Story | Source |
|-------|--------|
| Anomaly detection — Isolation Forest/autoencoder for schedule manipulation | EXPERT_CONSULTATION_RESULTS.md Q9, Q18 |
| Delay risk scoring — Ensemble methods (Random Forest, XGBoost) for activity-level delay prediction | LITERATURE_REVIEW.md Section 4, EXPERT_CONSULTATION_RESULTS.md Q18 |
| NLP milestone mapping — Automated matching of activity descriptions across schedules | EXPERT_CONSULTATION_RESULTS.md Q4 |
| Completion date prediction — LSTM/Transformer time-series from historical schedule updates | LITERATURE_REVIEW.md Section 4 |
| Explainable AI — SHAP values for all ML predictions (requirement per forensic/legal use) | LITERATURE_REVIEW.md Section 4.4 |
| Natural language schedule narratives — LLM-generated executive summaries from analysis results | GAP_ASSESSMENT.md (XER Toolkit has this) |
| GNN network topology analysis — Graph neural networks for critical path fragility/resilience | EXPERT_CONSULTATION_RESULTS.md Q18 |
| Auto-calibration of QSRA distributions from historical data | EXPERT_CONSULTATION_RESULTS.md Q18 |

---

## 6. Technical Decisions

### Chosen

| Decision | What | Why | Source |
|----------|------|-----|--------|
| **Backend language** | Python 3.12+ | Ecosystem (NetworkX, Pandas, NumPy, SciPy), domain-standard for schedule analysis, 5-10% perf improvement in 3.12 | TECHNOLOGY_ASSESSMENT.md |
| **Backend framework** | FastAPI 0.128+ | 94.8K stars, auto OpenAPI docs, native async, Pydantic V2 (5-50x faster), 3,000+ RPS | TECHNOLOGY_ASSESSMENT.md |
| **Frontend framework** | SvelteKit 2.x (Svelte 5) | Compile-time, 50%+ smaller bundles vs Next.js, 41% higher RPS, runes reactivity | TECHNOLOGY_ASSESSMENT.md |
| **Graph algorithms** | NetworkX 3.6+ (BSD-3) | DiGraph, topological_sort, dag_longest_path. Custom CPM layered on top. | TECHNOLOGY_ASSESSMENT.md |
| **Data manipulation** | Pandas 2.2+ | DataFrames for XER tables, comparison engine diffs | TECHNOLOGY_ASSESSMENT.md |
| **Interactive charts** | Plotly 5.x (MIT) | Server-side JSON specs consumed by Plotly.js frontend | TECHNOLOGY_ASSESSMENT.md |
| **Custom Gantt/network** | D3.js 7.x (ISC) | No off-the-shelf Gantt handles LOE, hammocks, resource-dependent durations | TECHNOLOGY_ASSESSMENT.md |
| **Tables** | TanStack Table 8.x (MIT) | Virtual scrolling for 500+ rows, headless with Svelte adapter | TECHNOLOGY_ASSESSMENT.md |
| **CSS** | Tailwind CSS 4.x (MIT) | Utility-first, dark mode, responsive | TECHNOLOGY_ASSESSMENT.md |
| **ORM** | SQLAlchemy 2.x (MIT) | Async support, smooth SQLite-to-PostgreSQL migration | TECHNOLOGY_ASSESSMENT.md |
| **Testing** | pytest 8.x (MIT) | Unit + integration tests, 222 tests passing | TECHNOLOGY_ASSESSMENT.md |
| **Architecture pattern** | Modular monolith | Single FastAPI app, separated engines, no cross-engine dependencies | architecture.md |
| **XER parser** | Custom Python, MIT | xerparser GPL incompatible; PyP6Xer inadequate. Pydantic models, streaming, encoding detection. | TECHNOLOGY_ASSESSMENT.md |
| **Deployment** | Docker Compose | Backend + Frontend + DB containers | TECHNOLOGY_ASSESSMENT.md |

### Rejected

| Option | Why Rejected | Source |
|--------|-------------|--------|
| **Option A: Python Full-Stack (HTMX)** | Insufficient interactivity for data-heavy dashboards, D3/Plotly still need JS, no component model | TECHNOLOGY_ASSESSMENT.md |
| **Option B: TypeScript Full-Stack (NestJS + Next.js)** | Wrong language for core algorithms — CPM, DCMA-14, float analysis natural in Python. No Pandas/NumPy/SciPy equivalent. Double dev time. | TECHNOLOGY_ASSESSMENT.md |
| **Option D: Rust + TypeScript** | Overkill for v0.1-v0.5 (schedules typically 300-2,000 activities). Steep learning curve. Immature scientific computing ecosystem. Harder to attract contributors. | TECHNOLOGY_ASSESSMENT.md |
| **Next.js (instead of SvelteKit)** | Larger bundles (700kB vs 300kB benchmark), lower RPS (850 vs 1,200), more boilerplate. Acknowledged: larger component ecosystem. | TECHNOLOGY_ASSESSMENT.md |
| **xerparser (Python)** | GPL-3.0 viral license, incompatible with MIT project goals | GAP_ASSESSMENT.md, TECHNOLOGY_ASSESSMENT.md |
| **PyP6Xer** | Limited table support, uncertain license, inconsistent maintenance | TECHNOLOGY_ASSESSMENT.md |
| **MPXJ for primary parsing** | Java-centric, requires interop layer. Considered for future multi-format expansion. | GAP_ASSESSMENT.md |

---

## 7. IPS Reconciliation

### What the Docs Say

**Definition (VISION_EVOLUTION.md, Section 3):**
- The IPS (Integrated Project Schedule) is the owner's or construction manager's master schedule integrating all contractors, vendors, and internal activities into a single coherent model.
- Serves as the single source of truth for project-level schedule performance reporting.
- Maintained by the Program Scheduler or Planning Lead on the owner/CM side.

**The Tension (EXPERT_CONSULTATION_RESULTS.md, Q4):**
- IPS updated monthly; contractor detail evolves weekly = staleness.
- Contractor schedules have different WBS, calendars, and activity coding than the IPS.
- The IPS-contractor disconnect generates millions in disputed claims (Forensic Analyst).
- Program Scheduler: "This process takes my team of three people approximately 10 working days per month" for 12 contracts.
- Project Manager: "They tell different stories. I need a single source of truth, and I do not have one."

**What "Reconciliation" Means (EXPERT_CONSULTATION_RESULTS.md, Q4-Q5):**
1. **Milestone mapping** — Identify which contractor milestones correspond to IPS milestones (often named differently).
2. **Vertical consistency checking** — Verify that driving paths in the detail schedule support the IPS milestone dates.
3. **Cross-schedule critical path identification** — Determine which contract is currently driving the program completion.
4. **Float propagation** — Surface Level 3 float erosion warnings at Level 1-2 dashboards.
5. **Calendar reconciliation** — Verify contractor calendars are consistent with IPS assumptions.

**Technical Requirements (EXPERT_CONSULTATION_RESULTS.md, Q4 Platform Architect):**
- Parse two XER files (contractor detail + IPS) into graph representations.
- Perform path analysis across the boundary.
- NLP/entity-matching for automated milestone mapping (activity descriptions use different terminology).
- Computationally feasible for typical program sizes.

**Current State:**
- Epic 14 (IPS-Contractor Schedule Reconciliation) is defined in DISCOVERY_STATUS.md as a new epic from consultation.
- Placed on v1.0 roadmap in MVP_DEFINITION.md.
- No technical design exists.

**Research Context (LITERATURE_REVIEW.md, Gap 4):**
- "The tension between owner IPS and contractor detailed schedules is well-known in practice but poorly studied academically."
- "How to automatically verify that a Level 3 schedule is consistent with its Level 1/2 summary remains an unsolved problem."
- Analogous to "refinement" in formal methods (CM Professor).

---

## 8. Deployment/Hosting

### What Exists

**Current deployment (TECHNOLOGY_ASSESSMENT.md, architecture.md):**
- Docker Compose orchestrating:
  - Backend container: Python 3.12 + FastAPI + Uvicorn
  - Frontend container: Node.js + SvelteKit (or static build served by Nginx)
  - Database: SQLite volume mount (v0.1) or PostgreSQL container (v1.0+)
- `docker-compose up` for local development
- Production: Docker images pushed to container registry

**No cloud provider chosen.** No mentions of AWS, GCP, Azure, or any specific hosting platform in any document.

**No CI/CD pipeline defined.** This is a gap (see Section 3).

### What Expert Consultation Says

- **Web-first, strongly preferred** by majority of personas for accessibility, collaboration, scalability. (Q14)
- **Self-hosted deployment option required** for government/defense clients and security-sensitive organizations. (Q14)
- **SaaS model mentioned** as potential approach: GPL covers distributed software, not SaaS (GAP_ASSESSMENT.md "SaaS loophole" discussion — now moot since custom MIT parser was built).
- **SOC 2 Type II compliance** recommended for forensic/litigation use cases. (Q14)
- **Data residency options** (US, EU, on-premise) recommended. (Q14)
- **Monte Carlo requires server-side computation** — 10,000+ iterations on 5,000+ activity schedules. Cloud computing makes this feasible but latency must be acceptable. (Q14)

### Gap

No deployment strategy exists beyond Docker Compose. No cloud architecture, no Kubernetes manifests, no CDN strategy, no domain/DNS plan.

---

## 9. Auth/Multi-tenant

### What the Docs Say

**Multi-tenant architecture (VISION_EVOLUTION.md, Section 7):**

Target structure:
```
Firm-wide (portfolio health, cross-client benchmarking)
  └── Client (contract-level roll-up, SLA compliance)
       └── Campus / Site (cross-project dependencies, shared resources)
            └── Project (detailed schedule analysis, EV metrics)
```

Key capabilities defined:
- Roll-up aggregation from project to firm level
- Drill-down from any summary metric to activity level
- Cross-project benchmarking
- **Data isolation** — each client's data segregated with appropriate access controls

**Authentication/Authorization:**
- Deferred to v1.0 per MVP_DEFINITION.md roadmap
- Expert consultation recommends: SSO, role-based access control, enterprise authentication (Q14, Q15)
- Forensic Analyst requires: data residency control, access control, audit trail, chain of custody (Q14)
- Platform Architect recommends: SOC 2, encryption at rest/in transit, RBAC, full audit trail (Q14)
- Owner Rep needs: data processing agreements, information security compliance (Q14)

**Roles implied across personas:**
- Scheduler / Analyst — full analysis access
- Project Manager — dashboard and milestone views
- Owner Representative — submission compliance, executive reports
- Program Director — portfolio-level dashboards only
- Administrator — user management, client configuration

### Current State

**No auth design exists.** No evaluation of auth providers. No role definitions. No data isolation strategy. This is the largest gap between current v0.x state and v1.0 requirements.

---

## 10. Database Schema

### 16-Entity Data Model (ARCHITECTURE_DRAFT.md)

| # | Entity | Source Table | Key Fields | Relationships |
|---|--------|-------------|------------|---------------|
| 1 | **ScheduleUpload** | Application | upload_id (PK), filename, upload_date, file_size, file_hash, p6_version, status | Root entity for each XER file |
| 2 | **Project** | PROJECT | proj_id (PK), upload_id (FK), proj_short_name, last_recalc_date, plan_start_date, plan_end_date, data_date | FK to ScheduleUpload; parent of Calendar, WBS, Activity |
| 3 | **Calendar** | CALENDAR | clndr_id (PK), name, type, day_hr_cnt, week_hr_cnt | Referenced by Activity.clndr_id |
| 4 | **WBS** | PROJWBS | wbs_id (PK), proj_id (FK), parent_wbs_id (FK, self-referential), wbs_name, proj_node_flag | Self-referential tree; parent of Activity |
| 5 | **Activity** | TASK | task_id (PK), proj_id (FK), wbs_id (FK), clndr_id (FK), task_code, task_name, status_code (enum: TK_NotStart/TK_Active/TK_Complete), task_type (enum: TT_Task/TT_LOE/TT_Mile/TT_FinMile), early_start, early_end, late_start, late_end, target_start, target_end, total_float_hr, free_float_hr, remain_drtn_hr, target_drtn_hr, phys_complete_pct, cstr_type, cstr_date | Central entity; has Predecessors, ResourceAssignments, ActivityCodes, UDFValues |
| 6 | **Predecessor** | TASKPRED | task_id (FK), pred_task_id (FK), proj_id (FK), pred_proj_id (FK), pred_type (FS/FF/SS/SF), lag_hr_cnt | Many-to-many between Activities |
| 7 | **Resource** | RSRC | rsrc_id (PK), name, type | Referenced by ResourceAssignment |
| 8 | **ResourceAssignment** | TASKRSRC | task_id (FK), rsrc_id (FK), target_qty, act_reg_qty, remain_qty | Links Activity to Resource |
| 9 | **ActivityCode** | ACTVCODE | task_id (FK), actv_code_id (FK), code_value | Links Activity to ActivityCodeType |
| 10 | **ActivityCodeType** | ACTVTYPE | actv_code_type_id (PK), name | Defines code categories |
| 11 | **UDFType** | UDFTYPE | udf_type_id (PK), table_name, label, data_type | Defines user-defined field types |
| 12 | **UDFValue** | UDFVALUE | task_id (FK), udf_type_id (FK), udf_text, udf_number, udf_date | Stores UDF values per activity |
| 13 | **Baseline** | Application (derived) | baseline_id (PK), proj_id (FK), name, type, last_update | Tracks baseline schedule references |
| 14 | **AnalysisResult** | Application | result_id (PK), upload_id (FK), analysis_type, score, results_json, created_at | Stores any analysis output (DCMA, CPM, etc.) |
| 15 | **ValidationScore** | Application | score_id (PK), upload_id (FK), total_score, dcma_results (JSON), quality_metrics (JSON), created_at | Composite validation with per-metric details |
| 16 | **ComparisonResult** | Application | comparison_id (PK), upload_id_prev (FK), upload_id_curr (FK), changed_pct, activities_json, relations_json, flags_json, created_at | Period-to-period comparison output |

### Entity Relationship Summary

```
ScheduleUpload --1:N-- Project --1:N-- WBS (self-referential tree)
                                   |-- Activity --N:M-- Predecessor
                                   |            |-- ResourceAssignment --> Resource
                                   |            |-- ActivityCode --> ActivityCodeType
                                   |            |-- UDFValue --> UDFType
                                   |-- Calendar
ScheduleUpload --1:N-- AnalysisResult
               --1:N-- ValidationScore
ComparisonResult references two ScheduleUploads (prev + curr)
Baseline references Project
```

### Tables Parsed but Not in Schema (forward compatibility)

Per TECHNOLOGY_ASSESSMENT.md, these are parsed and stored but not analyzed:
- RSRCRATE (resource cost rates — v0.4 EVM)
- PCATTYPE / PCATVAL (project codes — v1.0 portfolio)
- FINDATES (financial period dates — v0.4 cost)
- TASKFIN (task financial data — v0.4 cost)
- TRSRCFIN (resource financial data — v0.4 cost)
- MEMOTYPE / TASKMEMO (activity notebook entries)
- CURRTYPE (currency definitions)

### Entities Missing from Schema (identified in discovery but not designed)

- **ForensicTimeline** — CPA timeline with windows (architecture.md shows API endpoints but no entity)
- **TIAAnalysis** — TIA with fragments, responsibility attribution (API endpoints exist, no entity)
- **EVMAnalysis** — EVM metrics, S-curve data (API endpoints exist, no entity)
- **RiskSimulation** — Monte Carlo results, histogram, tornado (API endpoints exist, no entity)
- **ValueMilestone** — Business metadata for milestones (EXPERT_CONSULTATION_RESULTS.md Q2)
- **ContractProvision** — NOD/PCO/recovery schedule rules (Epic 7)
- **ScheduleHierarchy** — Multi-schedule parent-child relationships for IPS reconciliation (EXPERT_CONSULTATION_RESULTS.md Q5)

---

## Contradictions Between Documents

| # | Contradiction | Documents | Resolution Needed |
|---|--------------|-----------|-------------------|
| 1 | **Licensing model** — VISION_EVOLUTION.md says "no freemium, no paywalled features, entire platform is free." EXPERT_CONSULTATION_RESULTS.md Q15 synthesis says "adopt the open-core model: community edition + commercial enterprise edition." | VISION_EVOLUTION.md vs. EXPERT_CONSULTATION_RESULTS.md | Must decide: pure open-source (MIT everything) or open-core (MIT core + proprietary enterprise). |
| 2 | **Database approach** — ARCHITECTURE_DRAFT.md designs SQLite schema with SQLAlchemy ORM. architecture.md (current) says "In-Memory Store, v0.x: dict, v1.0: SQLite, v1.x: PostgreSQL." Current code uses in-memory dict. | ARCHITECTURE_DRAFT.md vs. architecture.md | The draft was aspirational; current implementation is in-memory. The migration plan is consistent but the schema has not been implemented. |
| 3 | **Number of epics** — PRODUCT_BACKLOG.md defines 10 epics. DISCOVERY_STATUS.md says "6 additional" from consultation (Epics 11-16), totaling 16. MVP_DEFINITION.md roadmap only covers original 10 + multi-tenant. | PRODUCT_BACKLOG.md vs. DISCOVERY_STATUS.md vs. MVP_DEFINITION.md | The 6 new epics need to be formally integrated into the roadmap. |
| 4 | **API path prefix** — ARCHITECTURE_DRAFT.md uses `/api/upload`, `/api/validation/{id}`, etc. architecture.md uses `/api/v1/upload`, `/api/v1/projects/{id}/validation`, etc. | ARCHITECTURE_DRAFT.md vs. architecture.md | architecture.md (more recent, March 26) appears authoritative. The v1 prefix is the current standard. |
| 5 | **MVP version labeling** — MVP_DEFINITION.md titles itself "v0.1 Foundation" but the project is at v0.5.0. The roadmap in MVP_DEFINITION.md (v0.1 through v2.0) was written before v0.1 was built. | MVP_DEFINITION.md vs. git tags | The roadmap versions have been delivered (v0.1-v0.5). MVP_DEFINITION.md is now a historical document, not a current plan. |

---

## Summary for v0.6 Planning

**What has been built (v0.1-v0.5):**
- Custom MIT XER parser (streaming, encoding-aware, 8,000+ activities)
- DCMA 14-Point Assessment
- CPM engine (NetworkX forward/backward pass)
- Schedule comparison with manipulation detection
- Forensic CPA / Window Analysis
- TIA engine
- Contract compliance checking
- EVM engine
- Monte Carlo QSRA
- SvelteKit frontend with 13+ routes
- 32+ API endpoints
- 222 tests passing

**What v0.6 should focus on (based on all discovery documents):**
1. **Persistent storage** — Migrate from in-memory to SQLite. Without this, no trend analysis, no XER archive, no multi-session capability.
2. **Historical XER archive** — Store every upload chronologically. Foundation for everything proactive.
3. **Float trend analysis + Early Warning System** — The "killer differentiator" per expert consultation.
4. **Schedule Review Pipeline** — Automated upload-to-report workflow. Rated P0 by consultation.
5. **Enhanced manipulation detection** — Risk-level classification of changes (normal/suspicious/red-flag).
6. **PDF export for all analysis types** — Currently the weakest reporting capability.

**Key strategic question for v0.6:**
The project must resolve the open-core vs. pure open-source contradiction before building enterprise features (auth, multi-tenant, audit trail).
