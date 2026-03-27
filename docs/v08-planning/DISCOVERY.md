# MeridianIQ v0.8 "Intelligence" — Discovery & Scope Document

**Version:** Draft 1.0
**Date:** 2026-03-27
**Author:** Vitor Maia Rodovalho
**Status:** Planning

---

## 1. Design Philosophy

> "The tool should open the manager's vision — not make them manually search for problems."

v0.8 transforms MeridianIQ from a **reactive analysis engine** (user asks → system answers) into a **proactive intelligence platform** (system detects → user decides). The Python engine does the heavy lifting: standardized calculations run automatically on upload, anomalies surface without prompting, and every metric is grounded in published standards.

### Guiding Principles

1. **Predictive over Reactive** — Don't wait for the user to ask "is there a problem?" Detect it, quantify it, and present it with context.
2. **Standards-Based** — Every metric, threshold, and formula traces to a published standard or peer-reviewed source. No magic numbers.
3. **Scenario Extrapolation** — Always show "if this trend continues" projections alongside current state.
4. **Python Does the Work** — Standardized calculations (DCMA, EVM, CPM, float analysis) execute automatically. The user configures once, not every time.
5. **Professional Personas First** — Design for the senior scheduler, the claims consultant, the PM executive, and the academic researcher. Not for casual users.

---

## 2. Standards & References Foundation

### Industry Standards (Normative)

| Standard | Relevance to v0.8 | Specific Sections |
|----------|-------------------|-------------------|
| **AACE RP 29R-03** | Forensic Schedule Analysis | Methods 1-6, contemporaneous analysis |
| **AACE RP 52R-06** | Time Impact Analysis | Prospective TIA methodology |
| **AACE RP 57R-09** | Schedule Risk Analysis (QSRA) | Monte Carlo, correlation, sensitivity |
| **AACE RP 49R-06** | Identifying Critical Activities | Float consumption, near-critical paths |
| **AACE RP 10S-90** | Cost Engineering Terminology | EVM definitions (BCWS, BCWP, ACWP) |
| **PMI SP (2019)** | Practice Standard for Scheduling | Schedule health, float management |
| **PMI PMBOK 7th (2021)** | Performance domains | Measurement performance domain |
| **DCMA 14-Point Assessment** | Schedule quality metrics | All 14 checks with thresholds |
| **GAO Schedule Assessment Guide (2020)** | Best practices | Comprehensive, well-constructed, credible, controlled |
| **ISO 21500:2021** | Project management guidance | Schedule baseline management |
| **CMAA (2019)** | CM Standards of Practice | Schedule review, claims avoidance |

### Academic References (Informative)

| Publication | Relevance |
|-------------|-----------|
| Hegazy & Menesi (2008) | Critical path segments method |
| Kim & de la Garza (2005) | Phantom float detection |
| Ibbs & Nguyen (2011) | Schedule delay analysis methods comparison |
| Arditi & Pattanakitchamroon (2006) | Selection of delay analysis methods |
| Braimah & Ndekugri (2008) | Concurrent delay categorization |
| Zack (2001) | "But-for" schedule development |
| Winter (2003) | Float ownership concepts |

---

## 3. Target Personas

### P1 — Senior Scheduler / Planner
- **Context:** Manages P6 schedules for $50M–$2B projects. Runs monthly updates. Needs to spot deterioration fast.
- **v0.8 Value:** Float erosion alerts on upload. Health score trend across updates. "Your CP shifted from structural to MEP in the last 3 updates" — automatic.
- **Tools today:** Excel pivot tables, manual float comparison, Claim Digger.

### P2 — Claims Consultant / Forensic Analyst
- **Context:** Retained post-dispute. Analyzes 20-50 schedule updates. Needs defensible methodology per AACE RP 29R-03.
- **v0.8 Value:** Automatic manipulation detection across updates. PDF report with methodology citations. Delay waterfall with trend.
- **Tools today:** Manual Excel analysis, Primavera P6 comparison, Word reports.

### P3 — Project Manager / Construction Manager (CMAA)
- **Context:** Oversees multiple projects. Needs dashboard-level visibility. "Which of my 5 projects is in trouble?"
- **v0.8 Value:** Dashboard with health scores, alert counts, trend arrows. Drill-down to specifics. No P6 expertise required.
- **Tools today:** Monthly schedule narrative (often outdated), gut feel.

### P4 — Academic Researcher
- **Context:** Studies delay causation, schedule quality metrics, or dispute resolution. Needs reproducible analysis.
- **v0.8 Value:** Standardized metrics with formula transparency. Export data for statistical analysis. Method citations.
- **Tools today:** Manual data extraction from P6, custom Python scripts.

---

## 4. Feature Specifications

### 4.1 Float Trend Analysis

**Standard:** AACE RP 49R-06 (Identifying Critical Activities), PMI SP §6.6 (Float Management)

