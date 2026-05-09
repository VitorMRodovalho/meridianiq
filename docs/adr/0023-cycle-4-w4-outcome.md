# ADR-0023 Wave 4 — Calibration Outcome Record (Cycle 4)

* Parent: [`docs/adr/0022-cycle-4-entry-beta-honest.md`](0022-cycle-4-entry-beta-honest.md)
* Related: ADR-0022 §"W4 — Pre-registered calibration gate", [ADR-0009 W4 outcome](0009-w4-outcome.md) (path-A precedent), [ADR-0020](0020-calibration-harness-primitive.md) (calibration harness primitive)
* Date: 2026-05-09
* Status: recorded
* Audience: operators, contributors, prospective enterprise reviewers, Cycle 5+ corpus-growth + re-evaluation authors, **external diligence reviewers reading this for pattern-check, NOT only insiders who already share the pre-registration ideology**

## Purpose

Records the outcome of the Cycle 4 W4 pre-registered calibration gate executed against the `revision_trends` optimism-pattern-detection feature. Path-A activation per the pre-committed branch in ADR-0022 §"Pre-committed path A fallback".

This ADR is committed alongside the W4 evaluator, the outcome JSON, and the test suite to make the path-A activation falsifiable, reproducible, and auditable. It is paired with `devils-advocate + investor-view` exit-council per ADR-0022 NFM-9 BEFORE merge. **Council findings — both code-level (DA P0/P1/P2) and strategic (IV) — are addressed inline below; this version is post-fix-up.** Section §"Open process gap" tracks the residual.

## Substantive Cycle 4 outcomes — what shipped

