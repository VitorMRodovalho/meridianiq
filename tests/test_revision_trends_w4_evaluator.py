# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for ``tools.calibration_harness.gates.revision_trends_w4``.

Cycle 4 W4 — pre-registered calibration gate. Per ADR-0022 §"W4", these tests
pin:

* The locked thresholds (A=30, B=0.20, C=0.75) are NOT user-tunable through
  the dataclass constructors (defends against silent threshold relaxation).
* Sub-gate A validates the subset chain + attestation provenance discipline.
* Sub-gate B skips structurally distinct paths (precondition vs. empty-input).
* Sub-gate C reproduces the W3-C locked baseline F1=0.769231 against the
  committed fixtures and surfaces hash-lock tampering as ``hash_drift_error``.
* The aggregator activates path-A when any sub-gate fails or skips.
* Public payload omits raw calibration pair vectors (anti-leak discipline).
* Embedded ``_DEFAULT_CENSUS_KWARGS`` mirrors ADR-0009 W4 outcome record state.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tools.calibration_harness.gates.revision_trends_w4 import (
    _DEFAULT_CENSUS_KWARGS,
    _FIXTURE_OFFSET,
    _LOCKED_F1_BASELINE,
    _SUB_GATE_A_THRESHOLD,
    _SUB_GATE_B_THRESHOLD,
    _SUB_GATE_C_THRESHOLD,
    CalibrationPair,
    CorpusCensus,
    SubGateBResult,
    SubGateCResult,
    build_payloads,
    default_census,
    evaluate_sub_gate_a,
    evaluate_sub_gate_b,
    evaluate_sub_gate_c,
    load_calibration_pairs,
    load_census,
    run_revision_trends_w4,
)


# --------------------------------------------------------------------------- #
# CorpusCensus validation.
# --------------------------------------------------------------------------- #


_VALID_ATTESTATION = "ADR-0022 §Sub-gate A — synthetic for test"


class TestCorpusCensus:
    def test_valid_census_constructs(self) -> None:
        c = CorpusCensus(
            n_total_multi_revision_programs=4,
            n_completed_with_outcome=2,
            n_with_consent_path=1,
            attestation_source=_VALID_ATTESTATION,
        )
        assert c.threshold == _SUB_GATE_A_THRESHOLD

    def test_threshold_lock_rejects_user_override(self) -> None:
        with pytest.raises(ValueError, match="ADR-0022.*lock"):
            CorpusCensus(
                n_total_multi_revision_programs=30,
                n_completed_with_outcome=30,
                n_with_consent_path=30,
                attestation_source=_VALID_ATTESTATION,
                threshold=29,
            )

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be ≥ 0"):
            CorpusCensus(
                n_total_multi_revision_programs=-1,
                n_completed_with_outcome=0,
                n_with_consent_path=0,
                attestation_source=_VALID_ATTESTATION,
            )

    def test_outcome_exceeds_total_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed n_total"):
            CorpusCensus(
                n_total_multi_revision_programs=4,
                n_completed_with_outcome=5,
                n_with_consent_path=0,
                attestation_source=_VALID_ATTESTATION,
            )

    def test_consent_exceeds_outcome_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed n_completed"):
            CorpusCensus(
                n_total_multi_revision_programs=10,
                n_completed_with_outcome=5,
                n_with_consent_path=6,
                attestation_source=_VALID_ATTESTATION,
            )

    def test_attestation_too_short_rejected(self) -> None:
        with pytest.raises(ValueError, match="≥ 16 chars"):
            CorpusCensus(
                n_total_multi_revision_programs=4,
                n_completed_with_outcome=0,
                n_with_consent_path=0,
                attestation_source="ADR-0022 short",
            )

    def test_attestation_without_citation_rejected(self) -> None:
        with pytest.raises(ValueError, match="ADR-NNNN or git@SHA"):
            CorpusCensus(
                n_total_multi_revision_programs=4,
                n_completed_with_outcome=0,
                n_with_consent_path=0,
                attestation_source="this is plain text only no provenance",
            )

    def test_attestation_with_git_sha_accepted(self) -> None:
        CorpusCensus(
            n_total_multi_revision_programs=4,
            n_completed_with_outcome=0,
            n_with_consent_path=0,
            attestation_source="git@1ab4a2a sandbox-counts on 2026-05-09 main",
        )


