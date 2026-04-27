# MeridianIQ — Roadmap

Forward-looking 1-page plan. Refreshed at every cycle close per
[ADR-0018](adr/0018-cycle-cadence-doc-artifacts.md). Historical
release-by-release detail lives in [`CHANGELOG.md`](../CHANGELOG.md);
architectural decisions in [`docs/adr/`](adr/); structural audits in
[`docs/audit/`](audit/).

> Last refreshed: **2026-04-26 (Cycle 2 close, v4.1.0)**.

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

## Next — Cycle 3 (kickoff TBD; scope TBD)

**Cycle 3 has not opened.** ADR-0019 §"Cycle 3 status" pre-committed two
candidate deeps gated on the calibration harness landing (which it did
in Cycle 2 W3):

- **A1+A2 — auto-grouping + baseline inference** (product-validator
  deep). Additional gates before opening: MERGE-cascade migration
  scoped as its own wave; A2 baseline contract defined.
- **E1 — multi-discipline forensic methodology** (strategist deep).
  Additional gate: measurability framing for the investor lens.

Cycle 3 opens with the standard council protocol from ADR-0019 §"Process":
`product-validator` + `strategist` synthesis, then `devils-advocate` +
`investor-view` paired adversarial round, then Chairman synthesis →
scope memo. A follow-up PR will populate this section with concrete
waves once that round closes.

---

## Cycle 2 close — outstanding follow-ups

### Operator actions (require human execution; cannot be closed by automation)

- **#26 (P0, ops)** — Apply migration `026_api_keys_schema_align.sql`
  to production Supabase. Diagnostic + backup + apply procedure in
  [`docs/audit/HANDOFF.md §H-01`](audit/HANDOFF.md#h-01--aplicar-migration-026-em-produção).
- **#28 (P2, governance)** — Council ratification of
  [ADR-0017](adr/0017-deduplicate-api-keys-migration.md),
  [ADR-0018](adr/0018-cycle-cadence-doc-artifacts.md),
  [ADR-0019](adr/0019-cycle-2-entry-consolidation-primitive.md),
  [ADR-0020](adr/0020-calibration-harness-primitive.md).
- **W4 manifest archive** — move `/tmp/w4_manifest.json` +
  `/tmp/w4_calibration_private.json` + `/tmp/w4_calibration_public.json`
  into `meridianiq-private/calibration/cycle1-w4/`. Pre-condition for
  the W4-reproduction regression test.
- **2026-04-26 audit re-run** — owed per
  [ADR-0018 §5](adr/0018-cycle-cadence-doc-artifacts.md), which states
  the audit re-run is *cycle-close mandatory*, not opportunistic. The
  Cycle 2 close ships only 4 of the 5 ADR-0018 artifacts in this
  refresh; this 5th is tracked as a separate operator work item to be
  executed before Cycle 3 W0 opens. Output: a new
  `docs/audit/YYYY-MM-DD/` directory following the 6-layer structure
  of the 2026-04-22 baseline; findings become GitHub issues with the
  `audit-YYYY-MM-DD` label. If pragmatically deferred past Cycle 3 W0,
  authoring an ADR-0018 amendment (rather than silently slipping the
  contract) is the honest move.

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
- **Schedule Viewer Wave 7** — backend engines exist
  (`src/analytics/resource_leveling.py`, `src/analytics/evm.py`); Gantt
  UI integration tracked at #23 with sub-issues #29 (P1 resource
  histogram), #30 (P2 cost-loading), #31 (P2 BVA per activity), #32
  (P3 RCCP highlighting). Strong candidate for a Cycle 3+ wave.

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
| `docs/ROADMAP.md` (this doc) | refreshed in this commit |
| [`BUGS.md`](../BUGS.md) header + pruning | refreshed in this commit |
| [`docs/LESSONS_LEARNED.md`](LESSONS_LEARNED.md) cycle entry | appended in this commit |
| Catalog regen via `scripts/generate_*.py` | done in `6be1ec8` (pre-bump) |
| `docs/audit/2026-04-26/` re-run | **owed** per ADR-0018 §5 (deferred to a separate operator work item — see "Operator actions" follow-ups) |

---

## See also

- [`CHANGELOG.md`](../CHANGELOG.md) — release-by-release record.
- [`docs/adr/`](adr/) — architectural decisions (current canon: 0001–0020).
- [`docs/audit/`](audit/) — structural audits + handoff procedures.
- [`docs/SCHEDULE_VIEWER_ROADMAP.md`](SCHEDULE_VIEWER_ROADMAP.md) —
  feature-specific Gantt roadmap (deeper detail than this top-level
  view).
