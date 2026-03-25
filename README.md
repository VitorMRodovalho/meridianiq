# P6 XER Analytics -- Primavera P6 Schedule Analysis Toolkit

**Parse, analyze, and compare Oracle P6 XER schedule files using Power BI.**

Author: Vitor Rodovalho
Based on: [djouallah/Xer-Reader-PowerBI](https://github.com/djouallah/Xer-Reader-PowerBI) (enhanced and extended)

## Overview

This repository contains the documented knowledge artifacts (DAX measures, Power Query/M code, and data model schemas) from a suite of Power BI dashboards built for Oracle Primavera P6 schedule analysis.

These are **not runnable .pbix files** -- they are the extracted, documented, and anonymized intellectual property: the DAX formulas, M code, data model relationships, and architectural decisions that make the dashboards work. This enables knowledge sharing, code review, and serves as the foundation for a future standalone tool.

### What is P6/XER?

Oracle Primavera P6 is the industry-standard project scheduling tool for construction, infrastructure, and energy projects. It exports schedule data as `.xer` files -- tab-delimited text files containing project activities, dependencies, calendars, WBS hierarchies, and resource assignments. See [docs/xer-format-reference.md](docs/xer-format-reference.md) for format details.

### Evolution

This toolkit evolved from a simple open-source XER reader (2020) into a production-grade enterprise schedule analytics platform. See [docs/evolution.md](docs/evolution.md) for the full story.

## Tool Inventory

| Tool | DAX Measures | Power Queries | Purpose |
|------|-------------|---------------|---------|
| **v1-reader** | 36 | 12 | Parse and analyze single XER/SQLite schedule |
| **v1-compare** | 40 | 10 | Compare two P6 schedule versions |
| **v1-program-schedule** | 130 | 20 | Production enterprise schedule dashboard |

**Total: 206 DAX measures** for comprehensive schedule analytics.

## Key Features

- **XER text file parsing via Power Query** -- no external dependencies, no Python, no plugins
- **SQLite alternative data source** -- same dashboards can read from SQLite databases via ODBC
- **Composite keys** (proj_id.task_id, proj_id.wbs_id) for multi-project XER support
- **Schedule health metrics**: float analysis, milestone tracking, predecessor/successor gap detection
- **Version comparison**: float erosion calculation, activity change detection, relationship free float analysis
- **Forecast integration**: time-series forecast hours with cumulative tracking
- **Activity categorization**: LOE, milestones (start/finish), task dependent, by completion percentage type

## Repository Structure

```
p6-xer-analytics/
+-- README.md                  # This file
+-- LICENSE                    # MIT (Vitor's additions only)
+-- ATTRIBUTION.md             # Upstream credit and license note
+-- ANONYMIZATION_RULES.md     # Sanitization methodology
+-- .gitignore
+-- docs/
|   +-- xer-format-reference.md    # Oracle P6 XER file format guide
|   +-- architecture.md            # Data flow and parsing patterns
|   +-- evolution.md               # Project history (2020-2026)
|   +-- business-case.md           # Industry context and value proposition
|   +-- v2-roadmap.md              # Future: beyond Power BI
+-- v1-reader/                 # Enhanced XER Reader
|   +-- dax-measures/measures.md
|   +-- power-query/queries.md
|   +-- data-model/{schema.csv, relationships.csv}
|   +-- UPSTREAM_DIFF.md
+-- v1-compare/                # Schedule Comparison Tool
|   +-- dax-measures/measures.md
|   +-- power-query/queries.md
|   +-- data-model/{schema.csv, relationships.csv}
|   +-- README.md
+-- v1-program-schedule/       # Production Enterprise Dashboard
|   +-- dax-measures/measures.md
|   +-- power-query/queries.md
|   +-- data-model/{schema.csv, relationships.csv}
|   +-- README.md
+-- xer-samples/
    +-- README.md
```

## How to Use

1. **Study the DAX measures** in each tool's `dax-measures/measures.md` to understand the schedule analysis logic
2. **Review Power Query code** in `power-query/queries.md` to see the XER parsing implementation
3. **Examine data models** via `schema.csv` and `relationships.csv` to understand table structures
4. **Read the architecture docs** in `docs/` for the overall system design

To recreate a working dashboard, you would need to:
- Import the Power Query code into a new Power BI file
- Recreate the data model relationships from the CSV files
- Add the DAX measures to a Metrics table
- Build visualizations on top

## Attribution

This project builds on [Xer-Reader-PowerBI](https://github.com/djouallah/Xer-Reader-PowerBI) by djouallah. The upstream project provided the foundational XER parsing concept. All DAX measures, the Compare tool, the Program Schedule dashboard, composite key patterns, and forecast integration are original work by Vitor Rodovalho. See [ATTRIBUTION.md](ATTRIBUTION.md) for full details.

## Anonymization

All files have been sanitized to remove client names, internal IPs, SharePoint URLs, and personal identifiers. The anonymization follows a methodology-only approach documented in [ANONYMIZATION_RULES.md](ANONYMIZATION_RULES.md). No real values appear in any repository file.

## Note on Portuguese Code

Some Power Query variable names and DAX measure names may contain Portuguese-language terms. These are preserved from the original development environment to maintain code accuracy and are not sensitive information.

## License

MIT License -- applies to Vitor Rodovalho's contributions only. The upstream project (djouallah/Xer-Reader-PowerBI) has no specified license. See [LICENSE](LICENSE) and [ATTRIBUTION.md](ATTRIBUTION.md).
