# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Lifecycle phase inference engine (W3 of Cycle 1 v4.0).

Classifies a parsed P6 XER schedule into one of the canonical lifecycle
phases ``planning / design / procurement / construction / closeout`` (or
``unknown`` when the input lacks the minimum signal). Output is a
:class:`LifecyclePhaseInference` carrying the phase, a confidence in
``[0.0, 1.0]``, and a JSON-serialisable rationale dict listing the
signals and the triggered rule.

Per ADR-0009 §Wave-3 + ADR-0016 the engine is intentionally lightweight —
the deep phase-aware analytics live in the W5/W6 conditional
``lifecycle_health.py`` engine. W3 ships only the label inference + a
confidence score that is honest about uncertainty.

Standards cited:

- AACE RP 14R §3 (planning-phase ownership delineation — anchors the
  early-phase signal: planning vs design depends on baseline availability
  and on whether the schedule shows discipline-segregated WBS depth).
- ISO 21502 §6.3 (project lifecycle as first-class metadata — informs
  the 5-phase taxonomy choice over a finer-grained PMI-CP mapping).
- PMI Construction Extension §4 — referenced as "mappable to" in the
  rationale dict; not claimed as alignment because PMI-CP uses different
  phase names (initiating / planning / executing / monitoring / closing).
- W4 calibration gate (ADR-0009 §Gate-criteria): ``confidence >= 0.80``
  is the gate-passing band. Confidence values returned here MUST be
  honest about uncertainty so the gate's ``>=80%`` filter is meaningful.

