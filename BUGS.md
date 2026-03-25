# Known Bugs — v0.1

## BUG-001: Milestones not detected in real XER files
- **Status:** OPEN
- **Severity:** HIGH
- **Found:** 2026-03-25 testing with real production XER file
- **Symptom:** Milestones tab shows "No milestones found" for a schedule with many milestones
- **Root Cause (suspected):** Parser/API milestone filter is too narrow. Likely only checks `task_type == "TT_Mile"` but P6 uses case-sensitive values and multiple milestone types
- **P6 Milestone Types to support:**
  - `TT_Mile` — Start Milestone
  - `TT_FinMile` — Finish Milestone
  - `TT_mile` — lowercase variant (P6 version-dependent)
  - `TT_finmile` — lowercase variant
  - Activities with `remain_drtn_hr_cnt == 0` and zero original duration
  - Check actual task_type values in the real XER: run `grep "TT_"` on parsed data
- **Fix location:** `src/api/app.py` (milestones endpoint filter), possibly `src/parser/models.py`
- **Test:** Upload real XER, verify milestones appear
- **Note:** Sample XER generator uses mixed case — real P6 exports may differ

## BUG-002: Case sensitivity in task_type and status_code matching
- **Status:** OPEN (related to BUG-001)
- **Severity:** MEDIUM
- **Description:** P6 XER files from different versions use different case conventions:
  - P6 v8.x: `TT_Task`, `TK_Complete`, `TK_Active`, `TK_NotStart`
  - P6 v19+: `TT_task`, `TK_complete`, `TK_active`, `TK_notstart` (sometimes)
  - Our sample generator uses specific case — real files may not match
- **Fix:** Normalize task_type and status_code to uppercase during parsing, or use case-insensitive comparison in analytics
- **Fix location:** `src/parser/xer_reader.py` (post-processing), all analytics modules

## BUG-003: Calendar-aware duration calculation not implemented
- **Status:** OPEN
- **Severity:** MEDIUM
- **Description:** CPM engine uses raw duration hours divided by 8 (assumed 8hr day). Real P6 schedules have per-calendar work hours (day_hr_cnt, week_hr_cnt) and non-work days. The CPM forward/backward pass should use the assigned calendar for each activity.
- **Fix location:** `src/analytics/cpm.py`
- **Impact:** Duration and float calculations may be slightly off for schedules with non-standard calendars (e.g., 6-day weeks, 10-hour days)

## BUG-004: Frontend types may not match API response shapes
- **Status:** OPEN
- **Severity:** LOW
- **Description:** TypeScript interfaces in `web/src/lib/types.ts` were written to match expected API schemas but actual response key names may differ (e.g., `critical_activity_count` vs `critical_path` array length)
- **Fix:** Run frontend against live backend and fix type mismatches as they surface
- **Fix location:** `web/src/lib/types.ts`, page components

---

## PENDING REAL-WORLD TESTING
- [ ] Overview tab — verify with real XER (activity counts, status distribution)
- [ ] DCMA 14-Point — verify scoring accuracy vs Schedule Validator output
- [ ] Critical Path — verify CP identification (calendar/workday issues possible)
- [ ] Float Distribution — verify bucketing with real float values (P6 stores in hours, need conversion)
- [ ] Compare — test with two consecutive real schedule updates
- [ ] Milestones — verify detection across P6 versions
- [ ] Upload — test with large XER files (1000+ activities)
- [ ] Encoding — test with XER files containing special characters (accents, symbols)