# --------------------------------------------------------------------------- #
# Sub-gate A.
# --------------------------------------------------------------------------- #


class TestSubGateA:
    def _census(self, n_total: int, n_outcome: int, n_consent: int) -> CorpusCensus:
        return CorpusCensus(
            n_total_multi_revision_programs=n_total,
            n_completed_with_outcome=n_outcome,
            n_with_consent_path=n_consent,
            attestation_source=_VALID_ATTESTATION,
        )

    def test_pass_at_exact_threshold(self) -> None:
        result = evaluate_sub_gate_a(self._census(30, 30, 30))
        assert result.passed
        assert result.binding_count == 30

    def test_fail_just_below_threshold(self) -> None:
        result = evaluate_sub_gate_a(self._census(29, 29, 29))
        assert not result.passed
        assert result.binding_count == 29

    def test_binding_is_min_of_three(self) -> None:
        # outcome largest; consent smallest → binding = consent.
        result = evaluate_sub_gate_a(self._census(40, 35, 28))
        assert result.binding_count == 28
        assert not result.passed  # 28 < 30

    def test_binding_min_protects_against_non_monotone(self) -> None:
        # n_total smallest (operator transposed columns) → binding = n_total.
        # Both subset-chain rules satisfied: outcome ≤ total, consent ≤ outcome.
        result = evaluate_sub_gate_a(self._census(30, 30, 30))
        assert result.binding_count == 30

    def test_default_census_fails(self) -> None:
        result = evaluate_sub_gate_a(default_census())
        assert not result.passed
        assert result.binding_count == 0
        assert result.n_total_multi_revision_programs == 4


# --------------------------------------------------------------------------- #
# CalibrationPair validation.
# --------------------------------------------------------------------------- #


class TestCalibrationPair:
    def test_valid_pair_constructs(self) -> None:
        p = CalibrationPair(
            predicted_optimism_factor=0.5,
            actual_outcome=0.6,
            horizon_days=30,
        )
        assert p.predicted_optimism_factor == 0.5

    def test_predicted_above_one_rejected(self) -> None:
        with pytest.raises(ValueError, match="predicted_optimism_factor"):
            CalibrationPair(
                predicted_optimism_factor=1.5,
                actual_outcome=0.5,
                horizon_days=10,
            )

    def test_actual_below_zero_rejected(self) -> None:
        with pytest.raises(ValueError, match="actual_outcome"):
            CalibrationPair(
                predicted_optimism_factor=0.5,
                actual_outcome=-0.1,
                horizon_days=10,
            )

    def test_horizon_negative_rejected(self) -> None:
        with pytest.raises(ValueError, match="horizon_days"):
            CalibrationPair(
                predicted_optimism_factor=0.5,
                actual_outcome=0.5,
                horizon_days=-1,
            )

    def test_horizon_zero_accepted(self) -> None:
        CalibrationPair(
            predicted_optimism_factor=0.5,
            actual_outcome=0.5,
            horizon_days=0,
        )


# --------------------------------------------------------------------------- #
# Sub-gate B.
# --------------------------------------------------------------------------- #


