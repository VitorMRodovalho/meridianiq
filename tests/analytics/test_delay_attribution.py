# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for delay attribution engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.analytics.delay_attribution import (
    AttributionResult,
    compute_delay_attribution,
)
from src.api.app import app
from src.parser.models import Calendar, ParsedSchedule, Relationship, Task


def _make_schedule(
    tasks: list[Task] | None = None,
    rels: list[Relationship] | None = None,
) -> ParsedSchedule:
    return ParsedSchedule(
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8, week_hr_cnt=40, default_flag="Y")],
        activities=tasks or [],
        relationships=rels or [],
    )


class TestWithTIAData:
    """When TIA results are available, use explicit party assignments."""

    def test_tia_attribution(self) -> None:
        schedule = _make_schedule()
        tia = {
            "total_owner_delay": 30.0,
            "total_contractor_delay": 15.0,
            "total_shared_delay": 5.0,
            "total_third_party_delay": 0.0,
            "total_force_majeure_delay": 10.0,
        }
        result = compute_delay_attribution(schedule, tia_results=tia)
        assert result.data_source == "tia"
        assert result.total_delay_days == 60.0
        assert result.excusable_days == 45.0
        assert result.non_excusable_days == 15.0
        assert result.concurrent_days == 5.0
        assert len(result.parties) == 4  # zero-delay parties excluded

    def test_tia_owner_only(self) -> None:
        schedule = _make_schedule()
        tia = {
            "total_owner_delay": 20.0,
            "total_contractor_delay": 0.0,
        }
        result = compute_delay_attribution(schedule, tia_results=tia)
        assert result.data_source == "tia"
        assert len(result.parties) == 1
        assert result.parties[0].party == "Owner"
        assert result.parties[0].pct_of_total == 100.0

    def test_tia_zero_delay(self) -> None:
        schedule = _make_schedule()
        tia = {
            "total_owner_delay": 0.0,
            "total_contractor_delay": 0.0,
        }
        result = compute_delay_attribution(schedule, tia_results=tia)
        assert result.total_delay_days == 0.0
        assert len(result.parties) == 0


class TestEstimatedAttribution:
    """Without TIA, attribution is heuristic-based."""

    def test_no_delay_no_baseline(self) -> None:
        tasks = [
            Task(task_id="A1", status_code="TK_Active", task_type="TT_Task"),
        ]
        result = compute_delay_attribution(_make_schedule(tasks))
        assert result.data_source == "estimated"
        # No negative float = no detected delay
        assert result.total_delay_days == 0.0

    def test_negative_float_detected(self) -> None:
        tasks = [
            Task(
                task_id="A1",
                status_code="TK_Active",
                task_type="TT_Task",
                total_float_hr_cnt=-40.0,  # 5 days negative float
            ),
        ]
        result = compute_delay_attribution(_make_schedule(tasks))
        assert result.data_source == "estimated"
        assert result.total_delay_days > 0

    def test_constraint_tasks_attributed_to_owner(self) -> None:
        tasks = [
            Task(
                task_id="A1",
                status_code="TK_Active",
                task_type="TT_Task",
                total_float_hr_cnt=-80.0,
                cstr_type="CS_MFNLT",  # Must Finish No Later Than
            ),
        ]
        result = compute_delay_attribution(_make_schedule(tasks))
        owner_party = next((p for p in result.parties if p.party == "Owner"), None)
        assert owner_party is not None
        assert owner_party.delay_days > 0


class TestMethodology:
    """Result includes methodology."""

    def test_methodology_present(self) -> None:
        result = compute_delay_attribution(_make_schedule())
        assert "AACE" in result.methodology
        assert "SCL" in result.methodology


# ------------------------------------------------------------------ #
# Baseline path — regression suite for issue #222.                    #
#                                                                     #
# The baseline branch shipped 2026-04-06 with zero coverage and       #
# raised AttributeError on every call for ~5 months behind a green    #
# suite. These tests pin the VALUE, not merely the absence of a       #
# crash, and TestBaselineParameterMatrix makes the "an optional       #
# parameter branch was never exercised" class structurally hard to    #
# repeat for this function.                                           #
# ------------------------------------------------------------------ #


