# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Cycle 4 W4 — pre-registered calibration gate for the ``revision_trends`` engine.

Implements the three sub-gate evaluators specified in
`ADR-0022 <../../../../docs/adr/0022-cycle-4-entry-beta-honest.md>`_
§"W4 — Pre-registered calibration gate" plus the heteroscedasticity-weight
pre-registration amended into
`ADR-0023 <../../../../docs/adr/0023-cycle-4-w4-outcome.md>`_.

Standards cited
---------------

- AACE RP 29R-03 §"Window analysis" — slope/CUSUM rationale (ADR-0022 §"W3").
- Brier (1950) "Verification of forecasts" — calibration metric for sub-gate B.
- Calibration literature convention: Brier ≤ 0.20 = "mediocre but informative"
  (vs ≈ 0.25 always-50% guess on binary outcomes; ≤ 0.10 well-calibrated).

Sub-gates
---------

* **A — corpus census** (operator-attested input → pass/fail).
* **B — heteroscedasticity-aware Brier** on calibration pairs.
* **C — change-point detection F1** on hash-locked synthetic fixtures.

Pre-registered LOCKED parameters (DO NOT EDIT — change requires an ADR amendment):

* A threshold: ``N≥30`` (ADR-0022 acknowledged "minimum-viable", NOT statistically
  powered; production deployment threshold N≥100-200 deferred to Cycle 5+).
* B threshold: ``Brier ≤ 0.20``.
* C threshold: ``F1 ≥ 0.75``.

Path-A activation per ADR-0022 §"Pre-committed path A fallback": any sub-gate
failure or precondition-skip activates path-A. Each path-A counts as 0.5 partial
credit toward the ≥7/9 graceful threshold.

CLI::

    python -m tools.calibration_harness.gates.revision_trends_w4 \\
        [--census-state PATH] \\
        [--calibration-pairs PATH] \\
        [--output-dir docs/calibration/]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np

from src.analytics.revision_trends import cusum_change_points
from tools.calibration_harness import (
    FixtureHashMismatch,
    evaluate_cusum_f1,
    verify_optimism_synth_hash_lock,
)


# --------------------------------------------------------------------------- #
# Locked thresholds (ADR-0022 §"W4 — Pre-registered calibration gate").
# --------------------------------------------------------------------------- #


_SUB_GATE_A_THRESHOLD: int = 30
"""ADR-0022 §"Sub-gate A — corpus census" lock."""

_SUB_GATE_B_THRESHOLD: float = 0.20
"""ADR-0022 §"Sub-gate B — Brier calibration" lock."""

_SUB_GATE_C_THRESHOLD: float = 0.75
"""ADR-0022 §"Sub-gate C — change-point detection F1" lock."""

_LOCKED_F1_BASELINE: float = 0.769231
"""Cycle 4 W3-C locked baseline F1 (PR #99); passes ≥ 0.75 with thin margin.

Documented for ADR-0023 cross-reference. Authoritative regression pin lives in
``tests/test_optimism_synth_fixtures.py::test_evaluate_cusum_f1_locked_baseline_against_committed_fixtures``.
"""

_GATE_SCHEMA_VERSION: int = 1
"""Bumped if the gate-output payload shape changes. Independent of the harness
``schema_version`` (``tools/calibration_harness/__init__.py:205``) so a future
bump on either side is unambiguous in the JSON output."""

_FIXTURE_OFFSET: int = 100
"""Per-fixture revision-index offset so cluster-collapse cannot bleed across
fixtures. Locked at W3-C baseline (matches
``tests/test_optimism_synth_fixtures.py::test_evaluate_cusum_f1_locked_baseline_against_committed_fixtures``);
changing requires re-locking the F1 baseline + ADR-0022 amendment."""

