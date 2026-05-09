# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Reusable calibration harness — ADR-0020.

Generalises the ``scripts/calibration/run_w4_calibration.py`` Wave-4
calibration script (Cycle 1 v4.0) into a primitive any future
probabilistic-heuristic engine can pre-register against. The Wave-4
script remains as the historical record of what was actually executed
for the lifecycle_phase v1 calibration; this module is the contract
for what the next engine (auto-grouping, ruleset v2, forensic
methodology variants) MUST author before it can ship a numeric claim.

Why this exists (per ADR-0019 §"W3"):
    The Wave-4 W4 calibration discovered that a probabilistic engine
    that ships without a pre-registered gate produces results no one
    can later challenge. The fix is structural — every engine that
    emits a numeric confidence against an evidence-based answer must
    declare its calibration protocol in advance and run against this
    harness before its surface ships as authoritative. The harness is
    the *measurement apparatus*; it does not adjudicate the outcome
    (that remains a human Amendment-2-style decision).

API
---

Three primitives:

* :class:`CalibrationProtocol` — the pre-registered §A-§E rules a
  protocol author commits to BEFORE running.
* :class:`EngineAdapter` — protocol an engine author implements so
  the harness can run their engine on a fixture and get a comparable
  ``Observation`` row.
* :func:`run_calibration` — applies the dedup / sub-gate / hysteresis
  / publication-scope pipeline and returns three payloads matching
  the Wave-4 output schema (manifest / public / private).

Plus a CLI wrapper at ``python -m tools.calibration_harness`` that
accepts ``--engine=lifecycle_phase --ruleset=v1 --fixtures=<DIR>``.

Publication scope (ADR-0009 Amendment 1 §F)
-------------------------------------------

The harness emits THREE payloads from any run:

* **manifest** — content-hashes only, no engine outputs. Safe for
  public commit. Maps the gate / hysteresis split.
* **public** — coarse-banded aggregate counts, histograms, sub-gate
  pass/fail. Safe to attach to a public calibration issue. Wave-4 used
  this as the input to ``docs/adr/0009-w4-outcome.md``.
* **private** — per-observation detail (program-key hashes, label,
  confidence, rules_fired). NEVER commit. Caller is responsible for
  archiving to ``meridianiq-private/calibration/<cycle>-<wave>/``.

The CLI writes all three to ``--output-dir`` (default ``/tmp``). The
``private`` filename is suffixed ``_private.json`` so a future
``.gitignore`` rule can blacklist it by glob.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


# --------------------------------------------------------------------------- #
# Observation record — engine-agnostic.
# --------------------------------------------------------------------------- #


@dataclass
class Observation:
    """One fixture's parse + engine-output row.

    Engine authors fill this via :meth:`EngineAdapter.parse_and_classify`.
    Fields are deliberately label-shaped, not phase-shaped, so the
    primitive generalises beyond ``lifecycle_phase``.
    """

    content_hash: str
    """SHA-256 of the fixture file bytes — identity for content-dedup."""

    program_key_hash: str | None
    """Truncated hash of the engine-specific program-grouping key. ``None``
    if the engine does not group fixtures (single-shot evaluation)."""

    label: str | None
    """Engine output. ``None`` only when ``parse_error`` is set."""

    confidence: float | None
    """Engine confidence in ``[0.0, 1.0]``. ``None`` only on parse error."""

    parse_error: str | None
    """Exception class name if parsing failed; otherwise ``None``."""

    rules_fired: list[str] = field(default_factory=list)
    """Names of the rules that contributed to the label, for forensic
    reconstruction. Engine-specific."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Engine-specific opaque metadata used by the dedup rule (e.g.
    ``activity_count``, ``last_recalc_date_iso`` for lifecycle_phase).
    Never serialised into the public payload — only into private +
    consulted by the harness internals."""

    def __post_init__(self) -> None:
        # Council finding (W3 devils-advocate P1, backend-reviewer P1):
        # an out-of-range confidence (e.g. ``2.7``) would silently pass
        # ``(o.confidence or 0.0) >= threshold`` AND be absent from the
        # ``< 0.5`` low-confidence subset, inflating the gate. Reject at
        # the boundary so a buggy engine fails LOUD with a typed error
        # instead of producing a "passing" calibration that is
        # mathematically impossible.
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Observation.confidence must be in [0.0, 1.0]; got {self.confidence!r}. "
                "Engine-side validation is the engine author's responsibility — "
                "do not coerce."
            )