class TestSubGateB:
    def _pair(
        self,
        pred: float = 0.5,
        actual: float = 0.5,
        horizon: int = 30,
    ) -> CalibrationPair:
        return CalibrationPair(
            predicted_optimism_factor=pred,
            actual_outcome=actual,
            horizon_days=horizon,
        )

    def test_skipped_when_sub_gate_a_failed(self) -> None:
        result = evaluate_sub_gate_b([self._pair()], sub_gate_a_passed=False)
        assert result.status == "skipped"
        assert result.skipped_reason == "sub_gate_a_failed"
        assert not result.passed

    def test_skipped_when_no_pairs(self) -> None:
        result = evaluate_sub_gate_b([], sub_gate_a_passed=True)
        assert result.status == "skipped"
        assert result.skipped_reason == "no_calibration_pairs"

    def test_skipped_distinguishes_precondition_vs_empty_input(self) -> None:
        a_failed = evaluate_sub_gate_b([self._pair()], sub_gate_a_passed=False)
        no_pairs = evaluate_sub_gate_b([], sub_gate_a_passed=True)
        assert a_failed.skipped_reason != no_pairs.skipped_reason

    def test_pass_at_low_brier(self) -> None:
        # Perfect predictions → Brier = 0.0.
        result = evaluate_sub_gate_b([self._pair(0.5, 0.5)] * 10, sub_gate_a_passed=True)
        assert result.status == "pass"
        assert result.passed
        assert result.brier_score == 0.0
        assert result.weighted_brier_score == 0.0

    def test_fail_above_threshold(self) -> None:
        # Constant 0.5 squared gap → Brier = 0.25 > 0.20.
        result = evaluate_sub_gate_b([self._pair(1.0, 0.5)] * 10, sub_gate_a_passed=True)
        assert result.status == "fail"
        assert not result.passed
        assert result.brier_score is not None
        assert result.brier_score > _SUB_GATE_B_THRESHOLD

    def test_weighted_brier_downweights_distant_horizons(self) -> None:
        # Bad prediction at near horizon (h=1) + perfect at far (h=400).
        # Unweighted: (0.25 + 0) / 2 = 0.125 → passes.
        # Weighted: w_near = 1/sqrt(2) ≈ 0.707; w_far = 1/sqrt(401) ≈ 0.05.
        # weighted_brier = (0.707*0.25 + 0.05*0) / (0.707+0.05) ≈ 0.234.
        # Distant horizons CANNOT rescue near-horizon bad calibration.
        bad_near = self._pair(1.0, 0.5, horizon=1)
        good_far = self._pair(0.0, 0.0, horizon=400)
        result = evaluate_sub_gate_b([bad_near, good_far], sub_gate_a_passed=True)
        assert result.brier_score is not None
        assert result.weighted_brier_score is not None
        # Weighted is HIGHER than unweighted because near-horizon bad is upweighted.
        assert result.weighted_brier_score > result.brier_score


# --------------------------------------------------------------------------- #
# Sub-gate C — locked F1 + tamper detection.
# --------------------------------------------------------------------------- #


class TestSubGateC:
    def test_locked_baseline_against_committed_fixtures(self) -> None:
        """Reproduce W3-C locked F1=0.769231 against committed fixtures."""
        result = evaluate_sub_gate_c()
        assert result.hash_lock_verified
        assert result.hash_drift_error is None
        assert result.n_fixtures == 8
        assert result.n_ground_truths_total == 8
        assert abs(result.f1 - _LOCKED_F1_BASELINE) < 1e-3
        assert result.passed
        assert result.precision == 1.0
        assert result.n_true_positives == 5
        assert result.n_false_positives == 0
        assert result.n_false_negatives == 3

    def test_tamper_detection_byte_flip_short_circuits_evaluation(self, tmp_path: Path) -> None:
        """A 1-byte fixture flip MUST surface as hash_drift_error and skip F1."""
        # Replicate the 8 fixtures + lock into tmp_path.
        from tools.calibration_harness import _OPTIMISM_SYNTH_DIR, _OPTIMISM_SYNTH_LOCK

        tampered_dir = tmp_path / "fixtures" / "optimism_synth"
        tampered_dir.mkdir(parents=True)
        for src in sorted(_OPTIMISM_SYNTH_DIR.glob("corner_*.json")):
            (tampered_dir / src.name).write_bytes(src.read_bytes())
        # Prepend a benign whitespace to alter the SHA without breaking JSON.
        target = tampered_dir / "corner_03.json"
        target.write_bytes(b" " + target.read_bytes())
        # Lock file points at original SHAs.
        lock_path = tmp_path / "optimism_synth.lock"
        lock_path.write_bytes(_OPTIMISM_SYNTH_LOCK.read_bytes())

        result = evaluate_sub_gate_c(fixtures_dir=tampered_dir, lock_path=lock_path)
        assert not result.hash_lock_verified
        assert result.hash_drift_error is not None
        assert "FixtureHashMismatch" in result.hash_drift_error
        assert result.f1 == 0.0
        assert not result.passed

    def test_offset_100_prevents_cross_fixture_cluster_bleed(self) -> None:
        """Structural pin: ``_FIXTURE_OFFSET`` must exceed max revisions per fixture.

        Each committed fixture has 12 revisions. With ``_FIXTURE_OFFSET = 100``,
        adjacent-fixture detection indices are separated by ≥ 88, far above the
        ``cluster_max_gap=1`` ceiling. If a future fixture rotation grew
        ``n_revisions`` past 99, this test surfaces the silent F1 inflation
        before W4 evaluator runs.
        """
        from tools.calibration_harness import _OPTIMISM_SYNTH_DIR

        max_revisions = 0
        for path in sorted(_OPTIMISM_SYNTH_DIR.glob("corner_*.json")):
            fx = json.loads(path.read_text(encoding="utf-8"))
            max_revisions = max(max_revisions, len(fx["finish_days"]))
        assert _FIXTURE_OFFSET > max_revisions, (
            f"_FIXTURE_OFFSET={_FIXTURE_OFFSET} <= max_revisions={max_revisions}; "
            "cluster collapse could bleed across fixtures, silently inflating F1."
        )


