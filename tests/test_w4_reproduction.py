# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""W3 reproduction regression test — Cycle 3 W3 deliverable per ADR-0021.

Pins equivalence between the original Wave-4 calibration script
(``scripts/calibration/run_w4_calibration.py``, Cycle 1 W4 historical
record) and the reusable harness primitive (``tools/calibration_harness``,
ADR-0020). Closes the ADR-0020 §"Decision" caveat outstanding since
2026-04-26: *"The demo proves the pipeline runs, not that it reproduces
the W4 outcome authoritatively."*

The strategy is **engine-agnostic equivalence on a shared input**:

1. Run both pipelines ONCE against the synthetic XER fixtures in
   ``tests/fixtures/`` via a module-scoped fixture.
2. Assert per-observation outputs (label/phase, confidence,
   rules_fired, program_key_hash, **plus the dedup-input metadata**
   ``activity_count`` and ``last_recalc_date_iso``) are byte-identical
   for every fixture.
3. Assert aggregate counts, histograms, identity strings
   (``engine_version``, ``ruleset_version``), and §B/§C/§D/§E sub-gate
   evaluations are byte-identical (modulo schema-renaming the harness
   applies to generalize beyond lifecycle_phase: ``phase`` →
   ``label``; ``numerator_phase_counts`` → ``numerator_label_counts``;
   ``total_xers_found`` → ``total_fixtures``).

Honest scope (DA exit-council finding addressed in fix-up):

The synthetic 3-XER corpus exercises dedup at the fixture level
(``sample.xer`` + ``sample_update.xer`` + ``sample_update2.xer`` are
revisions of the same program — gate=1, hysteresis=2 per ADR-0020
§"Decision" disclosure). It does NOT exercise hysteresis-flip arithmetic
across confidence-band edges nor §C/§D edge cases. Equivalence on
THESE fixtures is sufficient to prove the harness is a faithful
generalization of the W4 script's logic — a single-line drift in
either pipeline's dedup, sub-gate, or histogram code WILL break this
test. It is NOT a sufficient gate-pass test for any new engine
(authoring an engine still requires a corpus engineered to its own
§A-§E protocol). The reproduction-of-W4-outcome claim only becomes
authoritative when the harness runs against the archived W4 corpus
at ``meridianiq-private/calibration/cycle1-w4/`` — pending W2
operator action.

Drift-detection guarantees:
- Drift in ``infer_lifecycle_phase`` rules: detected (both pipelines
  share the engine; ``TestProtocolDriftPin`` in test_calibration_harness
  pins protocol params separately).
- Drift in harness §A/§B/§C/§D/§E logic: detected (W4 script keeps
  original).
- Drift in W4 script: detected (harness keeps original).
- Drift in ``activity_count`` / ``last_recalc_date_iso`` extraction
  between pipelines: detected (per-observation metadata pinned).
- Drift in hardcoded ``engine_version`` / ``ruleset_version`` between
  pipelines: detected (explicit identity tests).

Combined with ``TestProtocolDriftPin`` (protocol parameters), this
forms the structural reproducibility contract for ADR-0020.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from scripts.calibration import run_w4_calibration as w4_script
from tools.calibration_harness import (
    Observation,
    get_adapter,
    get_protocol,
    run_calibration,
)
from tools.calibration_harness import (
    _lifecycle_phase_revision_order_key as _harness_revision_order_key,
)

# Path resolution: tests run from repo root via pytest.
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# --------------------------------------------------------------------------- #
# Field-name mapping between the two pipelines.
# --------------------------------------------------------------------------- #

# The W4 script speaks `phase` (lifecycle_phase-specific); the harness
# speaks `label` (engine-agnostic). The maps below normalize both to
# the harness's vocabulary so byte-identical comparison is meaningful.
_GATE_EVAL_RENAMES: dict[str, str] = {
    "dominant_phase_share_of_numerator": "dominant_label_share_of_numerator",
    "phase_distribution_sub_gate_ok": "label_distribution_sub_gate_ok",
    "numerator_phase_counts": "numerator_label_counts",
}

