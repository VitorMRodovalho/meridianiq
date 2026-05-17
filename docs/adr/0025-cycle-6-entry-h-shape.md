# 0025. Cycle 6 entry — H-shape (forced hygiene + hard discovery gate at W2)

* Status: proposed
* Deciders: @VitorMRodovalho
* Date: 2026-05-17
* Cites template: [ADR-0019](0019-cycle-2-entry-consolidation-primitive.md) + [ADR-0021](0021-cycle-3-entry-floor-plus-field-shallow.md) + [ADR-0022](0022-cycle-4-entry-beta-honest.md) + [ADR-0024](0024-cycle-5-entry-z-shape-consolidation.md) (cycle entry pattern; 4-agent council protocol; off-list Round 2 convergence pattern)
* Cites lessons: [ADR-0023 §"Pattern check vs. ADR-0009"](0023-cycle-4-w4-outcome.md) (calibration-theater confrontation; this ADR identifies sycophancy-pattern v2 as the same mechanism reapplied)
* Cites operational artifacts: PR #129 (Bucket A pre-W0 unconditional CVE + Claude model migration shipped 2026-05-17); follow-up issues #130 (live Claude integration test), #131 (CI dep-floor verify step), #132 (centralize Claude model literal), #133 (Svelte XSS bump)

## Context and Problem Statement

Cycle 5 closed at v4.3.0 (2026-05-09) per [ADR-0024](0024-cycle-5-entry-z-shape-consolidation.md) Z-shape consolidation, 7/9 graceful with margin. Operator items closed: migration 029 applied, LESSONS_LEARNED Cycle 5 entry shipped, README.md synced, engine_version 4.2→4.3 lazy re-mat policy adopted. W5 Z-IV active outreach (AACE/PMI working-group inquiry) was DEFERRED at Cycle 5 close as operator-paced; pre-ratification disclosures stood (runway > 24mo, AACE/PMI member with prior contacts).

The 2026-05-17 45-day ecosystem scan (5 parallel research agents across Anthropic/Supabase/Python/Frontend+CI/Construction-standards verticals) surfaced 3 P0 items with external clocks: (a) Claude Sonnet 4 (`claude-sonnet-4-20250514`) retired 2026-06-15 — `src/analytics/schedule_builder.py:63` exposed; (b) `weasyprint` CVE-2025-68616 SSRF fixed in 68.0 (current pin `>=62.0` permitted 6 vulnerable releases); (c) `PyJWT` CVE-2026-32597 `crit` header bypass fixed in 2.12.1 (current pin `>=2.12` permitted vulnerable 2.12.0). These shipped pre-W0 unconditional as PR #129 (squash-merged + deployed live to Fly.io + Cloudflare Pages on 2026-05-17). PR #129's DA exit-council audit trail filed 4 follow-up issues (#130/#131/#132/#133). The 45-day scan also surfaced ~10 RECOMMENDED hygiene items (Bucket B) and confirmed Bucket A is the only emergent forcing-function class.

The 2026-05-17 evening Cycle 6 entry council ran the 4-agent protocol (PV + strategist Round 1 parallel; DA + IV Round 2 paired adversarial per [ADR-0022 NFM-9](0022-cycle-4-entry-beta-honest.md)).

**Round 1** converged strongly on a single path: PV primary "Z2-DA" + Strategist primary "Z-DA-2" = **same path**: second consecutive Z-shape consolidation cycle, narrowly scoped, framed as "compounding primitives" (audit_log paired writes / Anthropic prompt caching / WCAG-AA frontend a11y / content_hash at upload). 5 nominal / ~7.5 actual waves. Both Round 1 agents performed the anti-sycophancy work demanded by Cycle 5 close — refused to escalate Field/Sub persona framing without external evidence; refused to propose AACE/PMI/corpus/lawyer paths without crossable preconditions.

**Round 2** (DA + IV paired adversarial) REFUSED to validate Round 1 convergence. Both independently surfaced:

