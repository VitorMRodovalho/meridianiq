# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Cache-hygiene lint for ADR-0012 Wave 0 #4.

Every namespace declared via ``@cached(namespace="X")`` MUST have at least one
matching ``invalidate_namespace("X")`` call in production code (``src/``). Test
fixtures don't count — a cache that is only cleared by test teardown will
serve stale data in production.

v3.9.0 shipped with ``@cached(namespace="schedule:kpis")`` wired up but zero
production invalidation call sites — every KPI read served stale aggregates
until the 120s TTL expired, across every user, regardless of upload activity.
This lint exists so that failure mode cannot regress silently.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

_CACHED_DECL = re.compile(
    r"""@cached\s*\(\s*namespace\s*=\s*["'](?P<ns>[^"']+)["']""",
    re.VERBOSE,
)
_INVALIDATE_CALL = re.compile(
    r"""invalidate_namespace\s*\(\s*["'](?P<ns>[^"']+)["']""",
    re.VERBOSE,
)


def _scan(pattern: re.Pattern[str]) -> dict[str, list[str]]:
    """Return a mapping of namespace -> list of 'path:lineno' occurrences."""
    hits: dict[str, list[str]] = {}
    for py in SRC_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            ns = match.group("ns")
            lineno = text.count("\n", 0, match.start()) + 1
            rel = py.relative_to(REPO_ROOT)
            hits.setdefault(ns, []).append(f"{rel}:{lineno}")
    return hits


def test_every_cached_namespace_has_matching_invalidate() -> None:
    """Each @cached namespace in src/ must have at least one invalidate_namespace
    call site in src/ — otherwise stale entries live out their full TTL after
    the underlying data changes."""
    declared = _scan(_CACHED_DECL)
    invalidated = _scan(_INVALIDATE_CALL)

    orphans: list[str] = []
    for ns, sites in declared.items():
        if ns not in invalidated:
            orphans.append(
                f"{ns!r} declared at {', '.join(sites)} — no matching invalidate_namespace call"
            )

    assert not orphans, (
        "Cache hygiene violated (ADR-0012 Wave 0 #4): "
        + "; ".join(orphans)
        + ". Every @cached namespace must have at least one invalidate_namespace "
        "call in src/ covering the upstream state change (upload, analysis update, etc.)."
    )


def test_schedule_kpis_invalidation_is_wired_to_upload_and_delete_flows() -> None:
    """The ``schedule:kpis`` namespace must be invalidated from every upstream
    path that mutates the underlying schedule state — ingestion (upload) AND
    deletion (GDPR erasure). Missing either leaves stale KPI bundles cached
    for up to the full 120s TTL, which for the GDPR path is a secondary-copy
    retention of personal data after right-to-erasure."""
    invalidated = _scan(_INVALIDATE_CALL)
    sites = invalidated.get("schedule:kpis", [])
    paths = {site.split(":")[0] for site in sites}

    required = {
        "api/routers/upload.py": "HTTP upload happy-path",
        "mcp_server.py": "MCP upload_xer tool",
        "api/routers/admin.py": "GDPR right-to-erasure delete",
    }
    missing: list[str] = []
    for fragment, reason in required.items():
        if not any(fragment in p for p in paths):
            missing.append(f"{fragment} ({reason})")

    assert not missing, (
        "schedule:kpis must be invalidated from every schedule-state-mutating "
        "path. Missing call sites: " + "; ".join(missing) + f". Found sites: {sites}"
    )
