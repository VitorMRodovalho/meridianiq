# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Cycle 4 W3 PR-A — unit tests for src/analytics/revision_trends.py.

Pins the analytics contract: per-revision curve extraction, CUSUM change-
point detection, heteroscedasticity-aware slope CI band. Defends against
the engine_version-style ADR drift class — the methodology citation
string is checked verbatim against the constant.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.analytics.revision_trends import (
    METHODOLOGY_CITATION,
    analyze_revision_trends,
    cusum_change_points,
    extract_actual_curve,
    extract_planned_curve,
    planned_finish_day,
    slope_with_horizon_ci,
)
from src.parser.models import ParsedSchedule, Project, Task


def _act(
    task_id: str,
    duration_hr: float,
    target_end_offset_days: int = 0,
    act_end_offset_days: int | None = None,
    base_date: datetime | None = None,
) -> Task:
    """Build a Task with target/actual end dates for curve testing.

    CPMCalculator reads ``remain_drtn_hr_cnt`` (line 147 of cpm.py) for
    duration — set both fields so tests don't rely on parser-side
    propagation.
    """
    base = base_date or datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Task(
        task_id=task_id,
        target_drtn_hr_cnt=duration_hr,
        remain_drtn_hr_cnt=duration_hr,
        target_end_date=base + timedelta(days=target_end_offset_days),
        act_end_date=(
            base + timedelta(days=act_end_offset_days) if act_end_offset_days is not None else None
        ),
    )