_ATTESTATION_RE = re.compile(r"(ADR-\d{4}|git@[a-f0-9]{7,40})")
"""Census ``attestation_source`` MUST contain a citation token shaped like
``ADR-NNNN`` or ``git@<sha>``. **This is FORMAT validation, NOT semantic
validation** — the regex does not check that the cited ADR actually exists in
``docs/adr/`` nor that the cited SHA is in ``git log``. A malicious or sloppy
operator can fabricate ``ADR-9999`` or ``git@deadbeef`` and pass. The
structural defense is the audit trail (operator commits the census; reviewer
verifies the citation in PR review). Cycle 5+ may upgrade to existence checks
if corpus assembly involves multiple operators (DA exit-council finding P1
#5)."""

_DEFAULT_FIXTURES_DIR: Path = Path(__file__).resolve().parent.parent / "fixtures" / "optimism_synth"
"""Locked production fixture path (W3-C). Tests override via ``tmp_path``."""


_DEFAULT_CENSUS_KWARGS: dict[str, Any] = {
    "n_total_multi_revision_programs": 4,
    "n_completed_with_outcome": 0,
    "n_with_consent_path": 0,
    "attestation_source": (
        "ADR-0009 W4 outcome record §Aggregate counts (4 multi-revision programs "
        "in 103-XER sandbox, 2026-04-19) + ADR-0022 §Honest disclosures #6 "
        "(corpus assembly is operator + LGPD-blocked)"
    ),
}
"""Embedded default census mirroring known empirical state at Cycle 4 W4
evaluation time. Operator override via ``--census-state PATH``."""


# --------------------------------------------------------------------------- #
# Sub-gate A — corpus census.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CorpusCensus:
    """Operator-attested census of the calibration corpus.

    Frozen because the W4 evaluation MUST NOT silently mutate inputs after the
    gate runs. Subset chain:
    ``n_with_consent_path ≤ n_completed_with_outcome ≤ n_total_multi_revision_programs``.

    The binding count (see :func:`evaluate_sub_gate_a`) is the tightest of the
    three — NOT just ``n_with_consent_path`` — to defend against a non-monotone
    operator entry that would silently widen the gate.

    ``attestation_source`` MUST cite an ADR number or git SHA per ADR-0022
    §"Honest disclosures" #6 provenance discipline.
    """

    n_total_multi_revision_programs: int
    n_completed_with_outcome: int
    n_with_consent_path: int
    attestation_source: str
    threshold: int = _SUB_GATE_A_THRESHOLD

    def __post_init__(self) -> None:
        if self.threshold != _SUB_GATE_A_THRESHOLD:
            raise ValueError(
                f"CorpusCensus.threshold must be {_SUB_GATE_A_THRESHOLD} "
                f"(ADR-0022 §'Sub-gate A' lock); got {self.threshold!r}. "
                "Changing this requires an ADR amendment."
            )
        for name, val in (
            ("n_total_multi_revision_programs", self.n_total_multi_revision_programs),
            ("n_completed_with_outcome", self.n_completed_with_outcome),
            ("n_with_consent_path", self.n_with_consent_path),
        ):
            if val < 0:
                raise ValueError(f"CorpusCensus.{name} must be ≥ 0; got {val!r}")
        if self.n_completed_with_outcome > self.n_total_multi_revision_programs:
            raise ValueError(
                f"CorpusCensus.n_completed_with_outcome "
                f"({self.n_completed_with_outcome}) cannot exceed "
                f"n_total_multi_revision_programs "
                f"({self.n_total_multi_revision_programs})."
            )
        if self.n_with_consent_path > self.n_completed_with_outcome:
            raise ValueError(
                f"CorpusCensus.n_with_consent_path ({self.n_with_consent_path}) "
                f"cannot exceed n_completed_with_outcome "
                f"({self.n_completed_with_outcome})."
            )
        stripped = self.attestation_source.strip()
        if len(stripped) < 16:
            raise ValueError(
                "CorpusCensus.attestation_source must be ≥ 16 chars after "
                f"strip(); got {len(stripped)}. Cite ADR-NNNN or git@SHA per "
                "ADR-0022 §'Honest disclosures' #6 provenance discipline."
            )
        if not _ATTESTATION_RE.search(stripped):
            preview = stripped[:60] + ("…" if len(stripped) > 60 else "")
            raise ValueError(
                "CorpusCensus.attestation_source must contain ADR-NNNN or "
                f"git@SHA citation token. Got: {preview!r}"
            )


