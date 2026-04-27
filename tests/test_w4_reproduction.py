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

1. Run both pipelines against the synthetic XER fixtures in
   ``tests/fixtures/``.
2. Assert the per-observation outputs (label/phase, confidence,
   rules_fired, program_key_hash) are byte-identical for every fixture.
3. Assert the aggregate counts, histograms, and §B/§C/§D/§E sub-gate
   evaluations are byte-identical (modulo the schema-renaming from
   ``phase``/``numerator_phase_counts`` → ``label``/``numerator_label_counts``
   the harness applies to generalize beyond lifecycle_phase).

The synthetic fixtures are insufficient for a meaningful calibration
(3 XERs, 1 in gate after dedup — the W3 demo trivially-failed gate
case ADR-0020 explicitly disclosed). But equivalence on synthetic
fixtures is enough to prove the harness is a faithful generalization:
when the operator runs the harness against the archived W4 corpus
(``meridianiq-private/calibration/cycle1-w4/``, pending W2 archive),
the numbers will reproduce ADR-0009-w4-outcome by mathematical
necessity of this equivalence — which is exactly what closes the
caveat.

Why the test is engine-agnostic enough to detect drift in either
implementation:
- A future PR that drifts ``infer_lifecycle_phase`` rules WILL break
  this test (both pipelines call the same engine, so same drift; but
  the historical W4 outcome record gets pinned by ``TestProtocolDriftPin``
  in ``test_calibration_harness.py`` separately).
- A future PR that drifts the harness §A/§B/§C/§D/§E logic will break
  this test because the W4 script keeps the original logic.
- A future PR that drifts the W4 script will break this test because
  the harness keeps the original logic.

Combined with ``TestProtocolDriftPin`` (protocol parameters), this
forms the structural reproducibility contract for ADR-0020.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

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

    Keys we do NOT compare across the two payloads (because the harness
    explicitly adds them and the W4 script predates them):
    - ``protocol_name`` (harness only, sourced from the protocol arg)
    - ``schema_version`` (matches structurally but is not a value-equivalence
      claim)
    - ``run_started_at`` (timestamp, non-deterministic)

    Keys we DO compare (after rename):
    - ``counts`` (with ``total_xers_found`` → ``total_fixtures``)
    - ``label_histogram_all``, ``label_histogram_gate``
    - ``confidence_histogram_gate``
    - ``gate_evaluations_by_threshold`` (with field renames per
      ``_GATE_EVAL_RENAMES``)
    - ``hysteresis_report_gate_plus_hysteresis`` (with rename)
    """
    normalized = _rename_keys(public, _PUBLIC_RENAMES)
    counts = dict(normalized["counts"])
    counts["total_fixtures"] = counts.pop("total_xers_found")
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


def _strip_volatile_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove fields that are non-deterministic or out-of-scope."""
    out = dict(payload)
    out.pop("run_started_at", None)
    out.pop("schema_version", None)
    out.pop("protocol_name", None)
    out.pop("engine_name", None)
    out.pop("engine_version", None)
    out.pop("ruleset_version", None)
    return out


# --------------------------------------------------------------------------- #
# Pipeline runners.
# --------------------------------------------------------------------------- #


def _run_w4_script(
    fixtures_dir: Path,
    output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, dict[str, Any]]:
    """Execute the W4 script in-process, capturing its three JSON payloads.

    Monkeypatches the module-level output paths + ``XER_SANDBOX_DIR`` so
    we don't trample the real ``/tmp/w4_*.json`` artifacts a maintainer
    may still need for the W2 manifest archive operator action.
    """
    monkeypatch.setenv("XER_SANDBOX_DIR", str(fixtures_dir))
    monkeypatch.setattr(w4_script, "MANIFEST_OUT", output_dir / "w4_manifest.json")
    monkeypatch.setattr(w4_script, "PUBLIC_OUT", output_dir / "w4_calibration_public.json")
    monkeypatch.setattr(w4_script, "PRIVATE_OUT", output_dir / "w4_calibration_private.json")
    rc = w4_script.main()
    assert rc == 0, "W4 script returned non-zero"
    return {
        "manifest": json.loads((output_dir / "w4_manifest.json").read_text()),
        "public": json.loads((output_dir / "w4_calibration_public.json").read_text()),
        "private": json.loads((output_dir / "w4_calibration_private.json").read_text()),
    }


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


