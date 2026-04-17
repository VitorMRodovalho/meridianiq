# Schedule Viewer

Interactive Gantt chart built entirely with SVG (no chart.js, no d3 — just hand-crafted components). Handles 10,000+ activities via virtual scrolling. Lives at `/schedule` in the web UI.

## Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Toolbar: zoom · filters · toggles · WBS depth · export          │
├───────────────┬─────────────────────────────────────────────────┤
│ WBS tree      │ Gantt canvas                                    │
│ + ID column   │ (bars, float, dependencies, data date marker)   │
│ + activity    │                                                 │
│   table       │                                                 │
├───────────────┴─────────────────────────────────────────────────┤
│ ▸ Resource Histograms (collapsible, lazy-loaded)                │
├─────────────────────────────────────────────────────────────────┤
│ Activity detail panel (appears when a bar is clicked)           │
└─────────────────────────────────────────────────────────────────┘
```

## Core features (Waves 1–4)

- **WBS tree** — collapsible, with per-node activity counts. Use **Expand All / Collapse All** buttons or click individual nodes.
- **Gantt bars** — color-coded by status: critical = red, in progress = blue, complete = green, not started = grey.
- **Progress overlay** — physical % complete rendered as a filled portion inside each bar.
- **Milestones** — finish milestones show as diamond shapes rather than bars.
- **Data date marker** — amber dashed vertical line showing the schedule's data date.
- **Baseline comparison** — when a baseline project is picked, grey dashed bars render below current bars showing planned dates.
- **Float bars** — amber extension from early finish to late finish, toggleable via **Show Float**.
- **Negative float** — red dashed border on any activity whose total float is below zero.
- **Dependency lines** — SVG bezier curves (FS / FF / SS / SF) with arrowheads. Toggle via **Dependencies**.
- **Critical path only** — filter toggle that hides all non-critical activities.
- **Detail panel** — click any bar to see 12 fields plus clickable predecessor / successor list (network navigation).

## Wave 5 (v3.3) — standard columns

Per AIA G703 / AACE RP 29R-03 §5.3 schedule submission requirements, the activity table includes 23 columns:

| Column | Notes |
|---|---|
| Activity ID (task_code) | Always visible |
| Activity Name | Always visible |
| WBS path | Column + tree tooltip |
| Original / Remaining Duration | In days |
| % Complete | Physical complete |
| Early Start / Finish | From CPM |
| Late Start / Finish | From backward pass |
| Total Float / Free Float | TF is critical-path indicator |
| Actual Start / Finish | Populated post data-date |
| Baseline Start / Finish | From baseline project |
| Start / Finish Variance | In days vs baseline |
| Calendar | Calendar name or ID |
| Constraint Type / Date | CS_MEO etc. + badge |

Open **Columns** in the toolbar to show / hide any column.

## Wave 6 (v3.5) — advanced interactions

- **Drag-to-pan** — click-drag anywhere on the Gantt to scroll both axes.
- **Sticky columns** — task code + name remain visible while scrolling right.
- **WBS path filter** — dropdown in the activity table to filter by any WBS level.
- **Weekend / holiday shading** — Sat/Sun grey bands; P6 calendar exceptions in amber.
- **Virtual scrolling** — only visible rows are rendered (tested on 10K+ activity schedules).

## Wave 7 (v3.6) — resource histograms

A new collapsible panel appears below the Gantt when a project is selected. Click **▸ Resource Histograms** to expand; the panel lazy-fetches `/api/v1/projects/{id}/schedule-view/resources` and renders a bar chart per resource showing as-scheduled daily demand (distributed uniformly across each activity's duration from CPM early dates — no leveling applied).

Use cases:

- Spot resource overloads before committing to a leveling pass
- Compare peak demand vs. crew availability discussed in project meetings
- Feed data into an external leveling tool by inspecting the JSON response directly

For full RCPSP leveling, use the `/resources` page (Serial SGS per Kolisch 1996, AACE RP 46R-11).

## Wave 8 (partial) — print & export

- **PDF export** — browser print dialog with the full SVG Gantt (`Ctrl+P` → Save as PDF). Preserves colors and fits the timeline to page width.
- **Excel export** — available via `/api/v1/exports/{project_id}/excel` (four sheets: activities, relationships, WBS, summary). Not yet Gantt-styled; that's a v3.7 target.
- **PNG / raster export** — pending.

## Zoom levels

Three zoom levels — **Day**, **Week**, **Month** — in the toolbar. The viewer auto-picks the right level based on project duration (> 365 days → month, > 60 days → week, else day). Date axis label density adapts with 48 px minimum spacing to prevent overlap.

## Performance notes

- Projects with > 100 activities auto-collapse all WBS branches on first load
- Virtual scrolling ensures Gantt canvas paint stays O(visible rows), not O(total rows)
- Schedule-view responses are cached by the backend (`analysis_results` table) keyed on `(project_id, baseline_id)`. First call runs CPM (~15s for 10K activities); subsequent calls are instant. Pass `?force=true` to bypass the cache.

## Troubleshooting

- **Empty Gantt** — check that the XER parsed successfully in the upload response (activity count > 0). Re-upload if the count is zero.
- **Missing baseline bars** — you need to select a baseline project in the dropdown at the top of the page. Only projects in the same program show up.
- **Dependency lines hit hidden rows** — in v3.2 this was a bug; fixed in v3.3 via virtual scrolling (collapsed rows are excluded from the layout index). If you still see this, file a bug with your synthetic reproducer.

## Related

- [Resource Leveling page](../methodologies.md#resource-leveling--resource-leveling) — full RCPSP with constraints
- [EVM S-Curve](../methodologies.md#evm--evm) — schedule + cost earned value
- [Schedule Viewer Roadmap](../SCHEDULE_VIEWER_ROADMAP.md) — feature status + next waves
