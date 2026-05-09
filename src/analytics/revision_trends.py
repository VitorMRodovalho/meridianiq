# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Multi-revision schedule trend analysis (Cycle 4 W3 PR-A).

Implements **AACE RP 29R-03 Forensic Schedule Analysis §"Window analysis"
multi-revision overlay** primitive: extracts the planned-completion-percent
S-curve from each successive revision of a project, detects regime
changes via CUSUM, and surfaces slope CI bands with the
heteroscedasticity-aware contract per ADR-0022 §"W3 — C-visualization".

## Why CPM-based completion curves, NOT cashflow

Backend-reviewer entry-council on PR #N flagged that
``src.analytics.cashflow.analyze_cashflow`` produces a cost-mass-weighted
S-curve (with duration-as-proxy fallback when cost data is missing).
Window Analysis (AACE 29R-03) is **completion-percent-weighted**: the
curve point at day D is "what fraction of the schedule was planned to be
complete at day D, by activity count or duration-weighted activity
count". This module computes that directly from CPM ``early_finish``
output — no cost dependency.

## Methodology citation surfaced in the response

``"AACE RP 29R-03 — Forensic Schedule Analysis, §'Window analysis'
(multi-revision overlay); CUSUM change-point detection (Page 1954);
heteroscedasticity-aware OLS with σ ∝ √horizon. Forecast curve
intentionally omitted pending W4 calibration gate (ADR-0022 path-A
pre-commitment)."``

## Pure-numpy implementation

scipy is NOT in the dependency set (per ``pyproject.toml`` and verified
by grep across ``src/``). CUSUM is 5 lines of ``numpy.cumsum``; OLS for
the slope band is closed-form via ``numpy.polyfit``. Future migration to
scipy.stats would be a separate dep-add ADR.

## What this module does NOT do (W3 scope discipline)

- Does NOT produce a forecast curve (path-A pre-commit per ADR-0022 W4).
- Does NOT calibrate the heuristic (W4 deliverable).
- Does NOT cache responses (W2-coupling concern; future follow-up).
- Does NOT re-rank candidates by content_hash similarity (W3+ deferral
  per ADR-0022 Amendment 2).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import numpy as np

from src.analytics.cpm import CPMCalculator

if TYPE_CHECKING:
    from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


METHODOLOGY_CITATION = (
    "AACE RP 29R-03 §'Window analysis' (multi-revision overlay primitive). "
    "CUSUM change-point per Page (1954, Biometrika 41) — applied as a "
    "separate exploratory SPC layer, NOT prescribed by AACE 29R-03. "
    "Heteroscedasticity-aware OLS slope band with σ ∝ √horizon (ADR-0022 "
    "§'W3 — C-visualization' simple model). Forecast curve intentionally "
    "omitted pending W4 calibration gate per ADR-0022 path-A pre-commitment."
)
"""DA exit-council fix-up #P1-2: split AACE 29R-03 (Window Analysis primitive)
from Page (1954) CUSUM (separate SPC layer) so the methodology line
does not imply AACE prescribes the CUSUM convention.
"""

# Minimum revision count for CUSUM emission. With N=3 revisions there
# are only 2 deltas; sample std on 2 points is degenerate. Backend-
# reviewer entry-council recommended N≥5 as the "informative-but-not-
# powered" threshold for heuristic emission.
_MIN_REVISIONS_FOR_CUSUM = 5
# DA exit-council fix-up #P3-5: bumped from 3 to 4. With 3 revisions
# (2 deltas) OLS gives slope but residual variance is undefined (df=0),
# producing a zero-width CI that the UI would mis-render as confident.
# 4 revisions (3 deltas) gives df=1 — minimum non-degenerate fit.
_MIN_REVISIONS_FOR_SLOPE = 4
# DA exit-council fix-up #P1-3: lowered from 5σ to 3σ. 5σ on N=4-11 deltas
# gives ARL ~10000+ — the detector essentially never fires (the unit
# test had to drop to 2σ to fire). 3σ is more sensitive while still
# ARL-conservative (~370 in classical CUSUM). Honest signal beats
# theoretically-pure-but-mute.
_CUSUM_SIGMA_THRESHOLD = 3.0


