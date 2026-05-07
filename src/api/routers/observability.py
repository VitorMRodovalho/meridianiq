# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Runtime observability router — SuperAdmin-gated diagnostic endpoint.

Exposes the on-demand snapshot returned by
``src.api.observability.get_runtime_snapshot`` so an operator can probe
the live process state during a leak investigation, an OOM post-mortem
follow-up, or routine health checks.

The endpoint is intentionally separate from ``src/api/routers/admin.py``
(which is user-self-service: API keys, GDPR deletion, IPS reconciliation)
because this surface is gated by a **different role tier** — SuperAdmin
only — and conflating the two would tempt a future refactor to relax
the gate.

See ``project_role_hierarchy.md`` (memory) for the 5-tier model
(SuperAdmin → Enterprise → Program → Project → Contract) this endpoint
participates in. Today the model is env-gated; a future Tier-model
migration will replace the env primitive with a DB-backed contract.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import require_superadmin
from ..deps import RATE_LIMIT_LIGHT, limiter
from ..observability import get_runtime_snapshot
from ..schemas import RuntimeSnapshot

router = APIRouter()


@router.get("/api/v1/admin/runtime", response_model=RuntimeSnapshot)
@limiter.limit(RATE_LIMIT_LIGHT)
def runtime_snapshot_endpoint(
    request: Request,
    _user: dict[str, Any] = Depends(require_superadmin),
) -> RuntimeSnapshot:
    """Return a snapshot of process runtime state (SuperAdmin only).

    Use cases:
    - Live probe during a leak investigation
    - OOM post-mortem context (curve up to the kill is on Sentry / logs)
    - Routine ops check before an operator action (e.g., re-mat job)

    Rate-limited under ``RATE_LIMIT_LIGHT`` to match other read endpoints
    — diagnostic value falls off rapidly past once-per-second polling.
    """
    snapshot = get_runtime_snapshot()
    return RuntimeSnapshot(**snapshot)
