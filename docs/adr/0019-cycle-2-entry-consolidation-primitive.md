# 0019. Cycle 2 entry — Consolidation + Primitive (Option 4)

* Status: accepted — amended 2026-04-27 (**Amendment 1**: rate-limit policy contract; see end of file)
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

---

## Amendment 1 (2026-04-27) — Rate-limit policy contract

* Status: accepted
* Date: 2026-04-27
* Trigger: [AUDIT-2026-04-26-005 (P3)](../audit/2026-04-26/04-security.md) — the rate-limit buckets defined in W0 (D1) lacked an in-repo policy contract + enforcement test; ad-hoc decorator literals had drifted across routers. Tracked under [#45](https://github.com/VitorMRodovalho/meridianiq/issues/45).

### Context

ADR-0019 §"W0 — D1" introduced `RATE_LIMIT_READ = "30/minute"` for the WS progress endpoint and added `slowapi` to `[dev]` extras (D10) so CI exercises the real limiter. After Cycle 2 close + Cycle 3 W4, three buckets exist in `src/api/deps.py:138-140`:

```python
RATE_LIMIT_EXPENSIVE = "3/minute"
RATE_LIMIT_MODERATE = "10/minute"
RATE_LIMIT_READ = "30/minute"
```

But: the buckets had no documented application policy. AUDIT-2026-04-26-005 enumerated the gap — 18 write endpoints had NO `@limiter.limit` decorator at all; existing decorators used a mix of constants + literal strings (`"5/minute"`, `"10/minute"`, `"60/minute"`) without a written rule for which to use where.

This Amendment closes the policy gap by codifying the heuristic + an enforcement test.

### The policy

**Rule 1 — Write coverage.** Every endpoint with HTTP method `POST/PUT/PATCH/DELETE` MUST have `@limiter.limit(...)` (any value), UNLESS the endpoint is on the `APPROVED_EXCEPTIONS` list in `tests/test_rate_limit_policy.py` with a documented rationale.

**Rule 2 — Expensive coverage.** Every endpoint whose path or function name matches `EXPENSIVE_PATTERNS` (Monte Carlo simulate, schedule build, plugin run, what-if/pareto/leveling, evolution optimize, PDF generate) MUST have a rate limit ≤ 5/minute (`RATE_LIMIT_EXPENSIVE` = 3/min preferred; literals `"3/minute"`–`"5/minute"` accepted).

**Rule 3 — Exception discipline.** Any addition to `APPROVED_EXCEPTIONS` requires a one-line rationale in the test file. Reviewers should challenge the rationale on PR.

**Bucket choice (informal):**

| Bucket | Rate | Use for |
|---|---|---|
| `RATE_LIMIT_EXPENSIVE` | 3/min | Monte Carlo, evolution optimizer, pareto search, resource leveling solver, schedule build (CPM from scratch), plugin run (untrusted), PDF generate, what-if simulation |
| `RATE_LIMIT_MODERATE` | 10/min | XER round-trip, batch CRUD, MIP forensic windows, exports, write endpoints not in EXPENSIVE class |
| `RATE_LIMIT_READ` | 30/min | Single-resource GETs (when GET-rate-limit is added — currently optional per §"What this Amendment does NOT enforce") |
| Literal `"N/minute"` | Various | Acceptable forms: `"5/minute"` is the standard moderate-write rate before constants existed; preserved for backward-compat. Future PRs may convert to constants. |
| **No decorator** | n/a | Healthchecks (`/health`, `/api/v1/health`); admin-scope auth-gated endpoints (auth IS the throttle); endpoints in APPROVED_EXCEPTIONS |

### Empirical state at amendment time (2026-04-27, updated 2026-04-28 post-#57, post-N5/#68)

- **112 total endpoints** across 23 routers (floor — adds-only over time)
- **38 write endpoints**: 36 with `@limiter.limit` after the #45 + DA-review + #57 rename + #57 fix-up commits, 2 user-self-action exceptions (`require_auth`-gated; per-JWT auth-throttle), 0 deferred (#57 closed the body-collision deferral)
- **EXPENSIVE-pattern coverage**: 8 write endpoints match `EXPENSIVE_PATTERNS` (the test-file-defined matchers). All 8 are decorated with a Rule-2-compliant rate (`RATE_LIMIT_EXPENSIVE` or literal ≤ 5/min):
  - `plugins.run_plugin` (`/plugins/...`) → `RATE_LIMIT_EXPENSIVE` (added in #45)
  - `risk.run_risk_simulation` (`/risk/simulate`) → `RATE_LIMIT_EXPENSIVE`
  - `whatif.optimize_schedule_endpoint` (`/optimize`) → `"5/minute"` literal — **N5 (#68) intentionally retained the literal at this site**: every other callsite was converted to a constant, but folding this one under `RATE_LIMIT_WRITE` would have hidden the deliberate non-default rate (EXPENSIVE-pattern at WRITE bucket) behind a name that promises "ordinary write endpoint", risking silent relaxation if a future PR bulk-tunes WRITE. See inline comment at `src/api/routers/whatif.py:353-354`.
  - `whatif.run_what_if` (`/what-if`) → `RATE_LIMIT_EXPENSIVE` (added in #57)
  - `whatif.run_pareto_analysis` (`/pareto`) → `RATE_LIMIT_EXPENSIVE` (added in #57)
  - `whatif.run_resource_leveling` (`/resource-leveling`) → `RATE_LIMIT_EXPENSIVE` (added in #57)
  - `schedule_ops.build_schedule_endpoint` (`/schedule/build`) → `RATE_LIMIT_EXPENSIVE` (added in #57)
  - `reports.generate_report` → `RATE_LIMIT_EXPENSIVE`
- **Defensive promotions** (NOT `EXPENSIVE_PATTERNS`-matched, but DA-promoted to `RATE_LIMIT_EXPENSIVE`): `admin.reconcile_ips` + `admin.validate_recovery` — both `optional_auth` (anonymous-callable) + compute-heavy. These do NOT count toward the "8" above; they are a separate hardening from the same DA-review session that birthed #45.
- **#57 fix-up scope expansion (DA-caught)**: the issue body listed 6 `request: <Pydantic>` body-collision endpoints. A fresh AST sweep during #57's DA exit-council found 3 more in the same failure class — `comparison.compare_schedules`, `tia.tia_analyze`, `schedule_ops.generate_schedule_endpoint` — all with `@limiter.limit` decorators but no `Request`-typed parameter, so slowapi was silently failing at runtime. All 3 fixed in the same #57 PR (rate values preserved: `"20/minute"`, `"10/minute"`, `"5/minute"` literals).
- **Post-N5 (#68, 2026-04-28)**: 13 of 14 literal callsites converted to constants. The single remaining literal — `whatif.optimize_schedule_endpoint` (`"5/minute"`) — is the documented EXPENSIVE-pattern-at-WRITE-rate exception described above. Three new constants introduced (`RATE_LIMIT_WRITE = "5/minute"`, `RATE_LIMIT_ANALYSIS = "20/minute"`, `RATE_LIMIT_LIGHT = "60/minute"`) to consolidate values that previously lived only as literals. `Limiter.default_limits` now references `RATE_LIMIT_LIGHT` instead of literal `"60/minute"`.
- *(Historical, pre-N5)*: Mix of constants (~20 callsites) and literals (~14 callsites) — mid-state during convention adoption (`#57` added 6 constant uses + 3 literal preserves).

### Enforcement

`tests/test_rate_limit_policy.py` (6 tests) parses each router via AST and applies the four rules. CI catches:

- A new write endpoint added without a limiter decorator (violation of Rule 1)
- A new expensive endpoint added at MODERATE/READ rate (violation of Rule 2)
- An exception entry without rationale (violation of Rule 3)
- An exception entry pointing at a non-existent endpoint (dead weight)
- A `@limiter.limit`-decorated endpoint with no `Request`-typed parameter (violation of Rule 4 — slowapi can't extract the IP, decorator silently no-ops or raises in production while Rules 1+2 pass). Rule 4 was added by #57 after a DA exit-council found 3 silent-failure cases (`comparison.compare_schedules`, `tia.tia_analyze`, `schedule_ops.generate_schedule_endpoint`) that Rules 1+2 marked compliant.

### Negative / accepted costs

- **Pattern matching is heuristic.** EXPENSIVE_PATTERNS uses substring match against `<path> <function_name>`. False positives (a GET that happens to contain "/optimize" in its path but doesn't compute) are excluded by Rule 2's GET-skip clause. False negatives (a write endpoint that's expensive but doesn't match any pattern) require pattern refinement when discovered — the test file is the source of truth.
- **MIP forensic analyses chose MODERATE not EXPENSIVE.** Each MIP runs a window-by-window CPM (e.g., 10 windows × 10 days = 10 CPM passes); heavy but not Monte-Carlo-class. The maintainer's existing decision (`@limiter.limit(RATE_LIMIT_MODERATE)` on six MIP endpoints) is preserved by narrowing EXPENSIVE_PATTERNS to exclude broad "forensic" — the policy follows existing reasoned decisions, not a fresh-bucket-per-endpoint rewrite.
- **`request:` parameter collision closed (#57, 2026-04-28).** Issue #57 originally targeted 6 endpoints (3 in `whatif.py`, 1 in `forensics.py`, 1 in `analysis.py`, 1 in `schedule_ops.py`) that took a Pydantic body parameter named `request: <SomeRequest>`, which collided with the `request: Request` slowapi requires. The PR's exit-council DA review found 3 *additional* endpoints in the same failure class (`comparison.compare_schedules`, `tia.tia_analyze`, `schedule_ops.generate_schedule_endpoint`) that the issue body had missed — these had `@limiter.limit` decorators but no `Request` parameter at all, silently no-op'ing in production. All 9 fixed in the #57 PR.

  **Convention normalization (PR #64, 2026-04-28).** A follow-up refactor consolidated all `@limiter.limit`-decorated body-bearing endpoints to a single Convention A (`request: Request, body: <Pydantic | dict>`). Pre-#64 the codebase carried four conventions; PR #64 migrated all of B/C/D to A. **Critical disclosure: the PR was originally drafted as a 9-endpoint migration; the exit-council DA review caught a 10th endpoint (`risk.run_risk_simulation`) on a 4th convention that the issue body had missed — same recurrent ADR-citation/empirical-claim drift pattern flagged on PR #36/#38/#39/#56/#58/#60.**
  - **Convention A — rename to `body`** (now codebase-wide): `request: Request, body: <Pydantic | dict>`
  - **Convention B — sibling `_http_request: Request`** (was: `forensics.py` 6 MIP/half-step endpoints + `reports.generate_report`): `request: <Pydantic>, _http_request: Request` — **migrated to A in PR #64**
  - **Convention C — `request_body` rename** (was: `admin.reconcile_ips` + `admin.validate_recovery`): `request: Request, request_body: dict` — **migrated to A in PR #64**
  - **Convention D — `payload` rename** (was: `risk.run_risk_simulation`, the historical Convention A precedent before `optimize_schedule_endpoint` standardized on `body`): `request: Request, payload: <Pydantic>` — **migrated to A in PR #64 fix-up**

  All four conventions satisfied slowapi (Rule 4) and FastAPI's body auto-binding (parameter name is irrelevant for routing once the body type is annotated); the consolidation is hygiene, not correctness. **Rule 4 (added in #57) catches future regressions of the silent-failure class structurally**: the AST walker records each function's parameter annotations, and any `@limiter.limit`-decorated function without a `Request`-typed parameter fails the test. **A runtime spot-check (PR #63, `tests/test_rate_limit_runtime.py`)** correlates Rule 4 to actual slowapi runtime behavior on `build_schedule_endpoint` (sample-of-N=2 with the long-standing `TestOptimizeRateLimit`); not a parameterized harness.
- **Constants vs literals not enforced.** Both forms count as rate-limited. **Closed by PR #68 (N5, 2026-04-28)**: 13 of 14 literal callsites converted to constants for grep-discoverability + audit-friendliness. The 14th (`whatif.optimize_schedule_endpoint`) retains its literal as a documented exception (see §"Empirical state" line 389). `tests/test_rate_limit_policy.py:is_expensive_bucket` was extended to resolve constant names through a `CONSTANT_TO_RATE` lookup imported from `src.api.deps`, so a future rate-value tweak (e.g., `RATE_LIMIT_WRITE` "5/minute" → "8/minute") propagates without a test edit.

### Cross-references

- [AUDIT-2026-04-26-005 (P3)](../audit/2026-04-26/04-security.md) — formal audit finding
- Issue [#45](https://github.com/VitorMRodovalho/meridianiq/issues/45) — tracking
- `tests/test_rate_limit_policy.py` — the enforcement test file
- `src/api/deps.py:138-140` — bucket constants
- ADR-0017 §"Decision Outcome" — original rate-limit context (api_keys fail-closed); orthogonal to this policy
