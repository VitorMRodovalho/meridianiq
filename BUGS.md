# Known Issues — v0.9.0

Bug tracking for MeridianIQ. Entries are prioritized P1 (production-blocking) → P3 (minor).

All bugs from v0.8.1 have been resolved. See "Previously Fixed" below.

---

## Previously Fixed

| ID | Description | Fixed In |
|----|-------------|---------|
| BUG-001 | Milestones not detected — case-sensitive task_type matching | 2026-03-25 |
| BUG-002 | Case sensitivity in task_type/status_code across DCMA + API | 2026-03-25 |
| OBS-001 | WBS display showed count only — added WBSStats hierarchy | 2026-03-25 |
| BUG-006 | ReferenceError — circular store dependency in production build (auth.ts lazy init) | v0.8.1 |
| BUG-007 | Fly.io cold start 502+CORS — retry with backoff + warm-up banner | v0.8.1 docs sync |
| BUG-008 | DCMA threshold display — added `direction` field, correct `<=`/`>=` operators | v0.8.1 docs sync |
| BUG-009 | Orphan DB rows — soft-delete migration (006), RLS policy update | v0.8.1 docs sync |
| BUG-010 | v0.6 git tag missing — tagged `dcb699a` as v0.6.0 | v0.8.1 docs sync |
| BUG-011 | docker-compose port mismatch — corrected to 8080, commented out web service | v0.8.1 docs sync |

---

## Deferred Backlog (not bugs — planned features)

These were scoped for earlier versions but deferred. Tracked here to avoid losing context.

| Item | Original Version | Notes |
|------|-----------------|-------|
| Parser versioning | v0.6 P1 | Each parsed XER stored with `parser_version` field |
| Enhanced manipulation scoring | v0.8 P1 | Normal / Suspicious / Red Flag classification with scoring rationale |
| Monthly review template | v0.8 P2 | Standardized workflow, exportable PDF |
| Novel metrics — float entropy | v0.8 P2 | Entropy-based float distribution analysis |
| Novel metrics — constraint accumulation rate | v0.8 P2 | Track constraint growth over schedule updates |
| Anonymous/demo mode | v0.7 P2 | Unauthenticated access to curated sample project |
| Account settings page | v0.7 P2 | View profile, display name, usage statistics |

---

## Open Testing Checklist

Real-world XER testing (in addition to unit tests):

- [ ] Upload — test with large XER files (1,000+ activities)
- [ ] Upload — test with XER files containing special characters (accents, symbols)
- [ ] DCMA 14-Point — verify scoring accuracy against Schedule Validator reference output
- [ ] Critical Path — verify CP identification on calendar with non-standard work hours
- [ ] Float Distribution — verify P6 hours → days conversion on non-8hr calendars
- [ ] Compare — test with two consecutive real-world schedule updates
- [ ] Float Trends — verify trend calculation with 3+ sequential uploads
- [ ] Early Warning — verify all 12 rules fire correctly against known test cases
- [ ] PDF Reports — verify layout and data accuracy for all 5 report types
- [ ] Auth — test token expiry and refresh flow
- [ ] Contract Compliance — test provision checks against TIA with known violations

---

<div align="center">

**MeridianIQ** · MIT License · © 2025 Vitor Maia Rodovalho

</div>
