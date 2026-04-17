# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for MIP 3.6 — Collapsed As-Built (Modified Subtractive Single Simulation)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.analytics.mip_subtractive import (
    DelayEvent,
    Mip36Result,
    Mip37Result,
    WindowDelayEvents,
    analyze_mip_3_6,
    analyze_mip_3_7,
)
from src.api.app import app
from src.api.deps import get_store
from src.parser.models import ParsedSchedule, Project, Relationship, Task
from src.parser.xer_reader import XERReader

FIXTURES = Path(__file__).parent / "fixtures"


def _hours(days: float) -> float:
    return days * 8.0


def _linear_schedule() -> ParsedSchedule:
    """Three activities in a linear chain, each 10 days @ 8h/day.

    A (10d) → B (10d) → C (10d). Total duration should be 30 working days.
    """
    t1 = Task(
        task_id="T1",
        task_code="A",
        task_name="Activity A",
        target_drtn_hr_cnt=_hours(10),
        remain_drtn_hr_cnt=_hours(10),
    )
    t2 = Task(
        task_id="T2",
        task_code="B",
        task_name="Activity B",
        target_drtn_hr_cnt=_hours(10),
        remain_drtn_hr_cnt=_hours(10),
    )
    t3 = Task(
        task_id="T3",
        task_code="C",
        task_name="Activity C",
        target_drtn_hr_cnt=_hours(10),
        remain_drtn_hr_cnt=_hours(10),
    )
    rels = [
        Relationship(task_id="T2", pred_task_id="T1"),
        Relationship(task_id="T3", pred_task_id="T2"),
    ]
    return ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name="Linear")],
        activities=[t1, t2, t3],
        relationships=rels,
    )