def _schedule_with_acts(activities: list[Task]) -> ParsedSchedule:
    """Build a minimal ParsedSchedule with activities + a single project."""
    sched = ParsedSchedule()
    sched.projects.append(
        Project(
            proj_id="1",
            proj_short_name="W3-TEST",
            last_recalc_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    sched.activities = activities
    return sched


# ── extract_planned_curve ─────────────────────────────────


def test_extract_planned_curve_empty_schedule_returns_empty() -> None:
    sched = ParsedSchedule()
    assert extract_planned_curve(sched) == []


def test_extract_planned_curve_monotonic_non_decreasing() -> None:
    """The cumulative curve is non-decreasing — never goes backwards."""
    acts = [_act(f"t{i}", duration_hr=8.0 * (i + 1)) for i in range(5)]
    sched = _schedule_with_acts(acts)
    curve = extract_planned_curve(sched)
    assert curve, "expected non-empty curve"
    pcts = [pct for _day, pct in curve]
    for i in range(1, len(pcts)):
        assert pcts[i] >= pcts[i - 1], f"curve dipped at index {i}"
    # Final point must be at or near 1.0 (within float tolerance)
    assert pcts[-1] >= 0.99


def test_extract_planned_curve_starts_at_zero_or_below_one() -> None:
    acts = [_act(f"t{i}", duration_hr=40.0) for i in range(3)]
    sched = _schedule_with_acts(acts)
    curve = extract_planned_curve(sched)
    assert curve[0][1] <= curve[-1][1]


# ── extract_actual_curve ──────────────────────────────────


def test_extract_actual_curve_no_actuals_returns_empty() -> None:
    acts = [_act(f"t{i}", duration_hr=40.0) for i in range(3)]
    sched = _schedule_with_acts(acts)
    curve = extract_actual_curve(sched, "2026-01-01")
    assert curve == []


def test_extract_actual_curve_with_actuals() -> None:
    acts = [
        _act("t1", duration_hr=40.0, act_end_offset_days=5),
        _act("t2", duration_hr=40.0, act_end_offset_days=10),
        _act("t3", duration_hr=40.0, act_end_offset_days=None),  # not yet finished
    ]
    sched = _schedule_with_acts(acts)
    curve = extract_actual_curve(sched, "2026-01-01")
    assert curve, "expected non-empty actual curve when ≥1 actual present"
    # Final pct should be 2/3 (two activities completed of three)
    assert abs(curve[-1][1] - 2 / 3) < 1e-6


# ── planned_finish_day ────────────────────────────────────


def test_planned_finish_day_returns_first_99_pct_crossing() -> None:
    curve = [(0, 0.0), (5, 0.5), (10, 0.99), (15, 1.0)]
    assert planned_finish_day(curve) == 10


def test_planned_finish_day_empty_returns_none() -> None:
    assert planned_finish_day([]) is None


# ── cusum_change_points ──────────────────────────────────


def test_cusum_too_short_returns_empty() -> None:
    assert cusum_change_points([10.0, 20.0]) == []


def test_cusum_zero_variance_returns_empty() -> None:
    assert cusum_change_points([5.0] * 10) == []


def test_cusum_detects_planted_step_change() -> None:
    """6 deltas with a step change at index 3 → CUSUM should flag it.

    Series: [10, 10, 10, 50, 50, 50] — constant + jump + constant.
    The CUSUM crosses threshold AT or AFTER the planted change at index 2-3
    (CUSUM accumulates negative-then-positive, peaks where the regime shifts).
    Threshold lowered to 2σ for sensitivity on this short synthetic series.
    """
    shifts = [10.0, 10.0, 10.0, 50.0, 50.0, 50.0]
    detections = cusum_change_points(shifts, threshold_multiplier=2.0)
    assert detections, f"expected ≥1 detection, got {detections}"
    detected_indices = [idx for idx, _ in detections]
    # CUSUM detects at the regime-shift boundary (index 2 — last "old" value
    # before the jump, where the cumulative deviation peaks). Accept index
    # ≥ 2 as evidence of detection.
    assert any(i >= 2 for i in detected_indices), (
        f"expected detection at or after the regime shift (index ≥ 2), "
        f"got indices {detected_indices}"
    )


def test_cusum_no_change_returns_empty_or_low() -> None:
    """Linear-trend series should not produce huge CUSUM values."""
    shifts = list(range(10))  # 0, 1, 2, ..., 9 — linear, no step
    detections = cusum_change_points([float(s) for s in shifts], threshold_multiplier=5.0)
    # 5σ on a quasi-linear signal — should not detect at default threshold
    assert detections == [] or all(abs(v) < 50 for _i, v in detections), (
        "CUSUM should not over-detect on linear trends at 5σ threshold"
    )


# ── slope_with_horizon_ci ────────────────────────────────


def test_slope_too_short_returns_none() -> None:
    assert slope_with_horizon_ci([5.0]) is None


def test_slope_constant_series_zero_slope() -> None:
    band = slope_with_horizon_ci([10.0, 10.0, 10.0, 10.0])
    assert band is not None
    assert abs(band.slope_days_per_revision) < 1e-6


def test_slope_increasing_series_positive_slope() -> None:
    band = slope_with_horizon_ci([10.0, 20.0, 30.0, 40.0, 50.0])
    assert band is not None
    assert band.slope_days_per_revision > 0


def test_slope_ci_widens_with_horizon() -> None:
    """CI band widens linearly in √horizon — heteroscedasticity contract."""
    series = [10.0, 12.0, 11.0, 14.0, 13.0, 16.0]
    band1 = slope_with_horizon_ci(series, horizon=1)
    band4 = slope_with_horizon_ci(series, horizon=4)
    assert band1 is not None and band4 is not None
    width1 = band1.ci_upper - band1.ci_lower
    width4 = band4.ci_upper - band4.ci_lower
    assert width4 > width1, "CI must widen with horizon (σ ∝ √horizon)"
    # √4 = 2 → width should approximately double
    ratio = width4 / max(1e-9, width1)
    assert 1.5 < ratio < 2.5, f"horizon=4 should ≈2× horizon=1 width, got {ratio:.2f}"


# ── methodology citation ─────────────────────────────────


def test_methodology_cites_aace_29r_03() -> None:
    """ADR drift defense — the citation string is checked verbatim."""
    assert "AACE RP 29R-03" in METHODOLOGY_CITATION
    assert "Window analysis" in METHODOLOGY_CITATION
    assert "CUSUM" in METHODOLOGY_CITATION
    assert "√horizon" in METHODOLOGY_CITATION or "sqrt(horizon)" in METHODOLOGY_CITATION
    assert "Forecast curve intentionally omitted" in METHODOLOGY_CITATION


# ── analyze_revision_trends orchestrator ─────────────────


def test_analyze_no_revisions_returns_empty_with_note() -> None:
    out = analyze_revision_trends(project_id="proj-A", program_id=None, revisions=[])
    assert out.curves == []
    assert out.change_points == []
    assert out.slope_band is None
    assert any("no revisions" in n for n in out.notes)


def test_analyze_single_revision_executes_marker_and_skips_slope() -> None:
    sched = _schedule_with_acts([_act(f"t{i}", duration_hr=40.0) for i in range(3)])
    out = analyze_revision_trends(
        project_id="proj-A",
        program_id="prog-1",
        revisions=[("proj-A", "rev-1", 1, "2026-01-01", sched)],
    )
    assert len(out.curves) == 1
    assert out.curves[0].is_executed is True
    assert out.slope_band is None
    assert any("slope band omitted" in n or "fewer than 2 finish" in n for n in out.notes)


def test_analyze_three_revisions_no_slope_no_cusum() -> None:
    """N=3 → 2 deltas → slope band undefined (df=0) per DA P3-5; no CUSUM."""
    revs = []
    for i in range(3):
        sched = _schedule_with_acts([_act(f"t{j}", duration_hr=40.0) for j in range(3)])
        dd_iso = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=30 * i)).isoformat()
        revs.append((f"proj-{i}", f"rev-{i}", i + 1, dd_iso, sched))
    out = analyze_revision_trends(project_id="proj-2", program_id="prog-1", revisions=revs)
    assert len(out.curves) == 3
    assert out.curves[-1].is_executed is True
    assert out.slope_band is None, "3 revisions = 2 deltas → df=0 → slope CI undefined per DA P3-5"


