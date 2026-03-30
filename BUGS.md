# Known Issues & Backlog — v1.0.0

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

## Previously Delivered (from deferred backlog)

| Item | Delivered In |
|------|-------------|
| Parser versioning | v0.9.1 — `parser_version` field on ParsedSchedule |
| Enhanced manipulation scoring | v0.9.1 — Normal/Suspicious/Red Flag + 0-100 score |
| Anonymous/demo mode | v0.9.0 — /demo page + /api/v1/demo/project |
| Account settings page | v0.9.0 — /settings page with profile, usage, privacy |

---

## Sprint Backlog

### v1.1 "UX Maturity" — Next

| # | Item | Effort | Persona | Status |
|---|------|--------|---------|--------|
| 1 | Value milestones frontend page | Low | Owner, PM | |
| 2 | Compare page: show manipulation scoring badges | Low | PM, Scheduler | |
| 3 | Sidebar grouping (Analysis / Enterprise / Settings) | Low | All | |
| 4 | Toast notification system | Low | All | |
| 5 | i18n wiring — connect $t() to landing + upload + dashboard | Medium | LATAM market | |
| 6 | Monthly review template (PDF) | Medium | Scheduler | |
| 7 | Projects list: sorting, filtering, search | Low | All | |

### v1.2 "Academic & Research"

| # | Item | Effort | Persona |
|---|------|--------|---------|
| 1 | Float entropy metric | Medium | Researcher |
| 2 | Constraint accumulation rate | Medium | Researcher |
| 3 | MCP Server — Claude integration via Model Context Protocol | Medium | AI/Developer |
| 4 | API keys — self-service generation for programmatic access | Medium | Researcher |
| 5 | JSON/CSV export — structured data for external analysis | Low | Researcher |
| 6 | Root cause analysis — backwards network trace to delay origin | High | Forensic Analyst |

### v2.0 "AI"

| # | Item | Effort | Persona |
|---|------|--------|---------|
| 1 | NLP queries via Claude API | Medium | All |
| 2 | Anomaly detection — statistical outlier detection | Medium | Scheduler |
| 3 | Delay prediction — regression on historical float velocity | High | PM |
| 4 | Benchmark database — anonymized aggregate metrics | High | Industry |
| 5 | Federated learning | High | Enterprise |

---

## Technical Debt

| Item | Priority | Notes |
|------|----------|-------|
| i18n infrastructure wired but not connected to UI | P1 | Pages use hardcoded English |
| No RBAC enforcement on frontend | P2 | Sidebar shows all links regardless of role |
| No rate limiting on API | P2 | DDoS vulnerability |
| No loading skeletons (uses spinners) | P3 | Perceived performance |
| No breadcrumb navigation | P3 | Wayfinding on deep pages |
| No toast notifications | P3 | Action feedback |
| Sidebar crowded (13 links) | P3 | Needs grouping |
| No dark mode | P3 | Developer/researcher preference |
| Performance: large schedules (>5K activities) not profiled | P2 | Server-side summaries help, needs testing |

---

## Governance Gaps

| Item | Priority | Notes |
|------|----------|-------|
| No GDPR data deletion workflow | P1 | User cannot delete their data |
| No security headers (CSP, HSTS) on CF Pages | P2 | Security audit requirement |
| Audit trail IP tracking not populated | P2 | Schema field exists, frontend doesn't send |
| No documented backup/restore process | P3 | Supabase has backups, needs docs |

---

## Open Testing Checklist

- [ ] Upload — large XER files (1,000+ activities)
- [ ] Upload — MS Project XML files (validate parser)
- [ ] Upload — XER with special characters (accents, symbols)
- [ ] DCMA 14-Point — verify against Schedule Validator reference
- [ ] Critical Path — non-standard work hours calendar
- [ ] Float Distribution — P6 hours to days on non-8hr calendars
- [ ] Compare — two consecutive real-world schedule updates
- [ ] Compare — verify manipulation scoring UI badges
- [ ] Float Trends — 3+ sequential uploads
- [ ] Early Warning — all 12 rules against known test cases
- [ ] PDF Reports — layout and data for all 5 types
- [ ] Excel Export — verify 4-sheet workbook accuracy
- [ ] IPS Reconciliation — master + 2 sub-schedules
- [ ] Recovery Validation — impacted vs recovery with compressed durations
- [ ] Organizations — create, invite, share, audit trail
- [ ] Auth — token expiry and refresh flow
- [ ] Mobile — all pages accessible via hamburger menu
- [ ] Contract Compliance — provisions against TIA with violations

---

<div align="center">

**MeridianIQ** · MIT License · © 2025 Vitor Maia Rodovalho

</div>
