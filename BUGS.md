# Known Issues & Backlog — v3.0.1

Bug tracking and feature backlog for MeridianIQ.

---

## Previously Fixed

| ID | Description | Fixed In |
|----|-------------|---------|
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
| — | ParetoChart SVG dedicated component | v3.0.0 |
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

---

## Technical Debt (Open)

| Item | Priority | Notes |
|------|----------|-------|
| Large schedule profiling (>5K activities) | P2 | Not systematically tested |
| Audit trail IP not populated | P2 | Schema field exists, frontend doesn't send |
| Dockerfile pinned to Python 3.13 | P3 | pyiceberg lacks 3.14 wheel; CI tests on 3.14 |
| slowapi potentially unmaintained | P2 | Evaluate starlette-ratelimit alternative |
| No RBAC enforcement on frontend | P2 | Sidebar shows all links regardless of role |
| Wire $t() i18n keys to remaining pages | P3 | Keys exist in 3 langs, most pages still hardcoded |

---

## Feature Backlog (Prioritized)

### High Impact

| # | Feature | Personas | Effort |
|---|---------|----------|--------|
| 1 | Calendar validation engine | Scheduler | Medium |
| 2 | Contractor delay attribution summary | Owner Rep | High |
| 3 | Program shares API + UI | Program Scheduler, Director | Medium |
| 4 | i18n activation (PT-BR, ES translations) | LATAM market | Medium |
| 5 | Large schedule profiling (>5K activities) | All | Medium |

### Medium Impact

| # | Feature | Personas | Effort |
|---|---------|----------|--------|

### Future / Research

| # | Feature | Personas | Effort |
|---|---------|----------|--------|
| 11 | Federated learning (cross-org ML) | AI Researcher | High |
| 12 | BIM-lite integration (IFC metadata) | Architect, CCM | High |
| 13 | WebSocket for long operations (MC, ES) | All | Medium |
| 14 | Dark mode | Developer | Low |
| 15 | Loading skeletons | All | Low |

---

## Open Testing Checklist

- [ ] Upload — large XER files (1,000+ activities)
- [ ] Upload — MS Project XML files (validate parser)
- [ ] Upload — XER with special characters (accents, symbols)
- [ ] DCMA 14-Point — verify against Schedule Validator reference
- [ ] Critical Path — non-standard work hours calendar
- [ ] Float Distribution — P6 hours to days on non-8hr calendars
- [ ] Compare — two consecutive real-world schedule updates
- [ ] Float Trends — 3+ sequential uploads
- [ ] Early Warning — all 12 rules against known test cases
- [ ] PDF Reports — layout and data for all 7 types
- [ ] Excel Export — verify 4-sheet workbook accuracy
- [ ] IPS Reconciliation — master + 2 sub-schedules
- [ ] Recovery Validation — impacted vs recovery with compressed durations
- [ ] Organizations — create, invite, share, audit trail
- [ ] Auth — token expiry and refresh flow
- [ ] Mobile — all pages accessible via hamburger menu
- [ ] XER Export — round-trip fidelity with real P6 import
- [ ] Risk Register — CRUD + Monte Carlo integration
- [ ] Resource Leveling — real XER with resource assignments
