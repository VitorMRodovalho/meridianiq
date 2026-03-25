# Known Bugs — v0.1.0

## BUG-001: Milestones not detected in real XER files
- **Status:** FIXED (2026-03-25)
- **Severity:** HIGH
- **Root Cause:** Milestone filter in `src/api/app.py` used case-sensitive matching (`"TT_mile", "TT_finmile"`). P6 versions export task_type values in varying case (`TT_Mile`, `TT_mile`, `TT_FinMile`, `TT_finmile`).
- **Fix:** Changed to case-insensitive comparison using `.lower()` against a set of lowercase milestone types.
- **Files changed:** `src/api/app.py` (milestones endpoint)
- **Verified:** Sample XER now returns 5 milestones (3 TT_mile + 2 TT_finmile)

## BUG-002: Case sensitivity in task_type and status_code matching
- **Status:** FIXED (2026-03-25)
- **Severity:** MEDIUM
- **Root Cause:** Multiple locations in DCMA analyzer and API endpoints used case-sensitive string comparisons for task_type and status_code values.
- **Fix:** Applied `.lower()` normalization across all comparisons in:
  - `src/analytics/dcma14.py` — incomplete/countable filters, missed tasks, BEI, resource check
  - `src/api/app.py` — float distribution filter, milestones filter
- **Verified:** All 14 DCMA checks work correctly regardless of P6 version case conventions

## BUG-003: Calendar-aware duration calculation not implemented
- **Status:** OPEN
- **Severity:** MEDIUM
- **Description:** CPM engine uses raw duration hours divided by 8 (assumed 8hr day). Real P6 schedules have per-calendar work hours (day_hr_cnt, week_hr_cnt) and non-work days. The CPM forward/backward pass should use the assigned calendar for each activity.
- **Fix location:** `src/analytics/cpm.py`
- **Impact:** Duration and float calculations may be slightly off for schedules with non-standard calendars (e.g., 6-day weeks, 10-hour days)

## BUG-004: Frontend types may not match API response shapes
- **Status:** OPEN
- **Severity:** LOW
- **Description:** TypeScript interfaces in `web/src/lib/types.ts` were written to match expected API schemas but actual response key names may differ. New `wbs_stats` field added to ProjectDetailResponse needs frontend type update.
- **Fix:** Run frontend against live backend and fix type mismatches as they surface
- **Fix location:** `web/src/lib/types.ts`, page components

## BUG-005: DCMA Pass/Fail Logic for Zero-Threshold Checks
- **Status:** VERIFIED NOT A BUG (2026-03-25)
- **Severity:** N/A
- **Description:** Reported that Leads=0% and Invalid Dates=0% showed FAIL. Investigation found the source code already used `<=` for "lower is better" checks, which correctly evaluates `0.0 <= 0.0 = True (PASS)`. The issue was likely in the frontend rendering, not the backend logic.
- **Verified:** Backend correctly returns `passed: true` for Leads=0.0% and Invalid Dates=0.0%

## OBS-001: WBS Elements Display Enhancement
- **Status:** FIXED (2026-03-25)
- **Severity:** MEDIUM (enhancement)
- **Description:** Overview tab showed only "WBS Elements: 4" — just the total count. Real schedules have deep WBS hierarchies (5-7 levels) and need richer analysis.
- **Fix:** Added `WBSStats` schema and `_compute_wbs_stats()` function to project detail endpoint. Now returns: total elements, max depth, count by level, avg/min/max activities per WBS node, WBS nodes with no activities.
- **Files changed:** `src/api/schemas.py` (added WBSStats, WBSLevelCount), `src/api/app.py` (added _compute_wbs_stats, updated project detail endpoint)
- **Verified:** Sample XER returns: 10 elements, 3 levels, avg 3.0 activities/WBS

---

## PENDING REAL-WORLD TESTING
- [ ] Overview tab — verify with real XER (activity counts, status distribution)
- [ ] DCMA 14-Point — verify scoring accuracy vs Schedule Validator output
- [ ] Critical Path — verify CP identification (calendar/workday issues possible)
- [ ] Float Distribution — verify bucketing with real float values (P6 stores in hours, need conversion)
- [ ] Compare — test with two consecutive real schedule updates
- [x] Milestones — fixed case-insensitive detection (BUG-001)
- [ ] Upload — test with large XER files (1000+ activities)
- [ ] Encoding — test with XER files containing special characters (accents, symbols)
- [ ] WBS Stats — verify hierarchy depth calculation with real deep WBS
