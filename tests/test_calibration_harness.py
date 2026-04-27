# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for ``tools.calibration_harness`` — ADR-0020.

Pins the contract that the W4 calibration script (``scripts/
calibration/run_w4_calibration.py``) was generalised into a reusable
primitive: protocol authors can pre-register a calibration once,
engine authors register an adapter once, and the harness produces
the §B / §C / §D / §E sub-gate evaluations + manifest / public /
private payloads with the same coarse-banding the Wave-4 outcome
record was built from.

Most tests run on synthetic ``Observation`` rows so the suite is
both fast and engine-agnostic. The CLI smoke test exercises the
``lifecycle_phase`` adapter against the auto-generated fixture XERs
in ``tests/fixtures/`` to prove the full pipeline runs end-to-end.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.calibration_harness import (
    CalibrationProtocol,
    Observation,
    _bucket_confidence,
    confidence_histogram,
    evaluate_sub_gates,
    get_adapter,
    get_protocol,
    hysteresis_report,
    label_histogram,
    run_calibration,
    split_gate_and_hysteresis,
)


def _obs(
    *,
    label: str | None,
    confidence: float | None = 0.75,
    program: str | None = "p1",
    activity_count: int = 100,
    last_recalc_iso: str = "2026-01-01",
    parse_error: str | None = None,
    content_hash: str | None = None,
) -> Observation:
    """Compact factory for synthetic observations."""
    return Observation(
        content_hash=content_hash or f"hash-{label}-{program}-{activity_count}",
        program_key_hash=program,
        label=label,
        confidence=confidence,
        parse_error=parse_error,
        rules_fired=[],
        metadata={
            "activity_count": activity_count,
            "last_recalc_date_iso": last_recalc_iso,
        },
    )


_DEFAULT_PROTOCOL = CalibrationProtocol(name="test-protocol")


class TestSubGateB_UnknownDenominator:
    """§B — ``unknown`` MUST count in the denominator but NEVER in the
    numerator. The whole pre-registration discipline rests on this."""

    def test_unknown_appears_in_denominator(self) -> None:
        gate = [_obs(label="construction", confidence=0.9), _obs(label="unknown", confidence=0.0)]
        result = evaluate_sub_gates(gate, _DEFAULT_PROTOCOL, 0.80, unknown_label="unknown")
        assert result["denominator"] == 2

    def test_unknown_never_passes_gate_even_at_high_confidence(self) -> None:
        """Edge: an engine bug that emitted ``unknown`` with confidence
        1.0 would otherwise sneak past §E. The unknown filter MUST run
        before the threshold check."""
        gate = [_obs(label="unknown", confidence=1.0)]
        result = evaluate_sub_gates(gate, _DEFAULT_PROTOCOL, 0.80, unknown_label="unknown")
        assert result["numerator"] == 0
        assert result["pass_rate"] == 0.0


class TestSubGateC_LabelDistribution:
    """§C — no single label can exceed ``label_distribution_max_share``
    of the numerator. Anti-monoculture; protects against an engine
    that always answers ``construction``."""

    def test_dominant_share_exactly_at_ceiling_passes(self) -> None:
        # 3 of 5 = 60.0% — exactly at the ceiling.
        gate = [
            _obs(label="construction", confidence=0.9),
            _obs(label="construction", confidence=0.9),
            _obs(label="construction", confidence=0.9),
            _obs(label="design", confidence=0.9),
            _obs(label="design", confidence=0.9),
        ]
        result = evaluate_sub_gates(gate, _DEFAULT_PROTOCOL, 0.80, unknown_label="unknown")
        assert result["dominant_label_share_of_numerator"] == 0.6
        assert result["label_distribution_sub_gate_ok"] is True

    def test_dominant_share_above_ceiling_fails(self) -> None:
        gate = [
            _obs(label="construction", confidence=0.9),
            _obs(label="construction", confidence=0.9),
            _obs(label="construction", confidence=0.9),
            _obs(label="design", confidence=0.9),
        ]
        result = evaluate_sub_gates(gate, _DEFAULT_PROTOCOL, 0.80, unknown_label="unknown")
        assert result["dominant_label_share_of_numerator"] == 0.75
        assert result["label_distribution_sub_gate_ok"] is False


