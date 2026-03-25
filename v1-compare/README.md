# v1-compare -- P6 Schedule Comparison Tool

100% original creation by Vitor Rodovalho. Compares two Oracle P6 schedules to detect changes, float erosion, and activity modifications between schedule updates.

## Purpose

When a project schedule is updated (re-baselined or statused), stakeholders need to understand what changed. This tool loads two XER files from different dates and provides side-by-side comparison analytics.

## Key Features

### Project Indexing by Recalculation Date
Projects are sorted by `last_recalc_date` and assigned an index:
- **Index = 1** -- Older schedule (baseline or previous update)
- **Index = 2** -- Newer schedule (current update)

This enables DAX measures to isolate metrics for each version independently.

### Float Erosion Detection
The `Total_Float_Erosion` measure calculates:
```
Project_2_Total_Float - Project_1_Total_Float
```
Negative values indicate float erosion (schedule is getting tighter). This is a key schedule health indicator that project controls teams monitor between updates.

### Activity Change Identification
The `Change_Description` measure compares activity names between the two schedule versions:
- "No" -- Activity name is unchanged
- "Yes" -- Activity name differs (indicates scope or description change)

### Relationship Free Float Calculation
The PREDECESSOR query extracts `aref` (actual relationship early finish) and `arls` (actual relationship late start) to calculate relationship-level free float:
```
Relationship Free Float = arls - aref
```
This identifies tight relationships between activities.

## Data Model

- **40 DAX measures** for comparison analytics
- **10 Power Queries** including Table.Combine for multi-file merging
- Composite keys (Task_ID_Key, wbs_id_Key, clndr_id.Key) for cross-project linking

## Contents

```
v1-compare/
+-- dax-measures/measures.md    -- All 40 DAX measure definitions
+-- power-query/queries.md      -- All 10 Power Query/M expressions
+-- data-model/
|   +-- schema.csv              -- Table and column schema
|   +-- relationships.csv       -- Model relationships
+-- README.md                   -- This file
```

## Not Present in Upstream

This tool has no equivalent in the upstream [Xer-Reader-PowerBI](https://github.com/djouallah/Xer-Reader-PowerBI) project. The upstream is a single-schedule reader; all comparison logic is Vitor Rodovalho's original work.