@pytest.fixture(autouse=True)
def _clear() -> None:
    get_store().clear()


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestMip36Unit:
    def test_returns_result(self) -> None:
        schedule = _linear_schedule()
        result = analyze_mip_3_6(schedule, [DelayEvent(task_id="T1", days=0)])
        assert isinstance(result, Mip36Result)
        assert "MIP 3.6" in result.methodology

    def test_no_events_produces_no_delta(self) -> None:
        schedule = _linear_schedule()
        # Passing zero-day events shouldn't change completion
        result = analyze_mip_3_6(
            schedule,
            [DelayEvent(task_id="T1", days=0), DelayEvent(task_id="T2", days=0)],
        )
        assert result.as_built_completion_days == result.but_for_completion_days
        assert result.attributable_delay_days == 0.0

    def test_removing_days_shortens_completion(self) -> None:
        schedule = _linear_schedule()
        result = analyze_mip_3_6(schedule, [DelayEvent(task_id="T2", days=4)])
        # As-built total: 30 days; shrink B by 4d → 26d but-for
        assert result.as_built_completion_days == pytest.approx(30.0, abs=0.1)
        assert result.but_for_completion_days == pytest.approx(26.0, abs=0.1)
        assert result.attributable_delay_days == pytest.approx(4.0, abs=0.1)

    def test_multiple_events_compose(self) -> None:
        schedule = _linear_schedule()
        result = analyze_mip_3_6(
            schedule,
            [
                DelayEvent(task_id="T1", days=3),
                DelayEvent(task_id="T3", days=2),
            ],
        )
        # On a linear chain all tasks are critical; totals compose.
        assert result.attributable_delay_days == pytest.approx(5.0, abs=0.1)

    def test_events_clamp_to_original_duration(self) -> None:
        schedule = _linear_schedule()
        # B is 10d; request 50d of delay removal → should clamp to 10
        result = analyze_mip_3_6(schedule, [DelayEvent(task_id="T2", days=50)])
        applied = result.delay_events_applied[0]
        assert applied.days_requested == 50
        assert applied.days_applied == pytest.approx(10.0, abs=0.1)
        assert applied.collapsed_duration_days == pytest.approx(0.0, abs=0.1)
        assert "clamped" in applied.note

    def test_unmatched_task_id_is_reported_not_raised(self) -> None:
        schedule = _linear_schedule()
        result = analyze_mip_3_6(schedule, [DelayEvent(task_id="does-not-exist", days=5)])
        assert len(result.unmatched_events) == 1
        assert result.unmatched_events[0].task_id == "does-not-exist"
        assert result.delay_events_applied == []
        assert result.attributable_delay_days == 0.0

    def test_negative_days_raises(self) -> None:
        schedule = _linear_schedule()
        with pytest.raises(ValueError):
            analyze_mip_3_6(schedule, [DelayEvent(task_id="T1", days=-5)])

    def test_description_passes_through(self) -> None:
        schedule = _linear_schedule()
        result = analyze_mip_3_6(
            schedule,
            [DelayEvent(task_id="T2", days=2, description="Weather event")],
        )
        assert result.delay_events_applied[0].description == "Weather event"

    def test_non_critical_task_event_does_not_change_completion(self) -> None:
        """If an event targets a task with float, the critical path is untouched."""
        # Build schedule: T1 critical; T2 parallel non-critical with 5d float
        t1 = Task(
            task_id="T1",
            task_code="A",
            task_name="A",
            target_drtn_hr_cnt=_hours(10),
            remain_drtn_hr_cnt=_hours(10),
        )
        t2 = Task(
            task_id="T2",
            task_code="B",
            task_name="B",
            target_drtn_hr_cnt=_hours(5),
            remain_drtn_hr_cnt=_hours(5),
        )
        t3 = Task(
            task_id="T3",
            task_code="C",
            task_name="C",
            target_drtn_hr_cnt=_hours(10),
            remain_drtn_hr_cnt=_hours(10),
        )
        # Two parallel branches merging at T3: T1 (10d) || T2 (5d) → T3 (10d)
        # Critical path = T1 + T3 = 20 days; T2 has 5d float.
        rels = [
            Relationship(task_id="T3", pred_task_id="T1"),
            Relationship(task_id="T3", pred_task_id="T2"),
        ]
        sched = ParsedSchedule(
            projects=[Project(proj_id="P", proj_short_name="Para")],
            activities=[t1, t2, t3],
            relationships=rels,
        )
        result = analyze_mip_3_6(sched, [DelayEvent(task_id="T2", days=3)])
        # T2 had 5d float, removing 3 days shouldn't move project completion
        assert result.attributable_delay_days == pytest.approx(0.0, abs=0.1)

    def test_critical_path_captured_for_both_states(self) -> None:
        schedule = _linear_schedule()
        result = analyze_mip_3_6(schedule, [DelayEvent(task_id="T2", days=3)])
        assert result.as_built_critical_path == ["A", "B", "C"]
        # All three stay critical after shortening B; CP list unchanged.
        assert result.but_for_critical_path == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Router integration tests
# ---------------------------------------------------------------------------


def _upload_linear(client: TestClient) -> str:
    store = get_store()
    return store.add(_linear_schedule(), b"xer")


