# Upstream Diff -- v1-reader vs djouallah/Xer-Reader-PowerBI

This document categorizes each Power Query and DAX measure in the v1-reader,
indicating whether it came from the upstream project, was modified, or is entirely new.

## Upstream Project Reference

- **Repository**: https://github.com/djouallah/Xer-Reader-PowerBI
- **Author**: djouallah (Mimoune)
- **Last commit**: 2020-02-18
- **Contents**: README.md, Xer_Reader_PQ_sqlite.pbix, xerfile/sample.xer
- **Description**: Basic Power Query to parse XER files in Power BI with dual XER/SQLite source support

The upstream README states: "Building an Xer reader using PowerBI -- for the moment, it reads projects, either from Xer or SQLITE database."

## Power Query Classification

### [UPSTREAM] -- Core XER Parsing (from djouallah, minimal changes)

| Query | Description | Notes |
|-------|-------------|-------|
| `xer` | Reads raw XER file as text, splits by tab delimiter | Core upstream pattern. The `%T`/`%F`/`%R` parsing concept originates here. (Parameter-based, not shown in extracted queries.) |

### [MODIFIED] -- Upstream Enhanced by Vitor

| Query | Upstream Basis | Vitor's Enhancements |
|-------|---------------|---------------------|
| `TASK` | Filters XER for TASK table, promotes headers, selects 55 columns, type conversion. Dual XER/SQLite source with `Connections` parameter. | Added **composite keys**: `Task_ID_Key` (proj_id.task_id) and `wbs_id_Key` (proj_id.wbs_id). Added **datetime-to-date conversion** step for all 14 date fields. |
| `PROJECT` | Extracts proj_id, proj_short_name, last_recalc_date from XER/SQLite. | Minor: added explicit `proj_id` type conversion to text. |
| `PROJWBS` | Reads WBS hierarchy with parent-child relationships from XER/SQLite. | Added **composite keys**: `wbs_id_Key` (proj_id.wbs_id) and `Parent_wbs_id_Key` (proj_id.parent_wbs_id with proj_node_flag logic). Streamlined column selection. |
| `PREDECESSOR` | Reads TASKPRED table from XER/SQLite for predecessor relationships. | Added **composite keys**: `Task_id_key` and `pred_task_id_key`. Added `PR_` prefix removal from pred_type. |
| `P6_Calendars` | Reads CALENDAR table from XER/SQLite. | Added **composite key**: `clndr_id_key` with project-specific calendar logic (CA_Project type uses proj_id prefix). |

### [NEW] -- Created Entirely by Vitor

| Query | Purpose |
|-------|---------|
| `P6` | Summary view of TASK table -- extracts Activity_ID, Activity_name, Task_ID_Key, wbs_id_Key for simplified reporting. |
| `Metrics` | Empty scaffold table for DAX measures (standard Power BI pattern for measure containers). |
| `Successor` | Derives successor relationships from PREDECESSOR table by creating `Task_pred_id_key` from pred_proj_id and pred_task_id. |
| `Schema` | Extracts ERMHDR header from XER file to capture schema version. Falls back to "sqlite" label for SQLite sources. |
| `Path_Source` | Converts the active connection path (XER file path or SQLite path) into a table for reporting which source is active. |
| `Activity_Status` | Hardcoded lookup table mapping status_code values (TK_Complete, TK_active, TK_Notstart) to human-readable descriptions. |
| `Source` | Exposes the current `Connections` parameter value (XER or SQLite) as a table for dashboard display. |

## DAX Measures Classification

**All 36 DAX measures are [NEW]** -- the upstream project was a pure data reader with no DAX measures.

### Task Counting Measures
| Measure | Expression Summary |
|---------|-------------------|
| Task_Count | Count of all task_id values |
| Task_Count_Completed | Tasks where status = TK_Complete |
| Task_Count_Ongoing | Tasks where status = TK_active |
| Task_Count_Not_Started | Tasks where status = TK_Notstart |
| Task_Counts_Not_Completed | Sum of Not_Started + Ongoing |
| Task_Count_Negative_Float | Tasks with total_float < 0 |
| Task_Count_Float_0 | Non-complete tasks with total_float = 0 |