# --------------------------------------------------------------------------- #
# Aggregator.
# --------------------------------------------------------------------------- #


_FIXED_TS = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)


def _fixed_now() -> datetime:
    return _FIXED_TS


class TestAggregator:
    def test_default_state_activates_path_a(self) -> None:
        record = run_revision_trends_w4(default_census(), now=_fixed_now)
        assert not record.overall_pass
        assert record.path_a_activated
        assert any("sub-gate A" in r for r in record.path_a_reasons)
        assert any("sub-gate B" in r for r in record.path_a_reasons)
        # C passes — should NOT be in reasons.
        assert not any("sub-gate C" in r for r in record.path_a_reasons)

    def test_all_pass_no_path_a(self) -> None:
        # Synthetic sub-gate A pass (≥30 across all axes).
        passing_census = CorpusCensus(
            n_total_multi_revision_programs=30,
            n_completed_with_outcome=30,
            n_with_consent_path=30,
            attestation_source=_VALID_ATTESTATION,
        )
        # Sub-gate B pass: zero error.
        good_pairs = [
            CalibrationPair(
                predicted_optimism_factor=0.5,
                actual_outcome=0.5,
                horizon_days=10,
            )
        ] * 5
        record = run_revision_trends_w4(passing_census, good_pairs, now=_fixed_now)
        assert record.overall_pass
        assert not record.path_a_activated
        assert record.path_a_reasons == ()

    def test_run_started_at_is_injectable(self) -> None:
        record = run_revision_trends_w4(default_census(), now=_fixed_now)
        assert record.run_started_at == _FIXED_TS


# --------------------------------------------------------------------------- #
# Payloads.
# --------------------------------------------------------------------------- #


class TestPayloads:
    def test_public_omits_pair_vectors(self) -> None:
        pairs = [
            CalibrationPair(
                predicted_optimism_factor=0.7,
                actual_outcome=0.4,
                horizon_days=15,
            )
        ]
        record = run_revision_trends_w4(default_census(), pairs, now=_fixed_now)
        _, public, _private = build_payloads(record, pairs=pairs)
        public_str = json.dumps(public, sort_keys=True)
        # Pair-level fields must NOT leak to public.
        assert "predicted_optimism_factor" not in public_str
        assert "actual_outcome" not in public_str

    def test_private_contains_pair_vectors(self) -> None:
        pairs = [
            CalibrationPair(
                predicted_optimism_factor=0.7,
                actual_outcome=0.4,
                horizon_days=15,
            )
        ]
        record = run_revision_trends_w4(default_census(), pairs, now=_fixed_now)
        _, _, private = build_payloads(record, pairs=pairs)
        assert private["calibration_pairs"][0]["predicted_optimism_factor"] == 0.7

    def test_manifest_pins_locked_thresholds(self) -> None:
        record = run_revision_trends_w4(default_census(), now=_fixed_now)
        manifest, _, _ = build_payloads(record)
        assert manifest["thresholds_locked"] == {
            "sub_gate_a": _SUB_GATE_A_THRESHOLD,
            "sub_gate_b": _SUB_GATE_B_THRESHOLD,
            "sub_gate_c": _SUB_GATE_C_THRESHOLD,
        }


