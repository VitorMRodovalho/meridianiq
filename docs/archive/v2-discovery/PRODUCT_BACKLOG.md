# P6 XER Analytics v2 — Product Backlog

## Vision

Transform reactive, manual construction schedule analysis into proactive, automated, and evolutive schedule intelligence. Instead of discovering problems after the fact (post-mortem), provide real-time validation, scenario analysis, and decision-support dashboards that catch issues as they emerge.

## Source Documents Analyzed

| # | Document | Type | Pages | Key Content |
|---|----------|------|-------|-------------|
| 1 | Exhibit C | Contemporaneous Driving Critical Path SCO (Delay Trend Chart) | 1 | Visual CPA with 4 windows, 6 delay events (A-F), color-coded by type |
| 2 | CDC TIA Findings and Recommendations | Forensic Schedule Analysis by [Forensic Consultant] | 21 | Full CPA, bifurcated analysis, TIA evaluation, entitlement review, window analysis |
| 3 | CDC TIA Summary | Executive Summary Letter by [CM Firm] | 3 | 398 CDs total delay, 264 excusable, 134 non-excusable, 33 already granted |
| 4 | MC NL Horticulture BL03 | Baseline Schedule Review Memo by [CM Firm] | 4 | Milestone tracking, S-curve, PERT probability, float distribution, logic analysis |
| 5 | [Public Project] June 2024 Schedule Review | Monthly Schedule Update Review by [CM Firm] | 5 | EV metrics (SPI/BEI/SRI), float trend, critical path, schedule diagnostic |
| 6 | Schedule Diagnostic | Automated Schedule Validator Analysis | 20 | Quality metrics, activity relationships, critical/near-critical paths, constraints |
| 7 | Schedule Comparison | Schedule Validator Period Comparison | 5 | Changed percentage, activity/relationship/duration changes, float changes |

---

## EPIC 1: XER FILE INGESTION & VALIDATION

### Context
Every analysis starts with receiving an XER file from the contractor. Before any analysis, the file must be validated for completeness and compliance. Currently this is done manually or with Schedule Validator (a paid tool that scored this project at 82/100).

### User Stories

**US-1.1: Schedule Validation Score**
As a scheduler, I want to upload an XER file and see an immediate validation report with a numeric score, so I can reject non-compliant schedules before wasting time analyzing them.
- *Source: Schedule Diagnostic — "Schedule Validation Score: 82 (2024 Scoring Standard)" with green indicator*

**US-1.2: Open-Ended Activities Detection**
As a scheduler, I want to detect activities missing predecessors or successors, because they skew total float and critical path calculations.
- *Source: Schedule Diagnostic — "No Successors: 3 (1%) RED, No Predecessors: 3 (1%) RED, Open Finish: 2 (1%) RED, Open Start: 5 (1%) RED"*
- *Source: June 2024 Review — "Activities with Open Ends: 20 — Can skew total float and critical path" (increased from 0 in baseline)*

**US-1.3: Out-of-Sequence Progress Detection**
As a scheduler, I want to detect activities that started before their predecessors finished (out-of-sequence progress), because they indicate schedule manipulation or poor updates.
- *Source: Schedule Diagnostic — "Out of Sequence: 5 (1%) YELLOW"*
- *Source: June 2024 Review — "Out-of-Sequence: 8 — Can skew critical path" (increased from 0 in baseline)*

**US-1.4: Problematic Relationship Detection**
As a scheduler, I want to flag Start-Finish relationships, Finish-Start+Lag combinations, and negative lags, because they are non-standard practices that hide float.
- *Source: Schedule Diagnostic — "Finish-to-Start Lags: 0 (0%) GREEN, Negative Lags: 0 (0%) GREEN"*
- *Source: BL03 Memo Logic Analysis — "Activities with Finish-Start + Lag: 1 occurrence (Can hide float)", "Activities with Start-Finish: 0", "Negative Lag: 0"*

**US-1.5: Schedule Counts Summary**
As a PM, I want a complete schedule counts summary immediately upon upload.
- *Source: Schedule Diagnostic exact format:*
  - Schedule Dates: Data Date, Schedule Start, Schedule Finish, Must Finish By, % Completed
  - Schedule Counts: Activities (334), Relationships (577), Resources (0), Resource Assignments (0), Project Calendars (5), Linked Calendars (2), Global Calendars (1)
  - Task Type Counts: Finish Milestone 12 (4%), Level of Effort 7 (2%), Milestone 0, Resource 0, Task 315 (94%), WBS Summary 0
  - Activity Status Counts: Not Started 315 (45%), In Progress 19 (3%), Completed 368 (52%)
  - Relationship Type Counts: FS 526 (91%), FF 45 (8%), SS 6 (1%), SF 0 (0%)