class TestMip36Router:
    def test_missing_project_returns_404(self) -> None:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forensic/mip-3-6",
            json={
                "project_id": "missing",
                "delay_events": [{"task_id": "T1", "days": 2}],
            },
        )
        assert resp.status_code == 404

    def test_empty_events_rejected(self) -> None:
        client = TestClient(app)
        pid = _upload_linear(client)
        resp = client.post(
            "/api/v1/forensic/mip-3-6",
            json={"project_id": pid, "delay_events": []},
        )
        assert resp.status_code == 422

    def test_negative_days_rejected(self) -> None:
        client = TestClient(app)
        pid = _upload_linear(client)
        resp = client.post(
            "/api/v1/forensic/mip-3-6",
            json={
                "project_id": pid,
                "delay_events": [{"task_id": "T1", "days": -5}],
            },
        )
        assert resp.status_code == 422

    def test_end_to_end_on_linear_schedule(self) -> None:
        client = TestClient(app)
        pid = _upload_linear(client)
        resp = client.post(
            "/api/v1/forensic/mip-3-6",
            json={
                "project_id": pid,
                "delay_events": [
                    {"task_id": "T1", "days": 2, "description": "Permit delay"},
                    {"task_id": "T3", "days": 3, "description": "Weather"},
                ],
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "MIP 3.6" in data["methodology"]
        # Linear chain: 10+10+10=30 as-built; shortened to 8+10+7=25
        assert data["as_built_completion_days"] == pytest.approx(30.0, abs=0.1)
        assert data["but_for_completion_days"] == pytest.approx(25.0, abs=0.1)
        assert data["attributable_delay_days"] == pytest.approx(5.0, abs=0.1)
        assert len(data["delay_events_applied"]) == 2
        assert data["unmatched_events"] == []

    def test_unmatched_task_id_surfaces_in_response(self) -> None:
        client = TestClient(app)
        pid = _upload_linear(client)
        resp = client.post(
            "/api/v1/forensic/mip-3-6",
            json={
                "project_id": pid,
                "delay_events": [
                    {"task_id": "T1", "days": 2},
                    {"task_id": "ghost", "days": 4},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["delay_events_applied"]) == 1
        assert len(data["unmatched_events"]) == 1
        assert data["unmatched_events"][0]["task_id"] == "ghost"


# ---------------------------------------------------------------------------
# Integration with real fixture — verifies CPM is actually re-run
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# MIP 3.7 unit tests
# ---------------------------------------------------------------------------


class TestMip37Unit:
    def test_requires_two_schedules(self) -> None:
        with pytest.raises(ValueError):
            analyze_mip_3_7([_linear_schedule()])

    def test_returns_result_no_events(self) -> None:
        result = analyze_mip_3_7([_linear_schedule(), _linear_schedule()])
        assert isinstance(result, Mip37Result)
        assert result.schedule_count == 2
        assert result.window_count == 1
        assert len(result.windows) == 1
        # No events → zero attributable delay
        assert result.total_attributable_delay_days == 0.0
        assert result.windows[0].attributable_delay_days == 0.0

    def test_window_number_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            analyze_mip_3_7(
                [_linear_schedule(), _linear_schedule()],
                window_delay_events=[
                    WindowDelayEvents(window_number=2, events=[])  # only 1 window
                ],
            )

    def test_window_number_zero_raises(self) -> None:
        with pytest.raises(ValueError):
            analyze_mip_3_7(
                [_linear_schedule(), _linear_schedule()],
                window_delay_events=[WindowDelayEvents(window_number=0, events=[])],
            )

    def test_three_schedules_two_windows(self) -> None:
        result = analyze_mip_3_7(
            [_linear_schedule(), _linear_schedule(), _linear_schedule()],
            project_ids=["a", "b", "c"],
        )
        assert result.window_count == 2
        assert [w.window_id for w in result.windows] == ["W01", "W02"]
        assert result.windows[0].baseline_project_id == "a"
        assert result.windows[0].update_project_id == "b"
        assert result.windows[1].baseline_project_id == "b"
        assert result.windows[1].update_project_id == "c"

    def test_per_window_events_apply_independently(self) -> None:
        result = analyze_mip_3_7(
            [_linear_schedule(), _linear_schedule(), _linear_schedule()],
            window_delay_events=[
                WindowDelayEvents(
                    window_number=1,
                    events=[DelayEvent(task_id="T2", days=3)],
                ),
                WindowDelayEvents(
                    window_number=2,
                    events=[DelayEvent(task_id="T1", days=2)],
                ),
            ],
        )
        # Each window linear 30d baseline; window 1 − 3d, window 2 − 2d
        assert result.windows[0].attributable_delay_days == pytest.approx(3.0, abs=0.1)
        assert result.windows[1].attributable_delay_days == pytest.approx(2.0, abs=0.1)
        assert result.total_attributable_delay_days == pytest.approx(5.0, abs=0.1)

    def test_window_without_bundle_zero_delay(self) -> None:
        result = analyze_mip_3_7(
            [_linear_schedule(), _linear_schedule(), _linear_schedule()],
            window_delay_events=[
                WindowDelayEvents(
                    window_number=2,
                    events=[DelayEvent(task_id="T1", days=4)],
                )
                # window 1 omitted → zero attributable delay
            ],
        )
        assert result.windows[0].attributable_delay_days == 0.0
        assert result.windows[1].attributable_delay_days == pytest.approx(4.0, abs=0.1)
        assert result.total_attributable_delay_days == pytest.approx(4.0, abs=0.1)

    def test_unmatched_events_reported_per_window(self) -> None:
        result = analyze_mip_3_7(
            [_linear_schedule(), _linear_schedule()],
            window_delay_events=[
                WindowDelayEvents(
                    window_number=1,
                    events=[
                        DelayEvent(task_id="T1", days=1),
                        DelayEvent(task_id="ghost", days=9),
                    ],
                )
            ],
        )
        w = result.windows[0]
        assert len(w.delay_events_applied) == 1
        assert len(w.unmatched_events) == 1
        assert w.unmatched_events[0].task_id == "ghost"

    def test_methodology_string(self) -> None:
        result = analyze_mip_3_7([_linear_schedule(), _linear_schedule()])
        assert "MIP 3.7" in result.methodology


# ---------------------------------------------------------------------------
# MIP 3.7 router integration tests
# ---------------------------------------------------------------------------


def _upload_three_linear(client: TestClient) -> tuple[str, str, str]:
    store = get_store()
    a = store.add(_linear_schedule(), b"xer")
    b = store.add(_linear_schedule(), b"xer")
    c = store.add(_linear_schedule(), b"xer")
    return a, b, c


class TestMip37Router:
    def test_missing_project_returns_404(self) -> None:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forensic/mip-3-7",
            json={"project_ids": ["missing-a", "missing-b"]},
        )
        assert resp.status_code == 404

    def test_requires_at_least_2_projects(self) -> None:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forensic/mip-3-7",
            json={"project_ids": ["only-one"]},
        )
        assert resp.status_code == 422

    def test_end_to_end_no_events(self) -> None:
        client = TestClient(app)
        a, b, _c = _upload_three_linear(client)
        resp = client.post(
            "/api/v1/forensic/mip-3-7",
            json={"project_ids": [a, b], "window_delay_events": []},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "MIP 3.7" in data["methodology"]
        assert data["window_count"] == 1
        assert data["total_attributable_delay_days"] == 0.0

    def test_end_to_end_per_window_events(self) -> None:
        client = TestClient(app)
        a, b, c = _upload_three_linear(client)
        resp = client.post(
            "/api/v1/forensic/mip-3-7",
            json={
                "project_ids": [a, b, c],
                "window_delay_events": [
                    {
                        "window_number": 1,
                        "events": [{"task_id": "T2", "days": 3}],
                    },
                    {
                        "window_number": 2,
                        "events": [{"task_id": "T1", "days": 2}],
                    },
                ],
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["window_count"] == 2
        assert data["total_attributable_delay_days"] == pytest.approx(5.0, abs=0.1)
        assert data["windows"][0]["window_id"] == "W01"
        assert data["windows"][1]["window_id"] == "W02"

    def test_window_number_out_of_range_returns_400(self) -> None:
        client = TestClient(app)
        a, b, _c = _upload_three_linear(client)
        resp = client.post(
            "/api/v1/forensic/mip-3-7",
            json={
                "project_ids": [a, b],
                "window_delay_events": [
                    {"window_number": 5, "events": [{"task_id": "T1", "days": 1}]}
                ],
            },
        )
        assert resp.status_code == 400
        assert "out of range" in resp.text.lower()


class TestMip36OnRealFixture:
    def test_real_xer_collapses_cleanly(self) -> None:
        """Smoke test on the bundled XER fixture.

        Verifies the engine doesn't crash on a non-synthetic schedule and
        that the as-built CPM is positive (we're not collapsing against a
        zero-duration project by accident).
        """
        schedule = XERReader(FIXTURES / "sample.xer").parse()
        if not schedule.activities:
            pytest.skip("fixture has no activities")
        # Pick the first activity with positive duration as a safe target
        target = next(
            (t for t in schedule.activities if (t.target_drtn_hr_cnt or 0) > 0),
            None,
        )
        if target is None:
            pytest.skip("fixture has no activity with positive duration")

        result = analyze_mip_3_6(
            schedule,
            [DelayEvent(task_id=target.task_id, days=1, description="smoke")],
        )
        assert result.as_built_completion_days > 0
        assert result.but_for_completion_days > 0
        # Shortening can only shrink (or leave unchanged) the completion
        assert result.but_for_completion_days <= result.as_built_completion_days
        assert result.attributable_delay_days >= 0.0