**What it does:** Tracks how total float (TF) for each activity changes across schedule updates. Float consumption without progress = schedule deterioration.

**Engine (Python — automatic on upload when ≥2 updates exist):**

```
For each activity present in both baseline and update:
  Δ_float = TF_current - TF_baseline
  consumption_rate = Δ_float / days_between_updates
  projected_critical_date = today + (TF_current / |consumption_rate|)  # if rate < 0
```

**Metrics produced:**
- **Float Erosion Index (FEI):** % of activities that lost float without proportional progress
- **Near-Critical Drift:** Count of activities crossing the 10-day TF threshold (per DCMA #3)
- **Critical Path Stability:** % of CP activities that remain on CP across updates (per GAO §7.3)
- **Float Consumption Velocity:** Average float days lost per calendar day, per WBS area

**Thresholds (per DCMA + industry consensus):**
| Metric | Green | Yellow | Red |
|--------|-------|--------|-----|
| FEI | < 10% | 10-25% | > 25% |
| Near-critical drift | < 5% new | 5-15% | > 15% |
| CP Stability | > 80% | 60-80% | < 60% |

**Output:** Float trend chart per activity/WBS, heatmap of float consumption by area.

**References:**
- Kim & de la Garza (2005): Phantom float — float that exists mathematically but cannot be consumed without violating resource or physical constraints.
- DCMA checks #3 (High Float), #4 (Negative Float), #5 (High Duration).

---

### 4.2 Early Warning System

**Standard:** GAO Schedule Assessment Guide §9 (Schedule Surveillance), PMI PMBOK 7 §4.6 (Measurement)

**What it does:** Rules engine that runs automatically on every upload. Produces prioritized alerts — not just "pass/fail" but "this matters because..." with projected impact.

**Alert Categories (12 rules, expandable):**

| # | Alert | Trigger | Severity | Standard |
|---|-------|---------|----------|----------|
| 1 | Float Erosion | Activity lost >5d float, <50% progress | Warning | RP 49R-06 |
| 2 | Critical Path Shift | >20% of CP activities changed | Critical | GAO §7.3 |
| 3 | Logic Deletion | Predecessors removed between updates | Critical | DCMA #7 |
| 4 | Duration Growth | Activity duration increased >20% | Warning | DCMA #5 |
| 5 | Retroactive Date Change | Actual dates modified in past periods | Critical | RP 29R-03 |
| 6 | Constraint Addition | New constraints added (potential manipulation) | Warning | DCMA #10 |
| 7 | Negative Float Growth | Negative float increased >10d | Critical | DCMA #4 |
| 8 | Resource Overallocation | Resource >100% allocated | Warning | PMI SP §6.7 |
| 9 | Open-Ended Activities | Activities missing predecessor or successor | Critical | DCMA #6, #7 |
| 10 | Progress Override | Physical % complete doesn't match duration | Warning | DCMA #12 |
| 11 | Calendar Anomaly | Non-standard calendar reducing available days | Info | DCMA #13 |
| 12 | Baseline Deviation | Finish variance >10% of remaining duration | Warning | PMI PMBOK |

**Engine behavior:**
- Runs automatically when upload has ≥2 schedules in the same project
- Compares current update to previous (n vs n-1) AND to baseline (n vs 0)
- Produces `alert_score` = Σ(severity_weight × confidence × impact_magnitude)
- Alerts ranked by score, grouped by WBS area

**Projected impact calculation:**
```python
# For each alert, extrapolate:
if trend_detected:
    projected_delay = current_variance + (variance_velocity × remaining_duration_ratio)
    confidence = min(1.0, n_datapoints / 5)  # need ≥5 updates for high confidence
```

**Output:** Alert dashboard with severity badges, trend sparklines, projected impact in days.

---

### 4.3 Schedule Health Score

**Standard:** DCMA 14-Point Assessment, GAO Schedule Assessment Guide (4 characteristics)

**What it does:** Single composite score (0–100) that answers "how healthy is this schedule?" Combines structural quality (DCMA), analytical integrity (float/CP), and trend direction.

**Formula:**

```
Health Score = (
    0.40 × DCMA_Score +           # Structural quality (14 checks)
    0.25 × Float_Health +          # Float distribution quality
    0.20 × Logic_Integrity +       # Relationship completeness
    0.15 × Trend_Direction          # Improving or deteriorating
)
```

**Sub-scores:**

| Component | Calculation | Source |
|-----------|-------------|--------|
| DCMA_Score | Existing v0.1 engine (14 checks, weighted) | DCMA 14-Point |
| Float_Health | 100 - (neg_float_% × 2 + high_float_% × 0.5) | RP 49R-06 |
| Logic_Integrity | 100 × (1 - open_ended_% - missing_logic_%) | DCMA #6, #7 |
| Trend_Direction | Based on float trend slope across last 3 updates (0=declining, 50=stable, 100=improving) | GAO §9 |

**Thresholds (aligned with GAO 4 characteristics):**
| Score | Rating | GAO Alignment |
|-------|--------|---------------|
| 85-100 | Excellent | Comprehensive + Well-constructed + Credible + Controlled |
| 70-84 | Good | Minor gaps in 1 characteristic |
| 50-69 | Fair | Significant gaps in 2+ characteristics |
| < 50 | Poor | Fundamental issues — schedule unreliable |

**Output:** Score badge on every project card + trend arrow (↑↓→) + breakdown donut chart.

---

### 4.4 Dashboard Analytics

**Standard:** PMI PMBOK 7 §4.6 (Measurement Performance Domain)

**What it does:** Executive-level dashboard that answers: "What's the state of my portfolio?" without clicking into individual projects.

**KPIs displayed:**

| KPI | Calculation | Visual |
|-----|-------------|--------|
| Total Projects | Count of uploaded projects | Number |
| Active Alerts | Count of Warning + Critical alerts | Number + badge |
| Avg Health Score | Mean health score across projects | Gauge (0-100) |
| Trending Up/Down | Projects improving vs deteriorating | Arrow indicators |
| Most Critical Project | Lowest health score | Highlighted card |
| Upload Activity | Uploads over last 30 days | Sparkline |

**Portfolio-level metrics (when ≥3 projects):**
- Health distribution histogram
- Alert heatmap by category
- Float erosion leaderboard (worst first)

**Design principle:** No clicks required to understand portfolio state. Everything visible on one screen. Drill-down available but not required.

---

### 4.5 PDF Report Export

**Standard:** AACE RP 29R-03 §5.3 (Documentation), CMAA §7 (Reporting)

**What it does:** Generates a professional PDF report for any analysis, suitable for submission in dispute proceedings, owner review, or academic citation.

**Report types:**

| Report | Contents | Pages (est.) |
|--------|----------|-------------|
| Schedule Health Report | DCMA results, health score, float distribution, alerts | 3-5 |
| Comparison Report | Delta summary, manipulation indicators, changes by WBS | 5-10 |
| Forensic Report | Timeline, delay waterfall, windows analysis, trend | 8-15 |
| TIA Report | Fragment analysis, CP impact, compliance check results | 5-8 |
| Risk Report | Monte Carlo results, distribution, sensitivity, tornado | 4-6 |

**Report structure (per AACE RP 29R-03 §5.3):**
1. Executive Summary (auto-generated)
2. Methodology Statement (with standard citations)
3. Data Summary (project info, data date, activity count)
4. Analysis Results (charts, tables, findings)
5. Conclusions & Recommendations (templated with detected issues)
6. Appendix: Detailed Data Tables

**Engine:** Python `reportlab` or `weasyprint` on the backend. Endpoint: `POST /api/v1/reports/generate` with `{project_id, report_type, options}`.

**Key design decision:** Reports include methodology citations automatically. Example:
> "Schedule comparison performed per AACE RP 29R-03 Method 3 (Contemporaneous Period Analysis). Float analysis per AACE RP 49R-06. 14-point assessment per DCMA guidance."

---

## 5. Implementation Architecture

### Backend (Python engine additions)

```
src/
  engine/
    float_trends.py          # NEW — Float Trend Analysis engine
    early_warning.py          # NEW — Rules engine (12 rules)
    health_score.py           # NEW — Composite health score calculator
    report_generator.py       # NEW — PDF report generation
  api/
    dashboard.py              # NEW — Dashboard endpoints
    alerts.py                 # NEW — Alerts endpoints
    reports.py                # NEW — Report generation endpoints
```

### New API Endpoints (8-10 new)

```
GET  /api/v1/dashboard                        # Portfolio KPIs
GET  /api/v1/dashboard/alerts                  # Active alerts summary
GET  /api/v1/projects/{id}/health              # Health score + breakdown
GET  /api/v1/projects/{id}/float-trends        # Float trend data
GET  /api/v1/projects/{id}/alerts              # Project-level alerts
GET  /api/v1/projects/{id}/early-warning       # Early warning analysis
POST /api/v1/reports/generate                  # Generate PDF report
GET  /api/v1/reports/{id}/download             # Download generated report
```

### Database (new tables)

```sql
-- Float snapshots (one per activity per upload)
CREATE TABLE float_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_id UUID REFERENCES activities(id),
    upload_id UUID REFERENCES schedule_uploads(id),
    total_float INTEGER,
    free_float INTEGER,
    is_critical BOOLEAN,
    captured_at TIMESTAMPTZ DEFAULT now()
);

-- Alerts
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    upload_id UUID REFERENCES schedule_uploads(id),
    rule_id TEXT NOT NULL,            -- e.g., 'float_erosion', 'cp_shift'
    severity TEXT NOT NULL,           -- 'info', 'warning', 'critical'
    title TEXT NOT NULL,
    description TEXT,
    affected_activities TEXT[],
    projected_impact_days FLOAT,
    confidence FLOAT,
    alert_score FLOAT,
    dismissed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Health scores (one per project per upload)
CREATE TABLE health_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    upload_id UUID REFERENCES schedule_uploads(id),
    overall_score FLOAT NOT NULL,
    dcma_score FLOAT,
    float_health FLOAT,
    logic_integrity FLOAT,
    trend_direction FLOAT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Generated reports
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    user_id UUID REFERENCES auth.users(id),
    report_type TEXT NOT NULL,
    title TEXT,
    file_path TEXT,                   -- Supabase Storage path
    file_size INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Frontend (new routes)

```
/dashboard              — Portfolio dashboard (redesigned)
/projects/{id}/health   — Health score detail
/projects/{id}/alerts   — Project alerts
/reports                — Report generation & download
```

---

## 6. Automatic Pipeline ("Python Shines")

The key architectural decision for v0.8: **analysis runs automatically on upload**, not on user request.

```
Upload .xer file
    ↓
Parse (existing v0.1 engine)
    ↓
DCMA Assessment (existing v0.1 engine)  ──→  health_scores table
    ↓
Float Snapshot Capture (NEW)            ──→  float_snapshots table
    ↓
If ≥2 uploads for this project:
    ├── Float Trend Analysis (NEW)      ──→  float trends data
    ├── Early Warning Rules (NEW)       ──→  alerts table
    └── Health Score Calculation (NEW)  ──→  health_scores table (with trend)
    ↓
Dashboard reflects new state immediately
```

The user uploads a file and **immediately sees** health score, alerts, and trends — without clicking "Analyze." This is the "Python does the work" principle.

---

## 7. Scope Control — What v0.8 Does NOT Include

| Excluded | Reason | Deferred To |
|----------|--------|-------------|
| ML-based prediction | Needs training data volume we don't have yet | v2.0 |
| NLP contract clause extraction | Separate AI workstream | v2.0 |
| Multi-user collaboration | Needs team/org model | v1.0 |
| Resource leveling engine | Complex, separate feature | v1.0+ |
| Custom alert rules (user-defined) | Start with curated rules first | v0.9 |
| Automated recovery schedule generation | Needs validated CPM engine | v2.0 |
| Real-time P6 integration | API complexity, licensing | v1.0+ |

---

## 8. Delivery Plan

### Phase 1: Engine (backend) — ~3 sessions
- Float trend analysis engine + tests
- Early warning rules engine + tests
- Health score calculator + tests
- New database migration (003_intelligence.sql)
- New API endpoints (8-10)
- Auto-pipeline integration (run on upload)

### Phase 2: Dashboard & Frontend — ~2 sessions
- Dashboard page redesign
- Health score cards + trend arrows
- Alerts panel with severity badges
- Float trend charts (per activity/WBS)

### Phase 3: Reports — ~2 sessions
- PDF report generator (reportlab/weasyprint)
- Report templates (5 types)
- Methodology citations in reports
- Download endpoint + Supabase Storage

### Phase 4: Polish & Deploy — ~1 session
- Integration testing (end-to-end upload → dashboard → report)
- Performance optimization
- Deploy to production
- Tag v0.8.0

**Estimated total:** 7-8 Claude Code sessions

---

## 9. Success Criteria

| Criteria | Measurement |
|----------|-------------|
| Auto-analysis on upload | Upload → health score visible in <5s |
| Alert accuracy | Zero false-critical alerts on DCMA sample schedules |
| Health score consistency | Same schedule → same score (deterministic) |
| PDF report quality | Report contains methodology citations, is court-submittable |
| Dashboard load time | < 2s for portfolio with 10 projects |
| Test coverage | ≥260 tests (current 246 + ~20 new) |
| Standards traceability | Every metric linked to published standard |

---

## 10. Open Questions for Review

1. **Float trend granularity:** Per-activity or per-WBS rollup? (Recommendation: both, WBS default)
2. **Alert notification:** Email alerts in v0.8 or defer to v0.9? (Recommendation: defer)
3. **PDF library:** `reportlab` (more control) vs `weasyprint` (HTML→PDF, easier templates)? (Recommendation: weasyprint — HTML templates are faster to iterate)
4. **Health score weights:** Are the proposed weights (40/25/20/15) reasonable? Need calibration against real project data.
5. **Report branding:** MeridianIQ watermark? User company logo upload? (Recommendation: MeridianIQ only for v0.8, custom branding v1.0)

---

*Document prepared for internal review. All standards referenced are publicly available. Implementation follows MIT license terms.*