# --------------------------------------------------------------------------- #
# Engine adapter — Protocol implemented per engine.
# --------------------------------------------------------------------------- #


class EngineAdapter(Protocol):
    """Engine authors implement this to plug into the harness."""

    @property
    def engine_name(self) -> str: ...

    @property
    def engine_version(self) -> str: ...

    @property
    def ruleset_version(self) -> str: ...

    @property
    def label_set(self) -> tuple[str, ...]:
        """Valid output labels — MUST include the unknown sentinel."""
        ...

    @property
    def unknown_label(self) -> str:
        """The label that signals 'engine could not classify'."""
        ...

    def parse_and_classify(self, fixture_path: Path) -> Observation: ...

    def dedup_key_priority(self, obs: Observation) -> tuple[Any, ...]:
        """Return a tuple used to pick the canonical revision when
        multiple fixtures share the same ``program_key_hash``. The
        harness picks ``max(members, key=dedup_key_priority)``.
        Engines that do not group return any constant from this method
        (the harness short-circuits when no group has > 1 member)."""
        ...


# --------------------------------------------------------------------------- #
# Calibration protocol — pre-registered.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CalibrationProtocol:
    """Pre-registered calibration rules. Authored BEFORE running.

    The defaults match ADR-0009 Amendment 1 §B-§E for lifecycle_phase
    Wave-4. Other engines override fields. Once committed to the repo
    in an ADR, the protocol is immutable for the run it backs — drift
    must ship as a NEW protocol with a versioned name.
    """

    name: str
    """Stable identifier — e.g. ``'lifecycle_phase-w4-v1'``."""

    primary_threshold: float = 0.80
    """Confidence threshold the gate is formally evaluated at."""

    additional_thresholds: tuple[float, ...] = (0.70, 0.60)
    """Recorded for evidence; not part of the gate decision."""

    confidence_histogram_edges: tuple[float, ...] = (0.0, 0.5, 0.7, 0.8, 1.0)
    """Coarse-band edges for the publishable confidence histogram."""

    label_distribution_max_share: float = 0.60
    """§C ceiling — no single label may exceed this share of the
    numerator. Anti-monoculture sub-gate."""

    confidence_honesty_min_share: float = 0.20
    """§D floor — at least this share of the gate subset must land at
    confidence < 0.5. The engine must show its uncertainty."""

    primary_pass_rate_floor: float = 0.70
    """§E primary rate floor — gate passes only if the post-§B numerator
    over the gate subset is at least this large."""

    schema_version: int = 1
    """Bumped if the public/manifest/private payload shapes change."""


def evaluate_sub_gates(
    gate_obs: Sequence[Observation],
    protocol: CalibrationProtocol,
    threshold: float,
    *,
    unknown_label: str,
) -> dict[str, Any]:
    """Apply §B + §C + §D + §E at one threshold.

    §B: ``unknown`` is in the denominator (we count it against us) but
    NEVER in the numerator (it cannot pass the gate).
    §C: dominant-label share of the numerator must be ≤ ``label_distribution_max_share``.
    §D: low-confidence share of the gate subset must be ≥ ``confidence_honesty_min_share``.
    §E: numerator / denominator must be ≥ ``primary_pass_rate_floor``.

    Returns a dict matching the Wave-4 ``gate_evaluations_by_threshold``
    entry shape so the W4 outcome record stays reproducible.
    """
    n = len(gate_obs)
    pass_obs = [
        o
        for o in gate_obs
        if o.label != unknown_label and o.label is not None and (o.confidence or 0.0) >= threshold
    ]
    numerator_label_counts: Counter[str] = Counter(o.label for o in pass_obs if o.label is not None)
    pass_rate = len(pass_obs) / n if n else 0.0
    dominant_label_share = max(numerator_label_counts.values()) / len(pass_obs) if pass_obs else 0.0
    label_distribution_ok = (
        dominant_label_share <= protocol.label_distribution_max_share or not pass_obs
    )
    low_conf_count = sum(1 for o in gate_obs if (o.confidence or 0.0) < 0.5)
    low_conf_share = low_conf_count / n if n else 0.0
    confidence_honesty_ok = low_conf_share >= protocol.confidence_honesty_min_share
    primary_pass_rate_ok = pass_rate >= protocol.primary_pass_rate_floor
    overall_pass = primary_pass_rate_ok and label_distribution_ok and confidence_honesty_ok
    return {
        "threshold": threshold,
        "denominator": n,
        "numerator": len(pass_obs),
        "pass_rate": round(pass_rate, 4),
        "dominant_label_share_of_numerator": round(dominant_label_share, 4),
        "label_distribution_sub_gate_ok": label_distribution_ok,
        "low_confidence_share": round(low_conf_share, 4),
        "confidence_honesty_sub_gate_ok": confidence_honesty_ok,
        "primary_pass_rate_ok": primary_pass_rate_ok,
        "overall_pass": overall_pass,
        "numerator_label_counts": dict(numerator_label_counts),
    }


