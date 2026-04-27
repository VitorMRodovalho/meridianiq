# Lifecycle Phase v1 — W4 calibration post-mortem

* Engine: `lifecycle_phase` v1 (`src/analytics/lifecycle_phase.py`)
* Ruleset: `lifecycle_phase-v1-2026-04`
* Calibration window: 2026-04 (Cycle 1 W4)
* Outcome record: [`docs/adr/0009-w4-outcome.md`](../adr/0009-w4-outcome.md)
* Strategic decision: [ADR-0019 §"W2 — B2"](../adr/0019-cycle-2-entry-consolidation-primitive.md)
* Audience: operators, contributors, prospective enterprise reviewers, future ruleset-v2 authors

## What we set out to do

When MeridianIQ ships an analysis engine whose output a customer might cite in a delay claim, the engine has to be measurable against external evidence — not just shipped on the maintainer's intuition. Cycle 1 of v4.0 introduced a **lifecycle phase inference engine**: given a parsed P6 / MSP schedule, classify the project into one of `planning / design / procurement / construction / closeout / unknown` with a numeric confidence and a forensic-reconstructible rationale.

Before Wave 4, we wrote ADR-0009 Amendment 1 — a **pre-registered calibration protocol** stating exactly what would have to hold for the engine to ship with the full 5+1 surface as authoritative. The protocol was a hard gate: pass and ship; fail and demote the surface.

This post-mortem records what happened, what the engine actually does well, and what changing the answer would require.

## Pre-registered protocol (ADR-0009 Amendment 1)

* **Corpus**: 103 P6 XER files, content-hash-deduped from a 106-file staging set. No customer-identifying data outside `meridianiq-private`.
* **Dedup rule**: per program (`projects[0].proj_short_name`), keep `max(len(activities))`; tie-break on `max(last_recalc_date)`. Singletons go to the gate subset.
* **Sub-gates** (all must pass):
  * §B — `unknown` counts in the denominator, never the numerator (no quietly inflating pass rates by hiding non-classifications).
  * §C — no single phase exceeds 60% of numerator passes (anti-monoculture).
  * §D — confidence honesty floor: ≥20% of the gate subset must land at confidence < 0.5 (the engine must show its uncertainty, not anchor everything at 0.85).
* **Primary thresholds**: 0.80 (the formal pre-committed gate), 0.70 and 0.60 recorded for evidence.
* **Branch decision** (Amendment 2): if the gate fails at every threshold, fall back to **path A** — "preliminary indicator only", do not ship `lifecycle_health` (the deeper engine that would have built on top), publish the calibration outcome honestly.

## What the calibration found

Detail in [`docs/adr/0009-w4-outcome.md`](../adr/0009-w4-outcome.md). The headline:

* The engine **passed** as a binary "construction vs non-construction" detector with high reliability (60 of 96 gate-subset XERs classified `construction` at confidence 0.74–0.77; the `meaningful_actuals_mid_progress` rule dominated).
* The engine **failed** the §C ceiling sub-gate at every threshold for the full 5+1 taxonomy — the construction-share ran at 62.5%, above the pre-registered 60% ceiling. The 5+1 surface could not legitimately ship as authoritative.
* The engine **also failed** the §D confidence-honesty sub-gate, at 19.8% vs the pre-registered 20.0% floor — a knife-edge result that we record as a fail per the pre-commitment discipline (no post-hoc threshold relaxation; the gate is the gate).
* Hysteresis (§E, sticky-flip suppression on serial revisions) showed **0 phase flips across 4 multi-revision programs** — the rule's stickiness held up.
* Per-phase distribution on the gate subset (96 XERs): construction 60 (62.5%), design 24 (25.0%), procurement 6 (6.2%), planning 5 (5.2%), unknown 1 (1.0%), closeout **0**. The 0-closeout figure is concrete, not "small": v1 has had no chance to learn the closeout signal at all.

Path A was activated per the pre-committed branch. The deeper `lifecycle_health` engine that would have layered on top of this was deliberately **not shipped** in Cycle 1. ADR-0010 stays reserved.

## What v1 reliably does

The engine is a **construction-active classifier** wearing the surface area of a 5+1 taxonomy. Specifically, what passed the calibration:

* Correctly answering the question "is this project executing physical work right now?" — the field that operations and forensic engineering audiences need first.
* Honest non-classification: when the schedule has insufficient signal, the engine returns `phase='unknown'` with confidence 0.0 instead of guessing a label.
* Stickiness: the engine does not flip phase on a routine schedule revision.