### Activity Type Measures
| Measure | Expression Summary |
|---------|-------------------|
| LOE | Count of Level of Effort activities (TT_LOE) |
| Finish Milestone | Count of finish milestones (TT_finmile) |
| Start Milestone | Count of start milestones (TT_mile) |
| Task Dependent | Count of task-dependent activities (TT_task) |

### Completion Percentage Type Measures
| Measure | Expression Summary |
|---------|-------------------|
| Count_Task_Duration_% | Tasks using duration-based % complete |
| Count_Task_Units_% | Tasks using units-based % complete |
| Count_Task_Phys_% | Tasks using physical % complete |

### Labor and Resource Measures
| Measure | Expression Summary |
|---------|-------------------|
| Budget Labor Units | Sum of target_work_qty (non-zero) |
| Actual Labor Units | Sum of act_work_qty |
| Remaining Labor Unit | Sum of remain_work_qty (non-zero) |
| At Completion Labor Units | Actual + Remaining labor |
| %_Labor_units | Actual / At Completion ratio |
| Budget Non Labor Units | Sum of target_equip_qty (non-zero) |
| Actual Non Labor Units | Sum of act_equip_qty |
| Remaining Non Labor Unit | Sum of remain_equip_qty |
| At Completion Non Labor Units | Actual + Remaining non-labor |

### Date Measures
| Measure | Expression Summary |
|---------|-------------------|
| Start_Date | Minimum of Start field |
| Finish_Date | Maximum of Finish field |
| Actual Start | Minimum of act_start_date |
| Actual Finish | Maximum of act_end_date |

### Schedule Health Measures
| Measure | Expression Summary |
|---------|-------------------|
| Tota_Float | Minimum total float value |
| Primary Constraints | Count of tasks with non-blank constraint type |
| Missing Predecessor | Sum of predecessor flag (0 = missing) |
| Missing Successor | Sum of successor flag (0 = missing) |
| Sort | WBS master sort with blank handling |

### Forecast / Time Series Measures
| Measure | Expression Summary |
|---------|-------------------|
| Active | Count of tasks active within selected date range (uses Mstdate calendar) |
| Forecast_Hours_Period | Sum of Forecast table hours for selected period |
| Remaining_Hours_Cumulative | Cumulative remaining hours from Data_Date to selected date |
| Forecast_Hours_Cumulative | Running total of forecast hours up to selected date |

## Architectural Patterns

### Dual-Source Pattern (XER + SQLite)
**Origin**: Upstream (djouallah). Each query contains two parallel data loading paths:
- XER path: reads text file, filters by `%T` table marker, promotes `%F` headers
- SQLite path: connects via ODBC driver to SQLite database
- A `Connections` parameter switches between them: `if Connections="XER" then ... else ...`

**Vitor preserved this pattern** in all modified queries.

### Composite Keys (proj_id.task_id)
**Origin**: Vitor's addition. Not present in upstream.

The upstream assumes single-project XER files. Vitor added composite keys to support multi-project XER files where task_id values can repeat across projects:
- `Task_ID_Key` = proj_id & "." & task_id
- `wbs_id_Key` = proj_id & "." & wbs_id
- `Parent_wbs_id_Key` = proj_id & "." & parent_wbs_id (with root node handling)
- `clndr_id_key` = proj_id & "." & clndr_id (for project-specific calendars)

### Forecast Integration
**Origin**: Vitor's addition. Not present in upstream.

The Reader integrates with a `Forecast` table and `Mstdate` date dimension to provide time-series schedule analysis. This enables cumulative forecast tracking and period-over-period active task counting.

### DateTime-to-Date Conversion
**Origin**: Vitor's addition.

The upstream leaves schedule dates as `datetime` type. Vitor added an explicit second type conversion step that converts all 14 date fields from `datetime` to `date`, removing unnecessary time components for cleaner reporting.