def test_analyze_four_revisions_emits_slope_band_no_cusum() -> None:
    """N=4 → 3 deltas → slope band emitted (df=1, minimum non-degenerate)."""
    revs = []
    for i in range(4):
        sched = _schedule_with_acts([_act(f"t{j}", duration_hr=40.0) for j in range(3)])
        dd_iso = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=30 * i)).isoformat()
        revs.append((f"proj-{i}", f"rev-{i}", i + 1, dd_iso, sched))
    out = analyze_revision_trends(project_id="proj-3", program_id="prog-1", revisions=revs)
    assert len(out.curves) == 4
    assert out.slope_band is not None
    assert any("CUSUM change-point detection skipped" in n for n in out.notes)


def test_analyze_only_latest_carries_executed_actuals() -> None:
    """Older revisions' actuals must be suppressed per ADR-0022 W3 spec."""
    revs = []
    for i in range(3):
        # All revisions have act_end_date populated, but only the latest
        # should expose actual_cumulative_pct values.
        acts = [_act(f"t{j}", duration_hr=40.0, act_end_offset_days=5 + j) for j in range(3)]
        sched = _schedule_with_acts(acts)
        dd_iso = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=30 * i)).isoformat()
        revs.append((f"proj-{i}", f"rev-{i}", i + 1, dd_iso, sched))
    out = analyze_revision_trends(project_id="proj-2", program_id="prog-1", revisions=revs)
    # Older revisions' points have actual_cumulative_pct == None
    older_actuals = [p.actual_cumulative_pct for c in out.curves[:-1] for p in c.points]
    assert all(a is None for a in older_actuals), (
        "Older revisions must NOT carry actual_cumulative_pct (ADR-0022 W3 spec)"
    )
    # Most recent revision carries some actual values
    latest_actuals = [
        p.actual_cumulative_pct
        for p in out.curves[-1].points
        if p.actual_cumulative_pct is not None
    ]
    assert latest_actuals, "Most recent revision should expose actual values"


def test_change_point_marker_direction_slip_when_local_delta_positive() -> None:
    """Issue #89 / DA P3-1 + DA exit-council P0 #1 fix on PR #104:
    direction is derived from sign(delta_days) of the LOCAL shift, NOT
    sign(cusum_value).

    Construction: shifts [200, 200, 40×6] (front-loaded HIGH). Mean=80;
    sigma=74.07; threshold=3σ=222.2. abs(cusum) > 222 fires at idx=1
    only (cumsum=+240). At idx=1 the LOCAL shift = +200 (this revision
    plans 200d LATER than prior = SLIP forensically).
    """
    finish_offsets = [10, 180, 350, 360, 370, 380, 390, 400, 410]
    revs = []
    for i, fd in enumerate(finish_offsets):
        sched = _schedule_with_acts([_act("t1", duration_hr=float(fd) * 8.0)])
        dd_iso = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=30 * i)).isoformat()
        revs.append((f"proj-{i}", f"rev-{i}", i + 1, dd_iso, sched))
    out = analyze_revision_trends(project_id="proj-A", program_id="prog-1", revisions=revs)
    assert out.change_points, f"expected CUSUM to fire; notes={out.notes}"
    # Sign-consistency contract per DA P0 #1 fix: direction = sign(delta_days).
    for cp in out.change_points:
        if cp.delta_days > 0:
            assert cp.direction == "slip", (
                f"delta_days={cp.delta_days} (>0) MUST map to 'slip', got {cp.direction!r}"
            )
        elif cp.delta_days < 0:
            assert cp.direction == "improvement"
        else:
            assert cp.direction == "flat"
    assert any(cp.direction == "slip" for cp in out.change_points), (
        "expected ≥1 'slip' direction in front-loaded-positive-shifts construction"
    )
    assert all(cp.direction in cp.description for cp in out.change_points)


