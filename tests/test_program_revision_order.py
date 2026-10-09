# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""A program's revisions: numbered from ``projects``, ordered by data date."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

os.environ["ENVIRONMENT"] = "development"

from src.api.app import _store, app  # noqa: E402
from src.database.store import InMemoryStore, SupabaseStore, newest_first  # noqa: E402
from src.parser.models import ParsedSchedule, Project, Relationship, Task  # noqa: E402


def _schedule(name: str, data_date: datetime | None, activities: int = 3) -> ParsedSchedule:
    tasks = [
        Task(task_id=f"T{i}", task_code=f"A{i:04d}", task_name=f"Activity {i}")
        for i in range(1, activities + 1)
    ]
    return ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name=name, last_recalc_date=data_date)],
        activities=tasks,
        relationships=[Relationship(task_id="T2", pred_task_id="T1")],
    )


@pytest.fixture(autouse=True)
def _clear() -> None:
    _store.clear()


@pytest.fixture
def store() -> InMemoryStore:
    assert isinstance(_store, InMemoryStore)
    return _store


class _Query:
    def __init__(self, client: _Client, table: str) -> None:
        self.client, self.table = client, table
        self.calls: list[tuple[str, Any]] = []

    def __getattr__(self, name: str) -> Any:
        def record(*args: Any, **kwargs: Any) -> _Query:
            self.calls.append((name, (args, kwargs)))
            return self

        return record

    def execute(self) -> Any:
        self.client.executed.append(self)
        return type("Result", (), {"data": self.client.data.get(self.table, [])})()


class _Client:
    """Records which table each query reads and returns canned rows."""

    def __init__(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.data = data
        self.executed: list[_Query] = []

    def table(self, name: str) -> _Query:
        return _Query(self, name)


def _supabase(data: dict[str, list[dict[str, Any]]]) -> tuple[SupabaseStore, _Client]:
    store = SupabaseStore.__new__(SupabaseStore)
    client = _Client(data)
    store._client = client  # type: ignore[attr-defined]
    return store, client


class TestNextRevisionNumber:
    def test_reads_projects_which_carry_the_program(self) -> None:
        store, client = _supabase({"projects": [{"revision_number": 4}]})
        assert store.get_next_revision_number("p") == 5
        assert [q.table for q in client.executed] == ["projects"]

    def test_first_revision_is_one(self) -> None:
        store, _ = _supabase({"projects": []})
        assert store.get_next_revision_number("p") == 1


class TestProgramIdIsChecked:
    def test_a_name_is_not_sent_to_the_uuid_column(self) -> None:
        store, client = _supabase({"programs": [{"id": "x"}]})
        assert store.get_program_revisions("Some Short Name", user_id="u") == []
        assert store.update_program("Some Short Name", {"name": "n"}, user_id="u") is None
        assert client.executed == []

    def test_a_uuid_is_queried(self) -> None:
        store, client = _supabase({"programs": []})
        store.get_program_revisions("00000000-0000-4000-8000-000000000000", user_id="u")
        assert [q.table for q in client.executed] == ["programs"]


class TestNewestFirst:
    def test_data_date_decides_and_upload_order_breaks_ties(self) -> None:
        revs = [
            {"id": "a", "data_date": "2026-03-01", "revision_number": 3},
            {"id": "b", "data_date": "2026-05-01", "revision_number": 1},
            {"id": "c", "data_date": None, "revision_number": 4},
            {"id": "d", "data_date": "2026-05-01", "revision_number": 2},
        ]
        assert [r["id"] for r in newest_first(revs)] == ["d", "b", "a", "c"]


class TestRollupAndTrendsFollowDataDate:
    def _program(self, store: InMemoryStore) -> str:
        # The later schedule is uploaded first, the earlier one second.
        store.save_project("u1", _schedule("Alpha UP02", datetime(2026, 5, 1), 7), b"", "user-1")
        store.save_project("u2", _schedule("Alpha UP02", datetime(2026, 3, 1), 3), b"", "user-1")
        return str(store.get_programs(user_id="user-1")[0]["id"])

    def test_rollup_latest_is_the_latest_data_date(self, store: InMemoryStore) -> None:
        prog = self._program(store)
        data = TestClient(app).get(f"/api/v1/programs/{prog}/rollup").json()
        assert data["latest_data_date"].startswith("2026-05-01")
        assert data["latest_revision_number"] == 1
        assert data["previous_revision_number"] == 2
        assert data["latest_metrics"]["activity_count"] == 7

    def test_trends_run_oldest_to_newest(self, store: InMemoryStore) -> None:
        prog = self._program(store)
        data = TestClient(app).get(f"/api/v1/programs/{prog}/trends").json()
        assert [label[:10] for label in data["labels"]] == ["2026-03-01", "2026-05-01"]
        assert data["activity_counts"] == [3, 7]

    def test_detail_lists_newest_first(self, store: InMemoryStore) -> None:
        prog = self._program(store)
        revs = TestClient(app).get(f"/api/v1/programs/{prog}").json()["revisions"]
        assert [r["revision_number"] for r in revs] == [1, 2]


class TestRename:
    def _prog(self, store: InMemoryStore) -> str:
        store.save_project("u1", _schedule("Alpha", None), b"", "user-1")
        return str(store.get_programs(user_id="user-1")[0]["id"])

    @pytest.mark.parametrize(
        "body", [{"name": ""}, {"name": "x" * 201}, {"owner": "someone"}, {"user_id": "u"}]
    )
    def test_body_is_validated(self, store: InMemoryStore, body: dict[str, str]) -> None:
        prog = self._prog(store)
        resp = TestClient(app).put(f"/api/v1/programs/{prog}", json=body)
        assert resp.status_code == 422, resp.text

    def test_name_is_trimmed(self, store: InMemoryStore) -> None:
        prog = self._prog(store)
        resp = TestClient(app).put(f"/api/v1/programs/{prog}", json={"name": "  Beta  "})
        assert resp.status_code == 200, resp.text
        assert resp.json()["program"]["name"] == "Beta"

    def test_taken_name_is_a_409(
        self, store: InMemoryStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prog = self._prog(store)

        class Taken(Exception):
            code = "23505"

        def clash(*_a: Any, **_k: Any) -> None:
            raise Taken("duplicate key value violates unique constraint")

        monkeypatch.setattr(store, "update_program", clash)
        resp = TestClient(app).put(f"/api/v1/programs/{prog}", json={"name": "Beta"})
        assert resp.status_code == 409, resp.text
