# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Cached KPI aggregates used by program rollup + BI connector endpoints.

Both ``/api/v1/programs/{id}/rollup`` and ``/api/v1/bi/projects`` recompute
the same DCMA + Health + CPM bundle on every request. Centralising the
compute here lets the in-memory TTL cache amortise the work across both
surfaces and across repeated polls from BI dashboards.

The cache key is ``(project_id, user_id)`` — when an upload replaces the
schedule, the upload endpoint calls ``invalidate_namespace("schedule:kpis")``
to drop stale entries. Otherwise the 120s TTL keeps responses fresh enough
for executive dashboards while coalescing rapid polls.
"""

from __future__ import annotations

from typing import Any

from .cache import cached
from .deps import get_store


@cached(namespace="schedule:kpis", ttl=120)
def schedule_kpi_bundle(project_id: str, user_id: str | None) -> dict[str, Any]:
    """Return the canonical DCMA / Health / CPM aggregates for one schedule.

    Returns an empty dict if the schedule is missing. Each engine is wrapped
    in try/except so a single engine failure (e.g. CPM cycle) doesn't poison
    the whole bundle.
    """
    store = get_store()
    schedule = store.get(project_id, user_id=user_id)
    if schedule is None:
        return {}

    out: dict[str, Any] = {
        "activity_count": len(schedule.activities),
        "relationship_count": len(schedule.relationships),
    }

    try:
        from src.analytics.cpm import CPMCalculator

        cpm = CPMCalculator(schedule).calculate()
        out["critical_path_length_days"] = round(cpm.project_duration, 2)
        out["critical_activities_count"] = len(cpm.critical_path)
        out["has_cycles"] = cpm.has_cycles
        out["negative_float_count"] = sum(
            1 for ar in cpm.activity_results.values() if ar.total_float < 0
        )
    except Exception:
        pass

    try:
        from src.analytics.dcma14 import DCMA14Analyzer

        dcma = DCMA14Analyzer(schedule).analyze()
        out["dcma_score"] = round(dcma.overall_score, 1)
        out["dcma_passed_count"] = dcma.passed_count
        out["dcma_failed_count"] = dcma.failed_count
    except Exception:
        pass

    try:
        from src.analytics.health_score import HealthScoreCalculator

        h = HealthScoreCalculator(schedule).calculate()
        out["health_score"] = round(h.overall, 1)
        out["health_rating"] = h.rating
        out["health_trend_arrow"] = h.trend_arrow
    except Exception:
        pass

    return out