This section deliberately leads with English-language substantive outcomes, with credit accounting as a footnote downstream (per IV exit-council finding #2 — partial-credit math is itself a sycophancy attack vector if it leads the framing).

* **Migration 028** (data_date + revision_date columns + revision_history table + soft-tombstone columns + cap-enforcement trigger + RLS) deployed to staging + production. (Criterion 2.)
* **Auto-revision detection** with confirmation card UX + soft-tombstone deliverables (operator-visible, audit-logged, runbook-documented). (Criterion 3.)
* **Multi-revision S-curve overlay** visualization with calendar-aligned X-axis, change-point markers, slope CI bands. **No forecast curve.** (Criterion 4.)
* **Sub-gate C** (CUSUM change-point detection F1) PASSED at F1=0.769231 against hash-locked synthetic fixtures. The visualization surface (markers, CI bands) is empirically grounded.
* **Sub-gates A + B path-A activated**: the corpus that would validate the optimism-pattern forecast claim does not exist. The optimism-pattern forecast claim is **NOT validated** and the feature ships **as preview only**.
* **ADR-0023** + DA + IV paired exit-council documenting the outcome honestly (this document).

The substantive outcome is independent of the credit-accounting math; the math is a downstream check against ADR-0022's pre-registered framework, NOT the load-bearing decision.

## Pattern check vs. ADR-0009 — confronting the "calibration theater" critique

IV exit-council finding #1: ADR-0009 W4 (Cycle 1) and this ADR-0023 W4 (Cycle 4) are now **two consecutive W4 calibration gates that activated path-A on a corpus precondition**. A hostile reviewer reading both can declare a pattern: "this team's calibration discipline is institutional ritual that reliably permits unship-able features to ship under preview-flag cover."

This ADR confronts that critique directly rather than defending against it tacitly.

**The pattern is real.** Cycle 1 W4 and Cycle 4 W4 both activated path-A. The cycle templates rhyme, the ADR vocabulary rhymes, the "preview-only" outcome rhymes.

**The pattern is NOT YET falsified.** A single Cycle 5+ W4 outcome that PASSES sub-gate A would falsify the ritual reading. As of this ADR, no such outcome exists. Until one does, the discipline is the maintainer's word for it, recursively citing the maintainer's previous word for it.

**The falsifier is operational, not rhetorical.** The discipline ceases to be ritual when:
1. **A Cycle 5+ W4 sub-gate A passes** (corpus crosses N≥30 with consent-path-clear labeled outcomes), AND/OR
2. **Independent external citation** of the pre-registration template (AACE working group, peer open-source project, PMI document) appears, AND/OR
3. **Independent attestation** (someone other than the maintainer publishing a calibration outcome ADR using the same template).

**This ADR explicitly commits to that falsifier**: until at least one of those three lands, the calibration discipline framing in MeridianIQ external positioning copy MUST acknowledge the unrebutted pattern. Internal disclosure ≠ external claim.

What this confrontation does NOT do: it does NOT concede that the discipline is ritual today; it acknowledges that the question is unsettled and that an external reviewer's skepticism is reasonable. It commits to the falsifier rather than denying the pattern.

## Protocol executed (as pre-registered)

Per ADR-0022 §"W4 — Pre-registered calibration gate". All thresholds locked at ADR-0022 authoring time (2026-04-28); no post-W3 tuning was permitted, and the W4 evaluator enforces the locks at the dataclass `__post_init__` boundary (`tools/calibration_harness/gates/revision_trends_w4.py::CorpusCensus.__post_init__`, `SubGateBResult.__post_init__`, `SubGateCResult.__post_init__` — raise `ValueError` if user attempts override).

### Sub-gates and locked thresholds

| Sub-gate | Threshold (locked at ADR-0022) | Source |
|---|---|---|
| A — corpus census | `N ≥ 30` | ADR-0022 §"Sub-gate A — corpus census" |
| B — heteroscedasticity-aware Brier | `Brier ≤ 0.20` | ADR-0022 §"Sub-gate B — Brier calibration" |
| C — change-point detection F1 | `F1 ≥ 0.75` on hash-locked fixtures | ADR-0022 §"Sub-gate C — change-point detection F1" |

### Heteroscedasticity weight — pre-registration in this ADR (revised post-DA exit-council)

ADR-0022 §"Sub-gate B" specified "heteroscedasticity-aware regression with CI passes Brier ≤ 0.20" but left the weight formula unspecified. This ADR pins it AS PART OF THE PRE-REGISTRATION CONTRACT:

```
w_i = 1 / sqrt(horizon_i + 1)
```

**Honest framing of the formula choice (DA exit-council finding P0 #3)**: the `+1` is a **signal component**, not a numerical-stability epsilon. It floors weight at horizon=0 (treating same-day forecasts as carrying 1-day-equivalent measurement uncertainty rather than zero) and yields a ~30% weight differential between horizon=0 and horizon=1. That is a deliberate calibration choice, defensible per AACE RP 29R-03 §"Window analysis" (variance grows ∝ √horizon from a non-zero baseline), but it is a **tunable choice**, not a numerical-stability necessity.

**The lock has zero teeth in THIS evaluation** (sub-gate B was skipped on sub-gate A's precondition; no data ever touched the formula). Locking an unfalsified formula in this outcome ADR is a calibration-discipline IOU: a future Cycle 5+ author with corpus evidence that this weighting is wrong MUST author a re-pre-registration ADR amendment BEFORE re-running the gate. The lock-with-IOU framing is the honest treatment per the calibration-theater confrontation above.

Both unweighted Brier and weighted Brier are computed and emitted in the public payload for transparency. The threshold (`≤ 0.20`) is evaluated against the WEIGHTED form per ADR-0022's "heteroscedasticity-aware" qualifier.

### Calibration corpus and harness

* Engine: `revision_trends` (`src/analytics/revision_trends.py`); engine identity pinned via `src.__about__.__version__` per ADR-0014 + Cycle 3 W4 closure (PR #50).
* Harness: `tools/calibration_harness/gates/revision_trends_w4.py` (this PR's deliverable) wrapping the W3-C primitives `verify_optimism_synth_hash_lock`, `evaluate_cusum_f1`, `collapse_detection_clusters` from PR #99.
* Sub-gate A input: operator-attested `CorpusCensus` reflecting state at commit `1ab4a2a` (post-PR-#99 main) — see attestation in §"Sub-gate A" results below.
* Sub-gate C input: 8 hash-locked synthetic fixtures (`tools/calibration_harness/fixtures/optimism_synth/corner_*.json` + `optimism_synth.lock`) authored in W3-C per ADR-0022 §HB-D + DA P1 #1+#3.

## Aggregate results

### Sub-gate A — corpus census

Operator-attested counts at Cycle 4 W4 evaluation moment, mirroring `_DEFAULT_CENSUS_KWARGS` in the evaluator:

| Field | Value |
|---|---|
| `n_total_multi_revision_programs` | 4 |
| `n_completed_with_outcome` | 0 |
| `n_with_consent_path` | 0 |
| `binding_count` (= `min` of the three) | **0** |
| `threshold` | 30 |
| **Passed** | **NO** |

`attestation_source`: "ADR-0009 W4 outcome record §Aggregate counts (4 multi-revision programs in 103-XER sandbox, 2026-04-19) + ADR-0022 §Honest disclosures #6 (corpus assembly is operator + LGPD-blocked)".

The `binding_count` is the **minimum** of the three subset axes, not just `n_with_consent_path`. Backend-reviewer entry-council finding: a non-monotone operator entry (e.g., transposing the "total" and "consent" columns) would silently widen the gate if binding were `n_with_consent_path` alone. Taking `min` of all three is the structural defense.

**Attestation regex is FORMAT validation only** (DA P1 #5): the evaluator's `_ATTESTATION_RE` accepts any string matching `ADR-NNNN` or `git@<sha>`. It does NOT verify that the cited ADR exists in `docs/adr/` nor that the cited SHA is in `git log`. The structural defense for attestation honesty is the audit trail (operator commits census + reviewer verifies citation in PR review), NOT the regex. ADR-0023 acknowledges this rather than overclaiming structural defense the code does not provide.

### Sub-gate B — heteroscedasticity-aware Brier calibration

| Field | Value |
|---|---|
| `status` | `skipped` |
| `skipped_reason` | `sub_gate_a_failed` |
| `brier_score` | n/a (precondition not met) |
| `weighted_brier_score` | n/a (precondition not met) |
| `threshold` | 0.20 |
| `n_pairs` | 0 |
| **Passed** | **NO (precondition skip)** |

The evaluator distinguishes precondition skip (`skipped_reason = "sub_gate_a_failed"`) from empty-input skip (`skipped_reason = "no_calibration_pairs"`) so future re-evaluations can't conflate them. Per ADR-0022 §"Pre-committed path A fallback", precondition skip is path-A-activating equally with fail-by-evaluation.

**Credit asymmetry honesty (DA P1 #6)**: ADR-0022's partial-credit rule awards 0.5 credit for any path-A on a W4 sub-gate, treating "skipped on precondition" identically to "tried-and-failed". A Cycle 5+ evaluator that runs sub-gate B and gets Brier=0.21 receives the same credit as today's "we never even attempted the test". The rule is **coarse by design** — ADR-0022 chose simplicity over fine-grained accounting — but a critic can fairly call this "any failure rounds up to half-credit, indistinguishable from honest failure". A future Cycle 5+ amendment may refine the partial-credit scale (e.g., 0.5 for skip-by-precondition / 0.25 for skip-by-empty / 0.0 for fail-by-evaluation).

### Sub-gate C — change-point detection F1

| Field | Value |
|---|---|
| `hash_lock_verified` | `true` |
| `f1` | **0.769231** |
| `threshold` | 0.75 |
| `n_fixtures` | 8 |
| `n_detections_total` | 14 |
| `n_ground_truths_total` | 8 |
| `true_positives` | 5 |
| `false_positives` | 0 |
| `false_negatives` | 3 |
| `precision` | 1.000 |
| `recall` | 0.625 |
| **Passed** | **YES** (margin: 1 borderline detection wide — see brittleness analysis below) |

The locked baseline F1=0.769231 from W3-C PR #99 reproduces against the committed fixture set + engine. Hash-lock verifies clean (all 8 fixture SHA-256s match `optimism_synth.lock`).

The engine demonstrates **perfect precision** (P=1.0; every detection cluster overlaps a true CP) but **modest recall** (0.625; 3 of 8 planted regime changes go undetected, mostly in `corner_*` fixtures with smaller noise sigma where the CUSUM `1.5σ` threshold is conservative). The engine prefers false-negatives over false-positives, which is the credibility-conservative bias appropriate for a forensic surface — **but it is not "credible" in an unfalsifiable sense**: users see no false alarms but should expect ~⅓ of real regime changes to go unmarked. UI copy must reflect this asymmetry.

#### Margin honesty — discrete-metric brittleness analysis (DA exit-council P0 #2)

The headline "F1 = 0.769231 vs threshold 0.75 → margin = 0.019" is **misleading**. F1 on N=8 ground truths + integer-valued TP/FP/FN counts is **discrete**, not continuous. The granularity:

* Current state: TP=5, FP=0, FN=3 → F1 = 2·1.0·0.625 / (1.0+0.625) = **0.769231**.
* If a single planted regime change reclassifies from TP to FN (engine bump, fixture rotation, OR float-arithmetic drift): TP=4, FP=0, FN=4 → F1 = 2·1.0·0.5 / (1.0+0.5) = **0.667 → path-A**.

**The margin is "1 borderline detection wide", NOT "0.019 above threshold".** A reviewer who reads "0.019" thinks "small but durable"; a reviewer who reads "1 detection" understands the brittleness correctly.

The cluster-collapse rule + per-fixture `+100` offset disambiguation work as designed. No cross-fixture bleed (verified by `tests/test_revision_trends_w4_evaluator.py::test_offset_100_prevents_cross_fixture_cluster_bleed` — structural pin asserting `_FIXTURE_OFFSET > max(n_revisions_per_fixture)`).

### Aggregate decision

| Field | Value |
|---|---|
| `overall_pass` | **`false`** |
| `path_a_activated` | **`true`** |
| `path_a_reasons` | `sub-gate A: corpus census below threshold (binding=0, threshold=30)`; `sub-gate B: skipped (sub_gate_a_failed)` |

## Path-A activation interpretation

Per ADR-0022 §"W4 fallback if gate fails (path A explicit)":

* The optimism-pattern feature ships **as preview** — visualization + change-point markers + slope CI bands ONLY. **No forecast curve.** **No "predictive engine" copy.** The W3-B multi-rev S-curve overlay (PR #95) already conforms to this discipline.
* Feature flagged "preview, not load-bearing" (Cycle 2 W2 B2 honesty-debt pattern reuse).
* Cycle 4 still ships at `v4.2.0` with reduced C scope.
* Corpus assembly continues as the Cycle 5+ pre-condition.

This is **NOT graceful failure framing**. The honest sentence, **load-bearing for this ADR — pre-emptively framed for an external reader who has NOT been sold the pre-registration ideology**:

> **The corpus that would validate the optimism-pattern forecast claim does not exist.**
>
> *Pre-registration discipline produces this sentence when corpus is unmet; the alternative (in non-pre-registered industry norm) is silently shipping the forecast feature with no calibration evidence — which is the standard practice that ADR-0009 W4 + ADR-0023 W4 explicitly reject. The choice between (a) ship-with-honest-disclosure and (b) silent-overclaim is the discipline's contribution; the path-A outcome is the disclosure landing exactly where the discipline was designed to land it.*

Sub-gate A's `binding_count = 0` is a structural fact about LGPD/GDPR-blocked outcome-data labeling, not a near-miss. The minimum-viable demonstration threshold (`N ≥ 30`) is reached when corpus assembly + consent path mature. The production-deployment threshold (`N ≥ 100-200` per ADR-0022 §"Sub-gate A" honest disclosure) is further still.

ADR-0022 §"Honest disclosures" #6 made this explicit at cycle entry; this W4 evaluation confirms.

### What sub-gate C tells us in isolation

* The CUSUM change-point detection engine reliably **identifies** regime changes in synthetic schedule sequences with planted CPs at known revisions.
* F1=0.769 is "directionally informative" (precision-perfect, recall-modest); the chart's vertical change-point markers are **a precision-perfect, recall-modest (62.5%) diagnostic surface** — users see no false alarms but should expect ~⅓ of real regime changes to go unmarked. UI copy must reflect this asymmetry.
* It does **NOT** validate any forecast claim. Forecast = `optimism_pattern_factor × historical_slip_distribution`, and that requires the sub-gate B corpus that does not exist.

### What sub-gate A tells us in isolation

* The 4 multi-revision programs in the 103-XER sandbox are not enough to even **run** sub-gate B at minimum-viable demonstration scale (`N=30`), let alone production scale (`N=100-200`).
* Outcome-data labeling (executed completion fact + final actual completion date) AND LGPD/GDPR consent path AND organizational consent are all preconditions for corpus growth. Issue [#13](https://github.com/VitorMRodovalho/meridianiq/issues/13) (calibration dataset community ask, opened in Cycle 1 for the lifecycle_phase corpus) is the same on-ramp here, with optimism-pattern-specific labeling extension required.
* Cycle 4 W5 (operator-paced, parallel) starts the corpus assembly; Cycle 5+ reactivates this gate when `N ≥ 30` with Brier-evaluable pairs becomes available.

## Demand-validation signal observed during Cycle 4

Per IV exit-council finding #5: ADR-0023 must speak to whether the cycle produced demand-validation signal even if the answer is "none". Silence is itself a signal.

**Observed during Cycle 4 (2026-04-28 → 2026-05-09):**

* Issue [#13](https://github.com/VitorMRodovalho/meridianiq/issues/13) (calibration dataset community ask, opened Cycle 1 W3) — community-supplied corpus contributions: **0**.
* Inbound enterprise prospect inquiry: **0**.
* Design-partner discussions: **0**.
* External AACE/PMI-CP/peer-project citation of the pre-registration template: **0**.
* Contributor PRs touching `src/analytics/revision_trends.py` or the W4 calibration code: **0** (only the maintainer).

**Honest read.** Cycle 4 was a single-maintainer deep cycle with zero external demand-validation signal during the 11-day execution window. ADR-0022 §"Honest disclosures" #1 (internal-driven scope, N=1 self-validation) is unchanged post-Cycle 4. The demand-validation gap is widened by the Cycle 4 close, not narrowed.

This is acceptable per ADR-0022 §"Acquisition-path optionality, not premise" — Cycle 4 was sized as a lifestyle-product enhancement with research-grade primitive output, not as a demand-validated investment. Reactivation of any acquisition-path conversation requires demand-validation signal that has not yet emerged.

## Cycle 5+ preconditions for re-evaluation — with realistic timeline

Sub-gate B becomes evaluable when ALL of:

1. `n_with_consent_path ≥ 30` — operator-curated outcome-labeled corpus with LGPD/GDPR consent path.
2. Each labeled program has: (a) executed completion-curve, (b) final actual completion date, (c) at least 3 historical revisions per program for inter-revision optimism-factor extraction.
3. Calibration pairs JSON (one per qualifying program) authored per the schema documented in `tools.calibration_harness.gates.revision_trends_w4.load_calibration_pairs`.
4. Re-run `python3 -m tools.calibration_harness.gates.revision_trends_w4 --census-state ... --calibration-pairs ...` against the new corpus.
5. Author ADR-0023 amendment OR Cycle 5+ outcome ADR (new number) recording the re-evaluation outcome, with DA + IV paired exit-council per the same NFM-9 protocol.

**Honest realistic timeline (IV exit-council finding #3):**

The unlock conditions are TRIPLE-bottlenecked:
* **Operator-bottlenecked**: corpus assembly is solo-dev manually finding completed projects with outcome data — single point of failure, dependent on the maintainer's availability.
* **LGPD/GDPR-bottlenecked**: consent path is legal work + contributor anonymization + organizational consent + (potentially) DPA signatures — multi-month minimum, possibly never if no community materializes.
* **Community-bottlenecked**: issue #13 (Cycle 1 community ask) has produced **zero** community-supplied corpus across Cycle 1+2+3+4 — empirically dead so far.

**Realistic re-evaluation window**: 12-24 months minimum, contingent on at least one of {a community contribution materializing, a paid design partner emerging, OR a maintainer-collected internal corpus with consent assembled}. The community channel cannot be presumed productive based on the 4-cycle no-signal track record.

Until those conditions materialize, the optimism-pattern feature stays **preview** indefinitely. This is honest disclosure, not a near-term commitment.

## Cycle 4 success criteria status — credit accounting (per ADR-0022 §"Pre-registered success criteria")

This section is the credit-counting machinery from ADR-0022 §"Pre-registered success criteria" line 212. **It is presented as a footnote to the substantive outcomes above** (per IV exit-council finding #2 — the math itself is a sycophancy attack vector if it leads the framing).

| # | Criterion | Status | Credit | Source |
|---|---|---|---|---|
| 1 | ADR-0022 ratification + Cycle 4 ROADMAP refresh + L&A review | OPEN — operator-paced | 0.0 | parallel to W4 |
| 2 | Migration 028 staging + production | CLOSED | 1.0 | PR #72 |
| 3 | W2 detection + UX + tombstone | CLOSED | 1.0 | PR #78 + #83 |
| 4 | W3 viz + W3 fixtures + hash-lock | CLOSED | 1.0 | PR #88 + #95 + #99 |
| 5 | W4 sub-gate A: corpus census documented | **CLOSED — path-A** | 0.5 | this ADR |
| 6 | W4 sub-gate B: Brier evaluated against locked threshold | **CLOSED — path-A** | 0.5 | this ADR |
| 7 | W4 sub-gate C: F1 ≥ 0.75 on hash-locked fixtures | **CLOSED — passed** | 1.0 | this ADR |
| 8 | ADR-0023 authored + DA + IV paired exit-council | **CLOSED post-fix-up** (council ran; this revision incorporates findings) | 1.0 | this ADR + DA + IV exit-council |
| 9 | Release tag v4.2.0 (or v4.2.0-rc) | OPEN — after this PR | 0.0 | next |

**Post-W4 credit total**: 3.0 (criteria 2+3+4) + 0.5 + 0.5 + 1.0 + 1.0 = **6.0 / 9** (pending criteria 1 + 9).

After release tag (#9 closes): **7.0 / 9** = ADR-0022 graceful threshold (≥7/9). **No margin** (DA exit-council P2 #9): the cycle lands at exactly the floor when criterion #9 closes; criterion #1 ratification slipping further does not break the cycle, but criterion #9 slipping does.

If criterion #1 ratification syncs in time: **8.0 / 9**. Otherwise still ≥7/9 ships.

**Sycophancy-risk acknowledgment (IV exit-council finding #6)**: this credit accounting was designed by the maintainer (ADR-0022 §"Pre-registered success criteria" was the maintainer's pre-cycle authorship). An external reviewer might reasonably reject the partial-credit structure as self-grading. The **substantive** Cycle 4 outcome (see §"Substantive Cycle 4 outcomes — what shipped" above) is independent of the credit total; if a reviewer rejects the math, the substantive outcomes still hold. The math is a check against the pre-registered framework, not the load-bearing decision.

**Criterion #8 honesty (DA exit-council finding P0 #1)**: criterion #8 closes "ADR-0023 authored + DA + IV paired exit-council before merge". The exit-council ran — both DA and IV produced findings (DA: 3 P0 + 5 P1 + 2 P2 + 4 P3 ≈ 14 findings; IV: 6 strategic findings). The findings are addressed in this revision (post-fix-up). The credit accrues at the same merge moment that the council validates the fix-ups (i.e., the merge-time review confirms the council findings landed in the ADR text + code + tests). The prior version of this section credited #8 before the council had run, which was a tautology — that tautology is fixed by this revision.

## Reproducibility

The W4 evaluation produced three files under `docs/calibration/` (private gitignored per `.gitignore` line 68 `*_private.json`):

* `docs/calibration/revision_trends_w4_manifest.json` — content-hash manifest + locked thresholds + census attestation source (no engine outputs).
* `docs/calibration/revision_trends_w4_public.json` — full sub-gate aggregates safe for public commit.
* `docs/calibration/revision_trends_w4_private.json` — full detail incl. calibration pair vectors (gitignored, never committed).

To reproduce against the committed fixtures + default census:

```sh
python3 -m tools.calibration_harness.gates.revision_trends_w4
```

To reproduce **byte-identical** to the committed JSONs (DA exit-council P1 #4 — `--run-started-at` flag):

```sh
python3 -m tools.calibration_harness.gates.revision_trends_w4 \
    --run-started-at "2026-05-09T18:00:00+00:00"
```

To reproduce with operator override of the corpus census (Cycle 5+ workflow):

```sh
python3 -m tools.calibration_harness.gates.revision_trends_w4 \
    --census-state path/to/census.json \
    --calibration-pairs path/to/pairs.json
```

Engine version, fixture hash-lock, and locked thresholds are all version-controlled. Any future run with different versions is a different experiment; land it as a separate ADR record (next number reserved Cycle 5+ entry), not an edit to this file.

## What this ADR does NOT claim

* Does NOT claim the engine is unfit for use. Sub-gate C passed at a thin discrete-metric margin (1 borderline detection wide); the visualization surface is empirically grounded with explicit precision/recall asymmetry disclosure.
* Does NOT claim sub-gate A's threshold (`N ≥ 30`) is statistically powered. ADR-0022 acknowledged it as "minimum-viable demonstration"; production deployment requires `N ≥ 100-200` (deferred to Cycle 5+ corpus growth).
* Does NOT claim sub-gate B was "tried and failed". Sub-gate B was **NEVER ATTEMPTED** because its corpus precondition was unmet. Any future Cycle 5+ re-evaluation cannot frame this as "we improved Brier from skipped to passing"; the denominator is honest.
* Does NOT claim the heteroscedasticity weight formula is "the canonical" form. ADR-0022 + this amendment pin ONE form `w_i = 1 / sqrt(horizon_i + 1)`; the `+1` is a SIGNAL choice (1-day-equivalent measurement uncertainty floor), NOT numerical stability. Alternative forms (linear-inverse, exponential decay, etc.) are legitimate Cycle 5+ pre-registration ADR amendments if corpus evidence indicates a better fit. Pre-registration discipline says: pick one in advance, lock it in writing, document if changing.
* Does NOT close ADR-0022 itself. ADR-0022 stays "proposed" pending operator ratification (Cycle 4 success criterion #1).
* Does NOT presume the calibration discipline is institutional asset rather than ritual. See §"Pattern check vs. ADR-0009" — the falsifier is operational, not rhetorical.

## Honest disclosures (per ADR-0018 Amendment 1 + ADR-0022 §"Honest disclosures")

1. **Path-A as expected outcome, not surprise.** ADR-0022 §"NFM-5" and §"Pre-committed path A fallback" both made this explicit at cycle entry. This ADR confirms the expectation; it does not represent new information.

2. **Sub-gate C's margin is "1 borderline detection wide", not "0.019" (DA P0 #2).** F1 with N=8 ground truths is granular at increments of `2/(detection_count + 8)`. A single TP→FN reclassification yields F1 ≈ 0.667 (path-A activation). The brittleness vectors:
   * **Engine bump** — any change to `cusum_change_points()` thresholds, `np.std(ddof=1)`, or detection-cluster collapse rule can shift one borderline detection.
   * **Fixture rotation** — any non-trivial fixture re-roll (different seeds, different planted CPs) is structurally a different experiment; ADR amendment + re-baseline required.
   * **Numpy / scipy / Python minor-version float-arithmetic drift (DA P1 #7)** — `numpy 2.0 → 2.4` (already landed in v4.0.2 dep refresh), planned `Python 3.13 → 3.14` (Dockerfile note), `scikit-learn 1.6 → 1.8` (already landed). Any of these can change `np.cumsum`, `np.std` summation order, BLAS dispatch, etc. CI MUST run sub-gate C against the locked baseline on every dependency bump; a failure is path-A activation, not a flaky test to retry.

3. **The corpus gap is operator + LGPD/GDPR-blocked, not engineering-blocked.** No amount of additional code shipping closes sub-gate A. Issue #13 (community ask) is the on-ramp; PMI-CP / AACE / contributor-supplied anonymized + outcome-labeled corpora are the structural unlock.

4. **Heteroscedasticity weight pre-registration was deferred from ADR-0022 to this ADR.** Backend-reviewer entry-council surfaced this gap; closing it here (in writing, before any data is observed) preserves pre-registration discipline. **The lock has zero teeth in this evaluation** (sub-gate B was skipped); a Cycle 5+ author with corpus evidence the formula is wrong MUST author a re-pre-registration ADR amendment BEFORE re-running the gate.

5. **Cycle 4 path-A activation does not erode moat — but the calibration-discipline-as-asset claim is unrebutted, not yet verified.** See §"Pattern check vs. ADR-0009" for the falsifier commitment. External positioning copy MUST distinguish "the maintainer asserts the discipline is real" from "the discipline has been independently verified".

6. **Attestation regex is FORMAT validation, not SEMANTIC validation (DA P1 #5).** `_ATTESTATION_RE` accepts any `ADR-NNNN` or `git@<sha>` shape — including fabricated ADR numbers and arbitrary 7+ hex strings. The structural defense is the audit trail (operator + reviewer in PR), not the regex.

7. **Credit math is self-graded; substantive outcomes are independent (IV finding #6).** The 6.0 → 7.0 → 8.0 / 9 partial-credit accounting was designed by the maintainer in ADR-0022 (pre-cycle authorship). An external reviewer may reasonably reject the structure as self-grading. The substantive outcomes (§"Substantive Cycle 4 outcomes — what shipped") hold independently.

## Cross-references

* [ADR-0022](0022-cycle-4-entry-beta-honest.md) — Cycle 4 entry + W4 pre-registration (this ADR's parent)
* [ADR-0009](0009-cycle1-lifecycle-intelligence.md) + [ADR-0009 W4 outcome](0009-w4-outcome.md) — Cycle 1 W4 path-A precedent (the same discipline applied to lifecycle_phase v1; second-cycle pattern confronted in §"Pattern check vs. ADR-0009")
* [ADR-0014](0014-derived-artifact-provenance-hash.md) — `engine_version` provenance contract referenced by sub-gate C harness invocation
* [ADR-0018 Amendment 1](0018-cycle-cadence-doc-artifacts.md) — DA-as-second-reviewer protocol; this ADR receives DA + IV paired exit-council per NFM-9
* [ADR-0020](0020-calibration-harness-primitive.md) — calibration harness primitive; this ADR's evaluator extends with the W4 sub-gate gates submodule
* `tools/calibration_harness/gates/revision_trends_w4.py` — the evaluator
* `tests/test_revision_trends_w4_evaluator.py` — 49 regression tests pinning the contract (47 original + 2 added per DA P1 #4 reproducibility flag)
* `docs/calibration/revision_trends_w4_public.json` — machine-parsable outcome record
* `docs/calibration/revision_trends_w4_manifest.json` — content-hash + threshold pin manifest
* PR #99 (`tools/calibration_harness/__init__.py::evaluate_cusum_f1` + `verify_optimism_synth_hash_lock`) — the W3-C primitives this evaluator wraps
* `tests/test_optimism_synth_fixtures.py::test_evaluate_cusum_f1_locked_baseline_against_committed_fixtures` (line 301) — authoritative F1 regression pin (verified existing per DA P1 #8 cross-reference integrity check)

## Open process gap

* **DA + IV paired exit-council per NFM-9** — RAN. DA produced 3 P0 + 5 P1 + 2 P2 + 4 P3 findings. IV produced 6 strategic findings. **All P0 + all P1 addressed inline in this revision**. P2 (DA #9 no-margin disclosure, DA #10 "credible" replaced with empirical phrasing) addressed inline. P3 items (regex case-sensitivity, output-dir cwd-pollution edge, lock-comment edge, print() exception) acknowledged in code comments OR deferred to Cycle 5+ hygiene with no merge-blocking impact. Council-mandated re-review at PR-merge time confirms the fix-ups landed; criterion #8 closes at that confirmation, not at this commit.
* **Operator action items pending (NOT cycle-blocking)**: criterion #1 ratification (ADR-0022 + ROADMAP refresh + L&A review). Tracks operator availability; not part of W4 evaluator scope.
