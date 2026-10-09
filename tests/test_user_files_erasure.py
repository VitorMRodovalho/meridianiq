# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""The user's data erasure removes their uploaded files from Storage.

Before this, no code path removed a Storage object: measured 2026-10-09,
0 ``.remove(`` calls in ``src/`` and 25 objects in production, 3 of them
with no ``projects`` row. The fake bucket here lists like Supabase Storage
(one level per call, folders without an id) and removes what it is told.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.api.routers import admin
from src.database.store import InMemoryStore
from tests.test_store_persistence import MockSupabaseStore, _MockClient

USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"


class _FakeBucket:
    def __init__(self, names: set[str], *, removes: bool = True) -> None:
        self.names = set(names)
        self.removes = removes
        self.remove_calls: list[list[str]] = []

    def from_(self, bucket: str) -> _FakeBucket:
        return self

    def list(self, path: str | None = None, options: dict[str, Any] | None = None) -> list[dict]:
        """One level, sorted by name, paged by limit/offset (storage3 defaults: 100, 0)."""
        options = options or {}
        limit, offset = int(options.get("limit", 100)), int(options.get("offset", 0))
        prefix = f"{path}/" if path else ""
        level: dict[str, bool] = {}
        for name in self.names:
            if name.startswith(prefix):
                head, _, rest = name[len(prefix) :].partition("/")
                level[head] = level.get(head, False) or bool(rest)
        entries = [{"name": n, "id": None if level[n] else f"id-{n}"} for n in sorted(level)]
        return entries[offset : offset + limit]

    def remove(self, paths: list[str]) -> list[dict]:
        """Returns the objects it deleted, as the Storage API does."""
        self.remove_calls.append(list(paths))
        if not self.removes:
            return []
        gone = [p for p in paths if p in self.names]
        self.names -= set(gone)
        return [{"name": p} for p in gone]


class _Client(_MockClient):
    def __init__(self, tables: dict[str, list[dict[str, Any]]], bucket: _FakeBucket) -> None:
        super().__init__(tables)
        self.storage = bucket


def _store(bucket: _FakeBucket, projects: list[dict[str, Any]]) -> MockSupabaseStore:
    store = MockSupabaseStore()
    store._tables["projects"] = projects
    store._client = _Client(store._tables, bucket)  # type: ignore[assignment]
    return store


A_FILES = {f"{USER_A}/up1/Tower.xer", f"{USER_A}/up2/Plant.xer", f"{USER_A}/up3/orphan.xer"}
B_FILE = f"{USER_B}/up9/Other.xer"


def test_removes_every_file_in_the_users_folder_and_nothing_else() -> None:
    bucket = _FakeBucket(A_FILES | {B_FILE, "anonymous/up0/schedule.xer"})
    projects = [
        {"user_id": USER_A, "storage_path": f"{USER_A}/up1/Tower.xer"},
        {"user_id": USER_A, "storage_path": f"{USER_A}/up2/Plant.xer"},
        {"user_id": USER_B, "storage_path": B_FILE},
    ]

    removed = _store(bucket, projects).delete_user_files(USER_A)

    assert removed == 3  # the orphan without a row too
    assert bucket.names == {B_FILE, "anonymous/up0/schedule.xer"}


def test_a_slash_in_the_schedule_name_nests_deeper_and_is_still_removed() -> None:
    """The file name is the schedule's short name, unsanitised: ``A/B`` nests."""
    deep = f"{USER_A}/up1/Block A/Level 2/Tower.xer"
    bucket = _FakeBucket({deep, B_FILE})

    assert _store(bucket, []).delete_user_files(USER_A) == 1
    assert bucket.names == {B_FILE}


def test_more_than_a_page_of_uploads_is_removed() -> None:
    names = {f"{USER_A}/up{i:04d}/s.xer" for i in range(1001)}
    bucket = _FakeBucket(names | {B_FILE})

    assert _store(bucket, []).delete_user_files(USER_A) == 1001
    assert bucket.names == {B_FILE}


def test_a_row_whose_file_is_already_gone_is_not_counted() -> None:
    bucket = _FakeBucket({f"{USER_A}/up1/Tower.xer"})
    projects = [
        {"user_id": USER_A, "storage_path": f"{USER_A}/up1/Tower.xer"},
        {"user_id": USER_A, "storage_path": f"{USER_A}/up2/gone.xer"},
    ]

    assert _store(bucket, projects).delete_user_files(USER_A) == 1


def test_a_row_pointing_outside_the_users_folder_is_not_followed() -> None:
    bucket = _FakeBucket({B_FILE})
    projects = [{"user_id": USER_A, "storage_path": B_FILE}]

    assert _store(bucket, projects).delete_user_files(USER_A) == 0
    assert bucket.names == {B_FILE}


@pytest.mark.parametrize("bad", ["", "anonymous", "../x", f"{USER_A}/up1"])
def test_a_non_uuid_id_lists_and_removes_nothing(bad: str) -> None:
    """An empty id would make the prefix the whole bucket."""
    bucket = _FakeBucket(A_FILES | {B_FILE})

    with pytest.raises(ValueError):
        _store(bucket, []).delete_user_files(bad)
    assert bucket.remove_calls == []


def test_files_still_listed_after_removal_raise() -> None:
    bucket = _FakeBucket(A_FILES, removes=False)

    with pytest.raises(RuntimeError):
        _store(bucket, []).delete_user_files(USER_A)
    # Control: the same store with a working bucket finishes.
    assert _store(_FakeBucket(A_FILES), []).delete_user_files(USER_A) == 3


def _erase(monkeypatch: pytest.MonkeyPatch, store: Any) -> Any:
    monkeypatch.setattr(admin, "get_store", lambda: store)
    return admin.delete_user_data(_user={"id": USER_A})


def test_route_reports_the_files_and_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryStore()
    store.delete_user_files = lambda user_id: 3  # type: ignore[attr-defined]

    response = _erase(monkeypatch, store)

    assert (response.deleted_files, response.status) == (3, "complete")


class _RowsStore(InMemoryStore):
    """Records whether the route went on to delete the rows."""

    def __init__(self, files_fail: bool) -> None:
        super().__init__()
        self.files_fail = files_fail
        self.rpc_calls: list[str] = []
        store = self

        class _Client:
            def rpc(self, name: str, params: dict[str, Any]) -> Any:
                store.rpc_calls.append(name)
                raise RuntimeError("stop here")

            def table(self, name: str) -> Any:
                raise RuntimeError("stop here")

        self._client = _Client()

    def delete_user_files(self, user_id: str) -> int:
        if self.files_fail:
            raise RuntimeError("storage down")
        return 2


def test_route_keeps_the_rows_and_reports_partial_when_storage_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _RowsStore(files_fail=True)

    response = _erase(monkeypatch, store)

    assert (response.deleted_files, response.status) == (0, "partial")
    assert store.rpc_calls == []  # the rows still point at the files for the retry
    # Control: when Storage finishes, the route does go on to the rows.
    ok = _RowsStore(files_fail=False)
    _erase(monkeypatch, ok)
    assert ok.rpc_calls == ["delete_user_data"]
