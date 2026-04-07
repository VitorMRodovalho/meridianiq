# Gap Assessment — MeridianIQ v3.3.0

Date: 2026-04-07
Methodology: API journey testing with real data (10K+ activities), code audit, persona simulation

---

## 1. API Journey Test Results

### All Endpoints Tested (proj with 10,284 activities)

| Endpoint | Status | Time | Notes |
|----------|--------|------|-------|
| GET /schedule-view | 200 | 332ms | 9.7MB response — OK |
| GET /scorecard | 200 | 213ms | OK |
| GET /critical-path | 200 | 104ms | OK |
| GET /float-entropy | 200 | 11ms | OK |
| GET /risk-register | 200 | 7ms | OK |
| GET /calendar-validation | 200 | 10ms | OK |
| GET /delay-attribution | 200 | 112ms | OK |
| GET /anomalies | 200 | 32ms | OK |
| GET /root-cause | 200 | 368ms | OK |
| GET /delay-prediction | 200 | 201ms | 3.1MB — large response |
| GET /milestones | 200 | 13ms | OK |
| GET /alerts | 400 | 6ms | Requires baseline_id param |
| GET /health | 200 | 35ms | OK |
| GET /pareto | 405 | 5ms | Wrong method — should be POST |
| GET /lookahead | 200 | 115ms | OK |
| POST /compare | 200 | 363ms | OK |
| POST /trends | 200 | 26ms | OK (with scorecard) |
| POST /evm/analyze | 200 | - | OK |
| GET /dashboard | 200 | - | OK |

### Issues Found
- **Alerts endpoint** requires `baseline_id` — frontend should auto-select or show guidance
- **Pareto** is POST, not GET — frontend route `/pareto` doesn't exist yet
- **Delay prediction** response is 3.1MB for 10K activities — may be slow on mobile

---

## 2. Frontend Route Audit (45 pages)

### Dark Mode Support
- **5 pages with dark mode:** /, /schedule, /trends, /upload, /programs
- **40 pages without dark mode** — will show white backgrounds in dark theme
- **Priority:** P2 — affects all authenticated users using dark mode

### Internationalization (i18n)
- **4 pages with good i18n:** / (22), /upload (7), /calendar-validation (4), /lookahead (4)
- **41 pages with minimal/no i18n** — hardcoded English strings
- **Priority:** P3 — most users are English-speaking, but PT-BR/ES keys exist unused

### Missing Page Titles
- `/evm`, `/risk`, `/risk/[id]`, `/evm/[id]`, `/auth/callback` — no `<svelte:head>` title
- **Priority:** P3 — affects SEO and browser tab identification

### Missing Frontend Pages (API exists, no page)
- `/pareto` — API endpoint exists, no frontend page
- **Priority:** P2 — feature gap

---

## 3. Persona Journey Analysis

### Persona 1: Scheduler (Primary)
**Journey:** Upload → Schedule Viewer → Compare → Float Trends → Look-Ahead
- Upload: Works, metadata tags shown ✅
- Schedule Viewer: Virtual scrolling works for 10K+ ✅
- Compare: Works with real data ✅
- Float Trends: Works ✅
- Look-Ahead: Works ✅
- **Gap:** No way to quickly switch between consecutive updates in Schedule Viewer
- **Gap:** WBS filter in table is limited to `wbs_path.startsWith()` — needs full-text search

### Persona 2: Project Manager
**Journey:** Dashboard → Scorecard → Schedule Viewer → Reports
- Dashboard: KPIs, health distribution, quick actions ✅
- Scorecard: 5 dimensions, A-F grade ✅
- Reports: PDF generation hub ✅
- **Gap:** No executive summary PDF that combines scorecard + Gantt + key findings

### Persona 3: Claims Consultant
**Journey:** Upload Baseline + Update → Compare → Forensic CPA → TIA → Delay Attribution
- Compare: Manipulation detection, activity matching ✅
- Forensic: Window analysis ✅
- TIA: Delay fragments ✅
- Delay Attribution: Party breakdown ✅
- **Gap:** No narrative report template for claim documentation
- **Gap:** No way to export forensic analysis as structured PDF for legal proceedings

