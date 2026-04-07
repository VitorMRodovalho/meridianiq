# Schedule Submission Standards — Industry Reference

Research for MeridianIQ Schedule Viewer column requirements.

## MUST-HAVE Columns (Required by DCMA, AACE, AIA)

These columns are required in virtually every professional schedule submission:

| # | Column | Field | Our Status |
|---|--------|-------|-----------|
| 1 | Activity ID | task_code | Done |
| 2 | Activity Name | task_name | Done |
| 3 | WBS | wbs_path | Done (table + tree) |
| 4 | Original Duration | target_drtn_hr_cnt / day_hours | Done (duration_days) |
| 5 | Remaining Duration | remain_drtn_hr_cnt / day_hours | Done (remaining_days) |
| 6 | % Complete | phys_complete_pct | Done (progress_pct) |
| 7 | Early Start | early_start_date | Done |
| 8 | Early Finish | early_end_date | Done |
| 9 | Late Start | late_start_date | Done |
| 10 | Late Finish | late_end_date | Done |
| 11 | Total Float | total_float_hr_cnt / day_hours | Done |
| 12 | Free Float | free_float_hr_cnt / day_hours | Done |
| 13 | Actual Start | act_start_date | Done |
| 14 | Actual Finish | act_end_date | Done |
| 15 | Calendar | clndr_id | Done (detail panel) |
| 16 | Activity Status | status_code | Done |
| 17 | Activity Type | task_type | Done |
| 18 | Constraint Type | cstr_type | Done (badge + detail) |
| 19 | Constraint Date | cstr_date | Done (detail panel) |
| 20 | Critical Path indicator | is_critical | Done |

## SHOULD-HAVE (Professional Quality)

| # | Column | Field | Our Status |
|---|--------|-------|-----------|
| 21 | Predecessor List | relationships | Done (detail panel only) |
| 22 | Successor List | relationships | Done (detail panel only) |
| 23 | Baseline Start | baseline_start | Done (with baseline) |
| 24 | Baseline Finish | baseline_finish | Done (with baseline) |
| 25 | Start Variance (days) | early_start - baseline_start | Not computed |
| 26 | Finish Variance (days) | early_finish - baseline_finish | Not computed |
| 27 | Float Variance (days) | current_TF - baseline_TF | Not computed |
| 28 | Resource Assignments | task_resources | Not in viewer |
| 29 | Budget Cost | target_cost | Not in viewer |
| 30 | Actual Cost | act_reg_cost | Not in viewer |

## NICE-TO-HAVE (Enhanced Reporting)

| # | Column | Our Status |
|---|--------|-----------|
| 31 | Complete % Type (Duration/Physical/Units) | Available in data |
| 32 | Duration Type | Available in data |
| 33 | Float Path | Available in data |
| 34 | Driving Path Flag | Available in data |
| 35 | Priority Type | Available in data |
| 36 | Resource Units (Budget/Actual/Remaining) | Available in data |

## Summary Metrics Required

Per AACE RP 29R-03 and DCMA 14-Point:
- Total Activities, Relationships, Calendars count (Done - summary cards)
- Activity status distribution (Done - status pills)
- Relationship type distribution (Not shown)
- Critical path length and activities (Done - critical count + toggle)
- Float distribution histogram (Done - collapsible)
- Negative float count (Done - summary card)
- Milestone count (Done - summary card)
- Schedule completion % (Done - progress bar)

## Visual Requirements

Per industry practice:
- **Gantt bars** with status coloring ✓
- **Baseline bars** below current bars ✓
- **Progress fill** on activity bars ✓
- **Milestone diamonds** ✓
- **Data date vertical line** ✓
- **Today line** ✓
- **Dependency lines** (FS/FF/SS/SF) ✓
- **Float bars** (early finish → late finish) ✓
- **Critical path highlighting** ✓
- **WBS hierarchy** with collapse/expand ✓
- **Constraint indicators** ✓

## PDF Report Format (AACE RP 29R-03 S5.3)

A forensic schedule report should include:
1. Cover page with project identification
2. Table of contents
3. Executive summary
4. Methodology statement citing applicable standards
5. Data summary (schedule metadata, activity counts)
6. Analysis results (tables with findings)
7. Schedule printout (Gantt chart with standard columns)
8. Conclusions and recommendations
9. Appendices (data tables, detailed calculations)

## Sources

- AACE Recommended Practice 29R-03 — Forensic Schedule Analysis
- DCMA 14-Point Assessment — Schedule Quality Metrics
- AIA A201/G703 — General Conditions / Certificate for Payment
- SCL Delay and Disruption Protocol, 2nd Edition
- GAO Schedule Assessment Guide (2020)
- PMI Practice Standard for Scheduling (3rd Edition)
