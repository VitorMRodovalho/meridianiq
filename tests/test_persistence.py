# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for Supabase persistence wiring — user_id filtering in InMemoryStore."""

from __future__ import annotations

import os

os.environ["ENVIRONMENT"] = "development"

from src.database.store import InMemoryStore  # noqa: E402
from src.parser.models import ParsedSchedule, Project, Task, Relationship  # noqa: E402


def _make_schedule(name: str = "TestProj", num_activities: int = 3) -> ParsedSchedule:
    """Build a minimal ParsedSchedule for testing."""
    activities = [
        Task(task_id=f"T{i}", task_code=f"A{i:04d}", task_name=f"Activity {i}")
        for i in range(1, num_activities + 1)
    ]
    relationships = [Relationship(task_id="T2", pred_task_id="T1")] if num_activities >= 2 else []
    return ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name=name)],
        activities=activities,
        relationships=relationships,
    )


class TestInMemoryStoreUserIdAdd:
    """ProjectStore (via InMemoryStore) accepts and uses user_id param."""

    def test_add_with_user_id(self) -> None:
        store = InMemoryStore()
        pid = store.add(_make_schedule("A"), b"data", user_id="user-001")
        assert pid.startswith("proj-")
        # Retrievable by the same user
        assert store.get(pid, user_id="user-001") is not None

    def test_add_without_user_id(self) -> None:
        store = InMemoryStore()
        pid = store.add(_make_schedule("B"), b"data")
        assert pid.startswith("proj-")
        # Retrievable without user_id
        assert store.get(pid) is not None

    def test_add_with_user_id_blocks_other_user(self) -> None:
        store = InMemoryStore()
        pid = store.add(_make_schedule("C"), b"data", user_id="user-001")
        # Different user cannot access
        assert store.get(pid, user_id="user-999") is None


class TestInMemoryStoreListFiltersUser:
    """list_all with user_id returns only that user's projects + anonymous ones."""

    def test_list_all_no_filter(self) -> None:
        store = InMemoryStore()
        store.add(_make_schedule("A"), b"", user_id="user-001")
        store.add(_make_schedule("B"), b"", user_id="user-002")
        store.add(_make_schedule("C"), b"")  # anonymous
        items = store.list_all()
        assert len(items) == 3

    def test_list_all_filters_by_user(self) -> None:
        store = InMemoryStore()
        store.add(_make_schedule("A"), b"", user_id="user-001")
        store.add(_make_schedule("B"), b"", user_id="user-002")
        store.add(_make_schedule("C"), b"")  # anonymous (visible to all)
        items = store.list_all(user_id="user-001")
        names = {i["name"] for i in items}
        assert "A" in names
        assert "C" in names  # anonymous projects visible
        assert "B" not in names  # other user's project hidden

    def test_list_all_user_with_no_projects(self) -> None:
        store = InMemoryStore()
        store.add(_make_schedule("A"), b"", user_id="user-001")
        items = store.list_all(user_id="user-999")
        assert len(items) == 0

    def test_clear_resets_owners(self) -> None:
        store = InMemoryStore()
        store.add(_make_schedule("A"), b"", user_id="user-001")
        store.clear()
        assert store.list_all() == []
        assert store.list_all(user_id="user-001") == []
