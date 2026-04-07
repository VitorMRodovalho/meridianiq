# Schedule Submission Standards — Industry Reference

Comprehensive research for MeridianIQ Schedule Viewer column requirements.
Sources: AACE RP 29R-03, DCMA 14-Point, AIA G703, USACE UFGS, SCL Protocol, DOT specs.

## MUST-HAVE Columns (22 fields — required by virtually all standards)

| # | Field | Source | MeridianIQ Status |
|---|-------|--------|-------------------|
| 1 | Activity ID | All | Done (task_code) |
| 2 | Activity Name | All | Done (task_name) |
| 3 | WBS Code | DCMA, USACE, CM | Done (table + tree) |
| 4 | Original Duration | DCMA, AACE, DOT | Done (duration_days) |
| 5 | Remaining Duration | DCMA, AACE, USACE | Done (remaining_days) |
| 6 | Actual Start | All | Done (AS column) |
| 7 | Actual Finish | All | Done (AF column) |
| 8 | Early Start | DCMA, AACE, DOT | Done (ES column) |
| 9 | Early Finish | DCMA, AACE, DOT | Done (EF column) |
| 10 | Total Float | All | Done (TF column) |
| 11 | % Complete | DCMA, DOT, CM | Done (progress_pct) |
| 12 | Predecessors/Successors | DCMA, AACE | Done (detail panel) |
| 13 | Relationship Type (FS/FF/SS/SF) | DCMA (90% FS rule) | Done (dependency lines) |
| 14 | Calendar | DCMA, AACE, DOT | Done (detail panel) |
| 15 | Constraint Type | DCMA | Done (badge + detail) |
| 16 | Constraint Date | DCMA | Done (detail panel) |
| 17 | Critical Path Flag | All | Done (toggle + badge) |
| 18 | Baseline Start | DCMA (BEI), CM | Done (with baseline) |
| 19 | Baseline Finish | DCMA (BEI), CM | Done (with baseline) |
| 20 | Data Date | All | Done (marker line) |
| 21 | Forecast Completion Date | All | Done (project_finish) |
| 22 | Contractual Completion Date | CM, SCL | Not tracked (needs DB field) |

**Score: 21/22 MUST-HAVE implemented (95.5%)**

## SHOULD-HAVE Columns (11 fields)

| # | Field | Source | MeridianIQ Status |
|---|-------|--------|-------------------|
| 23 | Late Start | CPM, AACE | Done (LS) |
| 24 | Late Finish | CPM, AACE | Done (LF) |
| 25 | Free Float | DOT, CM | Done (FF column) |
| 26 | Physical % Complete | DOT, USACE | Done (same as progress_pct) |
| 27 | Responsibility Code | USACE, CM | Not available |
| 28 | Activity Code(s) | USACE, CM | Available in parser, not shown |
| 29 | Lag Value | DCMA | Done (detail panel) |
| 30 | Milestone Flag | All | Done (diamond shape) |
| 31 | Start Variance (BL vs Current) | CM | Done (start_variance_days) |
| 32 | Finish Variance (BL vs Current) | CM | Done (finish_variance_days) |
| 33 | At Completion Duration | DOT | Not computed |

**Score: 9/11 SHOULD-HAVE implemented (81.8%)**

## NICE-TO-HAVE (Cost/EVM context — 9 fields)

| # | Field | Source | MeridianIQ Status |
|---|-------|--------|-------------------|
| 34 | Budgeted Total Cost | USACE, AIA | Available (target_cost) |
| 35 | Actual Total Cost | USACE, EVM | Available (act_reg_cost) |
| 36 | Remaining Total Cost | USACE, EVM | Available (remain_cost) |
| 37 | Earned Value | USACE, DCMA | Computed in EVM engine |
| 38 | Planned Value | USACE, DCMA | Computed in EVM engine |
| 39 | CPI | EVM | Computed in EVM engine |
| 40 | SPI | EVM | Computed in EVM engine |
| 41 | Resource Assignment | DCMA (100%) | Available in parser |
| 42 | Resource Hours/Units | EVM | Available in parser |

## Summary Metrics Required

| Metric | Source | MeridianIQ Status |
|--------|--------|-------------------|
| Overall % Complete (planned vs actual) | All | Done (progress bar) |
| Days Ahead/Behind Schedule | CM | Done (variance) |
| Projected Completion Date | All | Done (project_finish) |
| TF on Completion Milestone | AACE, DCMA | Computable |
| CPLI | DCMA | Not computed |
| BEI | DCMA | Not computed |
| Critical Activity Count | CM | Done (summary card) |
| Near-Critical Count (TF 1-10) | CM | Not shown |
| DCMA 14-Point Summary | DCMA | Done (separate page) |
| Milestones Variance Table | CM, SCL | Done (detail panel) |
| Added/Deleted Activities | CM | Done (compare page) |
| Logic Changes Count | CM | Done (compare page) |

## Visual Format Requirements

| Element | Source | MeridianIQ Status |
|---------|--------|-------------------|
| Gantt bars (early dates) | All | Done |
| Critical path red | DOT, CM | Done |
| Baseline bars alongside | CM | Done |
| Data date vertical line | All | Done |
| Today line | CM | Done |
| Milestone diamonds | All | Done |
| WBS grouping | DOT, CM | Done (tree) |
| Sort by start within groups | DOT | Done |
| Title block (project, contract, data date) | DOT, CM | Partial (name + data date) |
| Relationship lines | P6 | Done |
| Float bars | Industry | Done |
| Progress fill on bars | Industry | Done |

## Monthly Narrative Report Sections (CM Practice)

Per DOT specs, USACE, and CM industry practice:
1. Executive Summary (ahead/behind, planned vs actual %, projected vs contractual) — **Done** (scorecard, exec summary PDF)
2. Critical Path Analysis (longest path, near-critical) — **Done** (CP toggle, float trends)
3. Progress This Period — **Done** (compare page, forensic)
4. Upcoming Work (look-ahead) — **Done** (lookahead page)
5. Milestone Status — **Done** (milestones page)
6. Schedule Changes — **Done** (compare page)
7. Delays and Recovery — **Done** (forensic, TIA, delay attribution)
8. Resource/Manpower Summary — Partial (resource leveling)
9. Weather Days — Not tracked

## Sources

- AACE RP 29R-03 — Forensic Schedule Analysis (Section 5.3 Documentation)
- DCMA 14-Point Assessment — Schedule quality metrics
- AIA A201/G703 — General Conditions / Certificate for Payment
- USACE UFGS 01 32 01 — Project Schedule specification
- USACE ER 1-1-11 — SDEF Format
- SCDOT, NYSDOT, MnDOT — State DOT schedule specifications
- SCL Delay and Disruption Protocol, 2nd Ed. (Appendix B — Records)
- GAO Schedule Assessment Guide (2020)
- PMI Practice Standard for Scheduling
- FAR 52.236-15 — Federal schedules for construction
