# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the plugin discovery + registry."""

from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from src.parser.models import ParsedSchedule, Project, Task
from src.plugins import (
    AnalysisEngine,
    PluginRecord,
    discover_plugins,
    get_plugin,
    list_plugins,
    register_plugin,
)


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    """Each test starts with an empty registry."""
    from src.plugins import _registry

    _registry.clear()


class _MinimalPlugin:
    name = "test-plugin"
    version = "0.1.0"

    def analyze(self, schedule: ParsedSchedule) -> dict[str, Any]:
        return {"activity_count": len(schedule.activities)}


class _SecondPlugin:
    name = "test-plugin-2"
    version = "0.2.0"

    def analyze(self, schedule: ParsedSchedule) -> dict[str, Any]:
        return {"projects": len(schedule.projects)}


class _BrokenPlugin:
    """Missing `version`, so should fail the protocol check."""

    name = "broken"

    def analyze(self, schedule: ParsedSchedule) -> dict[str, Any]:
        return {}


def test_minimal_plugin_satisfies_protocol() -> None:
    assert isinstance(_MinimalPlugin(), AnalysisEngine)


def test_broken_plugin_rejected_by_protocol() -> None:
    assert not isinstance(_BrokenPlugin(), AnalysisEngine)


def test_register_plugin_then_lookup() -> None:
    register_plugin(_MinimalPlugin())
    rec = get_plugin("test-plugin")
    assert isinstance(rec, PluginRecord)
    assert rec.name == "test-plugin"
    assert rec.version == "0.1.0"


def test_register_broken_plugin_raises() -> None:
    with pytest.raises(TypeError):
        register_plugin(_BrokenPlugin())  # type: ignore[arg-type]


def test_list_plugins_sorted() -> None:
    register_plugin(_SecondPlugin())
    register_plugin(_MinimalPlugin())
    names = [r.name for r in list_plugins()]
    assert names == ["test-plugin", "test-plugin-2"]


def test_get_plugin_returns_none_for_unknown() -> None:
    assert get_plugin("does-not-exist") is None


def test_plugin_analyze_round_trip() -> None:
    register_plugin(_MinimalPlugin())
    schedule = ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name="Demo")],
        activities=[
            Task(task_id=f"T{i}", task_code=f"A{i:04d}", task_name=f"Activity {i}")
            for i in range(1, 6)
        ],
    )
    rec = get_plugin("test-plugin")
    assert rec is not None
    result = rec.instance.analyze(schedule)
    assert result == {"activity_count": 5}


def test_discover_plugins_idempotent_with_empty_group() -> None:
    """When no plugins are installed, discover_plugins() returns an empty dict."""
    result = discover_plugins()
    # Other packages on the system might register plugins, so we just
    # verify the call returns a dict and is repeatable.
    assert isinstance(result, dict)
    second = discover_plugins()
    assert set(second.keys()) == set(result.keys())


def test_sample_plugin_analysis_shape() -> None:
    """Replicates what the bundled samples/plugin-example/ does."""

    class ActivityCounter:
        name = "activity-counter"
        version = "0.1.0"

        def analyze(self, schedule: ParsedSchedule) -> dict[str, Any]:
            statuses = Counter((a.status_code or "Unknown") for a in schedule.activities)
            return {"total": len(schedule.activities), "by_status": dict(statuses)}

    register_plugin(ActivityCounter())
    schedule = ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name="Demo")],
        activities=[
            Task(task_id="T1", task_code="A1", task_name="A", status_code="Complete"),
            Task(task_id="T2", task_code="A2", task_name="B", status_code="In Progress"),
            Task(task_id="T3", task_code="A3", task_name="C", status_code="Complete"),
        ],
    )
    rec = get_plugin("activity-counter")
    assert rec is not None
    result = rec.instance.analyze(schedule)
    assert result["total"] == 3
    assert result["by_status"] == {"Complete": 2, "In Progress": 1}
