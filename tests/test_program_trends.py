# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the /api/v1/programs/{id}/trends endpoint (P2 Multi-Revision Dashboard)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["ENVIRONMENT"] = "development"

from src.api.app import app, _store  # noqa: E402
from src.database.store import InMemoryStore  # noqa: E402
from src.parser.models import ParsedSchedule, Project, Task, Relationship  # noqa: E402


FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XER = FIXTURES / "sample.xer"


def _make_schedule(
    name: str = "TestProj",
    num_activities: int = 3,
    data_date: str | None = None,
) -> ParsedSchedule:
    """Build a minimal ParsedSchedule for testing."""
    activities = [
        Task(task_id=f"T{i}", task_code=f"A{i:04d}", task_name=f"Activity {i}")
        for i in range(1, num_activities + 1)
    ]
    relationships = (
        [
            Relationship(task_id="T2", pred_task_id="T1"),
        ]
        if num_activities >= 2
        else []
    )
    return ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name=name)],
        activities=activities,
        relationships=relationships,
    )


@pytest.fixture(autouse=True)
def clear_store():
    """Clear the in-memory store before each test."""
    _store.clear()


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def store() -> InMemoryStore:
    """Return the global store as InMemoryStore for direct testing."""
    assert isinstance(_store, InMemoryStore)
    return _store


# ── Test helpers ─────────────────────────────────────────────────


def _upload_two_revisions(store: InMemoryStore, name: str = "AlphaProg") -> str:
    """Upload two revisions to the same program. Returns program_id."""
    store.add(_make_schedule(name, num_activities=3), b"v1", user_id="user-1")
    store.add(_make_schedule(name, num_activities=5), b"v2", user_id="user-1")
    programs = store.get_programs(user_id="user-1")
    assert len(programs) == 1
    return programs[0]["id"]


# ── Tests ─────────────────────────────────────────────────────────


class TestTrendsReturnsArrays:
    """test_trends_returns_arrays"""

    def test_trends_returns_arrays(self, client: TestClient, store: InMemoryStore) -> None:
        """Uploading 2 XERs to the same program yields parallel trend arrays."""
        prog_id = _upload_two_revisions(store)

        resp = client.get(f"/api/v1/programs/{prog_id}/trends")
        assert resp.status_code == 200
        data = resp.json()

        # All parallel arrays should have 2 entries
        assert data["revision_count"] == 2
        assert len(data["labels"]) == 2
        assert len(data["health_scores"]) == 2
        assert len(data["dcma_scores"]) == 2
        assert len(data["alert_counts"]) == 2
        assert len(data["activity_counts"]) == 2
        assert len(data["revisions"]) == 2


class TestTrendsSingleRevision:
    """test_trends_single_revision"""

    def test_trends_single_revision(self, client: TestClient, store: InMemoryStore) -> None:
        """A program with 1 revision returns arrays of length 1."""
        store.add(_make_schedule("Solo"), b"v1", user_id="user-1")
        programs = store.get_programs(user_id="user-1")
        prog_id = programs[0]["id"]

        resp = client.get(f"/api/v1/programs/{prog_id}/trends")
        assert resp.status_code == 200
        data = resp.json()

        assert data["revision_count"] == 1
        assert len(data["labels"]) == 1
        assert len(data["health_scores"]) == 1
        assert len(data["activity_counts"]) == 1


class TestTrendsOrderedAscending:
    """test_trends_ordered_ascending"""

    def test_trends_ordered_ascending(self, client: TestClient, store: InMemoryStore) -> None:
        """Revisions in the trends response are sorted by revision_number ascending."""
        name = "OrderTest"
        store.add(_make_schedule(name, num_activities=3), b"v1", user_id="user-1")
        store.add(_make_schedule(name, num_activities=5), b"v2", user_id="user-1")
        store.add(_make_schedule(name, num_activities=7), b"v3", user_id="user-1")
        programs = store.get_programs(user_id="user-1")
        prog_id = programs[0]["id"]

        resp = client.get(f"/api/v1/programs/{prog_id}/trends")
        assert resp.status_code == 200
        data = resp.json()

        revision_numbers = [r["revision_number"] for r in data["revisions"]]
        assert revision_numbers == sorted(revision_numbers), (
            f"Expected ascending order, got {revision_numbers}"
        )


class TestTrendsNullResults:
    """test_trends_null_results"""

    def test_trends_null_results(self, client: TestClient, store: InMemoryStore) -> None:
        """A revision with no analysis_results produces null entries in metric arrays."""
        prog_id = _upload_two_revisions(store)

        resp = client.get(f"/api/v1/programs/{prog_id}/trends")
        assert resp.status_code == 200
        data = resp.json()

        # Revisions stored via InMemoryStore.add() have no analysis_results,
        # so health_scores entries must be None.
        for score in data["health_scores"]:
            assert score is None, f"Expected None (no analysis_results stored), got {score}"


class TestTrends404ForNonexistent:
    """test_trends_404_for_nonexistent"""

    def test_trends_404_for_nonexistent(self, client: TestClient) -> None:
        """Requesting trends for a non-existent program returns 404."""
        resp = client.get("/api/v1/programs/does-not-exist-9999/trends")
        assert resp.status_code == 404
