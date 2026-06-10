# 0026. Stay public + open-core boundary rule

* Status: proposed
* Deciders: @VitorMRodovalho
* Date: 2026-06-10 (decision taken 2026-05-31; this ADR records it)
* Council: strategist + legal-and-accountability + investor-view PAIRED with devils-advocate (per the anti-sycophancy pairing rule); full deliberation in session workflow output `w3i2xelaz`, decision summary preserved in the maintainer's session handoff
* Cites: [LICENSE](../../LICENSE) lines 5-8 (parser upstream ancestry), [ADR-0022 §"Honest disclosures"](0022-cycle-4-entry-beta-honest.md) (demand-validation gap), `docs/ROADMAP.md` (demand-gate language)

## Context and Problem Statement

On 2026-05-31 the maintainer (acting as CTO/CIO) asked: should the MeridianIQ repository be made **private**, and should the public site's "exposed code" framing change? The concern: 48 standards-based analysis engines, the parser, and the scheduling intelligence are publicly readable under MIT while the project has **$0 validated demand** — is the code a giveaway of the future moat?

An ADR-level council ran with investor-view explicitly paired with devils-advocate (investor-view never runs solo per its documented sycophancy bias). This ADR records the verdict so the decision is citable and is not silently re-litigated each time the "exposed code" anxiety recurs.

## Decision Drivers

1. **The MIT grant is irrevocable for everything already published.** Taking the repo private recaptures nothing: any clone of the current tree carries a perpetual MIT license. Going private only stops FUTURE code from being publicly licensed.
2. **The repo is empirically inert as a distribution channel.** Verified at decision time: **0 forks, 0 stars, 0 watchers** after 2 months public. The 731 clones/14 days are CI/automation traffic, not humans. Nobody is currently taking the code — and nobody is currently arriving because of it either. Privatizing is therefore a strategic no-op that removes one of the few credibility props ("auditable, no black box") the demand conversations can use. The devils-advocate framing is the honest one: **0 forks means inert, not safe** — the absence of forks is evidence the OSS channel has produced no adoption, not evidence the code is protected.
3. **The moat thesis: differentiation lives in accumulated data + hosted operation + brand, not in the published engines.** Standards-based engine logic (DCMA-14, AACE RPs) is replicable by any competent team from the same public standards documents; publishing it forfeits little. What compounds is the **longitudinal portfolio layer** (cross-revision, cross-project intelligence over customer data), the hosted platform, and the trust position.
4. **Honest caveat (council-surfaced): the "moat ≠ code" thesis is only HALF-true today.** The differentiated engines (`benchmark_priors`, `revision_trends`, `duration_prediction`, `lifecycle_phase`) are ALREADY MIT-public, and the longitudinal layer is not yet a persisted asset. The boundary rule below exists precisely because the thesis must be enforced going forward, not assumed retroactively.
5. **Latent IP hazard in the parser ancestry.** `src/parser/` descends from `djouallah/Xer-Reader-PowerBI`, which has **no license** (all rights reserved by the upstream author) — documented in [LICENSE](../../LICENSE) lines 5-8 and `ATTRIBUTION.md`. Any future commercial assertion, dual-licensing, or relicensing over the parser lineage requires **licensed counsel first**. This is a standing constraint, not a blocker on staying public (the exposure exists regardless of repo visibility).

## Considered Options

### Option A — Take the repository private

**Rejected.** Recaptures nothing already published (driver 1); removes the auditability credibility prop; signals retreat without any offsetting protection. With 0 external adoption (driver 2) there is no leak to stop.

### Option B — Tighten the license now (BSL / AGPL / dual-license)

**Rejected as premature.** With $0 validated demand there is no commercial surface to protect and no basis for choosing protective terms. AGPL additionally violates the project's own no-GPL dependency rule and MIT positioning. Dual-licensing is blocked by driver 5 (parser ancestry needs counsel) before any such assertion. Revisit ONLY on real commercial signal, with counsel.

### Option C — Stay public + adopt an explicit open-core BOUNDARY rule (chosen)

Keep the repo public under MIT and adopt the boundary as a **forward-looking rule, not a migration**:

> **Anything that derives its value from accumulated DATA or from HOSTED operation is proprietary from commit 1 (lives in `meridianiq-private` or the hosted stack; never enters this repo). Stateless, single-file/single-schedule transforms stay MIT in this repo.**

Concretely: cross-customer benchmark corpora, persisted longitudinal portfolio state, hosted-ops tooling, demand/customer artifacts → private. Parsers, single-schedule engines, single-project analytics, UI → public, as today.

## Decision Outcome

**Option C.** The repository stays public under MIT. The open-core boundary rule above governs where every future component lands, evaluated at design time (entry-council question: "does this derive value from accumulated data or hosted operation?").

### Consequences

* **Positive:** keeps the "auditable, no black box" positioning intact for demand conversations; zero migration cost; the moat-bearing layer (longitudinal/data/hosted) is protected by default going forward; decision is citable, ending repeated re-litigation.
* **Negative / accepted risks:** the already-published differentiated engines remain MIT forever (driver 4) — accepted because they are standards-replicable anyway; the boundary requires discipline at every future design decision (it is a rule, not a fence); repo inertness (driver 2) means staying public produces no adoption by itself — the demand gate remains the real work.
* **Standing obligations:**
  1. Engage licensed counsel before ANY commercial/dual-license assertion touching the parser lineage (driver 5).
  2. Apply the boundary question at entry-council for every new component.
  3. Revisit license posture (Option B) only on real commercial signal — an inbound paying-customer conversation or design-partner commitment, not internal anxiety.

## Pattern check

This decision is consistent with [ADR-0022 §"Honest disclosures"](0022-cycle-4-entry-beta-honest.md): the binding constraint on MeridianIQ is demand validation, not code exposure. Privatizing the code would have treated a visibility lever as if it were a demand lever — the same category error the cycle councils have repeatedly flagged.