# --------------------------------------------------------------------------- #
# Census + pair JSON loading.
# --------------------------------------------------------------------------- #


class TestCensusLoading:
    def test_load_census_from_json_validates(self, tmp_path: Path) -> None:
        path = tmp_path / "census.json"
        path.write_text(
            json.dumps(
                {
                    "n_total_multi_revision_programs": 4,
                    "n_completed_with_outcome": 0,
                    "n_with_consent_path": 0,
                    "attestation_source": _VALID_ATTESTATION,
                }
            )
        )
        census = load_census(path)
        assert census.n_total_multi_revision_programs == 4

    def test_load_census_invalid_attestation_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "census.json"
        path.write_text(
            json.dumps(
                {
                    "n_total_multi_revision_programs": 4,
                    "n_completed_with_outcome": 0,
                    "n_with_consent_path": 0,
                    "attestation_source": "no provenance here at all",
                }
            )
        )
        with pytest.raises(ValueError, match="ADR-NNNN or git@SHA"):
            load_census(path)

    def test_load_pairs_from_json(self, tmp_path: Path) -> None:
        path = tmp_path / "pairs.json"
        path.write_text(
            json.dumps(
                [
                    {
                        "predicted_optimism_factor": 0.5,
                        "actual_outcome": 0.4,
                        "horizon_days": 10,
                    }
                ]
            )
        )
        pairs = load_calibration_pairs(path)
        assert len(pairs) == 1
        assert pairs[0].predicted_optimism_factor == 0.5

    def test_load_pairs_non_list_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "pairs.json"
        path.write_text(json.dumps({"not": "a list"}))
        with pytest.raises(ValueError, match="must be a list"):
            load_calibration_pairs(path)


# --------------------------------------------------------------------------- #
# Threshold lock guards (defense against silent relaxation).
# --------------------------------------------------------------------------- #


class TestThresholdLocks:
    def test_sub_gate_a_threshold_constant_pinned(self) -> None:
        assert _SUB_GATE_A_THRESHOLD == 30

    def test_sub_gate_b_threshold_constant_pinned(self) -> None:
        assert _SUB_GATE_B_THRESHOLD == 0.20

    def test_sub_gate_c_threshold_constant_pinned(self) -> None:
        assert _SUB_GATE_C_THRESHOLD == 0.75

    def test_sub_gate_b_result_threshold_lock(self) -> None:
        with pytest.raises(ValueError, match="ADR-0022.*lock"):
            SubGateBResult(
                status="pass",
                skipped_reason=None,
                brier_score=0.0,
                weighted_brier_score=0.0,
                threshold=0.30,  # tampered
                n_pairs=1,
                passed=True,
            )

    def test_sub_gate_c_result_threshold_lock(self) -> None:
        with pytest.raises(ValueError, match="ADR-0022.*lock"):
            SubGateCResult(
                hash_lock_verified=True,
                hash_drift_error=None,
                f1=1.0,
                threshold=0.50,  # tampered
                n_fixtures=8,
                n_detections_total=8,
                n_ground_truths_total=8,
                n_true_positives=8,
                n_false_positives=0,
                n_false_negatives=0,
                precision=1.0,
                recall=1.0,
                passed=True,
            )


# --------------------------------------------------------------------------- #
# Embedded census mirrors ADR-0009 W4 outcome record.
# --------------------------------------------------------------------------- #