**US-1.6: Quality Metrics Dashboard**
As a scheduler, I want a quality metrics dashboard with traffic-light indicators.
- *Source: Schedule Diagnostic Quality Metrics:*
  - Date Constraints: 1 (<1%) GREEN
  - Critical (Longest) Path: 79 (24%) GREEN
  - Near Critical Path: 253 (76%) RED
  - Out of Sequence: 5 (1%) YELLOW
  - Negative Lags: 0 (0%) GREEN
  - Finish-to-Start Lags: 0 (0%) GREEN
  - Long Lags: 1 (<1%) YELLOW
  - High Float: 19 (6%) RED
  - High Duration: 13 (4%) YELLOW
  - Invalid Dates: 0 (0%) GREEN
  - Duplicate Descriptions: 178 (53%) GREEN

**US-1.7: Activity Relationships Quality**
As a scheduler, I want to see activity relationship quality metrics.
- *Source: Schedule Diagnostic Activity Relationships Noted:*
  - Average Logic Ties: 4 YELLOW
  - No Successors: 3 (1%) RED
  - No Predecessors: 3 (1%) RED
  - Open Finish: 2 (1%) RED
  - Open Start: 5 (1%) RED
  - Duplicates Present: 0 (0%) GREEN
  - Riding Data Date: 2 (1%) YELLOW
  - Network Hotspots: 0 (0%) GREEN

**US-1.8: XER Table Completeness Validation**
As a scheduler, I want to validate that the XER contains all required Oracle P6 tables (CALENDAR, PROJECT, PROJWBS, TASK, TASKPRED) and flag missing tables.

### Acceptance Criteria (from real documents)
- Must detect: FS+Lag, SF relationships, open ends, OOS, negative lag, riding data date, network hotspots
- Must count: activities by type (Task, Milestone, LOE, WBS Summary), by status (Not Started, In Progress, Completed)
- Must count: relationships by type (FS, FF, SS, SF)
- Must calculate: Schedule Validation Score with traffic-light indicators
- Must list: all activities on critical path with ID, description, status, and float value
- Must list: all near-critical activities (<20 days float) with float values
- Reference: DCMA 14-Point Assessment, GAO Schedule Assessment Guide

---

## EPIC 2: BASELINE SCHEDULE REVIEW

### Context
When a project starts, the contractor submits a baseline schedule. The CM/PM team reviews it for compliance with contract requirements and general best practices. This is currently a manual 4-page memo (see BL03 Memo).

### User Stories

**US-2.1: Longest Critical Path Narrative**
As a scheduler, I want to automatically identify the Longest Critical Path, listing every activity sequence with durations and key dates.
- *Source: BL03 Memo critical path narrative:*
  - NTP → Mobilization/Site Prep/Abatement/Demo → complete 3/20/23
  - Site Work/Foundation/Slab → complete 6/23/23
  - Exterior Wall Framing → complete 10/19/23
  - Library Interior through MEP → complete 5/29/24
  - Closeout/Punch List/Final Inspection → 7/29/24

**US-2.2: Total Float Distribution**
As a scheduler, I want to see Total Float Distribution with percentages and contract compliance check.
- *Source: BL03 Memo — "Of the overall 571 activities:*
  - *11.2% critical*
  - *7.0% near-critical*
  - *18.2% combined critical and near-critical*
  - *Contract requires ≤25% combined — PASS"*
- Float categories: Critical (0 days), Near-Critical (1-10 days), Moderate (11-20 days), Semi-Moderate (21-44 days), Not Critical (>44 days)

**US-2.3: Duration Probability Analysis (PERT)**
As a scheduler, I want a Constructability/Duration Probability analysis using PERT to assess completion probability.
- *Source: BL03 Memo exact calculations:*
  - Optimistic: 967 days, Most Likely: 1,038 days, Pessimistic: 1,118 days, MEAN: 1,040 days
  - 1σ = 3.67, 2σ = 7.33, 3σ = 11.00
  - 50% (MEAN): 1,039.58 days
  - 68% (1σ): 1,046.91 days
  - 95% (2σ): 1,050.58 days
  - **99.7% (3σ): completion within 574-587 days (6-9% longer than 540-day contract duration)**
  - Equivalent Project Duration: Baseline 967.00 (CP), Optimistic 540 (project), High range 1,050.58/587, Low range 1,028.58/574

