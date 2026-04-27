# 0020. Calibration harness as a reusable primitive for probabilistic-heuristic engines

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-26
* Implements: ADR-0019 §"W3"
* Cites template: ADR-0009 Amendments 1+2 (the W4 calibration that this primitive generalises)

## Context and Problem Statement

Wave 4 of Cycle 1 introduced a one-off calibration script
([`scripts/calibration/run_w4_calibration.py`](../../scripts/calibration/run_w4_calibration.py))
to test the lifecycle phase inference engine against a 103-XER
sandbox before its surface shipped publicly. The protocol —
pre-registered as ADR-0009 Amendment 1 — defined sub-gates §B-§E
that a probabilistic-heuristic engine must pass to ship its full
output as authoritative. The W4 calibration ran, the gate failed at
every threshold for distinct sub-gate reasons, and the engine
shipped with a narrowed authoritative surface (the binary
`is_construction_active` flag — see ADR-0019 §"W2 — B2" and
[`docs/calibration/lifecycle-phase-w4-postmortem.md`](../calibration/lifecycle-phase-w4-postmortem.md)).

The Cycle 2 entry decision (ADR-0019) committed to deferring two
deeper Cycle 3 candidates — A1+A2 auto-grouping and E1
multi-discipline forensic methodology — **gated on a calibration
harness landing first**. Without a reusable harness:

- Each future engine has to copy `run_w4_calibration.py` and rewrite
  the per-engine bits, drifting the protocol code path away from the
  one that produced the W4 outcome record.
- New protocol authors have no shared API to declare against; "the
  pre-registration" devolves into a per-author convention.
- Coarse-banding, manifest format, and publication-scope rules
  (Amendment 1 §F filename-leakage guard) get re-implemented per
  engine, with subtle differences that defeat cross-engine
  comparability.

The primitive missing here is not "another calibration run" but
"the apparatus a future engine author runs *before* shipping the
numeric claim".

## Decision Drivers

1. **Compounding leverage.** The same shape of pre-registration
   discipline applies to auto-grouping, ruleset v2, forensic
   methodology variants, baseline inference, and any future
   probabilistic-heuristic surface. One harness that covers all of
   them eliminates protocol drift across cycles.
2. **Repo-as-record.** ADRs that name the protocol must point at
   a runnable artifact. A primitive that lives in the repo (not as a
   one-off `scripts/` script) lets the ADR cite an importable module
   and a CLI command verbatim.
3. **Publication-scope discipline.** The §F filename-leakage guard,
   the coarse-banding edges, and the three-payload (manifest /
   public / private) split are the parts most prone to "I'll do it
   slightly differently this time". Centralising them makes
   regressions visible.
4. **Solo-maintainer fit.** A reusable harness lowers the cost of
   running a calibration to "register an adapter, register a
   protocol, run the CLI". This is the single biggest leverage on
   the maintainer's time across Cycle 3+.

## Considered Options

### Option 1 — Keep the one-off W4 script as the template

Future engine authors copy `scripts/calibration/run_w4_calibration.py`
and edit it. **Rejected**: the W4 script encodes lifecycle_phase
specifics deep in its core (program-key extraction, recalc-date
tie-break, `phase` label, XER reader). Copies will diverge in
sub-gate evaluation, manifest schema, and §F discipline. Two engines
calibrated this way produce non-comparable results.

### Option 2 — Per-engine ad-hoc calibration scripts

Each engine ships its own script under `scripts/calibration/`. Same
problem as Option 1 plus the explicit acknowledgement that there is
no contract.

### Option 3 — A reusable harness primitive (selected)

A small Python module at `tools/calibration_harness.py` that
generalises the W4 pattern into three abstractions:

- **`Observation`** — engine-agnostic per-fixture row
  (`content_hash`, `program_key_hash`, `label`, `confidence`,
  `parse_error`, `rules_fired`, `metadata`).
- **`EngineAdapter`** — protocol the engine author implements
  (`engine_name`, `engine_version`, `ruleset_version`, `label_set`,
  `unknown_label`, `parse_and_classify`, `dedup_key_priority`).
  Engine authors register the adapter via the `_REGISTRY` dict at
  the bottom of the module.
