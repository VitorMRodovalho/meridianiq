# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Shared lifecycle vocabulary used by the W3 inference engine, store, API,
and (conditional on W4 gate) the W5/W6 ``lifecycle_health.py`` deep engine.

Per ADR-0016 §2 the type live in ``src.analytics.lifecycle_types`` so any
downstream engine can import the vocabulary without importing the inference
engine itself — preserving the standalone-engine invariant ADR-0009 §Wave-3
established for ``src/analytics/`` (no engine imports another engine; the
materializer is the composition layer).

Phase taxonomy: 5 + ``unknown`` per ADR-0016 §1. The construction
sub-phase split (early / mid / late) is intentionally NOT a phase value
in W3 — W4 sandbox calibration would crater on a 9-value classifier with
the available signal density. ADR-0016 reserves the construction-band
concept as a *derived dimension* for the W5 ``lifecycle_health.py`` engine
should the W4 gate pass.

Standards cited:

- AACE RP 14R §3 — planning-phase ownership delineation as the baseline
  signal that anchors phase inference at the front of the lifecycle.
- ISO 21502 §6.3 — project lifecycle as first-class metadata.
- PMI Construction Extension §4 — referenced as "mappable to" in the engine
  docstring; not claimed as alignment because PMI-CP uses different phase
  names (initiating / planning / executing / monitoring / closing) and the
  mapping has not been formally walked.

SCL Protocol §4 is cited on the override-log audit trail (migration 025),
NOT on the phase taxonomy itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

LifecyclePhase = Literal[
    "planning",
    "design",
    "procurement",
    "construction",
    "closeout",
    "unknown",
]
"""The five canonical phases plus the explicit ``'unknown'`` guard.

``'unknown'`` is emitted by the inference engine when the input lacks the
minimum signal needed to classify (e.g. no ``data_date``). Per ADR-0016
§3 the engine MUST persist an ``'unknown'`` artifact rather than skip
the row — the distinction "inference has not run" (no artifact) vs
"inference ran and could not classify" (artifact with phase=unknown) is
load-bearing for the UI empty-state vs failure-state vocabulary.
"""

LIFECYCLE_PHASES: tuple[LifecyclePhase, ...] = (
    "planning",
    "design",
    "procurement",
    "construction",
    "closeout",
    "unknown",
)
"""Tuple form for runtime iteration / validation. Mirrors the DB CHECK
constraints in migration 025 on ``lifecycle_override_log.override_phase``
and ``.inferred_phase``.
"""


@dataclass(frozen=True)
class LifecyclePhaseInference:
    """One inference output from ``src.analytics.lifecycle_phase``.

    Attributes:
        phase: one of :data:`LIFECYCLE_PHASES`.
        confidence: float in ``[0.0, 1.0]``. ``'unknown'`` always pairs with
            ``confidence=0.0``. Per ADR-0016 §1 the engine SHOULD also emit
            the gate-equivalent band ("low" <0.5 / "medium" 0.5–0.79 /
            "high" >=0.8) via :func:`confidence_band` for UI consumers.
        rationale: free-form dict. Engines are encouraged to include the
            signal weights and triggered rules so a forensic reviewer can
            reconstruct the decision. JSON-serialisable values only.

    The dataclass is ``frozen=True`` so engines cannot mutate the result
    after returning it — a small forensic-discipline guard.
    """

    phase: LifecyclePhase
    confidence: float
    rationale: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.phase not in LIFECYCLE_PHASES:
            raise ValueError(
                f"invalid LifecyclePhase: {self.phase!r}; must be one of {list(LIFECYCLE_PHASES)}"
            )
        # NaN / +Inf / -Inf are not valid confidence — also blocked at the
        # canonical_hash boundary (allow_nan=False) but the engine boundary
        # is the right place to fail loudly rather than silently.
        if not isinstance(self.confidence, (int, float)) or self.confidence != self.confidence:
            raise ValueError(f"invalid LifecyclePhaseInference.confidence: {self.confidence!r}")
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError(
                f"LifecyclePhaseInference.confidence must be in [0.0, 1.0], got {self.confidence}"
            )
        if self.phase == "unknown" and float(self.confidence) != 0.0:
            raise ValueError(f"phase='unknown' must have confidence=0.0, got {self.confidence}")


def confidence_band(confidence: float) -> Literal["low", "medium", "high"]:
    """Map a numeric confidence to the 3-band UI vocabulary.

    Thresholds align with the W4 gate requirement of ``confidence >= 0.80``
    per ADR-0009 §"Gate criteria" — the "high" band IS the gate-passing
    band. UI surfaces the numeric value AND the band per ADR-0009 W3 hard
    requirement.
    """
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"
