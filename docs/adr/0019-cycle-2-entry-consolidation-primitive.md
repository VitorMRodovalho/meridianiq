# 0019. Cycle 2 entry — Consolidation + Primitive (Option 4)

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-26
* Triggered by: post-v4.0.2 cycle-entry decision; supersedes the Track 2
  discovery's two recommended deeps (PV A1+A2 + strategist E3) and the
  alternative E1 deep.

## Context and Problem Statement

After v4.0.0 (Cycle 1 close, "Materialized Intelligence") and the
v4.0.1 → v4.0.2 patch arc (Track 1 polish + audit remediation +
i18n closure), the next cycle needs a committed scope. Two candidate
deeps came out of the Track 2 discovery round and a third came from
the alternative branch:

- **PV deep — A1+A2** (auto-grouping of revisions + baseline
  inference) — argued from persona coverage breadth.
- **Strategist deep — E3** (plugin marketplace) — argued from
  compounding-moat thesis.
- **Strategist alternative — E1** (multi-discipline forensic
  security) — argued as the "thinnest-but-real moat" for hypothetical
  Series-A.

Devils-advocate and investor-view in the adversarial round
**both rejected** all three deeps and independently converged on a
fourth path not in the original candidate pool: treat Cycle 2 as
a **consolidation cycle** that ships the primitives every future
deep depends on, rather than betting the cycle on a feature deep or
a platform deep.

The other live forward-track option at the time of this decision is
**#23 Schedule Viewer Wave 7** (cost-loading + EVM overlay; resource
histogram already shipped in v4.0.2). It is a smaller, frontend-heavy
feature wave and does not address the deferred tech-debt list.

This ADR records why Cycle 2 enters as Option 4 and why both the
recommended deeps and the Schedule Viewer Wave 7 alternative are
deferred.

## Decision Drivers

1. **Security debt is enterprise-gating.** The deferred-tech-debt list
   from v4.0.0 + v4.0.1 devils-advocate rounds includes: token in WS
   query string (Fly.io edge logs), no WS re-auth on token expiry,
   no rate limit on `POST /api/v1/jobs/progress/start`, transient TLS
   hiccup = unrecoverable disconnect. Enterprise conversations cannot
   start before these close.

