# Analysis Workflow

Forensic pipeline from initial upload through risk simulation. Each stage answers a specific scheduling question and feeds the next. Use this as the reference sequence for a claim preparation or monthly review.

## The pipeline

```
Upload → DCMA 14-Point → CPM → Compare → CPA → TIA → EVM → Monte Carlo → Narrative
         (structure)     (dates)  (change) (delay) (what-if) (cost)  (risk)      (report)
```

You don't need to run every step for every project. The sections below are keyed to common workflows.

## 1. DCMA 14-Point — is this schedule well-formed?

**When:** Always, as soon as a schedule is uploaded.

**Answers:** Are there logic gaps? Too many hard constraints? Excessive lags? Activities with > 44 days of float that signal missing constraints?

**Endpoint:** `GET /api/v1/projects/{id}/validation`
**Standard:** DCMA 14-Point Schedule Assessment
**Engine:** `src/analytics/dcma14.py`

Output: 14 metric results with thresholds, a composite score (0–100), and pass / fail indicators per check. A score < 80 is a red flag for a schedule about to enter contract review or forensic analysis.

## 2. CPM — what's the critical path?

**When:** Always — implicitly run on every upload.

**Answers:** Which activities are on the longest path? What are the float values across the network?

**Endpoint:** `GET /api/v1/projects/{id}/critical-path`
**Standard:** Kelly & Walker (1959)
**Engine:** `src/analytics/cpm.py` (NetworkX-backed forward / backward pass)

The CPM result is cached on first call (`analysis_results` table). Subsequent requests return instantly unless `?force=true` is passed.

## 3. Compare — what changed between two revisions?

**When:** Every monthly update.

**Answers:** Which activities were added, deleted, or modified? Were task codes restructured? Are there signs of manipulation (retroactive dates, out-of-sequence progress, constraint masking, duration inflation)?

**Endpoint:** `POST /api/v1/compare` with `{baseline_id, update_id}`
**Engine:** `src/analytics/comparison.py`

The comparison engine uses **multi-layer matching**:

1. Tier 1: match by `task_id` (P6's internal ID, stable across updates)
2. Tier 2: match by `task_code` (visible ID, human-assigned)
3. Unmatched in both tiers → genuinely added / deleted

A task matched in Tier 1 but with a different `task_code` triggers a **code restructuring** alert — a common signal when a scheduler renames work to obscure slippage.

Manipulation flags are surfaced as-is; the engine does not assign blame, only evidence. See `ScheduleComparison.compare` for the full flag list.

## 4. CPA — how did delay accumulate?

**When:** Claim preparation. Three or more consecutive updates required.

**Answers:** Which window (pair of updates) contributed the most delay to the project completion date? How did the critical path evolve across the timeline?

**Endpoint:** `POST /api/v1/forensic/create-timeline` with a list of project IDs in chronological order
**Standard:** AACE RP 29R-03 — Contemporaneous Period Analysis
**Engine:** `src/analytics/forensics.py`

Output: a timeline object with per-window delta completion dates, changes to the CP, and a **delay waterfall** showing cumulative slip. Also available: MIP 3.4 half-step bifurcation (separates progress effects from logic revisions) — `POST /api/v1/forensic/half-step`.

## 5. TIA — what was the prospective impact of a delay event?

**When:** Change order or claim for a specific delay fragment.

**Answers:** If this delay hadn't happened, what would the completion date have been? Is the delay excusable, compensable, non-excusable, or concurrent?

**Endpoint:** `POST /api/v1/tia/analyze` with the base project ID and a fragment (activities + relationships)
**Standard:** AACE RP 52R-06 — Time Impact Analysis
**Engine:** `src/analytics/tia.py`

The engine copies the schedule network, inserts the fragment, re-runs CPM, and reports:

- Impacted completion date vs. unimpacted
- Affected activities on the critical path
- Classification: excusable-compensable / excusable non-compensable / non-excusable / concurrent
- Responsibility waterfall by party

## 6. EVM — how does cost compare to schedule progress?

**When:** Project has resource assignments with cost and budget data.

**Answers:** Is the project ahead or behind schedule (SPI)? Over or under budget (CPI)? What's the forecast EAC?

**Endpoint:** `POST /api/v1/evm/analyze/{project_id}`
**Standard:** ANSI/EIA-748 + AACE RP 10S-90
**Engine:** `src/analytics/evm.py`

Produces: SPI, CPI, SV, CV, EAC, ETC, VAC, TCPI, plus an S-curve (`/evm/analyses/{id}/s-curve`) and WBS drill-down. Render the S-curve via the `EVMSCurveChart` component on the `/evm/{id}` page.

## 7. Monte Carlo QSRA — what's the range of possible outcomes?

**When:** Risk review — commonly quarterly, or before a milestone commitment.

**Answers:** What's the P50 / P80 / P90 completion date? Which activities contribute most to end-date variance? What's the criticality index (% of iterations where each activity was on CP)?

**Endpoint:** `POST /api/v1/risk/simulate/{project_id}` with risk inputs
**Standard:** AACE RP 57R-09
**Engine:** `src/analytics/risk.py` (NumPy-backed PERT-Beta sampling, 1000 iterations default)

If you don't have explicit duration-risk inputs per activity, use `benchmark_priors.py` to derive them from anonymized cross-project percentiles.

Output: completion histogram, tornado diagram (Spearman rank correlation), criticality index, and cumulative S-curve.

## 8. Narrative report — claim-ready write-up

**When:** Output stage for any of the workflows above, typically monthly review or claim submission.

**Answers:** How do I turn these numbers into a professional text report for an audience that doesn't look at dashboards?

**Endpoint:** `POST /api/v1/reports/generate` with `{"report_type": "narrative", "project_id": "...", "baseline_id": "..."}`
**Standard:** AACE RP 29R-03 §5.3
**Engine:** `src/analytics/narrative_report.py` + `src/analytics/report_generator.py` (WeasyPrint)

Combines the schedule-view summary, scorecard (`calculate_scorecard`), and optional baseline comparison into a severity-tagged narrative, then renders PDF. Sections are auto-tagged `info` / `warning` / `critical` with colored badges.

Alternative: `report_type="monthly_review"` combines health + DCMA + comparison + alerts into a single standardised monthly update.

## Intelligence layer

Besides the forensic pipeline, four engines provide proactive monitoring:

- **Health Score** (`src/analytics/health_score.py`) — composite 0–100 across DCMA, float, logic, and trend
- **Early Warning** (`src/analytics/early_warning.py`) — 12-rule alert engine per GAO Schedule Assessment Guide §9
- **Float Trends** (`src/analytics/float_trends.py`) — FEI, near-critical drift, CP stability across updates
- **Anomaly Detection** (`src/analytics/anomaly_detection.py`) — IQR + z-score outlier identification

These are accessible via the dashboard, `/health`, `/alerts`, and `/trends` pages. They're not forensic tools — they're early-warning tools — but they feed the same underlying schedule data and use the same CPM cache.

## Related

- [Schedule Viewer](schedule-viewer.md) — visualize any of these analyses on the Gantt
- [Methodology Catalog](../methodologies.md) — deep dive on each engine with citations
- [API Reference](../api-reference.md) — full endpoint list
