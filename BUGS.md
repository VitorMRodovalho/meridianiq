# Known Issues & Backlog — v3.6.0-dev

Bug tracking and feature backlog for MeridianIQ.

---

## Active Bugs

_No open bugs at v3.6.0-dev. Report new issues via GitHub Issues._

---

## Previously Fixed

| ID | Description | Fixed In |
|----|-------------|---------|
| BUG-024 | `/demo` already in sidebar (Getting Started section) — was false report | v3.2.0 |
| BUG-023 | `/programs` missing from sidebar — added to Enterprise section + index page | v3.3.0 |
| BUG-022 | Schedule Viewer: dependency lines to hidden rows — fixed by virtual scrolling | v3.3.0 |
| BUG-021 | Schedule Viewer: date axis labels overlap on day zoom — min 48px spacing, adaptive format | v3.3.0 |
| BUG-020 | Schedule Viewer: WBS tree not showing level names/path — full path tooltip, numeric-only codes filtered | v3.3.0 |
| BUG-001 | Milestones not detected — case-sensitive task_type matching | 2026-03-25 |
| BUG-002 | Case sensitivity in task_type/status_code across DCMA + API | 2026-03-25 |
| OBS-001 | WBS display showed count only — added WBSStats hierarchy | 2026-03-25 |
| BUG-006 | ReferenceError — circular store dependency (auth.ts lazy init) | v0.8.1 |
| BUG-007 | Fly.io cold start 502+CORS — retry with backoff + warm-up banner | v0.9.0 |
| BUG-008 | DCMA threshold display — `direction` field, `<=`/`>=` operators | v0.9.0 |
| BUG-009 | Orphan DB rows — soft-delete migration (006), RLS policy update | v0.9.0 |
| BUG-010 | v0.6 git tag missing — tagged `dcb699a` as v0.6.0 | v0.9.0 |
| BUG-011 | docker-compose port mismatch + missing web/Dockerfile | v0.9.0 |
| — | Toast notification system missing | v1.1.0 |
| — | i18n wiring not connected to UI | v1.1.0 |
| — | Sidebar crowded (13 links, no grouping) | v1.1.0 |
| — | No rate limiting on API | v2.0.0 (slowapi) |
| — | No CORS whitelist (wildcard *) | v1.3.0 |
| — | No security headers (HSTS, X-Frame) | v1.3.0 |
| — | No GDPR data deletion workflow | v2.1.0 (migration 014) |
| — | RLS policies missing on 5 tables | v2.0.0 (migration 011) |
| — | Cash flow S-Curve visualization | v3.0.0 |
| — | Risk heat map (probability x impact matrix) | v3.0.0 |
| — | GanttChart SVG component | v3.0.0 |
| — | Look-ahead schedule (2/4 week window) | v3.0.0 |
| — | Executive summary PDF report | v3.0.0 |
| ��� | ParetoChart SVG dedicated component | v3.0.0 |
| — | 8 frontend gap pages (anomalies, root-cause, etc.) | v3.0.1 |
| — | Dark mode with Tailwind CSS overrides | v3.1.0 |
| — | Loading skeletons on 24 pages | v3.1.0 |
| — | Breadcrumb navigation | v3.1.0 |
| — | Collapsible sidebar sections | v3.1.0 |
| — | Active link highlighting | v3.1.0 |
| — | Error boundary (svelte:boundary) | v3.1.0 |
| — | Calendar validation engine (DCMA #13) | v3.1.0 |
| — | Delay attribution engine (party breakdown) | v3.1.0 |
| — | i18n 90+ keys PT-BR/ES (page titles, common labels) | v3.1.0 |
| — | 2 MCP tools (calendar, attribution) | v3.1.0 |
| — | RBAC sidebar (hide when unauthenticated) | v3.1.0 |
| — | Interactive Schedule Viewer (30+ features, 4 waves) | v3.2.0 |
| — | 404 error page, SEO meta tags, keyboard shortcuts modal | v3.2.0 |
| — | Compare visual diff (duration bars, float erosion bars) | v3.2.0 |
| — | Cross-page "View Schedule" links (18 entry points) | v3.2.0 |
| — | Upload success: View Schedule + Scorecard buttons | v3.2.0 |

---

## Technical Debt (Open)

| Item | Priority | Notes |
|------|----------|-------|
| ~~Large schedule profiling (>5K activities)~~ | ~~P1~~ | Tested with 10K+ activities — virtual scrolling works |
| ~~Schedule Viewer virtual scrolling~~ | ~~P1~~ | Done — viewport-aware rendering with 20-row buffer |
| Audit trail IP not populated | P2 | Schema field exists, frontend doesn't send |
| Dockerfile pinned to Python 3.13 | P3 | pyiceberg lacks 3.14 wheel; CI tests on 3.14 |
| slowapi potentially unmaintained | P2 | Evaluate starlette-ratelimit alternative |
| Wire $t() i18n keys to page titles | P3 | Keys exist, most page titles still hardcoded English |
| Sidebar has 34 links (cognitive load) | P2 | Consider regrouping or adding search |
| a11y warnings in ScheduleViewer (3) | P3 | SVG `<g>` click without keyboard handler |

---

## Feature Backlog (Prioritized)

### High Impact — Schedule Viewer

| # | Feature | Personas | Effort |
|---|---------|----------|--------|
| ~~1~~ | ~~Fix WBS level names display~~ — done: path tooltip, numeric code filter | All | ~~Low~~ |
| ~~2~~ | ~~Fix date axis label overlap~~ — done: min-px spacing, adaptive format | All | ~~Low~~ |
| ~~3~~ | ~~Standard columns~~ — done: 23 columns incl. AS/AF/RD/FF/BL/Var | Scheduler | ~~Medium~~ |
| ~~4~~ | ~~Column configuration panel~~ — done: show/hide with checkbox panel | All | ~~Medium~~ |
| ~~5~~ | ~~PDF/image export~~ — done: print dialog with full SVG | PM, Owner Rep | ~~Medium~~ |
| ~~6~~ | ~~Non-working day shading~~ — done: weekend bands on timeline | Scheduler | ~~Medium~~ |

### High Impact — Platform

| # | Feature | Personas | Effort |
|---|---------|----------|--------|
| 7 | Add /programs to sidebar + program-level dashboard | Program Director | Medium |
| 8 | Resource histogram below Gantt | Scheduler, PM | High |
| 9 | EVM S-Curve inline visualization | Cost Engineer | Medium |
| ~~10~~ | ~~Sidebar search/filter for 34+ links~~ — done: / to focus search | All | ~~Low~~ |

### Medium Impact

| # | Feature | Personas | Effort |
|---|---------|----------|--------|
| ~~11~~ | ~~Drag-to-pan on Gantt timeline~~ — done: mouse drag scrolls both axes | All | ~~Medium~~ |
| 12 | Calendar exception parsing (CALEXCEPTION table) | Scheduler | Medium |
| 13 | Activity grouping by any field | All | Medium |
| 14 | WebSocket for Monte Carlo/optimizer progress | All | Medium |
| 15 | Earned value overlay on timeline | Cost Engineer | High |

### Future / Research

| # | Feature | Personas | Effort |
|---|---------|----------|--------|
| 16 | AIA G703/DCMA schedule submission PDF format | Claims | High |
| 17 | Federated learning (cross-org ML) | AI Researcher | High |
| 18 | BIM-lite integration (IFC metadata) | Architect | High |
| 19 | Resource-constrained critical path on Gantt | Scheduler | High |
| 20 | GIS for infrastructure linear scheduling | Field | High |

---

## Open Testing Checklist

- [x] Upload — large XER files (1,000+ activities) — tested with 10K+ acts
- [ ] Upload — MS Project XML files (validate parser)
- [ ] Upload — XER with special characters (accents, symbols)
- [ ] DCMA 14-Point — verify against Schedule Validator reference
- [ ] Critical Path — non-standard work hours calendar
- [x] Schedule Viewer — test with real production XER (500+ activities) — tested 10K+
- [x] Schedule Viewer — baseline comparison with consecutive updates
- [x] Schedule Viewer — verify WBS names display correctly — path tooltip + code filter
- [x] Compare — two consecutive real-world schedule updates — tested MPS UP03 vs UP04
- [ ] Float Trends — 3+ sequential uploads
- [ ] PDF Reports — layout and data for all 9 types
- [ ] Excel Export — verify 4-sheet workbook accuracy
- [ ] IPS Reconciliation — master + 2 sub-schedules
- [ ] Recovery Validation — impacted vs recovery with compressed durations
- [ ] Organizations — create, invite, share, audit trail
- [ ] Auth — token expiry and refresh flow
- [ ] Mobile — all pages + hamburger menu + collapsible sections
- [ ] Dark mode — verify all 42 pages render correctly
- [ ] Print — verify schedule page prints with correct layout
- [ ] XER Export — round-trip fidelity with real P6 import