1. **"Compounding primitives" = sycophancy-pattern v2** — DA framed sharpest: post-hoc rationalization for FORCED hygiene (Bucket A + Bucket B floor bumps shipping regardless due to CVE windows + Claude retirement + `mcp<2` SDK breaking + FastAPI/Starlette major substrate bump). IV: different words, same calibration-theater mechanism as Cycle 5 Path C — manufacturing internal evidence of progress while deferring external evidence of demand. The "primitive" framing turns ~6 wave-units of forced work into virtuous narrative.

2. **"Cycle 7 = inflection" = recursive deferral pattern** (IV finding) — same framing appeared in Cycles 3+4+5+6. Structural to the maintainer-as-PM-and-IC-and-strategist loop where shipping a wave provides falsifiable feedback (CI pass/fail in minutes) but customer-development does not (silence is ambiguous over weeks). The loop selects against the harder signal. NOT a Cycle 6 problem — a methodology problem that Z2-DA would preserve.

3. **Anti-sycophancy COMPLEMENTARY trap CONFIRMED** — both Round 1 agents removed escalation framing (good) but then used "we're being honest about constraints" as itself a validating proof for the conservative choice. Honest meta-stance ≠ validation of object-level conclusion. Both DA and IV named this independently as the structural failure of Round 1's convergence.

4. **Solo-maintainer burnout vector inverted** — Round 1 framed Z2 as protecting maintainer from burnout via scope-restriction. DA counter (citing Eghbal 2020 "Working in Public" + solo-OSS post-mortems): burnout vector for solo OSS with 24-month runway and no external feedback loop is MONOTONY + ISOLATION + lack-of-validation, NOT scope size. 5 consecutive Z cycles with zero demand signal IS the burnout vector.

5. **"Z-shape healthy 2nd time" claim base-rate-prior unsupported** — DA: solo OSS in 2nd consecutive consolidation cycle without external validation → maintenance mode within 6-18 months (modal outcome). Empirical signature of stalled solo OSS is exactly: (a) increasingly hygiene-dominated cycles, (b) deferred outreach, (c) "we're being mature about scope" framing, (d) consistent graceful-threshold passes. MeridianIQ has all four.

6. **TAM/SAM/SOM honest numbers** (IV finding; neither Round 1 agent computed): TAM $40-60M (construction scheduling intelligence US+LATAM, OSS-licensed addressable). SAM $8-15M (P6/MSP/Unifier users with budget for analytics layer on top — most buy services from incumbent EPCM consultancies instead). **SOM Cycle 6 horizon = $0-50k base case, $0 modal** because no GTM primitive in any Round 1 wave plan. Any future "moat" claim must reckon with these numbers.

7. **Acquisition path "hoping not planning"** (IV) — strategist's "acquisition realistic IF cycles 7-10 hit demand-validation" is hoping. Investor-grade underwriting requires named acquirer shortlist + reference customer pipeline + revenue/LOI. MeridianIQ at Cycle 6 has zero of three. Pass memo writes itself: "Strong engineering, no demand evidence, founder pattern shows recursive deferral of customer development."

