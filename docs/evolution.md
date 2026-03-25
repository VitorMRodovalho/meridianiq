# Evolution -- From Open-Source Reader to Enterprise Analytics

This document traces the evolution of this P6 XER analytics toolkit from its open-source origins to its current state.

## Timeline

### 2020 -- Upstream Origin

**djouallah** (Mimoune) creates [Xer-Reader-PowerBI](https://github.com/djouallah/Xer-Reader-PowerBI) on GitHub.

- **12 commits**, 12 stars, 7 forks
- **No license specified** (all rights reserved by author)
- Provides basic Power Query to parse Oracle P6 XER files in Power BI
- Key innovation: dual data source support (XER text file + SQLite database via ODBC)
- The `Connections` parameter switches between XER and SQLite paths
- Core queries: xer (raw parser), TASK, PROJECT, PROJWBS, TASKPRED, CALENDAR
- No DAX measures -- purely a data reader
- Last commit: **2020-02-18**
- Effectively abandoned after February 2020

### ~2024 -- Enhanced Reader (v1-reader)

Vitor Rodovalho takes the upstream concept and significantly enhances it:

**Composite Keys for Multi-Project Support**
- Added `Task_ID_Key` (proj_id.task_id) to uniquely identify activities across multiple projects in a single XER file
- Added `wbs_id_Key` (proj_id.wbs_id) for WBS cross-referencing
- Added `Parent_wbs_id_Key` with root node handling logic
- Added `clndr_id_key` for project-specific calendar linking

**Forecast and Time Series Integration**
- Integrated `Forecast` table and `Mstdate` date dimension
- Enabled cumulative forecast tracking and period-over-period analysis
- `Active` measure counts tasks active within a selected date range

**36 DAX Schedule Analysis Measures**
- Task counts by status (complete, ongoing, not started, negative float, zero float)
- Activity type categorization (LOE, start milestone, finish milestone, task dependent)
- Labor and equipment tracking (budget, actual, remaining, at-completion, % complete)
- Date metrics (start, finish, actual start, actual finish)
- Schedule health (total float, primary constraints, missing predecessors/successors)
- Completion percentage type distribution (duration, units, physical)

**Enhanced Date Handling**
- Added explicit datetime-to-date conversion for all 14 schedule date fields
- Removes unnecessary time components for cleaner date-based reporting

**New Queries**
- `P6` summary view for simplified activity reporting
- `Successor` table derived from predecessor data
- `Schema` for XER version extraction
- `Activity_Status` lookup table
- `Source` and `Path_Source` for connection metadata

### ~2024 -- Compare Tool (v1-compare)

Vitor creates **Xer_Compare_two_projects** -- an entirely new dashboard not present in the upstream project.

**Purpose**: Compare two P6 schedules side-by-side to detect changes between schedule updates.

**Key Innovations**:
- **Project indexing by last_recalc_date**: Projects sorted by recalculation date and indexed (Index=1 = older schedule, Index=2 = newer schedule)
- **Float erosion calculation**: `Project_2_Total_Float - Project_1_Total_Float` shows how float has changed between schedule versions
- **Activity change detection**: Compares activity names between versions to flag modifications
- **Relationship free float**: Calculates free float from predecessor data using `arls - aref` (actual relationship late start minus actual relationship early finish)
- **40 DAX measures** for comparison analytics
- **Table.Combine pattern** for merging multiple XER files into a single model

### 2024-2025 -- Production Dashboard (v1-program-schedule)

Vitor builds the **Program Schedule** dashboard for enterprise use in a major infrastructure program.

- **130 DAX measures** (vs 36 in the Reader) for comprehensive schedule management
- **84 M parameters** for configuration and connection management
- **20 Power Queries** with production-grade data handling
- Built on the Reader's XER parsing patterns but adapted for enterprise requirements
- Deployed as part of a multi-dashboard program management suite

This represents the production evolution of the Reader concept, scaled for real-world program controls.

### 2026 -- Knowledge Extraction

DAX measures, Power Query/M code, and data model schemas extracted from the .pbix files using [PBIXRay](https://github.com/Hugoberry/PBIXRay) (a Python library for reading Power BI file internals).

- All knowledge artifacts documented in Markdown and CSV formats
- Anonymized to remove client-specific information
- Published for open-source consumption and as the foundation for v2 development

### Future -- v2 Vision

Planned evolution beyond Power BI dependency. See [v2-roadmap.md](v2-roadmap.md) for details.

The goal is a standalone tool that can parse XER files and produce schedule health metrics without requiring Power BI, enabling broader adoption and CI/CD integration.