@dataclass
class CurvePoint:
    """One point on a per-revision completion curve."""

    day_offset: int
    """Days from the revision's ``data_date``."""

    planned_cumulative_pct: float
    """Fraction in [0.0, 1.0] of activities planned to be complete by this day."""

    actual_cumulative_pct: float | None = None
    """Fraction in [0.0, 1.0] of activities ACTUALLY complete by this day.

    Populated only on the most recent revision (the "executed" view) per
    ADR-0022 W3 spec. Older revisions have ``actual_cumulative_pct=None`` —
    suppressed to avoid past-actuals-vs-past-planned confusion.
    """


@dataclass
class RevisionCurve:
    """Per-revision S-curve metadata + points."""

    project_id: str
    revision_id: str | None = None
    """``revision_history.id`` if the project has been confirmed-as-revision; None for pre-W1 / unconfirmed."""
    revision_number: int | None = None
    data_date: str | None = None
    """ISO-8601 date string of the schedule's data_date."""
    points: list[CurvePoint] = field(default_factory=list)
    is_executed: bool = False
    """True only for the most recent revision (carries the actual_cumulative_pct values)."""


@dataclass
class ChangePointMarker:
    """A revision index where the CUSUM crossed the threshold."""

    revision_index: int
    """0-based position in the time-ordered revision list."""

    revision_id: str | None
    delta_days: int
    """Signed days difference from the prior revision's planned_finish."""
    cusum_value: float
    description: str
    direction: str
    """``"slip"`` when ``cusum_value > 0`` (accumulated above-mean drift =
    later finish than the trend); ``"improvement"`` when ``cusum_value < 0``
    (accumulated below-mean drift = earlier finish than the trend); ``"flat"``
    only when ``cusum_value == 0`` (which the threshold would not cross —
    included for type-completeness). UI surfaces "improvement" in green,
    "slip" in amber. Issue #89 / DA P3-1 from PR #88."""


@dataclass
class SlopeBand:
    """Heteroscedasticity-aware OLS slope of the inter-revision shift series."""

    slope_days_per_revision: float
    ci_lower: float
    ci_upper: float
    horizon_revisions: int
    """How many revisions ahead the CI was widened for (sigma ∝ √horizon)."""


@dataclass
class RevisionTrendsAnalysis:
    """Top-level analysis output for the /revision-trends endpoint."""

    project_id: str
    program_id: str | None
    curves: list[RevisionCurve] = field(default_factory=list)
    """Ordered by ``data_date`` ascending. Most recent has ``is_executed=True``."""
    change_points: list[ChangePointMarker] = field(default_factory=list)
    slope_band: SlopeBand | None = None
    methodology: str = METHODOLOGY_CITATION
    notes: list[str] = field(default_factory=list)
    """Free-form operator-facing strings (e.g., '<5 revisions — change-point detection skipped')."""


# ── Curve extraction ──────────────────────────────────────


