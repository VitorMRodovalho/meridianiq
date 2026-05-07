# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Revision detection + soft-tombstone router (Cycle 4 W2 PR-A — ADR-0022).

Three endpoints:

- ``POST /api/v1/projects/{id}/detect-revision-of`` — heuristic, no writes
- ``POST /api/v1/projects/{id}/confirm-revision-of`` — append-only INSERT
- ``POST /api/v1/revisions/{id}/tombstone`` — soft-delete + audit_log

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
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import require_auth
from ..deps import RATE_LIMIT_ANALYSIS, RATE_LIMIT_WRITE, get_store, limiter
from ..revision_detection import compute_xer_content_hash, detect_candidate_parent
from ..schemas import (
    ConfirmRevisionOfRequest,
    ConfirmRevisionOfResponse,
    DetectRevisionOfResponse,
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
        raise HTTPException(status_code=404, detail=f"project {project_id} not found")
    parent = store.get_project_meta(body.parent_project_id, user_id=user_id)
    if parent is None:
        raise HTTPException(
            status_code=404, detail=f"parent project {body.parent_project_id} not found"
        )
    if not current.get("program_id") or current.get("program_id") != parent.get("program_id"):
        raise HTTPException(
            status_code=409,
            detail=(
                "current and parent are not in the same program — auto-grouping at upload "
                "should have placed them together; refresh and retry, or open a support ticket"
            ),
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
            detail="cannot compute content_hash — XER bytes missing from storage",
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
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        # Cap violation (12+ active rows) OR UNIQUE collision under concurrency.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

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
