# MeridianIQ — Lessons Learned

This document collects **process + technical lessons** learned across MeridianIQ release cycles. Format follows the cycle structure: each entry summarizes a specific failure mode (or near-miss) and the discipline that closes it.

The intent is **future-self utility**: when planning a similar wave or PR, scan the relevant cycle entry for the failure modes already encountered.

---

## Cycle 6 — H-shape (forced hygiene + hard W2 gate) — ENTRY 2026-05-17

Authored at cycle entry per ADR-0025 success criterion 1. Six anti-sycophancy lessons banked at entry (load-bearing for Cycle 7+ council); close-time lessons will be appended at cycle close.

### Anti-sycophancy lessons banked at entry (Round 2 paired adversarial demolition of Round 1 Z2-DA convergence)

#### L6.1 — Sycophancy-pattern v2 named: post-hoc "compounding primitives" labeling of forced hygiene

- **Setup**: Cycle 6 entry council Round 1 (PV + strategist) converged on Z2-DA (second consecutive Z-shape) framed as shipping "compounding primitives" (audit_log paired writes = multi-tenant readiness; prompt caching = AI cost moat; WCAG-AA frontend = enterprise procurement credential; content_hash at upload = forensic chain-of-custody primitive).
- **What Round 2 (DA + IV) found**: All 4 "primitive" framings are post-hoc rationalization for FORCED hygiene. Bucket A (CVE bumps) + Bucket B floor bumps (mcp<2, fastapi 0.136.1, etc.) were shipping regardless due to external clocks. The "compounding primitive" framing rebrands ~6 wave-units of forced work into virtuous narrative. Structurally identical mechanism to Cycle 5 calibration-theater pattern (ADR-0023 §"Pattern check") — different words, same epistemic move: manufacturing internal evidence of progress while deferring external evidence of demand.
- **Discipline that closes it**: ADR-0025 explicitly DROPS all 4 framings. Cycle 6.5 sycophancy-recurrence trigger fires if any reintroduced in W3+ PR descriptions. DA-as-second-reviewer protocol enforced per `feedback_entry_council_discipline.md` checks PR text against the 4 dropped framings during exit-council.

#### L6.2 — Recursive deferral pattern named: "next cycle is the inflection"

- **Setup**: Round 1 both agents framed "Cycle 7 = inflection point" — either demand-validation arrives OR formally retire personas. Same framing appeared in Cycles 3+4+5 council entries.
- **What Round 2 IV found**: This is a recursive deferral pattern, not a Cycle 6 problem. Structural to the maintainer-as-PM-and-IC-and-strategist loop where shipping a wave provides falsifiable feedback (CI pass/fail in minutes) but customer-development does not (silence is ambiguous over weeks). The loop selects against the harder signal.
- **Discipline that closes it**: H-shape W2 HARD GATE breaks the recursion at mid-cycle, not next-cycle. 5 CDs OR persona-retirement-ADR is the first non-optional demand-validation surface in 6 cycles. Cycle 7 entry council can re-evaluate whether the methodology amendment proposed under decision 4 caveat (require Round 1 to challenge candidate pool before proposing scope) addresses the deeper root cause.

#### L6.3 — Complementary anti-sycophancy trap named: "we're being honest about constraints, therefore the conservative path is correct"

- **Setup**: Both Round 1 agents performed the anti-sycophancy work explicitly demanded by Cycle 5 close (no PV escalation framing on Field/Sub deferral; no strategist inside-ideology corpus/lawyer paths). Then both used the honest-constraint stance as object-level validation of the Z2-DA conservative choice.
- **What Round 2 (both DA + IV) found**: Honest meta-stance ≠ validation of object-level conclusion. "We're not over-claiming, therefore our conservative path is correct" is structurally identical to over-claiming — both use meta-stance as evidence for object-level. Honest meta-stance is "we're honest about constraints AND we cannot tell whether the conservative path is correct without external signal we don't have."
- **Discipline that closes it**: ADR-0025 §"Honest disclosures" #1 names this explicitly: "This cycle is 'forced + honest, NOT validated'. Chairman synthesis explicitly acknowledges the H-shape is least-wrong-among-bad-options, not best-validated."

#### L6.4 — Solo maintainer burnout vector recalibrated: monotony + isolation + lack-of-feedback, NOT scope ambition