Both Round 2 agents demanded **HARD demand-validation surface as non-optional for Cycle 6**, refusing the "operator-paced optional" framing that Cycle 5 W5 used and that left Z-IV unexecuted. DA: grudging approval of Z2-DA-MINUS (drop #79 content_hash + drop all 4 primitive framings) + hard-required Z-IV. IV: AMEND WITH PRECONDITIONS — Z2-DA proceeds ONLY if 5 customer-development conversations logged by W2 close, OR BLOCK + pivot Cycle 6.5 to discovery-only.

This ADR records the council protocol output, the H-shape OFF-LIST recommendation accepted by the maintainer, and pre-registers Cycle 6 entry under those terms.

## Decision Drivers

1. **Bucket A (security CVEs + Claude retirement) is already shipped via PR #129** as pre-W0 unconditional. Bucket B forced floor bumps (`mcp<2` cap, fastapi 0.136.1, pydantic 2.13.4, sveltekit/vite defensive, svelte XSS) remain forced by external clocks in the Cycle 6 horizon. Cannot be deferred to Cycle 6.5 without explicit security/operability cost. This forces SOME shipping in Cycle 6 — pure discovery-only is structurally non-viable.

2. **Round 2 DA + IV convergence on demand-validation as non-optional is load-bearing**. The "operator-paced optional" framing from Cycle 5 W5 (which left Z-IV unexecuted) cannot be repeated 6th cycle running without crossing the stall-signature threshold per DA P0 #4 base-rate prior.

3. **Sycophancy-pattern v2 named (NEW finding)** — post-hoc "compounding primitives" labeling of forced hygiene is structurally identical to Cycle 5 calibration-theater pattern (ADR-0023 §"Pattern check"). Different words, same epistemic move. Council protocol amendment candidate: Round 1 should be required to label any item as "forced hygiene" vs "discretionary primitive" BEFORE Round 2 fires.

4. **Recursive deferral pattern named (NEW finding from IV)** — "next cycle is the inflection" appeared in cycles 3+4+5+6. Structural to maintainer-as-PM loop. NOT a Cycle 6 problem; this ADR's W2 HARD GATE partially addresses by forcing checkpoint at known cycle moment.

5. **Anti-sycophancy COMPLEMENTARY trap named (NEW finding)** — honest acknowledgment of constraints used as object-level validation. Both Round 1 agents fell in. Future council protocol should explicitly note when chairman synthesis is "least-wrong-among-bad-options" vs "validated-best".

6. **Solo-maintainer burnout vector recalibrated (NEW finding)** — monotony + isolation + lack-of-feedback, NOT scope ambition. Round 1's "Z2 protects from burnout" framing inverts the actual vector for solo OSS per Eghbal 2020 + post-mortem evidence.

7. **TAM/SAM/SOM honest numbers established (NEW finding from IV)** — TAM $40-60M / SAM $8-15M / SOM Cycle 6 = $0 base case. Bankable for future cycle councils.

8. **5-cycle persona deferral is real cost but cannot be paid in Cycle 6 absent demand evidence**. The H-shape W2 GATE provides the demand-evidence acquisition mechanism (5 CD conversations) OR the alternative honest pathway (1 persona formally retired via ADR — converting "deferred" perpetual status to closed scope). Either outcome is council-acceptable; "operator-paced optional" is not.

9. **Bucket A forced + Bucket B forced consume ~1.5-2 waves of Cycle 6 regardless of council**. H-shape names this honestly rather than framing it as virtuous. The remaining 2.5-3.5 wave budget is what the council is actually choosing about — and Round 2 said: don't choose more shipping without first acquiring demand evidence.

## Considered Options

### Option α — Z2-DA as Round 1 converged (PV + Strategist primary)

**Rejected at Round 2.** Three structural defeats:

1. **"Compounding primitives" framing is sycophancy-pattern v2** (DA P0 #1). Indistinguishable mechanism from Cycle 5 Path C calibration-theater.
2. **Demand-validation gate cannot be "operator-paced optional" 6th cycle running** (DA P0 #4 + IV P0 #2). That's the recursive deferral pattern, structural to the loop.
3. **Base-rate prior makes "Z-shape healthy 2nd time" claim unsupportable** (DA P0 #4). Round 1 chose "healthy" without justification beyond burnout-avoidance — which DA showed inverts the actual burnout vector for solo OSS.

Reactivates Cycle 7+ ONLY with explicit demand-validation evidence from Cycle 6 W2 gate outcome (or formal persona retirement evidence).

### Option β — Pure discovery-only cycle (IV off-list)

**Rejected.** IV proposed 4 weeks customer-development only, zero shipping. Defeats:

1. **Bucket A is already shipped** (PR #129 — security CVEs + Claude model migration cannot wait for council per external clocks).
2. **Bucket B floor bumps are FORCED by external clocks** in the Cycle 6 horizon. Cannot be deferred to Cycle 6.5 without explicit security/operability/breaking-SDK cost.
3. **5-cycle deferral cost is real but cannot collapse mid-cycle to "zero shipping"** without operator's explicit acceptance of that cost trade.

IV's demand is preserved via H-shape's W2 HARD GATE (criterion #3, mandatory).

### Option γ — Z-IV-primary off-list (DA considered)

**Rejected at Round 2 by DA itself.** DA evaluated demoting Z-DA-tail and promoting Z-IV (90-day demand-discovery sprint per Cycle 5 ADR-0024) to primary. Rejected because:

1. Bucket A + B forced floors consume W0-W1 regardless.
2. `mcp<2` forced; Claude retirement forced.
3. Z-IV-primary requires maintainer to do outreach work explicitly operator-paced per Cycle 5 close — cannot be imposed at Chairman synthesis without operator's explicit consent.

H-shape preserves Z-IV's intent via W2 HARD GATE as criterion #3.

### Option δ — Z2-DA-MINUS as DA grudgingly approved

**Accepted as base for synthesis.** DA's modifications: drop #79 (E1 trap-compounder), drop all 4 framings ("compounding primitives" / "multi-tenant readiness" / "WCAG-AA procurement" / "AI cost moat"). All folded into H-shape with the addition of IV's specific W2 GATE (5 CDs OR persona-retirement-ADR).

### Option ε — Bucket G new deep (placeholder; neither Round 1 agent named)

**Rejected** because no new deep emerged from the 45-day ecosystem scan window. DA P2 #12 noted Bucket G emptiness as a process bug (Round 1 unanimously accepted the constrained candidate pool the planning memo handed them = effective delegation of scope-discovery to memo author). Future council protocol amendment candidate: Round 1 should be required to spend one explicit prompt on "what is NOT in the memo that should be."

## Decision

Adopt **H-shape — forced hygiene W0-W1 + HARD GATE W2 + conditional W3-W5**. This is the OFF-LIST synthesis that survives both Round 2 findings (forced Bucket B floor bumps must ship; demand-validation surface must be non-optional).

**Wave plan:**

```
W0 — entry ADR (this) + LESSONS_LEARNED Cycle 6 header
     + Z-IV operationalization (outreach plan + 5-CD target + persona-retirement-ADR template)
     + honest framing: "forced hygiene + hard discovery gate, NOT a validated cycle"

W1 — Bucket B forced floor bumps (single hygiene PR):
     - mcp<2 upper bound
     - fastapi>=0.136.1
     - pydantic>=2.13.4 (ADR-0014 byte-exact pin MANDATORY pre-merge re-verify)
     - sveltekit>=2.57.1, vite>=8.0.5
     - svelte>=5.55.7 (Dependabot XSS #133)

W2 — HARD GATE close:
     5 customer-development conversations logged OR 1 persona formally retired with ADR
     IF MET → continue W3-W5
     IF NOT MET → BLOCK + amend this ADR → Cycle 6.5 pivot to discovery-only

W3 (conditional) — Frontend DA cluster (#105/#106/#107/#108 + #110 + #46) on a11y intrinsic merit

W4 (conditional) — Backend P3 (#117 + #119 single-tenant framing + #120)
     + Anthropic prompt caching ADR with EXPLICIT "tactical cost reduction, NOT a moat" caveat
     + Fly autosuspend evaluation

W5 (conditional) — hygiene close, mypy slice (#121 first slice), CI floor-verify step (#131)
```

**Pre-registered success criteria (≥6/9 graceful threshold)**: see `memory/project_v40_cycle_6.md` §"Pre-registered success criteria". Criterion #3 (W2 HARD GATE) is MANDATORY — failure triggers Cycle 6.5 amendment to discovery-only.

**Honest disclosures (mandatory per ADR-0022 NFM-9 spirit)**:

1. **This cycle is "forced + honest, NOT validated"**. Chairman synthesis explicitly acknowledges the H-shape is least-wrong-among-bad-options, not best-validated.
2. **MeridianIQ at Cycle 6 entry has the empirical signature of stalled solo OSS** (4 markers from DA P0 #4 all present). W2 HARD GATE is the first non-optional demand-validation surface in 6 cycles.
3. **5 named personas remain deferred 5 cycles without external evidence**. No escalation framing this cycle. Falsifiers named per persona in `memory/project_v40_cycle_6.md`.
4. **All 4 "compounding primitive" framings are DROPPED** with explicit triggers: Cycle 6.5 patch triggers if any reintroduced in PR descriptions (sycophancy-recurrence trigger).
5. **TAM/SAM/SOM honest numbers ($40-60M / $8-15M / $0 Cycle 6) are now banked** for future council reckoning.

## Consequences

**Positive:**

- Demand-validation surface is non-optional this cycle for the first time in 6 cycles (W2 HARD GATE)
- 4 sycophancy framings explicitly DROPPED — anti-sycophancy discipline upgraded from Cycle 5
- Bucket B forced hygiene ships honestly framed (no "primitive" virtuous narrative)
- Cycle 6.5 amendment pathway pre-registered if gate fails
- Anti-sycophancy lessons 1-6 banked for LESSONS_LEARNED Cycle 6 close
- TAM/SAM/SOM honest numbers established for future council reckoning
- Reversibility maximum (gate forces honest checkpoint; no large bet)

**Negative:**

- Forced hygiene framing reveals ~1.5-2 waves of Cycle 6 budget is non-discretionary; conscious cycle budget for new decisions is small
- W2 HARD GATE operator-required work may conflict with maintainer's documented operator-pacing preference (mitigation: alternative path via 1 persona formally retired with ADR is operator-paced choice + creates closed scope, not perpetual deferral)
- 5 named personas may be formally retired Cycle 7+ if W2 gate triggers persona-retirement-ADR path — irreversible scope contraction
- If gate triggers Cycle 6.5 pivot, criteria 4-9 reset to deferred — release tag (#9) may slip to Cycle 7 close

**Risks:**

1. **Sycophancy-pattern v3 emerges in subsequent cycle** — if Cycle 7 council finds yet another mechanism to manufacture internal evidence of progress in absence of external validation, the pattern is methodological not Cycle-N-specific. ADR-0022 NFM-9 paired-adversarial protocol amendment may be required.

2. **W2 HARD GATE triggers Cycle 6.5 pivot AND discovery-only also produces 0 conversations** — modal outcome per IV's base-rate prior. Cycle 7 entry would face explicit "formally pivot OSS thesis OR retire project to maintenance mode" decision.

3. **Maintainer operator-pacing preference encounters W2 GATE as imposition** despite synthesis attempting to honor it via persona-retirement-ADR alternative path. Mitigation: ratification gate at ADR-0025 review allows operator to amend GATE specifics (CD count, alternative pathways) before W0 commits.

**Operator decisions required at this ADR's ratification (W0)**:

1. Confirm W2 HARD GATE criteria (5 CDs OR persona-retirement-ADR) OR amend (e.g., 3 CDs + Issue #13 refresh; different alternative pathway; different W2 deadline)
2. Confirm which 5 personas-in-scope are eligible for retirement path (all 6 from cycle_6.md persona table? Or subset?)
3. Confirm prompt caching ADR is scoped Cycle 6 W4 (or defer to Cycle 7 if W2 GATE outcome shifts priorities)
4. Sign-off on ADR-0024 + ADR-0025 lineage (both reserved-then-authored on entry; pattern continues)

ADR-0026+ NEWLY RESERVED for future cycle entries.
