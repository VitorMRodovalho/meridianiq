# MeridianIQ — Roadmap

Forward-looking 1-page plan. Refreshed at every cycle close per
[ADR-0018](adr/0018-cycle-cadence-doc-artifacts.md). Historical
release-by-release detail lives in [`CHANGELOG.md`](../CHANGELOG.md);
architectural decisions in [`docs/adr/`](adr/); structural audits in
[`docs/audit/`](audit/).

> Last refreshed: **2026-05-17 evening (Cycle 6 entry — H-shape: forced hygiene + hard W2 gate per [ADR-0025](adr/0025-cycle-6-entry-h-shape.md). Off-list option chosen per Round 2 paired DA+IV adversarial demolition of Round 1 Z2-DA convergence — both Round 2 agents refused to validate the "compounding primitives" framing as sycophancy-pattern v2; demanded non-optional demand-validation surface. H-shape ships forced Bucket B floor bumps W0-W1 (mcp<2, fastapi 0.136.1, pydantic 2.13.4, sveltekit/vite/svelte defensive), HARD GATE at W2 (5 CD conversations OR 1 persona formally retired with ADR per Pathway A/B HONEST), conditional W3-W5. 5 nominal waves; W3+ gated on W2 outcome.)**

---

## Current state — Cycle 5 closed at `v4.3.0`

