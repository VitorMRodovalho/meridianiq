# Architecture -- Data Flow and Parsing Patterns

## System Overview

```
                         +------------------+
                         |   XER File       |
                         |   (text, tab-    |
                         |    delimited)    |
                         +--------+---------+
                                  |
                                  v
                    +-------------+-------------+
                    |   Power Query Parser       |
                    |   (M Language)             |
                    |                            |
                    |  1. Read as text           |
                    |  2. Split by tabs          |
                    |  3. Filter by %T marker    |
                    |  4. Promote %F headers     |
                    |  5. Type conversion        |
                    |  6. Composite key gen      |
                    +-------------+--------------+
                                  |
                                  v
                    +-------------+--------------+
                    |   Power BI Data Model      |
                    |                            |
                    |  TASK ----+---- PROJWBS    |
                    |    |      |       |        |
                    |  TASKPRED |    PROJECT     |
                    |    |      |       |        |
                    |  CALENDAR +--- Forecast    |
                    |           |    Mstdate     |
                    +-------------+--------------+
                                  |
                                  v
                    +-------------+--------------+
                    |   DAX Measures              |
                    |                             |
                    |  Task counts, float         |
                    |  analysis, labor tracking,  |
                    |  milestone categorization,  |
                    |  forecast cumulation        |
                    +--------------+--------------+
                                   |
                                   v
                    +--------------+--------------+
                    |   Dashboard Visualizations   |
                    +------------------------------+


     ALTERNATIVE PATH:

                    +------------------+
                    |   SQLite DB      |
                    |   (P6 export)    |
                    +--------+---------+
                             |
                             v
                    +--------+---------+
                    |   ODBC Driver    |
                    |   (SQLite3)      |
                    +--------+---------+
                             |
                             v
                    [Same Power Query pipeline, different source step]
```

## The Connections Parameter

A central `Connections` parameter controls the data source:

```
Connections = "XER"   -->  Read from .xer text file via Path parameter
Connections = "SQLite" --> Read from SQLite database via Path_SQLITE parameter
```

Every query contains a branch:
```powerquery
result = if Connections="XER" then [XER parsing result] else [SQLite query result]
```

This allows the same dashboard to work with either data source without modification.

## Power Query Parsing Pattern (XER Path)

### Step 1: Raw File Read

The `xer` base query reads the entire XER file as a text table and splits each line by tab characters. This produces a wide table where:
- Column1 contains the line type prefix (%T, %F, %R, ERMHDR)
- Subsequent columns contain the tab-separated values

### Step 2: Table Marker Propagation

A custom column carries the current table name forward. When `%T TASK` appears, all subsequent rows are tagged with "TASK" until the next `%T` marker.

### Step 3: Table Isolation

Each query filters for its target table:
```powerquery
Table.SelectRows(Source, each ([#"Table "] = "TASK") and ([Column1] <> "%T"))
```

This keeps only the `%F` (field names) and `%R` (data rows) lines for that table.

### Step 4: Header Promotion

```powerquery
Table.PromoteHeaders(#"Filtered Rows")
```

The `%F` row becomes the column headers, and all `%R` rows become data.

### Step 5: Column Selection

Each query selects only the needed columns. For TASK, this is 55 fields covering identity, dates, float, duration, status, constraints, and type.

### Step 6: Type Conversion

Two-phase type conversion:
1. First pass: text to number (float hours, work quantities) and text to datetime (all date fields)
2. Second pass: datetime to date (removes time component for cleaner reporting)

### Step 7: Composite Key Generation

```powerquery
Task_ID_Key = Table.AddColumn(result, "Task_ID_Key", each [proj_id] & "." & [task_id])
```

Composite keys enable multi-project XER support where task_id values can repeat across projects.

## Data Model Relationships

### v1-reader (Enhanced Reader)

```
TASK ──(wbs_id_Key)──> PROJWBS
TASK ──(proj_id)──> PROJECT
PREDECESSOR ──(Task_id_key)──> TASK [via Task_ID_Key]
PREDECESSOR ──(pred_task_id_key)──> TASK [via Task_ID_Key]
Successor ──(Task_pred_id_key)──> TASK [via Task_ID_Key]
P6 ──(Task_ID_Key)──> TASK
P6_Calendars ──(clndr_id_key)──> TASK [via clndr_id]
Mstdate ──(Date)──> Forecast
```

### v1-compare (Schedule Comparison)

Same base relationships, plus:
- PROJECT includes an `Index` column (1=older, 2=newer) for version identification
- PREDECESSOR includes `Relationship Free Float` calculated column
- `clndr_id.Key` composite key links calendars to tasks per project

### v1-program-schedule (Production)

Extended model with additional tables:
- ACTVCODE / ACTVTYPE for activity code filtering
- UDFTYPE / UDFVALUE for user-defined field support
- FINDATES / TASKFIN for financial period data
- Multiple schema helper tables for multi-XER file support

## Evolution of Parsing Complexity

```
Reader (v1)          Compare (v1)           Program Schedule (v1)
12 queries           10 queries             20 queries
36 DAX measures      40 DAX measures        130 DAX measures
Single XER/SQLite    Multiple XER files     Multiple XER + schemas
Basic type conv.     Table.Combine merge    Full schema management
5 composite keys     6 composite keys       84 M parameters
```

Each version builds on the previous, adding more sophisticated data handling while preserving the core XER parsing pattern.