# --------------------------------------------------------------------------- #
# Dedup + hysteresis (engine-agnostic).
# --------------------------------------------------------------------------- #


def split_gate_and_hysteresis(
    observations: Sequence[Observation],
    *,
    dedup_key_priority: Callable[[Observation], tuple[Any, ...]],
) -> tuple[list[str], list[str]]:
    """Group observations by ``program_key_hash`` and pick the canonical
    revision per ADR-0009 Amendment 1 §A.

    Returns ``(gate_content_hashes, hysteresis_content_hashes)`` —
    sorted for deterministic manifest output.
    """
    groups: dict[str, list[Observation]] = defaultdict(list)
    for obs in observations:
        if obs.parse_error is not None or obs.program_key_hash is None:
            continue
        groups[obs.program_key_hash].append(obs)
    gate: list[str] = []
    hysteresis: list[str] = []
    for members in groups.values():
        if len(members) == 1:
            gate.append(members[0].content_hash)
            continue
        best = max(members, key=dedup_key_priority)
        gate.append(best.content_hash)
        for m in members:
            if m.content_hash != best.content_hash:
                hysteresis.append(m.content_hash)
    return sorted(gate), sorted(hysteresis)


def hysteresis_report(
    observations: Sequence[Observation],
    hysteresis_hashes: set[str],
    gate_hashes: set[str],
    *,
    revision_order_key: Callable[[Observation], str | int | float],
) -> dict[str, Any]:
    """Per-program flip-flop count across preserved serial revisions.

    For each program with multiple observations (gate + hysteresis),
    sort by ``revision_order_key`` ascending and count any consecutive
    label disagreement OR confidence-band crossing at 0.5 / 0.8.
    """
    by_program: dict[str, list[Observation]] = defaultdict(list)
    for obs in observations:
        if obs.parse_error is not None or obs.program_key_hash is None:
            continue
        if obs.content_hash in hysteresis_hashes or obs.content_hash in gate_hashes:
            by_program[obs.program_key_hash].append(obs)
    multi_revision_programs = 0
    label_flips = 0
    confidence_band_flips = 0
    for members in by_program.values():
        if len(members) < 2:
            continue
        multi_revision_programs += 1
        ordered = sorted(members, key=revision_order_key)
        for prev, curr in zip(ordered, ordered[1:], strict=False):
            if prev.label != curr.label:
                label_flips += 1
            pc, cc = prev.confidence or 0.0, curr.confidence or 0.0
            for edge in (0.5, 0.8):
                if (pc < edge and cc >= edge) or (pc >= edge and cc < edge):
                    confidence_band_flips += 1
                    break
    return {
        "multi_revision_programs": multi_revision_programs,
        "label_flips_across_revisions": label_flips,
        "confidence_band_flips_across_revisions": confidence_band_flips,
    }


def label_histogram(
    observations: Sequence[Observation], label_set: Sequence[str]
) -> dict[str, int]:
    c: Counter[str] = Counter({lbl: 0 for lbl in label_set})
    for obs in observations:
        if obs.parse_error is not None or obs.label is None:
            continue
        if obs.label in c:
            c[obs.label] += 1
    return dict(c)


def confidence_histogram(
    observations: Sequence[Observation], edges: Sequence[float]
) -> dict[str, int]:
    c: Counter[str] = Counter()
    for obs in observations:
        if obs.parse_error is not None:
            continue
        bucket = _bucket_confidence(obs.confidence, edges)
        c[bucket] += 1
    return dict(c)


