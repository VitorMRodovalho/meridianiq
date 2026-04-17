# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for MIP 3.5 — Modified / Additive Multiple Base (Impacted As-Planned)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.analytics.mip_additive import (
    Mip35Result,
    analyze_mip_3_5,
)
from src.analytics.mip_subtractive import DelayEvent, WindowDelayEvents
from src.api.app import app
from src.api.deps import get_store
from src.parser.models import ParsedSchedule, Project, Relationship, Task


def _hours(days: float) -> float:
    return days * 8.0


def _linear_schedule() -> ParsedSchedule:
    """Three activities in a linear chain, each 10 days. Total 30d."""
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


class TestMip35Unit:
    def test_requires_two_schedules(self) -> None:
        with pytest.raises(ValueError):
            analyze_mip_3_5([_linear_schedule()])

    def test_returns_result_no_events(self) -> None:
        result = analyze_mip_3_5([_linear_schedule(), _linear_schedule()])
        assert isinstance(result, Mip35Result)
        assert result.schedule_count == 2
        assert result.window_count == 1
        assert len(result.windows) == 1
        assert result.total_impact_delay_days == 0.0
        assert result.windows[0].impact_delay_days == 0.0

    def test_methodology_string(self) -> None:
        result = analyze_mip_3_5([_linear_schedule(), _linear_schedule()])
        assert "MIP 3.5" in result.methodology
        assert "Additive" in result.methodology

    def test_single_window_additive_impact(self) -> None:
        result = analyze_mip_3_5(
            [_linear_schedule(), _linear_schedule()],
            window_delay_events=[
                WindowDelayEvents(
                    window_number=1,
                    events=[DelayEvent(task_id="T2", days=4)],
                )
            ],
        )
        # Linear 30d baseline; extending B by 4d → 34d impacted; impact = 4d
        assert result.windows[0].baseline_completion_days == pytest.approx(30.0, abs=0.1)
        assert result.windows[0].impacted_completion_days == pytest.approx(34.0, abs=0.1)
        assert result.windows[0].impact_delay_days == pytest.approx(4.0, abs=0.1)

    def test_window_number_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            analyze_mip_3_5(
                [_linear_schedule(), _linear_schedule()],
                window_delay_events=[WindowDelayEvents(window_number=2, events=[])],
            )

    def test_window_number_zero_raises(self) -> None:
        with pytest.raises(ValueError):
            analyze_mip_3_5(
                [_linear_schedule(), _linear_schedule()],
                window_delay_events=[WindowDelayEvents(window_number=0, events=[])],
            )

    def test_three_schedules_two_windows(self) -> None:
        result = analyze_mip_3_5(
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
        result = analyze_mip_3_5(
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
        assert result.windows[0].impact_delay_days == pytest.approx(3.0, abs=0.1)
        assert result.windows[1].impact_delay_days == pytest.approx(2.0, abs=0.1)
        assert result.total_impact_delay_days == pytest.approx(5.0, abs=0.1)

    def test_negative_days_raises(self) -> None:
        with pytest.raises(ValueError):
            analyze_mip_3_5(
                [_linear_schedule(), _linear_schedule()],
                window_delay_events=[
                    WindowDelayEvents(
                        window_number=1,
                        events=[DelayEvent(task_id="T1", days=-5)],
                    )
                ],
            )

    def test_unmatched_events_reported_per_window(self) -> None:
        result = analyze_mip_3_5(
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

    def test_non_critical_task_event_does_not_change_completion(self) -> None:
        """Additive impact on a non-critical task should consume float, not move completion."""
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
        rels = [
            Relationship(task_id="T3", pred_task_id="T1"),
            Relationship(task_id="T3", pred_task_id="T2"),
        ]
        sched = ParsedSchedule(
            projects=[Project(proj_id="P", proj_short_name="Para")],
            activities=[t1, t2, t3],
            relationships=rels,
        )
        result = analyze_mip_3_5(
            [sched, sched],
            window_delay_events=[
                WindowDelayEvents(
                    window_number=1,
                    events=[DelayEvent(task_id="T2", days=3)],
                )
            ],
        )
        # T2 had 5d float; adding 3d consumes float, CP unchanged.
        assert result.total_impact_delay_days == pytest.approx(0.0, abs=0.1)

    def test_description_passes_through_to_applied(self) -> None:
        result = analyze_mip_3_5(
            [_linear_schedule(), _linear_schedule()],
            window_delay_events=[
                WindowDelayEvents(
                    window_number=1,
                    events=[DelayEvent(task_id="T2", days=2, description="Owner-caused rework")],
                )
            ],
        )
        assert result.windows[0].delay_events_applied[0].description == "Owner-caused rework"

    def test_impacted_duration_reflects_added_days(self) -> None:
        result = analyze_mip_3_5(
            [_linear_schedule(), _linear_schedule()],
            window_delay_events=[
                WindowDelayEvents(
                    window_number=1,
                    events=[DelayEvent(task_id="T2", days=7)],
                )
            ],
        )
        applied = result.windows[0].delay_events_applied[0]
        assert applied.original_duration_days == pytest.approx(10.0, abs=0.01)
        assert applied.impacted_duration_days == pytest.approx(17.0, abs=0.01)


# ---------------------------------------------------------------------------
# Router integration tests
# ---------------------------------------------------------------------------


def _upload_three_linear() -> tuple[str, str, str]:
    store = get_store()
    a = store.add(_linear_schedule(), b"xer")
    b = store.add(_linear_schedule(), b"xer")
    c = store.add(_linear_schedule(), b"xer")
    return a, b, c


class TestMip35Router:
    def test_missing_project_returns_404(self) -> None:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forensic/mip-3-5",
            json={"project_ids": ["missing-a", "missing-b"]},
        )
        assert resp.status_code == 404

    def test_requires_at_least_2_projects(self) -> None:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forensic/mip-3-5",
            json={"project_ids": ["only-one"]},
        )
        assert resp.status_code == 422

    def test_end_to_end_no_events(self) -> None:
        client = TestClient(app)
        a, b, _c = _upload_three_linear()
        resp = client.post(
            "/api/v1/forensic/mip-3-5",
            json={"project_ids": [a, b], "window_delay_events": []},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "MIP 3.5" in data["methodology"]
        assert data["window_count"] == 1
        assert data["total_impact_delay_days"] == 0.0

    def test_end_to_end_per_window_events(self) -> None:
        client = TestClient(app)
        a, b, c = _upload_three_linear()
        resp = client.post(
            "/api/v1/forensic/mip-3-5",
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
        assert data["total_impact_delay_days"] == pytest.approx(5.0, abs=0.1)
        assert data["windows"][0]["impact_delay_days"] == pytest.approx(3.0, abs=0.1)
        assert data["windows"][1]["impact_delay_days"] == pytest.approx(2.0, abs=0.1)

    def test_negative_days_rejected_at_schema(self) -> None:
        client = TestClient(app)
        a, b, _c = _upload_three_linear()
        resp = client.post(
            "/api/v1/forensic/mip-3-5",
            json={
                "project_ids": [a, b],
                "window_delay_events": [
                    {
                        "window_number": 1,
                        "events": [{"task_id": "T1", "days": -3}],
                    }
                ],
            },
        )
        assert resp.status_code == 422

    def test_window_number_out_of_range_returns_400(self) -> None:
        client = TestClient(app)
        a, b, _c = _upload_three_linear()
        resp = client.post(
            "/api/v1/forensic/mip-3-5",
            json={
                "project_ids": [a, b],
                "window_delay_events": [
                    {"window_number": 5, "events": [{"task_id": "T1", "days": 1}]}
                ],
            },
        )
        assert resp.status_code == 400