- **Setup**: Round 1 framed Z2 as "protecting maintainer from burnout" via scope-restriction.
- **What Round 2 DA found** (citing Eghbal 2020 "Working in Public" + solo-OSS post-mortem evidence): for solo OSS with 24-month runway and no external feedback loop, the burnout vector is MONOTONY + ISOLATION + lack-of-validation. 5 consecutive Z cycles with zero demand signal IS the burnout vector. Round 1 inverted this.
- **Discipline that closes it**: H-shape pairs forced hygiene with mandatory demand-validation surface — provides the external-feedback novelty that scope-restriction-alone removes.

#### L6.5 — Base-rate prior named: solo OSS in 2nd consecutive consolidation cycle without external validation → maintenance mode within 6-18 months (modal outcome)

- **Setup**: Round 1 claimed "Z2 is healthy if it ships compounding primitives; THIRD Z would be stale."
- **What Round 2 DA found**: Empirical signature of stalled solo OSS is exactly (a) increasingly hygiene-dominated cycles, (b) deferred outreach, (c) "we're being mature about scope" framing, (d) consistent graceful-threshold passes. MeridianIQ at Cycle 6 entry has all four. "Healthy 2nd time" claim requires evidence; Round 1 provided none beyond burnout-avoidance (which L6.4 shows inverts the vector).
- **Discipline that closes it**: Banked for Cycle 7+ council reckoning. If Cycle 6 W2 GATE met cosmetically, the 4 markers continue accumulating; Cycle 7 entry must explicitly weigh whether the pattern has crossed the maintenance-mode threshold.

#### L6.6 — TAM/SAM/SOM honest numbers banked: $40-60M / $8-15M / $0 Cycle 6 base case

- **Setup**: Neither Round 1 agent computed TAM/SAM/SOM. Acquisition-path framing (strategist) was conditional-on-future-cycles without underwriting evidence.
- **What Round 2 IV found**: TAM (construction scheduling intelligence US+LATAM, OSS-addressable) = $40-60M after halving for OSS-substitution ceiling. SAM (P6/MSP/Unifier users with analytics-layer budget vs services from incumbent EPCM consultancies) = $8-15M. SOM Cycle 6 horizon (solo-founder, MIT-licensed, zero reference customers, no sales motion, no GTM primitive in wave plan) = $0-50k base case, **$0 modal**. Acquisition path realism: investor pass memo writes itself — "Strong engineering, no demand evidence, founder pattern shows recursive deferral of CD."
- **Discipline that closes it**: Banked permanently in ADR-0025 §"Honest disclosures" #5 + this lesson. Any future "moat" or "acquisition" claim in council must reckon with these numbers. They are now part of the council record, not separate intelligence.

### Process lessons from Cycle 6 entry council mechanics

#### L6.7 — Off-list Chairman synthesis pattern is now structural across 3 cycles (Cycles 4+5+6)

- **Pattern**: Cycle 4 ADR-0023 (path-A pre-registered + executed), Cycle 5 ADR-0024 (Z-shape off-list from Round 2 paired demolition), Cycle 6 ADR-0025 (H-shape off-list from Round 2 paired demolition).
- **DA exit-council finding on PR #135**: "A Cycle 7 entry-council reader picking up only ADR-0025 will infer that the off-list Chairman synthesis pattern continued (Round 1 unanimous → Round 2 demolition → off-list), now establishing it as the de facto council outcome rather than an exception. The honest cost: Cycle 6 was the third consecutive cycle where Round 1 unanimity got demolished — calling into question whether Round 1 agents are actually adversarial enough, or whether the council protocol structurally selects for Round 1 sycophancy by giving them the constrained candidate pool first."
- **Open question for Cycle 7 entry council** (per ADR-0025 operator decision 4 caveat): "Should Round 1 agents be required to challenge the planning memo's candidate pool BEFORE proposing scope?" Council protocol amendment candidate.

---

## Cycle 5 — Z-shape consolidation (closed at `v4.3.0`, 2026-05-09)

Authored 2026-05-09 evening at cycle close. Per ADR-0024 success criterion 8.

### Process lessons

#### L5.1 — Entry-council MANDATORY on substantive scope, regardless of priority label