class TestEmbeddedCensusReflectsADR:
    def test_default_n_total_matches_adr_0009_w4_record(self) -> None:
        """ADR-0009 W4 outcome §"Hysteresis report" — 4 multi-revision programs."""
        assert _DEFAULT_CENSUS_KWARGS["n_total_multi_revision_programs"] == 4

    def test_default_outcome_count_acknowledges_lgpd_block(self) -> None:
        """ADR-0022 §"Honest disclosures" #6 — corpus is operator + LGPD-blocked.

        Pre-corpus-assembly state: zero programs have completion outcome
        labeled. The census is honest about this.
        """
        assert _DEFAULT_CENSUS_KWARGS["n_completed_with_outcome"] == 0
        assert _DEFAULT_CENSUS_KWARGS["n_with_consent_path"] == 0

    def test_default_attestation_cites_both_adr_sources(self) -> None:
        att = str(_DEFAULT_CENSUS_KWARGS["attestation_source"])
        assert "ADR-0009" in att
        assert "ADR-0022" in att


# --------------------------------------------------------------------------- #
# CLI smoke.
# --------------------------------------------------------------------------- #


class TestCLISmoke:
    def test_cli_runs_end_to_end(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.calibration_harness.gates.revision_trends_w4",
                "--output-dir",
                str(tmp_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        manifest_path = tmp_path / "revision_trends_w4_manifest.json"
        public_path = tmp_path / "revision_trends_w4_public.json"
        private_path = tmp_path / "revision_trends_w4_private.json"
        assert manifest_path.exists()
        assert public_path.exists()
        assert private_path.exists()
        public = json.loads(public_path.read_text(encoding="utf-8"))
        assert public["path_a_activated"] is True
        assert public["sub_gate_c"]["passed"] is True
        # F1 within 1e-3 of locked baseline.
        assert abs(public["sub_gate_c"]["f1"] - _LOCKED_F1_BASELINE) < 1e-3

    def test_cli_run_started_at_flag_yields_byte_identical_output(self, tmp_path: Path) -> None:
        """DA P1 #4: ``--run-started-at`` must enable byte-exact reproducibility.

        Two CLI invocations with the same flag value MUST produce identical
        public + manifest JSONs (excluding private payload — same shape modulo
        per-pair detail when pairs are non-empty).
        """
        first = tmp_path / "first"
        second = tmp_path / "second"
        for out in (first, second):
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.calibration_harness.gates.revision_trends_w4",
                    "--output-dir",
                    str(out),
                    "--run-started-at",
                    "2026-05-09T18:00:00+00:00",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, result.stderr
        for name in (
            "revision_trends_w4_public.json",
            "revision_trends_w4_manifest.json",
        ):
            a = (first / name).read_bytes()
            b = (second / name).read_bytes()
            assert a == b, f"{name} not byte-identical across runs"

    def test_cli_run_started_at_naive_datetime_rejected(self, tmp_path: Path) -> None:
        """Naive datetime (no tz offset) MUST exit non-zero with explicit error."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.calibration_harness.gates.revision_trends_w4",
                "--output-dir",
                str(tmp_path),
                "--run-started-at",
                "2026-05-09T18:00:00",  # no tz
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "timezone" in result.stderr.lower()

    def test_cli_passes_with_overridden_census(self, tmp_path: Path) -> None:
        census_path = tmp_path / "census.json"
        census_path.write_text(
            json.dumps(
                {
                    "n_total_multi_revision_programs": 30,
                    "n_completed_with_outcome": 30,
                    "n_with_consent_path": 30,
                    "attestation_source": ("ADR-0022 sandbox synthetic test — overrides default"),
                }
            )
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.calibration_harness.gates.revision_trends_w4",
                "--census-state",
                str(census_path),
                "--output-dir",
                str(tmp_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        public = json.loads(
            (tmp_path / "revision_trends_w4_public.json").read_text(encoding="utf-8")
        )
        assert public["sub_gate_a"]["passed"] is True
        # B still skipped (no calibration pairs).
        assert public["sub_gate_b"]["status"] == "skipped"
        assert public["sub_gate_b"]["skipped_reason"] == "no_calibration_pairs"