class TestSubGateD_ConfidenceHonesty:
    """§D — at least ``confidence_honesty_min_share`` of the gate
    subset must land at confidence < 0.5. The engine has to *show*
    its uncertainty, not anchor everything at 0.85."""

    def test_low_confidence_share_at_floor_passes(self) -> None:
        gate = [_obs(label="construction", confidence=c) for c in [0.4, 0.6, 0.6, 0.6, 0.6]]
        # 1 of 5 below 0.5 = 20.0% — at the floor.
        result = evaluate_sub_gates(gate, _DEFAULT_PROTOCOL, 0.80, unknown_label="unknown")
        assert result["low_confidence_share"] == 0.2
        assert result["confidence_honesty_sub_gate_ok"] is True

    def test_no_low_confidence_observations_fails(self) -> None:
        gate = [_obs(label="construction", confidence=0.9) for _ in range(5)]
        result = evaluate_sub_gates(gate, _DEFAULT_PROTOCOL, 0.80, unknown_label="unknown")
        assert result["low_confidence_share"] == 0.0
        assert result["confidence_honesty_sub_gate_ok"] is False


class TestSubGateE_PrimaryPassRate:
    """§E — pass_rate must reach ``primary_pass_rate_floor``."""

    def test_pass_rate_above_floor_passes(self) -> None:
        # 3 of 4 above threshold = 75% > 70%.
        gate = [
            _obs(label="construction", confidence=0.9),
            _obs(label="design", confidence=0.9),
            _obs(label="planning", confidence=0.9),
            _obs(label="construction", confidence=0.4),
        ]
        result = evaluate_sub_gates(gate, _DEFAULT_PROTOCOL, 0.80, unknown_label="unknown")
        assert result["pass_rate"] == 0.75
        assert result["primary_pass_rate_ok"] is True

    def test_pass_rate_below_floor_fails(self) -> None:
        gate = [
            _obs(label="construction", confidence=0.4),
            _obs(label="design", confidence=0.9),
        ]
        result = evaluate_sub_gates(gate, _DEFAULT_PROTOCOL, 0.80, unknown_label="unknown")
        assert result["pass_rate"] == 0.5
        assert result["primary_pass_rate_ok"] is False


class TestOverallPass:
    """``overall_pass`` is AND of all four sub-gates. Any single failure
    kills the gate — the whole pre-registration is a single decision."""

    def test_all_subgates_pass_yields_overall_pass(self) -> None:
        # Pass rate 80%, dominant 50%, low conf share 20% — all pass.
        gate = [
            _obs(label="construction", confidence=0.9),
            _obs(label="construction", confidence=0.9),
            _obs(label="design", confidence=0.9),
            _obs(label="design", confidence=0.9),
            _obs(label="construction", confidence=0.4),
        ]
        result = evaluate_sub_gates(gate, _DEFAULT_PROTOCOL, 0.80, unknown_label="unknown")
        assert result["overall_pass"] is True

    def test_any_subgate_fail_kills_overall(self) -> None:
        # Pass rate 100%, but dominant share 100% (single label).
        gate = [_obs(label="construction", confidence=0.9) for _ in range(5)]
        result = evaluate_sub_gates(gate, _DEFAULT_PROTOCOL, 0.80, unknown_label="unknown")
        assert result["primary_pass_rate_ok"] is True
        assert result["label_distribution_sub_gate_ok"] is False
        assert result["overall_pass"] is False