@dataclass(frozen=True)
class SubGateAResult:
    n_total_multi_revision_programs: int
    n_completed_with_outcome: int
    n_with_consent_path: int
    threshold: int
    binding_count: int
    passed: bool
    attestation_source: str


def evaluate_sub_gate_a(census: CorpusCensus) -> SubGateAResult:
    """Sub-gate A: corpus census against ADR-0022 §"Sub-gate A" threshold N≥30.

    Honest framing per ADR-0022 §"Sub-gate A": this is a *minimum-viable
    demonstration threshold*, NOT statistically powered. Production deployment
    requires N≥100-200 (deferred to Cycle 5+ on corpus growth).

    Cites: ADR-0022 §"Sub-gate A — corpus census".
    """
    binding = min(
        census.n_total_multi_revision_programs,
        census.n_completed_with_outcome,
        census.n_with_consent_path,
    )
    return SubGateAResult(
        n_total_multi_revision_programs=census.n_total_multi_revision_programs,
        n_completed_with_outcome=census.n_completed_with_outcome,
        n_with_consent_path=census.n_with_consent_path,
        threshold=census.threshold,
        binding_count=binding,
        passed=binding >= census.threshold,
        attestation_source=census.attestation_source,
    )


# --------------------------------------------------------------------------- #
# Sub-gate B — heteroscedasticity-aware Brier.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CalibrationPair:
    """One ``(predicted, actual)`` pair for Brier evaluation.

    Continuous-Brier interpretation: ``predicted_optimism_factor`` and
    ``actual_outcome`` both in ``[0.0, 1.0]``; Brier = ``mean((p - a)^2)``,
    bounded ``[0, 1]``.

    Heteroscedasticity weighting per ADR-0023 §"Heteroscedasticity weight
    pre-registration": ``w_i = 1 / sqrt(horizon_i + 1)``. **The ``+1`` is a
    SIGNAL component**, not just numerical stability — it floors weight at
    horizon=0 (treating same-day forecasts as carrying 1-day-equivalent
    uncertainty rather than zero) and yields a `~30%` weight differential
    between horizon=0 and horizon=1. This is the "minimum-1-day measurement
    uncertainty" assumption, defensible per AACE RP 29R-03 §"Window analysis"
    (variance grows ``∝ √horizon`` from a non-zero baseline), but should be
    acknowledged as a tunable choice that Cycle 5+ may revise on corpus
    evidence. DA exit-council finding P0 #3 made the signal nature explicit.
    """

    predicted_optimism_factor: float
    actual_outcome: float
    horizon_days: int

    def __post_init__(self) -> None:
        for name, val in (
            ("predicted_optimism_factor", self.predicted_optimism_factor),
            ("actual_outcome", self.actual_outcome),
        ):
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"CalibrationPair.{name} must be in [0.0, 1.0]; got {val!r}")
        if self.horizon_days < 0:
            raise ValueError(f"CalibrationPair.horizon_days must be ≥ 0; got {self.horizon_days!r}")


_SubGateBStatus = Literal["pass", "fail", "skipped"]
_SubGateBSkipReason = Literal["sub_gate_a_failed", "no_calibration_pairs"]


@dataclass(frozen=True)
class SubGateBResult:
    status: _SubGateBStatus
    skipped_reason: _SubGateBSkipReason | None
    brier_score: float | None
    weighted_brier_score: float | None
    threshold: float
    n_pairs: int
    passed: bool

    def __post_init__(self) -> None:
        if self.threshold != _SUB_GATE_B_THRESHOLD:
            raise ValueError(
                f"SubGateBResult.threshold must be {_SUB_GATE_B_THRESHOLD} "
                f"(ADR-0022 §'Sub-gate B' lock); got {self.threshold!r}."
            )