def _bucket_confidence(c: float | None, edges: Sequence[float]) -> str:
    if c is None:
        return "__missing__"
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        is_last = i == len(edges) - 2
        if lo <= c < hi or (is_last and c == hi):
            label = f"[{lo:.2f},{hi:.2f}]" if is_last else f"[{lo:.2f},{hi:.2f})"
            return label
    return "__out_of_range__"


# --------------------------------------------------------------------------- #
# Runner.
# --------------------------------------------------------------------------- #


@dataclass
class CalibrationOutputs:
    """Three payloads from one calibration run.

    Caller serialises these to disk (CLI does so at
    ``--output-dir/<protocol_name>_<scope>.json``) or feeds them into
    a programmatic adjudication step.
    """

    manifest_payload: dict[str, Any]
    public_payload: dict[str, Any]
    private_payload: dict[str, Any]


def run_calibration(
    engine: EngineAdapter,
    fixtures: Iterable[Path],
    protocol: CalibrationProtocol,
    *,
    revision_order_key: Callable[[Observation], str | int | float] | None = None,
) -> CalibrationOutputs:
    """Run the full calibration pipeline.

    Steps:
      1. Parse + classify each fixture via ``engine.parse_and_classify``.
      2. Split into gate / hysteresis subsets per the dedup rule.
      3. Evaluate sub-gates at primary + additional thresholds.
      4. Build the three payloads (manifest, public, private).

    ``revision_order_key`` orders members of a program for the
    hysteresis flip-flop count. Defaults to a stable but uninformative
    order (``content_hash``) — engines should pass their own (e.g.
    ``last_recalc_date_iso`` for lifecycle_phase).
    """
    revision_order_key = revision_order_key or (lambda o: o.content_hash)
    observations: list[Observation] = []
    for path in fixtures:
        observations.append(engine.parse_and_classify(path))

    parse_failures = sum(1 for o in observations if o.parse_error is not None)

    gate_hashes, hysteresis_hashes = split_gate_and_hysteresis(
        observations, dedup_key_priority=engine.dedup_key_priority
    )
    gate_set, hyst_set = set(gate_hashes), set(hysteresis_hashes)
    gate_obs = [o for o in observations if o.content_hash in gate_set]
    hysteresis_obs = [o for o in observations if o.content_hash in hyst_set]

    thresholds = (protocol.primary_threshold, *protocol.additional_thresholds)
    gate_evaluations = {
        f"{t:.2f}": evaluate_sub_gates(gate_obs, protocol, t, unknown_label=engine.unknown_label)
        for t in thresholds
    }

    run_started_at = datetime.now(UTC).isoformat()

    public_payload: dict[str, Any] = {
        "schema_version": protocol.schema_version,
        "protocol_name": protocol.name,
        "engine_name": engine.engine_name,
        "engine_version": engine.engine_version,
        "ruleset_version": engine.ruleset_version,
        "run_started_at": run_started_at,
        "counts": {
            "total_fixtures": len(observations),
            "parse_failures": parse_failures,
            "gate_subset": len(gate_obs),
            "hysteresis_subset": len(hysteresis_obs),
        },
        "label_histogram_all": label_histogram(observations, engine.label_set),
        "label_histogram_gate": label_histogram(gate_obs, engine.label_set),
        "confidence_histogram_gate": confidence_histogram(
            gate_obs, protocol.confidence_histogram_edges
        ),
        "gate_evaluations_by_threshold": gate_evaluations,
        "hysteresis_report_gate_plus_hysteresis": hysteresis_report(
            observations,
            hyst_set,
            gate_set,
            revision_order_key=revision_order_key,
        ),
    }

    manifest_payload: dict[str, Any] = {
        "schema_version": protocol.schema_version,
        "protocol_name": protocol.name,
        "run_started_at": run_started_at,
        "engine_version": engine.engine_version,
        "ruleset_version": engine.ruleset_version,
        "gate_subset_content_hashes": gate_hashes,
        "hysteresis_subset_content_hashes": hysteresis_hashes,
        "parse_failed_content_hashes": sorted(
            o.content_hash for o in observations if o.parse_error is not None
        ),
    }

    private_payload: dict[str, Any] = {
        "schema_version": protocol.schema_version,
        "protocol_name": protocol.name,
        "run_started_at": run_started_at,
        "observations": [
            {
                "content_hash": o.content_hash,
                "parse_error": o.parse_error,
                "program_key_hash": o.program_key_hash,
                "label": o.label,
                "confidence": o.confidence,
                "rules_fired": o.rules_fired,
                "metadata": o.metadata,
            }
            for o in observations
        ],
        "gate_assignment": {
            "gate": gate_hashes,
            "hysteresis": hysteresis_hashes,
        },
    }

    return CalibrationOutputs(
        manifest_payload=manifest_payload,
        public_payload=public_payload,
        private_payload=private_payload,
    )