This is the surface ADR-0019 W2 made structural — the API now returns an `is_construction_active: bool | null` field that the UI surfaces directly, alongside the 5+1 `phase` carried as `(preview)`.

## What v1 does NOT do well

* **Fine-grained 5+1 discrimination.** The §C ceiling failure is not an artifact — the engine genuinely cannot reliably tell `design` from `procurement` from `planning` on the 103-XER corpus we calibrated against. Treating those labels as authoritative is the silent-overclaim mode the post-mortem exists to close.
* **Cross-domain coverage.** The corpus skewed toward construction-domain projects (commercial, infrastructure). Software / R&D / hybrid lifecycle projects are not represented. The "construction-active" classification is the only one we are willing to put behind authoritative copy today.
* **Closeout signal.** The corpus had 0 `closeout` examples in the gate subset. We have no calibration evidence that the engine recognizes closeout at all; it just hasn't seen enough.

## What ruleset v2 would need

Three things, in priority order:

1. **A wider, contributor-supplied corpus.** Issue [#13](https://github.com/VitorMRodovalho/meridianiq/issues/13) is the open call. Phase-balanced, domain-balanced, anonymized XER / MSP files with self-attested ground-truth labels are what the next calibration generation needs. The current corpus is owner-curated and overweight on one domain.
2. **Per-phase rule additions** anchored against published standards (AACE RP 14R for planning vs design; PMI-CP procurement-phase signals; ISO 21502 closeout markers). The rules in `_classify` today are construction-biased because that's where the calibration was strongest; broadening requires writing the rules AND the calibration fixtures together.
3. **A calibration harness primitive** so any future ruleset (v2, v3 …) can re-run the same gate without bespoke scripting. ADR-0019 W3 is the wave that ships `tools/calibration_harness.py` for exactly this purpose. Until that lands, every ruleset bump will look like the one-off `scripts/calibration/run_w4_calibration.py` was.

## How to contribute

* Phase-labeled XER / MSP files → [issue #13](https://github.com/VitorMRodovalho/meridianiq/issues/13). Synthetic schedules built to exercise specific rules are also welcome.
* **Anonymization checklist before contributing** — XER files routinely carry personal data and recoverable customer identifiers. Strip:
  * company names, project names, project codes, cost-account names, cost values
  * resource names + email addresses + initials (P6 stores them in plain text)
  * custom field free-text and notebook attachments
  * `last_recalc_date` metadata if it could uniquely tag your organization
  * EU contributors: confirm your organization's policy permits the disclosure under GDPR art. 4 / art. 6
  * Brazilian contributors: same under LGPD art. 5 / art. 7
  This is hygiene guidance, not legal advice — when in doubt, do not contribute, or check with your DPO.
* Counter-evidence — schedules where v1's `is_construction_active` flag is wrong — is the highest-signal contribution. Open an issue with a minimal anonymized reproducer and the claimed correct phase.
* Ruleset v2 design discussion: keep it on the same issue thread until volume justifies a separate ADR draft.

## What this post-mortem is not

* Not a vendor disclosure. The 103-XER corpus is owner-curated; per-program identifiers are content-hash and stay in `meridianiq-private`. This document publishes the **outcome distribution** at coarse banding only, per ADR-0009 Amendment 1 §F.
* Not a binding warranty. v1 is shipped under the same MIT licence as the rest of the codebase; the construction-active flag is a best-effort classifier, and the README + `LifecyclePhaseCard` UI both label the rest of the 5+1 surface as `(preview)`.
* Not a substitute for SCL / AACE RP 29R-03 forensic methodology when a delay-claim case is on the line. Use the engine as schedule triage, not as expert testimony.

## Related

* [ADR-0009 — Cycle 1 lifecycle intelligence](../adr/0009-cycle1-lifecycle-intelligence.md) (parent)
* [ADR-0009 W4 outcome](../adr/0009-w4-outcome.md) (formal record)
* [ADR-0016 — lifecycle phase inference + override + lock](../adr/0016-lifecycle-phase-inference.md)
* [ADR-0019 — Cycle 2 entry: Consolidation + Primitive](../adr/0019-cycle-2-entry-consolidation-primitive.md) (W2 B2 honesty-debt closure + W3 calibration harness primitive)
* [Issue #13 — calibration dataset community ask](https://github.com/VitorMRodovalho/meridianiq/issues/13)