def evaluate_sub_gate_b(
    pairs: Sequence[CalibrationPair],
    *,
    sub_gate_a_passed: bool,
) -> SubGateBResult:
    """Sub-gate B: heteroscedasticity-aware Brier ≤ 0.20.

    Returns ``status="skipped"`` if sub-gate A failed (insufficient corpus
    precondition) OR if pairs is empty. Path-A accounting per ADR-0022:
    each skipped/failed sub-gate counts as 0.5 partial credit; skipped-by-
    precondition is structurally distinct from skipped-by-empty-input.

    Cites: Brier (1950) "Verification of forecasts"; ADR-0022 §"Sub-gate B";
    ADR-0023 §"Heteroscedasticity weight pre-registration".
    """
    n = len(pairs)
    threshold = _SUB_GATE_B_THRESHOLD
    if not sub_gate_a_passed:
        return SubGateBResult(
            status="skipped",
            skipped_reason="sub_gate_a_failed",
            brier_score=None,
            weighted_brier_score=None,
            threshold=threshold,
            n_pairs=n,
            passed=False,
        )
    if n == 0:
        return SubGateBResult(
            status="skipped",
            skipped_reason="no_calibration_pairs",
            brier_score=None,
            weighted_brier_score=None,
            threshold=threshold,
            n_pairs=0,
            passed=False,
        )
    sq_errors = [(p.predicted_optimism_factor - p.actual_outcome) ** 2 for p in pairs]
    brier = sum(sq_errors) / n
    weights = [1.0 / math.sqrt(p.horizon_days + 1) for p in pairs]
    weight_sum = sum(weights)
    weighted_brier = sum(w * e for w, e in zip(weights, sq_errors, strict=True)) / weight_sum
    passed = weighted_brier <= threshold
    return SubGateBResult(
        status="pass" if passed else "fail",
        skipped_reason=None,
        brier_score=round(brier, 6),
        weighted_brier_score=round(weighted_brier, 6),
        threshold=threshold,
        n_pairs=n,
        passed=passed,
    )


# --------------------------------------------------------------------------- #
# Sub-gate C — F1 on hash-locked optimism_synth fixtures.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SubGateCResult:
    hash_lock_verified: bool
    hash_drift_error: str | None
    f1: float
    threshold: float
    n_fixtures: int
    n_detections_total: int
    n_ground_truths_total: int
    n_true_positives: int
    n_false_positives: int
    n_false_negatives: int
    precision: float
    recall: float
    passed: bool

    def __post_init__(self) -> None:
        if self.threshold != _SUB_GATE_C_THRESHOLD:
            raise ValueError(
                f"SubGateCResult.threshold must be {_SUB_GATE_C_THRESHOLD} "
                f"(ADR-0022 §'Sub-gate C' lock); got {self.threshold!r}."
            )


