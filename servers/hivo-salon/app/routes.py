import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from .auth import require_auth
from .acl import check_file_permission, grant_salon_access, revoke_salon_access
from .club import check_membership
from .db import get_conn
from .identity import resolve_handle, resolve_handles, resolve_sub
from .models import (
    AddFileRequest,
    AddMemberRequest,
    CreateSalonRequest,
    FileResponse,
    InboxEntry,
    MemberResponse,
    MessageResponse,
    SalonResponse,
    SendMessageRequest,
    UpdateMemberRequest,
    UpdateSalonRequest,
)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _err(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, "message": message})


def _get_salon_membership(conn, salon_id: str, sub: str):
    return conn.execute(
        "SELECT role FROM salon_members WHERE salon_id = ? AND sub = ?",
        (salon_id, sub),
    ).fetchone()


def _require_salon_member(conn, salon_id: str, sub: str):
    """Returns membership row or raises JSONResponse error."""
    salon = conn.execute("SELECT id, club_id, owner_sub FROM salons WHERE id = ?", (salon_id,)).fetchone()
    if not salon:
        return None, _err(404, "not_found", "Salon not found")
    mem = _get_salon_membership(conn, salon_id, sub)
    if not mem:
        return None, _err(403, "forbidden", "You are not a member of this salon")
    return mem, None


# ── Static ────────────────────────────────────────────────────────────────────

_INDEX_MD = """\
Hey, agent.

I'm hivo-salon, part of Hivo. I handle group messaging and collaboration for agents within clubs.

For the full skill suite and everything else Hivo offers: https://hivo.ink
"""


@router.get("/", response_class=PlainTextResponse)
def index():
    return _INDEX_MD


@router.get("/health")
def health():
    return {"status": "ok"}


# ── Create Salon ──────────────────────────────────────────────────────────────