def _task(
    tid: str,
    *,
    end: datetime | None = None,
    task_type: str = "TT_Task",
    float_hr: float | None = None,
    end_field: str = "early_end_date",
) -> Task:
    """Build a Task carrying a single finish date on the named field."""
    kwargs: dict[str, object] = {
        "task_id": tid,
        "task_code": tid,
        "task_name": f"Activity {tid}",
        "task_type": task_type,
        "status_code": "TK_NotStart",
        "total_float_hr_cnt": float_hr,
    }
    if end is not None:
        kwargs[end_field] = end
    return Task(**kwargs)  # type: ignore[arg-type]


class TestBaselineFinishSlip:
    """Baseline path computes calendar slip of projected completion."""

    def test_slip_is_calendar_days_between_finishes(self) -> None:
        # Arrange
        baseline = _make_schedule([_task("A", end=datetime(2026, 1, 1))])
        update = _make_schedule([_task("A", end=datetime(2026, 1, 11))])

        # Act
        result = compute_delay_attribution(update, baseline=baseline)

        # Assert
        assert result.total_delay_days == 10.0
        assert result.delay_basis == "baseline_finish_slip"

    def test_acceleration_does_not_fall_through_to_float_proxy(self) -> None:
        """A baseline showing no slip must not be overwritten by the proxy.

        The update carries negative float on purpose: without it this test
        passes vacuously. With it, it is the only assertion pinning the
        control-flow decision that a resolved baseline wins.
        """
        # Arrange — update finishes 10 days EARLIER than baseline
        baseline = _make_schedule([_task("A", end=datetime(2026, 1, 11))])
        update = _make_schedule([_task("A", end=datetime(2026, 1, 1), float_hr=-80.0)])

        # Act
        result = compute_delay_attribution(update, baseline=baseline)

        # Assert — floored at 0, NOT 10.0 conjured from the float proxy
        assert result.total_delay_days == 0.0
        assert result.delay_basis == "baseline_finish_slip"

    def test_zero_slip_is_reported_as_zero(self) -> None:
        # Arrange
        baseline = _make_schedule([_task("A", end=datetime(2026, 1, 1))])
        update = _make_schedule([_task("A", end=datetime(2026, 1, 1), float_hr=-80.0)])

        # Act
        result = compute_delay_attribution(update, baseline=baseline)

        # Assert
        assert result.total_delay_days == 0.0
        assert result.delay_basis == "baseline_finish_slip"

    def test_timezone_aware_and_naive_inputs_do_not_raise(self) -> None:
        """A stored schedule is TIMESTAMPTZ-aware; an XER re-parse is naive.

        One request can mix the two, and subtracting them raises TypeError.
        """
        # Arrange
        baseline = _make_schedule([_task("A", end=datetime(2026, 1, 1))])
        update = _make_schedule([_task("A", end=datetime(2026, 1, 11, tzinfo=timezone.utc))])

        # Act
        result = compute_delay_attribution(update, baseline=baseline)

        # Assert
        assert result.total_delay_days == 10.0

    def test_nonzero_utc_offset_does_not_shift_the_day(self) -> None:
        """A UTC-offset test cannot detect a day shift; this one can.

        P6 dates are wall-clock local. Converting an aware midnight value to
        UTC can move it across midnight and change the day count by one.
        """
        # Arrange — midnight at +03:00 is the fragile case
        tz = timezone(timedelta(hours=3))
        baseline = _make_schedule([_task("A", end=datetime(2026, 1, 1, 0, 0, tzinfo=tz))])
        update = _make_schedule([_task("A", end=datetime(2026, 1, 11, 0, 0, tzinfo=tz))])

        # Act
        result = compute_delay_attribution(update, baseline=baseline)

        # Assert — both sides shift identically, so the span is preserved
        assert result.total_delay_days == 10.0

    def test_time_of_day_does_not_truncate_the_slip(self) -> None:
        """P6 finishes land at 17:00 and starts at 08:00 — 15h is one day."""
        # Arrange
        baseline = _make_schedule([_task("A", end=datetime(2026, 1, 1, 17, 0))])
        update = _make_schedule([_task("A", end=datetime(2026, 1, 2, 8, 0))])

        # Act
        result = compute_delay_attribution(update, baseline=baseline)

        # Assert — raw timedelta.days would be 0
        assert result.total_delay_days == 1.0

    def test_level_of_effort_activities_are_excluded(self) -> None:
        """Hammocks span past the finish milestone and fake delay."""
        # Arrange
        baseline = _make_schedule([_task("A", end=datetime(2026, 1, 1))])
        update = _make_schedule(
            [
                _task("A", end=datetime(2026, 1, 1)),
                _task("LOE", end=datetime(2026, 6, 1), task_type="TT_LOE"),
            ]
        )

        # Act
        result = compute_delay_attribution(update, baseline=baseline)

        # Assert
        assert result.total_delay_days == 0.0
        # Without this the test passes even if _resolve_project_finish is
        # broken enough to return None for every schedule.
        assert result.delay_basis == "baseline_finish_slip"

    def test_unresolvable_baseline_degrades_visibly(self) -> None:
        """No resolvable dates must fall back AND say so."""
        # Arrange — baseline activities carry no end date at all
        baseline = _make_schedule([_task("A")])
        update = _make_schedule([_task("A", end=datetime(2026, 1, 1), float_hr=-80.0)])

        # Act
        result = compute_delay_attribution(update, baseline=baseline)

        # Assert — 80 negative float hours / 8h day = 10 days
        assert result.delay_basis == "negative_float_proxy"
        assert result.total_delay_days == 10.0

    def test_actual_finish_outranks_forecast(self) -> None:
        """P6 Finish semantics: actual beats early beats target."""
        # Arrange
        baseline = _make_schedule([_task("A", end=datetime(2026, 1, 1))])
        update = _make_schedule(
            [
                Task(
                    task_id="A",
                    task_code="A",
                    task_type="TT_Task",
                    status_code="TK_Complete",
                    act_end_date=datetime(2026, 1, 6),
                    early_end_date=datetime(2026, 1, 20),
                    target_end_date=datetime(2026, 1, 30),
                )
            ]
        )

        # Act
        result = compute_delay_attribution(update, baseline=baseline)

        # Assert — reads the actual (5d slip), not the stale forecast (19d)
        assert result.total_delay_days == 5.0