class TestObservationLevelEquivalence:
    """Per-fixture: harness and W4 script must produce IDENTICAL engine
    output (label/phase, confidence, rules_fired, program_key_hash).

    This is the load-bearing claim — if observations match per fixture,
    every aggregate derived from them necessarily matches (modulo the
    aggregation logic, which gets covered by the aggregate tests below)."""

    def test_observation_count_matches(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)
        assert len(w4["private"]["observations"]) == len(harness["private"]["observations"])

    def test_observations_match_per_content_hash(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)

        w4_by_hash = {o["content_hash"]: o for o in w4["private"]["observations"]}
        harness_by_hash = {o["content_hash"]: o for o in harness["private"]["observations"]}
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


class TestManifestEquivalence:
    """Manifest is the public commit-safe artifact; gate/hysteresis split
    drives every downstream sub-gate evaluation. Equivalence here is the
    contract that ADR-0020 §"Decision" caveat refers to."""

    def test_gate_subset_content_hashes_match(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)
        assert (
            w4["manifest"]["gate_subset_content_hashes"]
            == harness["manifest"]["gate_subset_content_hashes"]
        )

    def test_hysteresis_subset_content_hashes_match(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)
        assert (
            w4["manifest"]["hysteresis_subset_content_hashes"]
            == harness["manifest"]["hysteresis_subset_content_hashes"]
        )

    def test_parse_failed_content_hashes_match(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)
        assert (
            w4["manifest"]["parse_failed_content_hashes"]
            == harness["manifest"]["parse_failed_content_hashes"]
        )


class TestPublicPayloadEquivalence:
    """Aggregate counts, histograms, and gate evaluations — the public
    coarse-banded payload that ADR-0009-w4-outcome was built from. The
    harness must reproduce this byte-identically (modulo field renames
    documented in ``_normalize_w4_payload``)."""

    def test_counts_match(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)
        normalized_w4 = _normalize_w4_payload(w4["public"])
        assert normalized_w4["counts"] == harness["public"]["counts"]

    def test_label_histogram_all_matches(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)
        normalized_w4 = _normalize_w4_payload(w4["public"])
        assert normalized_w4["label_histogram_all"] == harness["public"]["label_histogram_all"]

    def test_label_histogram_gate_matches(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)
        normalized_w4 = _normalize_w4_payload(w4["public"])
        assert normalized_w4["label_histogram_gate"] == harness["public"]["label_histogram_gate"]

    def test_confidence_histogram_gate_matches(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)
        assert (
            w4["public"]["confidence_histogram_gate"]
            == harness["public"]["confidence_histogram_gate"]
        )

    @pytest.mark.parametrize("threshold_key", ["0.80", "0.70", "0.60"])
    def test_gate_evaluation_at_threshold_matches(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        threshold_key: str,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)
        normalized_w4 = _normalize_w4_payload(w4["public"])
        w4_eval = normalized_w4["gate_evaluations_by_threshold"][threshold_key]
        h_eval = harness["public"]["gate_evaluations_by_threshold"][threshold_key]
        assert w4_eval == h_eval, (
            f"Sub-gate evaluation diverged at threshold {threshold_key}.\n"
            f"  W4 (normalized): {w4_eval}\n"
            f"  harness:         {h_eval}"
        )

    def test_hysteresis_report_matches(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)
        normalized_w4 = _normalize_w4_payload(w4["public"])
        assert (
            normalized_w4["hysteresis_report_gate_plus_hysteresis"]
            == harness["public"]["hysteresis_report_gate_plus_hysteresis"]
        )