- **Setup**: PR #104 (W3 PR-A, pre-Cycle-5 W3-A) was P3-priority (a polish PR per the cycle planning). The reviewer council was skipped on the assumption "P3 priority = P3 correctness-risk = no council needed".
- **What happened**: 4 P0 findings surfaced post-impl (2 in DA exit-council, 2 in user QA). Inversion of `direction = sign(cusum_value)` to `sign(delta_days)`, missing `methodology=""` fallback on error path, etc.
- **Discipline that closes it**: `feedback_entry_council_discipline.md` — backend/frontend-reviewer entry-council MANDATORY on substantive scope (schema-additive, semantic-mapping, wrapper additions). **Size is NOT a valid skip criterion. Priority is NOT a valid skip criterion.** This lesson was already codified in memory before Cycle 5; Cycle 5 reinforced it with 5/5 W3 PRs running entry-council.

#### L5.2 — DA exit-council finds what entry-council misses

- **Pattern across W3**: 5/5 W3 PRs went through both entry-council (pre-impl) AND DA exit-council (post-impl).
- **DA findings count**: PR #115 (3 P1 + 1 P2), PR #116 (3 P1 + 4 P2/P3), PR #118 (2 P1 + 4 P2/P3). All 8 P1s addressed inline; the P2/P3s tracked as follow-up issues.
- **Lesson**: Entry-council validates feasibility + UX; DA exit-council validates correctness post-implementation. They are **complementary, not redundant**. Skipping either hurts the cycle.

#### L5.3 — Honest framing on missed targets is the discipline, not target avoidance