**US-2.4: Contractual Milestone Tracking**
As a PM, I want to see Contractual Milestones vs Baseline dates with variance tracking across baseline versions.
- *Source: BL03 Memo exact table format:*
  | Activity ID | Milestone | Contract | BL01 | BL02 | BL03 | Variance |
  |---|---|---|---|---|---|---|
  | PM 1000 | NTP | Feb-06-23 | Feb-06-23 | Feb-06-23 | Feb-06-23 | 0 |
  | PM 1030 | All Submittals | May-07-23 | May-07-23 | Feb-27-23 | Feb-27-23 | 69 |
  | PM 1040 | Slab on Grade | Jul-13-23 | Jul-13-23 | Jul-13-23 | Jul-13-23 | 0 |
  | PM 1050 | Weather Tight | Feb-02-24 | Nov-03-23 | Feb-02-24 | Feb-02-24 | 0 |
  | PM 1060 | Substantial Completion | Jun-30-24 | Aug-20-24 | Jun-17-24 | Jun-18-24 | 12 |
  | PM 1010 | Final Completion | Jul-29-24 | Sep-30-24 | Jul-29-24 | Jul-29-24 | 0 |

**US-2.5: Planned Value S-Curve**
As a PM, I want to see a Planned Value S-Curve based on resource-loaded activities.
- *Source: BL03 Memo — "Contractor's Scheduled Cumulative Revenue" chart showing monthly revenue bars + cumulative S-curve from $209K (Feb-23) through $24.7M (Jul-24)*

**US-2.6: Logic Analysis Report**
As a scheduler, I want a Logic Analysis report detecting problematic scheduling patterns.
- *Source: BL03 Memo Logic Analysis table:*
  | Best Practice | Occurrences | Issue | Action |
  |---|---|---|---|
  | FS + Lag relationships | 1 | Can hide float | Ok |
  | Start-Finish relationships | 0 | Not widely accepted | Ok |
  | Open Ends | 0 | Skew float/CP | OK |
  | Out-of-Sequence | 0 | Skew CP | Ok |
  | Negative Lag | 0 | Better as alternate relationship | Ok |

**US-2.7: Professional Memo Generation**
As a CM, I want a professional memo template auto-generated from the analysis, following the [CM Firm] format: Purpose, Schedule Disposition (Accept/Revise), Executive Summary, Milestone Overview, Budget, S-Curve, Constructability Analysis, Critical Analysis, Logic Analysis, Conclusion.

---

## EPIC 3: MONTHLY SCHEDULE UPDATE REVIEW

### Context
Every month the contractor submits a schedule update. The CM team reviews progress, identifies slippage, and tracks critical path changes. Currently a manual 5-page memo (see June 2024 Review).

### User Stories

**US-3.1: Milestone Variance Tracking**
As a scheduler, I want month-over-month milestone variance tracking.
- *Source: June 2024 Review exact table:*
  | Activity ID | Milestone | Adj. Contract | May-24 | Jun-24 | Var from Contract | Var from Prev Month |
  |---|---|---|---|---|---|---|
  | PM 1000 | NTP | 2/6/2023 | 2/6/2023 | 2/6/2023 | 0 | 0 |
  | PM 1030 | All Submittals | 5/7/2023 | 3/11/2024 | 3/11/2024 | -309 | 0 |
  | PM 1040 | Slab on Grade | 8/21/2023 | 11/16/2023 | 11/16/2023 | -87 | 0 |
  | PM 1050 | Weather Tight | 3/12/2024 | 6/26/2024 | 6/26/2024 | -106 | 0 |
  | PM 1060 | Substantial Completion | 10/17/2024 | 11/4/2024 | 12/11/2024 | -55 | -37 |
  | PM 1010 | Final Completion | 11/16/2024 | 12/17/2024 | 1/23/2025 | -68 | -37 |
- *"Final project completion is 1/23/25 indicating they are 68-days behind"*

**US-3.2: Earned Value Metrics**
As a scheduler, I want Earned Value metrics calculated automatically.
- *Source: June 2024 Review exact values:*
  - Original Contract: $24,604,999.90
  - Change Orders: $113,967.85
  - Current Contract: $24,718,967.75
  - Completed Work: $10,181,000.14
  - Remaining Work: $14,537,967.61
  - % Budget Complete: 41%
  - % Duration Complete: 88%
  - **SPI(v) = $11,662,499.77 / $22,318,515.32 = 0.52** (value-based)
  - Earned Schedule: 12-Dec-23 (Current Earned Date)
  - Schedule Variance: -201 days
  - **SPI(t) = 309 / 510 = 0.61** (time-based)

**US-3.3: Baseline Execution Index (BEI)**
As a scheduler, I want BEI tracking with trend chart.
- *Source: June 2024 Review:*
  - A (Actual Finish): 289
  - B (Planned Finish): 400
  - **BEI = A/B = 0.72 (target ≥0.95)**
  - Trend chart from Jun-23 through Jun-24 showing: 0.15, 0.48, 0.52, 0.59, 0.80, 0.77, 0.79, 0.73, 0.72, 0.88, 0.72, 0.70, 0.72

**US-3.4: Schedule Relevance Index (SRI)**
As a scheduler, I want SRI for both starts and finishes.
- *Source: June 2024 Review:*
  - SRI Finishes: 10 actual / 121 planned = **0.08 (8%)**
  - SRI Starts: 17 actual / 103 planned = **0.17 (17%)**
  - *"These values are significantly low and do not bode well for an on-time finish"*

