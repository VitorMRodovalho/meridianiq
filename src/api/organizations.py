# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Organization, membership, and sharing API endpoints.

Implements the hybrid multi-org model:
- Each company (Owner, PM, CM, GC) has its own organization
- Projects can be shared across organizations with granular permissions
- Audit trail logs all significant actions

Access rules (ADR-0030):

- Organization routes act only for ACCEPTED members. A caller who is not a
  member, whose invitation is still pending, or who names an organization
  that does not exist gets the same ``404``. An accepted member whose role
  is too low for the action gets ``403``: the organization is visible to
  them, the action is not.
- An invitation records a PENDING membership (``accepted_at`` NULL) that
  grants nothing until the invited user accepts it. The invite answer, and
  its audit entry, are the same whether or not the address belongs to an
  account and whether or not it is already a member, and pending rows are
  never listed to the organization, so neither reveals which addresses
  have accounts. The role is recorded as granted only when it is accepted.
- An invitation can be accepted for ``INVITATION_TTL`` after it was last
  issued, and only while the member who issued it is still an accepted
  owner or admin of the organization. A manager can revoke it by address;
  removing a member also withdraws the invitations that member issued.
- Project shares and value milestones authorize the project through the
  access context before anything else: only the project owner reaches them.
  Recording a share grants no read access (ADR-0030 §4).
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .access import AccessContext, Principal, get_access, get_principal


def _client_ip(request: Request | None) -> str | None:
    """Return the client address recorded in the audit trail.

    Only values set by infrastructure the app trusts are read:

    1. ``Fly-Client-IP``. Fly.io's edge sets it to the address it accepted
       the connection from, replacing any value the client sent.
    2. Otherwise the RIGHTMOST ``X-Forwarded-For`` entry, the one appended
       by the proxy directly in front of the app. Every entry to its left
       came from the client and can say anything, so the leftmost entry
       would let a caller write an arbitrary address into the audit log.
    3. Otherwise the socket peer, ``request.client.host``.

    ``X-Real-IP`` is not read: no proxy in this deployment sets it, so it
    would carry only what the client chose to send. Returns ``None`` when
    there is no request or no client (synthesised test requests).
    """
    if request is None:
        return None
    fly_ip = (request.headers.get("fly-client-ip") or "").strip()
    if fly_ip:
        return fly_ip
    xff = request.headers.get("x-forwarded-for") or ""
    hops = [hop.strip() for hop in xff.split(",") if hop.strip()]
    if hops:
        return hops[-1]
    return request.client.host if request.client else None


def _user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    ua = request.headers.get("user-agent") or request.headers.get("User-Agent")
    return ua if ua else None


router = APIRouter(prefix="/api/v1", tags=["organizations"])


# ── Schemas ─────────────────────────────────────────────

#: Roles a membership can hold.
OrgRole = Literal["owner", "admin", "member", "viewer"]
#: Roles an invitation may grant. Ownership is never granted by invitation.
InviteRole = Literal["admin", "member", "viewer"]
#: Permissions a project share may record.
SharePermission = Literal["viewer", "editor", "admin"]

MEMBER_ROLES: tuple[OrgRole, ...] = ("owner", "admin", "member", "viewer")
MANAGER_ROLES: tuple[OrgRole, ...] = ("owner", "admin")

#: How long an invitation can be accepted after it was last issued.
INVITATION_TTL = timedelta(days=14)

_EMAIL_PATTERN = r"^\s*[^@\s]+@[^@\s]+\s*$"


class CreateOrgRequest(BaseModel):
    name: str
    org_type: str = "general"
    description: str = ""


class InviteMemberRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=_EMAIL_PATTERN)
    role: InviteRole = "member"


class RevokeInvitationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=_EMAIL_PATTERN)


class ShareProjectRequest(BaseModel):
    project_id: str
    shared_with_org_id: str
    permission: SharePermission = "viewer"


class ShareProgramRequest(BaseModel):
    program_id: str
    shared_with_org_id: str
    permission: str = "viewer"


# ── Helper ──────────────────────────────────────────────

_ORG_NOT_FOUND = "Organization not found"
_INVITATION_NOT_FOUND = "Invitation not found"
_MILESTONE_NOT_FOUND = "Value milestone not found"


