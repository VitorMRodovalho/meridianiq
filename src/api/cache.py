# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""In-memory TTL cache for hot read endpoints.

Used by program rollup and BI connector endpoints, both of which recompute
CPM / DCMA / Health on every request. With this cache, repeated polls from
BI dashboards (Power BI, Tableau) and program-director dashboards coalesce
to a single computation per TTL window.

Design choices:
- Namespace-scoped so different endpoints can share the module without
  colliding on cache keys.
- Time-bounded (TTL) — no LRU eviction. Caches are small (one entry per
  unique-key-tuple); upload-driven invalidation handles the "schedule
  changed" case.
- Single-process: deliberate. MeridianIQ deploys to one Fly.io instance;
  Redis would add infrastructure for marginal benefit.
- Stats counters surfaced via ``cache_stats()`` for /admin observability.

Reference: PEP 8; Cargo Cult Programming antipattern (Erlich, 2008) — keep
this module under ~80 lines, no premature abstraction.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Hashable
from functools import wraps
from typing import Any, TypeVar

_DEFAULT_TTL_SECONDS = 60

_caches: dict[str, dict[Hashable, tuple[float, Any]]] = {}
_stats: dict[str, dict[str, int]] = {}
# Monotonic per-namespace generation. Bumped by ``invalidate_namespace``;
# wrappers capture the value at miss-time and refuse to write back if the
# generation changed during compute — closes the classic "read-compute-write
# after invalidate" race that would otherwise re-poison the cache.
_generations: dict[str, int] = {}
_lock = threading.Lock()

F = TypeVar("F", bound=Callable[..., Any])


def cached(namespace: str, ttl: int = _DEFAULT_TTL_SECONDS) -> Callable[[F], F]:
    """Cache a function by its (args, sorted-kwargs) tuple within a namespace.

    Each namespace has its own dict; ``invalidate_namespace`` clears one
    namespace at a time. Entries past their ``ttl`` are recomputed lazily on
    next access (no background sweeper).

    Invalidation race: between a cache-miss and the write-back, the compute
    runs without the lock held. If ``invalidate_namespace`` fires during that
    window, the wrapper would otherwise write a now-stale value and poison
    the cache for the full TTL. A per-namespace generation counter is
    captured at miss-time and re-checked before the write-back; a mismatch
    means an invalidate happened during compute and the write is skipped.
    """

    def deco(fn: F) -> F:
        cache = _caches.setdefault(namespace, {})
        stats = _stats.setdefault(namespace, {"hits": 0, "misses": 0})
        _generations.setdefault(namespace, 0)

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            with _lock:
                entry = cache.get(key)
                if entry is not None and entry[0] > now:
                    stats["hits"] += 1
                    return entry[1]
                stats["misses"] += 1
                gen_at_miss = _generations.get(namespace, 0)
            result = fn(*args, **kwargs)
            with _lock:
                # Skip the write if the namespace was invalidated while we
                # were computing — otherwise we'd overwrite a fresh cleared
                # state with a now-stale value.
                if _generations.get(namespace, 0) == gen_at_miss:
                    cache[key] = (now + ttl, result)
            return result

        return wrapper  # type: ignore[return-value]

    return deco


def invalidate_namespace(namespace: str) -> int:
    """Drop every entry in a namespace. Returns the number of entries removed.

    Also bumps the namespace generation counter so any in-flight compute that
    started before this call will skip its write-back on completion.
    """
    with _lock:
        _generations[namespace] = _generations.get(namespace, 0) + 1
        cache = _caches.get(namespace)
        if not cache:
            return 0
        n = len(cache)
        cache.clear()
        return n


def invalidate_all() -> int:
    """Drop every entry across all namespaces. Returns total entries removed."""
    with _lock:
        for ns in _caches:
            _generations[ns] = _generations.get(ns, 0) + 1
        n = sum(len(c) for c in _caches.values())
        for c in _caches.values():
            c.clear()
        return n


def cache_stats() -> dict[str, dict[str, int]]:
    """Per-namespace {hits, misses, size} snapshot. Cheap; safe to expose."""
    with _lock:
        return {
            ns: {
                "hits": _stats.get(ns, {}).get("hits", 0),
                "misses": _stats.get(ns, {}).get("misses", 0),
                "size": len(_caches.get(ns, {})),
            }
            for ns in _caches
        }
