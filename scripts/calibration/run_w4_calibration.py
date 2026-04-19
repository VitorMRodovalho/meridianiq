# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""MeridianIQ Wave 4 calibration harness (Cycle 1 v4.0 — ADR-0009 Amendment 1).

Reads XERs from ``$XER_SANDBOX_DIR``, applies the pre-registered dedup rule
to split the corpus into a gate subset (one representative per program) and
a hysteresis subset (serial updates preserved), runs the W3 lifecycle_phase
inference engine against every XER, and emits three files:

- ``/tmp/w4_manifest.json``              — hash-only dedup manifest
- ``/tmp/w4_calibration_public.json``    — coarse-banded aggregates safe for
                                           the public calibration issue
- ``/tmp/w4_calibration_private.json``   — per-observation detail, local only
                                           (gitignored, never committed)

No filenames, project identifiers, or raw rationale text ever enter the
output — content is keyed by sha256 hash of the XER bytes and a truncated
hash of the `proj_short_name` program key.

Pre-registered dedup rule (ADR-0009 Amendment 1 §A):
  For each program group (keyed by ``projects[0].proj_short_name``), keep
  the revision with the largest ``len(activities)``; tie-break by most-recent
  ``last_recalc_date``. Programs with a single revision are always in the
  gate subset.

Pre-registered gate criteria (ADR-0009 Amendment 1):
  §B unknown denominator  — ``unknown`` counts in denominator, never numerator
  §C phase distribution   — no single phase > 60% of numerator passes
  §D confidence honesty   — >=20% of gate subset at confidence < 0.5
  §E primary threshold    — 0.80 retained formally; 0.70 and 0.60 also recorded

Usage::

    XER_SANDBOX_DIR=/abs/path python3 -m scripts.calibration.run_w4_calibration

Any non-zero exit code means the harness itself failed (missing env var,
unreadable dir, parse crash). The gate pass/fail outcome is in the emitted
JSON, not in the exit code — the gate decision is a human-synthesised
Amendment 2 concern, not an automated CI gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.analytics.lifecycle_phase import ENGINE_NAME, RULESET_VERSION, infer_lifecycle_phase
from src.analytics.lifecycle_types import LIFECYCLE_PHASES
from src.parser.models import ParsedSchedule
from src.parser.xer_reader import XERReader

PRIMARY_THRESHOLD: float = 0.80
ADDITIONAL_THRESHOLDS: tuple[float, ...] = (0.70, 0.60)
CONFIDENCE_HISTOGRAM_EDGES: tuple[float, ...] = (0.0, 0.5, 0.7, 0.8, 1.0)
PHASE_DISTRIBUTION_MAX_SHARE: float = 0.60  # §C — no single phase > 60% numerator
CONFIDENCE_HONESTY_MIN_SHARE: float = 0.20  # §D — >=20% at confidence < 0.5

MANIFEST_OUT = Path("/tmp/w4_manifest.json")
PUBLIC_OUT = Path("/tmp/w4_calibration_public.json")
PRIVATE_OUT = Path("/tmp/w4_calibration_private.json")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _program_key(schedule: ParsedSchedule) -> str:
    if not schedule.projects:
        return "__no_project__"
    p = schedule.projects[0]
    return (p.proj_short_name or p.proj_id or "__unknown__").strip().upper()


def _program_key_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _last_recalc_iso(schedule: ParsedSchedule) -> str | None:
    if not schedule.projects:
        return None
    d = schedule.projects[0].last_recalc_date
    return d.isoformat() if d else None


def _bucket_confidence(c: float | None) -> str:
    if c is None:
        return "__missing__"
    for i in range(len(CONFIDENCE_HISTOGRAM_EDGES) - 1):
        lo, hi = CONFIDENCE_HISTOGRAM_EDGES[i], CONFIDENCE_HISTOGRAM_EDGES[i + 1]
        # Last bucket is inclusive of the upper bound.
        if lo <= c < hi or (i == len(CONFIDENCE_HISTOGRAM_EDGES) - 2 and c == hi):
            return f"[{lo:.2f},{hi:.2f})" if i < len(CONFIDENCE_HISTOGRAM_EDGES) - 2 else f"[{lo:.2f},{hi:.2f}]"
    return "__out_of_range__"


def _parse_and_classify(path: Path) -> dict[str, Any]:
    content_hash = _sha256(path)
    try:
        schedule = XERReader(str(path)).parse()
    except Exception as exc:
        return {
            "content_hash": content_hash,
            "parse_error": type(exc).__name__,
            "program_key_hash": None,
            "activity_count": 0,
            "last_recalc_date_iso": None,
            "phase": None,
            "confidence": None,
            "rules_fired": [],
        }
    key = _program_key(schedule)
    key_hash = _program_key_hash(key)
    activity_count = len(schedule.activities) if schedule.activities else 0
    recalc_iso = _last_recalc_iso(schedule)
    result = infer_lifecycle_phase(schedule)
    rules_fired = list(result.rationale.get("rules_fired", [])) if isinstance(result.rationale, dict) else []
    return {
        "content_hash": content_hash,
        "parse_error": None,
        "program_key_hash": key_hash,
        "activity_count": activity_count,
        "last_recalc_date_iso": recalc_iso,
        "phase": result.phase,
        "confidence": float(result.confidence),
        "rules_fired": rules_fired,
    }


