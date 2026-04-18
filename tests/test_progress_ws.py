# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the WebSocket progress channel + Monte Carlo wiring.

The unit-level tests poke ``src.api.progress`` directly so they don't need a
running server. The integration test uses ``TestClient`` to drive the
``/api/v1/ws/progress/{job_id}`` socket end-to-end against a real Monte
Carlo run."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from src.api import progress
from src.api.app import app
from src.api.deps import _store
from src.parser.models import (
    ParsedSchedule,
    Project,
    Relationship,
    Task,
)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    progress._channels.clear()
    _store.clear()


def test_open_get_close_channel_round_trip() -> None:
    queue = progress.open_channel("job-A")
    assert progress.get_channel("job-A") is queue
    assert progress.channel_count() == 1
    progress.close_channel("job-A")
    assert progress.get_channel("job-A") is None
    assert progress.channel_count() == 0


def test_publish_to_unknown_channel_is_a_noop() -> None:
    # Should not raise — publish silently drops events for unknown jobs.
    progress.publish("nonexistent-job", {"type": "progress", "done": 1, "total": 10})


def test_publish_then_consume_one_event() -> None:
    async def _run() -> dict:
        queue = progress.open_channel("job-B")
        progress.publish("job-B", {"type": "progress", "done": 5, "total": 10})
        return await asyncio.wait_for(queue.get(), timeout=1.0)

    event = asyncio.run(_run())
    assert event == {"type": "progress", "done": 5, "total": 10}


def test_close_unknown_channel_is_safe() -> None:
    # Idempotent — closing a channel that was never opened should not raise.
    progress.close_channel("never-existed")


def _tiny_schedule() -> ParsedSchedule:
    """A 3-activity linear schedule, big enough for Monte Carlo to chug
    through and emit at least one progress tick."""
    return ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name="ProgressTest")],
        activities=[
            Task(
                task_id="T1",
                task_code="A1",
                task_name="A",
                task_type="TT_Task",
                target_drtn_hr_cnt=8.0,
                remain_drtn_hr_cnt=8.0,
            ),
            Task(
                task_id="T2",
                task_code="A2",
                task_name="B",
                task_type="TT_Task",
                target_drtn_hr_cnt=16.0,
                remain_drtn_hr_cnt=16.0,
            ),
            Task(
                task_id="T3",
                task_code="A3",
                task_name="C",
                task_type="TT_Task",
                target_drtn_hr_cnt=8.0,
                remain_drtn_hr_cnt=8.0,
            ),
        ],
        relationships=[
            Relationship(task_id="T2", pred_task_id="T1", pred_type="PR_FS", lag_hr_cnt=0),
            Relationship(task_id="T3", pred_task_id="T2", pred_type="PR_FS", lag_hr_cnt=0),
        ],
    )


def test_websocket_streams_done_event_when_simulation_finishes() -> None:
    """End-to-end: open WS, run Monte Carlo with the same job_id, expect
    progress events terminated by a ``done`` event with the simulation_id."""
    import uuid as _uuid

    pid = _store.add(_tiny_schedule(), b"raw")

    # Wave 0 #7 hardening: WS path param must be a UUID; non-UUID ids are
    # rejected with close code 4404 before reaching the handler.
    job_id = str(_uuid.uuid4())
    client = TestClient(app)

    with client.websocket_connect(f"/api/v1/ws/progress/{job_id}") as ws:
        # Trigger the simulation in the same TestClient — TestClient runs
        # the WS in one thread and the request in another, so they can both
        # be active at once.
        resp = client.post(
            f"/api/v1/risk/simulate/{pid}?job_id={job_id}",
            json={
                "config": {
                    "iterations": 200,
                    "default_distribution": "triangular",
                    "default_uncertainty": 0.2,
                    "seed": 42,
                    "confidence_levels": [50, 90],
                }
            },
        )
        assert resp.status_code == 200, resp.text

        events: list[dict] = []
        # Drain the socket until done. Bound the loop so a regression
        # doesn't hang the suite.
        for _ in range(500):
            event = ws.receive_json()
            events.append(event)
            if event.get("type") in ("done", "error"):
                break

    types = [e.get("type") for e in events]
    assert "done" in types
    # Should have at least one progress event before done
    assert any(t == "progress" for t in types)
    # Done payload includes the simulation id
    done_event = next(e for e in events if e["type"] == "done")
    assert done_event.get("simulation_id")
