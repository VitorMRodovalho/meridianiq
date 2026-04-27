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
at commit `aae1bb1`. **7/7** pre-registered success criteria closed.

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
- **2026-04-26 audit re-run** — per ADR-0018 §5, every cycle close
  produces a new `docs/audit/YYYY-MM-DD/` directory following the
  6-layer structure of the 2026-04-22 baseline. Findings become GitHub
  issues with the `audit-2026-04-26` label. Tracked as a separate work
  item; not blocking Cycle 3.

### Pre-Cycle-3 hygiene (Claude-doable, queued)

- **D4 backend wiring** — `RiskStore.job_id` index +
  `GET /api/v1/risk/simulations/by-job/{id}` endpoint + risk-page
  passes `recoveryPoller(jobId)` arg + i18n key `'recovering'` × 3
  locales. Un-dormants the Cycle 2 W1 composable for real users.
- **`engine_version` dynamic** — replace hardcoded `"4.0"` in lifecycle
  adapter with `importlib.metadata`-based read.
- **Mypy strict** on `EngineAdapter` Protocol conformance.

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
| `docs/audit/2026-04-26/` re-run | **pending** (operator action) |

---

## See also

- [`CHANGELOG.md`](../CHANGELOG.md) — release-by-release record.
- [`docs/adr/`](adr/) — architectural decisions (current canon: 0001–0020).
- [`docs/audit/`](audit/) — structural audits + handoff procedures.
- [`docs/SCHEDULE_VIEWER_ROADMAP.md`](SCHEDULE_VIEWER_ROADMAP.md) —
  feature-specific Gantt roadmap (deeper detail than this top-level
  view).