# --------------------------------------------------------------------------- #
# Built-in adapters — engines pre-register here.
# --------------------------------------------------------------------------- #


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def truncated_program_key_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


# --------------------------------------------------------------------------- #
# W3-C — optimism_synth fixture hash-lock verification (ADR-0022 HB-D).
# --------------------------------------------------------------------------- #


_OPTIMISM_SYNTH_DIR = Path(__file__).parent / "fixtures" / "optimism_synth"
_OPTIMISM_SYNTH_LOCK = Path(__file__).parent / "fixtures" / "optimism_synth.lock"


class FixtureHashMismatch(RuntimeError):
    """Raised when an on-disk fixture does not match its hash-lock entry.

    W4 sub-gate C MUST treat this as an evaluation abort: the fixtures
    have been retuned post-W3-close, so the gate is structurally
    invalid. ADR-0023 documents the tampering when this fires.
    """


def parse_fixture_lock(lock_path: Path) -> dict[str, str]:
    """Parse a fixture lock file into ``{filename: sha256}``.

    Lock-file format (W3-C, intentionally minimal — no library
    dependency, no JSON-schema overhead):

        # comments start with '#'
        # blank lines ignored
        <sha256_hex>  <relative_filename>

    Spaces between hash and filename are flexible (≥1 whitespace).
    """
    out: dict[str, str] = {}
    if not lock_path.exists():
        raise FileNotFoundError(f"fixture lock not found: {lock_path}")
    for raw in lock_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise ValueError(f"malformed lock entry: {raw!r}")
        sha, name = parts
        if len(sha) != 64 or not all(c in "0123456789abcdef" for c in sha.lower()):
            raise ValueError(f"non-sha256 hash in lock: {sha!r}")
        out[name] = sha.lower()
    return out


def verify_optimism_synth_hash_lock(
    fixtures_dir: Path | None = None,
    lock_path: Path | None = None,
) -> dict[str, str]:
    """Verify every fixture in ``fixtures_dir`` matches its lock entry.

    Returns the ``{filename: sha256}`` dict on success.

    Raises:
        FixtureHashMismatch: if any fixture's on-disk SHA256 differs
            from the lock, OR the lock has entries with no on-disk
            file, OR the directory has fixtures absent from the lock.
            All three are tampering signals.

    W4 sub-gate C invocation contract: call this BEFORE any
    F1-evaluation work begins. A clean return is the only path to
    proceeding; any raise aborts and lands in ADR-0023.
    """
    fdir = fixtures_dir or _OPTIMISM_SYNTH_DIR
    lpath = lock_path or _OPTIMISM_SYNTH_LOCK
    expected = parse_fixture_lock(lpath)
    actual: dict[str, str] = {}
    for path in sorted(fdir.glob("corner_*.json")):
        actual[path.name] = sha256_path(path)
    if set(expected) != set(actual):
        missing_disk = sorted(set(expected) - set(actual))
        missing_lock = sorted(set(actual) - set(expected))
        raise FixtureHashMismatch(
            f"fixture set mismatch — locked={sorted(expected)} disk={sorted(actual)} "
            f"missing_disk={missing_disk} missing_lock={missing_lock}"
        )
    drift: dict[str, tuple[str, str]] = {}
    for name, want in expected.items():
        got = actual[name]
        if got != want:
            drift[name] = (want, got)
    if drift:
        report = ", ".join(f"{n}: locked={w[:8]}… got={g[:8]}…" for n, (w, g) in drift.items())
        raise FixtureHashMismatch(f"hash drift detected (W4 sub-gate C MUST abort): {report}")
    return actual


