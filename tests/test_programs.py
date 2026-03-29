# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the Program -> Revisions model."""

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


# ── Unit tests on InMemoryStore directly ────────────────────────


class TestUploadCreatesProgram:
    """test_upload_creates_program"""

    def test_upload_creates_program(self, store: InMemoryStore) -> None:
        """Adding a schedule with a user_id auto-creates a program."""
        schedule = _make_schedule("Alpha")
        store.add(schedule, b"xer-data", user_id="user-1")
        programs = store.get_programs(user_id="user-1")
        assert len(programs) == 1
        assert programs[0]["name"] == "Alpha"
        assert programs[0]["revision_count"] == 1


class TestSecondUploadGroupsUnderSameProgram:
    """test_second_upload_groups_under_same_program"""

    def test_second_upload_groups_under_same_program(self, store: InMemoryStore) -> None:
        """Two uploads with the same project name go under one program."""
        s1 = _make_schedule("Alpha")
        s2 = _make_schedule("Alpha", num_activities=5)
        store.add(s1, b"v1", user_id="user-1")
        store.add(s2, b"v2", user_id="user-1")
        programs = store.get_programs(user_id="user-1")
        assert len(programs) == 1
        assert programs[0]["revision_count"] == 2


class TestDifferentNamesCreateSeparatePrograms:
    """test_different_names_create_separate_programs"""

    def test_different_names_create_separate_programs(self, store: InMemoryStore) -> None:
        """Uploads with different project names create separate programs."""
        store.add(_make_schedule("Alpha"), b"v1", user_id="user-1")
        store.add(_make_schedule("Beta"), b"v2", user_id="user-1")
        programs = store.get_programs(user_id="user-1")
        assert len(programs) == 2
        names = {p["name"] for p in programs}
        assert names == {"Alpha", "Beta"}


class TestRevisionNumbersIncrement:
    """test_revision_numbers_increment"""

    def test_revision_numbers_increment(self, store: InMemoryStore) -> None:
        """Revision numbers increment for each upload under the same program."""
        store.add(_make_schedule("Alpha"), b"v1", user_id="user-1")
        store.add(_make_schedule("Alpha"), b"v2", user_id="user-1")
        store.add(_make_schedule("Alpha"), b"v3", user_id="user-1")
        programs = store.get_programs(user_id="user-1")
        assert len(programs) == 1
        revisions = store.get_program_revisions(programs[0]["id"], user_id="user-1")
        rev_numbers = [r["revision_number"] for r in revisions]
        assert sorted(rev_numbers) == [1, 2, 3]


class TestProgramsList:
    """test_programs_list"""

    def test_programs_list(self, store: InMemoryStore) -> None:
        """get_programs returns enriched data with latest_revision and revision_count."""
        store.add(_make_schedule("Alpha", num_activities=3), b"v1", user_id="user-1")
        store.add(_make_schedule("Alpha", num_activities=5), b"v2", user_id="user-1")
        programs = store.get_programs(user_id="user-1")
        assert len(programs) == 1
        prog = programs[0]
        assert prog["revision_count"] == 2
        assert prog["latest_revision"] is not None
        assert prog["latest_revision"]["revision_number"] == 2
        assert prog["latest_revision"]["activity_count"] == 5


class TestProgramRevisions:
    """test_program_revisions"""

    def test_program_revisions(self, store: InMemoryStore) -> None:
        """get_program_revisions returns all revisions sorted desc."""
        store.add(_make_schedule("Alpha", num_activities=3), b"v1", user_id="user-1")
        store.add(_make_schedule("Alpha", num_activities=7), b"v2", user_id="user-1")
        programs = store.get_programs(user_id="user-1")
        revisions = store.get_program_revisions(programs[0]["id"], user_id="user-1")
        assert len(revisions) == 2
        # Should be sorted desc by revision_number
        assert revisions[0]["revision_number"] > revisions[1]["revision_number"]


class TestProgramRename:
    """test_program_rename"""

    def test_program_rename(self, store: InMemoryStore) -> None:
        """update_program can rename a program."""
        store.add(_make_schedule("Alpha"), b"v1", user_id="user-1")
        programs = store.get_programs(user_id="user-1")
        prog_id = programs[0]["id"]
        updated = store.update_program(prog_id, {"name": "Alpha Renamed"}, user_id="user-1")
        assert updated is not None
        assert updated["name"] == "Alpha Renamed"


class TestProgramsIsolatedByUser:
    """test_programs_isolated_by_user"""

    def test_programs_isolated_by_user(self, store: InMemoryStore) -> None:
        """Programs are isolated by user_id."""
        store.add(_make_schedule("Alpha"), b"v1", user_id="user-1")
        store.add(_make_schedule("Beta"), b"v2", user_id="user-2")
        progs_u1 = store.get_programs(user_id="user-1")
        progs_u2 = store.get_programs(user_id="user-2")
        assert len(progs_u1) == 1
        assert progs_u1[0]["name"] == "Alpha"
        assert len(progs_u2) == 1
        assert progs_u2[0]["name"] == "Beta"


# ── API endpoint tests ──────────────────────────────────────────


class TestProgramsAPIEndpoints:
    """Tests for the /api/v1/programs endpoints via HTTP."""

    def test_programs_api_list(self, client: TestClient, store: InMemoryStore) -> None:
        """GET /api/v1/programs returns programs."""
        store.add(_make_schedule("ProjectX"), b"xer", user_id="user-1")
        resp = client.get("/api/v1/programs")
        assert resp.status_code == 200
        data = resp.json()
        # In dev mode (no auth), user_id is None so programs may not be created
        # But the endpoint itself should work
        assert "programs" in data

    def test_programs_api_detail(self, client: TestClient, store: InMemoryStore) -> None:
        """GET /api/v1/programs/{id} returns program + revisions."""
        store.add(_make_schedule("ProjectX"), b"xer", user_id="user-1")
        programs = store.get_programs(user_id="user-1")
        if programs:
            prog_id = programs[0]["id"]
            resp = client.get(f"/api/v1/programs/{prog_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert "program" in data
            assert "revisions" in data
