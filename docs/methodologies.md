# Methodology Catalog

MeridianIQ's analysis stack is **47 engines** plus **1 export module** in `src/export/`. Every engine is a standalone module whose docstring cites the published standard it implements — this catalog is auto-generated from those docstrings.

When a scheduler or forensic analyst asks *"what standard does this calculation follow?"*, the answer is in the engine docstring and in this catalog.

## Index

| Engine | Title |
|---|---|
| [`aia_g702`](#aia-g702--aia-g702) | AIA G702 Application and Certificate for Payment — data model. |
| [`aia_g703`](#aia-g703--aia-g703) | AIA G703 Continuation Sheet — build billing line items from CBS snapshots. |
| [`anomaly_detection`](#anomaly-detection--anomaly-detection) | Anomaly Detection — statistical outlier identification in schedule data. |
| [`benchmark_priors`](#benchmark-priors--benchmark-priors) | Benchmark-derived priors for Monte Carlo risk simulation. |
| [`benchmarks`](#benchmarks--benchmarks) | Benchmark analytics — anonymized cross-project comparison. |
| [`calendar_validation`](#calendar-validation--calendar-validation) | Calendar Validation — work calendar quality and integrity checks. |
| [`cashflow`](#cashflow--cashflow) | Cash flow analysis — cost distribution over time with S-Curve. |
| [`comparison`](#comparison--comparison) | Schedule comparison engine for detecting changes between two XER snapshots. |
| [`contract`](#contract--contract) | Contract compliance checking for delay events. |
| [`cost_integration`](#cost-integration--cost-integration) | Cost-Schedule Integration — CBS/WBS correlation and budget analysis. |
| [`cpm`](#cpm--cpm) | Critical Path Method (CPM) calculator using NetworkX. |
| [`dcma14`](#dcma14--dcma14) | DCMA 14-Point Schedule Assessment. |
| [`delay_attribution`](#delay-attribution--delay-attribution) | Delay Attribution Summary — aggregate delay by responsible party. |
| [`delay_prediction`](#delay-prediction--delay-prediction) | Delay prediction engine — activity-level delay risk scoring. |
| [`duration_prediction`](#duration-prediction--duration-prediction) | ML duration prediction — benchmark-trained project duration forecasting. |
| [`early_warning`](#early-warning--early-warning) | Early Warning System — 12-rule alert engine per GAO Schedule Assessment Guide §9. |
| [`evm`](#evm--evm) | Earned Value Management analysis per ANSI/EIA-748. |
| [`evolution_optimizer`](#evolution-optimizer--evolution-optimizer) | Evolution Strategies optimizer for resource-constrained scheduling. |
| [`float_trends`](#float-trends--float-trends) | Float Trend Analysis engine per AACE RP 49R-06. |
| [`forensics`](#forensics--forensics) | Forensic schedule analysis -- Contemporaneous Period Analysis (CPA). |
| [`half_step`](#half-step--half-step) | Half-Step (Bifurcation) analysis — separating progress from revisions. |
| [`health_score`](#health-score--health-score) | Composite Schedule Health Score per DCMA + GAO. |
| [`ips_reconciliation`](#ips-reconciliation--ips-reconciliation) | Integrated Project Schedule (IPS) Reconciliation Engine. |
| [`lifecycle_phase`](#lifecycle-phase--lifecycle-phase) | Lifecycle phase inference engine (W3 of Cycle 1 v4.0). |
| [`lifecycle_types`](#lifecycle-types--lifecycle-types) | Shared lifecycle vocabulary used by the W3 inference engine, store, API, |
| [`lookahead`](#lookahead--lookahead) | Look-ahead schedule — short-term activity window view. |
| [`mip_additive`](#mip-additive--mip-additive) | AACE RP 29R-03 MIP 3.5 — Modified / Additive Multiple Base. |
| [`mip_observational`](#mip-observational--mip-observational) | AACE RP 29R-03 observational MIPs — 3.1 (Gross) and 3.2 (As-Is). |
| [`mip_subtractive`](#mip-subtractive--mip-subtractive) | AACE RP 29R-03 MIP 3.6 — Modified / Subtractive Single Simulation. |
| [`narrative_report`](#narrative-report--narrative-report) | Narrative report generator — structured text from schedule analysis. |
| [`nlp_query`](#nlp-query--nlp-query) | NLP Schedule Query engine — natural language interface for schedule data. |
| [`pareto`](#pareto--pareto) | Time-cost Pareto analysis — multi-scenario trade-off frontier. |
| [`recovery_validation`](#recovery-validation--recovery-validation) | Recovery Schedule Validation Engine. |
| [`report_generator`](#report-generator--report-generator) | Professional PDF report generator per AACE RP 29R-03 S5.3. |
| [`resource_leveling`](#resource-leveling--resource-leveling) | Resource-constrained project scheduling (RCPSP) via Serial SGS. |
| [`risk`](#risk--risk) | Monte Carlo schedule risk simulation per AACE RP 57R-09. |
| [`risk_register`](#risk-register--risk-register) | Risk register — discrete risk event management and Monte Carlo integration. |
| [`root_cause`](#root-cause--root-cause) | Root Cause Analysis — backwards network trace to delay origin. |
| [`schedule_builder`](#schedule-builder--schedule-builder) | Conversational schedule builder — NLP-driven schedule generation. |
| [`schedule_generation`](#schedule-generation--schedule-generation) | ML schedule generation — auto-generate schedules from project parameters. |
| [`schedule_metadata`](#schedule-metadata--schedule-metadata) | Schedule metadata intelligence — extract update/revision/type from filename and XER data. |
| [`schedule_trends`](#schedule-trends--schedule-trends) | Schedule trend analysis — track evolution across sequential schedule updates. |
| [`schedule_view`](#schedule-view--schedule-view) | Schedule View — pre-computed layout data for interactive Gantt viewer. |
| [`scorecard`](#scorecard--scorecard) | Schedule scorecard — single-page aggregate assessment. |
| [`tia`](#tia--tia) | Time Impact Analysis (TIA) engine. |
| [`visualization`](#visualization--visualization) | 4D visualization data — timeline + WBS spatial layout. |
| [`whatif`](#whatif--whatif) | What-if schedule simulator — deterministic and probabilistic scenario analysis. |

## Engines

### `aia_g702` — Aia G702

**AIA G702 Application and Certificate for Payment — data model.**

Produces the figures for an AIA G702 cover certificate that pairs with a G703 Continuation Sheet. Lines 1–9 of the G702 form are computed from the G703 totals (Total Completed & Stored, Retainage) combined with caller-supplied contract inputs (original contract sum, change orders, previously-certified payments). No PDF rendering is done here — this module is a pure dataclass builder so the figures can be unit-tested and reused by the HTML/PDF renderer.

**Explicit references from docstring:**

- AIA Document G702™-1992 (current edition) — Application and
- Certificate for Payment. https://www.aiacontracts.org/contract-documents/25131-application-for-payment

---

### `aia_g703` — Aia G703

**AIA G703 Continuation Sheet — build billing line items from CBS snapshots.**

Produces the row data for an AIA G703 "Continuation Sheet" (the schedule of values attached to an AIA G702 Application for Payment). Fields that require contractual data not captured in the CBS (retainage %, change orders, previous period billings) are accepted as caller inputs with sensible defaults so the user can still bootstrap a draft G703 from a parsed CBS workbook.

**Explicit references from docstring:**

- AIA Document G703™-1992 (current edition) — Continuation Sheet for G702.
- https://www.aiacontracts.org/contract-documents/25131-application-for-payment

---

### `anomaly_detection` — Anomaly Detection

**Anomaly Detection — statistical outlier identification in schedule data.**

Uses z-score and IQR methods to identify activities with unusual: - Duration (abnormally long or short relative to peers) - Float (unexpected float values given schedule structure) - Progress (physical % complete inconsistent with elapsed time) - Relationships (unusually high or low predecessor/successor count)

Each anomaly is classified by severity (info/warning/critical) and
includes an explanation of why it's flagged.

Standards:
    - DCMA 14-Point — Thresholds for duration and float
    - AACE RP 29R-03 — Schedule manipulation detection patterns
    - Tukey (1977) — Box plot / IQR method for outlier detection

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis
- DCMA 14-Point Schedule Assessment

---

### `benchmark_priors` — Benchmark Priors

**Benchmark-derived priors for Monte Carlo risk simulation.**

Auto-generates DurationRisk specifications from the benchmark database by matching activities to similar projects and deriving empirical uncertainty distributions.  This eliminates the need for manual min/max/most_likely input for every activity.

The approach:
1. Extract metrics from the target schedule.
2. Find benchmarks in the same size category.
3. Compute the coefficient of variation (CV) of key metrics across
   benchmarks to derive a data-driven uncertainty range.
4. Generate DurationRisk entries using PERT distributions calibrated
   to the empirical variance.

**Standards implemented:**

- AACE RP 57R-09 — Integrated Cost/Schedule Risk Analysis

**Explicit references from docstring:**

- AACE RP 57R-09 — Schedule Risk Analysis (enhanced with priors)
- Bayesian updating principles for prior specification

---

### `benchmarks` — Benchmarks

**Benchmark analytics — anonymized cross-project comparison.**

Extracts anonymized aggregate metrics from a schedule and compares them against a benchmark dataset.  All identifying information (project names, activity names, WBS descriptions) is stripped before storage.

The benchmark dataset enables percentile-based comparison:
"Your DCMA score is in the 75th percentile for projects of this size."

**Standards implemented:**

- AACE RP 49R-06 — Identifying Critical Activities
- DCMA 14-Point Schedule Assessment
- GAO Schedule Assessment Guide

**Explicit references from docstring:**

- DCMA 14-Point Assessment — standard metric thresholds
- AACE RP 49R-06 — Float health criteria
- GAO Schedule Assessment Guide — quality indicators

---

### `calendar_validation` — Calendar Validation

**Calendar Validation — work calendar quality and integrity checks.**

Validates P6 work calendar definitions for structural integrity, consistency, and scheduling best practices. A scheduler needs to trust the calendars before trusting float and critical path.

Checks:
    1. Default calendar exists
    2. All tasks reference valid calendar IDs
    3. No orphaned calendars (defined but unused)
    4. Daily/weekly hour consistency (day_hr_cnt × working_days ≈ week_hr_cnt)
    5. Reasonable work hours (not >24h/day or >168h/week)
    6. Non-standard calendars flagged (compressed, extended, etc.)
    7. Calendar diversity (too many calendars can indicate manipulation)
    8. Tasks without calendar assignment

Standards:
    - DCMA 14-Point Assessment — Check #13 (calendar adequacy)
    - GAO Schedule Assessment Guide — Reasonable activity parameters
    - AACE RP 49R-06 — Schedule Health Assessment

**Standards implemented:**

- AACE RP 49R-06 — Identifying Critical Activities
- DCMA 14-Point Schedule Assessment
- GAO Schedule Assessment Guide

---

### `cashflow` — Cashflow

**Cash flow analysis — cost distribution over time with S-Curve.**

Distributes planned and actual costs across the project timeline using CPM-calculated dates and TaskResource cost data.  Produces a cumulative S-Curve for planned vs actual cost tracking.

**Standards implemented:**

- AACE RP 10S-90 — Cost Engineering Terminology

**Explicit references from docstring:**

- AACE RP 10S-90 — Cost Engineering Terminology
- PMI Practice Standard for EVM — Budget at Completion (BAC)
- AACE RP 48R-06 — Schedule Contingency

---

### `comparison` — Comparison

**Schedule comparison engine for detecting changes between two XER snapshots.**

Compares a *baseline* and *update* ``ParsedSchedule`` to identify activity changes, relationship changes, float shifts, constraint modifications, progress issues, and schedule manipulation indicators.

---

### `contract` — Contract

**Contract compliance checking for delay events.**

Checks delay events against standard construction contract provisions per AIA A201, ConsensusDocs 200, and FIDIC conditions.

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis
- AACE RP 52R-06 — Time Impact Analysis

**Explicit references from docstring:**

- AIA A201-2017 General Conditions of the Contract for Construction
- ConsensusDocs 200 Standard Agreement and General Conditions
- FIDIC Conditions of Contract (Red Book, 1999)
- AACE RP 52R-06 Time Impact Analysis
- AACE RP 29R-03 Forensic Schedule Analysis

---

### `cost_integration` — Cost Integration

**Cost-Schedule Integration — CBS/WBS correlation and budget analysis.**

Parses cost breakdown structure (CBS) data from Excel files and correlates with schedule WBS for integrated cost-schedule views.

Supports:
- CBS hierarchy parsing (Level 1, Level 2, Scope, Design Package)
- WBS element budget totals
- CBS-to-WBS mapping extraction
- Budget variance analysis (original vs current)

Reference: AACE RP 10S-90 — Cost Engineering Terminology;
           PMI Practice Standard for EVM — CBS/WBS integration.

**Standards implemented:**

- AACE RP 10S-90 — Cost Engineering Terminology

---

### `cpm` — Cpm

**Critical Path Method (CPM) calculator using NetworkX.**

Builds a directed activity-on-node graph from parsed P6 schedule data, performs forward and backward passes, and identifies the critical path based on total float.

---

### `dcma14` — Dcma14

**DCMA 14-Point Schedule Assessment.**

Implements the Defence Contract Management Agency 14-point check used to assess the health of a project schedule.  Each metric is compared against industry-standard thresholds and the overall result is reported as a composite score.

**Standards implemented:**

- DCMA 14-Point Schedule Assessment

---

### `delay_attribution` — Delay Attribution

**Delay Attribution Summary — aggregate delay by responsible party.**

Provides a claims-ready breakdown of project delay by party (Owner, Contractor, Shared, Third Party, Force Majeure). Designed for the scheduler or claims consultant who needs to answer: "Who caused how much delay, and which activities drove it?"

Works with two data sources:
1. **TIA fragments** — if TIA analysis has been run, uses the explicit
   party assignments from delay fragments.
2. **Standalone estimation** — if no TIA data, infers attribution from
   activity characteristics (out-of-sequence, constraint changes, etc.)

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis
- AACE RP 52R-06 — Time Impact Analysis

**Explicit references from docstring:**

- AACE RP 29R-03 — Forensic Schedule Analysis
- AACE RP 52R-06 — Time Impact Analysis
- SCL Delay and Disruption Protocol, 2nd ed., Core Principles 1-4

---

### `delay_prediction` — Delay Prediction

**Delay prediction engine — activity-level delay risk scoring.**

Extracts schedule features and produces per-activity risk scores with explainable risk factors.  Works in two tiers:

1. **Single-schedule** — rule-based risk scoring using float, logic,
   duration, and network features.  No training data required.
2. **With baseline** — trend-enhanced scoring that detects float
   deterioration, duration growth, and constraint additions.

The risk model uses weighted multi-factor scoring aligned with DCMA
14-Point thresholds, AACE RP 49R-06 float health criteria, and the
GAO Schedule Assessment Guide.

**Standards implemented:**

- AACE RP 49R-06 — Identifying Critical Activities
- DCMA 14-Point Schedule Assessment
- GAO Schedule Assessment Guide

**Explicit references from docstring:**

- DCMA 14-Point Assessment — standard thresholds
- AACE RP 49R-06 — Float Trend Analysis
- GAO Schedule Assessment Guide §7–§9
- Gondia et al. (2021) — Applied AI for Construction Delay Prediction

---

### `duration_prediction` — Duration Prediction

**ML duration prediction — benchmark-trained project duration forecasting.**

Trains a Random Forest + Gradient Boosting ensemble on the benchmark database to predict project duration based on schedule characteristics. Unlike the delay prediction engine (which scores per-activity risk), this engine predicts the expected overall project duration in days based on structural features visible at planning time.

**Explicit references from docstring:**

- AbdElMottaleb (2025) — ML for Construction Scheduling (R²=0.91)
- Gondia et al. (2021) — Applied AI for Construction Delay Prediction
- Breiman (2001) — Random Forests
- Friedman (2001) — Gradient Boosting Machines

---

### `early_warning` — Early Warning

**Early Warning System — 12-rule alert engine per GAO Schedule Assessment Guide §9.**

Runs automatically when two schedule snapshots are available (baseline + update).  Each rule checks a specific schedule health indicator and produces ``Alert`` objects ranked by score.

Standards:
    - GAO Schedule Assessment Guide (2020) §9 — Schedule Surveillance
    - AACE RP 49R-06 — Identifying Critical Activities
    - AACE RP 29R-03 — Forensic Schedule Analysis
    - DCMA 14-Point Assessment — checks #3-#7, #10, #12, #13
    - PMI Practice Standard for Scheduling §6.7 — Resource Management
    - PMI PMBOK 7th Ed §4.6 — Measurement Performance Domain

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis
- AACE RP 49R-06 — Identifying Critical Activities
- DCMA 14-Point Schedule Assessment
- GAO Schedule Assessment Guide
- PMI PMBOK Guide
- PMI Practice Standard for Scheduling

---

### `evm` — Evm

**Earned Value Management analysis per ANSI/EIA-748.**

Calculates standard EVM metrics (SPI, CPI, SV, CV, EAC, ETC, VAC, TCPI) from XER resource assignment data and activity progress. Supports project-level and WBS-level analysis with S-curve generation.

**Standards implemented:**

- AACE RP 10S-90 — Cost Engineering Terminology
- ANSI/EIA-748 — Earned Value Management Systems

**Explicit references from docstring:**

- ANSI/EIA-748: Earned Value Management Systems
- AACE RP 10S-90: Cost Engineering Terminology
- PMI Practice Standard for Earned Value Management
- GAO-16-89G: Schedule Assessment Guide (Chapter 10: EVM Integration)

---

### `evolution_optimizer` — Evolution Optimizer

**Evolution Strategies optimizer for resource-constrained scheduling.**

Uses (mu, lambda) Evolution Strategy to optimize RCPSP solutions beyond the greedy Serial SGS.  The optimizer evolves a population of priority vectors (activity ordering), each decoded through SGS, and selects based on makespan fitness.

**Explicit references from docstring:**

- Loncar (2023) — Evolution Strategies for Task Scheduling
- Hartmann & Kolisch (2000) — RCPSP Benchmark Instances
- Beyer & Schwefel (2002) — Evolution Strategies: A Comprehensive Introduction
- Kolisch (1996) — Serial SGS for RCPSP

---

### `float_trends` — Float Trends

**Float Trend Analysis engine per AACE RP 49R-06.**

Tracks how total float for each activity changes across schedule updates. Float consumption without proportional progress indicates schedule deterioration.  Produces Float Erosion Index, Near-Critical Drift, Critical Path Stability, Float Consumption Velocity per WBS, and per-activity float deltas.

Also provides:
- **Float Entropy** — Shannon entropy of float distribution.  Measures
  how uniformly float is spread across activities.  Low entropy indicates
  float concentrated in few activities (potentially unreliable); high
  entropy indicates even distribution.
- **Constraint Accumulation Rate** — rate of constraint growth between
  schedule updates, indicating potential manipulation via excessive
  constraint additions.

Standards:
    - AACE RP 49R-06 — Identifying Critical Activities
    - PMI Practice Standard for Scheduling §6.6 — Float Management
    - DCMA 14-Point checks #3 (High Float), #4 (Negative Float)
    - Kim & de la Garza (2005) — Phantom float detection
    - Shannon (1948) — A Mathematical Theory of Communication (entropy)
    - DCMA check #10 — Hard Constraints

**Standards implemented:**

- AACE RP 49R-06 — Identifying Critical Activities
- DCMA 14-Point Schedule Assessment
- GAO Schedule Assessment Guide
- PMI Practice Standard for Scheduling

**Explicit references from docstring:**

- GAO Schedule Assessment Guide §7.3 — Critical Path Stability

---

### `forensics` — Forensics

**Forensic schedule analysis -- Contemporaneous Period Analysis (CPA).**

Implements window analysis methodology per AACE RP 29R-03 (Forensic Schedule Analysis) and the SCL Delay and Disruption Protocol.  Divides a project's schedule update history into analysis windows and quantifies delay per window.

Supports both MIP 3.3 (standard CPA) and MIP 3.4 (bifurcated / half-step
analysis) which separates delay into progress and revision effects.

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis

**Explicit references from docstring:**

- AACE RP 29R-03 Forensic Schedule Analysis, MIP 3.3 and MIP 3.4
- SCL Delay and Disruption Protocol, 2nd ed., Core Principle 2
- Ron Winter PS-1264 "Creating Half-Step Schedules Using P6 Baseline Update"

---

### `half_step` — Half Step

**Half-Step (Bifurcation) analysis — separating progress from revisions.**

Implements the bifurcation technique per AACE RP 29R-03 MIP 3.4 (Contemporaneous Split Analysis).  Given two consecutive schedule updates (Schedule A and Schedule B), creates an intermediate "half-step" schedule that isolates the effect of actual progress from the effect of logic/plan revisions.

The half-step schedule (A-1/2) is built by cloning Schedule A and applying
**only** progress-related fields from Schedule B (actuals, remaining
duration proportional to progress, status).  Logic, relationships,
calendars, constraints, and scope changes are deliberately excluded.

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis

**Explicit references from docstring:**

- AACE RP 29R-03 Forensic Schedule Analysis, MIP 3.4
- Ron Winter PS-1264 "Creating Half-Step Schedules Using P6 Baseline Update"
- Ron Winter PS-1197 "Introducing the Zero-Step Schedule"
- SCL Delay and Disruption Protocol, 2nd ed., Time Slice Window Analysis

---

### `health_score` — Health Score

**Composite Schedule Health Score per DCMA + GAO.**

Produces a single 0–100 score answering "how healthy is this schedule?" by combining structural quality (DCMA 14-point), float distribution, logic integrity, and trend direction.

Formula:
    Health = 0.40 * DCMA_Score + 0.25 * Float_Health
           + 0.20 * Logic_Integrity + 0.15 * Trend_Direction

Standards:
    - DCMA 14-Point Assessment — structural quality
    - AACE RP 49R-06 — Float distribution and consumption
    - DCMA checks #6, #7 — Logic completeness
    - GAO Schedule Assessment Guide §9 — Trend surveillance
    - GAO 4 Characteristics: Comprehensive, Well-constructed, Credible, Controlled

**Standards implemented:**

- AACE RP 49R-06 — Identifying Critical Activities
- DCMA 14-Point Schedule Assessment
- GAO Schedule Assessment Guide

---

### `ips_reconciliation` — Ips Reconciliation

**Integrated Project Schedule (IPS) Reconciliation Engine.**

Verifies consistency between a master schedule and sub-schedules. Per AACE Recommended Practice 71R-12 — Required Skills and Knowledge of Integrated Project Schedule Development.

The IPS reconciliation checks:
1. Milestone alignment — do sub-schedule milestones match master dates?
2. Interface point consistency — are handoff activities aligned?
3. Logic continuity — are cross-schedule dependencies maintained?
4. Date consistency — do sub completion dates align with master windows?
5. WBS alignment — do sub WBS elements map to master WBS?
6. Float consistency — does sub float align with master float allowance?

---

### `lifecycle_phase` — Lifecycle Phase

**Lifecycle phase inference engine (W3 of Cycle 1 v4.0).**

Classifies a parsed P6 XER schedule into one of the canonical lifecycle phases ``planning / design / procurement / construction / closeout`` (or ``unknown`` when the input lacks the minimum signal). Output is a :class:`LifecyclePhaseInference` carrying the phase, a confidence in ``[0.0, 1.0]``, and a JSON-serialisable rationale dict listing the signals and the triggered rule.

Per ADR-0009 §Wave-3 + ADR-0016 the engine is intentionally lightweight —
the deep phase-aware analytics live in the W5/W6 conditional
``lifecycle_health.py`` engine. W3 ships only the label inference + a
confidence score that is honest about uncertainty.

Standards cited:

- AACE RP 14R §3 (planning-phase ownership delineation — anchors the
  early-phase signal: planning vs design depends on baseline availability
  and on whether the schedule shows discipline-segregated WBS depth).
- ISO 21502 §6.3 (project lifecycle as first-class metadata — informs
  the 5-phase taxonomy choice over a finer-grained PMI-CP mapping).
- PMI Construction Extension §4 — referenced as "mappable to" in the
  rationale dict; not claimed as alignment because PMI-CP uses different
  phase names (initiating / planning / executing / monitoring / closing).
- W4 calibration gate (ADR-0009 §Gate-criteria): ``confidence >= 0.80``
  is the gate-passing band. Confidence values returned here MUST be
  honest about uncertainty so the gate's ``>=80%`` filter is meaningful.

The engine is **stateless** per CLAUDE.md ``Code Standards`` ("Analysis
engines in src/analytics/ must be stateless — receive data, return
results"). Hysteresis to suppress phase flip-flops between consecutive
uploads is a W4+ follow-up that lives at the *materializer* layer
(which has access to prior artifacts), NOT inside this engine.

Multi-project XER scope: this engine evaluates ``schedule.projects[0]``
and that project's activities. ADR-0015 §1 acknowledges multi-project
XERs as Wave 3+ scope — the materializer raises if it encounters one.
Inference of multi-project rollup phase is out of scope.

---

### `lifecycle_types` — Lifecycle Types

**Shared lifecycle vocabulary used by the W3 inference engine, store, API,**

and (conditional on W4 gate) the W5/W6 ``lifecycle_health.py`` deep engine.

Per ADR-0016 §2 the type live in ``src.analytics.lifecycle_types`` so any
downstream engine can import the vocabulary without importing the inference
engine itself — preserving the standalone-engine invariant ADR-0009 §Wave-3
established for ``src/analytics/`` (no engine imports another engine; the
materializer is the composition layer).

Phase taxonomy: 5 + ``unknown`` per ADR-0016 §1. The construction
sub-phase split (early / mid / late) is intentionally NOT a phase value
in W3 — W4 sandbox calibration would crater on a 9-value classifier with
the available signal density. ADR-0016 reserves the construction-band
concept as a *derived dimension* for the W5 ``lifecycle_health.py`` engine
should the W4 gate pass.

Standards cited:

- AACE RP 14R §3 — planning-phase ownership delineation as the baseline
  signal that anchors phase inference at the front of the lifecycle.
- ISO 21502 §6.3 — project lifecycle as first-class metadata.
- PMI Construction Extension §4 — referenced as "mappable to" in the engine
  docstring; not claimed as alignment because PMI-CP uses different phase
  names (initiating / planning / executing / monitoring / closing) and the
  mapping has not been formally walked.

SCL Protocol §4 is cited on the override-log audit trail (migration 025),
NOT on the phase taxonomy itself.

**Standards implemented:**

- SCL Delay and Disruption Protocol

---

### `lookahead` — Lookahead

**Look-ahead schedule — short-term activity window view.**

Filters activities to a configurable time window (typically 2-4 weeks) relative to the data date, providing construction managers and field teams with a focused view of near-term work.

**Standards implemented:**

- PMI Practice Standard for Scheduling

**Explicit references from docstring:**

- PMI Practice Standard for Scheduling — Look-Ahead Planning
- Lean Construction Institute — Last Planner System (LPS)

---

### `mip_additive` — Mip Additive

**AACE RP 29R-03 MIP 3.5 — Modified / Additive Multiple Base.**

Implements the "Impacted As-Planned, Multiple Base" method per AACE Recommended Practice 29R-03 §3.5.  For each analysis window (pair of consecutive schedule updates), the caller attributes delay events (activity + days) to that window.  The engine clones the window's baseline (first schedule of the pair), *extends* each affected activity's duration by the event days, re-runs CPM, and reports the impact as the difference between the impacted completion and the original (as-planned) baseline completion.

This mirrors ``mip_subtractive`` in structure but applies additive
rather than subtractive edits — i.e. "add these delay events to the
schedule and measure the resulting slippage" vs. MIP 3.6/3.7's "remove
these delay events and measure the but-for completion".

The method is **subjective** in that the caller identifies the delay
events; the computation of the impacted completion is deterministic
once the events are fixed.

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis

**Explicit references from docstring:**

- AACE RP 29R-03 §3.5 (Modified / Additive Multiple Base).
- SCL Delay and Disruption Protocol 2nd ed. §22.2 (Impacted
- As-Planned Analysis).

---

### `mip_observational` — Mip Observational

**AACE RP 29R-03 observational MIPs — 3.1 (Gross) and 3.2 (As-Is).**

Implements the two observational Methods of Implementation per AACE Recommended Practice 29R-03 (Forensic Schedule Analysis):

- **MIP 3.1 — Observational / Static Logic / Gross**.  The most abridged
  forensic method.  Pairs the earliest as-planned schedule with the
  latest as-built schedule and reports gross delay, critical-path shift,
  and activity inventory deltas.  No intermediate updates are examined.

- **MIP 3.2 — Observational / Dynamic Logic / Contemporaneous As-Is**.
  Walks every schedule update chronologically, observing completion
  date movement and critical-path evolution at each data date without
  splitting the project into discrete windows.  Output is a narrative
  event stream rather than a window-by-window decomposition (that is
  MIP 3.3's job).

Both methods are *observational* — neither alters the schedules.  They
rely on the existing CPM calculator and schedule comparison engine.

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis

**Explicit references from docstring:**

- AACE RP 29R-03 §3.1 (Static Logic Gross), §3.2 (Dynamic Logic As-Is).
- SCL Delay and Disruption Protocol, 2nd ed. (2017) — time-slice
- methodology alignment.

---

### `mip_subtractive` — Mip Subtractive

**AACE RP 29R-03 MIP 3.6 — Modified / Subtractive Single Simulation.**

Implements the "Collapsed As-Built" method per AACE Recommended Practice 29R-03 §3.6.  Starting from the as-built schedule, the caller names the activities (and delay amounts) they attribute to specific events.  The engine shortens each affected activity's duration by the stated amount and re-runs CPM, yielding a "but-for" completion date: *what the project completion would have been had those delay events not occurred*.

The method is **subjective** in that the caller identifies the delay
events; the computation of the but-for completion is deterministic once
the events are fixed.  This matches how owner-side counsel typically
prepares a collapsed as-built: the analyst chooses which delays to
"remove" and the tool measures the impact.

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis

**Explicit references from docstring:**

- AACE RP 29R-03 §3.6 (Modified / Subtractive Single Simulation).
- SCL Delay and Disruption Protocol 2nd ed. §22.4 (Collapsed As-Built
- Analysis).

---

### `narrative_report` — Narrative Report

**Narrative report generator — structured text from schedule analysis.**

Generates professional schedule narrative text for: - Monthly status reports - Claims documentation (delay analysis narrative) - Executive summaries - Scorecard commentary

Reference: AACE RP 29R-03 — Forensic Schedule Analysis (narrative requirements);
           SCL Protocol — Delay Analysis presentation standards.

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis
- SCL Delay and Disruption Protocol

---

### `nlp_query` — Nlp Query

**NLP Schedule Query engine — natural language interface for schedule data.**

Allows users to ask questions about a schedule in plain language. Uses Claude API to interpret the question, extract relevant data, and generate a human-readable answer grounded in the schedule facts.

The engine does NOT send raw schedule data to the API. Instead, it:
1. Pre-computes a structured summary of the schedule
2. Sends the summary + user question to Claude
3. Returns the answer with citations to specific activities

This approach minimizes token usage and prevents sensitive data exposure.

Standards:
    - PMI PMBOK 7 S4.6 — Measurement Performance Domain
    - DCMA 14-Point — Referenced in answers where applicable

**Standards implemented:**

- DCMA 14-Point Schedule Assessment
- PMI PMBOK Guide

---

### `pareto` — Pareto

**Time-cost Pareto analysis — multi-scenario trade-off frontier.**

Runs multiple what-if scenarios with associated cost impacts and computes the Pareto-optimal frontier (non-dominated solutions) on the time-vs-cost plane.  Points on the frontier represent scenarios where no other scenario is both cheaper and shorter.

**Standards implemented:**

- PMI Practice Standard for Scheduling

**Explicit references from docstring:**

- AACE RP 36R-06 — Cost Estimate Classification
- PMI Practice Standard for Scheduling — Time-Cost Trade-off
- Kelley & Walker (1959) — Critical Path Planning and Scheduling

---

### `recovery_validation` — Recovery Validation

**Recovery Schedule Validation Engine.**

Per AACE Recommended Practice 29R-03 Section 4 — Recovery Schedule Analysis.

A recovery schedule is submitted by a contractor to demonstrate how they
plan to recover from delay. This engine validates whether the recovery
plan is reasonable, achievable, and properly linked to the impacted schedule.

Checks:
1. Duration reasonableness — are recovery durations unrealistically compressed?
2. Logic integrity — does the recovery maintain proper predecessor/successor logic?
3. Resource loading — are resources overloaded beyond reasonable capacity?
4. Calendar compliance — does recovery respect work calendar constraints?
5. Float consumption — does recovery eliminate all available float?
6. Scope consistency — are activities added/removed vs the impacted schedule?

---

### `report_generator` — Report Generator

**Professional PDF report generator per AACE RP 29R-03 S5.3.**

Generates court-submittable reports with: - Executive summary (auto-generated) - Methodology statement with standard citations - Data summary (project info, data date, activity count) - Analysis results (tables, findings) - Conclusions & recommendations

Supports 6 report types:
1. Schedule Health Report: DCMA results, health score, float distribution, alerts
2. Comparison Report: Delta summary, manipulation indicators, changes by WBS
3. Forensic Report: Timeline, delay waterfall, windows analysis
4. TIA Report: Fragment analysis, CP impact, compliance check
5. Risk Report: Monte Carlo results, P-values, sensitivity
6. Monthly Review Report: Standardized monthly update narrative with
   progress, health, comparison delta, alerts, and action items

Standards:
    - AACE RP 29R-03 S5.3 -- Documentation
    - CMAA (2019) S7 -- Reporting
    - DCMA 14-Point Assessment -- Schedule quality metrics
    - AACE RP 52R-06 -- Time Impact Analysis
    - AACE RP 57R-09 -- Schedule Risk Analysis
    - PMI PMBOK 7 S4.6 -- Measurement Performance Domain

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis
- AACE RP 52R-06 — Time Impact Analysis
- AACE RP 57R-09 — Integrated Cost/Schedule Risk Analysis
- DCMA 14-Point Schedule Assessment
- PMI PMBOK Guide

---

### `resource_leveling` — Resource Leveling

**Resource-constrained project scheduling (RCPSP) via Serial SGS.**

Solves the resource-constrained scheduling problem using a Serial Schedule Generation Scheme (SGS).  Activities are scheduled in priority order at their earliest feasible start time, subject to both precedence and resource constraints.

The algorithm:
1. Run unconstrained CPM to get the baseline schedule.
2. Build resource demand per activity from TaskResource data.
3. Iterate through activities in priority order (configurable rule).
4. For each activity, find the earliest start where resource capacity
   is not exceeded for the activity's full duration.
5. Re-compute floats on the leveled schedule.

**Standards implemented:**

- AACE RP 46R-11 — Scheduling Professional Skills
- PMI Practice Standard for Scheduling

**Explicit references from docstring:**

- AACE RP 46R-11 — Required Skills and Knowledge of a Scheduling
- Professional (resource analysis)
- PMI Practice Standard for Scheduling — Resource Leveling
- Kelley & Walker (1959) — CPM with Resource Constraints
- Kolisch (1996) — Serial and Parallel SGS for RCPSP

---

### `risk` — Risk

**Monte Carlo schedule risk simulation per AACE RP 57R-09.**

Implements Quantitative Schedule Risk Analysis (QSRA) using Monte Carlo simulation.  Samples activity durations from probability distributions, runs CPM for each iteration, and produces completion date probability distributions, criticality indices, and sensitivity analysis.

**Standards implemented:**

- AACE RP 57R-09 — Integrated Cost/Schedule Risk Analysis
- AACE RP 41R-08 — Risk Analysis and Contingency
- AACE RP 65R-11 — Monte Carlo Risk Analysis

**Explicit references from docstring:**

- AACE RP 57R-09: Integrated Cost and Schedule Risk Analysis
- AACE RP 41R-08: Risk Analysis and Contingency Determination
- AACE RP 65R-11: Integrated Cost and Schedule Risk Analysis Using
- Monte Carlo Simulation

---

### `risk_register` — Risk Register

**Risk register — discrete risk event management and Monte Carlo integration.**

Manages a register of identified risks with probability, impact, responsible party, and mitigation plans.  Risk entries can be converted to ``RiskEvent`` objects for Monte Carlo simulation (AACE RP 57R-09).

**Standards implemented:**

- AACE RP 57R-09 — Integrated Cost/Schedule Risk Analysis

**Explicit references from docstring:**

- AACE RP 57R-09 — Schedule Risk Analysis (discrete risk events)
- PMI Practice Standard for Risk Management
- ISO 31000 — Risk Management Framework

---

### `root_cause` — Root Cause

**Root Cause Analysis — backwards network trace to delay origin.**

Walks backwards through the schedule dependency network from a target activity (typically the project completion milestone) to identify the chain of driving predecessors that determine the project end date.

At each step, the *driving predecessor* is the predecessor whose
early finish + lag produces the latest early start for the successor
(i.e., the predecessor that actually controls when work can begin).

The result is an ordered chain from target back to root cause — the
activity or constraint that ultimately drives the project completion.

Standards:
    - AACE RP 49R-06 — Identifying Critical Activities
    - AACE RP 29R-03 — Forensic Schedule Analysis (root cause identification)
    - PMI Practice Standard for Scheduling §6 — Critical Path Method

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis
- AACE RP 49R-06 — Identifying Critical Activities
- PMI Practice Standard for Scheduling

---

### `schedule_builder` — Schedule Builder

**Conversational schedule builder — NLP-driven schedule generation.**

Uses Claude API to interpret a natural language project description and extract structured parameters, then calls the schedule generation engine to produce a complete schedule.

**Standards implemented:**

- PMI Practice Standard for Scheduling

**Explicit references from docstring:**

- AbdElMottaleb (2025) — ML for Construction Scheduling
- PMI Practice Standard for Scheduling — Schedule Development

---

### `schedule_generation` — Schedule Generation

**ML schedule generation — auto-generate schedules from project parameters.**

Uses Random Forest models trained on the benchmark database to predict activity durations and logical relationships based on project characteristics. Generates a complete ParsedSchedule compatible with all analysis engines.

The approach follows AbdElMottaleb (2025) methodology:
1. Given project type + size → predict number of activities per WBS area
2. Given activity features → predict durations (RF regressor)
3. Given activity pairs → predict relationships (RF classifier)
4. Assemble into a complete ParsedSchedule with CPM validation

**Standards implemented:**

- PMI Practice Standard for Scheduling

**Explicit references from docstring:**

- AbdElMottaleb (2025) — ML for Construction Scheduling (R²=0.91)
- Breiman (2001) — Random Forests
- PMI Practice Standard for Scheduling — Schedule Development

---

### `schedule_metadata` — Schedule Metadata

**Schedule metadata intelligence — extract update/revision/type from filename and XER data.**

Detects: - Update number (UP 01, UP 02, ...) - Revision number (Rev 00 = draft, Rev 01+ = final) - Schedule type: MPS (Master Program Schedule), IMS (Integrated Master Schedule),   CMAR (Contractor Schedule), Baseline, Draft - Data date from XER PROJECT table - Baseline presence (target_start_date / target_end_date fields) - Schedule series grouping (same project across time)

Reference: AACE RP 49R-06 — Identifying the Critical Path.

**Standards implemented:**

- AACE RP 49R-06 — Identifying Critical Activities

---

### `schedule_trends` — Schedule Trends

**Schedule trend analysis — track evolution across sequential schedule updates.**

Computes period-over-period trends for a series of schedule submissions: - Activity count growth (scope creep indicator) - Float erosion (schedule compression) - Completion progress (earned schedule) - Critical path length and count - Relationship density - Schedule quality score

Reference: AACE RP 29R-03 — Forensic Schedule Analysis;
           DCMA 14-Point Assessment (trending checks over time).

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis
- DCMA 14-Point Schedule Assessment

---

### `schedule_view` — Schedule View

**Schedule View — pre-computed layout data for interactive Gantt viewer.**

Builds a WBS tree hierarchy, flattens activities with indent levels, and computes layout data optimized for the frontend ScheduleViewer component.  All date math and sorting happens server-side so the frontend only needs to render.

**Standards implemented:**

- AACE RP 49R-06 — Identifying Critical Activities
- DCMA 14-Point Schedule Assessment
- GAO Schedule Assessment Guide

**Explicit references from docstring:**

- AACE RP 49R-06 — Identifying Critical Activities
- DCMA 14-Point Assessment — Schedule structure metrics
- GAO Schedule Assessment Guide — Activity hierarchy

---

### `scorecard` — Scorecard

**Schedule scorecard — single-page aggregate assessment.**

Combines outputs from DCMA 14-Point, Health Score, Delay Prediction, and Benchmark Comparison into a unified letter-grade scorecard with actionable recommendations.

The scorecard provides a quick "executive summary" of schedule quality
across five dimensions, each scored 0-100 and graded A-F.

**Standards implemented:**

- AACE RP 57R-09 — Integrated Cost/Schedule Risk Analysis
- AACE RP 49R-06 — Identifying Critical Activities
- DCMA 14-Point Schedule Assessment
- GAO Schedule Assessment Guide

**Explicit references from docstring:**

- DCMA 14-Point Assessment — schedule validation standard
- GAO Schedule Assessment Guide — 4 characteristics of a reliable schedule
- AACE RP 49R-06 — Schedule Health Assessment
- AACE RP 57R-09 — Schedule Risk Analysis

---

### `tia` — Tia

**Time Impact Analysis (TIA) engine.**

Implements prospective delay analysis per AACE RP 52R-06 and AACE RP 29R-03. Inserts delay fragments into a schedule network and measures the impact on the project completion date.

Methodology:
1. Load base schedule -> run CPM -> unimpacted completion
2. For each delay fragment:
   a. Copy the schedule network graph
   b. Insert fragment activities and relationships
   c. Run CPM on impacted network -> impacted completion
   d. Delay = impacted - unimpacted completion
3. Detect concurrent delays (overlapping fragments on CP)
4. Classify by responsibility

**Standards implemented:**

- AACE RP 29R-03 — Forensic Schedule Analysis
- AACE RP 52R-06 — Time Impact Analysis

**Explicit references from docstring:**

- AACE RP 52R-06 Time Impact Analysis -- As Applied in Construction
- AACE RP 29R-03 Forensic Schedule Analysis

---

### `visualization` — Visualization

**4D visualization data — timeline + WBS spatial layout.**

Produces a structured dataset that maps activities to a 2D spatial grid (WBS hierarchy × time) suitable for rendering as a 4D-style chart. Activities are positioned by their WBS path (Y-axis) and CPM dates (X-axis), with color coding by status, float level, or risk score.

**Standards implemented:**

- AACE RP 49R-06 — Identifying Critical Activities
- PMI Practice Standard for Scheduling

**Explicit references from docstring:**

- PMI Practice Standard for Scheduling — Gantt Chart Extensions
- AACE RP 49R-06 — Float Trend Visualization

---

### `whatif` — Whatif

**What-if schedule simulator — deterministic and probabilistic scenario analysis.**

Applies duration adjustments to selected activities, re-runs CPM, and returns the impact on project duration, critical path, and per-activity dates.  Supports two modes:

1. **Deterministic** — single adjustment per activity, one CPM run.
2. **Probabilistic** — sample adjustments from a range, run CPM N times,
   return distribution with P-values.

The simulator uses the existing CPM engine (fully reentrant) to compute
each scenario.

**Standards implemented:**

- AACE RP 57R-09 — Integrated Cost/Schedule Risk Analysis
- PMI PMBOK Guide
- PMI Practice Standard for Scheduling

**Explicit references from docstring:**

- AACE RP 57R-09 — Schedule Risk Analysis (scenario modelling)
- PMI PMBOK 7 S4.6 — Measurement Performance Domain
- PMI Practice Standard for Scheduling — What-If Analysis

---

## Export Modules

### `xer_writer` — Xer Writer

**Oracle P6 XER file writer.**

Writes a ParsedSchedule back to XER format for import into Primavera P6. Supports writing original, modified (post what-if / post-leveling), and generated schedules.

XER format structure:
    ERMHDR      ...                         (file header)
    %T  TABLE_NAME                   (table start)
    %F  field1  field2  ...          (field names)
    %R  val1    val2    ...              (data row)
    ...
    %E                               (end of file)

**Explicit references from docstring:**

- Oracle Primavera P6 XER Format (de facto standard)

---


Regenerate with: `python3 scripts/generate_methodology_catalog.py`
