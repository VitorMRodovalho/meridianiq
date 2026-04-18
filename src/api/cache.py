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
_lock = threading.Lock()

F = TypeVar("F", bound=Callable[..., Any])


def cached(namespace: str, ttl: int = _DEFAULT_TTL_SECONDS) -> Callable[[F], F]:
    """Cache a function by its (args, sorted-kwargs) tuple within a namespace.

    Each namespace has its own dict; ``invalidate_namespace`` clears one
    namespace at a time. Entries past their ``ttl`` are recomputed lazily on
    next access (no background sweeper).
    """

    def deco(fn: F) -> F:
        cache = _caches.setdefault(namespace, {})
        stats = _stats.setdefault(namespace, {"hits": 0, "misses": 0})

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
            result = fn(*args, **kwargs)
            with _lock:
                cache[key] = (now + ttl, result)
            return result

        return wrapper  # type: ignore[return-value]

    return deco


def invalidate_namespace(namespace: str) -> int:
    """Drop every entry in a namespace. Returns the number of entries removed."""
    with _lock:
        cache = _caches.get(namespace)
        if not cache:
            return 0
        n = len(cache)
        cache.clear()
        return n


def invalidate_all() -> int:
    """Drop every entry across all namespaces. Returns total entries removed."""
    with _lock:
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