class TestUnattributedQuantum:
    """A delay quantum must never be reported with nobody holding it.

    DA exit-council P0 on PR #234. When a real slip exists but no indicator
    predicate matches, the heuristic has nothing to apportion. Before this
    guard the engine returned parties=[] alongside a non-zero total, so the
    UI rendered "47d Total Delay" directly above "No delay detected -
    schedule is on track", and the AACE/SCL PDFs printed "attribution not
    supplied" for a computation that had produced a number. Same defect
    class as #224.
    """

    def _as_built(self, end: datetime) -> ParsedSchedule:
        """A fully-statused as-built: every predicate excludes TK_Complete."""
        return _make_schedule(
            [
                Task(
                    task_id="A",
                    task_code="A",
                    task_type="TT_Task",
                    status_code="TK_Complete",
                    act_end_date=end,
                )
            ]
        )

    def test_slip_with_no_matching_indicator_is_unattributed(self) -> None:
        # Arrange — the flagship baseline-vs-as-built forensic comparison
        baseline = self._as_built(datetime(2026, 1, 1))
        update = self._as_built(datetime(2026, 2, 17))

        # Act
        result = compute_delay_attribution(update, baseline=baseline)

        # Assert
        assert result.total_delay_days == 47.0
        assert len(result.parties) == 1
        assert result.parties[0].party == "Unattributed"
        assert result.parties[0].delay_days == 47.0
        assert result.parties[0].pct_of_total == 100.0

    def test_a_quantum_is_never_rendered_as_no_delay(self) -> None:
        """The frontend gates its 'no delay' banner on parties being empty."""
        # Arrange
        baseline = self._as_built(datetime(2026, 1, 1))
        update = self._as_built(datetime(2026, 2, 17))

        # Act
        result = compute_delay_attribution(update, baseline=baseline)

        # Assert — non-zero total with empty parties must be unrepresentable
        assert not (result.total_delay_days > 0 and not result.parties)