**US-3.5: Total Float Distribution Trend**
As a scheduler, I want float distribution trend over time showing migration toward critical.
- *Source: June 2024 Review — stacked bar chart from BL02 through Jun-24 showing categories: Critical (red), Near Critical (orange), Moderate (yellow), Medium High (light green), High (green)*
- *"High Float is at 86%. Near-Critical and Critical Float is at 12% — much lower than the 25% best practice"*

**US-3.6: Critical Path Identification**
As a scheduler, I want the current critical path described in phases.
- *Source: June 2024 Review:*
  - Roof Framing through 7/12/2024
  - Exterior Envelope through 7/23/2024
  - Interior Buildout through 10/31/2024
  - MEP through 11/19/2024
  - Final Project Completion 1/23/2025
  - *"Critical path is still driven by the extended duration of Roof Sheathing and Roof Framing"*

**US-3.7: Schedule Diagnostic Integration**
As a scheduler, I want schedule diagnostic and comparison tables embedded in the monthly review.
- *Source: June 2024 Review includes both Logic Analysis and Schedule Diagnostic tables showing changes from baseline to current update*

---

## EPIC 4: SCHEDULE COMPARISON (PERIOD-TO-PERIOD)

### Context
Comparing two consecutive schedule updates reveals what the contractor changed. Currently done with Schedule Validator (see Schedule Comparison PDF).

### User Stories

**US-4.1: Changed Percentage Score**
As a scheduler, I want a single "Changed Percentage" score showing overall schedule volatility.
- *Source: Schedule Comparison — "Changed Percentage: 1" (green indicator) — low is good*

**US-4.2: Activity Changes (Added/Modified/Deleted)**
As a scheduler, I want to see activities added, modified, and deleted between two XER files.
- *Source: Schedule Comparison — "Activities Added/Modified/Deleted: 12/0/0"*
- Added Activities listed with ID, description, status, duration:
  - ACT-2805.8: Revise Headers at Canopy Locations per DSA CCD 024 (NotStart, 5 days)
  - ACT-2805.9: Replacing Discontinuous Headers (Active, 5 days)
  - CDC1-3189.1: Frame Ceilings and Soffits Once Building is Weather Tight (NotStart, 10 days)
  - CDC2-4009.1: Frame Ceilings and Soffits Once Building is Weather Tight (NotStart, 10 days)

**US-4.3: Relationship Changes**
As a scheduler, I want relationship additions, modifications, and deletions tracked.
- *Source: Schedule Comparison — "Relationships Added/Modified/Deleted: 54/0/22"*
- Includes: Changed relationships showing REL A → REL B (e.g., SS0 → FS0), added predecessors with full detail

**US-4.4: Duration Changes**
As a scheduler, I want original duration changes tracked (increased/decreased).
- *Source: Schedule Comparison — 4 duration changes:*
  - ACT-0180: 157 → 147 (Not Start)
  - ACT-0200: 141 → 139 (Not Start)
  - ACT-0870: 220 → 60 (Active) — significant reduction
  - ACT-2499: 5 → 14 (Not Start to Active)

**US-4.5: Actualized Date Changes**
As a scheduler, I want to detect retroactive date changes (dates changed on already-started activities).
- *Source: Schedule Comparison — "Actualized Date Changes (1)": ACT-0870 actual start changed from 02/13/2023 to 06/21/2024*
- This is a critical manipulation indicator

**US-4.6: Float Changes > 20 Days**
As a scheduler, I want to see all activities with float changes greater than 20 days.
- *Source: Schedule Comparison — 14 activities with significant float changes, e.g.:*
  - ACT-0870: 44 → 7 (loss of 37 days float)
  - CDC1-3315: 120 → 46 (loss of 74 days float)
  - Multiple HVAC activities: 86 → 46 (loss of 40 days float)

**US-4.7: Critical Path Changes**
As a scheduler, I want to see activities that left and joined the critical path.
- *Source: Schedule Comparison:*
  - "Activities No Longer Driving the Critical Path (7)" — listed with IDs
  - "Activities Newly Driving the Critical Path (14)" — listed with IDs (in RED)

**US-4.8: Activity Description Changes**
As a scheduler, I want activity description changes flagged.
- *Source: Schedule Comparison — 5 description changes showing original vs new text, e.g.:*
  - ACT-2415: Added "RFI 416 and 439, DSA CCD 024" to description
  - ACT-2499: Added "484,487, 492 and 493 Stair 3 Discrepancies and Submittal Package 241"

**US-4.9: Activity Code Changes**
As a scheduler, I want activity code additions, modifications, and deletions tracked.
- *Source: Schedule Comparison — 4 modified codes, 19 added code assignments, 10 deleted code assignments*

---