_HYSTERESIS_RENAMES: dict[str, str] = {
    "phase_flips_across_revisions": "label_flips_across_revisions",
}

_PUBLIC_RENAMES: dict[str, str] = {
    "phase_histogram_all": "label_histogram_all",
    "phase_histogram_gate": "label_histogram_gate",
}


def _rename_keys(d: dict[str, Any], renames: dict[str, str]) -> dict[str, Any]:
    """Return ``d`` with keys remapped per ``renames`` (non-mapped keys preserved)."""
    return {renames.get(k, k): v for k, v in d.items()}


def _normalize_w4_payload(public: dict[str, Any]) -> dict[str, Any]:
    """Translate W4-script public payload to harness vocabulary.

    Renames applied:
    - ``phase_histogram_all`` → ``label_histogram_all``
    - ``phase_histogram_gate`` → ``label_histogram_gate``
    - inside ``counts``: ``total_xers_found`` → ``total_fixtures``
    - inside each gate evaluation: ``dominant_phase_share_of_numerator`` →
      ``dominant_label_share_of_numerator``;
      ``phase_distribution_sub_gate_ok`` → ``label_distribution_sub_gate_ok``;
      ``numerator_phase_counts`` → ``numerator_label_counts``
    - inside hysteresis report: ``phase_flips_across_revisions`` →
      ``label_flips_across_revisions``

    Volatile fields stripped before equivalence comparison via
    ``_strip_aggregate_volatile_fields`` (a separate function so the
    rename and strip concerns don't entangle).
    """
    normalized = _rename_keys(public, _PUBLIC_RENAMES)
    counts = {**normalized["counts"], "total_fixtures": normalized["counts"]["total_xers_found"]}
    del counts["total_xers_found"]
    normalized["counts"] = counts
    gate_evals = {
        threshold: _rename_keys(ev, _GATE_EVAL_RENAMES)
        for threshold, ev in normalized["gate_evaluations_by_threshold"].items()
    }
    normalized["gate_evaluations_by_threshold"] = gate_evals
    normalized["hysteresis_report_gate_plus_hysteresis"] = _rename_keys(
        normalized["hysteresis_report_gate_plus_hysteresis"], _HYSTERESIS_RENAMES
    )
    return normalized