class TestDedup:
    """ADR-0009 Amendment 1 §A — per program, keep max(activity_count)
    with tie-break on max(last_recalc_iso). Singletons go to gate."""

    def _key(self, obs: Observation) -> tuple[object, ...]:
        return (
            obs.metadata.get("activity_count", 0),
            obs.metadata.get("last_recalc_date_iso") or "",
        )

    def test_singletons_all_go_to_gate(self) -> None:
        observations = [
            _obs(label="construction", program="p1", content_hash="A"),
            _obs(label="design", program="p2", content_hash="B"),
        ]
        gate, hyst = split_gate_and_hysteresis(observations, dedup_key_priority=self._key)
        assert sorted(gate) == ["A", "B"]
        assert hyst == []

    def test_largest_activity_count_wins(self) -> None:
        observations = [
            _obs(label="construction", program="p1", activity_count=100, content_hash="A"),
            _obs(label="construction", program="p1", activity_count=200, content_hash="B"),
            _obs(label="construction", program="p1", activity_count=150, content_hash="C"),
        ]
        gate, hyst = split_gate_and_hysteresis(observations, dedup_key_priority=self._key)
        assert gate == ["B"]
        assert sorted(hyst) == ["A", "C"]

    def test_recalc_date_breaks_activity_count_tie(self) -> None:
        observations = [
            _obs(
                label="construction",
                program="p1",
                activity_count=100,
                last_recalc_iso="2026-01-01",
                content_hash="A",
            ),
            _obs(
                label="construction",
                program="p1",
                activity_count=100,
                last_recalc_iso="2026-03-01",
                content_hash="B",
            ),
        ]
        gate, hyst = split_gate_and_hysteresis(observations, dedup_key_priority=self._key)
        assert gate == ["B"]
        assert hyst == ["A"]

    def test_parse_failures_excluded_from_grouping(self) -> None:
        observations = [
            _obs(label=None, program=None, parse_error="ParseError", content_hash="X"),
            _obs(label="design", program="p1", content_hash="A"),
        ]
        gate, hyst = split_gate_and_hysteresis(observations, dedup_key_priority=self._key)
        assert gate == ["A"]
        assert hyst == []


class TestHysteresis:
    """Flip-flop counting across preserved serial revisions."""

    def test_no_flips_when_label_and_band_stable(self) -> None:
        observations = [
            _obs(
                label="construction",
                confidence=0.85,
                program="p1",
                last_recalc_iso="2026-01",
                content_hash="A",
            ),
            _obs(
                label="construction",
                confidence=0.85,
                program="p1",
                last_recalc_iso="2026-02",
                content_hash="B",
            ),
            _obs(
                label="construction",
                confidence=0.85,
                program="p1",
                last_recalc_iso="2026-03",
                content_hash="C",
            ),
        ]
        report = hysteresis_report(
            observations,
            hysteresis_hashes={"A", "B"},
            gate_hashes={"C"},
            revision_order_key=lambda o: o.metadata.get("last_recalc_date_iso") or "",
        )
        assert report["multi_revision_programs"] == 1
        assert report["label_flips_across_revisions"] == 0
        assert report["confidence_band_flips_across_revisions"] == 0

    def test_label_change_counts_as_flip(self) -> None:
        observations = [
            _obs(
                label="design",
                confidence=0.85,
                program="p1",
                last_recalc_iso="2026-01",
                content_hash="A",
            ),
            _obs(
                label="construction",
                confidence=0.85,
                program="p1",
                last_recalc_iso="2026-02",
                content_hash="B",
            ),
        ]
        report = hysteresis_report(
            observations,
            hysteresis_hashes={"A"},
            gate_hashes={"B"},
            revision_order_key=lambda o: o.metadata.get("last_recalc_date_iso") or "",
        )
        assert report["label_flips_across_revisions"] == 1

    def test_band_crossing_at_05_counts(self) -> None:
        observations = [
            _obs(
                label="construction",
                confidence=0.4,
                program="p1",
                last_recalc_iso="2026-01",
                content_hash="A",
            ),
            _obs(
                label="construction",
                confidence=0.6,
                program="p1",
                last_recalc_iso="2026-02",
                content_hash="B",
            ),
        ]
        report = hysteresis_report(
            observations,
            hysteresis_hashes={"A"},
            gate_hashes={"B"},
            revision_order_key=lambda o: o.metadata.get("last_recalc_date_iso") or "",
        )
        assert report["confidence_band_flips_across_revisions"] == 1


