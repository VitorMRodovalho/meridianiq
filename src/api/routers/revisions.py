# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Revision detection + soft-tombstone + multi-rev trends router.

Cycle 4 W2 PR-A + W3 PR-A — ADR-0022 + Amendment 2.

Endpoints:

- ``POST /api/v1/projects/{id}/detect-revision-of`` — W2 heuristic, no writes
- ``POST /api/v1/projects/{id}/confirm-revision-of`` — W2 append-only INSERT
- ``POST /api/v1/revisions/{id}/tombstone`` — W2 soft-delete + audit_log
- ``GET  /api/v1/projects/{id}/revision-trends`` — W3 multi-rev S-curve overlay

The detection heuristic v1 is encoded in
``src.api.revision_detection.detect_candidate_parent`` per ADR-0022
Amendment 2 (project_name + program_id + data_date; proj_id and
content_hash similarity deferred to W3 / Cycle 5+).

The confirm endpoint is metadata-only post-Cycle-4-W1 redefinition
(per backend-reviewer entry-council fix-up #BLOCKER-1): ``program_id``
linkage already happens at ``save_project`` time via
``get_or_create_program``. Confirm only writes the revision_history row.

Tombstone writes the paired audit_log row mirroring the materialize /
lifecycle pattern at ``src/database/store.py:761`` + ``:938`` +
``:2767``. Best-effort audit write — UPDATE succeeds atomically; audit
insert is logged-on-failure but does not roll back the tombstone.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request

from src.analytics.revision_trends import (
    RevisionTrendsAnalysis,
    analyze_revision_trends,
)

from ..auth import require_auth
from ..deps import RATE_LIMIT_ANALYSIS, RATE_LIMIT_WRITE, get_store, limiter
from ..revision_detection import compute_xer_content_hash, detect_candidate_parent
from ..schemas import (
    ChangePointMarkerSchema,
    ConfirmRevisionOfRequest,
    ConfirmRevisionOfResponse,
    DetectRevisionOfResponse,
    RevisionCurvePoint,
    RevisionCurveSchema,
    RevisionTrendsResponse,
    SlopeBandSchema,
    TombstoneRevisionRequest,
    TombstoneRevisionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ────────────────────────────────────────────────────────────
# 1. detect-revision-of (read + compute, no writes)
# ────────────────────────────────────────────────────────────


@router.post(
    "/api/v1/projects/{project_id}/detect-revision-of",
    response_model=DetectRevisionOfResponse,
)
@limiter.limit(RATE_LIMIT_ANALYSIS)
def detect_revision_of_endpoint(
    request: Request,
    project_id: str,
    user: dict[str, Any] = Depends(require_auth),
) -> DetectRevisionOfResponse:
    """Return candidate parent project per the v1 heuristic.

    Heuristic returns the most recent SIBLING in the same program with a
    different ``data_date`` — see ``src.api.revision_detection`` for the
    full contract. Defensive: failures return the no-candidate shape
    rather than raising 500 (a heuristic crash on every call would block
    the upload→confirm UX).
    """
    store = get_store()
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    snapshot = detect_candidate_parent(store, user_id=user_id, project_id=project_id)
    return DetectRevisionOfResponse(**snapshot)


# ────────────────────────────────────────────────────────────
# 2. confirm-revision-of (append-only INSERT)
# ────────────────────────────────────────────────────────────


@router.post(
    "/api/v1/projects/{project_id}/confirm-revision-of",
    response_model=ConfirmRevisionOfResponse,
)
@limiter.limit(RATE_LIMIT_WRITE)
def confirm_revision_of_endpoint(
    request: Request,
    project_id: str,
    body: ConfirmRevisionOfRequest,
    user: dict[str, Any] = Depends(require_auth),
) -> ConfirmRevisionOfResponse:
    """Write a ``revision_history`` row anchoring the current upload as a
    new revision in the parent's program.

    Append-only: the migration 028 BEFORE INSERT trigger enforces the cap
    + the UNIQUE NULLS NOT DISTINCT constraint catches duplicate
    (project_id, revision_number, NULL) inserts under concurrency.
    Concurrent confirms on the same project_id race; the loser surfaces
    as 409 Conflict.

    ``program_id`` linkage NOT mutated here (it already happened at
    ``save_project`` upload time per Cycle 4 W1 / W2A backend-reviewer
    blocker #1 redefinition). The endpoint validates parent + current are
    in the SAME program before writing — a different program would
    indicate a stale heuristic suggestion or a multi-program user error.
    """
    store = get_store()
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    current = store.get_project_meta(project_id, user_id=user_id)
    if current is None:
        # Structured error detail per ADR / issue #86 (DA P3-5 from PR #83).
        # Frontend pattern-matches on `error_code` to auto-collapse on
        # missing-project class errors vs keep-visible on other 4xx.
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "current_not_found",
                "message": f"project {project_id} not found",
            },
        )
    parent = store.get_project_meta(body.parent_project_id, user_id=user_id)
    if parent is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "parent_not_found",
                "message": f"parent project {body.parent_project_id} not found",
            },
        )
    if not current.get("program_id") or current.get("program_id") != parent.get("program_id"):
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "cross_program",
                "message": (
                    "current and parent are not in the same program — auto-grouping at upload "
                    "should have placed them together; refresh and retry, or open a support ticket"
                ),
            },
        )

    # Compute content_hash from the stored XER bytes. Server-side computation
    # prevents client-supplied-hash injection (the client may echo a hash
    # via body.content_hash for tamper-evidence; we ignore it as input but
    # could compare against the recompute for warning telemetry — not in v1).
    xer_bytes = b""
    try:
        xer_bytes = store.get_xer_bytes(project_id) or b""
    except Exception as exc:  # noqa: BLE001
        logger.warning("confirm: get_xer_bytes failed for %s: %s", project_id, exc)
    if not xer_bytes:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "no_xer_bytes",
                "message": "cannot compute content_hash — XER bytes missing from storage",
            },
        )
    content_hash = compute_xer_content_hash(xer_bytes)
    if body.content_hash and body.content_hash != content_hash:
        logger.info(
            "confirm: client-supplied content_hash mismatch (informational; using server-computed)"
        )

    # Determine next revision_number (cross-project within program).
    # DA exit-council fix-up #P1-3: use MAX + 1 (NOT count_active + 1).
    # Tombstoned rows occupy revision_number space — count_active + 1 would
    # collide with the still-existing-but-active row above the tombstone gap,
    # producing 409 forever after any tombstone. MAX over ALL rows (active +
    # tombstoned) preserves the gap discipline.
    program_id = current["program_id"]
    next_revision_number = store.max_revision_number_in_program(program_id, user_id=user_id) + 1

    try:
        row = store.insert_revision_history(
            project_id=project_id,
            revision_number=next_revision_number,
            data_date=current.get("data_date"),
            content_hash=content_hash,
            user_id=user_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail={"error_code": "permission_denied", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        # Cap violation (12+ active rows) OR UNIQUE collision under concurrency.
        # The two cases share a 409 status; the message text disambiguates.
        # Cap-reached message starts with "revision cap reached" per the
        # store helper convention.
        message = str(exc)
        code: Literal["cap_reached", "unique_collision"] = (
            "cap_reached" if "cap" in message.lower() else "unique_collision"
        )
        raise HTTPException(
            status_code=409,
            detail={"error_code": code, "message": message},
        ) from exc

    return ConfirmRevisionOfResponse(
        revision_id=str(row["id"]),
        project_id=str(row["project_id"]),
        revision_number=int(row["revision_number"]),
        program_id=program_id,
        data_date=row.get("data_date"),
        content_hash=row["content_hash"],
    )


# ────────────────────────────────────────────────────────────
# 3. tombstone (soft-delete + audit_log)
# ────────────────────────────────────────────────────────────


@router.post(
    "/api/v1/revisions/{revision_id}/tombstone",
    response_model=TombstoneRevisionResponse,
)
@limiter.limit(RATE_LIMIT_WRITE)
def tombstone_revision_endpoint(
    request: Request,
    revision_id: str,
    body: TombstoneRevisionRequest,
    user: dict[str, Any] = Depends(require_auth),
) -> TombstoneRevisionResponse:
    """Soft-tombstone a revision_history row + write paired audit_log entry.

    Idempotent: re-tombstoning an already-tombstoned row returns the
    existing tombstoned_at without writing a new audit row (the original
    incident is the load-bearing audit record).

    The ``reason`` is stored on the revision_history row (capped at 500
    chars by the migration's CHECK) AND mirrored into the audit_log
    ``details`` JSONB. Both are needed: revision_history.tombstoned_reason
    is for the UI; audit_log is for forensic chain-of-custody.
    """
    store = get_store()
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    ip_address = (request.client.host if request.client else None) or request.headers.get(
        "x-forwarded-for"
    )
    user_agent = request.headers.get("user-agent")

    result = store.tombstone_revision(
        revision_id=revision_id,
        reason=body.reason,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"revision {revision_id} not found or not owned"
        )
    return TombstoneRevisionResponse(
        revision_id=str(result["revision_id"]),
        tombstoned_at=str(result["tombstoned_at"]),
        audit_log_id=(
            str(result["audit_log_id"]) if result.get("audit_log_id") is not None else None
        ),
    )


# ────────────────────────────────────────────────────────────
# 4. revision-trends (multi-rev S-curve overlay)
# ────────────────────────────────────────────────────────────


@router.get(
    "/api/v1/projects/{project_id}/revision-trends",
    response_model=RevisionTrendsResponse,
)
@limiter.limit(RATE_LIMIT_ANALYSIS)
def revision_trends_endpoint(
    request: Request,
    project_id: str,
    user: dict[str, Any] = Depends(require_auth),
) -> RevisionTrendsResponse:
    """Return the multi-revision S-curve overlay + change-points + slope band.

    Cycle 4 W3 PR-A per ADR-0022. Visualization-only: NO forecast curve
    in W3 (path-A pre-commitment per ADR-0022 W4 calibration gate).

    CPM × N revisions runs at request time — bounded by W1 cap=12 active
    revisions per project (migration 028 ``enforce_revision_cap``
    trigger). RATE_LIMIT_ANALYSIS (20/min) is sufficient at the cap;
    EXPENSIVE bucket is reserved for Monte Carlo / PDF / forensic loops.

    Caching deferred per backend-reviewer entry-council #8 — would
    require coupling with W2 confirm/tombstone writers for invalidation.

    Methodology citation surfaced in the response for forensic
    credibility (AACE RP 29R-03 §"Window analysis").
    """
    store = get_store()
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # 1. Load the current project's metadata + program_id.
    current = store.get_project_meta(project_id, user_id=user_id)
    if current is None:
        raise HTTPException(status_code=404, detail=f"project {project_id} not found")
    program_id = current.get("program_id")
    if not program_id:
        # Not in a program — single-revision view; return curve-only response.
        sched = store.get_project(project_id, user_id=user_id)
        if sched is None:
            raise HTTPException(status_code=404, detail="project schedule not available")
        analysis = _analyze_with_fallback(
            project_id=project_id,
            program_id=None,
            revisions=[(project_id, None, None, current.get("data_date"), sched)],
        )
        analysis.notes.insert(
            0,
            "project not assigned to a program (anonymous upload?) — single-revision view returned",
        )
        return _to_response(analysis)

    # 2. Load all sibling projects in the program (RLS-scoped).
    siblings = store.list_projects_in_program(program_id, user_id=user_id)
    # Map project_id → revision_history row (active only) for revision_number.
    rh_rows = store.list_revision_history_by_program(program_id, user_id=user_id)
    rh_by_project: dict[str, dict[str, Any]] = {
        r["project_id"]: r for r in rh_rows if r.get("tombstoned_at") is None
    }

    # 3. Build (project_id, rev_id, rev_num, data_date_iso, schedule) tuples,
    #    sorted ascending by data_date for the orchestrator. Track skipped
    #    siblings per issue #91 / DA P3-3 (silent skip masks "missing" vs
    #    "RLS-denied" cases — surface in notes for operator audit).
    revisions: list[tuple[str, str | None, int | None, str | None, Any]] = []
    skipped_pids: list[str] = []
    for s in siblings:
        pid = s["project_id"]
        sched = store.get_project(pid, user_id=user_id)
        if sched is None:
            skipped_pids.append(pid)
            continue
        rh = rh_by_project.get(pid)
        revisions.append(
            (
                pid,
                str(rh["id"]) if rh else None,
                int(rh["revision_number"]) if rh else None,
                s.get("data_date"),
                sched,
            )
        )
    revisions.sort(key=lambda t: t[3] or "")

    if not revisions:
        analysis = _analyze_with_fallback(
            project_id=project_id, program_id=program_id, revisions=[]
        )
        analysis.skipped_revisions = list(skipped_pids)
        if skipped_pids:
            analysis.notes.append(
                f"{len(skipped_pids)} sibling revision(s) skipped: schedule data not "
                f"available (project missing OR RLS denied) — see "
                f"`skipped_revisions` field for the project_ids"
            )
        return _to_response(analysis)

    analysis = _analyze_with_fallback(
        project_id=project_id, program_id=program_id, revisions=revisions
    )
    analysis.skipped_revisions = list(skipped_pids)
    if skipped_pids:
        analysis.notes.append(
            f"{len(skipped_pids)} sibling revision(s) skipped: schedule data not "
            f"available (project missing OR RLS denied) — see "
            f"`skipped_revisions` field for the project_ids"
        )
    return _to_response(analysis)


def _analyze_with_fallback(
    *,
    project_id: str,
    program_id: str | None,
    revisions: list[tuple[str, str | None, int | None, str | None, Any]],
) -> RevisionTrendsAnalysis:
    """Wrap ``analyze_revision_trends`` with narrow exception catch per issue
    #90 / DA P3-2 (DA exit-council P1 #7 narrowing on PR #104).

    NumPy data-edge cases (NaN, zero-variance shifts, near-singular OLS
    matrices, divide-by-zero) could raise from inside
    ``analyze_revision_trends``. Per ADR-0022 §"W3 — C-visualization": viz
    should ship value even when downstream computation fails (same principle
    as W4 path-A fallback). Returns a partial analysis with
    ``notes: ["analysis failed: <ExceptionClassName> ..."]`` rather than 500.

    **Narrow catch per DA exit-council P1 #7**: only data-edge exceptions
    are caught (``ValueError``, ``ArithmeticError``, ``FloatingPointError``,
    ``np.linalg.LinAlgError``). Programming bugs (``TypeError``,
    ``AttributeError``, ``KeyError``, ``MemoryError``, ``RecursionError``)
    propagate as 500 to surface in Sentry/CI rather than silently degrade
    to "analysis failed: TypeError" with no alert.

    Methodology field is ALSO cleared on the fallback path per DA exit-
    council P1 #5 — failed analyses should not surface the AACE 29R-03
    citation as if the analysis ran.
    """
    try:
        return analyze_revision_trends(
            project_id=project_id, program_id=program_id, revisions=revisions
        )
    except (
        ValueError,
        ArithmeticError,
        FloatingPointError,
        np.linalg.LinAlgError,
    ) as exc:
        fallback = RevisionTrendsAnalysis(project_id=project_id, program_id=program_id)
        # P1 #5 fix: clear methodology so failed-analysis response does NOT
        # carry the AACE citation as if the analysis ran.
        fallback.methodology = ""
        fallback.notes.append(
            f"analysis failed: {type(exc).__name__} — partial response per ADR-0022 "
            f"viz-ships-value principle (issue #90 / DA P3-2). Methodology citation "
            f"cleared (DA exit-council P1 #5 on PR #104). Server-side log retains "
            f"full exception."
        )
        # Log the full exception for operator triage (DA exit-council P3 #16).
        logger.warning(
            "revision_trends analysis failed; returning fallback. project_id=%s, "
            "program_id=%s, revisions_n=%d, exc=%s",
            project_id,
            program_id,
            len(revisions),
            exc,
            exc_info=True,
        )
        return fallback


def _to_response(analysis: Any) -> RevisionTrendsResponse:
    """Convert the dataclass-based RevisionTrendsAnalysis to Pydantic."""
    return RevisionTrendsResponse(
        project_id=analysis.project_id,
        program_id=analysis.program_id,
        curves=[
            RevisionCurveSchema(
                project_id=c.project_id,
                revision_id=c.revision_id,
                revision_number=c.revision_number,
                data_date=c.data_date,
                points=[
                    RevisionCurvePoint(
                        day_offset=p.day_offset,
                        planned_cumulative_pct=p.planned_cumulative_pct,
                        actual_cumulative_pct=p.actual_cumulative_pct,
                    )
                    for p in c.points
                ],
                is_executed=c.is_executed,
            )
            for c in analysis.curves
        ],
        change_points=[
            ChangePointMarkerSchema(
                revision_index=cp.revision_index,
                revision_id=cp.revision_id,
                delta_days=cp.delta_days,
                cusum_value=cp.cusum_value,
                direction=cp.direction,
                description=cp.description,
            )
            for cp in analysis.change_points
        ],
        slope_band=(
            SlopeBandSchema(
                slope_days_per_revision=analysis.slope_band.slope_days_per_revision,
                ci_lower=analysis.slope_band.ci_lower,
                ci_upper=analysis.slope_band.ci_upper,
                horizon_revisions=analysis.slope_band.horizon_revisions,
            )
            if analysis.slope_band
            else None
        ),
        methodology=analysis.methodology,
        notes=analysis.notes,
        skipped_revisions=list(getattr(analysis, "skipped_revisions", [])),
    )
