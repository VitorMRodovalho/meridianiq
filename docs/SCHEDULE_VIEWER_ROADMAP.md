# Schedule Viewer Roadmap

## Current State (v3.6.0-dev)

Production-grade Gantt implementation: SVG-based, zero dependencies, dark-mode compatible, virtualized for 10K+ activities. Waves 1–6 and most of Wave 8 have shipped; Wave 7 (resource/cost) is partially delivered and is the main open workstream.

## Completed Waves

### Waves 1–4 (v3.2.0)
Collapsible WBS tree, SVG Gantt bars with status coloring, progress overlay, milestone diamonds, date axis (day/week/month zoom), baseline bars, float bars, sliding-right indicators, negative-float indicators, SVG bezier dependencies (FS/FF/SS/SF), critical-path filter, detail panel, tooltip, KPI cards.

### Wave 5 — Standard Columns + Bug Fixes (v3.3.0)
- WBS level names: full hierarchical path in tooltip, numeric-only codes filtered.
- Date axis: min 48 px spacing, adaptive label format — no overlap at day zoom.
- Dependency routing: collapsed rows excluded from index via virtual scrolling.
- 23 standard columns delivered (Activity ID/Name, OD/RD, % Complete, ES/EF/LS/LF, TF/FF, AS/AF, BL Start/Finish, Var, Constraint, Calendar). Column configuration panel with show/hide.

### Wave 6 — Advanced Interactions (v3.5.0)
- Drag-to-pan (both axes).
- Sticky left columns in activity table.
- WBS path dropdown filter.
- Weekend / holiday shading (calendar exceptions).
- Virtual scrolling across GanttCanvas + WBSTree + activity table.

### Wave 8 — Print & Export (v3.5.0, partial)
- PDF export via print dialog with full SVG (done).
- PNG/SVG image export (pending).
- Excel export with formatting (pending — basic Excel export exists via `src/api/routers/exports.py` but not Gantt-styled).
- Print preview with page breaks per WBS section (pending).

### v3.6.0-dev — Stability + EVM Integration
- Gantt stability refactor — removed re-render flicker, consolidated event wiring.
- `schedule_view` cache — projects + baselines memoized per session.
- EVM S-Curve chart (chart component #11) — schedule + cost S-curve overlay with forecast scenarios, usable standalone and alongside the Gantt.

## Standard Columns — Reference Status

Per AIA G703/G702 and AACE RP 29R-03 Schedule Submission requirements:

| Column | Status |
|--------|--------|
| Activity ID (Code) | ✅ |
| Activity Name | ✅ |
| WBS (column) | ✅ v3.3 |
| Original Duration | ✅ |
| Remaining Duration | ✅ v3.3 |
| % Complete | ✅ |
| Early Start / Early Finish | ✅ |
| Late Start / Late Finish | ✅ v3.3 |
| Total Float | ✅ |
| Free Float | ✅ v3.3 |
| Actual Start / Actual Finish | ✅ v3.3 |
| Baseline Start / Baseline Finish | ✅ |
| Start Variance / Finish Variance | ✅ v3.5 |
| Calendar | ✅ v3.5 |
| Constraint Type / Constraint Date | ✅ v3.5 |
| Predecessor List | Detail panel only (P3 for table) |
| Successor List | Detail panel only (P3 for table) |
| Resource Assignments | ❌ open (Wave 7) |
| Budget Cost | ❌ open (Wave 7) |

## Open — Next Targets (v3.7 candidates)

### Wave 7 — Resource & Cost Integration (Primary open wave)
- Resource histogram below Gantt (demand vs capacity) — engine exists (`src/analytics/resource_leveling.py`), UI missing.
- Cost-loading curve overlay on timeline (engine partial via EVM S-Curve; needs per-activity weight).
- Budget vs actual cost per activity (needs CBS persistence, also a v3.7 P1 item).
- Resource-constrained critical path highlighting.

### Wave 8 — Export Completion
- PNG/SVG raster export.
- Excel export with Gantt styling (not just tabular).
- Print preview with explicit page breaks per WBS section.

### Research — Submission Formats (v4.0 candidate)
- AIA G703 — Application and Certificate for Payment (schedule attachment).
- AACE RP 29R-03 §5.3 — Forensic Schedule Report documentation.
- DCMA Schedule Submission Format — government contract columns.
- Owner's Rep Monthly Update format (baseline vs current vs forecast).
- SCL Protocol Appendix C — claims presentation format.

These define what a professional schedule submission must include. Exporting in these formats would close the last claim-handoff gap.