# --------------------------------------------------------------------------- #
# W3-C — sub-gate C F1 evaluator (DA P1 #1+#3 closure).
# --------------------------------------------------------------------------- #
#
# Locked HERE before the W4 evaluation runs, on the SAME PR as the fixture
# hash-lock, to close both axes of the circular-tuning attack: fixtures
# can't be retuned post-W3 (hash-lock) AND the F1 metric definition
# can't be retuned post-W3 (code-lock). DA exit-council finding P1 #1+#3.


@dataclass(frozen=True)
class CusumF1Result:
    """Sub-gate C output: cluster-span-match F1 against ground truth.

    Notation:
    * ``true_positives`` — clusters that overlap at least one truth's
      tolerance window. Counted per-truth (at most one TP per truth).
    * ``false_positives`` — clusters that overlap no truth window.
    * ``false_negatives`` — truths with no overlapping cluster.

    F1 returns 0.0 on undefined cases (zero detections + zero truths,
    or zero TP). Avoids division-by-zero ambiguity that future
    evaluators could exploit to redefine the threshold.
    """

    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    matched_truths: tuple[int, ...]
    fp_cluster_starts: tuple[int, ...]


def collapse_detection_clusters(
    detections: Sequence[int],
    *,
    max_gap: int = 1,
) -> list[tuple[int, int]]:
    """Collapse adjacent detection indices into ``(first, last)`` spans.

    CUSUM is multi-fire by design (every index where ``|cumsum| ≥ Nσ``
    appears in the result list — see ``revision_trends.py:312-315``).
    For F1 evaluation we treat a contiguous run of detections as ONE
    regime-change signal, not N false positives. ``max_gap=1`` allows
    a single missing index inside a run (defensive — single index
    drop-outs are common at threshold boundaries).
    """
    if not detections:
        return []
    sorted_dets = sorted(detections)
    clusters: list[tuple[int, int]] = []
    start = prev = sorted_dets[0]
    for d in sorted_dets[1:]:
        if d - prev > max_gap:
            clusters.append((start, prev))
            start = d
        prev = d
    clusters.append((start, prev))
    return clusters


def evaluate_cusum_f1(
    detections: Sequence[int],
    ground_truths: Sequence[int],
    *,
    tolerance: int = 1,
    cluster_max_gap: int = 1,
) -> CusumF1Result:
    """F1 against ground-truth change-points using cluster-span match.

    Match rule: a detection cluster ``[first, last]`` matches a truth
    ``t`` iff its expanded span ``[first - tolerance, last + tolerance]``
    contains ``t``. Each truth can match at most one cluster (chosen
    greedily by cluster start index). Each cluster can match at most
    one truth.

    Span-match (vs first-detection match) chosen because the engine's
    CUSUM-on-shifts naturally fires across multiple revisions during
    the same regime shift (the cumsum minimum often lands at the END
    of pre-CP run, not at the CP itself). Span-match rewards the
    engine for correctly identifying the WINDOW containing the
    regime change — which is the user-facing semantic of the
    revision_trends visualization (vertical change-point markers
    indicate the contested window, not a single point estimate).

    Returns:
        ``CusumF1Result`` with TP / FP / FN / precision / recall / F1.
        ``f1 = 0.0`` on undefined cases (no detections + truths, or
        zero TP after matching). Returning 0 on undefined is the
        conservative choice — sub-gate C threshold ≥ 0.75 cannot be
        "passed by vacuity" via empty inputs.
    """
    clusters = collapse_detection_clusters(detections, max_gap=cluster_max_gap)
    truths = sorted(set(ground_truths))
    matched_truths: list[int] = []
    matched_cluster_idx: set[int] = set()
    for t in truths:
        for ci, (first, last) in enumerate(clusters):
            if ci in matched_cluster_idx:
                continue
            if (first - tolerance) <= t <= (last + tolerance):
                matched_truths.append(t)
                matched_cluster_idx.add(ci)
                break
    tp = len(matched_truths)
    fp = len(clusters) - len(matched_cluster_idx)
    fn = len(truths) - tp
    fp_starts = tuple(c[0] for ci, c in enumerate(clusters) if ci not in matched_cluster_idx)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if tp == 0 or (precision + recall) == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return CusumF1Result(
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=round(precision, 6),
        recall=round(recall, 6),
        f1=round(f1, 6),
        matched_truths=tuple(matched_truths),
        fp_cluster_starts=fp_starts,
    )