The engine is **stateless** per CLAUDE.md ``Code Standards`` ("Analysis
engines in src/analytics/ must be stateless — receive data, return
results"). Hysteresis to suppress phase flip-flops between consecutive
uploads is a W4+ follow-up that lives at the *materializer* layer
(which has access to prior artifacts), NOT inside this engine.

Multi-project XER scope: this engine evaluates ``schedule.projects[0]``
and that project's activities. ADR-0015 §1 acknowledges multi-project
XERs as Wave 3+ scope — the materializer raises if it encounters one.
Inference of multi-project rollup phase is out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.analytics.lifecycle_types import LifecyclePhase, LifecyclePhaseInference
from src.parser.models import ParsedSchedule, Project, Task

__all__ = [
    "infer_lifecycle_phase",
    "RULESET_VERSION",
    "ENGINE_NAME",
]

ENGINE_NAME = "lifecycle_phase"
RULESET_VERSION = "lifecycle_phase-v1-2026-04"
"""Bump when threshold tuning lands. Bumping triggers ``mark_stale`` of
prior inferences via the ``ruleset_upgraded`` reason per ADR-0014.
"""


@dataclass(frozen=True)
class _Signals:
    """Extracted signals — surfaced in the rationale dict for forensic review."""

    data_date: datetime
    plan_start: datetime | None
    plan_end: datetime | None
    elapsed_ratio: float | None
    activity_count: int
    started_pct: float
    completed_pct: float
    mean_phys_complete: float
    has_procurement_codes: bool
    has_baseline_dates: bool


def infer_lifecycle_phase(schedule: ParsedSchedule) -> LifecyclePhaseInference:
    """Classify the schedule into one of six phases (5 + ``unknown``).

    Pure function: same input → same output. No DB access, no external
    state. Per ADR-0016 §1 the engine emits a phase=``unknown`` artifact
    rather than skipping when the input lacks the minimum signal — the
    distinction "inference has not run" (no artifact) vs "inference ran
    and could not classify" (artifact with phase=unknown) is load-bearing
    for the UI empty-state vs failure-state vocabulary.

    Args:
        schedule: parsed XER. Multi-project XERs evaluate the first
            project only; the materializer enforces the single-project
            invariant before calling this engine.

    Returns:
        :class:`LifecyclePhaseInference` with ``rationale`` containing
        every extracted signal and the triggered rule name.
    """
    # ----- Guards (return phase='unknown') -------------------------------
    if not schedule.projects:
        return _unknown("no_project_record")

    proj = schedule.projects[0]
    data_date = proj.last_recalc_date or proj.sum_data_date
    if data_date is None:
        return _unknown(
            "no_data_date",
            extra={"proj_id": proj.proj_id, "proj_short_name": proj.proj_short_name},
        )

    project_activities = [t for t in schedule.activities if t.proj_id == proj.proj_id]
    if not project_activities:
        return _unknown(
            "no_activities",
            extra={"proj_id": proj.proj_id, "proj_short_name": proj.proj_short_name},
        )

    # ----- Signal extraction ---------------------------------------------
    signals = _extract_signals(project_activities, proj, data_date, schedule)

    # ----- Rule cascade ---------------------------------------------------
    # Order matters — earlier rules dominate. Each rule emits a rationale
    # carrying the signals AND the rule name so a forensic reviewer can
    # reconstruct the decision path post-hoc.
    return _classify(signals)


# --------------------------------------------------------------------- #
# Signal extraction                                                     #
# --------------------------------------------------------------------- #


def _extract_signals(
    project_activities: list[Task],
    proj: Project,
    data_date: datetime,
    schedule: ParsedSchedule,
) -> _Signals:
    """Compute the six numeric / boolean signals the rule cascade consumes."""
    plan_start = proj.plan_start_date
    plan_end = proj.plan_end_date or proj.scd_end_date

    elapsed_ratio: float | None = None
    if plan_start is not None and plan_end is not None and plan_end > plan_start:
        total = (plan_end - plan_start).total_seconds()
        elapsed = (data_date - plan_start).total_seconds()
        if total > 0:
            elapsed_ratio = elapsed / total
            # Negative elapsed (data_date before plan_start) collapses to 0 —
            # planning rule will then dominate.
            if elapsed_ratio < 0:
                elapsed_ratio = 0.0

    n = len(project_activities)
    # XER convention: phys_complete_pct is 0-100. Tasks default to 0.0 if
    # absent (per ParsedSchedule.Task). Treat the default as "not started".
    started = sum(1 for t in project_activities if t.phys_complete_pct > 0.0)
    completed = sum(1 for t in project_activities if t.phys_complete_pct >= 100.0)
    sum_phys = sum(t.phys_complete_pct for t in project_activities)

    # Procurement signal: activity codes whose name suggests procurement.
    # Conservative substring match — the goal is recall, not precision; the
    # rule cascade only considers this signal when other signals don't
    # already classify the project.
    proc_substrings = ("procur", "procure", "supply", "compras")
    has_procurement_codes = any(
        any(sub in (ac.actv_code_name or "").lower() for sub in proc_substrings)
        or any(sub in (ac.short_name or "").lower() for sub in proc_substrings)
        for ac in schedule.activity_codes
    )

    # Baseline availability proxy: any task carrying target_start_date and
    # target_end_date (XER baseline dates) signals a baselined schedule.
    # AACE RP 14R §3 anchors planning-phase identification on baseline
    # presence; absence of any target dates implies pre-baseline (planning).
    has_baseline_dates = any(
        t.target_start_date is not None and t.target_end_date is not None
        for t in project_activities
    )

    return _Signals(
        data_date=data_date,
        plan_start=plan_start,
        plan_end=plan_end,
        elapsed_ratio=elapsed_ratio,
        activity_count=n,
        started_pct=started / n if n > 0 else 0.0,
        completed_pct=completed / n if n > 0 else 0.0,
        mean_phys_complete=sum_phys / n if n > 0 else 0.0,
        has_procurement_codes=has_procurement_codes,
        has_baseline_dates=has_baseline_dates,
    )


# --------------------------------------------------------------------- #
# Classification cascade                                                #
# --------------------------------------------------------------------- #


def _classify(s: _Signals) -> LifecyclePhaseInference:
    """Apply the rule cascade. Order matters."""
    rationale_base: dict[str, Any] = {
        "elapsed_ratio": s.elapsed_ratio,
        "started_pct": round(s.started_pct, 4),
        "completed_pct": round(s.completed_pct, 4),
        "mean_phys_complete": round(s.mean_phys_complete, 4),
        "has_procurement_codes": s.has_procurement_codes,
        "has_baseline_dates": s.has_baseline_dates,
        "activity_count": s.activity_count,
    }

    # ----- Closeout (high confidence) ------------------------------------
    # Past plan_end and majority of activities complete: late-stage of the
    # project arc. Two paths to closeout to capture (i) on-schedule closeout
    # at plan_end and (ii) past-due-but-mostly-done closeout.
    if s.completed_pct >= 0.95 and (s.elapsed_ratio is None or s.elapsed_ratio >= 0.95):
        return _emit("closeout", 0.92, "majority_complete_late_in_baseline", rationale_base)
    if s.elapsed_ratio is not None and s.elapsed_ratio > 1.0 and s.mean_phys_complete >= 90.0:
        return _emit("closeout", 0.85, "past_plan_end_high_progress", rationale_base)

    # ----- Planning ------------------------------------------------------
    # Pre-baseline (no target dates anywhere) is the strongest planning
    # signal — AACE RP 14R §3.
    if not s.has_baseline_dates and s.started_pct < 0.05:
        return _emit("planning", 0.85, "no_baseline_no_actuals", rationale_base)

    # data_date at or before plan_start with no meaningful actuals: clearly
    # planning regardless of baseline state.
    if s.elapsed_ratio is not None and s.elapsed_ratio <= 0.02 and s.started_pct < 0.05:
        return _emit("planning", 0.80, "pre_or_at_plan_start", rationale_base)

    # ----- Procurement (mid-low actuals + procurement codes present) -----
    # Activity codes naming procurement are a strong taxonomy signal. Only
    # fire when actuals are still low — mid-construction projects often
    # carry procurement codes for residual long-leads but the project is
    # past procurement phase.
    if s.has_procurement_codes and s.started_pct < 0.25 and s.mean_phys_complete < 8.0:
        return _emit("procurement", 0.70, "procurement_codes_low_actuals", rationale_base)

    # ----- Design --------------------------------------------------------
    # Early elapsed window with very low actuals and no procurement signal:
    # the design phase typically precedes procurement codes appearing in the
    # WBS taxonomy.
    if (
        s.elapsed_ratio is not None
        and 0.02 < s.elapsed_ratio < 0.25
        and s.mean_phys_complete < 8.0
        and not s.has_procurement_codes
    ):
        return _emit("design", 0.65, "early_elapsed_low_actuals_no_procurement", rationale_base)

    # ----- Construction (the most common phase) --------------------------
    # Meaningful actuals across a wide elapsed band. Confidence scales with
    # how unambiguous the signal is — a project at 50% elapsed with 50%
    # actuals is more obviously construction than one at 5% elapsed with
    # 8% actuals (the latter could be late design / early construction).
    if s.started_pct >= 0.20 and 5.0 <= s.mean_phys_complete < 90.0:
        # Sharper signal in the middle of the construction band.
        center_distance = abs(s.mean_phys_complete - 50.0) / 50.0
        confidence = 0.65 + (1.0 - center_distance) * 0.20
        # Bound to keep below the closeout/planning confidence ceilings.
        confidence = min(0.85, max(0.55, confidence))
        return _emit("construction", confidence, "meaningful_actuals_mid_progress", rationale_base)

    # ----- Fallbacks (low confidence) ------------------------------------
    # No signal triggered a rule — emit our best guess with a warning-band
    # confidence so the W4 gate filter (>=0.80) excludes it. The UI will
    # surface the "low" band per ADR-0016 §UX so the user knows the
    # inference is uncertain.
    if s.elapsed_ratio is None:
        # No baseline plan dates → cannot anchor in time; planning is the
        # best low-confidence guess.
        return _emit("planning", 0.40, "fallback_no_plan_dates", rationale_base)
    if s.elapsed_ratio < 0.5:
        return _emit("design", 0.40, "fallback_early_elapsed", rationale_base)
    return _emit("construction", 0.45, "fallback_default_construction", rationale_base)


# --------------------------------------------------------------------- #
# Helpers                                                               #
# --------------------------------------------------------------------- #


def _emit(
    phase: LifecyclePhase,
    confidence: float,
    rule: str,
    rationale_base: dict[str, Any],
) -> LifecyclePhaseInference:
    rationale = dict(rationale_base)
    rationale["rule"] = rule
    return LifecyclePhaseInference(phase=phase, confidence=confidence, rationale=rationale)


def _unknown(reason: str, extra: dict[str, Any] | None = None) -> LifecyclePhaseInference:
    rationale: dict[str, Any] = {"rule": "unknown", "reason": reason}
    if extra:
        rationale.update(extra)
    return LifecyclePhaseInference(phase="unknown", confidence=0.0, rationale=rationale)