- **`CalibrationProtocol`** — frozen dataclass holding the §B-§E
  parameters (primary threshold, additional thresholds,
  histogram edges, distribution ceiling, confidence-honesty floor,
  primary pass-rate floor). Pre-registered protocols are committed
  to the `_PROTOCOLS` dict and ADR-cited by name.

Plus:

- **`run_calibration(engine, fixtures, protocol, *, revision_order_key=...)`**
  — library entry point; returns three payloads (`manifest_payload`,
  `public_payload`, `private_payload`) matching the Wave-4 schema.
- **CLI** — `python -m tools.calibration_harness --engine=<NAME>
  --protocol=<NAME> --fixtures=<DIR>`. Writes the three JSON files
  to `--output-dir` (default `/tmp`).

The ad-hoc Wave-4 script remains in `scripts/calibration/` as the
historical record of what was actually run. Future engines call
this primitive instead.

## Decision

**Option 3 is selected.** The primitive lives at
`tools/calibration_harness.py`; the W4 protocol is registered as
`lifecycle_phase-w4-v1`; the lifecycle_phase v1 engine is registered
as the first adapter (so the demo command is runnable without
authoring a new engine). Tests at
[`tests/test_calibration_harness.py`](../../tests/test_calibration_harness.py)
pin §B-§E sub-gate behavior, dedup, hysteresis, coarse-banding,
``Observation`` boundary validation, and the CLI smoke surface
(31+ cases at landing).

> **Caveat — read before assuming "W4 reproduced"**: this commit
> ships the harness pipeline end-to-end, but does NOT reproduce the
> W4 outcome numbers authoritatively. The W4 private manifest
> (`/tmp/w4_manifest.json` / `meridianiq-private/calibration/cycle1-w4/`)
> is a pending operator-archive action carried over from W4 closure.
> Without it, the demo runs on tiny synthetic fixtures from
> `tests/fixtures/`. See §"Negative / accepted costs" for the gap.

### Engine-author contract

To ship a new engine that emits a numeric confidence:

1. Author the engine itself.
2. Implement `EngineAdapter` for it. Register in `_REGISTRY`.
3. Author a `CalibrationProtocol` declaring sub-gate parameters.
   Commit it to `_PROTOCOLS` and cite it in the engine's ADR.
4. Run `python -m tools.calibration_harness --engine=… --protocol=…
   --fixtures=…` against the calibration corpus. **Fixtures must be
   anonymized or sandbox-origin.** Never archive a private payload
   from un-consented customer data — LGPD art. 7 / GDPR art. 6
   lawful-basis hooks both apply, and the per-observation detail
   in the private payload (program-key hashes + label + confidence)
   is enough to uniquely re-identify a customer schedule. Inspect
   the public payload.
5. Author an outcome record (analogous to
   [`docs/adr/0009-w4-outcome.md`](0009-w4-outcome.md)) and a
   public-facing post-mortem (analogous to
   [`docs/calibration/lifecycle-phase-w4-postmortem.md`](../calibration/lifecycle-phase-w4-postmortem.md))
   in the same wave that ships the engine surface.

The harness is the apparatus, not the adjudicator. Whether the gate
passes is recorded in the public payload; the **decision** of what
to ship given a fail is a human Amendment-2-style judgement
(reference: [`0009-w4-outcome.md` §"Decision branch"](0009-w4-outcome.md)).

### Publication-scope discipline (Amendment 1 §F preserved)

* `manifest_payload` — content-hashes only. Safe to commit / link.
* `public_payload` — coarse-banded aggregates only. Safe to publish.
* `private_payload` — per-observation detail with rules-fired and
  program-key hash. **Never commit.** Caller archives to
  `meridianiq-private/calibration/<cycle>-<wave>/`.

The CLI writes the private payload with a `_private.json` filename
suffix so a future repo-side `.gitignore` rule can blacklist the
shape by glob.

## Consequences

**Positive**

* Cycle 3 deeps (A1+A2 auto-grouping; E1 forensic methodology;
  ruleset v2) ship with a calibration entry on day one rather than
  hand-rolling a script per engine.
