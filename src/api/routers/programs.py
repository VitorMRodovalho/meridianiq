# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Programs router — group uploads under programs with revision tracking."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from typing import Any

from src.database.store import ProgramPlacementError, newest_first
from src.materializer.runtime import _ENGINE_VERSION, _RULESET_VERSIONS

from ..access import AccessContext, get_access, owned_project
from ..auth import optional_auth
from ..deps import RATE_LIMIT_MODERATE, get_store, limiter
from ..kpi_helpers import schedule_kpi_bundle
from ..schemas import (
    ProgramPlacement,
    ProgramPlacementBatchRequest,
    ProgramPlacementBatchResponse,
    ProgramTarget,
    UpdateProgramRequest,
)

# Postgres SQLSTATE for a UNIQUE violation, as PostgREST reports it.
_UNIQUE_VIOLATION = "23505"

router = APIRouter()


@router.get("/api/v1/programs")
def list_programs(_user: object = Depends(optional_auth)):
    """Return all programs with latest revision info."""
    store = get_store()
    user_id = _user["id"] if _user else None
    programs = store.get_programs(user_id=user_id)
    return {"programs": programs}


@router.get("/api/v1/programs/{program_id}")
def get_program_detail(program_id: str, _user: object = Depends(optional_auth)):
    """Return a program with all its revisions."""
    store = get_store()
    user_id = _user["id"] if _user else None
    if user_id:
        program = store.get_program(program_id, user_id)
    else:
        # Anonymous development caller: no owner to match, so scan.
        program = next((p for p in store.get_programs() if p["id"] == program_id), None)
    if program is None:
        raise HTTPException(status_code=404, detail="Program not found")
    revisions = store.get_program_revisions(program_id, user_id=user_id)
    latest = revisions[0] if revisions else None
    program = {**program, "latest_revision": latest, "revision_count": len(revisions)}
    return {"program": program, "revisions": revisions}


@router.put("/api/v1/programs/{program_id}")
@limiter.limit(RATE_LIMIT_MODERATE)
def update_program(
    request: Request,
    program_id: str,
    body: UpdateProgramRequest,
    _user: object = Depends(optional_auth),
):
    """Rename or update a program."""
    store = get_store()
    user_id = _user["id"] if _user else None
    try:
        updated = store.update_program(
            program_id, body.model_dump(exclude_none=True), user_id=user_id
        )
    except Exception as exc:
        # Program names are unique per user, case-insensitively.
        if getattr(exc, "code", None) == _UNIQUE_VIOLATION:
            raise HTTPException(
                status_code=409, detail="You already have a program with that name"
            ) from exc
        raise
    if updated is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return {"program": updated}


def _rounded(value: Any) -> float | None:
    return round(float(value), 1) if isinstance(value, (int, float)) else None


def _kpis_from_artifacts(
    dcma: dict[str, Any] | None, health: dict[str, Any] | None, cpm: dict[str, Any] | None
) -> dict[str, Any]:
    """The rollup's KPI fields, from stored artifact payloads (same keys and
    rounding as ``schedule_kpi_bundle``)."""
    out: dict[str, Any] = {}
    if cpm is not None:
        out["critical_path_length_days"] = round(float(cpm.get("project_duration") or 0), 2)
        out["critical_activities_count"] = len(cpm.get("critical_path") or [])
        out["has_cycles"] = bool(cpm.get("has_cycles"))
        results = cpm.get("activity_results") or {}
        out["negative_float_count"] = sum(
            1
            for r in results.values()
            if isinstance(r, dict) and float(r.get("total_float") or 0) < 0
        )
    if dcma is not None:
        out["dcma_score"] = round(float(dcma.get("overall_score") or 0), 1)
        out["dcma_passed_count"] = dcma.get("passed_count")
        out["dcma_failed_count"] = dcma.get("failed_count")
    if health is not None:
        out["health_score"] = round(float(health.get("overall") or 0), 1)
        out["health_rating"] = health.get("rating")
        out["health_trend_arrow"] = health.get("trend_arrow")
    return out


def _payload(row: dict[str, Any] | None) -> dict[str, Any] | None:
    payload = (row or {}).get("payload")
    return payload if isinstance(payload, dict) else None