class TestConfidenceBuckets:
    """The coarse-banding has to be stable — Wave-4 outcome doc cites
    the bucket strings as authoritative."""

    edges = (0.0, 0.5, 0.7, 0.8, 1.0)

    def test_below_first_edge_returns_first_bucket(self) -> None:
        assert _bucket_confidence(0.0, self.edges) == "[0.00,0.50)"
        assert _bucket_confidence(0.49, self.edges) == "[0.00,0.50)"

    def test_at_internal_boundary_belongs_to_higher_bucket(self) -> None:
        assert _bucket_confidence(0.5, self.edges) == "[0.50,0.70)"

    def test_at_max_edge_belongs_to_last_inclusive_bucket(self) -> None:
        assert _bucket_confidence(1.0, self.edges) == "[0.80,1.00]"

    def test_none_confidence_is_separate_bucket(self) -> None:
        assert _bucket_confidence(None, self.edges) == "__missing__"


class TestHistograms:
    def test_label_histogram_zeroes_unobserved_labels(self) -> None:
        h = label_histogram(
            [_obs(label="construction"), _obs(label="design")],
            ("planning", "design", "construction", "unknown"),
        )
        assert h == {"planning": 0, "design": 1, "construction": 1, "unknown": 0}

    def test_confidence_histogram_skips_parse_errors(self) -> None:
        h = confidence_histogram(
            [
                _obs(label="construction", confidence=0.85),
                _obs(label=None, confidence=None, parse_error="ParseError"),
            ],
            (0.0, 0.5, 0.7, 0.8, 1.0),
        )
        assert h == {"[0.80,1.00]": 1}


class TestRegistry:
    def test_unknown_engine_raises(self) -> None:
        with pytest.raises(KeyError, match="not registered"):
            get_adapter("non-existent-engine")

    def test_unknown_protocol_raises(self) -> None:
        with pytest.raises(KeyError, match="not registered"):
            get_protocol("non-existent-protocol")

    def test_lifecycle_phase_adapter_metadata(self) -> None:
        a = get_adapter("lifecycle_phase")
        assert a.engine_name == "lifecycle_phase"
        assert a.unknown_label == "unknown"
        assert "construction" in a.label_set
        assert "unknown" in a.label_set

    def test_w4_protocol_matches_amendment_1(self) -> None:
        """Pin the canonical W4 numbers — the protocol shipped publicly
        as the example for ADR-0020 and downstream engines will copy
        these as a starting template."""
        p = get_protocol("lifecycle_phase-w4-v1")
        assert p.primary_threshold == 0.80
        assert p.additional_thresholds == (0.70, 0.60)
        assert p.label_distribution_max_share == 0.60
        assert p.confidence_honesty_min_share == 0.20
        assert p.primary_pass_rate_floor == 0.70


