# MeridianIQ — Roadmap

Forward-looking 1-page plan. Refreshed at every cycle close per
[ADR-0018](adr/0018-cycle-cadence-doc-artifacts.md). Historical
release-by-release detail lives in [`CHANGELOG.md`](../CHANGELOG.md);
architectural decisions in [`docs/adr/`](adr/); structural audits in
[`docs/audit/`](audit/).

> Last refreshed: **2026-05-09 (Cycle 4 close — v4.2.0 β-honest path-A discipline tag. Cycle 4 W4 pre-registered calibration gate path-A activated per ADR-0023; optimism-pattern forecast feature ships preview-only. Cycle 3 + Cycle 4 work consolidated in single v4.2.0 release tag. 7.0/9 graceful threshold met at exact floor — no margin per DA exit-council finding).**

---

## Current state — Cycle 4 closed

**Theme:** β-honest ([ADR-0022](adr/0022-cycle-4-entry-beta-honest.md) — auto-revision + multi-rev S-curve + W4 pre-registered calibration gate).
**Released as:** [`v4.2.0`](https://github.com/VitorMRodovalho/meridianiq/releases/tag/v4.2.0)
(release tag pending merge of [PR `chore/release-v4.2.0`](../CHANGELOG.md#420--2026-05-09--%CE%B2-honest-path-a-discipline-cycle-3-close-arc--cycle-4-close)).

**Cycle 4 success criteria: 7.0/9 closed** at release tag. Per [ADR-0022 §"Pre-registered success criteria"](adr/0022-cycle-4-entry-beta-honest.md): graceful threshold ≥7/9 met at exact floor. The path-A activation on sub-gates A + B (corpus census + Brier precondition skip) accounts for 1.0 of the 7.0 partial credit per ADR-0022's locked accounting (each path-A = 0.5). Sub-gate C passed at F1=0.769231 with margin "1 borderline detection wide" per discrete-metric brittleness analysis ([ADR-0023](adr/0023-cycle-4-w4-outcome.md) §"Sub-gate C — discrete-metric brittleness").

| Wave | Delivers |
|------|----------|
| W0 | [ADR-0022](adr/0022-cycle-4-entry-beta-honest.md) Cycle 4 entry (β-honest) + L&A review of W5 corpus prep. |
| W1 | Migration `028` (`data_date` + `revision_date` + `revision_history` table + soft-tombstone + cap-enforcement trigger + RLS) staging + production. |
| W2 | Auto-revision detection + confirmation card UX + soft-tombstone deliverables (column + AST regression test + audit_log + runbook). |
| W3 | Multi-revision S-curve overlay with calendar-aligned X-axis + slope CI bands + change-point markers + 8 hash-locked synthetic fixtures + locked baseline F1=0.769231. **No forecast curve.** |
| W4 | Pre-registered calibration gate evaluator (`tools/calibration_harness/gates/revision_trends_w4.py` + 49 tests + ADR-0023 outcome record + DA + IV paired exit-council per NFM-9). Path-A activated as expected. |
| W5 | Operator-paced (parallel) — corpus assembly start; manifest archive; #54 re-mat decision. Continues post-cycle. |

**Cycle 3** (Floor + Field-surface shallow per [ADR-0021](adr/0021-cycle-3-entry-floor-plus-field-shallow.md)) closed mid-stream within this same v4.2.0 release. Cycle 3 contributed: 2026-04-26 audit re-run, W3 reproduction regression test (closes ADR-0020 §"Decision" caveat), `_ENGINE_VERSION` source-of-truth migration (`src/__about__.py`), 5+ ADR-0018-Am.1-disciplined PRs (PR #38 entry, #39 audit, #48 W3, #50 W4 code-side, #52-#58 follow-ups). Cycle 3 W5 (Field Engineer mobile look-ahead spike) DROPPED per the optional-buffer ADR-0021 §"Wave plan" provision.

---

## Next — Cycle 5+ (post-v4.2.0)

**No Cycle 5 entry ADR yet authored.** Cycle 5 entry pre-registration runs on the same protocol established Cycle 2: 4-agent council (PV + strategist round 1 parallel; DA + IV round 2 paired adversarially). Date TBD on maintainer schedule.

**Cycle 5 candidate deeps** (carry-over from prior cycles, gated on demand-validation OR corpus-evidence preconditions):

- **A1+A2 — auto-grouping deep + baseline inference** (ADR-0019 §"Reversibility", deferred from Cycle 3 + Cycle 4). Three preconditions per ADR-0021 §"Why NOT the PV deep": (a) merge-cascade migration scoped + ADR; (b) labeled corpus for grouping; (c) labeled corpus for baseline. None satisfied.
- **E1 — multi-discipline forensic methodology** (ADR-0019 §"Option 3", deferred from Cycle 4). Reactivates when (a) Cycle 5+ W4 sub-gate A passes (corpus N≥30) AND (b) labeled forensic gold-standard corpus is procurable. Same corpus precondition that Cycle 4 W4 path-A confirms is unmet.
- **Optimism-pattern forecast feature reactivation** (ADR-0023 §"Cycle 5+ preconditions") — gated on ALL of: `n_with_consent_path ≥ 30`, outcome-labeled corpus, calibration pairs JSON, re-run sub-gate B, author Cycle 5+ outcome ADR with paired DA + IV council. **Realistic timeline 12-24 months minimum** per ADR-0023 §"Cycle 5+ preconditions" + IV exit-council finding #3 (operator + LGPD + community triple-bottleneck).
- **Field-surface deep** — Field Engineer mobile + offline + AIA G702/G703 + sub workflows. Cycle 4 W5 was scoped as a spike, dropped in execution. Could promote to deep with demand-validation evidence (≥3 prospects asking explicitly).
- **Schedule Viewer Wave 7** — backend engines exist (resource_leveling, evm); Gantt UI integration tracked at #23 + sub-issues #29-#32. Slot-opportunistic shallow inside any cycle.
- **Plugin sandbox / E3 marketplace** (ADR-0019 §"Option 2") — gated on subprocess/WASM sandbox ADR + ≥5 external plugins + license-attestation flow. None satisfied.

**Cycle 5+ entry framing risk** — per [ADR-0023 §"Pattern check vs. ADR-0009"](adr/0023-cycle-4-w4-outcome.md) the "calibration theater" critique is now CITABLE (two consecutive W4 path-A activations). Cycle 5+ entry ADR MUST address this honestly: either (a) Cycle 5 ships a deep that is corpus-independent (visualization/UX/governance), OR (b) Cycle 5 commits to corpus assembly as the primary deliverable (Operator-paced + LGPD/GDPR + community-supplied), accepting the 12-24 month timeline. Pretending Cycle 5+ will incidentally produce the corpus while shipping another calibration-dependent feature would be calibration theater of its own.

---

## Cycle 3 + Cycle 4 carry-over operator backlog (post-v4.2.0)

These items remained open at v4.2.0 release tag time. None blocked the cycle close per ADR-0021 (Cycle 3 ≥5/9 graceful threshold) and ADR-0022 (Cycle 4 ≥7/9 graceful threshold). All have runbooks + tracking issues.

| # | Item | Tracking | Runbook |
|---|---|---|---|
| Cy3 #2 | Apply migration `026_api_keys_schema_align.sql` to production Supabase | [#26](https://github.com/VitorMRodovalho/meridianiq/issues/26) | [`cycle3.md §W1`](operator-runbooks/cycle3.md) |
| Cy3 #3 | Council ratification of 5 ADRs (0017–0021) | [#28](https://github.com/VitorMRodovalho/meridianiq/issues/28) | [`cycle3.md §W2-A`](operator-runbooks/cycle3.md) |
| Cy3 #4 | Archive W4 manifest to `meridianiq-private/calibration/cycle1-w4/` | meta `#25` | [`cycle3.md §W2-B`](operator-runbooks/cycle3.md) |
| Cy3 #7 | Re-mat OR tombstone 88 prod rows at `engine_version='4.0'` | [#54](https://github.com/VitorMRodovalho/meridianiq/issues/54) | [`cycle3.md §W4`](operator-runbooks/cycle3.md) |
| Cy4 #1 | ADR-0022 ratification + Cycle 4 ROADMAP refresh + L&A review | n/a — operator action | [ADR-0022](adr/0022-cycle-4-entry-beta-honest.md) |
| ⚠️ NEW | Re-mat OR tombstone artifacts at `engine_version='4.1.0'` (v4.2.0 bump) | n/a — same as Cy3 #7 | Operator may consolidate both bumps in single re-mat pass |
| ⚠️ NEW | Cycle 4 W5 corpus assembly start (post-v4.2.0, multi-cycle) | issue [#13](https://github.com/VitorMRodovalho/meridianiq/issues/13) (Cycle 1 community ask) | [ADR-0023 §"Cycle 5+ preconditions"](adr/0023-cycle-4-w4-outcome.md) |

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
- **ADR-0022 + ADR-0023** — **AUTHORED** at Cycle 4 entry + Cycle 4 W4 close (β-honest deep + W4 outcome record). No longer reserved.
- **ADR-0024+** — next reserved number for whichever Cycle 5+ deep entry ADR ships.
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

Per [ADR-0018](adr/0018-cycle-cadence-doc-artifacts.md), every cycle close updates five artifacts. v4.2.0 Cycle 4 close artifacts:

| Artifact | Status |
|----------|--------|
| `docs/ROADMAP.md` | refreshed at v4.2.0 release tag (this commit) |
| [`BUGS.md`](../BUGS.md) header + pruning | refreshed at v4.2.0 release tag |
| [`docs/LESSONS_LEARNED.md`](LESSONS_LEARNED.md) Cycle 4 entry | appended at v4.2.0 release tag with 9 lessons captured Cycle 4 close |
| Catalog regen via `scripts/generate_*.py` + `scripts/check_stats_consistency.py` | run at v4.2.0 release tag prep |
| Audit re-run | **DEFERRED** to Cycle 5 W0 entry (Cycle 4 close-arc consolidated `docs/audit/2026-04-26/`; next baseline to follow Cycle 5 entry kickoff) |

Cycle 4 entry ADR (ADR-0022) was authored 2026-04-28; Cycle 5+ entry ADR will follow the same pattern (4-agent council + scope memo at W0).

---

## See also

- [`CHANGELOG.md`](../CHANGELOG.md) — release-by-release record.
- [`docs/adr/`](adr/) — architectural decisions (current canon: 0001–0023).
- [`docs/audit/`](audit/) — structural audits + handoff procedures.
- [`docs/SCHEDULE_VIEWER_ROADMAP.md`](SCHEDULE_VIEWER_ROADMAP.md) —
  feature-specific Gantt roadmap (deeper detail than this top-level
  view).