def _build_rollup(program_id: str, revisions: list[dict], user_id: str | None = None) -> dict:
    """Build the program rollup payload from a revisions list.

    Extracted so both the HTTP endpoint and other callers (exec-summary
    PDF enrichment) can reuse the same computation path. The KPIs come from
    the artifacts the materializer stored for the latest and previous
    revisions (ADR-0014/0015); recomputing them parsed two schedules per
    request and took over 13 s on a cold cache for 10k-activity schedules
    (measured 2026-10-10). ``schedule_kpi_bundle`` is the fallback for a
    revision with no current artifacts (not yet materialized).
    """
    revisions = newest_first(revisions)
    latest = revisions[0]
    prev = revisions[1] if len(revisions) > 1 else None
    store = get_store()

    latest_metrics: dict = {
        "activity_count": latest.get("activity_count"),
        "relationship_count": latest.get("relationship_count"),
        "revision_number": latest.get("revision_number"),
        "data_date": latest.get("data_date"),
    }

    ids = [str(latest["id"])] + ([str(prev["id"])] if prev else [])
    stored = store.get_latest_derived_artifacts(
        ids, {kind: _RULESET_VERSIONS[kind] for kind in ("health", "dcma")}, _ENGINE_VERSION
    )
    latest_id = str(latest["id"])
    cpm_row = store.get_latest_derived_artifact(
        latest_id, "cpm", _ENGINE_VERSION, _RULESET_VERSIONS["cpm"]
    )
    dcma = _payload(stored.get((latest_id, "dcma")))
    health = _payload(stored.get((latest_id, "health")))
    cpm = _payload(cpm_row)
    if dcma is not None and health is not None and cpm is not None:
        latest_metrics.update(_kpis_from_artifacts(dcma, health, cpm))
    else:
        bundle = schedule_kpi_bundle(latest["id"], user_id)
        if bundle:
            latest_metrics.update(bundle)

    trend_direction = "stable"
    trend_delta: float | None = None
    if prev and "health_score" in latest_metrics:
        prev_health_payload = _payload(stored.get((str(prev["id"]), "health")))
        if prev_health_payload is not None:
            prev_health = _kpis_from_artifacts(None, prev_health_payload, None).get("health_score")
        else:
            prev_health = schedule_kpi_bundle(prev["id"], user_id).get("health_score")
        if prev_health is not None:
            trend_delta = round(latest_metrics["health_score"] - prev_health, 1)
            if trend_delta > 2:
                trend_direction = "improving"
            elif trend_delta < -2:
                trend_direction = "degrading"

    return {
        "program_id": program_id,
        "revision_count": len(revisions),
        "latest_revision_id": latest["id"],
        "latest_revision_number": latest.get("revision_number"),
        "latest_data_date": latest.get("data_date"),
        "latest_metrics": latest_metrics,
        "trend_direction": trend_direction,
        "trend_delta": trend_delta,
        "previous_revision_id": prev["id"] if prev else None,
        "previous_revision_number": prev.get("revision_number") if prev else None,
    }


def compute_program_rollup(program_id: str, user_id: str | None = None) -> dict | None:
    """Return a rollup dict for a program, or None when it has no revisions.

    Plain-callable version of the /rollup endpoint so other reports (e.g.
    executive summary PDF) can embed rollup context without going through
    ``Depends(optional_auth)``.
    """
    store = get_store()
    revisions = (
        store.get_program_revisions(program_id, user_id)
        if hasattr(store, "get_program_revisions")
        else []
    )
    if not revisions:
        return None
    return _build_rollup(program_id, revisions, user_id=user_id)


@router.get("/api/v1/programs/{program_id}/rollup")
def get_program_rollup(program_id: str, _user: object = Depends(optional_auth)):
    """Aggregated KPIs across a program's revisions.

    Computes CPM + DCMA + health on the latest revision and compares its
    health score against the previous revision for trend direction. Gives
    Program Directors a one-call summary (CP length, negative float,
    DCMA score, health + trend) without drilling into each revision.

    Reference: DCMA 14-Point Assessment; AACE RP 29R-03.
    """
    store = get_store()
    user_id = _user["id"] if _user else None  # type: ignore[index]

    revisions = (
        store.get_program_revisions(program_id, user_id)
        if hasattr(store, "get_program_revisions")
        else []
    )
    if not revisions:
        raise HTTPException(status_code=404, detail="Program not found or no revisions")

    return _build_rollup(program_id, revisions, user_id=user_id)


