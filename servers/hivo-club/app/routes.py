import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from .auth import require_auth
from .acl import check_file_permission, grant_club_access, revoke_club_access
from .db import get_conn
from .models import (
    AddFileRequest,
    AddMemberRequest,
    ClubFileResponse,
    ClubResponse,
    CreateClubRequest,
    CreateInviteLinkRequest,
    InviteLinkResponse,
    JoinResponse,
    MemberResponse,
    MyClubEntry,
    UpdateClubRequest,
    UpdateMyMembershipRequest,
    UpdateRoleRequest,
)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _err(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, "message": message})


def _get_membership(conn, club_id: str, sub: str):
    return conn.execute(
        "SELECT role FROM memberships WHERE club_id = ? AND sub = ?",
        (club_id, sub),
    ).fetchone()


# ── Static ────────────────────────────────────────────────────────────────────

_INDEX_MD = """\
Hey, agent.

I'm hivo-club, part of Hivo. I manage teams and organizations for agents.

For the full skill suite and everything else Hivo offers: https://hivo.ink
"""


@router.get("/", response_class=PlainTextResponse)
def index():
    return _INDEX_MD


@router.get("/health")
def health():
    return {"status": "ok"}


# ── Create Club ───────────────────────────────────────────────────────────────

@router.post("/clubs")
def create_club(req: CreateClubRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]
    now = _now_iso()
    club_id = "club_" + str(uuid.uuid4())
    membership_id = str(uuid.uuid4())

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO clubs (club_id, name, description, owner_sub, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (club_id, req.name, req.description, sub, now, now),
        )
        conn.execute(
            "INSERT INTO memberships (id, club_id, sub, role, invited_by, joined_at) "
            "VALUES (?, ?, ?, 'owner', ?, ?)",
            (membership_id, club_id, sub, sub, now),
        )

    return JSONResponse(
        status_code=201,
        content=ClubResponse(
            club_id=club_id, name=req.name, description=req.description,
            owner_sub=sub, created_at=now, updated_at=now,
        ).model_dump(),
    )


# ── Get Club Info ─────────────────────────────────────────────────────────────

@router.get("/clubs/{club_id}")
def get_club(club_id: str, payload: dict = Depends(require_auth)):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
    if not row:
        return _err(404, "not_found", "Club not found")
    return ClubResponse(
        club_id=row["club_id"], name=row["name"], description=row["description"],
        owner_sub=row["owner_sub"], created_at=row["created_at"], updated_at=row["updated_at"],
    )


# ── List Members ──────────────────────────────────────────────────────────────

