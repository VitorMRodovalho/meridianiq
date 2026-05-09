# 0024. Cycle 5 entry — Z-shape consolidation (off-list per Round 2 paired adversarial council)

* Status: proposed
* Deciders: @VitorMRodovalho
* Date: 2026-05-09
* Cites template: [ADR-0019](0019-cycle-2-entry-consolidation-primitive.md) + [ADR-0021](0021-cycle-3-entry-floor-plus-field-shallow.md) + [ADR-0022](0022-cycle-4-entry-beta-honest.md) (cycle entry pattern; 4-agent council protocol)
* Cites lessons: [ADR-0023 §"Pattern check vs. ADR-0009"](0023-cycle-4-w4-outcome.md) (calibration-theater confrontation), Cycle 4 LESSONS_LEARNED (9 lessons + 1 pattern observation), [ADR-0022 §"Honest disclosures"](0022-cycle-4-entry-beta-honest.md) (demand-validation gap, internal-driven scope, single-key-maintainer risk)
* Cites primitive: [ADR-0020](0020-calibration-harness-primitive.md) (calibration harness — held without modification this cycle)

## Context and Problem Statement

Cycle 4 closed at v4.2.0 (2026-05-09) with W4 path-A activation per [ADR-0023](0023-cycle-4-w4-outcome.md). Two consecutive W4 calibration gates (Cycle 1 ADR-0009 W4 + Cycle 4 ADR-0023) have now activated path-A on the same corpus precondition. ADR-0023 §"Pattern check vs. ADR-0009" made the pattern citable + committed to an operational falsifier (Cycle 5+ sub-gate A pass OR external citation OR independent attestation). Cycle 4 produced ZERO demand-validation signal during its 11-day execution window (0 inbound enterprise inquiries, 0 design partners, 0 contributor PRs touching calibration code, 0 community-supplied corpus on Issue #13 across 4 cycles, 0 external citations of the pre-registration template).

The 2026-05-09 Cycle 5 entry council ran the 4-agent protocol (PV + strategist Round 1 parallel; DA + IV Round 2 paired adversarial per [ADR-0022 NFM-9](0022-cycle-4-entry-beta-honest.md) — IV alone is sycophancy-prone for path-A framing).

**Round 1** surfaced 4 candidate cycle deeps (Path A Field-surface deep, Path B Owner-rep portfolio dashboard, Path C calibration-discipline + corpus assembly, Path D E1 forensic methodology) with PV champion-ing persona-recovery urgency and strategist recommending Path C as "highest-conviction available moat play" while explicitly naming Path D as TRAP. Maintainer accepted dropping Path D + paths E (A1+A2 standalone; positioning drift) + F (Consultant narrative-builder; 5th-consolidation framing risk). Round 2 ran on surviving paths A/B/C.

**Round 2** (paired adversarial) reached convergence that **all 3 surviving paths fail in distinct ways**, with both DA and IV independently surfacing an OFF-LIST option. Specifically:

1. **Path A — DA P0 findings** include: 4 unfamiliar primitives stacked (IndexedDB + Service Worker + Svelte 5 runes + offline-first sync) → first-time-stack scope risk 2-3× vs historical 1.5× (8-12 nominal could blow to 18-24 actual); G702/G703 "half-shipped v3.7-v3.8" residual gap UNINSPECTED requiring pre-W0 audit spike; sub upload-and-link schema collision with Cycle 4 W2 `revision_history` + soft-tombstone (per [ADR-0022 W2 fix-up #BLOCKER-1](0022-cycle-4-entry-beta-honest.md) — the same auto-grouping collision); AIA G702/G703 license/copyright concern unaddressed; Brazilian medição ≠ G703 (drop one or 2× scope).

2. **Path B drops**. DA: *"Strategist DIDN'T evaluate it because it's structurally evaluable on moat and FAILS — read-only rollup over commodity engines IS B-completo-lite. The strategist's silence is more damning than rejection."* B-completo was rejected per [ADR-0022 §"Decision Drivers" #2](0022-cycle-4-entry-beta-honest.md) as "PPM commodity, replicable in 6-12 weeks by any incumbent"; subset-of-commodity is still commodity. Plus 5-tier role-hierarchy work (per memory `project_role_hierarchy.md`) needs new schema before any rollup view ships.

3. **Path C drops in current shape**. DA P0 finding (sharpest in the entire council): *"Path C IS exactly the trap [`docs/ROADMAP.md` line 47](../ROADMAP.md) names."* Three structural blockers:
   - **Falsifier #1 (Cycle 5+ sub-gate A pass at N≥30) is mathematically unreachable in Cycle 5**. Operator-curated corpus upper bound from sandbox + completed projects = N≤10 per IV's standing finding. Cycle 5 = C ships ADR + outreach + 0 corpus growth — empirically same as suspension, with 6-8 waves opportunity cost.
   - **AACE/PMI working group outreach has NO identified contact path** in the maintainer's reference materials (no AACE TCM membership in memory, no prior conversation history). Cold outreach to standards bodies has multi-month-to-year response cycles; Cycle 5 ships SOLICITATION not citation.
   - **LGPD/GDPR consent path requires actual legal counsel, not L&A agent**. Solo bootstrapped maintainer has not engaged a lawyer (no evidence in memory). "12-24 month timeline" presumes LGPD work just happens — it does not. Lawyer engagement is a budget line ($500-2000/hr range) not yet committed.

Both DA and IV independently surfaced **anti-sycophancy convergence**:
- **PV's "persona-recovery is structural urgency"** is unfalsifiable escalation. Field+Sub deferral has been flagged in Cycles 1+2+3+4 with each cycle's framing escalating from "negative" (ADR-0019) → "Owner-rep first" (ADR-0021) → "demand-validation gap" (ADR-0022) → "structural foreclosure" (Cycle 5 PV) without any new external evidence. Internal urgency ≠ external demand.
- **Strategist's "Path C highest-conviction" framing is itself a sycophancy attack vector**. DA framed sharpest: *"Strategist is an inside-the-ideology agent. The ideology is the thing being audited. Strategist's recommendation is therefore epistemically circular for THIS decision specifically."*

Both Round 2 agents recommended OFF-LIST (with different shapes — see §"Considered Options" below). The 4-cycle pattern is now load-bearing critique that NO Cycle 5 entry framed as A/B/C can rebut. Path A converts to commodity feature work but evades the pattern; Path B compounds the commodity critique; Path C engages the pattern but cannot resolve it within Cycle 5 absent runway + contacts + lawyer commitments not yet on the table.

This ADR records the council protocol output, the Z-shape OFF-LIST recommendation accepted by the maintainer, and pre-registers Cycle 5 entry under those terms.

## Decision Drivers

1. **Two-consecutive-path-A pattern is now citable** per [ADR-0023 §"Pattern check"](0023-cycle-4-w4-outcome.md). 5th-cycle entry without resolution risks the pattern becoming self-confirming. Cycle 5 must NOT be a 3rd corpus-dependent deep without corpus-side movement. Forces either (a) suspend the framework explicitly OR (b) execute the operational falsifier directly. Z-shape does (a) by design with optional (b) folded as W5.

2. **4 cycles + 0 demand-validation signal = structural fact**. PV's "demand signal arrives via design-partner conversations not GitHub stars" is true BUT unfalsifiable — at 4 cycles + 0 signal, the diagnosis cannot be "we're being patient with silent personas". The diagnosis is: the gap is not featural, and shipping more features in absence of inbound conversation does not close it.

3. **Solo-maintainer 5th consecutive cycle = empirical reality**. Cycles 1-4 averaged 6-8 waves at 1.5× ratio. Cycle 4 just shipped 7.0/9 at exact graceful-threshold floor (no margin per DA exit-council finding). 5th cycle compounds single-key-maintainer risk per [ADR-0021 §"Hidden moat-erosion mechanism"](0021-cycle-3-entry-floor-plus-field-shallow.md) (IV finding). Cycle 5 must size to that empirical reality, not aspiration.

4. **PV's "persona-recovery structural urgency" framing is unfalsifiable escalation** (NEW finding from Round 2 DA + IV). Cycle 5 entry MUST acknowledge this honestly rather than continue the escalation pattern. The Field/Sub/Owner deferral is real but demand-validation gate is the same gate ADR-0022 §"Honest disclosures #1" pre-registered; it cannot be selectively waived for personas who don't write GitHub issues.

5. **Strategist's "Path C highest-conviction" framing is inside-ideology epistemic circularity** (NEW finding from Round 2 DA + IV). The pre-registration ideology that gives Path C its conviction is the thing being audited by the calibration-theater pattern critique. Strategist recommendations rated through the ideology cannot validate the ideology.

6. **Maintainer financial runway is binary blocker for any active-discovery component**. Per Round 1 strategist + Round 2 IV. Without runway disclosure (even bracketed: < 6mo / 6-12mo / 12-24mo / > 24mo), Z-IV components are undecidable. **Mitigation**: runway disclosure is W0 deliverable (criterion #2); cycle ratifies with bracket not exact figure.

7. **AACE TCM / PMI-CP contact-path inventory is W0 deliverable** for Z-IV optional W5 execution. If 0 prior contacts AND no current membership, Z-IV outreach component drops; cycle is pure Z-DA. If ≥1 contact OR maintainer willing to apply for membership, Z-IV W5 becomes executable.

8. **Calibration-theater pattern is engaged ONLY through Z-IV's outreach + Issue #13 refresh + community on-ramp components**. Pure Z-DA SUSPENDS the pattern (NOT extended); Z-DA + Z-IV optional ATTEMPTS to engage falsifier #2 (external citation) + #3 (independent attestation) + indirect movement on #1 (corpus growth via community refresh). Cycle 5 close honestly reports which falsifiers moved and which did not.

## Considered Options

### Option α — A1+A2 deep (auto-grouping + baseline inference)

**Rejected** for the third consecutive cycle (ADR-0019 §"Reversibility" listed; ADR-0021 §"Why NOT the PV deep" detailed; ADR-0022 §"Why NOT Option α B-completo" reframed). Three preconditions per [ADR-0021](0021-cycle-3-entry-floor-plus-field-shallow.md) §"Decision Drivers" #1 still UNMET: (a) merge-cascade migration scoped + ADR; (b) labeled corpus for grouping; (c) labeled corpus for baseline. Cycle 4 W2 PR-A heuristic v1 partially advanced this scope; full A1+A2 deep continues deferred to Cycle 6+ on corpus + migration evidence.

### Option β — E1 multi-discipline forensic methodology

**Rejected as TRAP** by Round 1 strategist (verbatim "Option β is the trap option"). Highest perceived moat + highest actual third-path-A risk on litigation-risky surface; reputational damage compounds. ADR-0019 §"Option 3" remained-reserved framing held. Reactivates Cycle 6+ ONLY if (a) labeled forensic gold-standard corpus is procurable AND (b) demand-validation signal materializes (paid prospect / design-partner conversation).

### Option γ — Optimism-pattern forecast reactivation

**Rejected as mathematically unreachable in Cycle 5**. ADR-0023 §"Cycle 5+ preconditions" requires `n_with_consent_path ≥ 30`; current state = 0; operator-curated upper bound from sandbox = N≤10. 12-24 month realistic timeline per ADR-0023 + IV exit-council finding #3. Pure Cycle 5 = γ ships ADR amendment + 0 corpus growth = third path-A.

### Option δ — Field-surface deep (PV's γ / Strategist's α / "Path A")

**Rejected** despite being least-worst of A/B/C per Round 2 IV. DA P0 findings: 4 unfamiliar primitives stacked (offline + IndexedDB + Service Worker + Svelte 5 runes) push first-time-stack scope ratio to 2-3× vs historical 1.5× (8-12 nominal → 18-24 actual); G702/G703 residual gap from v3.7-v3.8 UNINSPECTED; sub upload-and-link schema collides with Cycle 4 W2 `revision_history` semantics; AIA license/copyright unaddressed; Brazilian medição ≠ AIA G702/G703 (2× scope or drop one). Reactivates Cycle 6+ as **deep candidate** (NOT spike — promotion blocked by lack of "spike-to-deep graduation governance" per Round 2 DA hidden trap #3) IF (a) demand-validation evidence (≥1 design-partner conversation logged) AND (b) pre-W0 audit-spike completes G702/G703 inventory.

### Option ε — Owner-rep program-portfolio dashboard ("Path B")

**Rejected as B-completo-lite**. Strategist Round 1 silence on B = implicit moat-rejection. PV-only champion. ADR-0022 §"Decision Drivers" #2's "table stakes, not moat" applies to subset same as full hierarchy. 5-tier role hierarchy work needed before any rollup view ships. Reactivates Cycle 6+ IF (a) ≥3 prospects ask explicitly per ADR-0022 demand-validation gate AND (b) the PMO Director persona pull demonstrably opens (a)-class moat surface (e.g., AACE-anchored MIP comparison cross-contractor) that pure rollup does not.

### Option ζ — Plugin sandbox / E3 marketplace

**Rejected** per [ADR-0019 §"Option 2"](0019-cycle-2-entry-consolidation-primitive.md) — preconditions still unmet: subprocess/WASM sandbox ADR + ≥5 external plugins + license-attestation flow. Empty marketplace is reputational liability per IV finding #5. Authoring the framework now without external adoption = "thought leadership theater" sister-failure to calibration theater.

### Option η — Schedule Viewer Wave 7

**NOT a cycle commitment** — slot-opportunistic shallow inside any cycle (consistent with [ADR-0021 §"Why NOT Schedule Viewer Wave 7 as cycle commitment"](0021-cycle-3-entry-floor-plus-field-shallow.md)). Cycle 5 may absorb cost-loading + EVM overlay if scope budget permits; not pre-committed.

### Option Z-IV — Active demand-discovery sprint (Round 2 IV's off-list)

**Rejected as PRIMARY** because cold-outreach base rate to AACE/PMI working groups for solo OSS authors ≈ 0% per Round 2 IV pattern-match. Maintainer-temperament fit poor (outreach-heavy is uncomfortable for builder-temperament).

**Folded as OPTIONAL W5 component** of Z-DA primary — gated on W0 contact-path inventory + runway disclosure. If runway > 12mo AND ≥1 prior contact (or maintainer willing to apply for AACE TCM membership), Z-IV W5 executes. Else, drops to pure Z-DA.

### Option Z-DA — Pure consolidation cycle (Round 2 DA's off-list, **chairman recommendation accepted**)

**Selected.** Same shape as Cycle 2 (Option 4 consolidation per [ADR-0019](0019-cycle-2-entry-consolidation-primitive.md)) which had the BEST historical scope-ratio across all 4 cycles. Maintainer-temperament fit (code-light maintenance, low-burnout). Reversibility: HIGH. Calibration-theater pattern: SUSPENDED (NOT extended) — same critique against Path A applies BUT Z-DA's explicit acknowledgment + W5 optional Z-IV folds in the engagement vector.

## Decision

**Cycle 5 enters as Z-shape: Option Z-DA primary + Option Z-IV optional W5 parallel.**

Plan: **5 mandatory wave-clusters (W0-W4) totaling ~5-7.5 nominal sub-waves** + **W5 optional Z-IV parallel** (NOT cycle-blocking; gated on W0 disclosure). Per-wave breakdown:

| Wave | Budget | Notes |
|------|--------|-------|
| W0 | 1-1.5 | Entry artifacts + runway disclosure + contact-path inventory |
| W1 | 1-1.5 | Tech-debt close-out batch 1 (Cycle 4 W3 P3 follow-ups) |
| W2 | 1-1.5 | Tech-debt close-out batch 2 (Cycle 4 W3-B/C follow-ups + UX polish) |
| W3 | 1-1.5 | Tech-debt close-out batch 3 (Cycle 4 W2/W4 follow-ups + Vitest harness) |
| W4 | 1 | Hygiene: dep refresh + types-networkx + dcma14 datetime + catalog regen |
| **Total** | **5-7 nominal** | Solo-dev historical 1.5× = 7.5-10.5 actual realistic |
| W5 | parallel optional | Z-IV active outreach IF runway > 12mo AND ≥1 contact path |

**Cycle 5.5 patch trigger conditions** (per [ADR-0022 NFM-2](0022-cycle-4-entry-beta-honest.md) adapted for Z-shape): triggers if ALL of (a) ≥2 W1-W4 sub-criteria fail to close, (b) >3 weeks elapsed without close OR runway disclosure forces scope reduction mid-cycle, (c) DA-as-second-reviewer protocol skipped on a substantive PR. Without all three, Cycle 5 lands as ≥6/9 OR triggers honest cycle-extension ADR amendment without "patch" framing — same NFM-2 discipline as Cycle 4. **Note**: NFM-2's "feature regression" trigger from ADR-0022 does NOT apply to Z-shape (no new feature shipped); substituted with "runway disclosure forces scope reduction" per Round 2 DA cross-cutting blocker #2.

### Wave plan

**W0 — Cycle 5 entry + scope memo + ADR ratification + maintainer disclosures**

- This ADR (ADR-0024) committed at W0
- `docs/ROADMAP.md` refreshed marking Cycle 4 closed + Cycle 5 entry
- `docs/LESSONS_LEARNED.md` Cycle 5 entry header (lessons appended at Cycle 5 close per ADR-0018 cadence)
- **Maintainer financial runway disclosure** (bracket OK — <6mo / 6-12mo / 12-24mo / >24mo) committed to §"Honest disclosures" of THIS ADR before W1 opens
- **AACE TCM / PMI-CP contact-path inventory** documented (even if "0 contacts, no membership") — explicit, not silent
- L&A review on any new dep planned for W4 hygiene

W0 budget: **1-1.5 waves**.

**W1 — Tech-debt close-out batch 1: Cycle 4 W3 backend P3 follow-ups**

Targets (revisit on W0 close based on issue-state freshness):
- [#92](https://github.com/VitorMRodovalho/meridianiq/issues/92) endpoint integration test for `/revision-trends` (DA P3-6 from PR #88)
- [#91](https://github.com/VitorMRodovalho/meridianiq/issues/91) distinguish 404 not-found from RLS-denied in revision-trends (DA P3-3 from PR #88)
- [#90](https://github.com/VitorMRodovalho/meridianiq/issues/90) error handling on `analyze_revision_trends` in endpoint (DA P3-2 from PR #88)
- [#89](https://github.com/VitorMRodovalho/meridianiq/issues/89) distinguish CUSUM improvement vs slip in revision-trends (DA P3-1 from PR #88)

W1 budget: **1-1.5 waves**.

**W2 — Tech-debt close-out batch 2: Cycle 4 W3-B/C frontend P2/P3 follow-ups**

Targets:
- [#96](https://github.com/VitorMRodovalho/meridianiq/issues/96) locale-aware number formatting + backend description i18n (PR #95 P2)
- [#97](https://github.com/VitorMRodovalho/meridianiq/issues/97) SVG chart a11y — mobile `<title>` + screen-reader + N>8 legend collapse (PR #95 P2)
- [#98](https://github.com/VitorMRodovalho/meridianiq/issues/98) revision-trends edge cases + polish (PR #95 P3 — CLS, xMax=0, contrast, defensive z-order)
- [#100](https://github.com/VitorMRodovalho/meridianiq/issues/100) W3-C ADR amendment, cross-Python byte-stability, naming polish (PR #99 P3)

W2 budget: **1-1.5 waves**.

**W3 — Tech-debt close-out batch 3: Cycle 4 W2/W4 + frontend test infra**

Targets:
- [#82](https://github.com/VitorMRodovalho/meridianiq/issues/82) race condition test for detect-confirm with program_id mutation (PR #78 P3)
- [#84](https://github.com/VitorMRodovalho/meridianiq/issues/84), [#85](https://github.com/VitorMRodovalho/meridianiq/issues/85), [#86](https://github.com/VitorMRodovalho/meridianiq/issues/86) UX polish carry-overs (PR #83)
- [#87](https://github.com/VitorMRodovalho/meridianiq/issues/87) Vitest component test harness for Svelte 5 components (DA assumption from PR #83)
- Cycle 4 W4 P3 deferrals (DA-flagged in PR #101 not opened as issues — inline-deferred)

W3 budget: **1-1.5 waves**.

**W4 — Hygiene: dep refresh + mypy strict cleanup + catalog regen**

- Dependabot review pass: backend + frontend dep PRs accumulated since v4.2.0
- `types-networkx` install + `src/analytics/dcma14.py:100-102` datetime mismatch fix → `mypy --strict` 4 errors → 0
- Catalog regen if any new endpoint / engine added during W1-W3 (unlikely for tech-debt cycle but verify)
- `scripts/check_stats_consistency.py` self-pass

W4 budget: **1 wave**.

**W5 — Active outreach (OPTIONAL parallel, gated on W0 disclosure)**

Components (each independently executable):
- **Maintainer-led prospect outreach**: ≥1 paid-product conversation logged across PMO Director / Owner-Rep / GC / Consultant personas. Falsifier: <1 design partner emerges → MeridianIQ is personal-use tool, all future cycles scope accordingly.
- **AACE TCM / PMI-CP member application + 1-2 working group introductions**: achievable in 90 days even cold IF maintainer applies for membership in W0. Falsifier: 0 working group conversations within 90 days → calibration-discipline-as-citable-asset claim is dead, retire from positioning copy.
- **Issue #13 community-call refresh**: explicit "we are pausing feature work to assemble corpus" framing on the existing issue. Falsifier: 0 community contributions within 90 days → corpus path is empirically dead, retire forecast feature permanently.

W5 budget: operator-paced parallel; not cycle-blocking. Each component independently executable. Cycle 5 close honestly reports which executed and which deferred.

### Pre-registered success criteria

| # | Criterion | Status |
|---|---|---|
| 1 | ADR-0024 ratified + Cycle 5 ROADMAP refresh + LESSONS_LEARNED Cycle 5 entry header | OPEN — this ADR (ratifies on PR merge) |
| 2 | Maintainer financial runway disclosure published in §"Honest disclosures" (bracket: <6mo / 6-12mo / 12-24mo / >24mo) | OPEN — W0 deliverable |
| 3 | AACE TCM / PMI-CP contact-path inventory documented (even if "0 contacts, no membership") | OPEN — W0 deliverable |
| 4 | Cycle 3 + Cycle 4 carry-over: ≥3 of 6 operator items closed (#26 OR #28 OR #54 OR ADR-0022-ratification OR consolidated re-mat OR W4 manifest archive) | OPEN — operator-paced |
| 5 | Tech-debt P3 batch: ≥6 of ~14 issues closed (#82, #84-#92, #96-#100, #87) | OPEN — W1+W2+W3 |
| 6 | Hygiene: dep refresh batch + types-networkx + dcma14 datetime fix → mypy strict 0 errors | OPEN — W4 |
| 7 | Z-IV optional execution: ≥1 of {paid-product conversation, AACE/PMI working group inquiry, Issue #13 refresh published} OR explicit "deferred per W0 inventory" | OPEN — W5 optional OR explicit deferral |
| 8 | LESSONS_LEARNED Cycle 5 entry appended at close + DA exit-council on entry ADR PR | OPEN — entry ADR (this) PR + close-time append |
| 9 | Release tag v4.3.0 (consolidation + hygiene minor) OR v4.2.1 (patch class if scope reduces) | OPEN — at close |

Cycle 5 ships gracefully if **≥6/9 close** (relaxed from ADR-0022 ≥7/9 floor reflecting Z-shape's lower aggregate ambition + the tech-debt-only nature of W1-W4). **<6/9 triggers honest cycle-extension ADR amendment** (NOT "Cycle 5.5 patch" framing — see Cycle 5.5 trigger conditions in §"Decision" above).

**Partial-credit accounting** (per ADR-0022 self-grading-acknowledged pattern + Round 2 DA hidden trap #1):
- Each criterion is full (1.0) or zero (0.0) — no partial credit on Z-shape because no path-A sub-gate runs.
- **Self-grading risk acknowledgment**: this credit framework was designed by the maintainer (this ADR's authorship). External reviewer may reject the structure as self-graded. The substantive Cycle 5 outcome (tech debt closed + runway disclosed + W5 components executed or explicitly deferred) is independent of the credit total per the lesson learned in [Cycle 4 LESSONS_LEARNED §"Substantive English outcomes lead; partial-credit math is footnote"](../LESSONS_LEARNED.md).
- **External-verified credit** (Round 2 DA hidden trap #1 fix forward-looking): future Cycle 6+ entry ADR should pre-register that ≥1 success criterion be EXTERNAL-VERIFIED (PR from non-maintainer, citation from external body, design-partner attestation) before the framework is non-self-sealing. **Cycle 5 does NOT yet implement this** — Cycle 5 ships with the same self-grading framework as Cycles 2-4, but flags it for Cycle 6+ entry.

### Reversibility

- **HIGH**. Z-DA primary is tech-debt close-out + dep refresh + mypy hygiene — fully reversible per-issue. No schema commitments. No new deep. No probabilistic-engine-adjacent surface.
- Z-IV W5 optional is fail-safe (worst case: silence; best case: 1-3 inbound conversations).
- Calibration framework (W4 evaluator + sub-gate thresholds + heteroscedasticity formula) held without modification this cycle. ADR-0023 stays load-bearing.

## Negative consequences / accepted costs

1. **5th-consolidation-flavored cycle framing risk** per Round 2 IV. External reviewer may read 5 consecutive cycles without a deep deep as "inability to ship product, not patience". This is structural risk, not bug — accepted in entry framing rather than papered over.

2. **Cycle 5 ships no user-visible new feature**. Release tag v4.3.0 may be defensible only as patch v4.2.1. Decision deferred to Cycle 5 close based on actual tech-debt-closed vs new-feature ratio.

3. **Demand-validation gap stays open structurally**. Cycle 5 = Z does not close it; only Z-IV W5 components attempt to surface signal, with explicit falsifier framing per ADR-0023 §"Pattern check" #1/#2/#3.

4. **Field/Sub/Owner persona deferral at 5+ cycles → positioning damage**. Acknowledged. Cycle 6+ entry ADR will face the same deferral-vs-demand-validation tension under sharper terms; Cycle 5 explicitly does not relieve it.

5. **Calibration-theater pattern not RESOLVED**. Pure Z-DA SUSPENDS (not extended); Z-DA + Z-IV optional ATTEMPTS to engage falsifier #2/#3 and indirectly #1. Cycle 5 close honestly reports which falsifiers moved (likely zero unless Z-IV components execute and produce inbound signal).

6. **No ADR-0023 amendment in Cycle 5**. Heteroscedasticity formula stays locked; sub-gate thresholds (A=30, B=0.20, C=0.75) stay locked. Cycle 6+ if corpus growth materializes.

7. **Z-IV outreach base rate ≈ 0% honest acknowledgment**. Even if all three Z-IV components execute, the base rate of solo OSS author + cold AACE/PMI outreach producing citation within 90 days is statistically low per Round 2 IV pattern-match. Cycle 5 ships the OUTREACH not the OUTCOME; Cycle 6+ may re-evaluate.

## Honest disclosures (per ADR-0018 Amendment 1 + ADR-0022 §"Honest disclosures" pattern)

1. **Off-list option chosen explicitly** despite ADR-0021 §"Negative consequences" line warning that "third consecutive cycle without deep risks 'honesty inflation' (technically impeccable, competitively flat)". Cycle 5 = Z is the **fourth** consolidation-flavored cycle. Acknowledged. Round 2 IV explicit: "5th-consecutive-cycle-without-deep would be velocity problem signal to acquirer-class observers" — accepted as risk, not deflected.

2. **Maintainer financial runway**: TBD pending W0 disclosure. **Pre-W0 commitment**: maintainer will publish bracket (< 6mo / 6-12mo / 12-24mo / > 24mo) in this ADR's §"Honest disclosures" before W1 opens. If < 6mo, all Z-IV W5 components drop and cycle is pure Z-DA.

3. **AACE TCM / PMI-CP membership status**: TBD pending W0 inventory. **Pre-W0 commitment**: maintainer will document either (a) prior contacts + membership status, OR (b) explicit "0 contacts, no membership, willing/unwilling to apply" before W1 opens. Z-IV W5 outreach component gates on this.

4. **PV's "persona-recovery is structural urgency" framing escalation acknowledged honestly**. Cycle 5 entry does NOT defer Field/Sub/Owner under the framing of "structural foreclosure"; it defers under the framing of "demand-validation gap is unmet for ALL personas including these". The escalation pattern is now explicit + entry-time-acknowledged.

5. **Strategist Round 1 "Path C highest-conviction" framing acknowledged as inside-ideology epistemic circularity** per Round 2 DA. Cycle 5 explicitly chooses the off-list option BECAUSE the strategist's adversarially-framed recommendation rated Path C high inside the ideology being audited. Future Cycle 6+ council protocols should consider invoking an out-of-ideology adversarial reviewer (e.g., legal-and-accountability or product-validator with explicit inside-ideology-skeptic framing) to counter strategist's calibration-discipline ratings.

6. **Self-grading credit framework continues**. Cycle 5 ships under the same maintainer-authored partial-credit accounting as Cycles 2-4. Round 2 DA hidden trap #1 surfaced this; Cycle 5 acknowledges + Cycle 6+ entry should pre-register external-verified credit category. Cycle 5 does NOT implement that fix.

7. **Cycle 4 LESSONS_LEARNED #5 ("Demand-validation observed-during-cycle silence is itself a signal") applied to Cycle 5 entry**: zero new demand signal produced between Cycle 4 close (2026-05-09 morning) and this ADR (2026-05-09 evening). Cycle 5 ships under acknowledged-zero-signal state; Z-IV W5 components attempt to update the datum, NOT presume it.

8. **Single-key-maintainer risk per ADR-0021 §"Hidden moat-erosion mechanism"** is unaddressed by Cycle 5. Acknowledged — no Cycle 5 candidate would have addressed it; the structural risk is multi-cycle / multi-year scope.

## Scope of what this ADR does NOT do

- Does NOT commit to Cycle 6 deep selection. Cycle 6 entry ADR (eventual) makes the decision based on Cycle 5 close evidence + Z-IV W5 outcomes.
- Does NOT pre-commit to v4.3.0 vs v4.2.1 release framing. Decision deferred to Cycle 5 close.
- Does NOT amend ADR-0022 success-criteria framework or ADR-0023 heteroscedasticity / sub-gate thresholds.
- Does NOT modify [ADR-0019 §"Reversibility"](0019-cycle-2-entry-consolidation-primitive.md) — A1+A2 + E1 stay reserved for Cycle 6+ on their original gating language.
- Does NOT re-evaluate ADR-0023 §"Pattern check" falsifier conditions — those stay load-bearing for Cycle 5 close + Cycle 6+ entry.
- Does NOT presume any new dep, feature, or persona surface ships in Cycle 5. Z-shape is consolidation-only.
- Does NOT claim acquisition-path movement. ADR-0022 §"Honest disclosures" #2 stays in force.

## Cross-references

- [ADR-0019](0019-cycle-2-entry-consolidation-primitive.md) — Cycle 2 entry pattern (Option 4 consolidation; closest historical analog to Z-shape)
- [ADR-0021](0021-cycle-3-entry-floor-plus-field-shallow.md) — Cycle 3 entry (Floor + Field-surface shallow); §"Hidden moat-erosion mechanism" + §"Workflow-data-gravity moat structural concern" still load-bearing
- [ADR-0022](0022-cycle-4-entry-beta-honest.md) — Cycle 4 entry; NFM-2 / NFM-3 / NFM-9 framework adapted to Z-shape; §"Honest disclosures" pattern continued
- [ADR-0023](0023-cycle-4-w4-outcome.md) — Cycle 4 W4 outcome + §"Pattern check vs ADR-0009" calibration-theater confrontation (load-bearing for Cycle 5 entry framing)
- [ADR-0018 Amendment 1](0018-cycle-cadence-doc-artifacts.md) — DA-as-second-reviewer protocol; this ADR's PR receives DA exit-council
- [ADR-0020](0020-calibration-harness-primitive.md) — calibration harness; held without modification this cycle
- `docs/ROADMAP.md` §"Next — Cycle 5+" — refreshed at this ADR's PR merge
- `docs/LESSONS_LEARNED.md` §"Cycle 4" — 9 lessons + 1 pattern observation; Cycle 5 entry inherits the framework
- `~/.claude/projects/-home-vitormrodovalho-projects-meridianiq/memory/project_v40_cycle_5.md` — Cycle 5 scope memo (authored alongside this ADR)

## Open process gap

- **DA exit-council on this entry ADR's PR** per ADR-0018 Amendment 1. Required for ratification. This ADR is meta-PR class (cycle entry); recursive validation pattern from Cycle 3 close-arc applies.
- **Maintainer runway disclosure** as W0 deliverable (criterion #2). Pre-commitment in §"Honest disclosures" #2 above.
- **AACE TCM / PMI-CP contact-path inventory** as W0 deliverable (criterion #3). Pre-commitment in §"Honest disclosures" #3 above.
- **L&A review** on any new dep added during Cycle 5 W4 hygiene per ADR-0022 §"Open process gap" pattern.
- **Cycle 5.5 patch trigger conditions** adapted from ADR-0022 NFM-2: substituted "feature regression" trigger (does not apply to Z-shape) with "runway disclosure forces scope reduction OR DA-as-second-reviewer protocol skipped on substantive PR" per Round 2 DA cross-cutting blocker #2.
- **Round 2 DA hidden trap #1 — external-verified credit category** flagged for Cycle 6+ entry ADR; Cycle 5 explicitly does NOT implement.
- **Round 2 DA + IV anti-sycophancy convergence** documented in §"Decision Drivers" #4 + #5; Cycle 6+ council protocol should consider out-of-ideology adversarial reviewer alongside strategist.

## Council protocol record (for future-cycle synthesis chairman)

Round 1 (PV + strategist parallel, 2026-05-09):
- PV surfaced 4 options (β Owner-rep, γ Field-surface, δ Corpus assembly, ε Consultant + SV-W7) + 2 NEW candidates (Owner-rep portfolio, Consultant narrative-builder)
- Strategist surfaced 4 options (α Field-surface, β E1 trap, γ Corpus assembly, δ A1+A2) with primary recommendation γ (corpus assembly) + explicit TRAP framing on β (E1)

Round 2 (paired DA + IV adversarial, 2026-05-09):
- **DA**: P0 findings against ALL 3 surviving paths; off-list recommendation (pure consolidation cycle, Z-DA shape); anti-sycophancy commit documented against PV's persona-urgency + strategist's Path C circularity
- **IV**: anti-sycophancy commit BREAKS from Round 1 strategist counterpart on 2 specific points (Path C "highest-conviction" as sycophancy attack vector + PV "persona-recovery" as unfalsifiable escalation); off-list recommendation (90-day demand-discovery sprint, Z-IV shape); ranked C ≥ B > A if forced to A/B/C, with all 3 dominated by off-list

Chairman synthesis: Z-DA primary + Z-IV optional W5 parallel = fold both Round 2 outputs into one cycle with IV components gated on W0 disclosure + DA components as primary.

Cycle 5 entry is the FIRST cycle where both Round 2 agents broke from their Round 1 counterparts on substantive grounds. This is the council protocol working as designed (paired adversarial counters Round 1 ideology). Future-cycle chairman synthesis should expect this pattern when corpus / demand-validation / pattern-check constraints accumulate.
