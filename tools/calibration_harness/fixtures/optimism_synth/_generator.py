# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Deterministic generator for the optimism_synth fixture set (W3-C).

Authored 2026-05-09 per ADR-0022 §"W3 fixture authoring + hash lock"
(HB-D — moved from W4 to W3 close to prevent circular tuning).

Spec (ADR-0022):
    8 synthetic schedule-revision sequences with planted regime changes.
    σ ∈ {0.1, 0.4} × CP ∈ {3, 7} × baseline ∈ {A, B} = 2³ = 8 corners.
    (Middle σ=0.2 + CP=5 cells dropped — corner design captures main
    effects + interactions for sub-gate C F1 evaluation.)

Ground truth:
    Each fixture plants ONE regime-change at revision_index ∈ {3, 7}.
    W4 sub-gate C evaluates CUSUM-detected change-points against this
    ground truth using F1 (precision × recall harmonic mean).

Output:
    Eight ``corner_NN.json`` files in this directory plus the
    ``../optimism_synth.lock`` SHA-256 hash-lock.

Determinism contract:
    Each fixture uses a per-corner seeded ``numpy.random.RandomState``.
    Re-running this generator MUST produce byte-identical files; the
    lock validates that contract. Drift = a tampered fixture set —
    W4 evaluation aborts and ADR-0023 documents the tampering.

Usage (developer-only, NOT a CI step):
    python tools/calibration_harness/fixtures/optimism_synth/_generator.py

    Re-runs the whole set + writes the .lock. Should be run ONCE at W3
    close. Re-running afterwards (e.g., to "improve" a fixture) is the
    explicit anti-pattern this hash-lock is designed to detect.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


_SCHEMA_VERSION = 1
# N=12 chosen to give CUSUM enough post-CP shifts to accumulate at CP=7
# (5 post-CP shifts with N=12 vs 1 with N=8 — engine's
# _MIN_REVISIONS_FOR_CUSUM=5 effectively requires >=4 shifts).
_N_REVISIONS = 12
_BASELINE_FINISH_DAYS = 100.0
_NOISE_DAYS_PER_SIGMA = 10.0  # σ=0.1 → std=1 day, σ=0.4 → std=4 days

# Pre-CP and post-CP per-revision drift rates (days/revision).
# CUSUM-on-shifts (revision_trends.cusum_change_points) detects SUSTAINED
# drift-rate changes, NOT single-jump outliers. Pattern A: stable→drift;
# Pattern B: slow_drift→fast_drift. The post-CP drift rate of +5 days/rev
# sustained over the post-CP plateau gives a CUSUM signal of
# (5 − pre_rate) × post_cp_count vs noise std, which exceeds the 3σ gate
# even at σ=0.4 with N=8 revisions. Hand-verified at W3-C generation time
# against ``revision_trends.cusum_change_points`` (line 289).
_PATTERN_DRIFT_RATES: dict[str, dict[str, float]] = {
    "A": {"pre_cp_rate": 0.0, "post_cp_rate": 5.0},  # stable → drift
    "B": {"pre_cp_rate": 1.0, "post_cp_rate": 5.0},  # slow drift → fast drift
}

_HERE = Path(__file__).parent
_LOCK_PATH = _HERE.parent / "optimism_synth.lock"

# 8 corners of the 2³ design (DA P2 #5 — middle-cell {σ=0.2, CP=5} dropped
# per fractional-factorial corner design; main effects + interactions
# captured at the corners). N=12 (DA P3 #14) chosen so CP=7 has 5 post-CP
# shifts vs the engine's _MIN_REVISIONS_FOR_CUSUM=5 floor.
CORNERS: tuple[dict[str, object], ...] = (
    {"id": "corner_01", "noise_sigma": 0.1, "cp": 3, "baseline": "A", "seed": 142},
    {"id": "corner_02", "noise_sigma": 0.1, "cp": 7, "baseline": "A", "seed": 242},
    {"id": "corner_03", "noise_sigma": 0.4, "cp": 3, "baseline": "A", "seed": 342},
    {"id": "corner_04", "noise_sigma": 0.4, "cp": 7, "baseline": "A", "seed": 442},
    {"id": "corner_05", "noise_sigma": 0.1, "cp": 3, "baseline": "B", "seed": 542},
    {"id": "corner_06", "noise_sigma": 0.1, "cp": 7, "baseline": "B", "seed": 642},
    {"id": "corner_07", "noise_sigma": 0.4, "cp": 3, "baseline": "B", "seed": 742},
    {"id": "corner_08", "noise_sigma": 0.4, "cp": 7, "baseline": "B", "seed": 842},
)
# Backwards-compat alias — internal tests imported `_CORNERS` before
# DA P2 #10 promoted the symbol to public. Removing the alias is OK
# once no caller in `tests/` references it.
_CORNERS = CORNERS