### Persona 4: Program Director
**Journey:** Dashboard → Programs → Trends → IPS Reconciliation
- Programs: Index page exists ✅
- Trends: Multi-schedule evolution ✅
- IPS: Reconciliation page exists ✅
- **Gap:** No program-level aggregated dashboard (rollup across sub-schedules)
- **Gap:** No portfolio-level trend analysis (across programs)

### Persona 5: Cost Engineer
**Journey:** EVM → Milestones → Cashflow → Risk
- EVM: SPI/CPI/EAC analysis ✅
- Milestones: Value milestones page ✅
- Cashflow: S-Curve visualization ✅
- **Gap:** No CBS (Cost Breakdown Structure) integration
- **Gap:** No budget vs actual cost tracking
- **Gap:** EVM page lacks dark mode

---

## 4. Quality Score Trend (Real Data)

Testing with 3 sequential MPS updates:
- **UP 05 (Feb 2025):** Score 73.3 (C)
- **UP 08 (May 2025):** Score 67.9 (D)
- **UP 13 (Oct 2025):** Score 66.1 (D)

**Insight:** Quality declining over time — scope growth (+16%) without proportional logic maintenance. Critical path expanded from 594 to 1,530 activities. Negative float grew from 466 to 1,328.

---

## 5. Risk & Compliance Assessment

### Security
- [ ] CORS: Currently using wildcard in development — production should whitelist domains
- [ ] Auth: `optional_auth` on upload endpoint — allows anonymous uploads
- [ ] File upload: 50MB limit, type validation (XER/XML only) ✅
- [ ] Rate limiting: slowapi configured ✅
- [ ] No SQL injection risk — Supabase client abstraction ✅
- [ ] No XSS risk — Svelte auto-escapes by default ✅

### Compliance
- [ ] MIT license — need to verify all dependencies are compatible
- [ ] GDPR: Soft-delete migration exists (014) ✅
- [ ] No client names in code — confirmed via grep ✅
- [ ] Academic citations in engine docstrings — need to verify completeness

### Governance
- [ ] CHANGELOG.md exists but may be outdated
- [ ] BUGS.md updated this session ✅
- [ ] No formal release process (no git tags for v3.3.0)
- [ ] No CONTRIBUTING.md or CODE_OF_CONDUCT.md

---

## 6. Data Integration Opportunities

### Available Data Sources (sandbox)
- **04-Schedule.zip:** ~90 XER files (MPS, IMS, CMAR) — already parsed
- **06-Costs.zip:** CBS/budget data — unexplored
- **07-Reporting.zip:** Monthly reports — unexplored

### CBS/OBS/WBS/RBS Correlation Potential
- WBS already parsed from XER ✅
- CBS would come from cost data (06-Costs.zip)
- OBS from organizational hierarchy in XER (partially parsed)
- RBS from risk register data

### Next Steps for 3-World Correlation
1. Explore 06-Costs.zip structure
2. Map CBS codes to WBS codes
3. Build cost loading engine (new engine #36)
4. Create cost-schedule integration view
5. Explore 07-Reporting.zip for narrative report templates

---

## 7. Prioritized Action Items

### Critical (Fix Now)
1. Nothing critical — all core functionality works

### High Priority
1. Dark mode for 40 pages (batch fix with sed/script)
2. Pareto frontend page
3. Executive summary PDF report
4. CBS integration from cost data
5. Narrative report templates for claims

### Medium Priority
6. i18n wiring for remaining 41 pages
7. Missing page titles (5 pages)
8. Alerts page: auto-detect baseline
9. Program-level aggregated dashboard
10. Portfolio trend analysis

### Low Priority
11. CHANGELOG.md update
12. CONTRIBUTING.md
13. Git tag v3.3.0
14. a11y improvements (SVG keyboard handlers)
15. Mobile responsive testing
