# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Lifecycle phase router — W3 of Cycle 1 v4.0 (ADR-0016).

Endpoints:

- ``GET  /api/v1/projects/{project_id}/lifecycle`` — summary (inference + override + effective)
- ``POST /api/v1/projects/{project_id}/lifecycle/override`` — write a manual override
- ``DELETE /api/v1/projects/{project_id}/lifecycle/override`` — revert to inferred (keeps history)
- ``GET  /api/v1/projects/{project_id}/lifecycle/overrides`` — paginated override history

Contract notes:

- Override before inference returns 409 (BR P1#7 per ADR-0016 council).
- Override on ``projects.status='pending'`` returns 409 — the inference
  may still land; let the user wait for the pending → ready flip.
- Revert flips ``projects.lifecycle_phase_locked`` back to false but does
  NOT delete override rows (append-only per ADR-0016 §3). The existing
  inference artifact remains the authoritative source post-revert —
  reverting restores the inference view without a recompute.
- DB writes go through the store abstraction; the store layer writes the
  paired ``audit_log`` row with ``action='lifecycle_override'`` per BR P1#8.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from src.analytics.lifecycle_phase import ENGINE_NAME as _LIFECYCLE_ENGINE_NAME
from src.analytics.lifecycle_phase import RULESET_VERSION as _LIFECYCLE_RULESET_VERSION
from src.analytics.lifecycle_types import LIFECYCLE_PHASES, confidence_band
from src.materializer.runtime import _ENGINE_VERSION as _MATERIALIZER_ENGINE_VERSION

from ..auth import optional_auth
from ..deps import get_store, limiter
from ..schemas import (
    LifecycleOverrideListResponse,
    LifecycleOverrideRequest,
    LifecycleOverrideSchema,
    LifecyclePhaseInferenceSchema,
    LifecyclePhaseSummary,
)

router = APIRouter()


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _inference_from_artifact(row: dict[str, Any]) -> LifecyclePhaseInferenceSchema:
    """Build the wire schema from a ``schedule_derived_artifacts`` row.

    Falls back gracefully when the payload shape drifts — missing keys
    map to ``'unknown'`` / 0.0 / empty rationale. Council P1 (BR P1-2):
    enforce the engine's ``phase='unknown' ⇒ confidence=0.0`` invariant
    on the wire too, so the API never contradicts the engine
    contract documented in ``lifecycle_types.LifecyclePhaseInference``.
    """
    payload = row.get("payload") or {}
    phase = payload.get("phase", "unknown")
    if phase not in LIFECYCLE_PHASES:
        phase = "unknown"
    raw_conf = payload.get("confidence", 0.0)
    try:
        confidence = float(raw_conf)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    if phase == "unknown":
        confidence = 0.0
    return LifecyclePhaseInferenceSchema(
        phase=phase,
        confidence=confidence,
        confidence_band=confidence_band(confidence),
        rationale=payload.get("rationale") or {},
        engine_version=row.get("engine_version", "") or "",
        ruleset_version=row.get("ruleset_version", "") or "",
        effective_at=_iso(row.get("effective_at")),
        computed_at=_iso(row.get("computed_at")),
    )


def _override_from_row(row: dict[str, Any]) -> LifecycleOverrideSchema:
    return LifecycleOverrideSchema(
        id=str(row.get("id", "")),
        project_id=str(row.get("project_id", "")),
        inferred_phase=row.get("inferred_phase"),
        override_phase=str(row.get("override_phase", "unknown")),
        override_reason=str(row.get("override_reason", "")),
        overridden_by=row.get("overridden_by"),
        overridden_at=_iso(row.get("overridden_at")),
        engine_version=str(row.get("engine_version", "")),
        ruleset_version=str(row.get("ruleset_version", "")),
    )


def _assert_project_access(store: Any, project_id: str, user_id: Optional[str]) -> None:
    """404 if the caller cannot see the project (owner-scope)."""
    schedule = store.get(project_id, user_id=user_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _build_summary(store: Any, project_id: str) -> LifecyclePhaseSummary:
    """Collapse inference + override + lock into one render-ready summary."""
    artifact = store.get_latest_derived_artifact(
        project_id=project_id,
        artifact_kind="lifecycle_phase_inference",
        current_engine_version=_MATERIALIZER_ENGINE_VERSION,
        current_ruleset_version=_LIFECYCLE_RULESET_VERSION,
    )
    inference: Optional[LifecyclePhaseInferenceSchema] = None
    if artifact is not None:
        inference = _inference_from_artifact(artifact)

    locked = bool(store.get_lifecycle_phase_lock(project_id))
    latest_override_row = store.get_latest_lifecycle_override(project_id)
    latest_override = _override_from_row(latest_override_row) if latest_override_row else None

    # Precedence rule — ADR-0016 §UX.
    # Council P1 (devils-advocate #5 + backend-reviewer P1-1): only
    # surface ``latest_override`` to the UI when it is currently
    # authoritative (locked=true). After a revert, the override row
    # stays in history but stops being "active" — exposing it on the
    # summary endpoint confuses the UI into rendering a stale override
    # alongside the fresh inference. The override history endpoint
    # (``GET /lifecycle/overrides``) remains the canonical surface for
    # post-revert history review.
    if locked:
        effective_phase = (
            latest_override.override_phase
            if latest_override is not None
            else (inference.phase if inference is not None else "unknown")
        )
        effective_confidence: Optional[float] = None
        source: Optional[str] = "manual" if latest_override is not None else None
        active_override = latest_override
    elif inference is not None:
        effective_phase = inference.phase
        effective_confidence = inference.confidence
        source = "inferred"
        active_override = None
    else:
        effective_phase = "unknown"
        effective_confidence = None
        source = None
        active_override = None

    return LifecyclePhaseSummary(
        project_id=project_id,
        locked=locked,
        inference=inference,
        latest_override=active_override,
        effective_phase=effective_phase,
        effective_confidence=effective_confidence,
        source=source,
    )


@router.get(
    "/api/v1/projects/{project_id}/lifecycle",
    response_model=LifecyclePhaseSummary,
)
@limiter.limit("60/minute")
def get_lifecycle_summary(
    request: Request,
    project_id: str,
    _user: object = Depends(optional_auth),
) -> LifecyclePhaseSummary:
    """Return the current lifecycle phase view for a project.

    Combines the latest ``lifecycle_phase_inference`` artifact (if any),
    the latest ``lifecycle_override_log`` row (if any), and the
    ``projects.lifecycle_phase_locked`` flag into one summary.

    Returns 404 if the project does not exist or the caller cannot see it.
    """
    store = get_store()
    user_id: Optional[str] = _user["id"] if isinstance(_user, dict) else None
    _assert_project_access(store, project_id, user_id)
    return _build_summary(store, project_id)


@router.post(
    "/api/v1/projects/{project_id}/lifecycle/override",
    response_model=LifecycleOverrideSchema,
    status_code=201,
)
@limiter.limit("20/minute")
def create_lifecycle_override(
    request: Request,
    project_id: str,
    body: LifecycleOverrideRequest,
    _user: object = Depends(optional_auth),
) -> LifecycleOverrideSchema:
    """Write a manual lifecycle phase override + flip the lock.

    Guards (per ADR-0016 §3 + BR P1#7):

    - 404 if the project is missing or the caller cannot see it.
    - 409 if the project is still materializing (``status='pending'``).
    - 409 if no inference artifact exists yet (override-before-inference
      is almost always user confusion, not a forensic gesture).
    - 422 (Pydantic) if the phase vocabulary or reason length violate
      the contract.

    On success the store writes the override row, flips
    ``projects.lifecycle_phase_locked=true``, and appends an
    ``audit_log`` row with ``action='lifecycle_override'``.
    """
    store = get_store()
    user_id: Optional[str] = _user["id"] if isinstance(_user, dict) else None
    _assert_project_access(store, project_id, user_id)

    if body.override_phase not in LIFECYCLE_PHASES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"invalid override_phase: {body.override_phase!r}; "
                f"must be one of {list(LIFECYCLE_PHASES)}"
            ),
        )

    status_getter = getattr(store, "get_project_status", None)
    if status_getter is not None:
        try:
            current_status = status_getter(project_id)
        except Exception:
            current_status = None
        if current_status == "pending":
            raise HTTPException(
                status_code=409,
                detail="Project is still materializing; wait for status='ready' before overriding.",
            )

    artifact = store.get_latest_derived_artifact(
        project_id=project_id,
        artifact_kind="lifecycle_phase_inference",
        current_engine_version=_MATERIALIZER_ENGINE_VERSION,
        current_ruleset_version=_LIFECYCLE_RULESET_VERSION,
    )
    if artifact is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "No inference artifact available yet. "
                "Wait for the materializer to emit a phase before overriding."
            ),
        )

    inferred_phase = (artifact.get("payload") or {}).get("phase")
    if inferred_phase is not None and inferred_phase not in LIFECYCLE_PHASES:
        inferred_phase = "unknown"

    # Council P1 (devils-advocate #3): the override row's
    # ``engine_version`` / ``ruleset_version`` columns pin which
    # algorithm version the user was reviewing at override time
    # (forensic disambiguation per ADR-0016 §3). If the artifact's
    # provenance is missing, do NOT silently forge the materializer's
    # current version into the override — that would lie about which
    # algorithm version the user disagreed with. Refuse the write so
    # the UI can prompt for a refresh.
    artifact_engine = artifact.get("engine_version")
    artifact_ruleset = artifact.get("ruleset_version")
    if not artifact_engine or not artifact_ruleset:
        raise HTTPException(
            status_code=409,
            detail=(
                "Inference engine or ruleset version is unavailable on "
                "the latest artifact. Refresh the project view and retry."
            ),
        )

    saved = store.save_lifecycle_override(
        project_id,
        override_phase=body.override_phase,
        override_reason=body.override_reason,
        inferred_phase=inferred_phase,
        overridden_by=user_id,
        engine_version=artifact_engine,
        ruleset_version=artifact_ruleset,
    )
    # Normalise overridden_at for the wire — SupabaseStore returns an ISO
    # string already; InMemoryStore returns a datetime object.
    if "overridden_at" not in saved or saved["overridden_at"] is None:
        saved["overridden_at"] = datetime.now(UTC).isoformat()
    return _override_from_row(saved)