@router.get("/api/v1/programs/{program_id}/trends")
def get_program_trends(program_id: str, _user: object = Depends(optional_auth)):
    """Trend data across all revisions for charting."""
    store = get_store()
    user_id = _user["id"] if _user else None
    revisions = (
        store.get_program_revisions(program_id, user_id)
        if hasattr(store, "get_program_revisions")
        else []
    )
    if not revisions:
        raise HTTPException(status_code=404, detail="Program not found or no revisions")

    # Oldest first, by data date, for the chart's time axis. Revisions with
    # no data date cannot be placed in time; they come first, labelled "Rev N".
    revisions = list(reversed(newest_first(revisions)))

    trends: dict = {
        "revision_count": len(revisions),
        "labels": [],
        "health_scores": [],
        "dcma_scores": [],
        "alert_counts": [],
        "activity_counts": [],
        "revisions": [],
    }

    # Health and DCMA come from what the materializer stored for each
    # revision (ADR-0014/0015), in one query; nothing is recomputed here. A
    # revision without a current artifact plots as a gap (None). Alerts are
    # not materialized, so their series stays None.
    artifacts = store.get_latest_derived_artifacts(
        [str(r.get("id")) for r in revisions],
        {kind: _RULESET_VERSIONS[kind] for kind in ("health", "dcma")},
        _ENGINE_VERSION,
    )

    for rev in revisions:
        rid = str(rev.get("id"))
        health = (artifacts.get((rid, "health")) or {}).get("payload") or {}
        dcma = (artifacts.get((rid, "dcma")) or {}).get("payload") or {}

        label = rev.get("data_date") or f"Rev {rev.get('revision_number', '?')}"
        trends["labels"].append(str(label))
        trends["health_scores"].append(_rounded(health.get("overall")))
        trends["dcma_scores"].append(_rounded(dcma.get("overall_score")))
        trends["alert_counts"].append(None)
        trends["activity_counts"].append(rev.get("activity_count"))
        trends["revisions"].append(
            {
                "id": rev.get("id"),
                "revision_number": rev.get("revision_number"),
                "data_date": rev.get("data_date"),
                "filename": rev.get("filename"),
            }
        )

    return trends


# ------------------------------------------------------------------ #
# Placing schedules in programs                                      #
# ------------------------------------------------------------------ #

_PROGRAM_NOT_FOUND = "Program not found"


def _owner(ctx: AccessContext) -> str:
    """The signed-in user a placement acts for; programs belong to a user."""
    if ctx.principal.kind not in ("user", "api_key"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return ctx.principal.user_id


def resolve_program_target(store: Any, user_id: str, target: ProgramTarget) -> str:
    """Return the id of the program ``target`` names, creating it if it is new."""
    if target.program_id is not None:
        if store.get_program(target.program_id, user_id) is None:
            raise HTTPException(status_code=404, detail=_PROGRAM_NOT_FOUND)
        return target.program_id
    if target.new_program_name is None:  # the model guarantees one of the two
        raise HTTPException(status_code=422, detail="Name a program")
    return str(store.get_or_create_program(user_id, target.new_program_name))


def _place(store: Any, user_id: str, project_id: str, program_id: str) -> ProgramPlacement:
    try:
        revision, deleted = store.place_project_in_program(user_id, project_id, program_id)
    except ProgramPlacementError as exc:
        if exc.reason == "linked":
            raise HTTPException(
                status_code=409,
                detail="This schedule has confirmed revision links in its current "
                "program; remove them before moving it",
            ) from exc
        raise HTTPException(status_code=404, detail="Project not found") from exc
    return ProgramPlacement(
        project_id=project_id,
        program_id=program_id,
        revision_number=revision,
        source_program_deleted=deleted,
    )


@router.put("/api/v1/projects/{project_id}/program", response_model=ProgramPlacement)
@limiter.limit(RATE_LIMIT_MODERATE)
def place_project(
    request: Request,
    body: ProgramTarget,
    project_id: str = Depends(owned_project),
    ctx: AccessContext = Depends(get_access),
) -> ProgramPlacement:
    """Move a schedule into one of the caller's programs, or into a new one.

    It becomes the program's next revision; revisions are shown by data date.
    The program it left is deleted if that leaves it empty and unshared.
    """
    user_id = _owner(ctx)
    store = get_store()
    program_id = resolve_program_target(store, user_id, body)
    return _place(store, user_id, project_id, program_id)


@router.post("/api/v1/programs/placements", response_model=ProgramPlacementBatchResponse)
@limiter.limit(RATE_LIMIT_MODERATE)
def place_projects(
    request: Request,
    body: ProgramPlacementBatchRequest,
    ctx: AccessContext = Depends(get_access),
) -> ProgramPlacementBatchResponse:
    """Move several schedules into one program.

    Every id is checked before anything moves: one the caller cannot reach
    makes the whole request a 404. The moves then run one by one; if one is
    refused (409), the ones before it stay moved, and a retry is safe because
    moving a schedule into the program it is in changes nothing.
    """
    user_id = _owner(ctx)
    project_ids = ctx.projects(list(dict.fromkeys(body.project_ids)))
    store = get_store()
    program_id = resolve_program_target(store, user_id, body)
    placements = [_place(store, user_id, pid, program_id) for pid in project_ids]
    return ProgramPlacementBatchResponse(program_id=program_id, placements=placements)
