# ADR-0009 Wave 4 — Calibration Outcome Record

* Parent: `docs/adr/0009-cycle1-lifecycle-intelligence.md`
* Related: ADR-0009 Amendment 1 (pre-registration), ADR-0009 Amendment 2 (outcome + branch decision), ADR-0014 (provenance contract), ADR-0016 (engine + override contract)
* Date: 2026-04-19
* Status: recorded
* Audience: operators, external forensic reviewers, future ruleset-v2 authors

## Purpose

Committed sibling that records the coarse-banded aggregate outcome of the Wave 4 calibration per ADR-0009 Amendment 1 §F (publication scope) and §H step 4 (calibration_result artifact). Per-observation detail, program-key hashes, and content hashes stay off-Git per Amendment 1 §G (filename leakage guard).

## Protocol executed (as pre-registered)

- Engine: `lifecycle_phase`, engine_version `4.0`, ruleset_version `lifecycle_phase-v1-2026-04` (unchanged from the W3 ship).
- Input corpus: 103 XERs at `$XER_SANDBOX_DIR`, content-hash-deduped from a serial-update-inclusive 106-XER staging population.
- Harness: `scripts/calibration/run_w4_calibration.py` (Task #2 ship, commit `4391155`).
- Dedup rule (Amendment 1 §A, pre-registered):
  > For each program group keyed by `projects[0].proj_short_name`, keep the revision with `max(len(activities))`. Tie-break by `max(last_recalc_date)`. Singletons go to the gate subset.
  Produced: **96 gate subset + 7 hysteresis subset** (only 7 of the 103 XERs belong to programs with multiple revisions in the corpus).
- Sub-gates:
  - §B unknown-denominator convention (`unknown` counts in denominator, never numerator).
  - §C phase-distribution ceiling (no single phase > 60% of numerator passes).
  - §D confidence honesty floor (≥20% of gate subset at confidence < 0.5).
- Primary thresholds swept: 0.80 (pre-registered formal), 0.70 and 0.60 (recorded for evidence).

## Aggregate results

### Corpus counts

| Subset | Count |
|---|---|
| Total XERs discovered | 103 |
| Parse failures | 0 |
| Gate subset (post-dedup) | 96 |
| Hysteresis subset (serial updates) | 7 |

### Phase distribution (gate subset, 96)

| Phase | Count | Share |
|---|---|---|
| construction | 60 | 62.5% |
| design | 24 | 25.0% |
| procurement | 6 | 6.2% |
| planning | 5 | 5.2% |
| unknown | 1 | 1.0% |
| closeout | 0 | 0.0% |

### Confidence histogram (gate subset, 96)

| Bucket | Count |
|---|---|
| [0.00, 0.50) | 19 |
| [0.50, 0.70) | 6 |
| [0.70, 0.80) | 61 |
| [0.80, 1.00] | 10 |

### Gate evaluations

| Threshold | Numerator / Denominator | Primary pass (≥70%) | Phase-dist (≤60% single phase) | Confidence honesty (≥20% <0.5) | Overall |
|---|---|---|---|---|---|
| **0.80** | 10 / 96 (10.4%) | FAIL | PASS (50.0%) | FAIL (19.8%) | FAIL |
| **0.70** | 71 / 96 (74.0%) | PASS | FAIL (84.5%) | FAIL (19.8%) | FAIL |
| **0.60** | 77 / 96 (80.2%) | PASS | FAIL (77.9%) | FAIL (19.8%) | FAIL |

### Hysteresis report (4 multi-revision programs in the corpus)

| Metric | Value |
|---|---|
| Multi-revision programs | 4 |
| Phase flips across consecutive revisions | 0 |
| Confidence-band flips (crossings at 0.5 or 0.8) | 1 |

## Interpretation

- **Gate fails at every pre-registered threshold.** Not Amendment 1 §J scenario #1 (pass), not #2 (lower threshold with sub-gates OK), not #3 (>90% unknown). A fourth scenario is explicit in Amendment 2.
- **Engine behaves as a construction-vs-non-construction detector**, not a full 5+1 discriminator. 60 of 96 classifications are `construction` at confidence 0.74–0.77. The `meaningful_actuals_mid_progress` rule (`src/analytics/lifecycle_phase.py:258-264`) dominates. Devils-advocate W3 end-of-wave P1#2 anticipated this failure mode; the sub-gate (Amendment 1 §C) caught it.
- **Hysteresis strongly positive.** Zero phase flips across 4 multi-revision programs indicates the engine is stable when the same program is re-uploaded with an updated snapshot. A forensic-defensibility asset.
- **Honesty sub-gate fails by 0.2 percentage points.** 19.8% vs the required 20.0%. The numerator of observations at confidence < 0.5 is 19 of 96 = 19.79%. Literally pre-registered threshold — fails. This is knife-edge and deliberately does NOT trigger a post-hoc adjustment per Amendment 1 §E.

## W5/W6 branch decision (recorded in ADR-0009 Amendment 2)

**Path A** — pre-committed fallback per ADR-0009 §"Wave 5–6 (conditional branch) — If gate fails":

- W5/W6 delivers `progress_callback` wiring in `src/analytics/evolution_optimizer.py` plus the Svelte composable for the WebSocket progress bar on the risk-simulation page.
- `src/analytics/lifecycle_health.py` NOT authored this cycle.
- ADR-0010 stays reserved; any future lifecycle-intelligence deep engine cites Amendment 2 and authors a new ADR number.
- W3 engine stays in prod as an informative `lifecycle_phase` label. Engine_version and ruleset_version are unchanged; no `mark_stale` chain triggered; existing 22 prod artifacts remain valid.

Rejected alternatives at Amendment 2 (kept for v4.1+ consideration): **B** (ruleset v2 tuning informed by this data), **C** (binary construction-detector surface + preview flag for full 5+1). Both are legitimate v4.1 paths and the data in `meridianiq-private/calibration/cycle1-w4/` is the starting point if either is revisited.

## Reproducibility

The run produced three files under `/tmp` (gitignored per Amendment 1 §G):
- `/tmp/w4_manifest.json` — dedup manifest with content hashes only.
- `/tmp/w4_calibration_public.json` — coarse-banded aggregates (the data in this document).
- `/tmp/w4_calibration_private.json` — per-observation detail keyed by content hash (no filenames, no project names).

Canonical off-Git archival home: `meridianiq-private/calibration/cycle1-w4/`. Maintainer archives after committing this record.

To reproduce (requires the private sandbox directory):

```sh
XER_SANDBOX_DIR=/abs/path/to/sandbox python3 -m scripts.calibration.run_w4_calibration
```

Engine + ruleset versions are pinned at `4.0` / `lifecycle_phase-v1-2026-04`. Any future run with a different version is a different experiment; land it as a separate ADR record, not an edit to this file.

## Cycle 1 closure

Wave 4 is closed by this record + Amendment 2. Cycle 1 v4.0 ships with:

- Lifecycle phase label surface (W3 — ADR-0016, validated at W4 as a construction detector).
- Materialization pipeline (W2 — ADR-0015, operationally validated post-W4).
- Provenance chain (W1 — ADR-0014).
- Governance: Amendments 1 + 2, `PRIVACY.md`, backfill CLI (ADR-0015 §6), pre-registered calibration harness.
- Bug fixes surfaced by W4 operational validation: datetime JSON serialization at store boundary (commit `d0df3e3`).

**Not shipped** this cycle: `lifecycle_health.py`, phase-aware analytics beyond the W3 label, ADR-0010. These deferrals are explicit per this record and Amendment 2 — correct outcome of the pre-registered gate discipline, not scope concession.
