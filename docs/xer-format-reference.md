# XER File Format Reference

## Overview

The Oracle Primavera P6 XER format is a tab-delimited text file used for importing and exporting project schedule data. It is the standard interchange format for P6 Professional Project Management.

## File Structure

An XER file consists of four types of lines, all tab-delimited:

```
ERMHDR  <version>  <date>  <project_id>  <export_user>
%T  TABLE_NAME
%F  field1  field2  field3  ...
%R  value1  value2  value3  ...
%R  value1  value2  value3  ...
%T  NEXT_TABLE_NAME
%F  field1  field2  ...
%R  value1  value2  ...
%E
```

### Line Types

| Prefix | Meaning | Description |
|--------|---------|-------------|
| `ERMHDR` | Header | File header with P6 schema version, export date, and source info |
| `%T` | Table | Declares the start of a new table (e.g., `%T TASK`) |
| `%F` | Fields | Column names for the current table (tab-separated) |
| `%R` | Row | One data row with values matching the `%F` columns |
| `%E` | End | Marks the end of the XER file |

### Important Characteristics

- All values are **tab-delimited** (not comma-separated)
- Date values use the format `YYYY-MM-DD HH:MM` (24-hour, no seconds)
- Numeric values are stored as text
- Empty fields are represented as empty strings between tabs
- A single XER file can contain multiple projects

## Key Tables

### Core Tables

| Table | Description | Key Fields |
|-------|-------------|------------|
| **CALENDAR** | Work calendar definitions | clndr_id, clndr_name, day_hr_cnt, week_hr_cnt, clndr_type |
| **PROJECT** | Project master record | proj_id, proj_short_name, last_recalc_date |
| **PROJWBS** | Work Breakdown Structure hierarchy | wbs_id, proj_id, parent_wbs_id, wbs_name, proj_node_flag |
| **TASK** | Activities/tasks (the core schedule data) | task_id, proj_id, wbs_id, task_code, task_name, status_code |
| **TASKPRED** | Predecessor/dependency relationships | task_id, pred_task_id, pred_type, lag_hr_cnt |

### Resource Tables

| Table | Description | Key Fields |
|-------|-------------|------------|
| **TASKRSRC** | Resource assignments to activities | task_id, rsrc_id, target_qty, act_reg_qty |
| **RSRC** | Resource definitions | rsrc_id, rsrc_name, rsrc_type |
| **RSRCRATE** | Resource cost rates | rsrc_id, cost_per_qty |

### Classification Tables

| Table | Description |
|-------|-------------|
| **ACTVTYPE** | Activity code type definitions |
| **ACTVCODE** | Activity code values |
| **PCATTYPE** | Project code type definitions |
| **PCATVAL** | Project code values |
| **UDFTYPE** | User-defined field type definitions |
| **UDFVALUE** | User-defined field values |

### Financial Tables

| Table | Description |
|-------|-------------|
| **FINDATES** | Financial period date definitions |
| **TASKFIN** | Task-level financial period data |
| **TRSRCFIN** | Resource-level financial period data |

## TASK Table Fields (55 Fields)

The TASK table is the most important table in the XER file. Each row represents one scheduled activity.

### Identity Fields
- `task_id` -- Unique activity identifier (within a project)
- `proj_id` -- Project identifier (links to PROJECT table)
- `wbs_id` -- WBS node identifier (links to PROJWBS table)
- `clndr_id` -- Calendar identifier (links to CALENDAR table)
- `task_code` -- Activity ID (user-visible code, e.g., "A1010")
- `task_name` -- Activity name/description
- `guid` -- Global unique identifier
- `tmpl_guid` -- Template GUID

### Schedule Date Fields
- `act_start_date` -- Actual start date
- `act_end_date` -- Actual finish date
- `early_start_date` -- Early start (CPM forward pass)
- `early_end_date` -- Early finish (CPM forward pass)
- `late_start_date` -- Late start (CPM backward pass)
- `late_end_date` -- Late finish (CPM backward pass)
- `target_start_date` -- Baseline start date
- `target_end_date` -- Baseline finish date
- `restart_date` -- Remaining start date
- `reend_date` -- Remaining finish date
- `rem_late_start_date` -- Remaining late start
- `rem_late_end_date` -- Remaining late finish
- `expect_end_date` -- Expected finish date
- `external_early_start_date` -- External early start (inter-project links)
- `external_late_end_date` -- External late finish (inter-project links)
- `suspend_date` -- Date activity was suspended
- `resume_date` -- Date activity was resumed