def _get_supabase() -> Any:
    """Get Supabase client (service role for admin operations)."""
    from src.database.client import get_supabase_client

    return get_supabase_client()


def _caller(principal: Principal = Depends(get_principal)) -> Principal:
    """The authenticated caller. Organizations have no anonymous or system actor."""
    if principal.kind not in ("user", "api_key"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal


def _canonical_uuid(value: str | None) -> str | None:
    """Return ``value`` as a canonical UUID, or ``None`` if it cannot name a row.

    Organization, membership and milestone ids are UUIDs. Anything else is
    answered like a missing row, without a query (Postgres would raise 22P02).
    """
    try:
        canonical = str(uuid.UUID(str(value)))
    except ValueError:
        return None
    return canonical if canonical == str(value).lower() else None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _get_user_orgs(user_id: str) -> list[dict[str, Any]]:
    """Get all organizations the user is an accepted member of."""
    client = _get_supabase()
    result = (
        client.table("memberships")
        .select("org_id, role, organizations(id, name, slug, org_type)")
        .eq("user_id", user_id)
        .not_.is_("accepted_at", "null")
        .execute()
    )
    return list(result.data or [])


def _require_member(
    client: Any, user_id: str, org_id: str, roles: tuple[OrgRole, ...]
) -> tuple[str, str]:
    """Return ``(canonical org id, caller's role)``, or refuse.

    Not an accepted member (never invited, invitation still pending, or no
    such organization): ``404``, the same answer in all three cases. An
    accepted member without one of ``roles``: ``403``.
    """
    oid = _canonical_uuid(org_id)
    rows: list[dict[str, Any]] = []
    if oid is not None:
        result = (
            client.table("memberships")
            .select("role")
            .eq("org_id", oid)
            .eq("user_id", user_id)
            .not_.is_("accepted_at", "null")
            .execute()
        )
        rows = list(result.data or [])
    if not rows:
        raise HTTPException(status_code=404, detail=_ORG_NOT_FOUND)
    role = str(rows[0].get("role") or "")
    if role not in roles:
        raise HTTPException(
            status_code=403,
            detail=f"Requires role {list(roles)}, you have {role}",
        )
    return str(oid), role


def _is_manager(client: Any, org_id: str, user_id: Any) -> bool:
    """Whether ``user_id`` is currently an accepted owner or admin of ``org_id``."""
    if not user_id:
        return False
    result = (
        client.table("memberships")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", str(user_id))
        .not_.is_("accepted_at", "null")
        .execute()
    )
    rows = result.data or []
    return bool(rows) and rows[0].get("role") in MANAGER_ROLES


def _invitation_cutoff() -> str:
    """Invitations issued before this instant can no longer be accepted."""
    return (datetime.now(UTC) - INVITATION_TTL).isoformat()


def _open_invitations(client: Any, user_id: str, org_id: str | None = None) -> list[dict[str, Any]]:
    """The caller's own invitations that can still be accepted.

    Pending, issued within ``INVITATION_TTL``, and issued by someone who is
    still an accepted owner or admin of the organization. An invitation
    with no recorded issuer is not open.
    """
    query = (
        client.table("memberships")
        .select("org_id, role, invited_by, created_at, organizations(id, name)")
        .eq("user_id", user_id)
        .is_("accepted_at", "null")
        .gte("created_at", _invitation_cutoff())
    )
    if org_id is not None:
        query = query.eq("org_id", org_id)
    rows = list(query.execute().data or [])
    return [r for r in rows if _is_manager(client, str(r["org_id"]), r.get("invited_by"))]


def _user_id_for_email(client: Any, email: str) -> str | None:
    result = client.table("user_profiles").select("id").eq("email", email).execute()
    rows = result.data or []
    return str(rows[0]["id"]) if rows else None


def _project_org_id(client: Any, project_id: str) -> str | None:
    """The organization an (already authorized) project belongs to, if any."""
    result = client.table("projects").select("org_id").eq("id", project_id).execute()
    rows = result.data or []
    org_id = rows[0].get("org_id") if rows else None
    return str(org_id) if org_id else None


def _audit(
    org_id: str | None,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Write an audit log entry.

    When ``request`` is supplied, the originating client IP (see
    :func:`_client_ip` for which headers are trusted) and User-Agent are
    captured on the row. Required for litigation-grade traceability per
    the ``audit_log`` schema in migration 007.
    """
    client = _get_supabase()
    client.table("audit_log").insert(
        {
            "org_id": org_id,
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details or {},
            "ip_address": _client_ip(request),
            "user_agent": _user_agent(request),
        }
    ).execute()


# ── Organization CRUD ───────────────────────────────────


@router.get("/organizations")
def list_organizations(caller: Principal = Depends(_caller)) -> dict[str, Any]:
    """List organizations the current user is an accepted member of."""
    memberships = _get_user_orgs(caller.user_id)
    orgs = []
    for m in memberships:
        org = m.get("organizations", {})
        if org:
            orgs.append(
                {
                    "id": org["id"],
                    "name": org["name"],
                    "slug": org["slug"],
                    "org_type": org["org_type"],
                    "role": m["role"],
                }
            )
    return {"organizations": orgs}


@router.post("/organizations")
def create_organization(
    req: CreateOrgRequest,
    request: Request,
    caller: Principal = Depends(_caller),
) -> dict[str, Any]:
    """Create a new organization and add the creator as owner."""
    client = _get_supabase()

    slug = re.sub(r"[^a-zA-Z0-9]", "-", req.name.lower()).strip("-")
    slug = f"{slug}-{caller.user_id[:8]}"

    # Create org
    org_result = (
        client.table("organizations")
        .insert(
            {
                "name": req.name,
                "slug": slug,
                "org_type": req.org_type,
                "description": req.description,
                "created_by": caller.user_id,
            }
        )
        .execute()
    )

    if not org_result.data:
        raise HTTPException(status_code=500, detail="Failed to create organization")

    org = org_result.data[0]

    # Add creator as owner
    client.table("memberships").insert(
        {
            "org_id": org["id"],
            "user_id": caller.user_id,
            "role": "owner",
            "accepted_at": "now()",
        }
    ).execute()

    _audit(
        org["id"],
        caller.user_id,
        "create",
        "organization",
        org["id"],
        {"name": req.name},
        request=request,
    )

    return {"organization": org}


@router.get("/organizations/{org_id}")
def get_organization(org_id: str, caller: Principal = Depends(_caller)) -> dict[str, Any]:
    """Get organization details and its accepted members (members only)."""
    client = _get_supabase()
    org_id, _role = _require_member(client, caller.user_id, org_id, MEMBER_ROLES)

    org_result = client.table("organizations").select("*").eq("id", org_id).execute()
    if not org_result.data:
        raise HTTPException(status_code=404, detail=_ORG_NOT_FOUND)

    # Pending invitations are not listed: a pending row would tell the
    # inviter that the address has an account before its owner said yes.
    members_result = (
        client.table("memberships")
        .select("user_id, role, accepted_at, user_profiles(email, full_name, avatar_url)")
        .eq("org_id", org_id)
        .not_.is_("accepted_at", "null")
        .execute()
    )

    return {
        "organization": org_result.data[0],
        "members": members_result.data or [],
    }


# ── Membership Management ──────────────────────────────


@router.post("/organizations/{org_id}/invite")
def invite_member(
    org_id: str,
    req: InviteMemberRequest,
    request: Request,
    caller: Principal = Depends(_caller),
) -> dict[str, Any]:
    """Invite a user to the organization by email (owner/admin).

    The invitation is recorded as pending and grants nothing until the
    invited user accepts it (``POST /organizations/{org_id}/accept``).
    Inviting someone who already has a pending invitation re-issues it:
    the latest role and issuer replace the earlier ones and the acceptance
    window starts again. Inviting an accepted member changes nothing.

    The answer and the ``invite_requested`` audit entry echo the REQUESTED
    role and are identical in every case (no account, pending, member), so
    neither tells the caller which case it was. A role is recorded as
    granted only by the ``accept_invite`` entry.
    """
    client = _get_supabase()
    org_id, _role = _require_member(client, caller.user_id, org_id, MANAGER_ROLES)
    email = req.email.strip().lower()

    target_user_id = _user_id_for_email(client, email)
    if target_user_id is not None:
        existing = (
            client.table("memberships")
            .select("accepted_at")
            .eq("org_id", org_id)
            .eq("user_id", target_user_id)
            .execute()
        )
        rows = existing.data or []
        if not rows:
            # accepted_at stays NULL: pending until the invited user accepts.
            client.table("memberships").insert(
                {
                    "org_id": org_id,
                    "user_id": target_user_id,
                    "role": req.role,
                    "invited_by": caller.user_id,
                }
            ).execute()
        elif rows[0].get("accepted_at") is None:
            # For a pending row, created_at is when the invitation was last issued.
            (
                client.table("memberships")
                .update({"role": req.role, "invited_by": caller.user_id, "created_at": _now()})
                .eq("org_id", org_id)
                .eq("user_id", target_user_id)
                .is_("accepted_at", "null")
                .execute()
            )

    _audit(
        org_id,
        caller.user_id,
        "invite_requested",
        "membership",
        None,
        {"email": email, "requested_role": req.role},
        request=request,
    )

    return {"status": "requested", "email": email, "role": req.role}


@router.post("/organizations/{org_id}/invitations/revoke")
def revoke_invitation(
    org_id: str,
    req: RevokeInvitationRequest,
    request: Request,
    caller: Principal = Depends(_caller),
) -> dict[str, Any]:
    """Withdraw the pending invitation of an address (owner/admin).

    Accepted members are not touched (remove them with
    ``DELETE /organizations/{org_id}/members/{user_id}``). The answer and
    the audit entry are the same whether or not there was an invitation.
    """
    client = _get_supabase()
    org_id, _role = _require_member(client, caller.user_id, org_id, MANAGER_ROLES)
    email = req.email.strip().lower()

    target_user_id = _user_id_for_email(client, email)
    if target_user_id is not None:
        (
            client.table("memberships")
            .delete()
            .eq("org_id", org_id)
            .eq("user_id", target_user_id)
            .is_("accepted_at", "null")
            .execute()
        )

    _audit(
        org_id,
        caller.user_id,
        "invite_revoked",
        "membership",
        None,
        {"email": email},
        request=request,
    )
    return {"status": "revoked", "email": email}


@router.get("/invitations")
def list_invitations(caller: Principal = Depends(_caller)) -> dict[str, Any]:
    """The calling user's own invitations that can still be accepted."""
    client = _get_supabase()
    invitations = []
    for row in _open_invitations(client, caller.user_id):
        org = row.get("organizations") or {}
        invitations.append(
            {
                "org_id": str(row["org_id"]),
                "org_name": org.get("name"),
                "role": row.get("role"),
                "invited_at": row.get("created_at"),
            }
        )
    return {"invitations": invitations}


@router.post("/organizations/{org_id}/accept")
def accept_invitation(
    org_id: str,
    request: Request,
    caller: Principal = Depends(_caller),
) -> dict[str, Any]:
    """Accept the calling user's own open invitation to ``org_id``.

    Only the caller's own pending row changes, and only while it is open
    (see :func:`_open_invitations`). No open invitation for the caller
    (never invited, expired, issuer no longer a manager, already a member,
    or no such organization) answers ``404``, the same in every case.
    """
    oid = _canonical_uuid(org_id)
    rows: list[dict[str, Any]] = []
    if oid is not None:
        client = _get_supabase()
        invitations = _open_invitations(client, caller.user_id, oid)
        if invitations:
            invitation = invitations[0]
            # Compare-and-set: a re-issue between the check and this write
            # (other role or issuer) leaves the row pending.
            result = (
                client.table("memberships")
                .update({"accepted_at": _now()})
                .eq("org_id", oid)
                .eq("user_id", caller.user_id)
                .is_("accepted_at", "null")
                .eq("role", invitation["role"])
                .eq("invited_by", str(invitation["invited_by"]))
                .gte("created_at", _invitation_cutoff())
                .execute()
            )
            rows = list(result.data or [])
    if oid is None or not rows:
        raise HTTPException(status_code=404, detail=_INVITATION_NOT_FOUND)

    role = rows[0].get("role")
    _audit(
        oid,
        caller.user_id,
        "accept_invite",
        "membership",
        caller.user_id,
        {"role": role, "invited_by": rows[0].get("invited_by")},
        request=request,
    )
    return {"status": "accepted", "org_id": oid, "role": role}


@router.delete("/organizations/{org_id}/members/{member_user_id}")
def remove_member(
    org_id: str,
    member_user_id: str,
    request: Request,
    caller: Principal = Depends(_caller),
) -> dict[str, Any]:
    """Remove a member, or revoke a pending invitation (owner/admin).

    Only an owner may remove an owner.
    """
    client = _get_supabase()
    org_id, caller_role = _require_member(client, caller.user_id, org_id, MANAGER_ROLES)

    target_user_id = _canonical_uuid(member_user_id)
    if target_user_id is None:
        return {"status": "removed"}

    target = (
        client.table("memberships")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", target_user_id)
        .execute()
    )
    target_rows = target.data or []
    if target_rows and target_rows[0].get("role") == "owner" and caller_role != "owner":
        raise HTTPException(status_code=403, detail="Only an owner can remove an owner")

    client.table("memberships").delete().eq("org_id", org_id).eq(
        "user_id", target_user_id
    ).execute()
    # The invitations this member issued in the org are withdrawn with them.
    (
        client.table("memberships")
        .delete()
        .eq("org_id", org_id)
        .eq("invited_by", target_user_id)
        .is_("accepted_at", "null")
        .execute()
    )

    _audit(
        org_id,
        caller.user_id,
        "remove_member",
        "membership",
        target_user_id,
        request=request,
    )

    return {"status": "removed"}


# ── Cross-Org Sharing ──────────────────────────────────


@router.post("/shares/project")
def share_project(
    req: ShareProjectRequest,
    request: Request,
    caller: Principal = Depends(_caller),
    ctx: AccessContext = Depends(get_access),
) -> dict[str, Any]:
    """Share a project with another organization (project owner only).

    Recording a share grants no read access yet (ADR-0030 §4).
    """
    project_id = ctx.project(req.project_id)
    client = _get_supabase()

    target_org = _canonical_uuid(req.shared_with_org_id)
    target_rows: list[dict[str, Any]] = []
    if target_org is not None:
        found = client.table("organizations").select("id").eq("id", target_org).execute()
        target_rows = list(found.data or [])
    if target_org is None or not target_rows:
        raise HTTPException(status_code=404, detail=_ORG_NOT_FOUND)

    project_org_id = _project_org_id(client, project_id)

    # Create share
    client.table("project_shares").upsert(
        {
            "project_id": project_id,
            "shared_with_org": target_org,
            "permission": req.permission,
            "shared_by": caller.user_id,
        }
    ).execute()

    _audit(
        project_org_id,
        caller.user_id,
        "share",
        "project",
        project_id,
        {
            "shared_with_org": target_org,
            "permission": req.permission,
        },
        request=request,
    )

    return {"status": "shared", "permission": req.permission}


@router.get("/shares/project/{project_id}")
def get_project_shares(
    project_id: str,
    caller: Principal = Depends(_caller),
    ctx: AccessContext = Depends(get_access),
) -> dict[str, Any]:
    """List all organizations a project is shared with (project owner only)."""
    pid = ctx.project(project_id)
    client = _get_supabase()
    result = (
        client.table("project_shares")
        .select("*, organizations(id, name, slug, org_type)")
        .eq("project_id", pid)
        .execute()
    )

    return {"shares": result.data or []}


# ── Audit Trail ────────────────────────────────────────


@router.get("/organizations/{org_id}/audit")
def get_audit_log(
    org_id: str,
    limit: int = 50,
    offset: int = 0,
    caller: Principal = Depends(_caller),
) -> dict[str, Any]:
    """Get audit log for an organization. Required for litigation traceability."""
    client = _get_supabase()
    org_id, _role = _require_member(client, caller.user_id, org_id, MANAGER_ROLES)

    result = (
        client.table("audit_log")
        .select("*, user_profiles(email, full_name)")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return {"entries": result.data or [], "limit": limit, "offset": offset}


# ── Value Milestones ───────────────────────────────────


class ValueMilestoneRequest(BaseModel):
    project_id: str
    task_code: str
    task_name: str = ""
    milestone_type: str = "payment"
    commercial_value: float = 0.0
    currency: str = "USD"
    payment_trigger: str = ""
    contract_ref: str = ""
    notes: str = ""
    baseline_date: str | None = None
    forecast_date: str | None = None


def _authorized_milestone(client: Any, ctx: AccessContext, milestone_id: str) -> tuple[str, str]:
    """Return ``(milestone_id, project_id)`` for a milestone the caller may reach.

    A milestone that does not exist and one in a project the caller may not
    reach get the same ``404``.
    """
    mid = _canonical_uuid(milestone_id)
    if mid is not None:
        result = client.table("value_milestones").select("id, project_id").eq("id", mid).execute()
        rows = result.data or []
        if rows:
            project_id = str(rows[0].get("project_id") or "")
            if ctx.can_access_project(project_id):
                return mid, project_id
    raise HTTPException(status_code=404, detail=_MILESTONE_NOT_FOUND)


@router.get("/projects/{project_id}/value-milestones")
def list_value_milestones(
    project_id: str,
    caller: Principal = Depends(_caller),
    ctx: AccessContext = Depends(get_access),
) -> dict[str, Any]:
    """List all value milestones for a project."""
    pid = ctx.project(project_id)
    client = _get_supabase()
    result = (
        client.table("value_milestones")
        .select("*")
        .eq("project_id", pid)
        .order("created_at")
        .execute()
    )
    return {"milestones": result.data or []}


@router.post("/projects/{project_id}/value-milestones")
def create_value_milestone(
    project_id: str,
    req: ValueMilestoneRequest,
    request: Request,
    caller: Principal = Depends(_caller),
    ctx: AccessContext = Depends(get_access),
) -> dict[str, Any]:
    """Create a value milestone linking a schedule milestone to commercial value."""
    pid = ctx.project(project_id)
    # The body names a project too: authorize it like any other id, then
    # require that it is the one in the path.
    if ctx.project(req.project_id) != pid:
        raise HTTPException(status_code=422, detail="project_id in the body must match the path")

    client = _get_supabase()
    org_id = _project_org_id(client, pid)

    data: dict[str, Any] = {
        "project_id": pid,
        "org_id": org_id,
        "task_code": req.task_code,
        "task_name": req.task_name,
        "milestone_type": req.milestone_type,
        "commercial_value": req.commercial_value,
        "currency": req.currency,
        "payment_trigger": req.payment_trigger,
        "contract_ref": req.contract_ref,
        "notes": req.notes,
        "created_by": caller.user_id,
    }
    if req.baseline_date:
        data["baseline_date"] = req.baseline_date
    if req.forecast_date:
        data["forecast_date"] = req.forecast_date

    result = client.table("value_milestones").insert(data).execute()

    if org_id:
        _audit(
            org_id,
            caller.user_id,
            "create",
            "value_milestone",
            pid,
            {
                "task_code": req.task_code,
                "value": req.commercial_value,
            },
            request=request,
        )

    return {"milestone": result.data[0] if result.data else {}}


@router.put("/value-milestones/{milestone_id}")
def update_value_milestone(
    milestone_id: str,
    updates: dict[str, Any],
    caller: Principal = Depends(_caller),
    ctx: AccessContext = Depends(get_access),
) -> dict[str, Any]:
    """Update a value milestone (status, dates, value). It never changes project."""
    client = _get_supabase()
    mid, pid = _authorized_milestone(client, ctx, milestone_id)

    requested = updates.get("project_id")
    if requested is not None:
        # A project id in the body is authorized like any other (404 if
        # hidden); naming a different project, even one the caller owns, is
        # refused rather than silently ignored.
        if not isinstance(requested, str) or ctx.maybe_project(requested) not in (None, pid):
            raise HTTPException(
                status_code=422, detail="A value milestone cannot move to another project"
            )

    allowed_fields = {
        "commercial_value",
        "currency",
        "payment_trigger",
        "contract_ref",
        "notes",
        "baseline_date",
        "forecast_date",
        "actual_date",
        "status",
        "milestone_type",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed_fields}
    filtered["updated_at"] = "now()"

    result = (
        client.table("value_milestones")
        .update(filtered)
        .eq("id", mid)
        .eq("project_id", pid)
        .execute()
    )

    return {"milestone": result.data[0] if result.data else {}}