def evaluate_sub_gate_c(
    fixtures_dir: Path | None = None,
    lock_path: Path | None = None,
) -> SubGateCResult:
    """Sub-gate C: invoke W3-C primitives ``verify_optimism_synth_hash_lock`` +
    ``evaluate_cusum_f1`` against the 8 hash-locked synthetic fixtures.

    Truth-extraction contract (PIN per backend-reviewer entry-council):

    * Each fixture has ``ground_truth.regime_change_at_revision_index`` (single
      CP per fixture).
    * Per-fixture detection indices are shifted ``+1`` (diff-index → revision-
      index per the engine convention).
    * Each fixture's revision-indices are offset by ``+100 × fixture_position``
      so cluster collapse cannot bleed across fixtures.
    * Tolerance fixed at ``1`` (W3-C locked baseline).

    Locked baseline F1 = 0.769231 (PR #99). Threshold ≥ 0.75. Passes thin margin.

    On hash-lock drift: returns ``SubGateCResult`` with ``hash_lock_verified=False``
    and ``hash_drift_error`` populated; F1 not computed (would be evaluating
    against tampered fixtures). Path-A activates.

    Cites: ADR-0022 §"Sub-gate C — change-point detection F1"; W3-C PR #99
    (hash-lock + F1 metric code-lock per DA P1 #1+#3).
    """
    threshold = _SUB_GATE_C_THRESHOLD
    try:
        verify_optimism_synth_hash_lock(fixtures_dir=fixtures_dir, lock_path=lock_path)
    except (FixtureHashMismatch, FileNotFoundError, ValueError) as exc:
        return SubGateCResult(
            hash_lock_verified=False,
            hash_drift_error=f"{type(exc).__name__}: {exc}",
            f1=0.0,
            threshold=threshold,
            n_fixtures=0,
            n_detections_total=0,
            n_ground_truths_total=0,
            n_true_positives=0,
            n_false_positives=0,
            n_false_negatives=0,
            precision=0.0,
            recall=0.0,
            passed=False,
        )
    fdir = fixtures_dir or _DEFAULT_FIXTURES_DIR
    fixture_paths = sorted(fdir.glob("corner_*.json"))
    all_detections: list[int] = []
    all_truths: list[int] = []
    truth_offset = 0
    for path in fixture_paths:
        fx = json.loads(path.read_text(encoding="utf-8"))
        finish_days = np.array(fx["finish_days"], dtype=float)
        shifts: list[float] = np.diff(finish_days).tolist()
        detected = [idx + 1 for idx, _ in cusum_change_points(shifts)]
        all_detections.extend(d + truth_offset for d in detected)
        all_truths.append(int(fx["ground_truth"]["regime_change_at_revision_index"]) + truth_offset)
        truth_offset += _FIXTURE_OFFSET
    f1_result = evaluate_cusum_f1(
        detections=all_detections,
        ground_truths=all_truths,
        tolerance=1,
    )
    return SubGateCResult(
        hash_lock_verified=True,
        hash_drift_error=None,
        f1=f1_result.f1,
        threshold=threshold,
        n_fixtures=len(fixture_paths),
        n_detections_total=len(all_detections),
        n_ground_truths_total=len(all_truths),
        n_true_positives=f1_result.true_positives,
        n_false_positives=f1_result.false_positives,
        n_false_negatives=f1_result.false_negatives,
        precision=f1_result.precision,
        recall=f1_result.recall,
        passed=f1_result.f1 >= threshold,
    )


# --------------------------------------------------------------------------- #
# Aggregator + payloads.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class W4OutcomeRecord:
    sub_gate_a: SubGateAResult
    sub_gate_b: SubGateBResult
    sub_gate_c: SubGateCResult
    overall_pass: bool
    path_a_activated: bool
    path_a_reasons: tuple[str, ...]
    run_started_at: datetime
    gate_schema_version: int = _GATE_SCHEMA_VERSION


def run_revision_trends_w4(
    census: CorpusCensus,
    pairs: Sequence[CalibrationPair] = (),
    *,
    fixtures_dir: Path | None = None,
    lock_path: Path | None = None,
    now: Callable[[], datetime] | None = None,
) -> W4OutcomeRecord:
    """Run all three sub-gates and aggregate into a :class:`W4OutcomeRecord`.

    Path-A activation per ADR-0022 §"Pre-committed path A fallback": any
    sub-gate failure or precondition-skip activates path-A. Each path-A counts
    as 0.5 partial credit toward the ≥7/9 graceful threshold.
    """
    now_fn = now or (lambda: datetime.now(UTC))
    a = evaluate_sub_gate_a(census)
    b = evaluate_sub_gate_b(pairs, sub_gate_a_passed=a.passed)
    c = evaluate_sub_gate_c(fixtures_dir=fixtures_dir, lock_path=lock_path)
    overall_pass = a.passed and b.passed and c.passed
    reasons: list[str] = []
    if not a.passed:
        reasons.append(
            f"sub-gate A: corpus census below threshold "
            f"(binding={a.binding_count}, threshold={a.threshold})"
        )
    if b.status == "skipped":
        reasons.append(f"sub-gate B: skipped ({b.skipped_reason})")
    elif not b.passed:
        reasons.append(
            f"sub-gate B: weighted Brier {b.weighted_brier_score} > threshold {b.threshold}"
        )
    if not c.passed:
        if c.hash_drift_error:
            reasons.append(f"sub-gate C: hash-lock tampering — {c.hash_drift_error}")
        else:
            reasons.append(f"sub-gate C: F1 {c.f1:.6f} < threshold {c.threshold}")
    return W4OutcomeRecord(
        sub_gate_a=a,
        sub_gate_b=b,
        sub_gate_c=c,
        overall_pass=overall_pass,
        path_a_activated=bool(reasons),
        path_a_reasons=tuple(reasons),
        run_started_at=now_fn(),
    )