### Float Fields
- `total_float_hr_cnt` -- Total float in hours
- `free_float_hr_cnt` -- Free float in hours
- `float_path` -- Float path number
- `float_path_order` -- Order within float path
- `driving_path_flag` -- Whether activity is on the driving path (Y/N)

### Duration and Work Fields
- `remain_drtn_hr_cnt` -- Remaining duration in hours
- `target_drtn_hr_cnt` -- Original (baseline) duration in hours
- `act_work_qty` -- Actual work quantity
- `remain_work_qty` -- Remaining work quantity
- `target_work_qty` -- Budgeted work quantity
- `target_equip_qty` -- Budgeted equipment quantity
- `act_equip_qty` -- Actual equipment quantity
- `remain_equip_qty` -- Remaining equipment quantity
- `act_this_per_work_qty` -- Actual work this period
- `act_this_per_equip_qty` -- Actual equipment this period

### Status Fields
- `status_code` -- Activity status: `TK_Notstart`, `TK_active`, `TK_Complete`
- `phys_complete_pct` -- Physical percent complete (0-100)
- `complete_pct_type` -- How % complete is calculated: `cp_drtn`, `cp_units`, `cp_phys`

### Constraint Fields
- `cstr_date` -- Primary constraint date
- `cstr_type` -- Primary constraint type (CS_MSO, CS_MEF, CS_MEOA, etc.)
- `cstr_date2` -- Secondary constraint date
- `cstr_type2` -- Secondary constraint type

### Type Fields
- `task_type` -- Activity type: `TT_task` (task), `TT_LOE` (level of effort), `TT_mile` (start milestone), `TT_finmile` (finish milestone)
- `duration_type` -- Duration type calculation method
- `priority_type` -- Activity priority

### Other Fields
- `rsrc_id` -- Primary resource ID
- `rev_fdbk_flag` -- Review feedback flag
- `lock_plan_flag` -- Lock plan flag
- `auto_compute_act_flag` -- Auto-compute actuals flag
- `create_date` -- Record creation date
- `update_date` -- Last update date
- `create_user` -- User who created the activity
- `update_user` -- User who last updated the activity

## TASKPRED Table (Predecessor Relationships)

| Field | Description |
|-------|-------------|
| `task_id` | Successor activity ID |
| `pred_task_id` | Predecessor activity ID |
| `proj_id` | Project ID of successor |
| `pred_proj_id` | Project ID of predecessor (can differ for inter-project links) |
| `pred_type` | Relationship type: `PR_FS` (finish-to-start), `PR_SS` (start-to-start), `PR_FF` (finish-to-finish), `PR_SF` (start-to-finish) |
| `lag_hr_cnt` | Lag in hours (negative = lead) |
| `aref` | Actual relationship early finish |
| `arls` | Actual relationship late start |

## How XER Parsing Works in Power Query

The Power Query implementation in this toolkit follows this pattern:

1. **Read XER file as text**: Load the entire file as a text table
2. **Split by tabs**: Each line becomes a row with tab-separated columns
3. **Add table markers**: The first column after `%T` contains the table name, which is carried forward to all subsequent rows until the next `%T`
4. **Filter by table**: `Table.SelectRows(Source, each [Table] = "TASK" and [Column1] <> "%T")` isolates rows for a specific table
5. **Promote headers**: The `%F` row becomes column names via `Table.PromoteHeaders`
6. **Filter header duplicates**: Remove rows where field values equal field names (artifact of multi-table parsing)
7. **Type conversion**: Convert text values to appropriate types (number, datetime, date)
8. **Composite key generation**: Add calculated columns like `proj_id & "." & task_id` for multi-project support

## Reference

- Oracle P6 XER Import/Export Data Map: https://docs.oracle.com/cd/F51303_01/English/Mapping_and_Schema/xer_import_export_data_map_project/index.htm
- Upstream XER Reader: https://github.com/djouallah/Xer-Reader-PowerBI
- Python xerparser library: https://github.com/jjcode-datamining/xerparser
