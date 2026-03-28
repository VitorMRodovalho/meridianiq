# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the unified data-store interface (InMemoryStore)."""
from __future__ import annotations

import os

import pytest

os.environ["ENVIRONMENT"] = "development"

from src.database.store import InMemoryStore, get_store  # noqa: E402
from src.parser.models import ParsedSchedule, Project, Task, Relationship  # noqa: E402


# -- fixtures --------------------------------------------------------


def _make_schedule(
    name: str = "TestProj",
    num_activities: int = 3,
) -> ParsedSchedule:
    """Build a minimal ParsedSchedule for testing."""
    activities = [
        Task(task_id=f"T{i}", task_code=f"A{i:04d}", task_name=f"Activity {i}")
        for i in range(1, num_activities + 1)
    ]
    relationships = [
        Relationship(task_id="T2", pred_task_id="T1"),
    ] if num_activities >= 2 else []
    return ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name=name)],
        activities=activities,
        relationships=relationships,
    )


# -- get_store factory -----------------------------------------------


class TestGetStore:
    """The factory should return InMemoryStore in development."""

    def test_returns_in_memory_store(self) -> None:
        from src.database import store as store_module

        store_module._store_instance = None  # reset singleton
        s = get_store()
        assert isinstance(s, InMemoryStore)
        store_module._store_instance = None  # cleanup


# -- InMemoryStore: project operations --------------------------------


class TestInMemoryStoreProjects:
    """Project add / get / list_all via InMemoryStore."""

    def test_add_and_get(self) -> None:
        store = InMemoryStore()
        schedule = _make_schedule()
        pid = store.add(schedule, b"fake-xer-data")
        assert pid.startswith("proj-")
        retrieved = store.get(pid)
        assert retrieved is not None
        assert retrieved.projects[0].proj_short_name == "TestProj"

    def test_save_project_and_get_project(self) -> None:
        store = InMemoryStore()
        schedule = _make_schedule("SaveTest")
        pid = store.save_project("upload-001", schedule, b"data")
        assert pid.startswith("proj-")
        assert store.get_project(pid) is not None

    def test_get_nonexistent_returns_none(self) -> None:
        store = InMemoryStore()
        assert store.get("proj-9999") is None
        assert store.get_project("proj-9999") is None

    def test_list_all(self) -> None:
        store = InMemoryStore()
        store.add(_make_schedule("A"), b"")
        store.add(_make_schedule("B"), b"")
        items = store.list_all()
        assert len(items) == 2
        names = {i["name"] for i in items}
        assert names == {"A", "B"}

    def test_get_projects(self) -> None:
        store = InMemoryStore()
        store.add(_make_schedule("X"), b"")
        projects = store.get_projects()
        assert len(projects) == 1
        assert projects[0]["name"] == "X"

    def test_get_xer_bytes(self) -> None:
        store = InMemoryStore()
        pid = store.add(_make_schedule(), b"xer-content")
        assert store.get_xer_bytes(pid) == b"xer-content"

    def test_clear(self) -> None:
        store = InMemoryStore()
        store.add(_make_schedule(), b"")
        store.clear()
        assert store.list_all() == []


# -- InMemoryStore: analysis results -----------------------------------


class TestInMemoryStoreAnalysis:
    """Analysis save / get."""

    def test_save_and_get_analysis(self) -> None:
        store = InMemoryStore()
        aid = store.save_analysis("proj-0001", "dcma14", {"score": 85})
        assert aid.startswith("analysis-")
        result = store.get_analysis("proj-0001", "dcma14")
        assert result == {"score": 85}

    def test_get_missing_analysis(self) -> None:
        store = InMemoryStore()
        assert store.get_analysis("proj-0001", "dcma14") is None


# -- InMemoryStore: comparisons ----------------------------------------


class TestInMemoryStoreComparisons:
    """Comparison save."""

    def test_save_comparison(self) -> None:
        store = InMemoryStore()
        cid = store.save_comparison("proj-0001", "proj-0002", {"changes": 5})
        assert cid.startswith("cmp-")


# -- InMemoryStore: forensic timelines ---------------------------------


class TestInMemoryStoreForensicTimelines:
    """Forensic timeline CRUD."""

    def _make_timeline(self) -> "ForensicTimeline":
        from src.analytics.forensics import ForensicTimeline

        return ForensicTimeline(
            timeline_id="",
            project_name="Test",
            schedule_count=2,
            total_delay_days=10.0,
            windows=[],
        )

    def test_save_and_get(self) -> None:
        store = InMemoryStore()
        tl = self._make_timeline()
        tid = store.save_forensic_timeline(tl)
        assert tid.startswith("timeline-")
        retrieved = store.get_forensic_timeline(tid)
        assert retrieved is not None
        assert retrieved.project_name == "Test"

    def test_list(self) -> None:
        store = InMemoryStore()
        store.save_forensic_timeline(self._make_timeline())
        items = store.list_forensic_timelines()
        assert len(items) == 1


# -- InMemoryStore: TIA analyses ----------------------------------------