def test_change_point_marker_direction_improvement_when_local_delta_negative() -> None:
    """Issue #89 / DA P3-1 + DA exit-council P0 #1 fix on PR #104:
    NEGATIVE local delta at change-point fires 'improvement' direction.

    Construction: shifts [-200, -200, 50×6] (front-loaded NEGATIVE — early
    revisions plan EARLIER finish than prior; later revisions slip 50d).
    Mean=-12.5; sigma=115.7; threshold=347.2. abs(cusum) > 347 fires at
    idx=1 (cumsum=-375). At idx=1 the LOCAL shift = -200 (this revision
    plans 200d EARLIER than prior = IMPROVEMENT forensically). To get
    shift=-200 via orchestrator (shift = 30 + fd-delta): fd-deltas =
    [-230, -230, 20×6]. Pick fd_0=500 so all fd values stay positive.
    """
    finish_offsets = [500, 270, 40, 60, 80, 100, 120, 140, 160]
    revs = []
    for i, fd in enumerate(finish_offsets):
        sched = _schedule_with_acts([_act("t1", duration_hr=float(fd) * 8.0)])
        dd_iso = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=30 * i)).isoformat()
        revs.append((f"proj-{i}", f"rev-{i}", i + 1, dd_iso, sched))
    out = analyze_revision_trends(project_id="proj-A", program_id="prog-1", revisions=revs)
    assert out.change_points, f"expected CUSUM to fire; notes={out.notes}"
    for cp in out.change_points:
        if cp.delta_days > 0:
            assert cp.direction == "slip"
        elif cp.delta_days < 0:
            assert cp.direction == "improvement", (
                f"delta_days={cp.delta_days} (<0) MUST map to 'improvement', got {cp.direction!r}"
            )
        else:
            assert cp.direction == "flat"
    assert any(cp.direction == "improvement" for cp in out.change_points), (
        "expected ≥1 'improvement' direction in front-loaded-negative-shifts construction"
    )


def test_change_point_marker_direction_decoupled_from_cusum_sign() -> None:
    """DA exit-council P0 #1 fix on PR #104: direction is decoupled from
    cusum_value sign (which is path-dependent), tied to local delta sign.

    Pinning regression: a CP where cusum_value < 0 BUT delta_days > 0
    MUST be labeled 'slip' (not 'improvement'). The earlier draft mapped
    from sign(cusum) which would inverted-label this revision.

    Construction: shifts [40×6, 200×2] (back-loaded HIGH). Cumsum drifts
    NEGATIVE on the early-low-shifts and stays negative through the
    late-high-shifts because cumsum-from-mean integral is below zero
    overall. At idx=5 cumsum=-240 (NEGATIVE), but shifts[5]=40 (POSITIVE
    — local slip). With the CORRECT semantic, direction='slip'. With the
    broken sign(cusum) semantic, direction would have been 'improvement'.
    """
    finish_offsets = [10, 20, 30, 40, 50, 60, 70, 240, 410]
    revs = []
    for i, fd in enumerate(finish_offsets):
        sched = _schedule_with_acts([_act("t1", duration_hr=float(fd) * 8.0)])
        dd_iso = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=30 * i)).isoformat()
        revs.append((f"proj-{i}", f"rev-{i}", i + 1, dd_iso, sched))
    out = analyze_revision_trends(project_id="proj-A", program_id="prog-1", revisions=revs)
    assert out.change_points, f"expected CUSUM to fire; notes={out.notes}"
    inverted_cases = [cp for cp in out.change_points if cp.cusum_value < 0 and cp.delta_days > 0]
    assert inverted_cases, (
        "test construction failed to produce a CP with cusum<0 + delta>0; "
        "rebalance shifts to surface the inversion case"
    )
    for cp in inverted_cases:
        assert cp.direction == "slip", (
            f"DA P0 #1 fix regression: cusum<0+delta>0 case must be 'slip' "
            f"(local slip dominant), got {cp.direction!r}"
        )


def test_analyze_curves_ordered_by_data_date() -> None:
    """Caller is responsible for ascending data_date order; verify it survives."""
    revs = []
    iso_a = "2026-03-01T00:00:00+00:00"
    iso_b = "2026-04-01T00:00:00+00:00"
    iso_c = "2026-05-01T00:00:00+00:00"
    for pid, dd_iso in [("p1", iso_a), ("p2", iso_b), ("p3", iso_c)]:
        sched = _schedule_with_acts([_act(f"t{i}", duration_hr=40.0) for i in range(2)])
        revs.append((pid, None, None, dd_iso, sched))
    out = analyze_revision_trends(project_id="p3", program_id="prog-1", revisions=revs)
    assert [c.data_date for c in out.curves] == [iso_a, iso_b, iso_c]
