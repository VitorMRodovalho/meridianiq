# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""GET /api/v1/health/db: the probe the uptime workflow polls.

``/health`` never touches the database, so it answered 200 on 2026-10-09
while the Supabase project was paused and its hostnames did not resolve.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.routers import health


class _Store:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def database_reachable(self) -> bool:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return True


@pytest.fixture(autouse=True)
def _fresh_probe() -> Iterator[None]:
    health.reset_database_probe()
    yield
    health.reset_database_probe()


def _use(monkeypatch: pytest.MonkeyPatch, store: object) -> None:
    monkeypatch.setattr(health, "get_store", lambda: store)


def test_a_reachable_database_answers_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _Store())

    resp = TestClient(app).get("/api/v1/health/db")

    assert (resp.status_code, resp.json()) == (200, {"database": "ok"})


def test_an_unreachable_database_answers_503_without_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use(
        monkeypatch,
        _Store(ConnectionError("db.example-ref.supabase.co: Name or service not known")),
    )

    resp = TestClient(app).get("/api/v1/health/db")

    assert (resp.status_code, resp.json()) == (503, {"database": "unavailable"})
    assert "supabase" not in resp.text


def test_the_in_memory_store_is_reported_as_such() -> None:
    resp = TestClient(app).get("/api/v1/health/db")

    assert (resp.status_code, resp.json()) == (200, {"database": "in_memory"})


def test_requests_within_the_ttl_reuse_one_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    _use(monkeypatch, store)
    client = TestClient(app)

    for _ in range(3):
        assert client.get("/api/v1/health/db").status_code == 200

    assert store.calls == 1


def test_a_stale_answer_is_probed_again(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    _use(monkeypatch, store)
    client = TestClient(app)
    client.get("/api/v1/health/db")

    monkeypatch.setattr(health, "DB_PROBE_TTL_S", 0.0)
    store.error = ConnectionError("down")
    resp = client.get("/api/v1/health/db")

    assert (resp.status_code, store.calls) == (503, 2)


def test_the_supabase_store_reads_one_row_of_projects() -> None:
    from src.database.store import SupabaseStore

    seen: list[tuple[str, object]] = []

    class _Query:
        def select(self, *cols: str) -> _Query:
            seen.append(("select", cols))
            return self

        def limit(self, n: int) -> _Query:
            seen.append(("limit", n))
            return self

        def execute(self) -> object:
            seen.append(("execute", None))
            return object()

    class _Client:
        def table(self, name: str) -> _Query:
            seen.append(("table", name))
            return _Query()

    store = SupabaseStore.__new__(SupabaseStore)
    store._client = _Client()  # type: ignore[assignment]

    assert store.database_reachable() is True
    assert seen == [("table", "projects"), ("select", ("id",)), ("limit", 1), ("execute", None)]