class TestInMemoryStoreTIA:
    """TIA analysis CRUD."""

    def _make_tia(self) -> "TIAAnalysis":
        from src.analytics.tia import TIAAnalysis

        return TIAAnalysis(
            analysis_id="",
            project_name="TIA Test",
            base_project_id="P1",
            fragments=[],
            net_delay=5.0,
            total_owner_delay=3.0,
            total_contractor_delay=2.0,
        )

    def test_save_and_get(self) -> None:
        store = InMemoryStore()
        a = self._make_tia()
        aid = store.save_tia_analysis(a)
        assert aid.startswith("tia-")
        retrieved = store.get_tia_analysis(aid)
        assert retrieved is not None
        assert retrieved.project_name == "TIA Test"

    def test_list(self) -> None:
        store = InMemoryStore()
        store.save_tia_analysis(self._make_tia())
        items = store.list_tia_analyses()
        assert len(items) == 1


# -- InMemoryStore: EVM analyses ----------------------------------------


class TestInMemoryStoreEVM:
    """EVM analysis CRUD."""

    def _make_evm(self) -> "EVMAnalysisResult":
        from src.analytics.evm import (
            EVMAnalysisResult,
            EVMMetrics,
            HealthClassification,
        )

        return EVMAnalysisResult(
            project_name="EVM Test",
            project_id="P1",
            data_date="2025-01-01",
            metrics=EVMMetrics(
                bac=1000, ev=500, pv=600, ac=550,
            ),
            schedule_health=HealthClassification(
                index_name="SPI", value=0.833,
                status="warning", label="Behind Schedule",
            ),
            cost_health=HealthClassification(
                index_name="CPI", value=0.909,
                status="warning", label="Over Budget",
            ),
            s_curve=[],
        )

    def test_save_and_get(self) -> None:
        store = InMemoryStore()
        r = self._make_evm()
        aid = store.save_evm_analysis(r)
        assert aid.startswith("evm-")
        retrieved = store.get_evm_analysis(aid)
        assert retrieved is not None
        assert retrieved.project_name == "EVM Test"

    def test_list(self) -> None:
        store = InMemoryStore()
        store.save_evm_analysis(self._make_evm())
        items = store.list_evm_analyses()
        assert len(items) == 1


# -- InMemoryStore: risk simulations ------------------------------------


class TestInMemoryStoreRisk:
    """Risk simulation CRUD."""

    def _make_risk(self) -> "SimulationResult":
        from src.analytics.risk import SimulationResult

        return SimulationResult(
            project_name="Risk Test",
            project_id="P1",
            iterations=1000,
            deterministic_days=100.0,
            mean_days=105.0,
            std_days=5.0,
        )

    def test_save_and_get(self) -> None:
        store = InMemoryStore()
        r = self._make_risk()
        sid = store.save_risk_simulation(r)
        assert sid.startswith("risk-")
        retrieved = store.get_risk_simulation(sid)
        assert retrieved is not None
        assert retrieved.project_name == "Risk Test"

    def test_list(self) -> None:
        store = InMemoryStore()
        store.save_risk_simulation(self._make_risk())
        items = store.list_risk_simulations()
        assert len(items) == 1


# -- InMemoryStore: get_parsed_schedule --------------------------------


class TestInMemoryStoreParsedSchedule:
    """Tests for the get_parsed_schedule method added in storage refactor."""

    def test_get_parsed_schedule_returns_valid_schedule(self) -> None:
        """get_parsed_schedule should return the same schedule stored via add()."""
        store = InMemoryStore()
        schedule = _make_schedule("ReParseTest", num_activities=5)
        pid = store.add(schedule, b"xer-data")
        retrieved = store.get_parsed_schedule(pid)
        assert retrieved is not None
        assert retrieved.projects[0].proj_short_name == "ReParseTest"
        assert len(retrieved.activities) == 5
        assert len(retrieved.relationships) == 1

    def test_get_parsed_schedule_nonexistent_returns_none(self) -> None:
        """get_parsed_schedule should return None for unknown project_id."""
        store = InMemoryStore()
        assert store.get_parsed_schedule("proj-9999") is None

    def test_get_parsed_schedule_matches_get(self) -> None:
        """get_parsed_schedule and get() should return the same object."""
        store = InMemoryStore()
        schedule = _make_schedule("SameObj")
        pid = store.add(schedule, b"bytes")
        assert store.get_parsed_schedule(pid) is store.get(pid)


# -- InMemoryStore: metadata-only list ---------------------------------


class TestMetadataOnlyList:
    """Verify list_all returns metadata, not full ParsedSchedule objects."""

    def test_list_all_returns_metadata_not_full_schedule(self) -> None:
        """list_all items should contain metadata keys only, not schedule data."""
        store = InMemoryStore()
        store.add(_make_schedule("Meta1", num_activities=10), b"")
        store.add(_make_schedule("Meta2", num_activities=7), b"")
        items = store.list_all()
        assert len(items) == 2
        for item in items:
            assert "project_id" in item
            assert "name" in item
            assert "activity_count" in item
            assert "relationship_count" in item
            # Should NOT contain a full schedule object or schedule_data key
            assert "schedule" not in item
            assert "schedule_data" not in item

    def test_list_all_activity_counts_are_correct(self) -> None:
        """list_all should report correct counts from metadata."""
        store = InMemoryStore()
        store.add(_make_schedule("CountTest", num_activities=15), b"")
        items = store.list_all()
        assert len(items) == 1
        assert items[0]["activity_count"] == 15
        assert items[0]["name"] == "CountTest"
