# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Organization, membership, and sharing API endpoints.

Implements the hybrid multi-org model:
- Each company (Owner, PM, CM, GC) has its own organization
- Projects can be shared across organizations with granular permissions
- Audit trail logs all significant actions
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import optional_auth

router = APIRouter(prefix="/api/v1", tags=["organizations"])


# ── Schemas ─────────────────────────────────────────────


class CreateOrgRequest(BaseModel):
    name: str
    org_type: str = "general"
    description: str = ""


class InviteMemberRequest(BaseModel):
    email: str
    role: str = "member"


class ShareProjectRequest(BaseModel):
    project_id: str
    shared_with_org_id: str
    permission: str = "viewer"


class ShareProgramRequest(BaseModel):
    program_id: str
    shared_with_org_id: str
    permission: str = "viewer"


# ── Helper ──────────────────────────────────────────────


def _get_supabase():
    """Get Supabase client (service role for admin operations)."""
    from src.database.client import get_supabase_client

    return get_supabase_client()


def _get_user_orgs(user_id: str) -> list[dict]:
    """Get all organizations the user belongs to."""
    client = _get_supabase()
    result = (
        client.table("memberships")
        .select("org_id, role, organizations(id, name, slug, org_type)")
        .eq("user_id", user_id)
        .execute()
    )
    return result.data or []


def _check_org_role(user_id: str, org_id: str, required_roles: list[str]) -> dict:
    """Verify user has required role in org. Raises 403 if not."""
    client = _get_supabase()
    result = (
        client.table("memberships")
        .select("role")
        .eq("user_id", user_id)
        .eq("org_id", org_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    role = result.data[0]["role"]
    if role not in required_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Requires role {required_roles}, you have {role}",
        )
    return result.data[0]


def _audit(
    org_id: str | None,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None,
    details: dict | None = None,
):
    """Write an audit log entry."""
    client = _get_supabase()
    client.table("audit_log").insert(
        {
            "org_id": org_id,
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details or {},
        }
    ).execute()


# ── Organization CRUD ───────────────────────────────────


@router.get("/organizations")
def list_organizations(user: dict = Depends(optional_auth)):
    """List organizations the current user belongs to."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    memberships = _get_user_orgs(user["id"])
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
def create_organization(req: CreateOrgRequest, user: dict = Depends(optional_auth)):
    """Create a new organization and add the creator as owner."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    client = _get_supabase()
    import re

    slug = re.sub(r"[^a-zA-Z0-9]", "-", req.name.lower()).strip("-")
    slug = f"{slug}-{user['id'][:8]}"

    # Create org
    org_result = (
        client.table("organizations")
        .insert(
            {
                "name": req.name,
                "slug": slug,
                "org_type": req.org_type,
                "description": req.description,
                "created_by": user["id"],
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
            "user_id": user["id"],
            "role": "owner",
            "accepted_at": "now()",
        }
    ).execute()

    _audit(org["id"], user["id"], "create", "organization", org["id"], {"name": req.name})

    return {"organization": org}


@router.get("/organizations/{org_id}")
def get_organization(org_id: str, user: dict = Depends(optional_auth)):
    """Get organization details including members."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    _check_org_role(user["id"], org_id, ["owner", "admin", "member", "viewer"])

    client = _get_supabase()
    org_result = client.table("organizations").select("*").eq("id", org_id).execute()
    if not org_result.data:
        raise HTTPException(status_code=404, detail="Organization not found")

    members_result = (
        client.table("memberships")
        .select("user_id, role, accepted_at, user_profiles(email, full_name, avatar_url)")
        .eq("org_id", org_id)
        .execute()
    )

    return {
        "organization": org_result.data[0],
        "members": members_result.data or [],
    }


# ── Membership Management ──────────────────────────────


@router.post("/organizations/{org_id}/invite")
def invite_member(org_id: str, req: InviteMemberRequest, user: dict = Depends(optional_auth)):
    """Invite a user to the organization by email."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    _check_org_role(user["id"], org_id, ["owner", "admin"])

    client = _get_supabase()

    # Find user by email
    profile_result = client.table("user_profiles").select("id").eq("email", req.email).execute()
    if not profile_result.data:
        raise HTTPException(status_code=404, detail=f"No user found with email {req.email}")

    target_user_id = profile_result.data[0]["id"]

    # Check if already a member
    existing = (
        client.table("memberships")
        .select("id")
        .eq("org_id", org_id)
        .eq("user_id", target_user_id)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="User is already a member")

    # Create membership
    client.table("memberships").insert(
        {
            "org_id": org_id,
            "user_id": target_user_id,
            "role": req.role,
            "invited_by": user["id"],
            "accepted_at": "now()",
        }
    ).execute()

    _audit(
        org_id,
        user["id"],
        "invite",
        "membership",
        target_user_id,
        {
            "email": req.email,
            "role": req.role,
        },
    )

    return {"status": "invited", "email": req.email, "role": req.role}


@router.delete("/organizations/{org_id}/members/{member_user_id}")
def remove_member(org_id: str, member_user_id: str, user: dict = Depends(optional_auth)):
    """Remove a member from the organization."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    _check_org_role(user["id"], org_id, ["owner", "admin"])

    client = _get_supabase()
    client.table("memberships").delete().eq("org_id", org_id).eq(
        "user_id", member_user_id
    ).execute()

    _audit(org_id, user["id"], "remove_member", "membership", member_user_id)

    return {"status": "removed"}


# ── Cross-Org Sharing ──────────────────────────────────


@router.post("/shares/project")
def share_project(req: ShareProjectRequest, user: dict = Depends(optional_auth)):
    """Share a project with another organization."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    client = _get_supabase()

    # Verify user owns the project (via their org)
    project = client.table("projects").select("id, org_id").eq("id", req.project_id).execute()
    if not project.data:
        raise HTTPException(status_code=404, detail="Project not found")

    project_org_id = project.data[0].get("org_id")
    if project_org_id:
        _check_org_role(user["id"], project_org_id, ["owner", "admin"])

    # Create share
    client.table("project_shares").upsert(
        {
            "project_id": req.project_id,
            "shared_with_org": req.shared_with_org_id,
            "permission": req.permission,
            "shared_by": user["id"],
        }
    ).execute()

    _audit(
        project_org_id,
        user["id"],
        "share",
        "project",
        req.project_id,
        {
            "shared_with_org": req.shared_with_org_id,
            "permission": req.permission,
        },
    )

    return {"status": "shared", "permission": req.permission}


@router.get("/shares/project/{project_id}")
def get_project_shares(project_id: str, user: dict = Depends(optional_auth)):
    """List all organizations a project is shared with."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    client = _get_supabase()
    result = (
        client.table("project_shares")
        .select("*, organizations(id, name, slug, org_type)")
        .eq("project_id", project_id)
        .execute()
    )

    return {"shares": result.data or []}


# ── Audit Trail ────────────────────────────────────────


@router.get("/organizations/{org_id}/audit")
def get_audit_log(
    org_id: str,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(optional_auth),
):
    """Get audit log for an organization. Required for litigation traceability."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    _check_org_role(user["id"], org_id, ["owner", "admin"])

    client = _get_supabase()
    result = (
        client.table("audit_log")
        .select("*, user_profiles(email, full_name)")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return {"entries": result.data or [], "limit": limit, "offset": offset}
