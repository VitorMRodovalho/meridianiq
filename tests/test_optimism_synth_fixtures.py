# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Regression + tamper-detection tests for the optimism_synth fixtures.

Source: Cycle 4 W3-C per ADR-0022 §"W3 fixture authoring + hash lock"
(HB-D). The W4 sub-gate C calibration depends on these fixtures NOT
being silently retuned between W3-close and W4 evaluation. These tests
guarantee:

1. **Determinism contract** — re-running the generator produces byte-
   identical fixtures matching the committed lock. CI catches drift
   from NumPy float-formatting changes, accidental edits, or seed-
   value tampering.
2. **Lock parity** — every committed fixture has a lock entry, and
   every lock entry has an on-disk fixture (no orphans, no dangling
   locked-but-missing files).
3. **Tamper detection** — modifying a single fixture byte triggers
   ``FixtureHashMismatch`` from ``verify_optimism_synth_hash_lock``,
   so W4 sub-gate C can reliably abort evaluation when fixtures drift.
4. **Engine compatibility** — all eight fixtures parse cleanly and
   produce CUSUM input (``np.diff(finish_days)``) that the engine's
   ``cusum_change_points`` consumes without raising.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

from src.analytics.revision_trends import cusum_change_points
from tools.calibration_harness import (
    FixtureHashMismatch,
    collapse_detection_clusters,
    evaluate_cusum_f1,
    parse_fixture_lock,
    verify_optimism_synth_hash_lock,
)
from tools.calibration_harness.fixtures.optimism_synth._generator import (
    CORNERS,
    regenerate_all,
)


_FIXTURES_DIR = (
    Path(__file__).parent.parent / "tools" / "calibration_harness" / "fixtures" / "optimism_synth"
)
_LOCK_PATH = _FIXTURES_DIR.parent / "optimism_synth.lock"

# Locked sub-gate C F1 for the 8 committed fixtures + the engine at
# revision_trends.py current state. DA exit-council P1 #1: ship F1
# alongside the fixture lock to close the metric-definition axis of the
# circular-tuning attack. If this number changes, EITHER the engine was
# bumped (legitimate — re-baseline + amend ADR-0022) OR fixtures drifted
# (the lock test catches that first). The literal value below is THE
# pre-registered W4 sub-gate C result against the current engine.
_LOCKED_SUB_GATE_C_F1: float = 0.769231

# Python-version provenance pin for the determinism contract. Issue #100
# item 2 / DA P2 #8 + backend-reviewer entry-council BLOCKING #2 on PR #111:
# json.dumps + numpy float-formatting are byte-stable WITHIN a Python minor
# version but may drift across versions. The committed
# `optimism_synth.lock` was authored under THIS interpreter version. When
# CI moves to a newer Python (e.g., 3.13 → 3.14), `test_generator_is_deterministic`
# is SKIPPED with a clear message rather than failing for a non-tampering
# reason. Operator ceremony on Python bump: re-run the generator on the
# new interpreter, verify the lock is still semantically correct, update
# this constant + the lock + the locked F1 baseline if needed.
_PYTHON_AUTHORED_AT: tuple[int, int] = (3, 12)


def test_eight_corner_fixtures_committed() -> None:
    """ADR-0022 spec: 8 corners of the 2³ design (σ × CP × baseline)."""
    assert len(CORNERS) == 8
    on_disk = sorted(p.name for p in _FIXTURES_DIR.glob("corner_*.json"))
    assert len(on_disk) == 8


def test_lock_file_present_and_parseable() -> None:
    locked = parse_fixture_lock(_LOCK_PATH)
    assert len(locked) == 8
    for name, sha in locked.items():
        assert name.startswith("corner_")
        assert name.endswith(".json")
        assert len(sha) == 64


def test_committed_fixtures_match_lock() -> None:
    """Regression: on-disk fixtures must match lock entries verbatim."""
    actual = verify_optimism_synth_hash_lock()
    assert len(actual) == 8


