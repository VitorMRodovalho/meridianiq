# API Reference

Generated from `src/api/app.py` — **113 endpoints** across **20 routers**. Interactive Swagger UI is served at `/docs` when the API is running; this document is a static browseable index.

All paths are prefixed with the deployment base URL (e.g. `https://meridianiq.fly.dev`). Auth column: `none` (public), `optional` (degrades gracefully), `required` (returns 401 without bearer token).

Regenerate with: `python3 scripts/generate_api_reference.py`

## Contents

- [Upload](#upload) — 2 endpoints
- [Projects](#projects) — 3 endpoints
- [Programs](#programs) — 5 endpoints
- [Comparison](#comparison) — 1 endpoints
- [Forensics](#forensics) — 10 endpoints
- [TIA](#tia) — 4 endpoints
- [EVM](#evm) — 6 endpoints
- [Risk](#risk) — 8 endpoints
- [Analysis](#analysis) — 11 endpoints
- [Intelligence](#intelligence) — 8 endpoints
- [What-If](#what-if) — 7 endpoints
- [Schedule Ops](#schedule-ops) — 7 endpoints
- [Cost](#cost) — 7 endpoints
- [Exports](#exports) — 6 endpoints
- [Benchmarks](#benchmarks) — 3 endpoints
- [Reports](#reports) — 3 endpoints
- [Admin](#admin) — 6 endpoints
- [Health](#health) — 2 endpoints
- [Bi](#bi) — 3 endpoints
- [Organizations](#organizations) — 11 endpoints

## Upload

_File ingestion (XER, MS Project XML)_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/demo/project` | Return a pre-analyzed demo project from the sample XER fixture. | `—` | none |
| `POST` | `/api/v1/upload` | Upload a schedule file (XER or MS Project XML), parse it, and store the result. | `ProjectSummary` | optional |

## Projects

_CRUD, detail, activities, validation_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/projects` | List all uploaded projects. | `ProjectListResponse` | optional |
| `GET` | `/api/v1/projects/{project_id}` | Get full project data for a given project_id. | `ProjectDetailResponse` | optional |
| `PUT` | `/api/v1/projects/{project_id}/sandbox` | Toggle sandbox mode for a project. | `dict` | optional |

## Programs

_Multi-revision program rollup_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/programs` | Return all programs with latest revision info. | `—` | optional |
| `GET` | `/api/v1/programs/{program_id}` | Return a program with all its revisions. | `—` | optional |
| `PUT` | `/api/v1/programs/{program_id}` | Rename or update a program. | `—` | optional |
| `GET` | `/api/v1/programs/{program_id}/rollup` | Aggregated KPIs across a program's revisions. | `—` | optional |
| `GET` | `/api/v1/programs/{program_id}/trends` | Trend data across all revisions for charting. | `—` | optional |

## Comparison

_Two-schedule diff + manipulation detection_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `POST` | `/api/v1/compare` | Compare two uploaded projects (baseline vs update). | `CompareResponse` | optional |

## Forensics

_CPA per AACE RP 29R-03, delay waterfall_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `POST` | `/api/v1/forensic/create-timeline` | Create a forensic CPA timeline from multiple schedule updates. | `TimelineDetailSchema` | optional |
| `POST` | `/api/v1/forensic/half-step` | Run a half-step (bifurcation) analysis between two schedule updates. | `HalfStepResponse` | optional |
| `POST` | `/api/v1/forensic/mip-3-1` | Run MIP 3.1 — Observational Static Logic / Gross comparison. | `Mip31Response` | optional |
| `POST` | `/api/v1/forensic/mip-3-2` | Run MIP 3.2 — Observational Dynamic Logic / Contemporaneous As-Is. | `Mip32Response` | optional |
| `POST` | `/api/v1/forensic/mip-3-5` | Run MIP 3.5 — Modified / Additive Multiple Base (Impacted As-Planned). | `Mip35Response` | optional |
| `POST` | `/api/v1/forensic/mip-3-6` | Run MIP 3.6 — Modified / Subtractive Single Simulation (Collapsed As-Built). | `Mip36Response` | optional |
| `POST` | `/api/v1/forensic/mip-3-7` | Run MIP 3.7 — Modified / Subtractive Multiple Simulation (Windowed Collapsed). | `Mip37Response` | optional |
| `GET` | `/api/v1/forensic/timelines` | List all forensic timelines. | `TimelineListResponse` | optional |
| `GET` | `/api/v1/forensic/timelines/{timeline_id}` | Get full forensic timeline with all window results. | `TimelineDetailSchema` | optional |
| `GET` | `/api/v1/forensic/timelines/{timeline_id}/delay-trend` | Return delay trend data for charting. | `DelayTrendResponse` | optional |

## TIA

_Time Impact Analysis per AACE RP 52R-06_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/tia/analyses` | List all TIA analyses. | `TIAListResponse` | optional |
| `GET` | `/api/v1/tia/analyses/{analysis_id}` | Get full TIA analysis with all fragment results. | `TIAAnalysisSchema` | optional |
| `GET` | `/api/v1/tia/analyses/{analysis_id}/summary` | Get delay-by-responsibility summary for a TIA analysis. | `TIASummaryResponse` | optional |
| `POST` | `/api/v1/tia/analyze` | Run Time Impact Analysis on a project with delay fragments. | `TIAAnalysisSchema` | optional |

## EVM

_Earned Value Management per ANSI/EIA-748_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/evm/analyses` | List all EVM analyses. | `EVMListResponse` | optional |
| `GET` | `/api/v1/evm/analyses/{analysis_id}` | Get full EVM analysis with all metrics. | `EVMAnalysisSchema` | optional |
| `GET` | `/api/v1/evm/analyses/{analysis_id}/forecast` | Get EAC scenario forecasts for an analysis. | `ForecastResponse` | optional |
| `GET` | `/api/v1/evm/analyses/{analysis_id}/s-curve` | Get S-curve data for an EVM analysis. | `SCurveResponse` | optional |
| `GET` | `/api/v1/evm/analyses/{analysis_id}/wbs-drill` | Get WBS-level EVM breakdown for an analysis. | `WBSDrillResponse` | optional |
| `POST` | `/api/v1/evm/analyze/{project_id}` | Run Earned Value Management analysis on a project. | `EVMAnalysisSchema` | optional |

## Risk

_Monte Carlo QSRA per AACE RP 57R-09_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `POST` | `/api/v1/risk/simulate/{project_id}` | Run Monte Carlo schedule risk simulation (QSRA) on a project. | `SimulationResultSchema` | optional |
| `GET` | `/api/v1/risk/simulations` | List all risk simulations. | `SimulationListResponse` | optional |
| `GET` | `/api/v1/risk/simulations/{simulation_id}` | Get full risk simulation result with all analysis data. | `SimulationResultSchema` | optional |
| `GET` | `/api/v1/risk/simulations/{simulation_id}/criticality` | Get criticality index data for a risk simulation. | `CriticalityResponse` | optional |
| `GET` | `/api/v1/risk/simulations/{simulation_id}/histogram` | Get histogram data for a risk simulation. | `HistogramResponse` | optional |
| `GET` | `/api/v1/risk/simulations/{simulation_id}/register-entries` | Return register entries that touch the simulation's most-sensitive activities. | `dict` | optional |
| `GET` | `/api/v1/risk/simulations/{simulation_id}/s-curve` | Get cumulative probability S-curve data for a risk simulation. | `RiskSCurveResponse` | optional |
| `GET` | `/api/v1/risk/simulations/{simulation_id}/tornado` | Get sensitivity / tornado data for a risk simulation. | `TornadoResponse` | optional |

## Analysis

_CPM, DCMA 14-point, schedule view, calendar, attribution_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `POST` | `/api/v1/contract/check` | Run contract compliance checks against a TIA analysis. | `ContractCheckResponse` | optional |
| `GET` | `/api/v1/contract/provisions` | List default contract provisions used for compliance checking. | `ContractProvisionsResponse` | optional |
| `GET` | `/api/v1/projects/{project_id}/calendar-validation` | Validate work calendar definitions for integrity and best practices. | `dict` | optional |
| `GET` | `/api/v1/projects/{project_id}/critical-path` | Compute and return the critical path for a project. | `CriticalPathResponse` | optional |
| `GET` | `/api/v1/projects/{project_id}/delay-attribution` | Compute delay attribution breakdown by responsible party. | `dict` | optional |
| `GET` | `/api/v1/projects/{project_id}/float-distribution` | Return float distribution buckets for a project. | `FloatDistributionResponse` | optional |
| `GET` | `/api/v1/projects/{project_id}/milestones` | Return all milestone activities for a project. | `MilestonesResponse` | optional |
| `GET` | `/api/v1/projects/{project_id}/schedule-view` | Get pre-computed layout data for the interactive Gantt viewer. | `dict` | optional |
| `DELETE` | `/api/v1/projects/{project_id}/schedule-view/cache` | Drop all cached schedule-view variants (every baseline) for a project. | `dict` | optional |
| `GET` | `/api/v1/projects/{project_id}/schedule-view/resources` | Per-resource daily demand for histogram rendering below the Gantt. | `dict` | optional |
| `GET` | `/api/v1/projects/{project_id}/validation` | Run DCMA 14-Point assessment for a project. | `ValidationResponse` | optional |

## Intelligence

_Health Score, float trends, root cause, NLP, anomalies, alerts, dashboard_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/dashboard` | Get portfolio-level dashboard KPIs. | `DashboardKPIs` | optional |
| `GET` | `/api/v1/projects/{project_id}/alerts` | Get early warning alerts for a project. | `AlertsResponse` | optional |
| `GET` | `/api/v1/projects/{project_id}/anomalies` | Detect statistical anomalies in schedule data. | `dict` | optional |
| `POST` | `/api/v1/projects/{project_id}/ask` | Ask a natural language question about a schedule. | `NLPQueryResponse` | optional |
| `GET` | `/api/v1/projects/{project_id}/delay-prediction` | Predict delay risk for all non-complete activities. | `DelayPredictionResponse` | optional |
| `GET` | `/api/v1/projects/{project_id}/float-trends` | Get float trend data between a baseline and update schedule. | `FloatTrendResponse` | optional |
| `GET` | `/api/v1/projects/{project_id}/health` | Get the composite schedule health score for a project. | `ScheduleHealthResponse` | optional |
| `GET` | `/api/v1/projects/{project_id}/root-cause` | Trace backwards through the dependency network to find the root cause. | `dict` | optional |

## What-If

_Deterministic + probabilistic scenarios, Pareto_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/projects/{project_id}/duration-prediction` | Predict project duration using ML trained on benchmark data. | `DurationPredictionResponse` | optional |
| `POST` | `/api/v1/projects/{project_id}/optimize` | Optimize a resource-constrained schedule using Evolution Strategies. | `dict` | optional |
| `POST` | `/api/v1/projects/{project_id}/pareto` | Run time-cost Pareto analysis across multiple scenarios. | `ParetoResponse` | optional |
| `POST` | `/api/v1/projects/{project_id}/resource-leveling` | Run resource-constrained scheduling using Serial SGS. | `LevelingResponse` | optional |
| `GET` | `/api/v1/projects/{project_id}/scorecard` | Get a comprehensive schedule scorecard with letter grades. | `ScorecardResponse` | optional |
| `GET` | `/api/v1/projects/{project_id}/visualization` | Get 4D visualization data (WBS spatial x CPM temporal). | `dict` | optional |
| `POST` | `/api/v1/projects/{project_id}/what-if` | Run a what-if scenario on a project schedule. | `WhatIfResponse` | optional |

## Schedule Ops

_Generation, build, cashflow, lookahead, risk register_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/projects/{project_id}/cashflow` | Get cash flow analysis with S-Curve data. | `dict` | optional |
| `GET` | `/api/v1/projects/{project_id}/lookahead` | Get look-ahead schedule for the next N weeks. | `dict` | optional |
| `GET` | `/api/v1/projects/{project_id}/risk-register` | List risk register entries plus summary statistics for a project. | `dict` | optional |
| `POST` | `/api/v1/projects/{project_id}/risk-register` | Create or upsert a risk register entry for a project. | `dict` | optional |
| `DELETE` | `/api/v1/projects/{project_id}/risk-register/{risk_id}` | Remove a risk register entry. | `dict` | optional |
| `POST` | `/api/v1/schedule/build` | Build a schedule from natural language description. | `dict` | optional |
| `POST` | `/api/v1/schedule/generate` | Generate a complete schedule from project parameters. | `dict` | optional |

## Cost

_CBS upload + persistence, trends, narrative, float entropy_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `POST` | `/api/v1/cost/upload` | Upload a CBS Excel file, parse, and persist as a cost snapshot. | `dict` | optional |
| `GET` | `/api/v1/projects/{project_id}/constraint-accumulation` | Compute constraint accumulation rate between two schedule versions. | `dict` | optional |
| `GET` | `/api/v1/projects/{project_id}/cost/compare` | Compare two persisted CBS cost snapshots element-by-element. | `dict` | optional |
| `GET` | `/api/v1/projects/{project_id}/cost/snapshots` | List all persisted CBS cost snapshots for a project (newest first). | `dict` | optional |
| `GET` | `/api/v1/projects/{project_id}/float-entropy` | Compute Shannon entropy of float distribution. | `dict` | optional |
| `GET` | `/api/v1/projects/{project_id}/narrative` | Generate a narrative schedule status report. | `dict` | optional |
| `POST` | `/api/v1/trends` | Compute schedule trends across multiple project updates. | `dict` | optional |

## Exports

_Excel workbook, XER round-trip_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/projects/{project_id}/activities` | Search activities by ID or name.  Used by the TIA activity picker. | `dict` | optional |
| `GET` | `/api/v1/projects/{project_id}/export/aia-g703` | Export CBS snapshot as an AIA G703 Continuation Sheet workbook. | `—` | optional |
| `GET` | `/api/v1/projects/{project_id}/export/csv` | Export project data as CSV. | `—` | optional |
| `GET` | `/api/v1/projects/{project_id}/export/excel` | Export project schedule data as an Excel workbook. | `—` | optional |
| `GET` | `/api/v1/projects/{project_id}/export/json` | Export project schedule data and analysis results as JSON. | `—` | optional |
| `GET` | `/api/v1/projects/{project_id}/export/xer` | Export a project schedule to XER format for P6 import. | `dict` | optional |

## Benchmarks

_Cross-project percentile comparison_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/benchmarks/compare/{project_id}` | Compare a project's metrics against the benchmark dataset. | `BenchmarkCompareResponse` | optional |
| `POST` | `/api/v1/benchmarks/contribute` | Contribute anonymized schedule metrics to the benchmark database. | `dict` | optional |
| `GET` | `/api/v1/benchmarks/summary` | Get aggregate statistics of the benchmark dataset. | `BenchmarkSummaryResponse` | optional |

## Reports

_PDF generation (10 types) + download_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/projects/{project_id}/available-reports` | Check which report types have data available for a project. | `dict` | optional |
| `POST` | `/api/v1/reports/generate` | Generate a PDF report. Returns report ID for download. | `GenerateReportResponse` | optional |
| `GET` | `/api/v1/reports/{report_id}/download` | Download a generated PDF report. | `—` | optional |

## Admin

_API keys, GDPR deletion_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/api-keys` | List all API keys for the authenticated user. | `dict` | required |
| `POST` | `/api/v1/api-keys` | Generate a new API key for programmatic access. | `dict` | required |
| `DELETE` | `/api/v1/api-keys/{key_id}` | Revoke an API key. | `dict` | required |
| `POST` | `/api/v1/ips/reconcile` | Run IPS reconciliation between a master schedule and sub-schedules. | `dict` | optional |
| `POST` | `/api/v1/recovery/validate` | Validate a recovery schedule against the impacted schedule. | `dict` | optional |
| `DELETE` | `/api/v1/user/data` | Delete all data owned by the authenticated user (GDPR compliance). | `GDPRDeleteResponse` | required |

## Health

_Readiness and liveness_

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/health` | Health check endpoint. | `HealthResponse` | none |
| `GET` | `/health` | — | `—` | none |

## Bi

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/bi/activities` | Flat activity list — one row per activity with CPM-derived metrics. | `dict` | optional |
| `GET` | `/api/v1/bi/dcma-metrics` | One row per (project, DCMA metric) — flat pivot-ready surface. | `dict` | optional |
| `GET` | `/api/v1/bi/projects` | Flat project list with top-level KPIs — one row per project. | `dict` | optional |

## Organizations

| Method | Path | Summary | Response | Auth |
|---|---|---|---|---|
| `GET` | `/api/v1/organizations` | List organizations the current user belongs to. | `—` | optional |
| `POST` | `/api/v1/organizations` | Create a new organization and add the creator as owner. | `—` | optional |
| `GET` | `/api/v1/organizations/{org_id}` | Get organization details including members. | `—` | optional |
| `GET` | `/api/v1/organizations/{org_id}/audit` | Get audit log for an organization. Required for litigation traceability. | `—` | optional |
| `POST` | `/api/v1/organizations/{org_id}/invite` | Invite a user to the organization by email. | `—` | optional |
| `DELETE` | `/api/v1/organizations/{org_id}/members/{member_user_id}` | Remove a member from the organization. | `—` | optional |
| `GET` | `/api/v1/projects/{project_id}/value-milestones` | List all value milestones for a project. | `—` | optional |
| `POST` | `/api/v1/projects/{project_id}/value-milestones` | Create a value milestone linking a schedule milestone to commercial value. | `—` | optional |
| `POST` | `/api/v1/shares/project` | Share a project with another organization. | `—` | optional |
| `GET` | `/api/v1/shares/project/{project_id}` | List all organizations a project is shared with. | `—` | optional |
| `PUT` | `/api/v1/value-milestones/{milestone_id}` | Update a value milestone (status, dates, value). | `—` | optional |

