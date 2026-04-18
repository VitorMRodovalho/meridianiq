# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for schedule-view cache invalidation (v3.8 wave 11)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_store
from src.database.store import InMemoryStore
from src.parser.models import ParsedSchedule, Project, Relationship, Task


def _schedule(name: str = "Test", n: int = 3) -> ParsedSchedule:
    tasks = [
        Task(task_id=f"T{i}", task_code=f"A{i:04d}", task_name=f"Task {i}") for i in range(1, n + 1)
    ]
    rels = [Relationship(task_id="T2", pred_task_id="T1")] if n >= 2 else []
    return ParsedSchedule(
        projects=[Project(proj_id="P1", proj_short_name=name)],
        activities=tasks,
        relationships=rels,
    )


@pytest.fixture(autouse=True)
def _clear() -> None:
    get_store().clear()


# ---------------------------------------------------------------------------
# Unit tests for InMemoryStore.invalidate_analysis
# ---------------------------------------------------------------------------


class TestInMemoryStoreInvalidate:
    def test_invalidates_matching_prefix(self) -> None:
        store = InMemoryStore()
        store.save_analysis("p1", "schedule_view:none", {"ok": 1})
        store.save_analysis("p1", "schedule_view:base-a", {"ok": 2})
        store.save_analysis("p1", "cpm", {"dur": 30})
        store.save_analysis("p2", "schedule_view:none", {"ok": 3})

        count = store.invalidate_analysis("p1", analysis_type_prefix="schedule_view:")

        assert count == 2
        # schedule_view rows for p1 are gone, other caches survive
        assert store.get_analysis("p1", "schedule_view:none") is None
        assert store.get_analysis("p1", "schedule_view:base-a") is None
        assert store.get_analysis("p1", "cpm") == {"dur": 30}
        assert store.get_analysis("p2", "schedule_view:none") == {"ok": 3}

    def test_invalidates_all_types_when_prefix_none(self) -> None:
        store = InMemoryStore()
        store.save_analysis("p1", "schedule_view:none", {"ok": 1})
        store.save_analysis("p1", "cpm", {"dur": 30})
        store.save_analysis("p2", "cpm", {"dur": 99})

        count = store.invalidate_analysis("p1")

        assert count == 2
        assert store.get_analysis("p1", "schedule_view:none") is None
        assert store.get_analysis("p1", "cpm") is None
        # Other project untouched
        assert store.get_analysis("p2", "cpm") == {"dur": 99}

    def test_returns_zero_when_nothing_matches(self) -> None:
        store = InMemoryStore()
        store.save_analysis("p1", "cpm", {"dur": 30})

        count = store.invalidate_analysis("p1", analysis_type_prefix="schedule_view:")

        assert count == 0
        assert store.get_analysis("p1", "cpm") == {"dur": 30}

    def test_prefix_is_exact_prefix_not_substring(self) -> None:
        store = InMemoryStore()
        store.save_analysis("p1", "schedule_view:none", {"ok": 1})
        store.save_analysis("p1", "view:schedule_view_foo", {"ok": 2})

        count = store.invalidate_analysis("p1", analysis_type_prefix="schedule_view:")

        assert count == 1
        assert store.get_analysis("p1", "view:schedule_view_foo") == {"ok": 2}


# ---------------------------------------------------------------------------
# Router behaviour tests
# ---------------------------------------------------------------------------