def test_generator_is_deterministic(tmp_path: Path) -> None:
    """Re-running the generator produces byte-identical fixtures.

    DA exit-council P1 #2: drives the generator entirely under
    ``tmp_path`` via parameterised ``regenerate_all(out_dir=, lock_path=)``,
    so a test crash cannot corrupt the live working tree.

    Catches NumPy float-formatting drift between minor versions, JSON
    library changes, or accidental edits to ``_generator.py`` that
    would silently change the locked content.

    Issue #100 item 2 / DA P2 #8 + backend-reviewer entry-council
    BLOCKING #2 on PR #111: skipped on Python interpreter versions
    other than the one the lock was authored on. Cross-Python json.dumps
    byte-stability is NOT guaranteed; a CI move to a newer Python would
    fail this test for a non-tampering reason. Skip + ceremony engages.
    """
    if sys.version_info[:2] != _PYTHON_AUTHORED_AT:
        pytest.skip(
            f"determinism lock authored on Python {_PYTHON_AUTHORED_AT[0]}.{_PYTHON_AUTHORED_AT[1]}; "
            f"runner is {sys.version_info.major}.{sys.version_info.minor}. "
            f"Cross-version json.dumps + numpy float-formatting byte-stability is not "
            f"guaranteed. Operator: re-run _generator.py on new Python + verify lock + "
            f"update _PYTHON_AUTHORED_AT."
        )
    expected_hashes = parse_fixture_lock(_LOCK_PATH)
    regenerated_hashes = regenerate_all(
        out_dir=tmp_path / "fixtures",
        lock_path=tmp_path / "optimism_synth.lock",
    )
    assert regenerated_hashes == expected_hashes, (
        "Generator drift: re-running _generator.py into tmp_path produced different hashes "
        "than the committed lock. Either NumPy/Python float formatting changed, or the "
        "generator was edited. Investigate before regenerating + relocking."
    )


def test_tamper_detection_on_byte_flip(tmp_path: Path) -> None:
    """Modifying a single fixture byte triggers FixtureHashMismatch.

    Simulates the exact scenario the lock is designed to detect:
    someone "improves" a fixture between W3-close and W4 evaluation.
    """
    # Mirror the committed fixtures + lock into a tmp dir.
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    for p in _FIXTURES_DIR.glob("corner_*.json"):
        shutil.copy2(p, work_dir / p.name)
    work_lock = tmp_path / "work.lock"
    shutil.copy2(_LOCK_PATH, work_lock)

    # Sanity: clean state verifies.
    verify_optimism_synth_hash_lock(fixtures_dir=work_dir, lock_path=work_lock)

    # Tamper: flip one character in the first fixture.
    target = work_dir / "corner_01.json"
    raw = target.read_text(encoding="utf-8")
    tampered = raw.replace("100.", "999.", 1)
    assert tampered != raw, "test setup: replace did not modify content"
    target.write_text(tampered, encoding="utf-8")

    with pytest.raises(FixtureHashMismatch, match="hash drift"):
        verify_optimism_synth_hash_lock(fixtures_dir=work_dir, lock_path=work_lock)


def test_tamper_detection_on_extra_file_within_legitimate_range(tmp_path: Path) -> None:
    """Adding an unlocked fixture WITHIN the legitimate filename range
    triggers FixtureHashMismatch.

    Catches the "I added a new corner without updating the lock" tampering
    pattern with a stronger filename: ``corner_05_v2.json`` is
    numerically WITHIN the {01..12} range that future fixture rotations
    might extend to, so the test cannot pass for the wrong reason if
    Cycle 5+ extends to 12 corners. Issue #100 item 4 / DA P2 #9 fix on
    PR #99: previous test planted ``corner_99.json`` which is
    out-of-range and would still pass at 12 corners by trivial
    numerical-bound check rather than by the intended "lock vs disk"
    invariant.
    """
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    for p in _FIXTURES_DIR.glob("corner_*.json"):
        shutil.copy2(p, work_dir / p.name)
    work_lock = tmp_path / "work.lock"
    shutil.copy2(_LOCK_PATH, work_lock)

    # Plant an extra corner using the v2-suffix attack (within numeric range
    # of legitimate corners but not in the lock). Filename: corner_05_v2.json.
    extra = work_dir / "corner_05_v2.json"
    extra.write_text(
        json.dumps({"fixture_id": "corner_05_v2", "schema_version": 1}), encoding="utf-8"
    )

    with pytest.raises(FixtureHashMismatch, match="missing_lock"):
        verify_optimism_synth_hash_lock(fixtures_dir=work_dir, lock_path=work_lock)