def build_payloads(
    record: W4OutcomeRecord,
    *,
    pairs: Sequence[CalibrationPair] = (),
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build ``(manifest, public, private)`` payloads from a W4OutcomeRecord.

    Public payload deliberately omits raw ``predicted_optimism_factor`` /
    ``actual_outcome`` pair vectors (program-identifying when joined with
    public fixture metadata) per backend-reviewer entry-council finding.
    Private payload contains the full pair vectors + per-fixture detail.
    """
    iso = record.run_started_at.isoformat()
    common: dict[str, Any] = {
        "gate_schema_version": record.gate_schema_version,
        "protocol_name": "revision_trends_w4",
        "engine_name": "revision_trends",
        "run_started_at": iso,
    }
    sub_gate_a_dict = asdict(record.sub_gate_a)
    sub_gate_b_dict = asdict(record.sub_gate_b)
    sub_gate_c_dict = asdict(record.sub_gate_c)

    public_payload: dict[str, Any] = {
        **common,
        "overall_pass": record.overall_pass,
        "path_a_activated": record.path_a_activated,
        "path_a_reasons": list(record.path_a_reasons),
        "sub_gate_a": sub_gate_a_dict,
        "sub_gate_b": sub_gate_b_dict,
        "sub_gate_c": sub_gate_c_dict,
    }

    manifest_payload: dict[str, Any] = {
        **common,
        "overall_pass": record.overall_pass,
        "path_a_activated": record.path_a_activated,
        "fixture_hash_lock_verified": record.sub_gate_c.hash_lock_verified,
        "fixture_n": record.sub_gate_c.n_fixtures,
        "census_attestation_source": record.sub_gate_a.attestation_source,
        "thresholds_locked": {
            "sub_gate_a": record.sub_gate_a.threshold,
            "sub_gate_b": record.sub_gate_b.threshold,
            "sub_gate_c": record.sub_gate_c.threshold,
        },
    }

    private_payload: dict[str, Any] = {
        **common,
        "outcome": public_payload,
        "calibration_pairs": [asdict(p) for p in pairs],
    }

    return manifest_payload, public_payload, private_payload


# --------------------------------------------------------------------------- #
# Census + pair loading.
# --------------------------------------------------------------------------- #


def default_census() -> CorpusCensus:
    """Embedded W4 census reflecting known empirical state at this commit."""
    return CorpusCensus(**_DEFAULT_CENSUS_KWARGS)


def load_census(path: Path) -> CorpusCensus:
    """Load a census from a JSON file. Same ``__post_init__`` validation chain
    as the embedded default — no second validation source."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"census JSON must be a dict; got {type(raw).__name__}")
    raw_d = cast(dict[str, Any], raw)
    return CorpusCensus(
        n_total_multi_revision_programs=int(raw_d["n_total_multi_revision_programs"]),
        n_completed_with_outcome=int(raw_d["n_completed_with_outcome"]),
        n_with_consent_path=int(raw_d["n_with_consent_path"]),
        attestation_source=str(raw_d["attestation_source"]),
    )


def load_calibration_pairs(path: Path) -> list[CalibrationPair]:
    """Load calibration pairs from JSON. Each entry must have all 3 fields."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"calibration pairs JSON must be a list; got {type(raw).__name__}")
    raw_list = cast(list[dict[str, Any]], raw)
    return [
        CalibrationPair(
            predicted_optimism_factor=float(item["predicted_optimism_factor"]),
            actual_outcome=float(item["actual_outcome"]),
            horizon_days=int(item["horizon_days"]),
        )
        for item in raw_list
    ]


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #


def _cli(argv: list[str] | None = None) -> int:
    # NOTE: ``.claude/rules/backend.md`` requires "no print()" in application
    # code. CLI tools are the documented exception (operator-facing stdout) —
    # mirrors the existing harness CLI ``tools/calibration_harness/__init__.py::_cli``.
    parser = argparse.ArgumentParser(
        prog="python -m tools.calibration_harness.gates.revision_trends_w4",
        description=(
            "Run Cycle 4 W4 pre-registered calibration gate (sub-gates A/B/C) "
            "per ADR-0022 §'W4 — Pre-registered calibration gate'."
        ),
    )
    parser.add_argument(
        "--census-state",
        type=Path,
        default=None,
        help=(
            "JSON file with operator-attested corpus census. Default: "
            "embedded census mirroring ADR-0009 W4 outcome record."
        ),
    )
    parser.add_argument(
        "--calibration-pairs",
        type=Path,
        default=None,
        help=(
            "JSON file with calibration pairs for sub-gate B. Default: "
            "empty list (sub-gate B skipped)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/calibration"),
        help="Where to write manifest/public/private payloads.",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=None,
        help=("Override fixture directory (testing only — production = locked W3-C path)."),
    )
    parser.add_argument(
        "--lock-path",
        type=Path,
        default=None,
        help=("Override lock file path (testing only — production = locked W3-C path)."),
    )
    parser.add_argument(
        "--run-started-at",
        type=str,
        default=None,
        help=(
            "Override the run_started_at ISO-8601 timestamp for byte-identical "
            "reproducibility of committed JSONs (DA exit-council P1 #4). "
            "Default: wall-clock UTC. Example: 2026-05-09T18:00:00+00:00. "
            "MUST include a timezone offset; naive datetimes are rejected."
        ),
    )
    args = parser.parse_args(argv)

    census = load_census(args.census_state) if args.census_state is not None else default_census()
    pairs: list[CalibrationPair] = (
        load_calibration_pairs(args.calibration_pairs) if args.calibration_pairs is not None else []
    )
    now_fn: Callable[[], datetime] | None = None
    if args.run_started_at is not None:
        fixed_dt = datetime.fromisoformat(args.run_started_at)
        if fixed_dt.tzinfo is None:
            raise ValueError(
                "--run-started-at must include a timezone offset (e.g. '+00:00'); "
                "got naive datetime."
            )
        now_fn = lambda: fixed_dt  # noqa: E731  (lambda intentional for one-shot injection)
    record = run_revision_trends_w4(
        census,
        pairs,
        fixtures_dir=args.fixtures_dir,
        lock_path=args.lock_path,
        now=now_fn,
    )
    manifest, public, private = build_payloads(record, pairs=pairs)

    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "revision_trends_w4_manifest.json"
    public_path = out_dir / "revision_trends_w4_public.json"
    private_path = out_dir / "revision_trends_w4_private.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    public_path.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    private_path.write_text(json.dumps(private, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"W4 calibration gate @ {public['run_started_at']}")
    print(f"  overall_pass: {record.overall_pass}")
    print(f"  path_a_activated: {record.path_a_activated}")
    if record.path_a_reasons:
        print("  path_a_reasons:")
        for r in record.path_a_reasons:
            print(f"    - {r}")
    print(
        f"  sub-gate A: passed={record.sub_gate_a.passed} "
        f"binding={record.sub_gate_a.binding_count}/"
        f"{record.sub_gate_a.threshold}"
    )
    print(f"  sub-gate B: status={record.sub_gate_b.status} passed={record.sub_gate_b.passed}")
    if record.sub_gate_b.weighted_brier_score is not None:
        print(
            f"    weighted_brier={record.sub_gate_b.weighted_brier_score} "
            f"unweighted={record.sub_gate_b.brier_score} "
            f"threshold={record.sub_gate_b.threshold}"
        )
    print(
        f"  sub-gate C: passed={record.sub_gate_c.passed} "
        f"f1={record.sub_gate_c.f1} threshold={record.sub_gate_c.threshold}"
    )
    print("Written:")
    print(f"  {manifest_path}")
    print(f"  {public_path}")
    print(f"  {private_path}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
