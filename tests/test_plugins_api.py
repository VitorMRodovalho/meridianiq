# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the /api/v1/plugins HTTP surface."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import _store
from src.parser.models import ParsedSchedule, Project, Task
from src.plugins import register_plugin


@pytest.fixture(autouse=True)
def _clean_state() -> None:
    from src.plugins import _registry

    _registry.clear()
    _store.clear()


class _CounterPlugin:
    name = "test-counter"
    version = "9.9.9"

    def analyze(self, schedule: Any) -> dict[str, Any]:
        return {"count": len(schedule.activities)}


class _BoomPlugin:
    name = "test-boom"
    version = "0.0.1"

    def analyze(self, schedule: Any) -> dict[str, Any]:
        raise RuntimeError("intentional plugin failure for tests")


def test_list_endpoint_returns_registered_plugins() -> None:
    register_plugin(_CounterPlugin())
    client = TestClient(app)
    resp = client.get("/api/v1/plugins")
    assert resp.status_code == 200
    body = resp.json()
    names = [p["name"] for p in body["plugins"]]
    assert "test-counter" in names
    entry = next(p for p in body["plugins"] if p["name"] == "test-counter")
    assert entry["version"] == "9.9.9"


def test_list_endpoint_returns_empty_when_no_plugins() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/plugins")
    assert resp.status_code == 200
    assert resp.json() == {"plugins": []}


def test_run_unknown_plugin_returns_404() -> None:
    client = TestClient(app)
    resp = client.post("/api/v1/plugins/does-not-exist/run/proj-0001")
    assert resp.status_code == 404
    assert "Plugin not found" in resp.json()["detail"]


def test_run_unknown_project_returns_404() -> None:
    register_plugin(_CounterPlugin())
    client = TestClient(app)
    resp = client.post("/api/v1/plugins/test-counter/run/proj-9999")
    assert resp.status_code == 404
    assert "Project not found" in resp.json()["detail"]


def test_run_plugin_returns_result() -> None:
    register_plugin(_CounterPlugin())
    schedule = ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name="Demo")],
        activities=[
            Task(task_id=f"T{i}", task_code=f"A{i}", task_name=f"Activity {i}") for i in range(1, 8)
        ],
    )
    pid = _store.add(schedule, b"raw")

    client = TestClient(app)
    resp = client.post(f"/api/v1/plugins/test-counter/run/{pid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["plugin"] == {"name": "test-counter", "version": "9.9.9"}
    assert body["result"] == {"count": 7}


def test_run_plugin_that_raises_returns_500() -> None:
    register_plugin(_BoomPlugin())
    schedule = ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name="Demo")],
        activities=[Task(task_id="T1", task_code="A1", task_name="A")],
    )
    pid = _store.add(schedule, b"raw")

    client = TestClient(app)
    resp = client.post(f"/api/v1/plugins/test-boom/run/{pid}")
    assert resp.status_code == 500
    assert "intentional plugin failure" in resp.json()["detail"]