def extract_planned_curve(schedule: "ParsedSchedule") -> list[tuple[int, float]]:
    """Return the planned completion-percent S-curve as ``(day_offset, pct)`` pairs.

    Computes from CPM ``early_finish`` per activity. Day 0 is the start of
    the schedule's earliest activity; ``pct`` at day D is the fraction of
    activities whose ``early_finish <= D`` (activity-count weighted).

    Per AACE 29R-03 Window Analysis, this is the "planned completion
    percent at data date" projected forward — the canonical Window
    Analysis curve.

    Returns an empty list on CPM failure or empty schedule (defensive;
    the orchestrator MUST handle empty-curve cases without raising).
    """
    if not schedule.activities:
        return []
    try:
        cpm = CPMCalculator(schedule).calculate()
    except Exception:  # noqa: BLE001 — CPM failures degrade to empty curve
        logger.warning("revision_trends: CPM failed; planned curve unavailable")
        return []
    if not cpm.activity_results:
        return []
    # DA exit-council fix-up #P1-1: do NOT filter ``early_finish > 0``.
    # CPM (cpm.py:148) sets duration=0 for tasks with
    # ``status_code == 'TK_Complete'``. Filtering them silently broke
    # the curve for every progressed schedule — a 60%-complete project
    # with 100 activities computed total=40 (only the incomplete ones),
    # producing a curve normalized to the wrong base. Including them
    # makes the curve correctly show "X% complete at day 0" plus the
    # planned ramp-up of the remaining work.
    finishes = [ar.early_finish for ar in cpm.activity_results.values()]
    if not finishes:
        return []
    total = len(finishes)
    duration = int(max(finishes)) + 1
    finishes_sorted = sorted(finishes)
    # Sweep day-by-day, count cumulative completions.
    points: list[tuple[int, float]] = []
    idx = 0
    for day in range(duration + 1):
        while idx < total and finishes_sorted[idx] <= day:
            idx += 1
        points.append((day, idx / total))
    return points