@router.delete(
    "/api/v1/projects/{project_id}/lifecycle/override",
    status_code=204,
)
@limiter.limit("20/minute")
def revert_lifecycle_override(
    request: Request,
    project_id: str,
    _user: object = Depends(optional_auth),
) -> None:
    """Revert to the inferred phase (keeps override history).

    Flips ``projects.lifecycle_phase_locked`` back to false. The override
    rows are NOT deleted (append-only per ADR-0016 §3); the existing
    inference artifact resumes as the authoritative source. No
    re-materialization is triggered — the artifact is still valid for
    the current revision; the next upload will write a fresh inference.

    404 if the project is missing or the caller cannot see it.
    """
    store = get_store()
    user_id: Optional[str] = _user["id"] if isinstance(_user, dict) else None
    _assert_project_access(store, project_id, user_id)
    store.set_lifecycle_phase_lock(project_id, False)
    return None


@router.get(
    "/api/v1/projects/{project_id}/lifecycle/overrides",
    response_model=LifecycleOverrideListResponse,
)
@limiter.limit("60/minute")
def list_lifecycle_overrides(
    request: Request,
    project_id: str,
    limit: int = 50,
    _user: object = Depends(optional_auth),
) -> LifecycleOverrideListResponse:
    """Return the override history for a project (newest first)."""
    store = get_store()
    user_id: Optional[str] = _user["id"] if isinstance(_user, dict) else None
    _assert_project_access(store, project_id, user_id)
    limit = max(1, min(200, limit))
    rows = store.list_lifecycle_overrides(project_id, limit=limit)
    return LifecycleOverrideListResponse(overrides=[_override_from_row(r) for r in rows])


# Re-export for consistency with the rest of the codebase. Keeps
# ``from src.api.routers.lifecycle import ENGINE_NAME`` working even if
# the engine module is renamed.
ENGINE_NAME = _LIFECYCLE_ENGINE_NAME