def _generate_finish_days(
    *,
    n_revisions: int,
    cp_index: int,
    sigma: float,
    baseline: str,
    seed: int,
) -> list[float]:
    """Generate a synthetic finish_days sequence with a planted drift-rate
    change at ``cp_index``.

    finish_days[i] = baseline + cumulative_drift(i) + gaussian_noise(i)

    cumulative_drift jumps from ``pre_cp_rate * i`` to ``post_cp_rate``
    starting at ``cp_index``. CUSUM-on-shifts (np.diff(finish_days))
    detects this as a regime change because the SHIFTS sequence mean
    shifts from ``pre_cp_rate`` to ``post_cp_rate`` at the CP — exactly
    what the engine's CUSUM is designed to catch.
    """
    rates = _PATTERN_DRIFT_RATES.get(baseline)
    if rates is None:
        raise ValueError(f"unknown baseline pattern {baseline!r}")
    # DA P2 #7: ``np.random.default_rng`` (PCG64) replaces the legacy
    # ``RandomState`` (MT19937). Single ceremony cost paid here so the
    # lock provenance survives NumPy's eventual ``RandomState``
    # deprecation. PCG64 is byte-stable across NumPy 2.x at minimum
    # per the SeedSequence contract.
    rng = np.random.default_rng(seed)
    noise_std = sigma * _NOISE_DAYS_PER_SIGMA
    noise = rng.normal(loc=0.0, scale=noise_std, size=n_revisions)
    pre_rate = rates["pre_cp_rate"]
    post_rate = rates["post_cp_rate"]
    out: list[float] = []
    cumulative = 0.0
    for i in range(n_revisions):
        # Drift accrues per-revision: pre-CP at pre_rate, post-CP at post_rate.
        if i > 0:
            rate = pre_rate if (i - 1) < cp_index else post_rate
            cumulative += rate
        # Round to 4 decimals so the JSON is byte-stable across NumPy
        # minor-version float-formatting drift.
        out.append(round(_BASELINE_FINISH_DAYS + cumulative + float(noise[i]), 4))
    return out


def _build_fixture(corner: dict[str, object]) -> dict[str, object]:
    cp = int(corner["cp"])
    baseline = str(corner["baseline"])
    sigma = float(corner["noise_sigma"])
    seed = int(corner["seed"])
    finish_days = _generate_finish_days(
        n_revisions=_N_REVISIONS,
        cp_index=cp,
        sigma=sigma,
        baseline=baseline,
        seed=seed,
    )
    return {
        "fixture_id": corner["id"],
        "schema_version": _SCHEMA_VERSION,
        "spec": {
            "noise_sigma": sigma,
            "ground_truth_cp_revision_index": cp,
            "baseline_pattern": baseline,
            "n_revisions": _N_REVISIONS,
            "seed": seed,
        },
        "ground_truth": {
            "regime_change_at_revision_index": cp,
            "tolerance_revisions": 1,
        },
        "finish_days": finish_days,
    }


def _serialize(fixture: dict[str, object]) -> bytes:
    """Stable JSON serialization for hash-lock determinism."""
    return json.dumps(fixture, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regenerate_all(
    out_dir: Path | None = None,
    lock_path: Path | None = None,
) -> dict[str, str]:
    """Generate every fixture + write the lock. Returns filename → sha256.

    Parameterised paths (DA P1 #2) so tests can drive the generator
    entirely under ``tmp_path`` without touching the live working tree.
    Defaults to the committed fixture tree paths.
    """
    odir = out_dir or _HERE
    lpath = lock_path or _LOCK_PATH
    odir.mkdir(parents=True, exist_ok=True)

    hashes: dict[str, str] = {}
    for corner in CORNERS:
        fixture = _build_fixture(corner)
        path = odir / f"{corner['id']}.json"
        data = _serialize(fixture)
        path.write_bytes(data)
        hashes[path.name] = _sha256(data)

    lock_lines = [
        "# optimism_synth fixture hash-lock (W3-C, ADR-0022 HB-D)",
        "# DO NOT EDIT BY HAND — re-run _generator.py to refresh.",
        "# W4 sub-gate C aborts if any hash here drifts from the on-disk fixture.",
        "# Format: <sha256_hex>  <filename>. NOT sha256sum-compatible (comments).",
        "# Verify via tools.calibration_harness.verify_optimism_synth_hash_lock().",
        f"# schema_version = {_SCHEMA_VERSION}",
        "",
    ]
    for name in sorted(hashes):
        lock_lines.append(f"{hashes[name]}  {name}")
    lock_lines.append("")
    lpath.write_text("\n".join(lock_lines), encoding="utf-8")
    return hashes


def _cli_main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m tools.calibration_harness.fixtures.optimism_synth._generator",
        description=(
            "Regenerate the optimism_synth fixture set + lock. "
            "REQUIRES --force when the lock already exists — regen is a "
            "deliberate W3-close ceremony, not an idempotent dev step."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Required when the lock already exists. Re-running silently is the W3-C anti-pattern.",
    )
    args = parser.parse_args()
    if _LOCK_PATH.exists() and not args.force:
        print(
            f"refusing to overwrite existing lock at {_LOCK_PATH}.\n"
            "Pass --force to regenerate (this is a deliberate ceremony, not idempotent).",
        )
        return 1
    hashes = regenerate_all()
    for name in sorted(hashes):
        print(f"{hashes[name]}  {name}")
    print(f"# lock: {_LOCK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())