def test_tamper_detection_on_missing_file(tmp_path: Path) -> None:
    """Removing a locked fixture triggers FixtureHashMismatch.

    Catches a "I deleted a corner I didn't like" tampering pattern.
    """
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    for p in _FIXTURES_DIR.glob("corner_*.json"):
        shutil.copy2(p, work_dir / p.name)
    work_lock = tmp_path / "work.lock"
    shutil.copy2(_LOCK_PATH, work_lock)

    # Delete one corner.
    (work_dir / "corner_01.json").unlink()

    with pytest.raises(FixtureHashMismatch, match="missing_disk"):
        verify_optimism_synth_hash_lock(fixtures_dir=work_dir, lock_path=work_lock)


def test_each_fixture_consumable_by_engine_cusum() -> None:
    """All eight fixtures parse + run through the engine's CUSUM helper.

    Does NOT assert detection success — that is W4 sub-gate C territory.
    Asserts only that the fixture format is engine-compatible (no
    parse error, no exception inside ``cusum_change_points``).
    """
    for path in sorted(_FIXTURES_DIR.glob("corner_*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        finish_days = np.array(fixture["finish_days"], dtype=float)
        assert finish_days.size == 12, (
            f"{path.name}: expected N=12 revisions, got {finish_days.size}"
        )
        shifts = np.diff(finish_days)
        # Should not raise.
        result = cusum_change_points(shifts)
        # Result is a list of (index, cusum_value) tuples; can be empty
        # (engine correctly fails to detect under high-noise corners).
        assert isinstance(result, list)
        for idx, cusum_val in result:
            assert 0 <= idx < shifts.size
            assert isinstance(cusum_val, float)


def test_fixtures_have_complete_ground_truth() -> None:
    """Each fixture's ground truth is structurally complete for W4 F1 eval."""
    for path in sorted(_FIXTURES_DIR.glob("corner_*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        gt = fixture["ground_truth"]
        assert "regime_change_at_revision_index" in gt
        assert "tolerance_revisions" in gt
        cp = gt["regime_change_at_revision_index"]
        n = fixture["spec"]["n_revisions"]
        assert 0 < cp < n, f"{path.name}: CP={cp} must be in (0, {n})"
        assert gt["tolerance_revisions"] >= 0


def test_fixture_design_covers_orthogonal_corners() -> None:
    """The 8 corners cover the 2³ design space evenly.

    σ ∈ {0.1, 0.4} × CP ∈ {3, 7} × baseline ∈ {A, B}: every cell exactly once.
    Catches accidental duplication (e.g., two seeds for the same corner).
    """
    cells: set[tuple[float, int, str]] = set()
    for path in sorted(_FIXTURES_DIR.glob("corner_*.json")):
        f = json.loads(path.read_text(encoding="utf-8"))
        spec = f["spec"]
        cells.add(
            (spec["noise_sigma"], spec["ground_truth_cp_revision_index"], spec["baseline_pattern"])
        )
    expected = {
        (0.1, 3, "A"),
        (0.1, 7, "A"),
        (0.4, 3, "A"),
        (0.4, 7, "A"),
        (0.1, 3, "B"),
        (0.1, 7, "B"),
        (0.4, 3, "B"),
        (0.4, 7, "B"),
    }
    assert cells == expected


# --------------------------------------------------------------------------- #
# Sub-gate C F1 evaluator tests (DA P1 #1+#3 closure).
# --------------------------------------------------------------------------- #


def test_collapse_clusters_basic() -> None:
    assert collapse_detection_clusters([]) == []
    assert collapse_detection_clusters([5]) == [(5, 5)]
    assert collapse_detection_clusters([3, 4, 5, 6]) == [(3, 6)]
    # max_gap=1 → gap of 2 splits clusters.
    assert collapse_detection_clusters([3, 5, 8]) == [(3, 3), (5, 5), (8, 8)]
    # max_gap=2 collapses 3↔5 but not 5↔8.
    assert collapse_detection_clusters([3, 5, 8], max_gap=2) == [(3, 5), (8, 8)]
    assert collapse_detection_clusters([3, 4, 7, 8]) == [(3, 4), (7, 8)]


def test_collapse_clusters_handles_unsorted_input() -> None:
    assert collapse_detection_clusters([6, 3, 5, 4]) == [(3, 6)]


def test_evaluate_cusum_f1_perfect_match() -> None:
    """One detection cluster perfectly aligned with the truth → F1=1.0."""
    r = evaluate_cusum_f1(detections=[3, 4], ground_truths=[3])
    assert r.f1 == 1.0
    assert r.true_positives == 1
    assert r.false_positives == 0
    assert r.false_negatives == 0


def test_evaluate_cusum_f1_no_detections_with_truths() -> None:
    """Engine returns nothing — all FN, F1=0."""
    r = evaluate_cusum_f1(detections=[], ground_truths=[3])
    assert r.f1 == 0.0
    assert r.true_positives == 0
    assert r.false_positives == 0
    assert r.false_negatives == 1


def test_evaluate_cusum_f1_no_truths_no_detections() -> None:
    """Vacuous case — no truths AND no detections. F1=0 by spec."""
    r = evaluate_cusum_f1(detections=[], ground_truths=[])
    assert r.f1 == 0.0
    assert r.true_positives == 0


def test_evaluate_cusum_f1_only_false_positive() -> None:
    """Detection cluster nowhere near any truth → F1=0."""
    r = evaluate_cusum_f1(detections=[10, 11], ground_truths=[3])
    assert r.f1 == 0.0
    assert r.false_positives == 1
    assert r.false_negatives == 1


def test_evaluate_cusum_f1_tolerance_window_inclusive() -> None:
    """Cluster span [4, 8] with tolerance 1 covers truth 7."""
    r = evaluate_cusum_f1(detections=[4, 5, 6, 7, 8], ground_truths=[7], tolerance=1)
    assert r.true_positives == 1
    assert r.false_positives == 0
    assert r.f1 == 1.0


def test_evaluate_cusum_f1_locked_baseline_against_committed_fixtures() -> None:
    """LOCKED sub-gate C F1 against the 8 committed fixtures + engine.

    DA exit-council P1 #3: ship F1 metric definition alongside the
    fixture hash-lock so W4 evaluation cannot redefine F1 to produce
    its preferred outcome. This test PINS the expected F1 — any drift
    must be a legitimate engine bump (re-baseline + amend ADR-0022) or
    a fixture drift (caught earlier by the lock test).
    """
    all_detections: list[int] = []
    all_truths: list[int] = []
    truth_offset = 0
    for path in sorted(_FIXTURES_DIR.glob("corner_*.json")):
        fx = json.loads(path.read_text(encoding="utf-8"))
        finish_days = np.array(fx["finish_days"], dtype=float)
        shifts = np.diff(finish_days)
        # Engine convention: rev_index = idx + 1.
        detected = [idx + 1 for idx, _ in cusum_change_points(shifts)]
        # Offset each fixture's revision indices into a non-overlapping
        # range so cross-fixture coincidences cannot spuriously match
        # across corners.
        all_detections.extend(d + truth_offset for d in detected)
        all_truths.append(fx["ground_truth"]["regime_change_at_revision_index"] + truth_offset)
        truth_offset += 100

    result = evaluate_cusum_f1(detections=all_detections, ground_truths=all_truths, tolerance=1)
    assert abs(result.f1 - _LOCKED_SUB_GATE_C_F1) < 1e-3, (
        f"Sub-gate C F1 drift: got {result.f1}, locked {_LOCKED_SUB_GATE_C_F1}. "
        f"TP={result.true_positives} FP={result.false_positives} FN={result.false_negatives}. "
        "Either the engine changed (re-baseline + amend ADR-0022) or fixtures drifted "
        "(should have failed the lock test first)."
    )


def test_locked_f1_relationship_to_sub_gate_c_threshold() -> None:
    """Document whether the locked F1 passes ADR-0022 sub-gate C ≥ 0.75.

    A structural pin: if the locked F1 is ever rotated to a value
    below 0.75 (engine regression OR fixture-set toughening), this
    assertion catches the rotation and forces an explicit ADR
    update before the new path-A outcome lands silently.
    """
    assert _LOCKED_SUB_GATE_C_F1 >= 0.75, (
        f"Locked F1 {_LOCKED_SUB_GATE_C_F1} would fail sub-gate C threshold 0.75. "
        "If this is intentional (path-A activation expected), update ADR-0022 first "
        "and replace this assertion with the explicit < 0.75 expectation."
    )