## EPIC 5: CONTEMPORANEOUS PERIOD ANALYSIS (CPA)

### Context
The CPA is the core forensic analysis. It tracks delay trends period-by-period, identifying what drove the critical path and whether delays are excusable or non-excusable. This is the most complex and valuable analysis (see Exhibit C and [Forensic Consultant] memo).

### User Stories

**US-5.1: Delay Trend Chart Generation**
As a scheduler, I want to automatically calculate and plot the Substantial Completion Delay Trend across all schedule updates.
- *Source: Exhibit C — the blue line showing completion date sliding from Feb-24 (baseline) to Mar-25 over 16+ months, with specific data points: 27-Feb-24, 1-May-24, 29-May-24, 23-Apr-24, 6-May-24, 8-May-24, 16-Jun-24, 1-Aug-24, 3-Sep-24, 9-Oct-24, 5-Nov-24, 17-Dec-24, 16-Jan-25, 16-Feb-25, 31-Mar-25*
- Orange line = Contract Completion Date (constant)
- Blue line with dots = Record Schedule Completion (moving)

**US-5.2: Contemporaneous Driving Critical Path Scope**
As a scheduler, I want to identify the driving critical path activity for each update period.
- *Source: Exhibit C bottom bar:*
  - Jan-23 to Apr-23: "ASI for HVAC Unit Changes"
  - Apr-23 to Jun-23: "Slab Edge - Formwork"
  - Jun-23 to Jul-23: "Structural Steel Frame and Metal Deck"
  - Aug-23 to Jun-24: "Revisions to Storefront Design"

**US-5.3: Window Analysis with Delay Classification**
As a scheduler, I want to define analysis windows and see time gained/lost per window with delay classification.
- *Source: [Forensic Consultant] Table 5 — Summary of Windows Analysis:*
  | Window | Excusable Non-compensable | Excusable Compensable | Non-excusable |
  |---|---|---|---|
  | 1 | 64 | 28 | 0 |
  | 2 | -8 | -28 | 0 |
  | 3 | 0 | 0 | 15 |
  | 4 | 39 | 0 | 288 |
  | Previous Time Extension | -33 | 0 | 0 |
  | **TOTAL** | **62** | **0** | **303** |

**US-5.4: Bifurcated (Half-Step) Analysis**
As a scheduler, I want to separate progress-driven delays from logic/modification-driven delays.
- *Source: [Forensic Consultant] — "The Bifurcated Analysis is represented by the Black Line (pure progress results), vertical green dotted lines (mitigation from schedule modifications), and vertical red dotted lines (additional delay from schedule modifications)"*
- Per AACE RP 29R-03 FSA 2011 MIPs 3.3 and 3.4

**US-5.5: Delay Event Classification**
As a scheduler, I want each delay event classified into standard categories.
- *Source: Exhibit C legend and delay events:*
  - **Concurrent** (orange): Delay A — 64 CDs, multiple causes (excusable + non-excusable)
  - **Excusable** (red): Delay B — 28 CDs, GC awaiting ASI for HVAC from District
  - **Time Savings** (green): Savings C — +36 CDs, GC progressed slab edge faster
  - **Non-Excusable** (pink): Delay D — 15 CDs, failed to progress structural steel
  - **Concurrent** (orange): Delay E — 39 CDs, 3 causes (non-excusable + excusable + non-excusable)
  - **Non-Excusable** (pink): Delay F — 288 CDs, failed to produce acceptable storefront submittal
- *Source: Exhibit C totals: Non-compensable TE = 62 days, Non-excusable = 303 days, Compensable TE = 0 days*

**US-5.6: Window Driving Activities Table**
As a scheduler, I want detailed driving activities per window period.
- *Source: [Forensic Consultant] Tables 1-4 with columns: Schedule File, Schedule Update, Data Date, Record Schedule Completion, Update Delay, Cumulative Delay, Half Step, Mitigation, Cumulative Mitigation, CP Driving Activity ID, Critical Path Driving Activity Name*

---

## EPIC 6: TIME IMPACT ANALYSIS (TIA) SUPPORT

### Context
TIAs are the formal mechanism for time extensions. The contractor submits a TIA with a fragnet showing the delay. The CM reviews for AACE RP 29R-03 compliance. This is the most contentious deliverable.

### User Stories

**US-6.1: Pre-Impact Schedule Validation**
As a scheduler, I want to validate that a TIA uses the correct pre-impact schedule (contemporaneous update, not baseline).
- *Source: [Forensic Consultant] — "[General Contractor] should have selected the July 2023 schedule update instead of the baseline schedule. The baseline is 6 months earlier than the July 2023 schedule. [General Contractor] also submitted five schedule updates before the issue allegedly driving the critical path."*
- *FSA 2011: "Select the as-planned network... If not using the baseline, select the contemporaneous update that existed just prior to the initial delay that is to be evaluated."*