class TestSourcePrecedence:
    """TIA data outranks a supplied baseline."""

    def test_tia_wins_over_baseline(self) -> None:
        # Arrange
        baseline = _make_schedule([_task("A", end=datetime(2026, 1, 1))])
        update = _make_schedule([_task("A", end=datetime(2026, 1, 11))])
        tia = {"total_owner_delay": 30.0, "total_contractor_delay": 15.0}

        # Act
        result = compute_delay_attribution(update, baseline=baseline, tia_results=tia)

        # Assert — the baseline's 10-day slip is ignored
        assert result.data_source == "tia"
        assert result.delay_basis == "tia"
        assert result.total_delay_days == 45.0


class TestBaselineParameterMatrix:
    """Every (baseline, tia_results) combination must hold the invariants.

    This is the anti-recurrence mechanism: #222 existed because one cell of
    this matrix was never instantiated. Parametrizing makes "we forgot to
    pass a kwarg" structurally impossible for this function.
    """

    _VALID_BASES = {"tia", "baseline_finish_slip", "negative_float_proxy", "none"}

    @pytest.mark.parametrize("with_baseline", [False, True], ids=["no_base", "base"])
    @pytest.mark.parametrize("with_tia", [False, True], ids=["no_tia", "tia"])
    def test_invariants_hold(self, with_baseline: bool, with_tia: bool) -> None:
        # Arrange
        update = _make_schedule(
            [
                _task("A", end=datetime(2026, 1, 11), float_hr=-80.0),
                _task("B", end=datetime(2026, 1, 5), float_hr=16.0),
            ]
        )
        baseline = _make_schedule([_task("A", end=datetime(2026, 1, 1))]) if with_baseline else None
        tia = {"total_owner_delay": 30.0, "total_contractor_delay": 15.0} if with_tia else None

        # Act
        result = compute_delay_attribution(update, baseline=baseline, tia_results=tia)

        # Assert
        assert isinstance(result, AttributionResult)
        assert result.total_delay_days >= 0
        assert result.delay_basis in self._VALID_BASES
        assert sum(p.delay_days for p in result.parties) == pytest.approx(
            result.total_delay_days, abs=0.3
        )
        # DA P0: a non-zero quantum with nobody holding it renders as
        # "no delay detected" in the UI. Unrepresentable, in every cell.
        assert not (result.total_delay_days > 0 and not result.parties)
        for party in result.parties:
            assert 0.0 <= party.pct_of_total <= 100.0
        # NOTE: excusable + non_excusable != total on the estimated path —
        # excusable_days drops the Shared quantum, contradicting the module's
        # own docstring. Tracked in #232; do not assert it here until fixed.


class TestDelayAttributionEndpoint:
    """The layer that actually returned 500 in production (#222).

    Engine tests alone leave this path unguarded: reports.py swallows engine
    exceptions, so only an endpoint test proves the API contract holds.
    """

    def test_baseline_id_returns_200(self) -> None:
        # Arrange
        from src.api.deps import get_store

        store = get_store()
        base_pid = store.save_project(
            "t222-base", _make_schedule([_task("A", end=datetime(2026, 1, 1))])
        )
        upd_pid = store.save_project(
            "t222-upd", _make_schedule([_task("A", end=datetime(2026, 1, 11))])
        )
        client = TestClient(app)

        try:
            # Act
            resp = client.get(
                f"/api/v1/projects/{upd_pid}/delay-attribution?baseline_id={base_pid}"
            )

            # Assert
            assert resp.status_code == 200
            body = resp.json()
            assert isinstance(body["total_delay_days"], (int, float))
            assert body["total_delay_days"] == 10.0
            assert body["delay_basis"] == "baseline_finish_slip"
        finally:
            # The store is a process-global singleton and clear() resets the
            # sequential project_id counter other tests assert against.
            store.clear()
