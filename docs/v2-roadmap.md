# v2 Roadmap -- Beyond Power BI

## Current Limitation

XER parsing is currently embedded in Power BI Power Query (M language), creating a dependency on Microsoft's ecosystem. Users must have Power BI Desktop (Windows only) to use these tools. The DAX measures require the Power BI engine for evaluation.

## Vision

A standalone tool (web application or CLI) that:

- Parses Oracle P6 XER files directly without Power BI
- Produces schedule health metrics (float analysis, milestone tracking, predecessor gaps) as structured data
- Compares schedule versions programmatically, detecting float erosion and activity changes
- Generates reports in standard formats (PDF, HTML, JSON)
- Runs on any platform (Windows, macOS, Linux)

## Potential Approaches (TBD)

### Python Library
- Build on existing parsers like [xerparser](https://github.com/jjcode-datamining/xerparser) or create a custom parser
- Translate the 206 DAX measures into Python functions
- Output to pandas DataFrames for further analysis

### Web Application
- File upload interface for XER files
- Server-side parsing and analysis
- Interactive dashboards without Power BI dependency
- Multi-user support for team collaboration

### CLI Tool
- Parse XER files from the command line
- Generate schedule health reports as JSON/CSV
- Integrate into CI/CD pipelines for automated schedule validation
- Compare two XER files and output a change report

## Process

This will follow proper requirements engineering:

1. **Documentation of current capabilities** -- This repository captures all existing DAX and M code logic
2. **Gap assessment vs. industry tools** -- Evaluate what existing tools (Deltek Acumen, Schedule Analyzer Pro, etc.) provide and identify differentiation opportunities
3. **Business and technical requirements** -- Formal requirements documentation
4. **Persona consultation** -- Gather input from schedulers, project controls engineers, and PMO teams
5. **Technical specifications** -- Architecture, technology stack, deployment model
6. **Development** -- Iterative implementation with user testing

## Status

Planning phase. The knowledge extraction in this repository is the first step -- documenting what the current tools do so it can be translated to a new platform.

Contributions and requirements are welcome via Issues.