* Cross-engine comparability: a §C sub-gate failure means the same
  thing in lifecycle_phase v2, auto-grouping, and forensic-attribution.
* The three-payload split is enforced at the function boundary, not
  by author convention. §F filename-leakage guard centralised.
* The harness is small (~470 LoC at landing) and self-contained;
  it has no runtime dependency on the FastAPI app or Supabase, so a
  contributor can run a calibration locally without a full backend
  spin-up.

**Naming break vs the W4 script (one-time)**

The W4 script emitted `numerator_phase_counts` and
`dominant_phase_share_of_numerator` in its public payload. The
harness renames these to `numerator_label_counts` and
`dominant_label_share_of_numerator` so the JSON keys generalise
beyond the lifecycle_phase taxonomy. No public document depends on
the JSON keys (the W4 outcome record uses prose tables), but a
maintainer comparing the two payloads side by side should expect
the rename. The W4 script in `scripts/calibration/` is intentionally
not migrated — it remains the historical record of what produced
ADR-0009 W4 outcome.

**Negative / accepted costs**

* The harness adds another layer for engine authors to learn
  (one Protocol implementation + two registry registrations).
  Mitigated by the lifecycle_phase adapter being committed as a
  worked example.
* The synthetic XER fixtures used for the W3 demo run produce a
  trivially-failed gate (3 fixtures, 1 in gate after dedup —
  insufficient for a meaningful calibration). The demo proves the
  pipeline runs, not that it reproduces the W4 outcome
  authoritatively. Authoritative reproduction requires the archived
  W4 manifest at `meridianiq-private/calibration/cycle1-w4/`,
  which is a pending operator action carried over from W4 closure.
* The harness encodes the W4 §A dedup rule in a callable
  (`engine.dedup_key_priority`) that other engines can override.
  An engine that picks a different dedup pattern can drift away
  from the cross-engine "max(activity_count) tie-break by date"
  norm. This is intentional flexibility — but ADR authors should
  argue explicitly when their protocol diverges.

**Reversibility**

High at the engine-adapter layer; the protocols themselves live as
data in the `_PROTOCOLS` dict and migrate trivially. The cost that
escalates over time is ADR-citation drag: once Cycle 3+ engines cite
`tools/calibration_harness.py` by path in their own ADRs, replacing
the harness module name (or relocating it to `src/`) means
re-citing those ADRs too. Mitigated by the contract surface being
the registry dicts and the `EngineAdapter` Protocol, both of which
are stable abstractions independent of the file location.

## Scope of what this ADR does NOT do

* Does NOT mandate that every engine in `src/analytics/` register an
  adapter. The harness is for engines emitting numeric confidence
  against an evidence-based answer. Deterministic engines (CPM
  forward/backward pass; DCMA 14-point validator) do not have a
  calibration surface — they have a correctness surface, exercised
  by the regular pytest suite.
* Does NOT pre-author future engines' protocols. Each new engine
  authors its own protocol entry in `_PROTOCOLS`, cited from its
  ADR, and that entry is the pre-registration discipline that
  protocol commits to.
* Does NOT replace `scripts/calibration/run_w4_calibration.py`.
  That script remains the historical record of what produced
  ADR-0009 W4 outcome.
* Does NOT change the existing `lifecycle_phase` engine output.
  This ADR is purely apparatus.

## Related

* [ADR-0009 — Cycle 1 lifecycle intelligence](0009-cycle1-lifecycle-intelligence.md) (parent, source of Amendments 1+2)
* [ADR-0009 W4 outcome](0009-w4-outcome.md) (the calibration this primitive generalises)
* [ADR-0016 — lifecycle phase inference + override + lock](0016-lifecycle-phase-inference.md)
* [ADR-0019 — Cycle 2 entry: Consolidation + Primitive](0019-cycle-2-entry-consolidation-primitive.md) (commits W3 to ship this ADR-0020)
* [Calibration post-mortem (W4)](../calibration/lifecycle-phase-w4-postmortem.md)
* [Issue #13 — calibration dataset community ask](https://github.com/VitorMRodovalho/meridianiq/issues/13)
