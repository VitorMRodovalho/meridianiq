# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Runtime observability router — SuperAdmin-gated diagnostic endpoint.

Exposes the on-demand snapshot returned by
``src.api.observability.get_runtime_snapshot`` so an operator can probe
the live process state during a leak investigation, an OOM post-mortem
follow-up, or routine health checks.

## Path namespace

The endpoint lives at ``/api/v1/superadmin/runtime`` — NOT under
``/api/v1/admin/*`` — because the existing admin router contains
user-self-service endpoints (API keys, GDPR data deletion, IPS
reconciliation) that are NOT SuperAdmin-gated. Conflating tiers under
the same prefix would tempt a future refactor to relax this gate.
The path itself is the load-bearing security signal, not just the
docstring.

## 5-tier role model (destination architecture)

MeridianIQ's auth model targets a 5-level hierarchy, top-down:

```
SuperAdmin                 (single — maintainer)
   └── Enterprise          (organization / company / GC firm)
          └── Program      (portfolio of projects)
                 └── Project    (single construction project)
                        └── Contract   (subcontract / scope-of-work)
```

Today the codebase is single-tenant Project-scoped with flat
``project_owners``; the Tier-model migration is a Cycle 4+ deliverable.
SuperAdmin is currently env-gated (``SUPERADMIN_USER_IDS`` /
``SUPERADMIN_EMAILS``) — the smallest committable surface that gates
this endpoint TODAY without prejudging the destination contract.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import require_superadmin
from ..deps import RATE_LIMIT_LIGHT, limiter
from ..observability import get_runtime_snapshot
from ..schemas import RuntimeSnapshot

router = APIRouter()


@router.get("/api/v1/superadmin/runtime", response_model=RuntimeSnapshot)
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

    Rate-limited under ``RATE_LIMIT_LIGHT`` (60/min) — sufficient for
    once-per-second polling during an active incident.  Diagnostic value
    falls off rapidly past 1Hz; if more aggressive sampling is ever
    required, prefer Sentry profiling over endpoint polling.

    Note on ``cpu_percent``: psutil's contract is that the FIRST call
    per process always returns 0.0 (it baselines off the previous call).
    Operators interpreting an active incident should call twice with a
    short delay; the second value is meaningful.
    """
    snapshot = get_runtime_snapshot()
    return RuntimeSnapshot(**snapshot)
