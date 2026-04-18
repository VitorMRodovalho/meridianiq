# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the in-memory TTL cache used by /programs/rollup and /bi/* endpoints."""

from __future__ import annotations

import time

import pytest

from src.api.cache import (
    cache_stats,
    cached,
    invalidate_all,
    invalidate_namespace,
)


@pytest.fixture(autouse=True)
def _reset_cache_state() -> None:
    """Each test starts with a clean cache so namespaces don't leak across tests."""
    invalidate_all()


def test_first_call_misses_second_call_hits() -> None:
    calls = {"n": 0}

    @cached("test:basic", ttl=60)
    def compute(x: int) -> int:
        calls["n"] += 1
        return x * 2

    assert compute(5) == 10
    assert compute(5) == 10
    assert calls["n"] == 1

    stats = cache_stats()["test:basic"]
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1


def test_different_args_produce_distinct_cache_entries() -> None:
    @cached("test:args", ttl=60)
    def compute(x: int, y: int = 0) -> int:
        return x + y

    compute(1, y=2)
    compute(3, y=4)
    compute(1, y=2)  # hit

    stats = cache_stats()["test:args"]
    assert stats["misses"] == 2
    assert stats["hits"] == 1
    assert stats["size"] == 2


def test_ttl_expiry_recomputes() -> None:
    calls = {"n": 0}

    @cached("test:ttl", ttl=1)
    def compute() -> int:
        calls["n"] += 1
        return calls["n"]

    assert compute() == 1
    assert compute() == 1
    time.sleep(1.1)
    assert compute() == 2  # TTL expired, recomputed


def test_invalidate_namespace_clears_only_one() -> None:
    @cached("test:ns_a", ttl=60)
    def fn_a() -> int:
        return 1

    @cached("test:ns_b", ttl=60)
    def fn_b() -> int:
        return 2

    fn_a()
    fn_b()
    assert cache_stats()["test:ns_a"]["size"] == 1
    assert cache_stats()["test:ns_b"]["size"] == 1

    removed = invalidate_namespace("test:ns_a")
    assert removed == 1
    assert cache_stats()["test:ns_a"]["size"] == 0
    assert cache_stats()["test:ns_b"]["size"] == 1


def test_invalidate_all_clears_every_namespace() -> None:
    @cached("test:all_a", ttl=60)
    def fn_a() -> int:
        return 1

    @cached("test:all_b", ttl=60)
    def fn_b() -> int:
        return 2

    fn_a()
    fn_b()

    removed = invalidate_all()
    assert removed == 2
    assert cache_stats()["test:all_a"]["size"] == 0
    assert cache_stats()["test:all_b"]["size"] == 0


def test_invalidate_unknown_namespace_returns_zero() -> None:
    assert invalidate_namespace("does:not:exist") == 0


def test_kwargs_order_does_not_affect_cache_key() -> None:
    calls = {"n": 0}

    @cached("test:kwargs", ttl=60)
    def compute(**kwargs: int) -> int:
        calls["n"] += 1
        return sum(kwargs.values())

    compute(a=1, b=2, c=3)
    compute(c=3, a=1, b=2)  # same kwargs, different call order
    assert calls["n"] == 1


def test_none_user_id_distinct_from_empty_string() -> None:
    """user_id=None and user_id='' should not collide in the cache key."""

    @cached("test:userid", ttl=60)
    def fn(user_id: str | None) -> str:
        return f"user={user_id!r}"

    a = fn(None)
    b = fn("")
    assert a != b
    assert cache_stats()["test:userid"]["size"] == 2


def test_invalidate_during_compute_does_not_re_poison() -> None:
    """Classic cache-invalidation race: a cache-miss starts computing,
    ``invalidate_namespace`` fires while the compute is in flight, the
    compute finishes and would otherwise write its now-stale result back
    to a cache that was just cleared. The generation counter must cause
    the write-back to be skipped; next access must see a clean miss.
    """

    @cached("test:race", ttl=60)
    def compute(x: int) -> int:
        # Simulate the invalidation firing in the middle of compute. The
        # real production case is a concurrent upload request — here we
        # just do it inline so the timing is deterministic.
        invalidate_namespace("test:race")
        return x * 10

    result = compute(7)
    assert result == 70  # caller still observes the computed value

    # The key insight: the cache must NOT contain the stale write-back.
    # If the race were unfixed, size would be 1 (poisoned). With the
    # generation-counter fix, the compute's write is skipped.
    assert cache_stats()["test:race"]["size"] == 0, (
        "invalidate during compute must cause the write-back to be dropped; "
        "otherwise the cache is re-poisoned for the full TTL"
    )


def test_generation_counter_resumes_caching_after_invalidate() -> None:
    """After an invalidate, subsequent misses must cache normally — the
    generation counter must not permanently block writes to the namespace.
    """
    calls = {"n": 0}

    @cached("test:gen", ttl=60)
    def compute(x: int) -> int:
        calls["n"] += 1
        return x

    compute(1)
    assert cache_stats()["test:gen"]["size"] == 1
    invalidate_namespace("test:gen")
    assert cache_stats()["test:gen"]["size"] == 0
    compute(2)
    assert cache_stats()["test:gen"]["size"] == 1
    compute(2)
    # Second call on arg=2 should hit the cache — proves post-invalidate
    # writes resume normally.
    assert calls["n"] == 2