**US-6.2: Fragnet Quality Assessment**
As a scheduler, I want to identify TIA fragnets that use lump-sum durations instead of detailed activity sequences.
- *Source: [Forensic Consultant] — "Only one lump sum duration activity ACT-0642 instead of 48 detailed activities" for TIA 09.4, and "one hammock activity ACT-0448 instead of the detailed activities" for TIA 05.3*

**US-6.3: Timeline Gap Detection**
As a scheduler, I want to detect gaps in TIA timelines where the contractor was responsible for the next action.
- *Source: [Forensic Consultant] TIA 09.4 — 121 days of gaps across 8 instances:*
  - Gap of 24 days after AOR review of Submittal-095
  - Gap of 42 days after AOR review of RFI-040
  - Gap of 5 days after AOR review of Submittal-095.2
  - Gap of 10 days after AOR review of RFI-135
  - Gap of 11 days after AOR review of RFI-169
  - Gap of 4 days after AOR review of Submittal-095.5
  - Gap of 7 days after AOR review of Submittal-095.6
  - Gap of 18 days after AOR review of Submittal-095.7
- *Source: [Forensic Consultant] TIA 05.3 — 64 days of gaps:*
  - Gap of 41 days after AOR review of Submittal-070.1
  - Gap of 23 days after approval to release heat pump

**US-6.4: TIA Overlap and Concurrency Detection**
As a scheduler, I want to track overlaps between multiple TIAs.
- *Source: TIA Summary Figure 1:*
  - TIA 05.3 overlaps with TIAs 6, 7, & 8
  - TIAs 05.3 & 09.4 overlap each other
  - TIA 09.4 overlaps with TIAs 10, 11, 14, & 18
  - TIA #3, 4, 12, 13, 15, 16, 17 — impact activities not on the longest path

**US-6.5: TIA Summary Timeline**
As a PM, I want a visual timeline showing all submitted TIAs with their claimed delay days and overlaps.
- *Source: TIA Summary Figure 1 — 18 TIAs plotted on timeline from Jan-2023 to Sep-2025 showing fragnet durations, overlaps, and total delay quantification*

**US-6.6: Independent TIA Modeling**
As a scheduler, I want to independently model a TIA using the correct pre-impact schedule and compare results.
- *Source: [Forensic Consultant] independently modeled TIA 09.4 — "new forecasted Substantial Completion date is March 24, 2025, or a 15 CD improvement" compared to contractor's submission of March 31, 2025*

---

## EPIC 7: CONTRACT COMPLIANCE MONITORING

### Context
Delay entitlement depends on strict adherence to contract notification requirements. Contractors often lose entitlement by missing deadlines.

### User Stories

**US-7.1: Notice of Delay (NOD) Tracking**
As a PM, I want to track NOD submission dates against the contractual requirement.
- *Source: [Forensic Consultant] Table 6 and contract Article 16.2.1: "Contractor shall, within five (5) calendar days of beginning of any delay, notify District in writing"*
- *Actual NOD timing from Table 6:*
  | TIA | NOD | Days Claimed | NOD Late By | Entitlement |
  |---|---|---|---|---|
  | TIA-06 | NOD-02 | 15 | 39 days late | Not maintained |
  | TIA-07 | NOD-07 | 27 | 15 days late | Not maintained |
  | TIA-10 | NOD-09 | 134 | 28 days late | Not maintained |
  | TIA-14 | None | 134 | No NOD submitted | Not maintained |
  | TIA-18 | NOD-13 | 6 | 167 days late | Not maintained |

**US-7.2: PCO Submission Tracking**
As a PM, I want to track PCO submission timing against the contractual requirement.
- *Source: Contract Article 17.7.5: "Contractor shall submit its PCO within five (5) working days... if Contractor fails to submit its PCO within this timeframe, the contractor waives any entitlement"*

**US-7.3: Recovery Schedule Tracking**
As a PM, I want to track recovery schedule submissions against the 20-day requirement.
- *Source: Contract Article 16.2.3.3: "A recovery schedule must be submitted within twenty (20) calendar days"*
- *[Forensic Consultant]: "[Forensic Consultant] has not received any recovery schedule files pertaining to any of the TIAs"*

**US-7.4: Entitlement Status Dashboard**
As a PM, I want a dashboard showing entitlement status for each TIA.
- *Source: [Forensic Consultant] evaluation — All 5 additional TIAs (06, 07, 10, 14, 18) had entitlement waived due to: late NODs, wrong pre-impact schedule, no recovery schedule submitted*

---

## EPIC 8: PROACTIVE SCHEDULE INTELLIGENCE (THE DIFFERENTIATOR)

### Context
Everything above is REACTIVE — analyzing what already happened. The v2 tool's differentiator is PROACTIVE intelligence: catching problems before they become claims.

### User Stories

