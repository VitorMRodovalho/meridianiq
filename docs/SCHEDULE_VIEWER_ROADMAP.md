# Schedule Viewer Roadmap

## Current State (v3.2.0)

30+ features delivered across 4 waves + polish. SVG-based, zero dependencies, dark mode compatible.

### Known Bugs (to fix next session)

1. **WBS names not showing level names** — The WBS tree shows `short_name` but not the full hierarchical path. Needs to show WBS level names (e.g. "Phase 1 > Foundations > Concrete") with proper indent visualization.

2. **Date axis label overlap** — When zoom level is "day" on long schedules, date labels overlap each other. Needs dynamic label density based on available space (skip labels when too dense).

3. **Dependency lines to collapsed WBS** — When a WBS section is collapsed, dependency lines still try to route to hidden row positions. Lines should route to the collapsed WBS summary row instead.

4. **Fixed 500px height** — Viewer height defaults to 500px. Should auto-size based on visible rows (min 300px, max viewport height - header).

### Missing Standard Columns (Industry Reference)

Per AIA G703/G702 and AACE RP 29R-03 Schedule Submission requirements:

| Column | Status | Priority |
|--------|--------|----------|
| Activity ID (Code) | Done | - |
| Activity Name | Done | - |
| WBS | Partial (tree, not column) | P1 |
| Original Duration | Done (duration_days) | - |
| Remaining Duration | Missing | P1 |
| % Complete | Done (progress_pct) | - |
| Early Start | Done | - |
| Early Finish | Done | - |
| Late Start | Done | - |
| Late Finish | Done | - |
| Total Float | Done | - |
| Free Float | Available in data, not shown | P2 |
| Actual Start | Available in data, not shown | P1 |
| Actual Finish | Available in data, not shown | P1 |
| Baseline Start | Done (with baseline) | - |
| Baseline Finish | Done (with baseline) | - |
| Calendar | Available, not shown | P2 |
| Constraint Type | Badge shown, not column | P2 |
| Constraint Date | Available, not shown | P2 |
| Predecessor List | In detail panel only | P3 |
| Successor List | In detail panel only | P3 |
| Resource Assignments | Not available | P3 |
| Budget Cost | Not available | P3 |

### Planned Enhancements (Next Waves)

#### Wave 5: Standard Columns + Bug Fixes
- Fix WBS level names display
- Fix date axis overlap with dynamic density
- Fix dependency lines for collapsed WBS
- Add Actual Start/Finish columns to table
- Add Remaining Duration column
- Add Free Float display option
- Auto-size viewer height

#### Wave 6: Advanced Interactions
- Drag-to-pan timeline horizontally
- Column configuration panel (show/hide/reorder)
- Activity grouping by any field (status, calendar, WBS level)
- Sticky left columns in table (code + name always visible)

#### Wave 7: Resource & Cost Integration
- Resource histogram below Gantt (demand vs capacity)
- Cost loading curve overlay
- Budget vs actual cost per activity
- Resource-constrained critical path highlighting

#### Wave 8: Print & Export
- PDF export of current Gantt view (SVG → PDF)
- PNG/SVG image export
- Excel export with formatting
- Print preview with page breaks per WBS section

### Industry Templates Research Needed

Before next session, research these submission standards:
- **AIA G703** — Application and Certificate for Payment (schedule attachment format)
- **AACE RP 29R-03 Section 5.3** — Forensic Schedule Report documentation requirements
- **DCMA Schedule Submission Format** — Required columns and data for government contracts
- **Owner's Representative Standard Reports** — Monthly update format (baseline vs current vs forecast)
- **SCL Protocol Appendix C** — Recommended schedule presentation format for claims

These define what columns/data a professional schedule submission must include. Our Schedule Viewer should support exporting in these formats.