def _split_gate_and_hysteresis(
    observations: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obs in observations:
        if obs["parse_error"] is not None:
            continue
        groups[obs["program_key_hash"]].append(obs)
    gate: list[str] = []
    hysteresis: list[str] = []
    for _, members in groups.items():
        if len(members) == 1:
            gate.append(members[0]["content_hash"])
            continue
        # ADR-0009 Amendment 1 §A: largest activity_count; tie-break most-recent recalc_date.
        best = max(
            members,
            key=lambda m: (m["activity_count"], m["last_recalc_date_iso"] or ""),
        )
        gate.append(best["content_hash"])
        for m in members:
            if m["content_hash"] != best["content_hash"]:
                hysteresis.append(m["content_hash"])
    return sorted(gate), sorted(hysteresis)


def _compute_gate_summary(
    gate_obs: list[dict[str, Any]],
    threshold: float,
) -> dict[str, Any]:
    """§B + §C + §D evaluation at one confidence threshold."""
    n = len(gate_obs)
    # §B — unknown counts in denominator but never in numerator.
    pass_obs = [o for o in gate_obs if o["phase"] != "unknown" and (o["confidence"] or 0.0) >= threshold]
    numerator_phase_counts = Counter(o["phase"] for o in pass_obs)
    pass_rate = len(pass_obs) / n if n else 0.0
    # §C — no single phase > PHASE_DISTRIBUTION_MAX_SHARE of numerator.
    dominant_phase_share = (
        max(numerator_phase_counts.values()) / len(pass_obs) if pass_obs else 0.0
    )
    phase_distribution_ok = dominant_phase_share <= PHASE_DISTRIBUTION_MAX_SHARE or not pass_obs
    # §D — >=20% at confidence < 0.5.
    low_conf_count = sum(1 for o in gate_obs if (o["confidence"] or 0.0) < 0.5)
    low_conf_share = low_conf_count / n if n else 0.0
    confidence_honesty_ok = low_conf_share >= CONFIDENCE_HONESTY_MIN_SHARE
    # Primary gate criterion (§E): ≥70% pass rate.
    primary_pass_rate_ok = pass_rate >= 0.70
    overall_pass = primary_pass_rate_ok and phase_distribution_ok and confidence_honesty_ok
    return {
        "threshold": threshold,
        "denominator": n,
        "numerator": len(pass_obs),
        "pass_rate": round(pass_rate, 4),
        "dominant_phase_share_of_numerator": round(dominant_phase_share, 4),
        "phase_distribution_sub_gate_ok": phase_distribution_ok,
        "low_confidence_share": round(low_conf_share, 4),
        "confidence_honesty_sub_gate_ok": confidence_honesty_ok,
        "primary_pass_rate_ok": primary_pass_rate_ok,
        "overall_pass": overall_pass,
        "numerator_phase_counts": dict(numerator_phase_counts),
    }


def _hysteresis_report(
    observations: list[dict[str, Any]],
    hysteresis_hashes: set[str],
    gate_hashes: set[str],
) -> dict[str, Any]:
    """Per-program flip-flop report across preserved serial revisions.

    For each program that has multiple observations (gate + hysteresis
    members), emit the sequence of (phase, confidence) ordered by
    ``last_recalc_date_iso`` ascending. Count flips as any consecutive
    disagreement in phase OR confidence-band change.
    """
    by_program: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obs in observations:
        if obs["parse_error"] is not None:
            continue
        if obs["content_hash"] in hysteresis_hashes or obs["content_hash"] in gate_hashes:
            by_program[obs["program_key_hash"]].append(obs)
    multi_revision_programs = 0
    total_flip_flops = 0
    phase_flips = 0
    for _, members in by_program.items():
        if len(members) < 2:
            continue
        multi_revision_programs += 1
        ordered = sorted(members, key=lambda m: m["last_recalc_date_iso"] or "")
        for prev, curr in zip(ordered, ordered[1:]):
            if prev["phase"] != curr["phase"]:
                phase_flips += 1
            # Any confidence band crossing at 0.5 or 0.8 counts as a flip.
            pc, cc = prev["confidence"] or 0.0, curr["confidence"] or 0.0
            for edge in (0.5, 0.8):
                if (pc < edge and cc >= edge) or (pc >= edge and cc < edge):
                    total_flip_flops += 1
                    break
    return {
        "multi_revision_programs": multi_revision_programs,
        "phase_flips_across_revisions": phase_flips,
        "confidence_band_flips_across_revisions": total_flip_flops,
    }


def _phase_histogram(observations: list[dict[str, Any]]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for phase in LIFECYCLE_PHASES:
        c[phase] = 0
    for obs in observations:
        if obs["parse_error"] is not None:
            continue
        if obs["phase"] in LIFECYCLE_PHASES:
            c[obs["phase"]] += 1
    return dict(c)


def _confidence_histogram(observations: list[dict[str, Any]]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for obs in observations:
        if obs["parse_error"] is not None:
            continue
        c[_bucket_confidence(obs["confidence"])] += 1
    return dict(c)


def main(argv: list[str] | None = None) -> int:
    sandbox = os.environ.get("XER_SANDBOX_DIR")
    if not sandbox:
        print("ERROR: XER_SANDBOX_DIR environment variable is required.", file=sys.stderr)
        return 2
    sandbox_path = Path(sandbox)
    if not sandbox_path.is_dir():
        print("ERROR: XER_SANDBOX_DIR is not a directory.", file=sys.stderr)
        return 2
    xer_paths = sorted(sandbox_path.glob("*.xer"))
    if not xer_paths:
        print("ERROR: no *.xer files under XER_SANDBOX_DIR.", file=sys.stderr)
        return 2

    run_started_at = datetime.now(UTC).isoformat()
    observations = [_parse_and_classify(p) for p in xer_paths]
    parse_failures = sum(1 for o in observations if o["parse_error"] is not None)
    gate_hashes, hysteresis_hashes = _split_gate_and_hysteresis(observations)
    gate_set, hyst_set = set(gate_hashes), set(hysteresis_hashes)
    gate_obs = [o for o in observations if o["content_hash"] in gate_set]
    hysteresis_obs = [o for o in observations if o["content_hash"] in hyst_set]

    thresholds = (PRIMARY_THRESHOLD, *ADDITIONAL_THRESHOLDS)
    gate_evaluations = {
        f"{t:.2f}": _compute_gate_summary(gate_obs, t) for t in thresholds
    }

    # ------------------------- public aggregates -------------------------
    public_payload: dict[str, Any] = {
        "schema_version": 1,
        "engine_name": ENGINE_NAME,
        "engine_version": "4.0",
        "ruleset_version": RULESET_VERSION,
        "run_started_at": run_started_at,
        "counts": {
            "total_xers_found": len(xer_paths),
            "parse_failures": parse_failures,
            "gate_subset": len(gate_obs),
            "hysteresis_subset": len(hysteresis_obs),
        },
        "phase_histogram_all": _phase_histogram(observations),
        "phase_histogram_gate": _phase_histogram(gate_obs),
        "confidence_histogram_gate": _confidence_histogram(gate_obs),
        "gate_evaluations_by_threshold": gate_evaluations,
        "hysteresis_report_gate_plus_hysteresis": _hysteresis_report(
            observations, hyst_set, gate_set
        ),
    }
    PUBLIC_OUT.write_text(json.dumps(public_payload, indent=2, sort_keys=True))

    # --------------------------- manifest --------------------------------
    manifest_payload: dict[str, Any] = {
        "schema_version": 1,
        "run_started_at": run_started_at,
        "engine_version": "4.0",
        "ruleset_version": RULESET_VERSION,
        "dedup_rule": "Amendment 1 §A: max(activity_count); tie max(last_recalc_date_iso)",
        "gate_subset_content_hashes": gate_hashes,
        "hysteresis_subset_content_hashes": hysteresis_hashes,
        "parse_failed_content_hashes": sorted(
            o["content_hash"] for o in observations if o["parse_error"] is not None
        ),
    }
    MANIFEST_OUT.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True))

    # ------------------------- private detail ----------------------------
    # No filenames. Only content hashes + engine outputs + program-key hashes.
    # This file is gitignored and must never land in the repo — only
    # meridianiq-private/calibration/cycle1-w4/ is the canonical home.
    def _strip(obs: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in obs.items() if k in {
            "content_hash", "parse_error", "program_key_hash",
            "activity_count", "last_recalc_date_iso",
            "phase", "confidence", "rules_fired",
        }}

    private_payload: dict[str, Any] = {
        "schema_version": 1,
        "run_started_at": run_started_at,
        "observations": [_strip(o) for o in observations],
        "gate_assignment": {
            "gate": gate_hashes,
            "hysteresis": hysteresis_hashes,
        },
    }
    PRIVATE_OUT.write_text(json.dumps(private_payload, indent=2, sort_keys=True))

    # ------------------------- console summary ---------------------------
    print(f"W4 calibration run @ {run_started_at}")
    print(f"  engine_version=4.0 ruleset_version={RULESET_VERSION}")
    print(f"  total_xers={len(xer_paths)} parse_failures={parse_failures}")
    print(f"  gate_subset={len(gate_obs)} hysteresis_subset={len(hysteresis_obs)}")
    print("  gate evaluations:")
    for t, ev in gate_evaluations.items():
        print(
            f"    threshold={t} pass_rate={ev['pass_rate']:.2%} "
            f"overall_pass={ev['overall_pass']} "
            f"dominant_phase_share={ev['dominant_phase_share_of_numerator']:.2%} "
            f"low_conf_share={ev['low_confidence_share']:.2%}"
        )
    print(f"Written: {MANIFEST_OUT} {PUBLIC_OUT} {PRIVATE_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