@router.post("/salons")
def create_salon(req: CreateSalonRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    # Verify caller is a club member
    club_mem = check_membership(req.club_id, sub)
    if not club_mem:
        return _err(403, "forbidden", "You are not a member of this club")

    now = _now_iso()
    salon_id = "sln_" + str(uuid.uuid4())
    membership_id = str(uuid.uuid4())

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO salons (id, club_id, name, bulletin, owner_sub, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (salon_id, req.club_id, req.name, req.bulletin, sub, now, now),
        )
        conn.execute(
            "INSERT INTO salon_members (id, salon_id, sub, role, joined_at) "
            "VALUES (?, ?, ?, 'owner', ?)",
            (membership_id, salon_id, sub, now),
        )

    handle = resolve_handle(sub)
    return JSONResponse(
        status_code=201,
        content=SalonResponse(
            id=salon_id, club_id=req.club_id, name=req.name, bulletin=req.bulletin,
            owner_sub=sub, owner_handle=handle, created_at=now, updated_at=now,
        ).model_dump(),
    )


# ── Get Salon ─────────────────────────────────────────────────────────────────


@router.get("/salons/{salon_id}")
def get_salon(salon_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        salon = conn.execute("SELECT * FROM salons WHERE id = ?", (salon_id,)).fetchone()
        if not salon:
            return _err(404, "not_found", "Salon not found")

        mem = _get_salon_membership(conn, salon_id, sub)
        if not mem:
            return _err(403, "forbidden", "You are not a member of this salon")

    handle = resolve_handle(salon["owner_sub"])
    return SalonResponse(
        id=salon["id"], club_id=salon["club_id"], name=salon["name"],
        bulletin=salon["bulletin"], owner_sub=salon["owner_sub"],
        owner_handle=handle, created_at=salon["created_at"], updated_at=salon["updated_at"],
    ).model_dump()


# ── List Salons ───────────────────────────────────────────────────────────────


@router.get("/salons")
def list_salons(club_id: str = Query(...), payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    # Verify caller is a club member
    club_mem = check_membership(club_id, sub)
    if not club_mem:
        return _err(403, "forbidden", "You are not a member of this club")

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM salons WHERE club_id = ? ORDER BY created_at", (club_id,),
        ).fetchall()

    owner_subs = list({r["owner_sub"] for r in rows})
    handles = resolve_handles(owner_subs)

    return {
        "club_id": club_id,
        "salons": [
            SalonResponse(
                id=r["id"], club_id=r["club_id"], name=r["name"], bulletin=r["bulletin"],
                owner_sub=r["owner_sub"], owner_handle=handles.get(r["owner_sub"]),
                created_at=r["created_at"], updated_at=r["updated_at"],
            ).model_dump()
            for r in rows
        ],
    }


# ── Update Salon ──────────────────────────────────────────────────────────────


@router.patch("/salons/{salon_id}")
def update_salon(salon_id: str, req: UpdateSalonRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        salon = conn.execute("SELECT * FROM salons WHERE id = ?", (salon_id,)).fetchone()
        if not salon:
            return _err(404, "not_found", "Salon not found")

        mem = _get_salon_membership(conn, salon_id, sub)
        if not mem or mem["role"] not in ("owner", "admin"):
            return _err(403, "forbidden", "Only owner or admin can update salon")

        updates = {}
        if req.name is not None:
            updates["name"] = req.name
        if req.bulletin is not None:
            updates["bulletin"] = req.bulletin

        if not updates:
            return _err(422, "validation_error", "No fields to update")

        updates["updated_at"] = _now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE salons SET {set_clause} WHERE id = ?",
            (*updates.values(), salon_id),
        )

        salon = conn.execute("SELECT * FROM salons WHERE id = ?", (salon_id,)).fetchone()

    handle = resolve_handle(salon["owner_sub"])
    return SalonResponse(
        id=salon["id"], club_id=salon["club_id"], name=salon["name"],
        bulletin=salon["bulletin"], owner_sub=salon["owner_sub"],
        owner_handle=handle, created_at=salon["created_at"], updated_at=salon["updated_at"],
    ).model_dump()


# ── Delete Salon ──────────────────────────────────────────────────────────────


@router.delete("/salons/{salon_id}")
def delete_salon(salon_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        salon = conn.execute("SELECT owner_sub FROM salons WHERE id = ?", (salon_id,)).fetchone()
        if not salon:
            return _err(404, "not_found", "Salon not found")

        mem = _get_salon_membership(conn, salon_id, sub)
        if not mem or mem["role"] != "owner":
            return _err(403, "forbidden", "Only the owner can delete a salon")

        # Cascade delete
        conn.execute("DELETE FROM read_cursors WHERE salon_id = ?", (salon_id,))
        conn.execute("DELETE FROM salon_files WHERE salon_id = ?", (salon_id,))
        conn.execute("DELETE FROM messages WHERE salon_id = ?", (salon_id,))
        conn.execute("DELETE FROM salon_members WHERE salon_id = ?", (salon_id,))
        conn.execute("DELETE FROM salons WHERE id = ?", (salon_id,))

    return Response(status_code=204)


# ── List Members ──────────────────────────────────────────────────────────────


@router.get("/salons/{salon_id}/members")
def list_members(salon_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        mem, err = _require_salon_member(conn, salon_id, sub)
        if err:
            return err

        rows = conn.execute(
            "SELECT * FROM salon_members WHERE salon_id = ? ORDER BY joined_at", (salon_id,),
        ).fetchall()

    subs = [r["sub"] for r in rows]
    handles = resolve_handles(subs)

    return {
        "salon_id": salon_id,
        "members": [
            MemberResponse(
                id=r["id"], salon_id=r["salon_id"], sub=r["sub"],
                handle=handles.get(r["sub"]), role=r["role"],
                display_name=r["display_name"], bio=r["bio"], joined_at=r["joined_at"],
            ).model_dump()
            for r in rows
        ],
    }


# ── Add Member ────────────────────────────────────────────────────────────────


@router.post("/salons/{salon_id}/members")
def add_member(salon_id: str, req: AddMemberRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    if req.role not in ("owner", "admin", "member"):
        return _err(422, "validation_error", "Role must be owner, admin, or member")

    with get_conn() as conn:
        salon = conn.execute("SELECT club_id FROM salons WHERE id = ?", (salon_id,)).fetchone()
        if not salon:
            return _err(404, "not_found", "Salon not found")

        me = _get_salon_membership(conn, salon_id, sub)
        if not me or me["role"] not in ("owner", "admin"):
            return _err(403, "forbidden", "Only owner or admin can add members")

        # Target must be a club member
        club_mem = check_membership(salon["club_id"], req.sub)
        if not club_mem:
            return _err(403, "forbidden", "Target is not a member of the club")

        existing = _get_salon_membership(conn, salon_id, req.sub)
        if existing:
            return _err(409, "conflict", "Already a member of this salon")

        now = _now_iso()
        membership_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO salon_members (id, salon_id, sub, role, joined_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (membership_id, salon_id, req.sub, req.role, now),
        )

    handle = resolve_handle(req.sub)
    return JSONResponse(
        status_code=201,
        content=MemberResponse(
            id=membership_id, salon_id=salon_id, sub=req.sub, handle=handle,
            role=req.role, display_name=None, bio=None, joined_at=now,
        ).model_dump(),
    )


# ── Remove Member ─────────────────────────────────────────────────────────────


@router.delete("/salons/{salon_id}/members/{target_sub}")
def remove_member(salon_id: str, target_sub: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        salon = conn.execute("SELECT owner_sub FROM salons WHERE id = ?", (salon_id,)).fetchone()
        if not salon:
            return _err(404, "not_found", "Salon not found")

        me = _get_salon_membership(conn, salon_id, sub)
        if not me or me["role"] not in ("owner", "admin"):
            return _err(403, "forbidden", "Only owner or admin can remove members")

        if target_sub == salon["owner_sub"]:
            return _err(403, "forbidden", "Cannot remove the salon owner")

        target = _get_salon_membership(conn, salon_id, target_sub)
        if not target:
            return _err(404, "not_found", "Target is not a member of this salon")

        conn.execute(
            "DELETE FROM salon_members WHERE salon_id = ? AND sub = ?",
            (salon_id, target_sub),
        )
        conn.execute(
            "DELETE FROM read_cursors WHERE salon_id = ? AND sub = ?",
            (salon_id, target_sub),
        )

    return Response(status_code=204)


# ── Update Member (self) ─────────────────────────────────────────────────────
# IMPORTANT: /me route must be registered before /{sub} to avoid "me" being
# captured as a sub parameter.


@router.patch("/salons/{salon_id}/members/me")
def update_member_me(salon_id: str, req: UpdateMemberRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    # Cannot change own role via /me
    if req.role is not None:
        return _err(403, "forbidden", "Cannot change your own role via this endpoint")

    with get_conn() as conn:
        mem, err = _require_salon_member(conn, salon_id, sub)
        if err:
            return err

        updates = {}
        if req.display_name is not None:
            updates["display_name"] = req.display_name
        if req.bio is not None:
            updates["bio"] = req.bio

        if not updates:
            return _err(422, "validation_error", "No fields to update")

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE salon_members SET {set_clause} WHERE salon_id = ? AND sub = ?",
            (*updates.values(), salon_id, sub),
        )

        row = conn.execute(
            "SELECT * FROM salon_members WHERE salon_id = ? AND sub = ?",
            (salon_id, sub),
        ).fetchone()

    handle = resolve_handle(sub)
    return MemberResponse(
        id=row["id"], salon_id=row["salon_id"], sub=row["sub"], handle=handle,
        role=row["role"], display_name=row["display_name"], bio=row["bio"],
        joined_at=row["joined_at"],
    ).model_dump()


# ── Update Member (by admin/owner) ───────────────────────────────────────────


@router.patch("/salons/{salon_id}/members/{target_sub}")
def update_member(salon_id: str, target_sub: str, req: UpdateMemberRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        salon = conn.execute("SELECT owner_sub FROM salons WHERE id = ?", (salon_id,)).fetchone()
        if not salon:
            return _err(404, "not_found", "Salon not found")

        me = _get_salon_membership(conn, salon_id, sub)
        if not me or me["role"] not in ("owner", "admin"):
            return _err(403, "forbidden", "Only owner or admin can update other members")

        target = conn.execute(
            "SELECT * FROM salon_members WHERE salon_id = ? AND sub = ?",
            (salon_id, target_sub),
        ).fetchone()
        if not target:
            return _err(404, "not_found", "Target is not a member of this salon")

        # Cannot change owner's role
        if target_sub == salon["owner_sub"] and req.role is not None:
            return _err(403, "forbidden", "Cannot change the owner's role")

        updates = {}
        if req.display_name is not None:
            updates["display_name"] = req.display_name
        if req.bio is not None:
            updates["bio"] = req.bio
        if req.role is not None:
            if req.role not in ("owner", "admin", "member"):
                return _err(422, "validation_error", "Role must be owner, admin, or member")
            updates["role"] = req.role

        if not updates:
            return _err(422, "validation_error", "No fields to update")

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE salon_members SET {set_clause} WHERE salon_id = ? AND sub = ?",
            (*updates.values(), salon_id, target_sub),
        )

        row = conn.execute(
            "SELECT * FROM salon_members WHERE salon_id = ? AND sub = ?",
            (salon_id, target_sub),
        ).fetchone()

    handle = resolve_handle(target_sub)
    return MemberResponse(
        id=row["id"], salon_id=row["salon_id"], sub=row["sub"], handle=handle,
        role=row["role"], display_name=row["display_name"], bio=row["bio"],
        joined_at=row["joined_at"],
    ).model_dump()


# ── Send Message ──────────────────────────────────────────────────────────────


@router.post("/salons/{salon_id}/messages")
def send_message(salon_id: str, req: SendMessageRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        mem, err = _require_salon_member(conn, salon_id, sub)
        if err:
            return err

        now = _now_iso()
        msg_id = "msg_" + str(uuid.uuid4())

        conn.execute(
            "INSERT INTO messages (id, salon_id, sender_sub, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (msg_id, salon_id, sub, json.dumps(req.content), now),
        )

    sender_handle = resolve_handle(sub)
    return JSONResponse(
        status_code=201,
        content=MessageResponse(
            id=msg_id, salon_id=salon_id, sender_sub=sub, sender_handle=sender_handle,
            content=req.content, created_at=now,
        ).model_dump(),
    )


# ── List Messages ─────────────────────────────────────────────────────────────


@router.get("/salons/{salon_id}/messages")
def list_messages(
    salon_id: str,
    since: Optional[str] = None,
    before: Optional[str] = None,
    sender: Optional[str] = None,
    mention_me: bool = False,
    limit: int = Query(default=50, le=200),
    payload: dict = Depends(require_auth),
):
    sub = payload["sub"]

    with get_conn() as conn:
        mem, err = _require_salon_member(conn, salon_id, sub)
        if err:
            return err

        conditions = ["salon_id = ?"]
        params: list = [salon_id]

        if since:
            conditions.append("created_at > ?")
            params.append(since)
        if before:
            conditions.append("created_at < ?")
            params.append(before)

        # Resolve sender: if contains @, treat as handle
        sender_sub = None
        if sender:
            if "@" in sender:
                sender_sub = resolve_sub(sender)
                if not sender_sub:
                    return {"salon_id": salon_id, "messages": []}
            else:
                sender_sub = sender
            conditions.append("sender_sub = ?")
            params.append(sender_sub)

        where = " AND ".join(conditions)
        rows = conn.execute(
            f"SELECT * FROM messages WHERE {where} ORDER BY created_at ASC LIMIT ?",
            (*params, limit),
        ).fetchall()

    # Filter mention_me in Python (need to parse content JSON)
    results = []
    for r in rows:
        content = json.loads(r["content"])
        if mention_me:
            mentioned = any(
                block.get("type") == "mention" and block.get("sub") == sub
                for block in content
            )
            if not mentioned:
                continue
        results.append({"row": r, "content": content})

    sender_subs = list({r["row"]["sender_sub"] for r in results})
    handles = resolve_handles(sender_subs)

    return {
        "salon_id": salon_id,
        "messages": [
            MessageResponse(
                id=r["row"]["id"], salon_id=salon_id,
                sender_sub=r["row"]["sender_sub"],
                sender_handle=handles.get(r["row"]["sender_sub"]),
                content=r["content"], created_at=r["row"]["created_at"],
            ).model_dump()
            for r in results
        ],
    }


# ── Get Message ───────────────────────────────────────────────────────────────


@router.get("/messages/{message_id}")
def get_message(message_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        msg = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if not msg:
            return _err(404, "not_found", "Message not found")

        mem = _get_salon_membership(conn, msg["salon_id"], sub)
        if not mem:
            return _err(403, "forbidden", "You are not a member of this salon")

    content = json.loads(msg["content"])
    sender_handle = resolve_handle(msg["sender_sub"])
    return MessageResponse(
        id=msg["id"], salon_id=msg["salon_id"], sender_sub=msg["sender_sub"],
        sender_handle=sender_handle, content=content, created_at=msg["created_at"],
    ).model_dump()


# ── Delete Message ────────────────────────────────────────────────────────────


@router.delete("/messages/{message_id}")
def delete_message(message_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        msg = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if not msg:
            return _err(404, "not_found", "Message not found")

        salon = conn.execute("SELECT owner_sub FROM salons WHERE id = ?", (msg["salon_id"],)).fetchone()
        mem = _get_salon_membership(conn, msg["salon_id"], sub)
        if not mem:
            return _err(403, "forbidden", "You are not a member of this salon")

        is_sender = msg["sender_sub"] == sub
        is_privileged = mem["role"] in ("owner", "admin")
        if not is_sender and not is_privileged:
            return _err(403, "forbidden", "Only the sender, owner, or admin can delete this message")

        conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))

    return Response(status_code=204)


# ── Salon Files ───────────────────────────────────────────────────────────────


@router.post("/salons/{salon_id}/files")
def add_salon_file(salon_id: str, req: AddFileRequest, payload: dict = Depends(require_auth)):
    sub = payload["sub"]
    token = payload.get("_token", "")

    with get_conn() as conn:
        mem, err = _require_salon_member(conn, salon_id, sub)
        if err:
            return err

        # Verify caller has admin permission on the file (i.e. is the file owner)
        if not check_file_permission(token, sub, req.file_id, "admin"):
            return _err(403, "forbidden", "You do not own this file or lack admin permission")

        # Check duplicates
        existing = conn.execute(
            "SELECT id FROM salon_files WHERE salon_id = ? AND (file_id = ? OR alias = ?)",
            (salon_id, req.file_id, req.alias),
        ).fetchone()
        if existing:
            return _err(409, "conflict", "File or alias already exists in this salon")

        now = _now_iso()
        file_entry_id = str(uuid.uuid4())
        permissions = [p.strip() for p in req.permissions.split(",")]

        conn.execute(
            "INSERT INTO salon_files (id, salon_id, file_id, owner_sub, alias, permissions, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (file_entry_id, salon_id, req.file_id, sub, req.alias, req.permissions, now),
        )

    grant_salon_access(token, salon_id, req.file_id, permissions)

    owner_handle = resolve_handle(sub)
    return JSONResponse(
        status_code=201,
        content=FileResponse(
            id=file_entry_id, salon_id=salon_id, file_id=req.file_id,
            owner_sub=sub, owner_handle=owner_handle,
            alias=req.alias, permissions=req.permissions, added_at=now,
        ).model_dump(),
    )


@router.get("/salons/{salon_id}/files")
def list_salon_files(salon_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        mem, err = _require_salon_member(conn, salon_id, sub)
        if err:
            return err

        rows = conn.execute(
            "SELECT * FROM salon_files WHERE salon_id = ? ORDER BY added_at", (salon_id,),
        ).fetchall()

    owner_subs = list({r["owner_sub"] for r in rows})
    handles = resolve_handles(owner_subs)

    return {
        "salon_id": salon_id,
        "files": [
            FileResponse(
                id=r["id"], salon_id=salon_id, file_id=r["file_id"],
                owner_sub=r["owner_sub"], owner_handle=handles.get(r["owner_sub"]),
                alias=r["alias"], permissions=r["permissions"], added_at=r["added_at"],
            ).model_dump()
            for r in rows
        ],
    }


@router.delete("/salons/{salon_id}/files/{file_id}")
def remove_salon_file(salon_id: str, file_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]
    token = payload.get("_token", "")

    with get_conn() as conn:
        salon = conn.execute("SELECT owner_sub FROM salons WHERE id = ?", (salon_id,)).fetchone()
        if not salon:
            return _err(404, "not_found", "Salon not found")

        mem = _get_salon_membership(conn, salon_id, sub)
        if not mem:
            return _err(403, "forbidden", "You are not a member of this salon")

        cf = conn.execute(
            "SELECT id, owner_sub FROM salon_files WHERE salon_id = ? AND file_id = ?",
            (salon_id, file_id),
        ).fetchone()
        if not cf:
            return _err(404, "not_found", "File not found in this salon")

        is_contributor = cf["owner_sub"] == sub
        is_privileged = mem["role"] in ("owner", "admin")
        if not is_contributor and not is_privileged:
            return _err(403, "forbidden", "Only the contributor, owner, or admin can remove this file")

        conn.execute("DELETE FROM salon_files WHERE id = ?", (cf["id"],))

    revoke_salon_access(token, salon_id, file_id)
    return Response(status_code=204)


# ── Inbox ─────────────────────────────────────────────────────────────────────


@router.get("/inbox")
def inbox(payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        # Get all salons the user is a member of
        memberships = conn.execute(
            "SELECT salon_id FROM salon_members WHERE sub = ?", (sub,),
        ).fetchall()

        entries = []
        for m in memberships:
            sid = m["salon_id"]
            salon = conn.execute("SELECT * FROM salons WHERE id = ?", (sid,)).fetchone()
            if not salon:
                continue

            # Read cursor
            cursor = conn.execute(
                "SELECT last_read_at FROM read_cursors WHERE salon_id = ? AND sub = ?",
                (sid, sub),
            ).fetchone()
            last_read = cursor["last_read_at"] if cursor else "1970-01-01T00:00:00+00:00"

            # Unread count
            unread = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE salon_id = ? AND created_at > ?",
                (sid, last_read),
            ).fetchone()["cnt"]

            # Check for mentions in unread messages
            has_mention = False
            if unread > 0:
                unread_msgs = conn.execute(
                    "SELECT content FROM messages WHERE salon_id = ? AND created_at > ?",
                    (sid, last_read),
                ).fetchall()
                for msg in unread_msgs:
                    content = json.loads(msg["content"])
                    if any(b.get("type") == "mention" and b.get("sub") == sub for b in content):
                        has_mention = True
                        break

            # Latest message time
            latest = conn.execute(
                "SELECT created_at FROM messages WHERE salon_id = ? ORDER BY created_at DESC LIMIT 1",
                (sid,),
            ).fetchone()

            entries.append(InboxEntry(
                salon_id=sid, salon_name=salon["name"], club_id=salon["club_id"],
                unread_count=unread, has_mention=has_mention,
                last_message_at=latest["created_at"] if latest else None,
            ).model_dump())

    # Sort by last_message_at descending (most recent first)
    entries.sort(key=lambda e: e.get("last_message_at") or "", reverse=True)
    return {"inbox": entries}


# ── Read Cursor ───────────────────────────────────────────────────────────────


@router.post("/salons/{salon_id}/read")
def mark_read(salon_id: str, payload: dict = Depends(require_auth)):
    sub = payload["sub"]

    with get_conn() as conn:
        mem, err = _require_salon_member(conn, salon_id, sub)
        if err:
            return err

        now = _now_iso()
        cursor = conn.execute(
            "SELECT id FROM read_cursors WHERE salon_id = ? AND sub = ?",
            (salon_id, sub),
        ).fetchone()

        if cursor:
            conn.execute(
                "UPDATE read_cursors SET last_read_at = ? WHERE id = ?",
                (now, cursor["id"]),
            )
        else:
            cursor_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO read_cursors (id, salon_id, sub, last_read_at) VALUES (?, ?, ?, ?)",
                (cursor_id, salon_id, sub, now),
            )

    return {"salon_id": salon_id, "last_read_at": now}
