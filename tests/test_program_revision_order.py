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

    def test_program_list_latest_is_the_latest_data_date(self, store: InMemoryStore) -> None:
        self._program(store)
        progs = TestClient(app).get("/api/v1/programs").json()
        progs = progs["programs"] if isinstance(progs, dict) else progs
        assert progs[0]["latest_revision"]["activity_count"] == 7

    def test_detail_lists_newest_first(self, store: InMemoryStore) -> None:
        prog = self._program(store)
        revs = TestClient(app).get(f"/api/v1/programs/{prog}").json()["revisions"]
        assert [r["revision_number"] for r in revs] == [1, 2]


class TestRename:
    def _prog(self, store: InMemoryStore) -> str:
        store.save_project("u1", _schedule("Alpha", None), b"", "user-1")
        return str(store.get_programs(user_id="user-1")[0]["id"])

    @pytest.mark.parametrize(
        "body",
        [{"name": ""}, {"name": "x" * 201}, {"owner": "someone"}, {"user_id": "u"}, {}],
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


class TestTrendsReadStoredResults:
    """Health and DCMA trends come from the materializer's stored artifacts."""

    def _program(self, store: InMemoryStore) -> tuple[str, str, str]:
        older = store.save_project("u1", _schedule("A", datetime(2026, 3, 1)), b"", "user-1")
        newer = store.save_project("u2", _schedule("A", datetime(2026, 5, 1)), b"", "user-1")
        return str(store.get_programs(user_id="user-1")[0]["id"]), older, newer

    def _store_result(
        self, store: InMemoryStore, pid: str, kind: str, payload: dict[str, Any], **v: str
    ) -> None:
        from src.materializer.runtime import _ENGINE_VERSION, _RULESET_VERSIONS

        store.save_derived_artifact(
            pid,
            kind,
            payload,
            v.get("engine", _ENGINE_VERSION),
            v.get("ruleset", _RULESET_VERSIONS[kind]),
            f"hash-{pid}-{kind}-{v}",
            datetime(2026, 1, 1),
        )

    def test_scores_follow_the_revisions_in_date_order(self, store: InMemoryStore) -> None:
        prog, older, newer = self._program(store)
        self._store_result(store, older, "health", {"overall": 61.04})
        self._store_result(store, older, "dcma", {"overall_score": 40.0})
        self._store_result(store, newer, "health", {"overall": 54.0})
        self._store_result(store, newer, "dcma", {"overall_score": 42.86})
        data = TestClient(app).get(f"/api/v1/programs/{prog}/trends").json()
        assert data["health_scores"] == [61.0, 54.0]
        assert data["dcma_scores"] == [40.0, 42.9]
        assert data["alert_counts"] == [None, None]

    def test_a_result_from_an_older_engine_is_a_gap(self, store: InMemoryStore) -> None:
        prog, older, newer = self._program(store)
        self._store_result(store, older, "health", {"overall": 61.0}, engine="4.0")
        self._store_result(store, newer, "health", {"overall": 54.0})
        data = TestClient(app).get(f"/api/v1/programs/{prog}/trends").json()
        assert data["health_scores"] == [None, 54.0]
        assert data["dcma_scores"] == [None, None]


class TestBatchArtifactRead:
    """SupabaseStore.get_latest_derived_artifacts: one query, newest row decides."""

    def test_query_asks_for_current_rows_newest_first(self) -> None:
        a, b = "00000000-0000-4000-8000-00000000000a", "00000000-0000-4000-8000-00000000000b"
        rows = [  # as the query returns them: current engine, newest first
            {
                "project_id": a,
                "artifact_kind": "health",
                "engine_version": "8",
                "ruleset_version": "h1",
                "payload": {"overall": 2},
            },
            {
                "project_id": a,
                "artifact_kind": "health",
                "engine_version": "8",
                "ruleset_version": "h1",
                "payload": {"overall": 1},
            },
            {
                "project_id": b,
                "artifact_kind": "dcma",
                "engine_version": "8",
                "ruleset_version": "old",
            },
        ]
        store, client = _supabase({"schedule_derived_artifacts": rows})
        got = store.get_latest_derived_artifacts(
            [a, b, "not-a-uuid"], {"health": "h1", "dcma": "d1"}, "8"
        )
        # The newest row of a pair wins; a row of another ruleset is not used.
        assert set(got) == {(a, "health")}
        assert got[(a, "health")]["payload"] == {"overall": 2}
        assert [q.table for q in client.executed] == ["schedule_derived_artifacts"]
        calls = client.executed[0].calls
        assert ("in_", (("project_id", [a, b]), {})) in calls
        assert ("in_", (("artifact_kind", ["health", "dcma"]), {})) in calls
        assert ("eq", (("engine_version", "8"), {})) in calls
        assert ("eq", (("is_stale", False), {})) in calls
        assert ("order", (("computed_at",), {"desc": True})) in calls

    def test_ids_go_in_batches_of_100(self) -> None:
        import uuid as _uuid

        ids = [str(_uuid.uuid4()) for _ in range(250)]
        store, client = _supabase({})
        store.get_latest_derived_artifacts(ids, {"health": "h1"}, "8")
        sizes = [
            len(args[0][1])
            for q in client.executed
            for name, args in q.calls
            if name == "in_" and args[0][0] == "project_id"
        ]
        assert sizes == [100, 100, 50]

    def test_nothing_to_ask_sends_nothing(self) -> None:
        store, client = _supabase({})
        assert store.get_latest_derived_artifacts(["not-a-uuid"], {"health": "h1"}, "8") == {}
        assert client.executed == []