**Theme:** Z-shape consolidation ([ADR-0024](adr/0024-cycle-5-entry-z-shape-consolidation.md) — tech-debt close-out + dep refresh + mypy hygiene + Z-IV outreach optional).
**Released as:** [`v4.3.0`](https://github.com/VitorMRodovalho/meridianiq/releases/tag/v4.3.0) (commit `89e0f53`, 2026-05-09).

**Cycle 5 success criteria: 7/9 graceful with margin** at release tag per [ADR-0024 §"Pre-registered success criteria"](adr/0024-cycle-5-entry-z-shape-consolidation.md). Z-IV W5 outreach (active AACE/PMI working-group inquiry) DEFERRED at Cycle 5 close as operator-paced; pre-ratification disclosures stand (runway > 24mo, AACE/PMI member with prior contacts).

| Wave | Delivers |
|------|----------|
| W0 | [ADR-0024](adr/0024-cycle-5-entry-z-shape-consolidation.md) Cycle 5 entry (Z-shape) + ROADMAP refresh + LESSONS_LEARNED Cycle 5 header + maintainer disclosures (runway + contacts inventory). |
| W1-W3 | Tech-debt close-out (Cycle 4 W2/W3/W4 P3 follow-ups: #84, #82, #85, #86, #87, #89, #90, #91, #92, #96, #97, #98, #100). 6 PRs (#113/#114/#115/#116/#118). |
| W4 | Hygiene wave (dep refresh + types-networkx + dcma14 datetime + catalog regen) per [PR #122](https://github.com/VitorMRodovalho/meridianiq/pull/122). |
| W5 | Z-IV DEFERRED (operator-paced; explicit defer). |

**Cycle 6 pre-W0 unconditional wave** shipped post-Cycle-5 close: 45-day ecosystem scan (2026-05-17, 5 parallel agents) surfaced 3 P0 items with external clocks (Claude Sonnet 4 retired 2026-06-15, weasyprint CVE-2025-68616 SSRF, PyJWT CVE-2026-32597). Shipped via [PR #129](https://github.com/VitorMRodovalho/meridianiq/pull/129) before Cycle 6 entry council — Bucket A. 4 follow-up issues filed (#130/#131/#132/#133).

---

## Next — Cycle 6 (in flight, kickoff 2026-05-17 evening)

**Theme:** H-shape — forced hygiene + hard W2 gate ([ADR-0025](adr/0025-cycle-6-entry-h-shape.md), off-list per Round 2 paired DA+IV adversarial demolition of Round 1 Z2-DA convergence).
**Tag target:** `v4.4.0` (consolidation + hygiene minor IF GATE met) OR `v4.3.1` (patch class IF Cycle 6.5 pivot triggered).

The 2026-05-17 evening Cycle 6 entry council ran the 4-agent protocol per cycles 2-5 cadence (PV + strategist Round 1 parallel; DA + IV Round 2 paired adversarial per [ADR-0022 NFM-9](adr/0022-cycle-4-entry-beta-honest.md)). Round 1 converged strongly on Z2-DA (second consecutive Z-shape framed as "compounding primitives"). Round 2 REFUSED to validate. Both DA and IV independently surfaced six anti-sycophancy findings:

1. **Sycophancy-pattern v2 named** — "compounding primitives" labeling of FORCED hygiene = post-hoc rationalization; same calibration-theater mechanism as Cycle 5 Path C, different words.
2. **Recursive deferral pattern** — "next cycle = inflection" appeared in cycles 3+4+5+6; structural to maintainer-as-PM loop selecting against external signals.
3. **Complementary anti-sycophancy trap** — honest acknowledgment of constraints used as object-level validation.
4. **Solo maintainer burnout vector recalibrated** — monotony + isolation + lack-of-feedback (Eghbal 2020), NOT scope ambition.
5. **Base-rate prior** — solo OSS in 2nd consecutive consolidation cycle without external validation → maintenance mode 6-18 months modal outcome; MeridianIQ has all 4 empirical signature markers.
6. **TAM/SAM/SOM honest numbers** — $40-60M / $8-15M / $0 SOM Cycle 6 base case.

Chairman synthesis accepted H-shape OFF-LIST: forced hygiene W0-W1 (honestly framed, "primitive" labeling DROPPED) + HARD GATE at W2 (5 CD conversations OR 1 persona formally retired with ADR per Pathway A/B HONEST criteria pre-registered against Goodhart) + conditional W3-W5.

| Wave | Delivers | Status |
|------|----------|--------|
| W0 | This ROADMAP refresh + [ADR-0025](adr/0025-cycle-6-entry-h-shape.md) + LESSONS_LEARNED Cycle 6 entry header (6 anti-sycophancy lessons banked) + operator runbook ([cycle6.md](operator-runbooks/cycle6.md)) | IN FLIGHT — this PR |
| Pre-W0 | Bucket A unconditional CVE + Claude model migration ([PR #129](https://github.com/VitorMRodovalho/meridianiq/pull/129) — already shipped 2026-05-17, deployed live) | DONE |
| W1 | Bucket B forced floor bumps (mcp<2, fastapi 0.136.1, pydantic 2.13.4 with ADR-0014 byte-exact re-verify, sveltekit>=2.57.1, vite>=8.0.5, svelte>=5.55.7 [Dependabot XSS #133]) — single hygiene PR | NOT STARTED |
| W2 | **HARD GATE close** — operator delivers 5 CD conversations logged OR 1 persona formally retired with ADR. Pathway A/B HONEST criteria pre-registered per [ADR-0025 §"Honest GATE vs cosmetic GATE distinction"](adr/0025-cycle-6-entry-h-shape.md). IF MET → continue W3-W5; IF NOT MET → BLOCK + amend ADR-0025 → Cycle 6.5 pivot to discovery-only | NOT STARTED — issue #134 tracks |
| W3 (conditional) | Frontend DA cluster (#105/#106/#107/#108 + #110 + #46) — SHIP ON a11y intrinsic merit (DROPPED "WCAG-AA enterprise procurement" framing) | NOT STARTED |
| W4 (conditional) | Backend P3 (#117 + #119 single-tenant framing + #120 BLE001) + Fly autosuspend evaluation. **Prompt caching ADR DEFERRED to Cycle 7** per operator decision 3 at ADR-0025 ratification ($0 SOM = $0 ROI; coherent with DROPPED "AI cost moat" framing). | NOT STARTED |
| W5 (conditional) | Hygiene close (mypy slice #121 first cut; CI floor-verify step #131; release tag) | NOT STARTED |

Pre-registered success criteria (≥6/9 graceful threshold; criterion #3 W2 GATE is MANDATORY): see [ADR-0025 §"Decision"](adr/0025-cycle-6-entry-h-shape.md) + [`memory/project_v40_cycle_6.md`](https://github.com) (private operator memory).

**Operator decisions made at ratification (2026-05-17)**: A/A/B/B/A — keep W2 GATE criteria as-written; all 7 personas eligible for Pathway B; defer prompt caching to Cycle 7; sign-off ADR lineage with caveat that Round 1 council protocol may need amendment (3 consecutive off-list Chairman syntheses); accept Pathway A/B HONEST distinction as-written. Audit trail at [PR #135 comment](https://github.com/VitorMRodovalho/meridianiq/pull/135#issuecomment-4469468635).

**Calibration framework status this cycle**: held without modification (3rd consecutive cycle held). ADR-0023 stays load-bearing.

**4 framings DROPPED with sycophancy-recurrence trigger**: compounding primitives / multi-tenant readiness / WCAG-AA enterprise procurement / AI cost moat. Reintroduction in any W3+ PR description triggers Cycle 6.5 amendment via DA-as-second-reviewer protocol per `feedback_entry_council_discipline.md`.

---

## Cycle 7+ candidate deeps (deferred from Cycle 6 entry council, post-v4.4.0 / v4.3.1)

Same gating language as the Cycle 6 entry council carried forward:

- **A1+A2 — auto-grouping deep + baseline inference** (deferred 4th consecutive cycle). Three preconditions per [ADR-0021 §"Why NOT the PV deep"](adr/0021-cycle-3-entry-floor-plus-field-shallow.md) still UNMET.
- **E1 — multi-discipline forensic methodology** (named TRAP in Cycle 5 Round 1 strategist; #79 content_hash explicitly DROPPED from Cycle 6 scope by Cycle 6 DA exit-council to avoid trap-compounding). Reactivates Cycle 7+ ONLY if (a) labeled forensic gold-standard corpus is procurable AND (b) demand-validation signal materializes.
- **Optimism-pattern forecast feature reactivation** ([ADR-0023 §"Cycle 5+ preconditions"](adr/0023-cycle-4-w4-outcome.md)) — 12-24 month timeline minimum unchanged.
- **Field-surface deep** — gating preconditions: (a) ≥1 design-partner conversation logged AND (b) pre-W0 audit-spike completes G702/G703 inventory. Cycle 6 W2 GATE outcome materially affects whether (a) can be checked off.
- **Owner-rep program-portfolio dashboard** — gating: (a) ≥3 prospects ask explicitly per ADR-0022 demand-validation gate AND (b) PMO Director persona pull demonstrably opens (a)-class moat surface beyond commodity rollup.
- **Anthropic prompt caching ADR** — deferred Cycle 6 W4 → Cycle 7 per operator decision 3 at ADR-0025 ratification. Reactivates when (a) usage emerges OR (b) Cycle 6 W2 GATE outcome shifts priorities.
- **Schedule Viewer Wave 7** — slot-opportunistic shallow inside any cycle.
- **Plugin sandbox / E3 marketplace** — preconditions still unmet.
- **Council protocol amendment** (open question banked at Cycle 6 entry per operator decision 4 caveat): "Should Round 1 agents be required to challenge the planning memo's candidate pool BEFORE proposing scope?" 3 consecutive cycles (4+5+6) have produced off-list Chairman syntheses from Round 2 paired demolition. Cycle 7 entry council should evaluate whether this pattern indicates Round 1 council protocol structurally selects for sycophancy.

**Cycle 7 entry framing risks** carried forward:
- Cycle 6 W2 GATE outcome determines candidate set materially. GATE met honestly → Cycle 7 inherits one validated persona path (Field/Owner/Sub viable as deep with evidence base). GATE met cosmetically → Cycle 7 inherits Cycle 6.5 obligations (discovery-only pivot delayed one cycle, not avoided).
- If Cycle 7 becomes Cycle 6+1 also H-shape OR Z-shape, three consecutive consolidation cycles crosses base-rate stall-signature threshold per [ADR-0025 §"Decision Drivers" #6](adr/0025-cycle-6-entry-h-shape.md). Cycle 7 entry council must explicitly weigh "third consolidation cycle stale or forced" with the 4 markers as evidence.
- Persona retirement ADR pathway (per ADR-0025 §"Decision" Pathway B): if Cycle 6 retires 1 persona, Cycle 7+ pool contracts irreversibly to 6 personas. Cycle 7 entry must explicitly reckon with which persona was retired and how that affects deep candidate set.

---

## Cycle 5 + Cycle 6 carry-over operator backlog (post-v4.3.0)

Cycle 3+4 operator items closed during Cycle 5 close-arc (per Cycle 5 LESSONS_LEARNED). Currently open operator items:

| # | Item | Tracking | Runbook |
|---|---|---|---|
| Cy5 #1 | Z-IV active outreach (AACE/PMI working-group inquiry) — operator-paced; converted to W2 HARD GATE in Cycle 6 per ADR-0025 | Cycle 6 issue [#134](https://github.com/VitorMRodovalho/meridianiq/issues/134) | [`cycle6.md`](operator-runbooks/cycle6.md) |
| Cy6 #1 | **W2 HARD GATE (MANDATORY)** — 5 CD conversations logged OR 1 persona formally retired with ADR per Pathway A/B HONEST. W2 close ~2026-05-31. | [#134](https://github.com/VitorMRodovalho/meridianiq/issues/134) | [`cycle6.md`](operator-runbooks/cycle6.md) |
| Cy6 #2 | ADR-0025 ratification + Cycle 6 ROADMAP refresh + LESSONS_LEARNED Cycle 6 entry header + Cycle 6 operator runbook | this PR + [PR #135](https://github.com/VitorMRodovalho/meridianiq/pull/135) merged | [`cycle6.md`](operator-runbooks/cycle6.md) |
| Cy6 #3 | Cycle 6.5 amendment ADR (IF W2 GATE fails OR cosmetic-met) | ADR-0026 reserved | template in [`cycle6.md`](operator-runbooks/cycle6.md) |
| Cy6 #4 | Cycle 7 entry council protocol amendment question (per operator decision 4 caveat) | deferred Cycle 7 W0 | n/a |
| Cy5+ multi-cycle | Corpus assembly via Issue [#13](https://github.com/VitorMRodovalho/meridianiq/issues/13) (Cycle 1 community ask) — base rate ≈ 0% per IV pattern-match | issue #13 | [ADR-0023 §"Cycle 5+ preconditions"](adr/0023-cycle-4-w4-outcome.md) |

---

## Deferred technical follow-ups (parking lot — pull into a wave when relevant)

- Per-user `key_func` on `start_progress_job` (D1 partial — IP keying buys headroom; user-level keying is the structurally-correct fix).
- `429` alerting / Sentry breadcrumb suppression on heartbeat `auth_check` events (log-noise control).
- `GET /lifecycle` endpoint smoke test via TestClient (helper-level + summary-level coverage already exists).
- Source-aware boolean shape on `effective_is_construction_active` (rename only if MCP / external integrations report confusion).
- Entry-points-based engine discovery for the calibration harness (replace module-level `_REGISTRY` dict with `importlib.metadata.entry_points` so engines self-register via `pyproject.toml`).
- **`channel_known: bool` field on by-job endpoint** (devils-advocate PR #35 item 2). Differentiate "still running" (channel still in `_channels` registry) from "session lost" (channel reaped or process restart). Today both surface as `simulation_id: null` and the poller waits the full 60s window before declaring failure. Contract change; needs its own PR.
- **`AbortController` plumbing for `getRiskSimulationByJob`** (devils-advocate PR #35 item 7). On rapid unmount/remount loops (route navigation), `destroy()` flips `recoveryAborted = true` but the in-flight `await getRiskSimulationByJob` continues to completion before the flag is re-checked. Leaks one HTTP roundtrip per dropped instance. Wire `AbortController` through to the underlying `fetch`.
- **Vitest test for `_attemptRecovery` end-to-end** (devils-advocate PR #35 item 11). No test exercises the actual WS-drop → composable enters `recovering` → poller succeeds → composable flips to `done` path. Needs a Vitest test with a fake `recoveryPoller` and a controlled `error.code` event to drive the state machine.
- **Install `types-networkx` + fix `dcma14.py` datetime mismatch** (devils-advocate PR #36 item 3). Closes the 4 transitive mypy strict errors that ``--follow-imports=silent`` currently masks. Small change in `src/analytics/dcma14.py:100-102` (datetime None-handling) plus a `types-networkx` add to `[dev]` extras.
- **Cycle 4 W3 follow-ups** (PR #88/#95/#99 P3 carry-overs): #92 (revision-trends endpoint integration test), #91 (404-vs-RLS-denied), #90 (error handling), #89 (CUSUM improvement-vs-slip distinction), #96 (locale-aware formatting), #97 (SVG chart a11y), #98 (revision-trends polish), #100 (W3-C ADR amendment + cross-Python byte-stability).
- **Cycle 4 W2 + W4 follow-ups**: #82 (race condition test), #84/#85/#86 (UX polish), #87 (Vitest harness for Svelte 5).

---

## Engineering reservations

- **`src/analytics/lifecycle_health.py`** — reserved (ADR-0010 not
  authored). Revisit options: ruleset v2 tuning (gated on the
  contributor calibration dataset from issue #13) or a binary-detector
  + preview-flag redesign. See `docs/adr/0009-w4-outcome.md` for the
  full record of what was tried and why it parked.
- **Fuzzy-match dependency category** — reserved (ADR-0011 not
  authored). See ADR-0009 §"Wave A" for the original framing.
- **ADR-0022 + ADR-0023** — **AUTHORED** at Cycle 4 entry + Cycle 4 W4 close. No longer reserved.
- **ADR-0024** — **AUTHORED** at Cycle 5 entry (Z-shape consolidation). No longer reserved.
- **ADR-0025** — **AUTHORED** at Cycle 6 entry (H-shape: forced hygiene + hard W2 gate). No longer reserved.
- **ADR-0026+** — next reserved for either Cycle 6.5 amendment (if W2 GATE fails OR cosmetic-met) OR Cycle 7 entry ADR (whichever ships first).
- **Schedule Viewer Wave 7** — backend engines exist (`src/analytics/resource_leveling.py`, `src/analytics/evm.py`); Gantt UI integration tracked at #23 with sub-issues #29 (P1 resource histogram), #30 (P2 cost-loading), #31 (P2 BVA per activity), #32 (P3 RCCP highlighting). Slot-opportunistic shallow inside any cycle; Cycle 5+ candidate.

---

## Research-only — explicitly not on a roadmap slot

These appear in occasional discovery rounds. They are listed here so
contributors don't infer commitment from absence elsewhere.

- Federated learning across organizations.
- BIM-lite / IFC metadata integration.
- GIS for linear-infrastructure scheduling.

---

## Hard upstream blocks

1. **Python 3.14 in `Dockerfile`** — blocked by `supabase ≥ 2.10 →
   storage3 → pyiceberg`. pyiceberg has no 3.14 wheel for Debian slim
   as of 2026-04-26; build-from-source fails on missing system C
   headers. Bump only after pyiceberg ships a 3.14 wheel **or**
   storage3 drops the dependency. Revert history:
   `f1bd4e2` bumped → broke deploy → reverted in `df672d9`.
2. **`websockets` major 16** — blocked by `realtime 2.29.0` (Supabase
   realtime sub-package) pinning `websockets<16,>=11`. Local install
   stays at `15.0.1`.

---

## Cadence

Per [ADR-0018](adr/0018-cycle-cadence-doc-artifacts.md), every cycle close updates five artifacts. v4.3.0 Cycle 5 close artifacts (shipped via [PR #124](https://github.com/VitorMRodovalho/meridianiq/pull/124)):

| Artifact | Status |
|----------|--------|
| `docs/ROADMAP.md` | refreshed at v4.3.0 release tag |
| [`BUGS.md`](../BUGS.md) header + pruning | refreshed at v4.3.0 release tag |
| [`LESSONS_LEARNED.md`](../LESSONS_LEARNED.md) Cycle 5 entry | appended at v4.3.0 release tag with 7 lessons captured Cycle 5 close |
| Catalog regen via `scripts/generate_*.py` + `scripts/check_stats_consistency.py` | run at v4.3.0 release tag prep |
| Audit re-run | DEFERRED — last baseline `docs/audit/2026-04-26/`; next baseline to follow Cycle 6 close or Cycle 7 entry kickoff |

Cycle 5 entry ADR (ADR-0024) was authored 2026-05-09; Cycle 6 entry ADR (ADR-0025) authored 2026-05-17 with the same 4-agent council pattern. Cycle 6 W0 closure artifacts (this PR): ROADMAP refresh + LESSONS_LEARNED Cycle 6 entry header + `docs/operator-runbooks/cycle6.md`. v4.4.0 / v4.3.1 close artifacts will follow at Cycle 6 close (W5 conditional).

---

## See also

- [`CHANGELOG.md`](../CHANGELOG.md) — release-by-release record.
- [`docs/adr/`](adr/) — architectural decisions (current canon: 0001–0025).
- [`docs/audit/`](audit/) — structural audits + handoff procedures.
- [`docs/SCHEDULE_VIEWER_ROADMAP.md`](SCHEDULE_VIEWER_ROADMAP.md) —
  feature-specific Gantt roadmap (deeper detail than this top-level
  view).
