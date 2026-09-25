# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tenant access layer: who is calling, and which projects they may reach.

Every route that selects tenant data by id resolves it through an
:class:`AccessContext`. The context owns the single access rule, so a
route cannot read a project without first stating whose request it is.

Rule (see ADR-0030):

* the owner of a project may reach it;
* the ``system`` principal (materializer, backfill) may reach any project;
* a project with no recorded owner is reachable only by the anonymous
  development principal, which exists only outside production and only
  with the in-memory store;
* everyone else gets a 404, identical to a project that does not exist.

Sharing through ``project_shares`` / org membership is not honoured yet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from fastapi import Depends, HTTPException, status

from src.database.config import settings

from .auth import optional_auth
from .deps import get_store

logger = logging.getLogger(__name__)

PrincipalKind = Literal["user", "api_key", "dev", "system"]

#: Identity of the anonymous caller in development and tests.
DEV_USER_ID = "dev-anonymous"


@dataclass(frozen=True)
class Principal:
    """The identity a request (or a background job) acts for."""

    user_id: str
    kind: PrincipalKind


#: Trusted background work that is not tied to one tenant. Obtain a context
#: for it only through :meth:`AccessContext.system`, which records why.
SYSTEM = Principal("system", "system")


class OwnerLookup(Protocol):
    """The one store capability the access layer needs."""

    def get_project_owner(self, project_id: str) -> tuple[bool, str | None]: ...


def _is_in_memory(store: Any) -> bool:
    from src.database.store import InMemoryStore

    return isinstance(store, InMemoryStore)


def principal_from_user(user: dict[str, Any] | None, store: Any) -> Principal:
    """Map the authenticated user (or its absence) to a :class:`Principal`.

    ``None`` becomes the development principal only when that cannot reach
    real tenant data: never in production, never with a Supabase store.
    """
    if user is None:
        if settings.ENVIRONMENT == "production" or not _is_in_memory(store):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return Principal(DEV_USER_ID, "dev")
    user_id = str(user.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid identity")
    kind: PrincipalKind = "api_key" if user.get("role") == "api_key" else "user"
    return Principal(user_id, kind)


_NOT_FOUND = "Project not found"


@dataclass(frozen=True)
class AccessContext:
    """Per-request access decisions, memoised so each project is looked up once.

    Frozen, and the memo is not an init field: a copy made with
    ``dataclasses.replace`` for another principal starts with an empty memo,
    so a grant can never carry over from one principal to another.
    """

    principal: Principal
    store: OwnerLookup
    _grants: dict[str, bool] = field(default_factory=dict, init=False, repr=False, compare=False)

    @classmethod
    def system(cls, store: OwnerLookup, *, reason: str) -> AccessContext:
        """Context for trusted background work (materializer, backfill).

        ``reason`` is required and logged, so every use of the all-access
        principal leaves a trail.
        """
        if not reason:
            raise ValueError("A system access context needs a reason")
        logger.info("system access context: %s", reason)
        return cls(SYSTEM, store)

    def can_access_project(self, project_id: str | None) -> bool:
        """Return True if the principal may reach ``project_id``."""
        if not project_id:
            return False
        cached = self._grants.get(project_id)
        if cached is not None:
            return cached
        exists, owner = self.store.get_project_owner(project_id)
        granted = exists and self.allows_owner(owner)
        self._grants[project_id] = granted
        return granted

    def allows_owner(self, owner: str | None) -> bool:
        """The access rule itself, for any owned resource (not only projects)."""
        if self.principal.kind == "system":
            return True
        if owner is None:
            return self.principal.kind == "dev"
        return owner == self.principal.user_id

    def project(self, project_id: str | None) -> str:
        """Return ``project_id`` if reachable, else raise 404 (same as not found)."""
        if not project_id or not self.can_access_project(project_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
        return project_id

    def maybe_project(self, project_id: str | None) -> str | None:
        """Like :meth:`project` for optional ids: empty stays ``None``, given-but-hidden is 404."""
        if not project_id:
            return None
        return self.project(project_id)

    def projects(self, project_ids: list[str]) -> list[str]:
        """Authorize every id or none: one hidden id makes the whole request a 404."""
        return [self.project(pid) for pid in project_ids]


def get_principal(
    user: dict[str, Any] | None = Depends(optional_auth),
    store: Any = Depends(get_store),
) -> Principal:
    """FastAPI dependency: the principal of the current request (never ``None``)."""
    return principal_from_user(user, store)


def get_access(
    principal: Principal = Depends(get_principal),
    store: Any = Depends(get_store),
) -> AccessContext:
    """FastAPI dependency: a fresh :class:`AccessContext` for the current request."""
    return AccessContext(principal, store)


def owned_project(project_id: str, ctx: AccessContext = Depends(get_access)) -> str:
    """FastAPI dependency for a ``project_id`` path/query parameter the caller must reach.

    Only a cheap ownership lookup runs here, and it runs before the slowapi
    decorator check (FastAPI resolves dependencies first), so a 404 from it
    is not counted against a route's limit. Parsing the schedule stays in the
    handler body, after the limit.

    WebSocket routes cannot use this dependency (``optional_auth`` needs an
    HTTP request); they build ``AccessContext`` from their own token path.
    """
    return ctx.project(project_id)