class _LifecyclePhaseV1Adapter:
    """Adapter for ``src.analytics.lifecycle_phase`` v1 — the engine
    that backed the Wave-4 calibration. Used for the W3 demo run."""

    def __init__(self) -> None:
        # Lazy import so importing the harness module doesn't pull in
        # the analytics dependency tree (heavy: networkx, numpy).
        from src.analytics.lifecycle_phase import (
            ENGINE_NAME,
            RULESET_VERSION,
            infer_lifecycle_phase,
        )
        from src.analytics.lifecycle_types import LIFECYCLE_PHASES
        from src.parser.xer_reader import XERReader

        self._engine_name = ENGINE_NAME
        self._engine_version = "4.0"
        self._ruleset_version = RULESET_VERSION
        self._label_set = LIFECYCLE_PHASES
        self._infer = infer_lifecycle_phase
        self._reader = XERReader

    @property
    def engine_name(self) -> str:
        return self._engine_name

    @property
    def engine_version(self) -> str:
        return self._engine_version

    @property
    def ruleset_version(self) -> str:
        return self._ruleset_version

    @property
    def label_set(self) -> tuple[str, ...]:
        return tuple(self._label_set)

    @property
    def unknown_label(self) -> str:
        return "unknown"

    def parse_and_classify(self, fixture_path: Path) -> Observation:
        content_hash = sha256_path(fixture_path)
        try:
            schedule = self._reader(str(fixture_path)).parse()
        except Exception as exc:
            return Observation(
                content_hash=content_hash,
                program_key_hash=None,
                label=None,
                confidence=None,
                parse_error=type(exc).__name__,
                rules_fired=[],
                metadata={},
            )
        # Program key per W4 — proj_short_name uppercased.
        if schedule.projects:
            p = schedule.projects[0]
            raw_key = (p.proj_short_name or p.proj_id or "__unknown__").strip().upper()
            recalc_iso = p.last_recalc_date.isoformat() if p.last_recalc_date else None
        else:
            raw_key = "__no_project__"
            recalc_iso = None
        result = self._infer(schedule)
        rules_fired_raw = (
            result.rationale.get("rules_fired", []) if isinstance(result.rationale, dict) else []
        )
        rules_fired = [str(r) for r in rules_fired_raw]
        activity_count = len(schedule.activities) if schedule.activities else 0
        return Observation(
            content_hash=content_hash,
            program_key_hash=truncated_program_key_hash(raw_key),
            label=result.phase,
            confidence=float(result.confidence),
            parse_error=None,
            rules_fired=rules_fired,
            metadata={
                "activity_count": activity_count,
                "last_recalc_date_iso": recalc_iso,
            },
        )

    def dedup_key_priority(self, obs: Observation) -> tuple[Any, ...]:
        """W4 §A: max(activity_count) tie-break max(last_recalc_date_iso)."""
        return (
            obs.metadata.get("activity_count", 0),
            obs.metadata.get("last_recalc_date_iso") or "",
        )


def _lifecycle_phase_revision_order_key(obs: Observation) -> str:
    return obs.metadata.get("last_recalc_date_iso") or ""


_REGISTRY: dict[str, Callable[[], EngineAdapter]] = {
    "lifecycle_phase": _LifecyclePhaseV1Adapter,
}


_PROTOCOLS: dict[str, CalibrationProtocol] = {
    "lifecycle_phase-w4-v1": CalibrationProtocol(
        name="lifecycle_phase-w4-v1",
        primary_threshold=0.80,
        additional_thresholds=(0.70, 0.60),
        confidence_histogram_edges=(0.0, 0.5, 0.7, 0.8, 1.0),
        label_distribution_max_share=0.60,
        confidence_honesty_min_share=0.20,
        primary_pass_rate_floor=0.70,
    ),
}


def get_adapter(name: str) -> EngineAdapter:
    """Look up a registered engine adapter by name. Raises ``KeyError``
    if the engine has not pre-registered. New engines register via the
    ``_REGISTRY`` dict in this module — keep registration explicit so
    a `grep` against the harness reveals every consumer."""
    if name not in _REGISTRY:
        raise KeyError(f"engine {name!r} is not registered. Registered: {sorted(_REGISTRY.keys())}")
    return _REGISTRY[name]()