- **Setup**: Cycle 5 W4 hygiene memo target was "0 mypy `--strict` errors". Realistic baseline pre-stubs was 306 errors; post-stubs is 350 (stubs reveal previously-masked errors).
- **What happened**: Hit the "0 errors" target was unachievable in W4 scope. Two paths considered: (a) descope W4 (don't add stubs), (b) ship stubs + honest framing in CHANGELOG + file follow-up.
- **Choice**: Path (b). CHANGELOG documents "stubs in place" milestone instead of "0 errors achieved", with explicit framing on why the count went UP. Filed [#121](https://github.com/VitorMRodovalho/meridianiq/issues/121) for systematic cleanup.
- **Lesson**: This pattern repeats from Cycle 1 W4 + Cycle 4 W4 path-A activations. **The discipline is naming the target reset honestly, not avoiding the work that requires it.** Every cycle that lands a partial-target comes with public framing in CHANGELOG; future contributors get the real picture.

#### L5.4 — Single-PR vs split: blast-radius cost vs review cohesion

- **Setup**: PR #118 (W3-E, #84) was the largest PR in the wave: 875 LoC across 12 files (migration, store, endpoints, schemas, tests, frontend wire, i18n).
- **Choice offered to user**: Single-PR vs split into W3-E1 (backend) + W3-E2 (frontend). User chose single-PR.
- **Outcome**: Single-PR succeeded; review surface large but cohesive. DA exit-council still found 2 P1 (silent dev/prod count divergence + skip race), addressable inline.
- **Lesson**: Single-PR is the right call when the change is **internally coupled** — backend table + endpoint + frontend wire all need to land together for the feature to work. Split is the right call when the layers are **independently shippable** (e.g., a refactor that doesn't change behavior). #84 was the former.

#### L5.5 — Stats-catalog regen is a pre-PR mental checklist item, not a CI auto-recovery

- **Setup**: PR #118 added 2 endpoints + migration 029. First push to PR triggered CI failure on "Verify catalogs match source" (endpoint count drift 127 → 129; migration count 28 → 29).
- **What happened**: Took an extra commit (and CI cycle) to fix.
- **Discipline that closes it**: When a PR adds endpoints, run `python scripts/generate_api_reference.py` locally before pushing. Same for migrations + the README/CLAUDE.md/architecture.md catalog references.
- **Lesson**: The CI gate is the safety net, not the primary check. Adding a "regenerate catalogs" reminder to the PR-creation mental checklist saves an extra round-trip.

### Technical lessons

#### L5.T1 — PostgREST DELETE without `Prefer: return=representation` returns empty body

- **Setup**: PR #118 `clear_revision_skips` SupabaseStore helper returned `len(res.data or [])` from a `.delete().eq().eq().execute()` chain.
- **Failure mode**: PostgREST DELETE without explicit `returning` parameter returns NO body. `res.data` is `[]` even when N rows were deleted. **`cleared_count` would always be 0 in production while InMemoryStore tests pass.** Frontend's `cleared_count === 0` toast fires incorrectly + telemetry permanently 0.
- **DA exit-council**: caught this during PR #118 review. Same dev/prod divergence shape as BUG-007 / PR #104 silent-no-op precedent / tombstone audit_log_id race.
- **Fix**: Two-round-trip pattern (SELECT then DELETE, return SELECT count). Extra round-trip on a manual-button reconsider call (rare, operator-paced) is acceptable and dodges the supabase-py version-contract question.
- **Lesson**: ALWAYS verify SDK-level return-shape contracts when porting from InMemoryStore to SupabaseStore. The InMemoryStore is a TEST DOUBLE, not a CONTRACT MIRROR.

#### L5.T2 — Svelte 5 runes work in `@testing-library/svelte` v5 + jsdom

- **Setup**: PR #114 (W3-B) needed a Vitest harness for RevisionConfirmCard.
- **Spike result**: `@testing-library/svelte@5.3.1` + Svelte 5.55.5 + jsdom 29 + Vitest 4 — `$state` / `$derived` / `$effect` / `$props` all work without Playwright dependency.
- **Lesson**: `vitest-browser-svelte` (browser + Playwright) was the alternative path; the spike validated jsdom is sufficient for component tests today. Saved a Playwright dependency + browser CI infrastructure overhead. **30-minute spikes pay for themselves.**

#### L5.T3 — `Intl.DateTimeFormat` defaults to viewer-local TZ; force UTC for domain-naive dates

- **Setup**: PR #115 (W3-C) `formatDate` helper for revision-confirmation card data_date.
- **Failure mode**: P6 `data_date` is timezone-naive by domain convention. `Intl.DateTimeFormat` defaults to the viewer's local TZ — a UTC midnight ISO `2026-04-15T00:00:00Z` viewed in UTC-3 renders as "Apr 14".
- **Discipline that closes it**: Force `timeZone: 'UTC'` in options. Make the override **non-overridable at TypeScript level** via `Omit<Intl.DateTimeFormatOptions, 'timeZone'>` so callers compile-fail rather than fail silently. DA exit-council on PR #115 caught a fallback day-shift bug for offset-bearing ISOs (the `iso.slice(0, 10)` shortcut also breaks here); switched fallback to `parsed.toISOString().slice(0, 10)`.
- **Lesson**: When formatting dates from domain-specific schemas (P6 data_date, contract dates, baseline_lock_at, etc.), be explicit about TZ semantics in the helper signature. Viewer-local default is the wrong policy for domain-naive dates.

#### L5.T4 — Structured `error_code` > fragile text-match for 4xx differentiation

- **Setup**: PR #116 (W3-D) replaced text-pattern detection of cap-vs-other 4xx errors (introduced in PR #83) with structured `error_code` field on the response body.
- **Failure mode the structured form prevents**: a future i18n change that translates "revision cap reached" → "limite de revisões atingido" would break the `/revision cap/i` regex match silently, and the localized cap message would never surface.
- **Caveat**: PR #116 itself introduced fragile text-match on the cap-vs-unique disambiguation at `revisions.py:215-217` (`"cap" in message.lower()`). DA exit-council caught it. Filed [#117](https://github.com/VitorMRodovalho/meridianiq/issues/117) for typed-exception refactor.
- **Lesson**: When designing API error contracts, **use machine-readable codes**, not human-readable text. When implementing one error contract, audit your OWN code for the same anti-pattern you're fixing.

### Cycle-close discipline reinforced this cycle

- **6/6 PRs ran DA exit-council** per ADR-0018 Amendment 1
- **5/5 W3 PRs ran entry-council** per `feedback_entry_council_discipline.md`
- **4 follow-up issues filed** during cycle (#117 / #119 / #120 / #121) — each tracked specifically vs left as TODO comments in code
- **Honest CHANGELOG framing** on W4 partial close
- **Memory file refresh** at cycle close (`project_state.md` + `project_resume_next_session.md`)

---

## Future cycles

Each cycle close should append a new section above this one. Do NOT delete prior cycles' lessons — they accumulate as repository memory.
