# Business Case -- P6 XER Schedule Analytics

## Industry Context

**Construction, infrastructure, and energy** projects worldwide rely on Oracle Primavera P6 as the standard for project scheduling. P6 manages activities, dependencies, resources, and calendars for projects that can span years and involve thousands of activities.

P6 exports schedule data as `.xer` files -- but lacks built-in analytics for schedule health assessment. Schedulers need to answer questions like:

- How many activities have negative float? (schedule delay indicators)
- Is float eroding between schedule updates? (trend analysis)
- Are there activities missing predecessors or successors? (logic gaps)
- What percentage of activities are constrained? (schedule rigidity)
- How do two schedule versions compare? (change detection)

## The Problem

Answering these questions currently requires:

1. **Manual analysis** -- Schedulers export data and build spreadsheets by hand, which is error-prone and time-consuming
2. **Expensive proprietary tools** -- Products like Deltek Acumen Fuse or Schedule Analyzer Pro cost thousands of dollars per license
3. **Custom development** -- Organizations build one-off solutions that are not portable or maintainable

There is no widely available, open-source toolkit for P6 schedule analytics.

## The Solution

An open-source Power BI toolkit (with a roadmap toward a standalone tool) that:

- **Parses XER files directly** using Power Query -- no external dependencies, no Python scripts, no plugins
- **Produces standardized schedule health metrics** via 206 DAX measures
- **Compares schedule versions** to detect float erosion, activity changes, and relationship modifications
- **Works with SQLite** as an alternative data source (for P6 database connections)

## Value Proposition

| Value | Description |
|-------|-------------|
| **Automated analysis** | 206 DAX measures replace manual spreadsheet calculations |
| **Standardized metrics** | Consistent schedule health indicators across all projects |
| **Version tracking** | Side-by-side comparison of schedule updates with float erosion detection |
| **Zero cost** | Open-source alternative to proprietary schedule analysis tools |
| **No infrastructure** | Runs in Power BI Desktop (free) with no server requirements |
| **Portable knowledge** | DAX and M code documented for reuse and adaptation |

## Target Users

- **Project schedulers** -- Build and maintain P6 schedules, need health checks and trend analysis
- **Project controls engineers** -- Monitor schedule performance, report to management
- **PMO teams** -- Standardize schedule analysis across a portfolio of projects
- **Construction managers** -- Review schedule status without deep P6 expertise
- **Independent consultants** -- Need portable, license-free analysis tools

## Scale

The toolkit has been deployed in production for:
- A major infrastructure program with 130+ DAX measures and 84 configuration parameters
- Multi-project XER files with composite key support
- Schedule comparison workflows for version-over-version tracking

The documented patterns (36 Reader measures, 40 Compare measures, 130 Program Schedule measures) represent proven, production-tested analytics logic.