def get_protocol(name: str) -> CalibrationProtocol:
    if name not in _PROTOCOLS:
        raise KeyError(
            f"protocol {name!r} is not registered. Registered: {sorted(_PROTOCOLS.keys())}"
        )
    return _PROTOCOLS[name]


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #


def cli(argv: list[str] | None = None) -> int:
    """Public CLI entry point. Renamed from ``_cli`` per issue #100 / DA P2 #11
    on PR #99: ``__main__.py`` is the documented public entry; cross-package
    private import was convention-broken. DA exit-council on PR #111 P1 #2:
    the gate-level ``revision_trends_w4::cli`` was ALSO renamed in the same
    PR (originally claimed "private to the harness sub-tool" but actually
    cross-package-imported by ``gates/__main__.py`` + the test suite — the
    asymmetry was a docstring fiction)."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m tools.calibration_harness",
        description=(
            "Run a pre-registered calibration protocol against an engine. "
            "ADR-0020 — Cycle 2 v4.0 W3."
        ),
    )
    parser.add_argument(
        "--engine",
        required=True,
        help="Registered engine name (e.g. lifecycle_phase).",
    )
    parser.add_argument(
        "--protocol",
        required=True,
        help=(
            "Registered calibration protocol name. NO DEFAULT — protocols "
            "are engine-specific and silently using one engine's protocol "
            "against a different engine produces meaningless gate numbers "
            "(W3 council finding)."
        ),
    )
    parser.add_argument(
        "--fixtures",
        required=True,
        type=Path,
        help="Directory containing fixture files (engine-specific glob).",
    )
    parser.add_argument(
        "--fixture-glob",
        default="*.xer",
        help="Glob pattern under --fixtures (default *.xer).",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("/tmp"),
        type=Path,
        help="Where to write manifest / public / private payloads.",
    )
    args = parser.parse_args(argv)

    fixtures_dir: Path = args.fixtures
    if not fixtures_dir.is_dir():
        print(f"ERROR: fixtures dir {fixtures_dir} is not a directory", file=sys.stderr)
        return 2
    paths = sorted(fixtures_dir.glob(args.fixture_glob))
    if not paths:
        print(
            f"ERROR: no fixtures matching {args.fixture_glob!r} under {fixtures_dir}",
            file=sys.stderr,
        )
        return 2

    try:
        engine = get_adapter(args.engine)
    except KeyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        protocol = get_protocol(args.protocol)
    except KeyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    revision_key: Callable[[Observation], str | int | float] | None = None
    if args.engine == "lifecycle_phase":
        revision_key = _lifecycle_phase_revision_order_key

    outputs = run_calibration(
        engine,
        paths,
        protocol,
        revision_order_key=revision_key,
    )

    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / f"{protocol.name}_manifest.json"
    public_path = out_dir / f"{protocol.name}_public.json"
    private_path = out_dir / f"{protocol.name}_private.json"
    manifest_path.write_text(json.dumps(outputs.manifest_payload, indent=2, sort_keys=True))
    public_path.write_text(json.dumps(outputs.public_payload, indent=2, sort_keys=True))
    private_path.write_text(json.dumps(outputs.private_payload, indent=2, sort_keys=True))

    public = outputs.public_payload
    print(f"Calibration run @ {public['run_started_at']}")
    print(f"  protocol={protocol.name}")
    print(
        f"  engine={engine.engine_name} engine_version={engine.engine_version} "
        f"ruleset_version={engine.ruleset_version}"
    )
    counts = public["counts"]
    print(
        f"  total_fixtures={counts['total_fixtures']} "
        f"parse_failures={counts['parse_failures']} "
        f"gate_subset={counts['gate_subset']} "
        f"hysteresis_subset={counts['hysteresis_subset']}"
    )
    print("  gate evaluations:")
    for t, ev in public["gate_evaluations_by_threshold"].items():
        print(
            f"    threshold={t} pass_rate={ev['pass_rate']:.2%} "
            f"overall_pass={ev['overall_pass']} "
            f"dominant_label_share={ev['dominant_label_share_of_numerator']:.2%} "
            f"low_conf_share={ev['low_confidence_share']:.2%}"
        )
    print(f"Written:\n  {manifest_path}\n  {public_path}\n  {private_path}")
    return 0


if __name__ == "__main__":
    sys.exit(cli())