class TestCLISmoke:
    """End-to-end smoke against the auto-generated synthetic XERs in
    ``tests/fixtures/``. Pins the CLI argv contract + verifies the
    three output files actually land on disk."""

    def test_cli_runs_end_to_end(self, tmp_path: Path) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.calibration_harness",
                "--engine=lifecycle_phase",
                "--protocol=lifecycle_phase-w4-v1",
                "--fixtures=tests/fixtures",
                f"--output-dir={tmp_path}",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert (tmp_path / "lifecycle_phase-w4-v1_manifest.json").exists()
        assert (tmp_path / "lifecycle_phase-w4-v1_public.json").exists()
        assert (tmp_path / "lifecycle_phase-w4-v1_private.json").exists()
        public = json.loads((tmp_path / "lifecycle_phase-w4-v1_public.json").read_text())
        # Baseline schema expectations — pinning so a future refactor
        # that drops a key breaks loud, not silent.
        assert public["protocol_name"] == "lifecycle_phase-w4-v1"
        assert public["engine_name"] == "lifecycle_phase"
        assert "gate_evaluations_by_threshold" in public
        assert "0.80" in public["gate_evaluations_by_threshold"]

    def test_cli_requires_protocol_arg(self, tmp_path: Path) -> None:
        """W3 council finding (devils-advocate P1#2): the CLI must NOT
        default ``--protocol`` to a single engine's name. A future
        author who registers ``auto_grouping-v1`` and forgets the
        flag would otherwise run silently against the lifecycle_phase
        protocol — producing well-formed but meaningless gate numbers."""
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.calibration_harness",
                "--engine=lifecycle_phase",
                "--fixtures=tests/fixtures",
                f"--output-dir={tmp_path}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        # argparse exits with code 2 on missing required arg.
        assert proc.returncode == 2
        assert "--protocol" in proc.stderr

    def test_cli_unknown_engine_exits_2(self, tmp_path: Path) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.calibration_harness",
                "--engine=does-not-exist",
                "--protocol=lifecycle_phase-w4-v1",
                "--fixtures=tests/fixtures",
                f"--output-dir={tmp_path}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 2
        assert "not registered" in proc.stderr

    def test_cli_missing_fixtures_dir_exits_2(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nope"
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.calibration_harness",
                "--engine=lifecycle_phase",
                "--protocol=lifecycle_phase-w4-v1",
                f"--fixtures={nonexistent}",
                f"--output-dir={tmp_path}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 2


class TestObservationValidation:
    """W3 council finding (backend-reviewer + devils-advocate P1#1):
    out-of-range confidence MUST be rejected at the boundary so a
    buggy engine cannot silently inflate the gate via ``confidence > 1.0``
    bypassing both the threshold check (which uses ``or 0.0`` fallback)
    and the ``< 0.5`` honesty subset."""

    def test_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
            Observation(
                content_hash="h",
                program_key_hash=None,
                label="construction",
                confidence=1.7,
                parse_error=None,
            )

    def test_negative_confidence_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
            Observation(
                content_hash="h",
                program_key_hash=None,
                label="construction",
                confidence=-0.1,
                parse_error=None,
            )

    def test_none_confidence_allowed_for_parse_errors(self) -> None:
        # No exception — None is the parse-error sentinel.
        Observation(
            content_hash="h",
            program_key_hash=None,
            label=None,
            confidence=None,
            parse_error="ParseError",
        )

    def test_boundary_values_accepted(self) -> None:
        # 0.0 and 1.0 inclusive.
        Observation(
            content_hash="a",
            program_key_hash=None,
            label="construction",
            confidence=0.0,
            parse_error=None,
        )
        Observation(
            content_hash="b",
            program_key_hash=None,
            label="construction",
            confidence=1.0,
            parse_error=None,
        )


class TestEmptyGate:
    """W3 backend-reviewer test-gap: empty observations produce sane
    output (no division-by-zero, no crash, sensible failure mode)."""

    def test_empty_gate_produces_failed_evaluation_no_crash(self) -> None:
        result = evaluate_sub_gates([], _DEFAULT_PROTOCOL, 0.80, unknown_label="unknown")
        assert result["denominator"] == 0
        assert result["numerator"] == 0
        assert result["pass_rate"] == 0.0
        assert result["dominant_label_share_of_numerator"] == 0.0
        # §C trivially holds on empty (vacuous truth); §D fails (0 < 20%);
        # §E fails (0 < 70%); overall fails. The gate cannot pass on no
        # evidence — no calibration is not a passing calibration.
        assert result["overall_pass"] is False


class TestProtocolDriftPin:
    """W3 devils-advocate P1#3: protect against silent edits to the
    canonical W4 protocol parameters. A future PR that lowers
    ``confidence_honesty_min_share`` from 0.20 to 0.15 would otherwise
    pass the suite if the contributor also updates
    ``test_w4_protocol_matches_amendment_1``. This test pins a hash of
    the protocol's frozen field tuple — an edit forces an explicit
    Amendment-style ADR to update the expected hash, surfacing the
    drift in the diff."""

    def test_w4_protocol_field_hash_pinned(self) -> None:
        import hashlib

        p = get_protocol("lifecycle_phase-w4-v1")
        # Hash a canonicalised representation of the load-bearing
        # parameters. Excludes ``schema_version`` deliberately so a
        # bump to 2 (with shape change documented in an Amendment ADR)
        # doesn't trigger a spurious failure here.
        canon = (
            p.name,
            p.primary_threshold,
            p.additional_thresholds,
            p.confidence_histogram_edges,
            p.label_distribution_max_share,
            p.confidence_honesty_min_share,
            p.primary_pass_rate_floor,
        )
        digest = hashlib.sha256(repr(canon).encode("utf-8")).hexdigest()
        # If you're seeing this fail: the W4 protocol params have
        # changed. STOP. Author an Amendment-style ADR documenting
        # WHY the parameters are being changed (Amendment 1 §A says
        # the whole point of pre-registration is that you DON'T move
        # the goalposts mid-evaluation), then update the digest below.
        expected = "21c674c935682395d21ea7580f34536d64401f12753b5cab381e8b5ec70e7f23"
        assert digest == expected, (
            f"W4 protocol params changed. Old hash: {expected}, new: {digest}. "
            "Author an Amendment ADR before updating this digest."
        )


class TestRunCalibrationSchema:
    """The library entry point ``run_calibration`` returns a stable
    triple of payloads — pin the keys so callers integrating outside
    the CLI can rely on the shape without reverse-engineering."""

    def _stub_engine(self) -> object:
        class _Stub:
            engine_name = "stub"
            engine_version = "0.0.1"
            ruleset_version = "stub-v1"
            label_set = ("construction", "design", "unknown")
            unknown_label = "unknown"

            _idx = 0

            def parse_and_classify(self, fixture_path: Path) -> Observation:
                self._idx += 1
                return Observation(
                    content_hash=f"h{self._idx}",
                    program_key_hash=f"p{self._idx}",
                    label="construction",
                    confidence=0.85,
                    parse_error=None,
                    rules_fired=[],
                    metadata={"activity_count": 100, "last_recalc_date_iso": "2026-01"},
                )

            def dedup_key_priority(self, obs: Observation) -> tuple[object, ...]:
                return (
                    obs.metadata.get("activity_count", 0),
                    obs.metadata.get("last_recalc_date_iso") or "",
                )

        return _Stub()

    def test_outputs_have_three_payloads_with_required_keys(self, tmp_path: Path) -> None:
        # Fake fixture paths; the stub engine ignores them.
        fixtures = [tmp_path / f"f{i}.bin" for i in range(3)]
        for f in fixtures:
            f.write_bytes(b"")
        outs = run_calibration(self._stub_engine(), fixtures, _DEFAULT_PROTOCOL)
        # Manifest
        assert outs.manifest_payload["schema_version"] == _DEFAULT_PROTOCOL.schema_version
        assert outs.manifest_payload["protocol_name"] == _DEFAULT_PROTOCOL.name
        assert "gate_subset_content_hashes" in outs.manifest_payload
        # Public
        assert "counts" in outs.public_payload
        assert "gate_evaluations_by_threshold" in outs.public_payload
        assert "label_histogram_gate" in outs.public_payload
        # Private
        assert "observations" in outs.private_payload
        assert len(outs.private_payload["observations"]) == 3