class TestScheduleViewCacheBehaviour:
    def test_first_call_populates_cache(self) -> None:
        store = get_store()
        pid = store.add(_schedule(), b"xer")
        assert store.get_analysis(pid, "schedule_view:none:wbs") is None

        client = TestClient(app)
        resp = client.get(f"/api/v1/projects/{pid}/schedule-view")
        assert resp.status_code == 200, resp.text

        # Cache should be populated after first call
        cached = store.get_analysis(pid, "schedule_view:none:wbs")
        assert cached is not None

    def test_force_invalidates_sibling_variants(self) -> None:
        """force=true should drop caches for OTHER baseline variants too."""
        store = get_store()
        pid = store.add(_schedule("current"), b"xer")
        baseline_id = store.add(_schedule("baseline"), b"xer")

        # Seed the cache with two variants
        store.save_analysis(pid, "schedule_view:none", {"stale": True})
        store.save_analysis(pid, f"schedule_view:{baseline_id}", {"stale": True})

        client = TestClient(app)
        resp = client.get(f"/api/v1/projects/{pid}/schedule-view?force=true")
        assert resp.status_code == 200

        # The fresh variant replaced :none; the sibling baseline variant
        # should have been invalidated (no longer returns the stale dict).
        fresh_none = store.get_analysis(pid, "schedule_view:none")
        assert fresh_none != {"stale": True}
        sibling = store.get_analysis(pid, f"schedule_view:{baseline_id}")
        assert sibling is None

    def test_cache_is_used_on_second_call_without_force(self) -> None:
        """Pre-seeded cache must be returned verbatim when force is off."""
        store = get_store()
        pid = store.add(_schedule(), b"xer")
        sentinel = {"project_name": "CACHED-SENTINEL", "activities": []}
        store.save_analysis(pid, "schedule_view:none:wbs", sentinel)

        client = TestClient(app)
        resp = client.get(f"/api/v1/projects/{pid}/schedule-view")
        assert resp.status_code == 200
        # If the cache was honoured, the response equals the sentinel
        assert resp.json().get("project_name") == "CACHED-SENTINEL"

    def test_different_baselines_cached_independently(self) -> None:
        store = get_store()
        pid = store.add(_schedule("A"), b"xer")
        base_a = store.add(_schedule("Base A"), b"xer")
        base_b = store.add(_schedule("Base B"), b"xer")

        client = TestClient(app)
        r1 = client.get(f"/api/v1/projects/{pid}/schedule-view?baseline_id={base_a}")
        r2 = client.get(f"/api/v1/projects/{pid}/schedule-view?baseline_id={base_b}")
        assert r1.status_code == 200
        assert r2.status_code == 200

        # Two distinct cache entries exist
        assert store.get_analysis(pid, f"schedule_view:{base_a}:wbs") is not None
        assert store.get_analysis(pid, f"schedule_view:{base_b}:wbs") is not None


class TestInvalidateCacheEndpoint:
    def test_delete_endpoint_invalidates_all_variants(self) -> None:
        store = get_store()
        pid = store.add(_schedule(), b"xer")
        store.save_analysis(pid, "schedule_view:none", {"x": 1})
        store.save_analysis(pid, "schedule_view:base-xxx", {"x": 2})
        store.save_analysis(pid, "cpm", {"dur": 12})

        client = TestClient(app)
        resp = client.delete(f"/api/v1/projects/{pid}/schedule-view/cache")
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == pid
        assert body["invalidated"] == 2

        assert store.get_analysis(pid, "schedule_view:none") is None
        assert store.get_analysis(pid, "schedule_view:base-xxx") is None
        # Non-schedule-view caches untouched
        assert store.get_analysis(pid, "cpm") == {"dur": 12}

    def test_delete_returns_404_for_unknown_project(self) -> None:
        client = TestClient(app)
        resp = client.delete("/api/v1/projects/does-not-exist/schedule-view/cache")
        assert resp.status_code == 404

    def test_delete_is_idempotent(self) -> None:
        """Calling twice should succeed; second call returns 0."""
        store = get_store()
        pid = store.add(_schedule(), b"xer")
        store.save_analysis(pid, "schedule_view:none", {"x": 1})

        client = TestClient(app)
        first = client.delete(f"/api/v1/projects/{pid}/schedule-view/cache")
        second = client.delete(f"/api/v1/projects/{pid}/schedule-view/cache")
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["invalidated"] == 1
        assert second.json()["invalidated"] == 0
