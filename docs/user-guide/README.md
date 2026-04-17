# User Guide

Practical walkthroughs for the MeridianIQ platform. Each guide covers a user-facing workflow end-to-end — upload, analysis, and interpretation — with pointers to the underlying engine when deeper methodology is relevant.

For technical reference see:

- [API Reference](../api-reference.md) — 98 endpoints × 18 routers
- [Methodology Catalog](../methodologies.md) — 40 engines with AACE/DCMA citations
- [MCP Tools Catalog](../mcp-tools.md) — 22 tools for Claude integration
- [Architecture](../architecture.md) — system overview + data flow

## Workflows

- [Getting Started](getting-started.md) — 5-minute quickstart: upload your first XER and see CPM + DCMA + health
- [Schedule Viewer](schedule-viewer.md) — Interactive Gantt walkthrough: WBS tree, baseline bars, float, dependencies, resource histograms, export
- [Analysis Workflow](analysis-workflow.md) — Forensic pipeline: DCMA → Compare → CPA → TIA → EVM → Monte Carlo
- [Cost Integration](cost-integration.md) — CBS Excel upload, cost snapshots, budget-vs-schedule correlation, narrative PDF reports
- [Submission Deliverables](submission-deliverables.md) — SCL Protocol / AACE §5.3 / AIA G702 / AIA G703 — how to generate each artefact
- [BI Dashboards](bi-dashboards.md) — Power BI / Tableau / Looker templates for the `/api/v1/bi/*` connector
- [MCP + Claude Integration](mcp-integration.md) — Using the 22 MCP tools from Claude Code and Claude Desktop

## Personas addressed

| Persona | Start with |
|---|---|
| Scheduler (updating P6 schedule) | Getting Started → Schedule Viewer → DCMA |
| Forensic Analyst (claim prep) | Analysis Workflow → Compare → TIA → Narrative → Submission Deliverables |
| Cost Engineer | Cost Integration → EVM → S-Curve → Submission Deliverables (G702 + G703) |
| Program Director | Getting Started → Programs + Trends (in Analysis Workflow) → BI Dashboards |
| Owner Representative | Getting Started → Schedule Viewer → Health Score → Narrative |
| Researcher / Educator | Methodology Catalog → any workflow for worked examples |

## Conventions in this guide

- Code blocks prefixed with `$` are shell commands; everything else is `curl` / API output or UI description.
- Screenshots are omitted — the UI changes more often than screenshots can be refreshed. Use the live deployment at [meridianiq.vitormr.dev](https://meridianiq.vitormr.dev) to follow along.
- All example XER fixtures in `tests/fixtures/` are synthetic. Never use real project data when following these walkthroughs unless you're operating on your own deployment.