2. **Honesty-debt on lifecycle classifier still open.** v4.0.0
   shipped `lifecycle_phase` v1 as a "preliminary indicator" via
   subtitle copy (v4.0.1) — a cosmetic patch over the W4 calibration
   outcome, not a structural fix. Investor-view's published-post-mortem
   condition (#3) is not satisfied by subtitle text.

3. **Calibration harness is a compounding primitive.** Every future
   probabilistic-heuristic engine (auto-grouping, ruleset v2, forensic
   methodology variants) depends on a pre-registered calibration
   protocol per the W4 lesson. Without the harness, future engines
   ship on vibes and repeat the W4 failure publicly.

4. **PV's persona-coverage argument is valid but premature.** A1+A2
   would unblock 5 of 9 personas — a measurable persona-coverage win.
   But shipping it without a calibration gate replays W4. The harness
   must land first.

5. **Strategist's contributor-flywheel thesis is unfalsified.** Issue
   #13 has near-zero contributor signal at the time of this decision.
   Insufficient signal to bet a whole cycle on E3 or even the lighter
   contributor-bet variants of E1.

6. **Solo-maintainer + reversibility.** Cycle 2 has no must-ship
   bundle; each wave is independently valuable, and the cycle ships a
   tagged release at whatever state lands at the buffer point. Lowest
   burnout risk for a single-developer phase.

## Considered Options

### Option 1 — PV deep (A1+A2: auto-grouping + baseline inference)

Devils-advocate flagged 5 concrete failure modes:

1. No calibration gate on `rapidfuzz WRatio >= 85` against the
   103-XER sandbox. Same probabilistic-heuristic claim class that
   failed at every threshold in W4.
2. Migration `022 UNIQUE(user_id, lower(name))` is identity-by-name,
   not the merge-cascade primitive A1 actually needs across 6+ tables.
3. A2 "baseline" contract undefined relative to SCL + AACE MIP 3.7;
   re-baseline at month 6 inverts every forensic number.
4. `/optimizer` issue #14 was a schema decision, not a shallow bug
   fix — needs a spike before scope. (Note: closed in v4.0.2 via
   `OptimizeResponse` Pydantic schema.)
5. "5 of 9 personas unblocked" is unfalsifiable without measured
   signal.

Honest budget: 7-7.5 waves, not the 5-5.5 PV claimed. Overflow.

**Deferred to Cycle 3**, gated on (a) the W3 calibration harness
landing in this cycle and (b) the merge-cascade migration scoped as
its own wave.

### Option 2 — Strategist deep (E3: plugin marketplace)

Rejected by both devils-advocate and investor-view independently:

1. Plugin architecture already ships (ADR-0006 + `src/plugins/`).
   Zero external plugins after the mechanism went public is the
   strongest possible negative on the contributor-flywheel thesis.
2. `_load_one` runs `entry_point.load()` without subprocess/WASM
   isolation — a malicious plugin executes arbitrary code at startup
   before any sandbox is established. Marketplace-without-isolation
   is a supply-chain liability.
3. Empty marketplace is a *reputation* liability, not just dormant
   backlog — indexed by Google, cited in competitor sales decks.
4. License-attestation burden on a solo MIT-licensed maintainer
   (any GPL plugin = derivative-work violation passing through).
5. Investor-view: a platform marketplace REDUCES the acquirer
   universe. Anti-fit for the most likely strategic acquirer classes.

Honest budget: 4.5-5 waves, not the 2 strategist claimed. Overflow
plus a supply-chain ADR precondition.

**Deferred to Cycle 5+** with explicit gates: (a) `_load_one`
subprocess/WASM sandbox ADR ships; (b) ≥5 external plugins exist;
(c) license-attestation flow is designed.

### Option 3 — Strategist alternative (E1: multi-discipline forensic security)

Rejected because:

1. `src/analytics/forensics.py` plus `delay_prediction.py` and
   `tia.py` already exist; E1 as framed is polish-and-rename, not
   new capability.
2. Delay-attribution apportionment is litigation-risky — SCL vs
   AACE RP 29R-03 half-step vs Keating is a lawyer-consulted decision
   the solo maintainer cannot procure cheaply.
3. Cycle-2 success criterion undefined; "standards-cited methodology
   becomes authoritative reference" is a 10-year brand outcome.
4. Investor-view caveat: E1 is the thinnest-but-real moat option for
   a hypothetical Series-A — but only with measurability, which
   requires the calibration harness Option 4 ships first.

**Deferred to Cycle 3 as the strongest deep candidate, gated on
the W3 calibration harness from this cycle.**

### Option 4 — Consolidation + Primitive (selected)

Cycle 2 commits to no deep. It ships:

1. **Security hygiene** that any enterprise conversation requires.
2. **Honesty-debt closure** on the v4.0.0 lifecycle classifier
   calibration outcome.
3. **Calibration harness as a reusable primitive** — `tools/
   calibration_harness.py`, with the W4 protocol distilled into a
   pre-registration API any engine author can use.

Reversibility: maximum. No deep bet. Solo-maintainer + burnout fit.
Creates optionality for Cycle 3 (E1 deep gated on the harness, A1+A2
deep gated on the harness + merge-cascade migration).

### Option 5 — #23 Schedule Viewer Wave 7 (cost-loading + EVM overlay)

A frontend-heavy feature wave (~1-2 waves) layered on the Schedule
Viewer flagship. Resource histogram already shipped (rendered in
`web/src/routes/schedule/+page.svelte` via
`ResourceHistogramPanel`). Cost-loading and EVM overlay are
nice-to-haves, not enterprise-gating.

**Deferred** because:

- It does not close any item on the deferred-tech-debt list.
- It lands no calibration-harness primitive that future moats compound on.
- The Schedule Viewer is already user-visible production-grade per
  v3.2.0; another visual layer is incremental, not transformational.
- Frontend feature work can be picked up in any cycle with spare
  capacity (similar to A3 MSP first-class surface — slot opportunistically).

## Decision

**Cycle 2 enters as Option 4 — Consolidation + Primitive.** Plan:
4 waves + buffer (~6 realistic with Cycle 1's observed 1.5× scope
ratio). Each wave independently valuable; cycle ships a tagged
release at whatever state lands at the buffer point.

### Wave plan

**W0 — hygiene + decisions (trimmed by v4.0.2 closures)**

- ~~D9 issue #14 `/optimizer` field-mismatch decision spike~~ —
  CLOSED in v4.0.2 via `OptimizeResponse` Pydantic schema +
  `TestOptimizeResponseContract`.
- D10 — `slowapi` in `[dev]` extras so `@limiter.limit` is exercised
  in CI (today every CI run uses `_NoOpLimiter`).
- D1 — rate limit on `POST /api/v1/jobs/progress/start` (per-user
  cap + per-IP rate limit).
- D11 — `destroy()` helper on `useWebSocketProgress` (closes the
  F1 latent-listener-leak follow-up flagged in v4.0.1 devils-advocate).

W0 budget: ~0.3 wave (D9 closure removed half of W0's original mass).

**W1 — WS re-auth + transient-disconnect resilience**

- D3 — WS heartbeat + 4401 close on token expiry. `{type:"auth_check"}`
  ping at 30s cadence; close with 4401 if Supabase refresh hasn't
  replaced the stale token. Frontend composable already maps 4401 →
  `'auth_expired'` (v4.0.1 tested).
- D4 — transient-disconnect recovery. ADR-level branch: poll
  `GET /api/v1/risk/simulations` for 60s on `connection_lost`, OR
  backend exposes last-N-events ring buffer.

W1 budget: 1-1.3 waves.

**W2 — v4.0.0 honesty-debt closure (B2)**

- B2 — `is_construction_active: bool` (authoritative) on
  `GET /api/v1/projects/{id}/lifecycle`, alongside the existing 5+1
  `phase` (explicitly preview-flagged). UI splits: authoritative
  field surfaces directly; 5+1 sits behind a `(preview)` marker.
  Closes the v4.0.0 calibration honesty debt unambiguously.
- Calibration post-mortem doc — methodology, what failed, what v1
  actually does well, what ruleset v2 needs (cf. issue #13). Sign-off
  from `legal-and-accountability` for license + privacy.

W2 budget: 1.5 waves.

**W3 — calibration harness as reusable primitive**

- `tools/calibration_harness.py` — extracts the W4 protocol
  (ADR-0009 Amendment 1) into a CLI: any engine author can
  pre-register a calibration protocol (fixture set, threshold
  sub-gates, hysteresis check, publication scope) and invoke
  `python -m tools.calibration_harness --engine=… --ruleset=… --fixtures=…`.
  Output: coarse-banded aggregate report.
- ADR-0020 — "Calibration harness as a reusable primitive for
  probabilistic-heuristic engines." Cites ADR-0009 Amendments 1+2 as
  the template.
- Demo run against the existing `lifecycle_phase` v1 engine —
  reproduces the W4 outcome from the saved private manifest
  (`meridianiq-private/calibration/cycle1-w4/`).

W3 budget: 1.5 waves.

### Numbering note

The internal Cycle 2 scope memo (`project_v40_cycle_2.md`, authored
2026-04-19) referenced "ADR-0017" as the canonical strategic decision
and "ADR-0018" as the calibration harness primitive ADR. Those numbers
were subsequently taken by the 2026-04-22 audit remediation arc
(ADR-0017 = api_keys dedup, ADR-0018 = cycle cadence). This ADR-0019
**is** the strategic Option 4 decision the memo described — it's the
same content, renumbered to reflect what actually shipped between
the memo authoring and the cycle entry. The calibration harness ADR
will land as **ADR-0020** in W3.

### Pre-registered success criteria

Cycle 2 ships successfully if at close:

1. `/optimizer` page no longer renders undefined stats in production
   (D9 — already closed by v4.0.2; gate met at cycle entry).
2. `POST /api/v1/jobs/progress/start` returns 429 after N per-user
   starts within 1 minute (D1 — verifiable by `curl`).
3. WS heartbeat closes a session with 4401 when a synthetic expired
   token is injected mid-run (D3).
4. A user-visible `is_construction_active` boolean is served by
   `GET /api/v1/projects/{id}/lifecycle` alongside the preview-flagged
   5+1 `phase` (B2).
5. `python -m tools.calibration_harness --engine=lifecycle_phase --ruleset=v1 --fixtures=demo`
   reproduces a coarse-banded aggregate report matching the W4 outcome
   shape (W3).
6. ADR-0019 + ADR-0020 committed, with cross-link to ADR-0009
   Amendment 2.
7. v4.1.0 tagged + GitHub release + CI green.

Cycle 2 fails *gracefully* if ≥3 of the 7 criteria close and the
rest are cleanly documented for Cycle 2.5 or Cycle 3.

## Consequences

**Positive**

- Closes documented enterprise-gating security debt before any
  customer conversation.
- Calibration harness becomes a precondition for future
  probabilistic-heuristic engines — every future deep ships gated on
  real calibration, not vibes.
- B2 + post-mortem closes the v4.0.0 honesty debt structurally,
  satisfying investor-view condition #3 measurably.
- Solo-maintainer fit: no must-ship bundle, graceful failure mode
  pre-registered.
- Maintains audit-closure momentum from v4.0.2 (six audit-spawned
  issues + #14 + #22 closed in one tag) — Cycle 2 continues the
  structural-quality theme rather than pivoting hard to feature work.

**Negative / accepted costs**

- Less immediately user-visible than feature work. The Schedule
  Viewer Wave 7 alternative would have produced more demo-able
  artifacts per wave.
- A1+A2 personas (Owner / Program Director / Cost Engineer) stay
  under-served for one more cycle. The B2 docs partially address
  Program Director.
- Subcontractor and Field Engineer personas remain unaddressed.
  Slotted for Cycle 3 + Cycle 4.
- The published post-mortem (W2) is reputational exposure on the W4
  calibration outcome. Already accepted by investor-view as
  condition #3; the alternative (silently keeping the subtitle hack)
  is worse.

**Reversibility**

- Maximum. No commitments to a future cycle's deep beyond stating
  E1 + A1+A2 are gated on the harness landing first. If Cycle 3
  evidence (issue #13 contributor signal, partnership LOIs, customer
  conversations) reframes the strategic question, Cycle 3 chooses
  freely.

## Scope of what this ADR does NOT do

- Does not assign a Cycle 3 deep. That decision waits for the W3
  calibration harness outputs as evidence input.
- Does not commit to any persona-coverage breadth metric. The PV
  claim "5 of 9 personas unblocked" is explicitly excluded as
  unfalsifiable; revisit when measurable signal exists.
- Does not pre-author ADR-0020. The calibration harness ADR lands in
  W3 with the implementation, citing this ADR + ADR-0009 Amendment 1.

## Related

- ADR-0009 (+ Amendments 1, 2) — Cycle 1 lifecycle intelligence;
  source of the W4 calibration protocol.
- [`0009-w4-outcome.md`](0009-w4-outcome.md) — W4 calibration
  outcome documenting the path-A fallback that opened the Cycle 2
  honesty-debt.
- ADR-0010, ADR-0011 — both `reserved` by ADR-0009; remain reserved.
- ADR-0017, ADR-0018 — 2026-04-22 audit remediation; numbering
  collision noted in the "Numbering note" section above.
- `project_v40_cycle_2.md` (memory) — original scope memo from
  2026-04-19. This ADR is its repo artifact.
