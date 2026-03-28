# Known Issues — v0.8.1

Bug tracking for MeridianIQ. Entries are prioritized P1 (production-blocking) → P3 (minor).

---

## P1 — Production Issues

### BUG-006: ReferenceError — circular store dependency in production build

- **Status:** OPEN
- **Severity:** P1 — breaks production frontend
- **Description:** SvelteKit production build (`npm run build`) throws a `ReferenceError` caused by a circular dependency between Svelte stores (auth store ↔ project store). Works correctly in dev mode (`npm run dev`). Likely introduced during v0.8.1 dashboard wiring.
- **Symptom:** Page renders blank or crashes on first load in deployed CF Pages environment.
- **Fix location:** `web/src/lib/stores/` — identify and break the circular import
- **Workaround:** None. Must be fixed before any frontend deploy from a clean build.

### BUG-007: Fly.io cold start causes 502 + CORS on first request

- **Status:** OPEN
- **Severity:** P1 — degrades first-use experience
- **Description:** Fly.io free-tier machines scale to zero after inactivity. Cold start takes approximately 10 seconds. During startup, the first request(s) receive a 502 from Fly.io's proxy, which the browser interprets as a CORS failure (no CORS headers on the 502 response).
- **Symptom:** First API call after period of inactivity fails with `Failed to fetch` / CORS error in browser console. Subsequent calls succeed normally.
- **Fix options:** (a) Keep-alive ping from CF Pages edge on a schedule, (b) Fly.io `min_machines_running = 1` (costs ~$2/mo), (c) Frontend retry with exponential backoff and user-visible "warming up…" message.
- **Fix location:** `fly.toml` and/or `web/src/lib/api.ts`

---

## P2 — Functional Issues

### BUG-008: DCMA checks #2 and #9 — threshold display inconsistency

- **Status:** OPEN
- **Severity:** P2 — misleading UI output
- **Description:** DCMA checks #2 (Leads) and #9 (Invalid Dates) display a non-zero percentage in the frontend even when the backend returns `value: 0.0` and `passed: true`. The threshold label also sometimes shows `> 0%` instead of `= 0%` for zero-tolerance checks.
- **Fix location:** Frontend component rendering the DCMA results table — likely `web/src/routes/projects/[id]/+page.svelte` or a shared DCMA component.

### BUG-009: Orphan project from pre-v0.8.1 uploads

- **Status:** OPEN
- **Severity:** P2 — data integrity
- **Description:** Projects uploaded before the v0.8.1 storage refactor (migration `004_storage_refactor.sql`) have `xer_storage_path = NULL` and `user_id = NULL` because the upload pipeline previously stored files inline. These orphan rows appear in the projects list but fail to load analysis results.
- **Fix location:** `src/database/store.py` — add null-guard on `xer_storage_path`; optionally backfill or soft-delete orphan rows via a one-time migration.

---

## P3 — Minor Issues

### BUG-010: v0.6 git tag missing from history

- **Status:** OPEN
- **Severity:** P3 — documentation/history only
- **Description:** Git tags exist for v0.1.0–v0.5.0, v0.7.0, and v0.8.0. The `v0.6.0` tag was never created. The v0.6 Cloud release was delivered across several commits but not formally tagged.
- **Fix:** `git tag v0.6.0 <commit-sha>` and `git push origin v0.6.0` — identify the commit that completed Cloudflare Pages deployment as the tag target.

---

## Previously Fixed

| ID | Description | Fixed In |
|----|-------------|---------|
| BUG-001 | Milestones not detected — case-sensitive task_type matching | 2026-03-25 |
| BUG-002 | Case sensitivity in task_type/status_code across DCMA + API | 2026-03-25 |
| OBS-001 | WBS display showed count only — added WBSStats hierarchy | 2026-03-25 |

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

---

<div align="center">

**MeridianIQ** · MIT License · © 2025 Vitor Maia Rodovalho

</div>