@router.get("/clubs/{club_id}/members")
def list_members(club_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]
    with get_conn() as conn:
        club = conn.execute("SELECT club_id FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
        if not club:
            return _err(404, "not_found", "Club not found")

        me = _get_membership(conn, club_id, sub)
        if not me:
            return _err(403, "forbidden", "Only club members can view the member list")

        rows = conn.execute(
            "SELECT sub, role, display_name, bio, note, invited_by, joined_at FROM memberships WHERE club_id = ? ORDER BY joined_at",
            (club_id,),
        ).fetchall()

    return {
        "members": [
            MemberResponse(**dict(r)).model_dump()
            for r in rows
        ]
    }


# ── Add Member (direct) ─────────────────────────────────────────────────────

@router.post("/clubs/{club_id}/members")
def add_member(club_id: str, req: AddMemberRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    if req.role not in ("member", "admin"):
        return _err(422, "validation_error", "Role must be 'member' or 'admin'")

    with get_conn() as conn:
        club = conn.execute("SELECT club_id FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
        if not club:
            return _err(404, "not_found", "Club not found")

        me = _get_membership(conn, club_id, sub)
        if not me or me["role"] not in ("owner", "admin"):
            return _err(403, "forbidden", "Only owner or admin can add members")

        existing = _get_membership(conn, club_id, req.sub)
        if existing:
            return _err(409, "conflict", "User is already a member")

        membership_id = str(uuid.uuid4())
        now = _now_iso()
        conn.execute(
            "INSERT INTO memberships (id, club_id, sub, role, invited_by, joined_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (membership_id, club_id, req.sub, req.role, sub, now),
        )
        return JSONResponse(
            status_code=201,
            content={"sub": req.sub, "role": req.role},
        )


# ── Create Invite Link ─────────────────────────────────────────────────────

@router.post("/clubs/{club_id}/invite-links")
def create_invite_link(club_id: str, req: CreateInviteLinkRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    if req.role not in ("member", "admin"):
        return _err(422, "validation_error", "Role must be 'member' or 'admin'")

    with get_conn() as conn:
        club = conn.execute("SELECT club_id FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
        if not club:
            return _err(404, "not_found", "Club not found")

        me = _get_membership(conn, club_id, sub)
        if not me or me["role"] not in ("owner", "admin"):
            return _err(403, "forbidden", "Only owner or admin can create invite links")

        token = str(uuid.uuid4())
        now = _now_iso()
        conn.execute(
            "INSERT INTO invite_links (token, club_id, role, created_by, max_uses, expires_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token, club_id, req.role, sub, req.max_uses, req.expires_at, now),
        )
        return JSONResponse(
            status_code=201,
            content=InviteLinkResponse(
                token=token, club_id=club_id, role=req.role,
                max_uses=req.max_uses, use_count=0,
                expires_at=req.expires_at, created_at=now,
            ).model_dump(),
        )


# ── List Invite Links ──────────────────────────────────────────────────────

@router.get("/clubs/{club_id}/invite-links")
def list_invite_links(club_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        club = conn.execute("SELECT club_id FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
        if not club:
            return _err(404, "not_found", "Club not found")

        me = _get_membership(conn, club_id, sub)
        if not me or me["role"] not in ("owner", "admin"):
            return _err(403, "forbidden", "Only owner or admin can view invite links")

        rows = conn.execute(
            "SELECT token, club_id, role, max_uses, use_count, expires_at, created_at "
            "FROM invite_links WHERE club_id = ? ORDER BY created_at",
            (club_id,),
        ).fetchall()

    return {
        "invite_links": [
            InviteLinkResponse(**dict(r)).model_dump()
            for r in rows
        ]
    }


# ── Revoke Invite Link ─────────────────────────────────────────────────────

@router.delete("/clubs/{club_id}/invite-links/{token}")
def revoke_invite_link(club_id: str, token: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        club = conn.execute("SELECT club_id FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
        if not club:
            return _err(404, "not_found", "Club not found")

        me = _get_membership(conn, club_id, sub)
        if not me or me["role"] not in ("owner", "admin"):
            return _err(403, "forbidden", "Only owner or admin can revoke invite links")

        link = conn.execute(
            "SELECT token FROM invite_links WHERE token = ? AND club_id = ?",
            (token, club_id),
        ).fetchone()
        if not link:
            return _err(404, "not_found", "Invite link not found")

        conn.execute("DELETE FROM invite_links WHERE token = ?", (token,))

    return Response(status_code=204)


# ── Join via Invite Link ─────────────────────────────────────────────────────

@router.post("/join/{token}")
def join_club(token: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]
    now = _now_iso()

    with get_conn() as conn:
        link = conn.execute("SELECT * FROM invite_links WHERE token = ?", (token,)).fetchone()
        if not link:
            return _err(404, "not_found", "Invite link not found")

        if link["expires_at"] and link["expires_at"] < now:
            return _err(410, "expired", "Invite link has expired")

        if link["max_uses"] is not None and link["use_count"] >= link["max_uses"]:
            return _err(410, "exhausted", "Invite link has reached max uses")

        club_id = link["club_id"]
        existing = _get_membership(conn, club_id, sub)
        if existing:
            return _err(409, "conflict", "Already a member of this club")

        membership_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO memberships (id, club_id, sub, role, invited_by, joined_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (membership_id, club_id, sub, link["role"], link["created_by"], now),
        )
        conn.execute(
            "UPDATE invite_links SET use_count = use_count + 1 WHERE token = ?",
            (token,),
        )

    return JSONResponse(
        status_code=201,
        content=JoinResponse(club_id=club_id, sub=sub, role=link["role"]).model_dump(),
    )


# ── Remove Member / Leave ────────────────────────────────────────────────────

@router.delete("/clubs/{club_id}/members/{target_sub}")
def remove_member(club_id: str, target_sub: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        club = conn.execute("SELECT owner_sub FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
        if not club:
            return _err(404, "not_found", "Club not found")

        target = _get_membership(conn, club_id, target_sub)
        if not target:
            return _err(404, "not_found", "Member not found")

        if sub == target_sub:
            # Self-leave
            if target["role"] == "owner":
                return _err(403, "forbidden", "Owner cannot leave the club")
        else:
            # Remove by admin/owner
            me = _get_membership(conn, club_id, sub)
            if not me or me["role"] not in ("owner", "admin"):
                return _err(403, "forbidden", "Only owner or admin can remove members")
            if target["role"] == "owner":
                return _err(403, "forbidden", "Cannot remove the owner")
            if target["role"] == "admin" and me["role"] != "owner":
                return _err(403, "forbidden", "Only owner can remove an admin")

        conn.execute(
            "DELETE FROM memberships WHERE club_id = ? AND sub = ?",
            (club_id, target_sub),
        )

    return Response(status_code=204)


# ── Update Member Role ────────────────────────────────────────────────────────

@router.patch("/clubs/{club_id}/members/{target_sub}")
def update_role(
    club_id: str, target_sub: str, req: UpdateRoleRequest,
    payload: dict = Depends(require_auth),
):
    sub = payload["sub"]

    if req.role not in ("member", "admin"):
        return _err(422, "validation_error", "Role must be 'member' or 'admin'")

    with get_conn() as conn:
        club = conn.execute("SELECT owner_sub FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
        if not club:
            return _err(404, "not_found", "Club not found")

        me = _get_membership(conn, club_id, sub)
        if not me or me["role"] not in ("owner", "admin"):
            return _err(403, "forbidden", "Only owner or admin can change roles")

        if sub == target_sub:
            return _err(403, "forbidden", "Cannot change your own role")

        target = _get_membership(conn, club_id, target_sub)
        if not target:
            return _err(404, "not_found", "Member not found")

        if target["role"] == "owner":
            return _err(403, "forbidden", "Cannot change the owner's role")

        if me["role"] == "admin" and req.role not in ("member", "admin"):
            return _err(403, "forbidden", "Admin can only set role to member or admin")

        conn.execute(
            "UPDATE memberships SET role = ? WHERE club_id = ? AND sub = ?",
            (req.role, club_id, target_sub),
        )

    return {"sub": target_sub, "role": req.role}


# ── Update Club ──────────────────────────────────────────────────────────────

@router.patch("/clubs/{club_id}", response_model=ClubResponse)
def update_club(club_id: str, req: UpdateClubRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    fields = {}
    if req.name is not None:
        fields["name"] = req.name
    if req.description is not None:
        fields["description"] = req.description

    if not fields:
        return _err(422, "validation_error", "No fields to update")

    with get_conn() as conn:
        membership = _get_membership(conn, club_id, sub)
        if not membership:
            return _err(403, "forbidden", "Not a member of this club")
        if membership["role"] not in ("owner", "admin"):
            return _err(403, "forbidden", "Only owner or admin can update club info")

        fields["updated_at"] = _now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [club_id]
        conn.execute(f"UPDATE clubs SET {set_clause} WHERE club_id = ?", values)

        club = conn.execute(
            "SELECT club_id, name, description, owner_sub, created_at, updated_at FROM clubs WHERE club_id = ?",
            (club_id,),
        ).fetchone()

    return ClubResponse(**dict(club))


# ── Update My Membership ─────────────────────────────────────────────────────

@router.patch("/clubs/{club_id}/me", response_model=MemberResponse)
def update_my_membership(club_id: str, req: UpdateMyMembershipRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    fields = {}
    if req.display_name is not None:
        fields["display_name"] = req.display_name
    if req.bio is not None:
        fields["bio"] = req.bio

    if not fields:
        return _err(422, "validation_error", "No fields to update")

    with get_conn() as conn:
        membership = _get_membership(conn, club_id, sub)
        if not membership:
            return _err(403, "forbidden", "Not a member of this club")

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [club_id, sub]
        conn.execute(f"UPDATE memberships SET {set_clause} WHERE club_id = ? AND sub = ?", values)

        row = conn.execute(
            "SELECT sub, role, display_name, bio, note, invited_by, joined_at "
            "FROM memberships WHERE club_id = ? AND sub = ?",
            (club_id, sub),
        ).fetchone()

    return MemberResponse(**dict(row))


# ── Dissolve Club ─────────────────────────────────────────────────────────────

@router.delete("/clubs/{club_id}")
def dissolve_club(club_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]
    token = payload.get("_token", "")

    with get_conn() as conn:
        club = conn.execute("SELECT owner_sub FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
        if not club:
            return _err(404, "not_found", "Club not found")

        if club["owner_sub"] != sub:
            return _err(403, "forbidden", "Only the owner can dissolve the club")

        # Revoke ACL grants for all club files
        club_files = conn.execute(
            "SELECT file_id FROM club_files WHERE club_id = ?", (club_id,)
        ).fetchall()
        for cf in club_files:
            revoke_club_access(token, club_id, cf["file_id"])

        conn.execute("DELETE FROM club_files WHERE club_id = ?", (club_id,))
        conn.execute("DELETE FROM invite_links WHERE club_id = ?", (club_id,))
        conn.execute("DELETE FROM memberships WHERE club_id = ?", (club_id,))
        conn.execute("DELETE FROM clubs WHERE club_id = ?", (club_id,))

    return Response(status_code=204)


# ── My Clubs ──────────────────────────────────────────────────────────────────

@router.get("/me/clubs")
def my_clubs(payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.club_id, c.name, m.role, m.joined_at "
            "FROM memberships m JOIN clubs c ON m.club_id = c.club_id "
            "WHERE m.sub = ? ORDER BY m.joined_at",
            (sub,),
        ).fetchall()

    return {
        "clubs": [
            MyClubEntry(
                club_id=r["club_id"], name=r["name"],
                role=r["role"], joined_at=r["joined_at"],
            ).model_dump()
            for r in rows
        ]
    }


@router.get("/internal/members/{sub}/clubs")
def internal_member_clubs(sub: str):
    """Internal endpoint for hivo-acl to query club memberships without auth."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT club_id FROM memberships WHERE sub = ?",
            (sub,),
        ).fetchall()
    return [{"club_id": r["club_id"]} for r in rows]


# ── Club Files ───────────────────────────────────────────────────────────────

_VALID_PERMISSIONS = {"read", "read,write"}


@router.post("/clubs/{club_id}/files")
def add_club_file(club_id: str, req: AddFileRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]
    token = payload.get("_token", "")

    if req.permissions not in _VALID_PERMISSIONS:
        return _err(422, "validation_error", "permissions must be 'read' or 'read,write'")

    alias = req.alias.strip("/")
    if not alias or ".." in alias.split("/"):
        return _err(422, "validation_error", "Invalid alias")

    with get_conn() as conn:
        club = conn.execute("SELECT club_id FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
        if not club:
            return _err(404, "not_found", "Club not found")

        me = _get_membership(conn, club_id, sub)
        if not me:
            return _err(403, "forbidden", "You are not a member of this club")

        # Verify caller has admin permission on the file (i.e. is the file owner)
        if not check_file_permission(token, sub, req.file_id, "admin"):
            return _err(403, "forbidden", "You do not own this file or lack admin permission")

        # Check duplicates
        existing_alias = conn.execute(
            "SELECT id FROM club_files WHERE club_id = ? AND alias = ?",
            (club_id, alias),
        ).fetchone()
        if existing_alias:
            return _err(409, "conflict", f"Alias '{alias}' already exists in this club")

        existing_file = conn.execute(
            "SELECT id FROM club_files WHERE club_id = ? AND file_id = ?",
            (club_id, req.file_id),
        ).fetchone()
        if existing_file:
            return _err(409, "conflict", "This file is already registered in this club")

        record_id = str(uuid.uuid4())
        now = _now_iso()
        conn.execute(
            """INSERT INTO club_files
               (id, club_id, file_id, owner_sub, alias, permissions, contributed_by, added_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (record_id, club_id, req.file_id, sub, alias, req.permissions, sub, now),
        )

    # Grant club access via ACL
    perm_list = [p.strip() for p in req.permissions.split(",")]
    grant_club_access(token, club_id, req.file_id, perm_list)

    return JSONResponse(
        status_code=201,
        content=ClubFileResponse(
            id=record_id, club_id=club_id, file_id=req.file_id,
            owner_sub=sub, alias=alias, permissions=req.permissions,
            contributed_by=sub, added_at=now,
        ).model_dump(),
    )


@router.get("/clubs/{club_id}/files")
def list_club_files(club_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        club = conn.execute("SELECT club_id FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
        if not club:
            return _err(404, "not_found", "Club not found")

        me = _get_membership(conn, club_id, sub)
        if not me:
            return _err(403, "forbidden", "You are not a member of this club")

        rows = conn.execute(
            "SELECT id, club_id, file_id, owner_sub, alias, permissions, contributed_by, added_at "
            "FROM club_files WHERE club_id = ? ORDER BY added_at",
            (club_id,),
        ).fetchall()

    return {
        "files": [
            ClubFileResponse(
                id=r["id"], club_id=r["club_id"], file_id=r["file_id"],
                owner_sub=r["owner_sub"], alias=r["alias"], permissions=r["permissions"],
                contributed_by=r["contributed_by"], added_at=r["added_at"],
            ).model_dump()
            for r in rows
        ]
    }


@router.delete("/clubs/{club_id}/files/{file_id}")
def remove_club_file(club_id: str, file_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]
    token = payload.get("_token", "")

    with get_conn() as conn:
        club = conn.execute("SELECT owner_sub FROM clubs WHERE club_id = ?", (club_id,)).fetchone()
        if not club:
            return _err(404, "not_found", "Club not found")

        me = _get_membership(conn, club_id, sub)
        if not me:
            return _err(403, "forbidden", "You are not a member of this club")

        cf = conn.execute(
            "SELECT id, contributed_by FROM club_files WHERE club_id = ? AND file_id = ?",
            (club_id, file_id),
        ).fetchone()
        if not cf:
            return _err(404, "not_found", "File not found in this club")

        # Only contributor, club owner, or club admin can remove
        is_contributor = cf["contributed_by"] == sub
        is_privileged = me["role"] in ("owner", "admin")
        if not is_contributor and not is_privileged:
            return _err(403, "forbidden", "Only the contributor, owner, or admin can remove this file")

        conn.execute("DELETE FROM club_files WHERE id = ?", (cf["id"],))

    revoke_club_access(token, club_id, file_id)
    return Response(status_code=204)
