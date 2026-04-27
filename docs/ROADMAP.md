# MeridianIQ — Roadmap

Forward-looking 1-page plan. Refreshed at every cycle close per
[ADR-0018](adr/0018-cycle-cadence-doc-artifacts.md). Historical
release-by-release detail lives in [`CHANGELOG.md`](../CHANGELOG.md);
architectural decisions in [`docs/adr/`](adr/); structural audits in
[`docs/audit/`](audit/).

> Last refreshed: **2026-04-27 (Cycle 3 W3 close — W4 reproduction regression test merged at PR #48 `261eb72`; Cycle 3 success criteria #1 + #5 closed; 2/9 closed)**.

---

## Current state — Cycle 2 closed

**Theme:** Consolidation + Primitive ([ADR-0019](adr/0019-cycle-2-entry-consolidation-primitive.md), Option 4).
**Released as:** [`v4.1.0`](https://github.com/VitorMRodovalho/meridianiq/releases/tag/v4.1.0)
at commit `aae1bb1`. **6 of 7** pre-registered success criteria closed
wave-by-wave; the 7th = this release tag itself (per
[CHANGELOG.md §v4.1.0 → "Pre-registered success criteria"](../CHANGELOG.md)).
Criterion 5 (`python -m tools.calibration_harness` reproduces a
coarse-banded report shape) is met with an honest caveat —
[ADR-0020 §"Decision"](adr/0020-calibration-harness-primitive.md)
explicitly notes the pipeline ships but does NOT reproduce the W4
outcome numbers authoritatively until the W4 private manifest is
archived (see "Operator actions" below).

| Wave | Delivers |
|------|----------|
| W0 | `RATE_LIMIT_READ` on `POST /api/v1/jobs/progress/start` (D1) · slowapi in `[dev]` extras (D10) · `useWebSocketProgress.destroy()` (D11). |
| W1 | WS server heartbeat + `4401` close on JWT expiry / API-key revocation (D3) · `recoveryPoller` composable hook (D4 contract; backend wiring deferred — feature dormant for users until Cycle 3 lands the by-job endpoint). |
| W2 | Authoritative `is_construction_active` tri-state on `LifecyclePhaseInferenceSchema` + `LifecyclePhaseSummary` (B2 honesty-debt closure) · `LifecyclePhaseCard` UI split (chip above phase, phase demoted to `(preview)`) · W4 calibration post-mortem published. |
| W3 | `tools/calibration_harness.py` reusable primitive ([ADR-0020](adr/0020-calibration-harness-primitive.md)). |

---

## Next — Cycle 3 (kickoff 2026-04-27, in flight)

**Theme:** Floor + Field-surface shallow ([ADR-0021](adr/0021-cycle-3-entry-floor-plus-field-shallow.md), Option α).
**Tag target:** `v4.2.0` — "Governance + Corpus Foundation".

The 2026-04-27 council round (4 agents over 2 rounds per the protocol
established in Cycle 2 and documented in memory `project_v40_cycle_2.md`
§"Roles + councils for Cycle 2") rejected both ADR-0019 §"Reversibility"
pre-committed candidate deeps and the strategist-proposed hybrid. Round 2 devils-advocate
verified A2 baseline inference is **not separable** from A1 grouping
in the current codebase (`src/database/store.py:252-260` — `save_project`
auto-creates programs from `proj_short_name` exact-match with no
baseline modeling primitive); round 2 investor-view confronted its
own ADR-0019 §"Option 3" caveat as relative-not-absolute and now
underweighted, citing the absent forensic-corpus precondition for E1.
Both round 2 agents converged on a floor plan that closes the
contractual operator-block work (ADR-0018 §5 + ROADMAP §"Operator
actions") + ships the W4 reproduction regression test as the
load-bearing primitive that unblocks any future calibration-dependent
deep.

A1+A2 deferred to Cycle 5+ with corpus-build preconditions; E1
deferred to Cycle 4 with the corpus-precondition gate. ADR-0022 and
ADR-0023 reserved for whichever Cycle 4 deep ships.

| Wave | Delivers | Status |
|------|----------|--------|
| W0 | This ROADMAP refresh + ADR-0021 + ADR-0022/0023 reservations + 2026-04-26 audit re-run published as `docs/audit/2026-04-26/` (6-layer per ADR-0018 §5) with findings as `audit-2026-04-26`-labeled issues. | **DONE** — ADR-0021 + ROADMAP merged in PR #38 (`ea4ee4d`); audit re-run merged in PR #39 (`0524db7`); 7 issues created (`#40` meta + `#41`–`#46` individual). [`docs/audit/2026-04-26/`](audit/2026-04-26/) shipped 11 new findings (4 P2, 7 P3, zero P0/P1). |
| W1 | Migration `026_api_keys_schema_align.sql` applied in production per `docs/audit/HANDOFF.md §H-01` (backup, apply, sample-row inspection, RLS verification, audit-log entry). Closes `#26` (P0). | OPEN — operator-paced |
| W2 | `#28` ratifications of ADR-0017/0018/0019/0020/0021 (escopo ampliado per audit-2026-04-26 AUDIT-009 — body update needed). W4 manifest archive into `meridianiq-private/calibration/cycle1-w4/` with content-hash verification (re-run W4 protocol against the harness if `/tmp` was rotated). | OPEN — operator-paced |
| W3 | `tests/test_w4_reproduction.py` — pins equivalence between `scripts/calibration/run_w4_calibration.py` and `tools/calibration_harness.py` on the same input. Asserts byte-identical aggregate numbers. **Closes the [ADR-0020](adr/0020-calibration-harness-primitive.md) §"Decision" caveat outstanding since 2026-04-26.** (One of two load-bearing items in the cycle alongside the multi-wave operator block per [ADR-0021](adr/0021-cycle-3-entry-floor-plus-field-shallow.md) §"Decision Drivers" #1.) | **DONE** — PR #48 (`ab35074` + `c18222b`) shipped 19 tests covering observation-level equivalence (incl. dedup-input metadata `activity_count`/`last_recalc_date_iso`), engine identity integrity (engine_version + ruleset_version pinned across pipelines), manifest/public payload equivalence, and harness boundary validation on W4 outputs. DA exit-council caught 3 blocking + 4 non-blocking; all addressed. Closes Cycle 3 success criterion #5. |
| W4 | `_ENGINE_VERSION` → `src/__about__.py::__version__` per [ADR-0014 §"Decision Outcome"](adr/0014-derived-artifact-provenance-hash.md#decision-outcome). **Pré-requisito (per audit-2026-04-26 AUDIT-011, P2):** criar `src/__about__.py` (file nunca existiu — ADR não-implementable as-written desde 2026-04-18). Operator decision required on re-materialize event (88 prod rows). Closes the multi-cycle divergence documented in [`LESSONS_LEARNED.md` Cycle 2 §"The ADR-0014 implementation has been diverged for multiple cycles"](LESSONS_LEARNED.md) + `#43`. | NOT STARTED |
| W5 (optional) | Field Engineer mobile look-ahead spike. Sub-pick (deferred to W4 close based on remaining capacity): (a) responsive Schedule Viewer pass, OR (b) 3-week look-ahead view, OR (c) lighter offline cache for already-loaded schedules. Addresses 2-cycle-deep Field/Sub under-service. | NOT STARTED |

Pre-registered success criteria: see [ADR-0021 §"Pre-registered
success criteria"](adr/0021-cycle-3-entry-floor-plus-field-shallow.md).
Cycle 3 fails *gracefully* if ≥5 of the 9 criteria close and the rest
are cleanly documented for Cycle 3.5 or Cycle 4.

---

## Cycle 2 carry-over (now Cycle 3 W0-W2 work)

The four operator-action items below were carried over from Cycle 2
close. ADR-0021 commits them to specific Cycle 3 waves. Maintainer or
operator executes; Claude prepares runbooks. Tracked here for audit
trail; cycle-by-cycle status will move into the wave table above as
each closes.

- **#26 (P0, ops)** — Apply migration `026_api_keys_schema_align.sql`
  to production Supabase. Diagnostic + backup + apply procedure in
  [`docs/audit/HANDOFF.md §H-01`](audit/HANDOFF.md#h-01--aplicar-migration-026-em-produção).
  **Cycle 3 W1.**
- **#28 (P2, governance)** — Council ratification of
  [ADR-0017](adr/0017-deduplicate-api-keys-migration.md),
  [ADR-0018](adr/0018-cycle-cadence-doc-artifacts.md),
  [ADR-0019](adr/0019-cycle-2-entry-consolidation-primitive.md),
  [ADR-0020](adr/0020-calibration-harness-primitive.md).
  **Cycle 3 W2.**
- **W4 manifest archive** — move `/tmp/w4_manifest.json` +
  `/tmp/w4_calibration_private.json` + `/tmp/w4_calibration_public.json`
  into `meridianiq-private/calibration/cycle1-w4/`. If `/tmp` was
  rotated and the manifest is gone, re-run the W4 protocol against
  the harness as the archive material. Pre-condition for the W3
  reproduction regression test. **Cycle 3 W2.**
- ~~**2026-04-26 audit re-run**~~ — **DONE** at PR #39 (commits `7bfc334` +
  `0524db7`). 9 layer docs published in `docs/audit/2026-04-26/` following
  the 6-layer baseline structure. **0 P0 / 0 P1 new**, 4 P2 new (001 README
  mermaid, 003 DA-protocol gap, 007 `_ENGINE_VERSION` reescalada P3→P2,
  011 `__about__.py` missing), 7 P3 new. 11 of 18 baseline AUDIT-NNN
  resolved clean; 3 with regression sub-finding; 1 reaffirmed.
  Pre-registered Cycle 3 success criterion #1 — **CLOSED**. Findings
  tracked under label [`audit-2026-04-26`](https://github.com/VitorMRodovalho/meridianiq/issues?q=label%3Aaudit-2026-04-26)
  (meta #40 + individual #41-#46). **Cycle 3 W0.**

### Pre-Cycle-3 hygiene (Claude-doable, status)

- ~~**D4 backend wiring**~~ — **DONE** at PR #35 (commits
  `a392e85` + `dfcc0bd` + `c43483d` + `3de5ee9`). `RiskStore.bind_job`
  / `get_simulation_id_by_job` indexes added; new
  `GET /api/v1/risk/simulations/by-job/{job_id}` endpoint;
  risk page passes `recoveryPoller`; `'recovering'` UI state +
  i18n × 3 locales; centralised `_assert_channel_owner` helper
  shared between `run_risk_simulation` and the new endpoint.
- **`engine_version` source-of-truth dedup** — **PARTIAL** in this
  cycle. `src/materializer/backfill.py` now imports `_ENGINE_VERSION`
  from `src/materializer/runtime.py` instead of duplicating the
  literal. Two regression tests in
  `tests/test_materializer_runtime.py::TestEngineVersionSingleSource`
  use a monkeypatch+sentinel pattern to assert that both `backfill`
  and the lifecycle router pick up the runtime constant at call
  time (catches future literal-cache regressions even under
  refactors that change import shape).
  **Honest disclosure:** ADR-0014 §"engine_version" line 44
  specifies the source as `src/__about__.py::__version__` — i.e.,
  the package version IS the engine version per the canonical ADR.
  The implementation diverges: `src/__about__.py` does not exist
  and `runtime.py:54` hand-codes `"4.0"`. This PR did NOT close
  that divergence — it only deduped the cross-module literal.
  Wiring `_ENGINE_VERSION` to `importlib.metadata.version("meridianiq")`
  per the ADR would trigger fleet-wide re-materialization (current
  artifacts at `"4.0"` would be marked stale against `"4.1.0"`),
  which is a non-trivial deploy event and needs its own PR with
  operator sign-off. Tracked below.
- **Mypy strict on `EngineAdapter` Protocol conformance** —
  **DONE-with-caveat**. `mypy --strict --follow-imports=silent
  tools/calibration_harness.py` reports `Success: no issues found
  in 1 source file`. The Protocol conformance of
  `_LifecyclePhaseV1Adapter` is clean at the harness boundary.
  **Caveat:** without `--follow-imports=silent` mypy reports 4
  errors in transitive analytics modules
  (`src/analytics/dcma14.py` datetime mismatch,
  `src/analytics/{cpm,tia}.py` networkx untyped imports). These
  are NOT unrelated to the harness — a future engine adapter
  that calls into those modules differently could surface real
  type bugs through them. The honest closure of this item would
  install `types-networkx` and fix the dcma14 datetime; deferred
  to its own PR (separates type-stub installation from the dedup
  intent of this PR).

### Deferred technical follow-ups (parking lot — pull into a wave when relevant)

- Per-user `key_func` on `start_progress_job` (D1 partial — IP keying
  buys headroom; user-level keying is the structurally-correct fix).
- `429` alerting / Sentry breadcrumb suppression on heartbeat
  `auth_check` events (log-noise control).
- `GET /lifecycle` endpoint smoke test via TestClient (helper-level +
  summary-level coverage already exists).
- Source-aware boolean shape on `effective_is_construction_active`
  (rename only if MCP / external integrations report confusion).
- W4 reproduction regression test (`tests/test_w4_reproduction.py`),
  gated on the manifest archive above.
- Entry-points-based engine discovery for the calibration harness
  (replace module-level `_REGISTRY` dict with
  `importlib.metadata.entry_points` so engines self-register via
  `pyproject.toml`).
- **`channel_known: bool` field on by-job endpoint** (devils-advocate
  PR #35 item 2). Differentiate "still running" (channel still in
  `_channels` registry) from "session lost" (channel reaped or
  process restart). Today both surface as `simulation_id: null`
  and the poller waits the full 60s window before declaring
  failure. Contract change; needs its own PR.
- **`AbortController` plumbing for `getRiskSimulationByJob`**
  (devils-advocate PR #35 item 7). On rapid unmount/remount loops
  (route navigation), `destroy()` flips `recoveryAborted = true`
  but the in-flight `await getRiskSimulationByJob` continues to
  completion before the flag is re-checked. Leaks one HTTP
  roundtrip per dropped instance. Wire `AbortController` through
  to the underlying `fetch`.
- **Vitest test for `_attemptRecovery` end-to-end** (devils-advocate
  PR #35 item 11). The new `TestAssertChannelOwner` covers the
  ownership helper directly and `TestRiskByJobEndpoint` covers
  the bind/lookup pair, but no test exercises the actual
  WS-drop → composable enters `recovering` → poller succeeds →
  composable flips to `done` path. Needs a Vitest test with a
  fake `recoveryPoller` and a controlled `error.code` event to
  drive the state machine.
- **Wire `_ENGINE_VERSION` to `__about__.py::__version__` per
  ADR-0014** — close the divergence noted above. Approach:
  create `src/__about__.py` (or read via `importlib.metadata`),
  point `runtime.py:54` at it, ship migration-safe (existing
  `"4.0"` artifacts auto-stale + re-materialize on next access).
  Operator decision required: the re-materialization is a
  non-trivial deploy event (88 prod rows). Could be paired with
  the next legitimate engine algorithm bump rather than shipped
  as pure plumbing.
- **Install `types-networkx` + fix `dcma14.py` datetime mismatch**
  (devils-advocate PR #36 item 3). Closes the 4 transitive mypy
  strict errors that ``--follow-imports=silent`` currently masks.
  Small change in `src/analytics/dcma14.py:100-102` (datetime
  None-handling) plus a `types-networkx` add to `[dev]` extras.

---

## Engineering reservations

- **`src/analytics/lifecycle_health.py`** — reserved (ADR-0010 not
  authored). Revisit options: ruleset v2 tuning (gated on the
  contributor calibration dataset from issue #13) or a binary-detector
  + preview-flag redesign. See `docs/adr/0009-w4-outcome.md` for the
  full record of what was tried and why it parked.
- **Fuzzy-match dependency category** — reserved (ADR-0011 not
  authored). See ADR-0009 §"Wave A" for the original framing.
- **ADR-0022 + ADR-0023** — reserved for the two Cycle 4 deeps
  selected at Cycle 3 close per [ADR-0021](adr/0021-cycle-3-entry-floor-plus-field-shallow.md)
  §"Decision". Candidates: A1+A2 deep (corpus-conditional), E1 deep
  (corpus-conditional), or other if Cycle 3 evidence reframes. Pre-
  reservation matches the ADR-0010 / ADR-0011 pattern (numbers held;
  no stub files until the actual ADR is authored at Cycle 4 W0).
- **Schedule Viewer Wave 7** — backend engines exist
  (`src/analytics/resource_leveling.py`, `src/analytics/evm.py`); Gantt
  UI integration tracked at #23 with sub-issues #29 (P1 resource
  histogram), #30 (P2 cost-loading), #31 (P2 BVA per activity), #32
  (P3 RCCP highlighting). Re-evaluated at Cycle 3 entry (ADR-0021
  §"Considered Options" Option 3 — rejected as cycle commitment, kept
  as slot-opportunistic shallow). Strong candidate for a Cycle 4+
  shallow.

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

Per [ADR-0018](adr/0018-cycle-cadence-doc-artifacts.md), every cycle
close updates five artifacts. The Cycle 2 close did:

| Artifact | Status |
|----------|--------|
| `docs/ROADMAP.md` | refreshed at Cycle 2 close + this Cycle 3 W0 entry |
| [`BUGS.md`](../BUGS.md) header + pruning | refreshed at Cycle 2 close |
| [`docs/LESSONS_LEARNED.md`](LESSONS_LEARNED.md) Cycle 2 entry | appended at Cycle 2 close + 5 close-arc lessons appended in PR #37 (2026-04-27) |
| Catalog regen via `scripts/generate_*.py` | done at `6be1ec8` (pre-bump) + `dfcc0bd` (post-by-job endpoint, 2026-04-27) |
| `docs/audit/2026-04-26/` re-run | **DONE — Cycle 3 W0** at PR #39 (`0524db7`); 11 findings (4 P2 + 7 P3, zero P0/P1 new); meta-issue `#40` |

Cycle 3 also implements the Cycle 2 §"What we would do differently"
lesson — this ROADMAP refresh + ADR-0021 land at Cycle 3 W0 (kickoff),
not Cycle 3 close. Future cycles follow the same pattern.

---

## See also

- [`CHANGELOG.md`](../CHANGELOG.md) — release-by-release record.
- [`docs/adr/`](adr/) — architectural decisions (current canon: 0001–0020).
- [`docs/audit/`](audit/) — structural audits + handoff procedures.
- [`docs/SCHEDULE_VIEWER_ROADMAP.md`](SCHEDULE_VIEWER_ROADMAP.md) —
  feature-specific Gantt roadmap (deeper detail than this top-level
  view).