def extract_actual_curve(
    schedule: "ParsedSchedule", data_date_iso: str | None
) -> list[tuple[int, float]]:
    """Return the actual completion-percent S-curve from ``act_end_date`` per activity.

    Day 0 is the schedule's ``data_date``. ``pct`` at day D is the
    fraction of activities with ``act_end_date <= data_date + D days``.

    **Pre-data-date completions are clamped to day 0** — activities that
    finished BEFORE the data_date count as already-complete at the start
    of the curve. Without this clamp, the synthetic case where a re-
    uploaded XER has actuals predating its data_date silently produces
    an empty curve (filter dropped all negatives), defeating the
    "executed view" UX. The visualization treats day 0 as "starting
    point of the data-date window"; pre-existing completions show as
    a non-zero starting value.

    Returns empty list when no actuals are available — older XERs without
    progress data degrade gracefully.
    """
    if not schedule.activities or not data_date_iso:
        return []
    try:
        data_date = datetime.fromisoformat(data_date_iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return []
    actuals: list[float] = []
    for task in schedule.activities:
        end = task.act_end_date
        if end is None:
            continue
        # Normalize to naive UTC for arithmetic comparison.
        if end.tzinfo is None:
            end_naive = end
        else:
            end_naive = end.astimezone(data_date.tzinfo).replace(tzinfo=None)
        dd_naive = data_date.replace(tzinfo=None)
        delta_days = (end_naive - dd_naive).total_seconds() / 86400.0
        # Clamp pre-data-date completions to day 0 — they're already done.
        actuals.append(max(0.0, delta_days))
    if not actuals:
        return []
    total = len(schedule.activities)
    actuals_sorted = sorted(actuals)
    duration = int(max(actuals_sorted)) + 1
    points: list[tuple[int, float]] = []
    idx = 0
    for day in range(duration + 1):
        while idx < len(actuals_sorted) and actuals_sorted[idx] <= day:
            idx += 1
        points.append((day, idx / total))
    return points


def planned_finish_day(planned_curve: list[tuple[int, float]]) -> int | None:
    """Return the day at which planned cumulative crosses 100% (or last day).

    For curves that don't reach 100% (e.g., CPM with unresolved cycles),
    returns the last day in the curve as the best-effort proxy.
    """
    if not planned_curve:
        return None
    for day, pct in planned_curve:
        if pct >= 0.99:
            return day
    return planned_curve[-1][0]


# ── CUSUM change-point detection (pure numpy) ─────────────


def cusum_change_points(
    shift_series: list[float],
    threshold_multiplier: float = _CUSUM_SIGMA_THRESHOLD,
) -> list[tuple[int, float]]:
    """Pure-numpy CUSUM detection on the inter-revision shift series.

    Returns ``[(index, cusum_value), …]`` for each index where the
    upward or downward CUSUM crossed ``threshold_multiplier × sigma``.
    Threshold convention: Page (1954) "moderate sensitivity" default.

    Empty list if the series is too short (< _MIN_REVISIONS_FOR_CUSUM)
    or has zero variance.
    """
    arr = np.asarray(shift_series, dtype=float)
    if arr.size < _MIN_REVISIONS_FOR_CUSUM - 1:
        return []
    sigma = float(arr.std(ddof=1))
    if sigma <= 0.0:
        return []
    threshold = threshold_multiplier * sigma
    mean = float(arr.mean())
    centered = arr - mean
    cusum = np.cumsum(centered)
    detections: list[tuple[int, float]] = []
    for i, v in enumerate(cusum):
        if abs(v) >= threshold:
            detections.append((int(i), float(v)))
    return detections


# ── Heteroscedasticity-aware slope CI (pure numpy) ────────


def slope_with_horizon_ci(
    shift_series: list[float],
    horizon: int = 1,
    z: float = 1.96,
) -> SlopeBand | None:
    """Closed-form OLS slope on the shift series with horizon-scaled CI.

    Per ADR-0022 §"W3 — C-visualization": variance grows ∝ √horizon.
    The returned ``ci_lower``/``ci_upper`` widen linearly in √horizon.

    Returns ``None`` when the series is shorter than
    ``_MIN_REVISIONS_FOR_SLOPE - 1`` deltas (i.e., < 2 deltas → can't
    compute residual variance).
    """
    arr = np.asarray(shift_series, dtype=float)
    n = arr.size
    if n < _MIN_REVISIONS_FOR_SLOPE - 1:
        return None
    x = np.arange(n, dtype=float)
    # OLS slope via numpy.polyfit (closed-form, no scipy dep).
    if n <= 2:
        # DA exit-council fix-up #P3-5: degenerate — can't compute residual
        # variance with df = n - 2 = 0. Returning slope == ci_lower == ci_upper
        # (zero-width CI band) would mis-render in UI as high confidence.
        # Return None so the orchestrator emits an explicit "<3 revisions —
        # slope CI undefined" note instead.
        return None
    slope, intercept = np.polyfit(x, arr, 1)
    # Residual std for CI.
    fitted = slope * x + intercept
    residuals = arr - fitted
    sigma_res = float(np.sqrt(np.sum(residuals**2) / (n - 2)))
    # Standard error of the slope.
    sx2 = float(np.sum((x - x.mean()) ** 2))
    if sx2 <= 0.0:
        return None
    se_slope = sigma_res / np.sqrt(sx2)
    # Heteroscedasticity scaling: variance ∝ √horizon → SE widens with √horizon.
    se_at_horizon = se_slope * float(np.sqrt(max(1, horizon)))
    margin = z * se_at_horizon
    return SlopeBand(
        slope_days_per_revision=float(slope),
        ci_lower=float(slope - margin),
        ci_upper=float(slope + margin),
        horizon_revisions=horizon,
    )


# ── Orchestrator ──────────────────────────────────────────


def analyze_revision_trends(
    *,
    project_id: str,
    program_id: str | None,
    revisions: list[tuple[str, str | None, int | None, str | None, "ParsedSchedule"]],
) -> RevisionTrendsAnalysis:
    """Build a complete RevisionTrendsAnalysis from per-revision schedules.

    ``revisions`` is a list of ``(project_id, revision_id, revision_number,
    data_date_iso, schedule)`` tuples — caller MUST sort ascending by
    ``data_date``. Caller is responsible for RLS-scoped fetches via
    ``store.get_project(pid, user_id=user_id)`` + ``list_revision_history_by_program``.

    The most-recent revision (last in the list) gets the executed curve;
    older revisions only get planned curves.
    """
    out = RevisionTrendsAnalysis(project_id=project_id, program_id=program_id)

    if not revisions:
        out.notes.append("no revisions in program — empty analysis")
        return out

    # Per-revision curve extraction.
    finish_days: list[float] = []
    for i, (rid_proj, rev_id, rev_num, dd_iso, sched) in enumerate(revisions):
        is_latest = i == len(revisions) - 1
        planned = extract_planned_curve(sched)
        actual = extract_actual_curve(sched, dd_iso) if is_latest else []
        actual_by_day = {d: pct for d, pct in actual}
        curve_points = [
            CurvePoint(
                day_offset=day,
                planned_cumulative_pct=pct,
                actual_cumulative_pct=actual_by_day.get(day) if is_latest else None,
            )
            for day, pct in planned
        ]
        out.curves.append(
            RevisionCurve(
                project_id=rid_proj,
                revision_id=rev_id,
                revision_number=rev_num,
                data_date=dd_iso,
                points=curve_points,
                is_executed=is_latest,
            )
        )
        fd = planned_finish_day(planned)
        if fd is not None and dd_iso is not None:
            try:
                base = datetime.fromisoformat(dd_iso.replace("Z", "+00:00"))
                absolute_finish_day = (base + timedelta(days=fd)).toordinal()
                finish_days.append(float(absolute_finish_day))
            except (ValueError, TypeError):
                pass

    if len(finish_days) < 2:
        out.notes.append("fewer than 2 finish-day samples — change-point + slope omitted")
        return out

    # Inter-revision shift series (signed deltas in days).
    shifts = [float(finish_days[i] - finish_days[i - 1]) for i in range(1, len(finish_days))]

    # Slope band (requires >= 2 deltas i.e. >= 3 revisions).
    if len(shifts) >= _MIN_REVISIONS_FOR_SLOPE - 1:
        out.slope_band = slope_with_horizon_ci(shifts, horizon=1)
    else:
        out.notes.append("<3 revisions — slope band omitted")

    # CUSUM change-points (requires >= 4 deltas i.e. >= 5 revisions).
    if len(shifts) >= _MIN_REVISIONS_FOR_CUSUM - 1:
        for idx, cusum_val in cusum_change_points(shifts):
            # idx is 0-based in the shifts series → revision_index in curves
            # is idx + 1 (the revision AFTER the prior).
            rev_index = idx + 1
            rev_curve = out.curves[rev_index]
            # Direction per issue #89 / DA P3-1: sign(cusum_value).
            # cusum_value > 0 = accumulated above-mean drift = SLIP.
            # cusum_value < 0 = accumulated below-mean drift = IMPROVEMENT.
            direction = "slip" if cusum_val > 0 else "improvement" if cusum_val < 0 else "flat"
            out.change_points.append(
                ChangePointMarker(
                    revision_index=rev_index,
                    revision_id=rev_curve.revision_id,
                    delta_days=int(shifts[idx]),
                    cusum_value=cusum_val,
                    direction=direction,
                    description=(
                        f"shift of {int(shifts[idx])} days vs prior revision; "
                        f"CUSUM={cusum_val:.1f} crosses {_CUSUM_SIGMA_THRESHOLD}σ "
                        f"threshold — regime change detected ({direction})"
                    ),
                )
            )
    else:
        out.notes.append(
            f"<{_MIN_REVISIONS_FOR_CUSUM} revisions — CUSUM change-point detection skipped"
        )

    return out


__all__: list[str] = [
    "CurvePoint",
    "RevisionCurve",
    "ChangePointMarker",
    "SlopeBand",
    "RevisionTrendsAnalysis",
    "METHODOLOGY_CITATION",
    "extract_planned_curve",
    "extract_actual_curve",
    "planned_finish_day",
    "cusum_change_points",
    "slope_with_horizon_ci",
    "analyze_revision_trends",
]