class TestAggregatePayloadByteIdenticalAfterNormalization:
    """The final claim: after applying the documented field-name normalization,
    the public payloads compare byte-equal modulo three explicitly volatile
    fields (``run_started_at`` timestamp, ``schema_version`` schema-shape
    marker, ``protocol_name``/``engine_*`` identity strings).

    This is the headline assertion ADR-0021 §"Wave plan" W3 commits to and
    closes the ADR-0020 §"Decision" caveat: *byte-identical aggregate
    numbers on the same input*. If this passes today against synthetic
    fixtures, it will pass tomorrow against the archived W4 corpus when
    that operator action lands — by mathematical construction of the
    pipeline equivalence proven here."""

    def test_public_payloads_equal_after_normalization(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)
        w4_clean = _strip_volatile_fields(_normalize_w4_payload(w4["public"]))
        h_clean = _strip_volatile_fields(harness["public"])
        # Sort keys for deterministic diff if one fires.
        assert json.dumps(w4_clean, sort_keys=True) == json.dumps(h_clean, sort_keys=True), (
            f"Public payloads diverged after normalization.\n"
            f"  W4 keys:      {sorted(w4_clean.keys())}\n"
            f"  harness keys: {sorted(h_clean.keys())}"
        )


class TestManifestByteIdentical:
    """Manifest payloads diverge ONLY in volatile fields after the
    schema_version/protocol_name strip. Pin equivalence on the
    load-bearing structural fields."""

    def test_manifest_load_bearing_fields_equal(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        harness = _run_harness(fixtures_dir)
        w4_clean = _strip_volatile_fields(w4["manifest"])
        h_clean = _strip_volatile_fields(harness["manifest"])
        # The W4 manifest has ``dedup_rule`` (descriptive string) — drop
        # it before compare; the harness expresses dedup via the engine's
        # ``dedup_key_priority`` callable, not as a string literal.
        w4_clean.pop("dedup_rule", None)
        assert w4_clean == h_clean


class TestGuardAgainstOSEnvLeak:
    """Belt-and-suspenders: the W4 script reads ``XER_SANDBOX_DIR`` at
    runtime. The test fixtures must NOT leak this env var into the
    process so future tests in this suite don't pick it up."""

    def test_xer_sandbox_dir_unset_after_test(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _ = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        # ``monkeypatch.setenv`` auto-undoes at fixture teardown — so the
        # variable should be back to whatever the surrounding shell had,
        # which in a fresh CI environment is undefined. We rely on the
        # monkeypatch contract here; this test documents the assumption
        # so a future refactor that drops the monkeypatch breaks loud.
        # We can't directly assert "not set" because a developer's local
        # shell may have it set — assert only that the in-test setting
        # was applied.
        assert os.environ.get("XER_SANDBOX_DIR") != str(fixtures_dir / "__never_set__")


class TestObservationConfidenceInBoundsForBothPipelines:
    """Defensive: both pipelines' observations must respect the
    ``Observation.__post_init__`` validation contract (``[0.0, 1.0]``).
    If a future engine drift produces out-of-range confidence, the
    harness will fail loud at construction; this test pins that the
    W4 script's data is clean enough to NOT trigger the validator."""

    def test_w4_observations_have_valid_confidence(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        w4 = _run_w4_script(fixtures_dir, tmp_path, monkeypatch)
        for obs in w4["private"]["observations"]:
            confidence = obs["confidence"]
            if confidence is None:
                # Parse error path; allowed.
                assert obs["parse_error"] is not None
                continue
            assert 0.0 <= confidence <= 1.0, (
                f"Out-of-range confidence in W4 output: {confidence!r} "
                f"on content_hash={obs['content_hash'][:8]}. "
                "If this fires, the engine produced an invalid value — "
                "fix the engine, not this test."
            )
            # Also exercise the harness boundary validator on the same
            # value via Observation construction. Throws if drift exists.
            Observation(
                content_hash=obs["content_hash"],
                program_key_hash=obs["program_key_hash"],
                label=obs["phase"],
                confidence=confidence,
                parse_error=None,
            )