**US-8.1: Critical Path Change Alerts**
As a PM, I want automated alerts when the critical path changes between updates, with root cause analysis.
- *Source: Schedule Comparison — "Activities No Longer Driving Critical Path (7)" and "Activities Newly Driving Critical Path (14)" — this should trigger an alert*

**US-8.2: Float Erosion Alerts**
As a PM, I want float erosion alerts when activities' float trends toward zero.
- *Source: Schedule Comparison — 14 activities with float changes >20 days, e.g., ACT-1-3315 went from 120 to 46 days float*

**US-8.3: Progress Velocity Tracking**
As a PM, I want to know if remaining duration is decreasing slower than time is passing.
- *Source: BEI trend showing: 0.15 → 0.48 → 0.72 over 13 months (never reaching 0.95 target)*

**US-8.4: Scenario Modeling**
As a PM, I want "what if" scenario modeling showing cascade effects on milestones.

**US-8.5: Contractor Performance Scoring**
As a PM, I want a monthly contractor performance score combining BEI, SRI, SPI, and completion probability.
- *Source: June 2024 Review — BEI=0.72, SRI(finish)=0.08, SRI(start)=0.17, SPI(v)=0.52, SPI(t)=0.61 — all below targets*

**US-8.6: Schedule Manipulation Detection**
As a PM, I want automated detection of: retroactive date changes, unjustified relationship changes, duration padding, lump-sum fragnet activities.
- *Source: Schedule Comparison — ACT-0870 actual start changed retroactively from 02/13/2023 to 06/21/2024*
- *Source: [Forensic Consultant] — contractor used single lump-sum activity instead of 48 detailed activities*

**US-8.7: Time Extension Calculator**
As a PM, I want automatic computation of entitled days based on CPA results and contract rules.
- *Source: [Forensic Consultant] calculation: 64 (Delay A) + 28 (Delay B) - 15 (Delay D) - 33 (prior CO4) = 23 days non-compensable TE entitled*

---

## EPIC 9: SUBMITTAL & RFI TRACKING INTEGRATION

### Context
Submittal/RFI timelines are critical to TIA evaluation. Gaps in re-submissions were the key evidence (121 days of gaps for TIA 09.4).

### User Stories

**US-9.1: Submittal Log Import**
As a PM, I want to import submittal logs and map them to schedule activities.

**US-9.2: Submittal Cycle Time Tracking**
As a PM, I want to track submittal cycle times and flag abnormal gaps.
- *Source: [Forensic Consultant] TIA 09.4 Timeline — 8 re-submissions of Submittal #095 from 1/20/2023 to 6/24/2024, with gaps of 4-42 days between actions*

**US-9.3: RFI Response Time Tracking**
As a PM, I want RFI response time tracking with overdue alerts.

**US-9.4: Combined Timeline View**
As a PM, I want schedule activities + submittals + RFIs + NODs + PCOs on the same timeline axis.
- *Source: [Forensic Consultant] Figure 4 — TIA 09.4 Timeline of Events showing 50+ activities, submittals, RFIs, and gaps on a Gantt-style view*

---

## EPIC 10: REPORTING & VISUALIZATION

### User Stories

**US-10.1**: Generate Delay Trend Charts (like Exhibit C) with color-coded delay bars and annotations
**US-10.2**: Generate professional memo templates ([CM Firm] format) with auto-populated data
**US-10.3**: Generate TIA Summary timelines (like [Forensic Consultant] Figure 1) showing all TIAs with overlaps
**US-10.4**: Generate S-Curve / Earned Value charts with planned vs actual vs earned
**US-10.5**: Export to PDF, Excel, and interactive web dashboards
**US-10.6**: Generate Schedule Diagnostic reports (like Schedule Validator format)
**US-10.7**: Generate Schedule Comparison reports (like Schedule Validator format)
**US-10.8**: Generate CPA window tables (like [Forensic Consultant] Tables 1-5)
**US-10.9**: Generate Entitlement tracking tables (like [Forensic Consultant] Table 6)

---

## INDUSTRY STANDARDS & REFERENCES

