# Changelog

All notable changes to MeridianIQ are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — v2.1 — Prediction & Advanced Forensics

### Added
- Half-step bifurcation analysis (AACE RP 29R-03 MIP 3.4) — separates delay into progress effect vs revision effect (`src/analytics/half_step.py`)
- `POST /api/v1/forensic/half-step` endpoint for standalone bifurcation analysis
- `ForensicAnalyzer(bifurcated=True)` mode for integrated MIP 3.4 CPA
- MCP Server: 10th tool `run_half_step` for Claude integration
- Forensic PDF report: bifurcation section with progress/revision table and KPIs
- Frontend: bifurcation chart (progress blue vs revision amber bars) on forensic timeline page
- Frontend: progress/revision columns in forensic window analysis table
- `HalfStepResponse` types and API client in frontend
- 32 new tests for half-step analysis (classification, schedule creation, full analysis, real XER files, edge cases, PDF rendering)
- Delay prediction engine — activity-level risk scoring with 35 features, weighted multi-factor model, SHAP-like explainable risk factors (`src/analytics/delay_prediction.py`)
- `GET /api/v1/projects/{id}/delay-prediction` endpoint with optional baseline enhancement
- MCP Server: 11th tool `predict_delays` for Claude integration
- 30 new tests for delay prediction (scoring quality, risk factors, baseline enhancement, edge cases)

## [2.0.0] — 2026-04-02 — AI

### Added
- NLP schedule queries via Claude API (`POST /api/v1/projects/{id}/ask`)
- Anomaly detection engine — IQR/z-score outlier detection (`GET /api/v1/projects/{id}/anomalies`)
- Root cause analysis — backwards network trace to delay origin (`GET /api/v1/projects/{id}/root-cause`)
- MCP Server with 9 tools for Claude Code integration (`src/mcp_server.py`)
- API keys for programmatic access (self-service CRUD endpoints)
- Float entropy metric — Shannon entropy of float distribution
- Constraint accumulation rate — detect constraint growth between updates
- JSON/CSV export endpoints for structured data download
- Monthly review PDF report (6th report type)
- 6 reusable SVG chart components (BarChart, PieChart, GaugeChart, ScatterChart, WaterfallChart, TimelineChart)
- Charts integrated into 8 frontend pages (project detail, dashboard, compare, EVM, contract, IPS, recovery)
- Sandbox mode for test data isolation (upload toggle + API filter)
- CORS whitelist (replaced wildcard `*`)
- Security headers middleware (HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy)
- Rate limiting via slowapi (60 req/min default)
- Upload file size limit (50MB)
- RLS policy fixes for 5 tables that had zero policies (migration 011)
- API keys table with RLS (migration 012)
- Deploy checklist document (`docs/DEPLOY_CHECKLIST.md`)

### Fixed
- Forensic PDF report: ForensicAnalyzer constructor args + window attribute path
- Lint: removed unused imports across new modules

## [1.1.0] — 2026-03-30 — UX Maturity

### Added
- Value milestones frontend page with CRUD
- Compare page: manipulation scoring badges (Normal/Suspicious/Red Flag)
- Sidebar grouping (Analysis / Enterprise / Settings sections)
- Toast notification system (`$lib/toast.ts` + `ToastContainer.svelte`)
- i18n wiring connected to landing, upload, and dashboard pages
- Projects list: search, sort by name/activities/relationships, filter

## [1.0.0] — 2026-03-29 — Enterprise

### Added
- Organizations with roles and memberships
- Project sharing with granular permissions
- IPS Reconciliation (master + sub-schedule alignment per AACE RP 71R-12)
- Recovery schedule validation (compression analysis)
- Audit trail logging
- Multi-format support (Microsoft Project XML via native parser)
- Value milestones (commercial value, payment triggers)

## [0.9.0] — 2026-03-28 — Polish

### Added
- Responsive sidebar with mobile hamburger menu
- CI/CD pipeline (GitHub Actions: test, lint, build, deploy)
- E2E tests (Playwright, 25 tests)
- Sentry + PostHog integration
- Documentation site (/docs route, 10 sections)
- Onboarding flow (3-step guided)
- i18n infrastructure (EN, PT-BR, ES)
- Anonymous demo mode (/demo route)
- Account settings page
- Cold start fix (retry with backoff + warm-up banner)

## [0.8.0] — 2026-03-27 — Intelligence

### Added
- Float trend tracking across sequential uploads
- Early Warning System (12 configurable alert rules)
- Schedule Health Score (composite 0-100 metric)
- PDF Reports (5 types via WeasyPrint)
- Auto-pipeline (upload → parse → validate → compute → alert)

## [0.7.0] — 2026-03-26 — Identity

### Added
- Google + Microsoft + LinkedIn OAuth via Supabase Auth
- Row Level Security (RLS) policies
- API authentication (Bearer token)
- Frontend auth flow (login, OAuth redirect, session, logout)

## [0.6.0] — 2026-03-25 — Cloud

### Added
- Supabase PostgreSQL (persistent data, RLS)
- Supabase Storage (XER files, PDFs)
- Fly.io deployment (Docker container)
- Cloudflare Pages deployment (SvelteKit)

## [0.5.0] — 2026-03-24 — Risk

### Added
- Monte Carlo QSRA simulation (AACE RP 57R-09)

## [0.4.0] — 2026-03-23 — Controls

### Added
- Earned Value Management (SPI, CPI, EAC, S-Curve per ANSI/EIA-748)

## [0.3.0] — 2026-03-22 — Claims

### Added
- Time Impact Analysis (AACE RP 52R-06)
- Contract Compliance checking

## [0.2.0] — 2026-03-21 — Forensics

### Added
- Forensic CPA / Window Analysis (AACE RP 29R-03)

## [0.1.0] — 2026-03-20 — Foundation

### Added
- XER Parser (streaming, encoding detection, composite keys)
- CPM Calculator (NetworkX forward/backward pass)
- DCMA 14-Point Assessment
- Schedule Comparison engine
- SvelteKit frontend (initial routes)