def _strip_aggregate_volatile_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip fields known to legitimately differ between pipelines.

    NOT stripped (intentionally — these are structural identity markers
    that drift would mean a real bug):
    - ``engine_version`` — pinned in a separate explicit test
      (``TestEngineIdentityIntegrity``), kept in stripped payload here
      and asserted to match.
    - ``ruleset_version`` — same.

    Stripped (legitimately differ):
    - ``run_started_at`` — non-deterministic timestamp.
    - ``schema_version`` — both happen to ship as ``1`` today; allowed
      to diverge if either bumps after an ADR amendment.
    - ``protocol_name`` — harness-only; the W4 script predates the
      protocol concept.
    - ``engine_name`` — both ship as ``"lifecycle_phase"`` today; the
      W4 script writes the same value via ``ENGINE_NAME`` import. Allowed
      to diverge under refactor (e.g., harness adds qualifier suffix).
    """
    out = dict(payload)
    out.pop("run_started_at", None)
    out.pop("schema_version", None)
    out.pop("protocol_name", None)
    out.pop("engine_name", None)
    return out


# --------------------------------------------------------------------------- #
# Pipeline runners.
# --------------------------------------------------------------------------- #


class _PipelineOutputs(NamedTuple):
    """Outputs from one full run of both pipelines on the same fixtures."""

    w4_manifest: dict[str, Any]
    w4_public: dict[str, Any]
    w4_private: dict[str, Any]
    harness_manifest: dict[str, Any]
    harness_public: dict[str, Any]
    harness_private: dict[str, Any]


def _run_harness(fixtures_dir: Path) -> dict[str, dict[str, Any]]:
    """Execute the harness via ``run_calibration`` against the same fixtures."""
    engine = get_adapter("lifecycle_phase")
    protocol = get_protocol("lifecycle_phase-w4-v1")
    fixture_paths = sorted(fixtures_dir.glob("*.xer"))
    outputs = run_calibration(
        engine,
        fixture_paths,
        protocol,
        revision_order_key=_harness_revision_order_key,
    )
    return {
        "manifest": outputs.manifest_payload,
        "public": outputs.public_payload,
        "private": outputs.private_payload,
    }


# --------------------------------------------------------------------------- #
# Tests.
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def fixtures_dir() -> Path:
    """Path to the synthetic XER fixtures used by both pipelines."""
    if not FIXTURES_DIR.is_dir():
        pytest.skip(f"fixtures directory missing: {FIXTURES_DIR}")
    if not list(FIXTURES_DIR.glob("*.xer")):
        pytest.skip(f"no *.xer fixtures under {FIXTURES_DIR}")
    return FIXTURES_DIR


@pytest.fixture(scope="module")
def pipeline_outputs(
    fixtures_dir: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> _PipelineOutputs:
    """Run both pipelines ONCE per test module, share outputs across tests.

    Performance: cuts what was ~17 × 2 pipeline executions to 2 (one per
    pipeline). The W4 script and the harness re-parse the same XERs and
    re-run the same engine, so caching is purely aggregation-level.

    Implementation note: ``monkeypatch`` is function-scoped in pytest
    (cannot be used in module-scoped fixtures). We use
    ``tmp_path_factory`` + manual env var management instead. The
    ``run_w4_calibration`` module-level Path constants are reassigned
    in-place AND restored explicitly in the finally block — this is the
    single non-monkeypatch in the file because pytest's module-scoped
    fixture lifecycle requires it.
    """
    import os

    output_dir = tmp_path_factory.mktemp("w4_reproduction")
    saved_env = os.environ.get("XER_SANDBOX_DIR")
    saved_manifest = w4_script.MANIFEST_OUT
    saved_public = w4_script.PUBLIC_OUT
    saved_private = w4_script.PRIVATE_OUT
    try:
        os.environ["XER_SANDBOX_DIR"] = str(fixtures_dir)
        w4_script.MANIFEST_OUT = output_dir / "w4_manifest.json"
        w4_script.PUBLIC_OUT = output_dir / "w4_calibration_public.json"
        w4_script.PRIVATE_OUT = output_dir / "w4_calibration_private.json"
        rc = w4_script.main()
        assert rc == 0, "W4 script returned non-zero in module-scoped fixture"
        w4 = {
            "manifest": json.loads((output_dir / "w4_manifest.json").read_text()),
            "public": json.loads((output_dir / "w4_calibration_public.json").read_text()),
            "private": json.loads((output_dir / "w4_calibration_private.json").read_text()),
        }
        harness = _run_harness(fixtures_dir)
    finally:
        if saved_env is None:
            os.environ.pop("XER_SANDBOX_DIR", None)
        else:
            os.environ["XER_SANDBOX_DIR"] = saved_env
        w4_script.MANIFEST_OUT = saved_manifest
        w4_script.PUBLIC_OUT = saved_public
        w4_script.PRIVATE_OUT = saved_private
    return _PipelineOutputs(
        w4_manifest=w4["manifest"],
        w4_public=w4["public"],
        w4_private=w4["private"],
        harness_manifest=harness["manifest"],
        harness_public=harness["public"],
        harness_private=harness["private"],
    )


class TestObservationLevelEquivalence:
    """Per-fixture: harness and W4 script must produce IDENTICAL engine
    output AND identical dedup-input metadata.

    Coverage (DA exit-council blocking #1 closed in fix-up):
    - Engine output: label/phase, confidence, parse_error
    - Identity: program_key_hash
    - Forensic: rules_fired list (exact equality)
    - **Dedup inputs: activity_count, last_recalc_date_iso** — without
      these, a future drift where the harness adapter computes
      ``activity_count`` differently from ``_parse_and_classify`` would
      stay invisible if dedup-tie-break ordering happened to coincide.

    This is the load-bearing claim — if observations match per fixture
    on ALL these fields, every aggregate derived from them necessarily
    matches (modulo aggregation logic, covered by tests below)."""

    def test_observation_count_matches(self, pipeline_outputs: _PipelineOutputs) -> None:
        assert len(pipeline_outputs.w4_private["observations"]) == len(
            pipeline_outputs.harness_private["observations"]
        )

    def test_observations_match_per_content_hash(self, pipeline_outputs: _PipelineOutputs) -> None:
        w4_by_hash = {o["content_hash"]: o for o in pipeline_outputs.w4_private["observations"]}
        harness_by_hash = {
            o["content_hash"]: o for o in pipeline_outputs.harness_private["observations"]
        }
        assert w4_by_hash.keys() == harness_by_hash.keys(), (
            "Pipelines disagreed on which fixtures were processed"
        )

        for content_hash in w4_by_hash:
            w4_obs = w4_by_hash[content_hash]
            h_obs = harness_by_hash[content_hash]
            # Engine output: label/phase + confidence MUST match exactly.
            assert w4_obs["phase"] == h_obs["label"], (
                f"Engine label mismatch on {content_hash[:8]}: "
                f"W4={w4_obs['phase']!r} harness={h_obs['label']!r}"
            )
            assert w4_obs["confidence"] == h_obs["confidence"], (
                f"Confidence mismatch on {content_hash[:8]}: "
                f"W4={w4_obs['confidence']!r} harness={h_obs['confidence']!r}"
            )
            assert w4_obs["parse_error"] == h_obs["parse_error"]
            # program_key_hash uses the same algorithm in both pipelines.
            assert w4_obs["program_key_hash"] == h_obs["program_key_hash"]
            # rules_fired list — exact byte equivalence.
            assert w4_obs["rules_fired"] == h_obs["rules_fired"]

    def test_dedup_input_metadata_matches_per_content_hash(
        self, pipeline_outputs: _PipelineOutputs
    ) -> None:
        """Pin the dedup tie-break inputs (DA exit-council blocking #1).

        The W4 script writes ``activity_count`` and ``last_recalc_date_iso``
        at the top level of each observation; the harness writes them
        inside ``metadata``. A drift where one pipeline reads the count
        differently (e.g., excludes summary tasks) would yield identical
        gate hashes on single-revision fixtures BUT diverge on multi-
        revision ones — invisible to this test before this fix-up.
        """
        w4_by_hash = {o["content_hash"]: o for o in pipeline_outputs.w4_private["observations"]}
        harness_by_hash = {
            o["content_hash"]: o for o in pipeline_outputs.harness_private["observations"]
        }
        for content_hash in w4_by_hash:
            w4_obs = w4_by_hash[content_hash]
            h_obs = harness_by_hash[content_hash]
            if w4_obs["parse_error"] is not None:
                # Parse errors carry no metadata in either pipeline.
                continue
            h_metadata = h_obs.get("metadata", {})
            assert w4_obs["activity_count"] == h_metadata.get("activity_count"), (
                f"activity_count diverged on {content_hash[:8]}: "
                f"W4={w4_obs['activity_count']!r} "
                f"harness={h_metadata.get('activity_count')!r}"
            )
            assert w4_obs["last_recalc_date_iso"] == h_metadata.get("last_recalc_date_iso"), (
                f"last_recalc_date_iso diverged on {content_hash[:8]}: "
                f"W4={w4_obs['last_recalc_date_iso']!r} "
                f"harness={h_metadata.get('last_recalc_date_iso')!r}"
            )


class TestEngineIdentityIntegrity:
    """Pin ``engine_version`` and ``ruleset_version`` byte-equality across
    pipelines (DA exit-council blocking #2 closed in fix-up).

    Both values are hardcoded as string literals in TWO separate modules
    (W4 script lines 296+319; harness adapter line 535). If a future PR
    bumps one and forgets the other, the equivalence test for aggregates
    that strips these as "volatile" would silently pass — but the W4
    outcome would be reproduced from a different engine. This class
    pins the integrity directly so the failure mode is loud."""

    def test_engine_version_matches_between_pipelines(
        self, pipeline_outputs: _PipelineOutputs
    ) -> None:
        assert (
            pipeline_outputs.w4_public["engine_version"]
            == (pipeline_outputs.harness_public["engine_version"])
        ), (
            "engine_version diverged between W4 script and harness adapter — "
            "structural identity drift. Author an Amendment ADR to ADR-0014 "
            "before bumping either side."
        )
        assert (
            pipeline_outputs.w4_manifest["engine_version"]
            == (pipeline_outputs.harness_manifest["engine_version"])
        )

    def test_ruleset_version_matches_between_pipelines(
        self, pipeline_outputs: _PipelineOutputs
    ) -> None:
        assert (
            pipeline_outputs.w4_public["ruleset_version"]
            == (pipeline_outputs.harness_public["ruleset_version"])
        ), (
            "ruleset_version diverged between W4 script and harness adapter — "
            "structural identity drift. Author an Amendment ADR to ADR-0016 "
            "before bumping either side."
        )
        assert (
            pipeline_outputs.w4_manifest["ruleset_version"]
            == (pipeline_outputs.harness_manifest["ruleset_version"])
        )


class TestManifestEquivalence:
    """Manifest is the public commit-safe artifact; gate/hysteresis split
    drives every downstream sub-gate evaluation. Equivalence here is the
    contract that ADR-0020 §"Decision" caveat refers to."""

    def test_gate_subset_content_hashes_match(self, pipeline_outputs: _PipelineOutputs) -> None:
        assert (
            pipeline_outputs.w4_manifest["gate_subset_content_hashes"]
            == pipeline_outputs.harness_manifest["gate_subset_content_hashes"]
        )

    def test_hysteresis_subset_content_hashes_match(
        self, pipeline_outputs: _PipelineOutputs
    ) -> None:
        assert (
            pipeline_outputs.w4_manifest["hysteresis_subset_content_hashes"]
            == pipeline_outputs.harness_manifest["hysteresis_subset_content_hashes"]
        )

    def test_parse_failed_content_hashes_match(self, pipeline_outputs: _PipelineOutputs) -> None:
        assert (
            pipeline_outputs.w4_manifest["parse_failed_content_hashes"]
            == pipeline_outputs.harness_manifest["parse_failed_content_hashes"]
        )


class TestPublicPayloadEquivalence:
    """Aggregate counts, histograms, and gate evaluations — the public
    coarse-banded payload that ADR-0009-w4-outcome was built from. The
    harness must reproduce this byte-identically (modulo field renames
    documented in ``_normalize_w4_payload``)."""

    def test_counts_match(self, pipeline_outputs: _PipelineOutputs) -> None:
        normalized_w4 = _normalize_w4_payload(pipeline_outputs.w4_public)
        assert normalized_w4["counts"] == pipeline_outputs.harness_public["counts"]

    def test_label_histogram_all_matches(self, pipeline_outputs: _PipelineOutputs) -> None:
        normalized_w4 = _normalize_w4_payload(pipeline_outputs.w4_public)
        assert (
            normalized_w4["label_histogram_all"]
            == pipeline_outputs.harness_public["label_histogram_all"]
        )

    def test_label_histogram_gate_matches(self, pipeline_outputs: _PipelineOutputs) -> None:
        normalized_w4 = _normalize_w4_payload(pipeline_outputs.w4_public)
        assert (
            normalized_w4["label_histogram_gate"]
            == pipeline_outputs.harness_public["label_histogram_gate"]
        )

    def test_confidence_histogram_gate_matches(self, pipeline_outputs: _PipelineOutputs) -> None:
        assert (
            pipeline_outputs.w4_public["confidence_histogram_gate"]
            == pipeline_outputs.harness_public["confidence_histogram_gate"]
        )

    @pytest.mark.parametrize("threshold_key", ["0.80", "0.70", "0.60"])
    def test_gate_evaluation_at_threshold_matches(
        self, pipeline_outputs: _PipelineOutputs, threshold_key: str
    ) -> None:
        normalized_w4 = _normalize_w4_payload(pipeline_outputs.w4_public)
        w4_eval = normalized_w4["gate_evaluations_by_threshold"][threshold_key]
        h_eval = pipeline_outputs.harness_public["gate_evaluations_by_threshold"][threshold_key]
        assert w4_eval == h_eval, (
            f"Sub-gate evaluation diverged at threshold {threshold_key}.\n"
            f"  W4 (normalized): {w4_eval}\n"
            f"  harness:         {h_eval}"
        )

    def test_hysteresis_report_matches(self, pipeline_outputs: _PipelineOutputs) -> None:
        normalized_w4 = _normalize_w4_payload(pipeline_outputs.w4_public)
        assert (
            normalized_w4["hysteresis_report_gate_plus_hysteresis"]
            == pipeline_outputs.harness_public["hysteresis_report_gate_plus_hysteresis"]
        )


class TestAggregatePayloadByteIdenticalAfterNormalization:
    """Headline assertion ADR-0021 §"Wave plan" W3 commits to: byte-
    identical aggregate numbers on the same input.

    After applying documented field-name normalization, the public
    payloads compare byte-equal modulo three explicitly volatile
    fields (``run_started_at`` timestamp; ``schema_version`` shape
    marker; ``protocol_name`` harness-only identity; ``engine_name``
    refactor-tolerable). ``engine_version`` and ``ruleset_version`` are
    NOT stripped — they're pinned by ``TestEngineIdentityIntegrity``."""

    def test_public_payloads_equal_after_normalization(
        self, pipeline_outputs: _PipelineOutputs
    ) -> None:
        w4_clean = _strip_aggregate_volatile_fields(
            _normalize_w4_payload(pipeline_outputs.w4_public)
        )
        h_clean = _strip_aggregate_volatile_fields(pipeline_outputs.harness_public)
        # Sort keys for deterministic diff if one fires.
        assert json.dumps(w4_clean, sort_keys=True) == json.dumps(h_clean, sort_keys=True), (
            f"Public payloads diverged after normalization.\n"
            f"  W4 keys:      {sorted(w4_clean.keys())}\n"
            f"  harness keys: {sorted(h_clean.keys())}"
        )


class TestManifestByteIdentical:
    """Manifest payloads diverge ONLY in volatile fields after the
    schema_version/protocol_name strip + the W4-only ``dedup_rule``
    descriptive string. Pin equivalence on the load-bearing structural
    fields."""

    def test_manifest_load_bearing_fields_equal(self, pipeline_outputs: _PipelineOutputs) -> None:
        w4_clean = _strip_aggregate_volatile_fields(pipeline_outputs.w4_manifest)
        h_clean = _strip_aggregate_volatile_fields(pipeline_outputs.harness_manifest)
        # The W4 manifest has ``dedup_rule`` (descriptive string) — drop
        # before compare; the harness expresses dedup via the engine's
        # ``dedup_key_priority`` callable, not as a string literal.
        w4_clean.pop("dedup_rule", None)
        assert w4_clean == h_clean


class TestW4ScriptOutputPassesHarnessBoundaryValidator:
    """The harness's ``Observation.__post_init__`` rejects out-of-range
    confidence (``[0.0, 1.0]``); the W4 script does NOT have this
    validator. This class verifies the W4 script's raw dict outputs DO
    pass the harness's validator — closing the gap that the W4 script
    could have shipped a confidence drift the harness would have
    rejected.

    NOT tautological with the rest of the suite (DA exit-council
    blocking #3 reframed in fix-up): the rest of the suite runs the
    harness AFTER the engine produces confidence; this class runs the
    harness's validator AFTER the W4 script's output, exercising the
    cross-pipeline contract directly."""

    def test_w4_observations_pass_harness_boundary_validator(
        self, pipeline_outputs: _PipelineOutputs
    ) -> None:
        for obs in pipeline_outputs.w4_private["observations"]:
            confidence = obs["confidence"]
            if confidence is None:
                # Parse error path; allowed — harness also accepts None
                # under parse_error per Observation contract.
                assert obs["parse_error"] is not None
                continue
            # Construct a fresh Observation from the W4 dict via the
            # harness validator. Throws ValueError if confidence ∉ [0.0, 1.0]
            # — pinning the cross-pipeline contract for any future
            # engine drift that produces 1.0000001-style float quirks.
            Observation(
                content_hash=obs["content_hash"],
                program_key_hash=obs["program_key_hash"],
                label=obs["phase"],
                confidence=confidence,
                parse_error=None,
            )