| Standard | Application |
|----------|------------|
| AACE RP 29R-03 | Forensic Schedule Analysis (2011) — MIPs 3.3/3.4 for CPA and Bifurcated Analysis |
| DCMA 14-Point Assessment | Schedule health metrics and quality scoring |
| GAO Schedule Assessment Guide | Federal project schedule best practices |
| Oracle P6 XER Format | [XER Import/Export Data Map](https://docs.oracle.com/cd/F51303_01/English/Mapping_and_Schema/xer_import_export_data_map_project/index.htm) |
| AIA/AGC Contract Templates | Notification requirements (NOD 5 CD, PCO 5 WD, Recovery 20 CD) |
| CSI MasterFormat | Division specifications for submittal tracking |
| Schedule Validator | Benchmark for automated diagnostic scoring (www.ScheduleValidator.com) |

---

## PERSONAS

| Persona | Role | Primary Epics | Key Needs |
|---------|------|---------------|-----------|
| **Project Scheduler** (PSP certified) | Performs forensic analysis, CPAs, TIA reviews, diagnostics | 1-6, 8 | Accuracy, AACE compliance, defensible analysis |
| **Construction Manager (CM)** | Reviews scheduler's analysis, makes recommendations | 2-3, 5-7 | Clear narratives, professional memos, entitlement clarity |
| **Project Manager (PM)** | High-level dashboards, milestone tracking, decisions | 3, 7-8 | Executive summaries, proactive alerts, performance scores |
| **Owner Representative** | Executive summaries, entitlement tracking, cost impact | 6-7 | Risk visibility, compliance dashboards, claim defense |
| **GC Scheduler** | Prepares compliant TIA submissions | 1-2, 6 | Validation before submission, correct methodology guidance |

---

## NON-FUNCTIONAL REQUIREMENTS

- Must parse XER files without requiring Oracle P6 installation
- Must handle multi-project XER files (composite keys: proj_id.task_id)
- Must support schedules with 1000+ activities (reference: 334 activities, 577 relationships in source project)
- Must run on web (no desktop installation required)
- Must support concurrent multi-user access
- Must maintain audit trail of all analyses (litigation-sensitive data)
- Data must be stored securely (attorney work product privilege applies)
- Must support AACE RP 29R-03 methodology references
- Response time: schedule upload + validation < 30 seconds for 500-activity schedules
- Must preserve original XER data immutably (no modification of source files)

---

## BACKLOG PRIORITY

| Priority | Epic | Rationale | Complexity |
|----------|------|-----------|------------|
| **P1** | Epic 1: XER Ingestion & Validation | Foundation — everything depends on this | Medium |
| **P1** | Epic 4: Schedule Comparison | Quick win — high value, builds on existing v1-compare | Medium |
| **P2** | Epic 2: Baseline Review | Essential for project setup phase | Medium-High |
| **P2** | Epic 3: Monthly Update Review | Most frequent use case (monthly cadence) | High |
| **P3** | Epic 5: CPA | Highest analytical value but most complex | Very High |
| **P3** | Epic 6: TIA Support | Highest revenue potential (claims consulting) | Very High |
| **P3** | Epic 7: Contract Compliance | Differentiator for CM firms | Medium |
| **P4** | Epic 8: Proactive Intelligence | The vision — builds on all other epics | High |
| **P4** | Epic 9: Submittal/RFI Integration | Requires external data import | Medium |
| **P5** | Epic 10: Reporting | Evolves continuously alongside features | Ongoing |

---

## METRICS EXTRACTED FROM REAL DOCUMENTS

These exact numbers serve as test data and acceptance criteria benchmarks:

| Metric | Value | Source |
|--------|-------|--------|
| Total project delay | 398 calendar days | TIA Summary |
| Excusable delay days | 264 | TIA Summary |
| Non-excusable delay days | 134 | TIA Summary |
| Compensable delay days | 28 | [Forensic Consultant] Table 5 |
| Non-compensable TE entitled | 62 days (231 after offset) | TIA Summary |
| Previously granted TE | 33 days (CO4) | TIA Summary |
| Schedule Validation Score | 82/100 | Schedule Diagnostic |
| Activities on Critical Path | 79 (24%) | Schedule Diagnostic |
| Near-Critical Activities | 253 (76%) | Schedule Diagnostic |
| BEI at June 2024 | 0.72 (target ≥0.95) | June 2024 Review |
| SPI(v) at June 2024 | 0.52 | June 2024 Review |
| SPI(t) at June 2024 | 0.61 | June 2024 Review |
| Schedule Variance | -201 days | June 2024 Review |
| Earned Schedule Date | 12-Dec-2023 | June 2024 Review |
| SRI (finishes) | 0.08 (8%) | June 2024 Review |
| SRI (starts) | 0.17 (17%) | June 2024 Review |
| PERT 99.7% probability | 574-587 days (vs 540 contract) | BL03 Memo |
| Baseline critical+near-critical | 18.2% (contract limit: 25%) | BL03 Memo |
| TIA 09.4 timeline gaps | 121 days | [Forensic Consultant] |
| TIA 05.3 timeline gaps | 64 days | [Forensic Consultant] |
| Changed Percentage (comparison) | 1 | Schedule Comparison |
| Activities Added (comparison) | 12 | Schedule Comparison |
| Relationships Added (comparison) | 54 | Schedule Comparison |
| Float changes >20 days | 14 activities | Schedule Comparison |

---

*This is a DISCOVERY document. No technology decisions yet. No code. Just the map of what the product needs to do, grounded in real-world deliverables that construction PMs and schedulers produce manually today.*
