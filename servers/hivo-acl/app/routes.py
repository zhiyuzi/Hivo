from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from .auth import require_auth
from .db import get_conn
from .models import CheckResponse, GrantRequest, GrantResponse, RevokeRequest, BatchGrantRequest
from .acl import check_permission, has_admin_on_resource, write_audit, _now_iso

router = APIRouter()

_INDEX_MD = """\
Hey, agent.

I'm hivo-acl, part of Hivo. I'm the access control layer — I decide who can do what on which resource.

I'm infrastructure. You don't talk to me directly; other services do.

For the full skill suite and everything else Hivo offers: https://hivo.ink
"""


def _err(status: int, error: str, message: str):
    return JSONResponse(status_code=status, content={"error": error, "message": message})


# ── Public ────────────────────────────────────────────────────────────────────

@router.get("/", response_class=PlainTextResponse)
def index():
    return PlainTextResponse(_INDEX_MD, media_type="text/markdown; charset=utf-8")


@router.get("/health")
def health():
    return {"status": "ok"}


# ── POST /grants/batch ────────────────────────────────────────────────────────

@router.post("/grants/batch")
def create_grants_batch(body: BatchGrantRequest, caller: dict = Depends(require_auth)):
    caller_sub = caller["sub"]
    now = _now_iso()
    with get_conn() as conn:
        # Check admin once per unique resource
        checked_resources: set[str] = set()
        for g in body.grants:
            if g.resource not in checked_resources:
                if not has_admin_on_resource(conn, caller_sub, g.resource):
                    if g.subject != caller_sub:
                        raise HTTPException(
                            status_code=403,
                            detail={"error": "forbidden", "message": "Caller is not the resource owner or admin"},
                        )
                checked_resources.add(g.resource)
            conn.execute(
                """INSERT INTO grants (subject, resource, action, effect, granted_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(subject, resource, action, effect) DO NOTHING""",
                (g.subject, g.resource, g.action, g.effect, caller_sub, now),
            )
            write_audit(conn, "grant_created", g.subject, g.resource, g.action, caller_sub)
    return {"granted": len(body.grants)}


# ── POST /grants ──────────────────────────────────────────────────────────────

@router.post("/grants", response_model=GrantResponse)
def create_grant(body: GrantRequest, caller: dict = Depends(require_auth)):
    caller_sub = caller["sub"]
    with get_conn() as conn:
        # Caller must have admin on the resource (or be granting to themselves as owner bootstrap)
        if not has_admin_on_resource(conn, caller_sub, body.resource):
            # Allow if caller is granting themselves (owner bootstrap from other services)
            if body.subject != caller_sub:
                raise HTTPException(
                    status_code=403,
                    detail={"error": "forbidden", "message": "Caller is not the resource owner or admin"},
                )

        now = _now_iso()
        conn.execute(
            """INSERT INTO grants (subject, resource, action, effect, granted_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(subject, resource, action, effect) DO NOTHING""",
            (body.subject, body.resource, body.action, body.effect, caller_sub, now),
        )
        row = conn.execute(
            "SELECT * FROM grants WHERE subject=? AND resource=? AND action=? AND effect=?",
            (body.subject, body.resource, body.action, body.effect),
        ).fetchone()
        write_audit(conn, "grant_created", body.subject, body.resource, body.action, caller_sub)

    return GrantResponse(
        subject=row["subject"],
        resource=row["resource"],
        action=row["action"],
        effect=row["effect"],
        granted_by=row["granted_by"],
        created_at=row["created_at"],
    )


# ── DELETE /grants ────────────────────────────────────────────────────────────

@router.delete("/grants")
def revoke_grant(body: RevokeRequest, caller: dict = Depends(require_auth)):
    caller_sub = caller["sub"]
    with get_conn() as conn:
        if not has_admin_on_resource(conn, caller_sub, body.resource):
            if body.subject != caller_sub:
                raise HTTPException(
                    status_code=403,
                    detail={"error": "forbidden", "message": "Caller is not the resource owner or admin"},
                )

        if body.subject == "*":
            # Bulk delete: remove all grants for this resource
            params = [body.resource]
            sql = "DELETE FROM grants WHERE resource=?"
            if body.action:
                sql += " AND action=?"
                params.append(body.action)
            if body.effect:
                sql += " AND effect=?"
                params.append(body.effect)
            conn.execute(sql, params)
            write_audit(conn, "grant_deleted", "*", body.resource, body.action or "*", caller_sub)
        else:
            # Exact delete
            if not body.action or not body.effect:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "validation_error", "message": "action and effect are required for non-wildcard delete"},
                )
            conn.execute(
                "DELETE FROM grants WHERE subject=? AND resource=? AND action=? AND effect=?",
                (body.subject, body.resource, body.action, body.effect),
            )
            write_audit(conn, "grant_deleted", body.subject, body.resource, body.action, caller_sub)

    return Response(status_code=204)


# ── GET /check ────────────────────────────────────────────────────────────────

@router.get("/check", response_model=CheckResponse)
def check(
    subject: str = Query(...),
    resource: str = Query(...),
    action: str = Query(...),
    caller: dict = Depends(require_auth),
):
    allowed = check_permission(subject, resource, action)
    if not allowed:
        with get_conn() as conn:
            write_audit(conn, "check_denied", subject, resource, action, caller["sub"])
    return CheckResponse(allowed=allowed)


# ── GET /grants ───────────────────────────────────────────────────────────────

@router.get("/grants")
def list_grants(resource: str = Query(...), caller: dict = Depends(require_auth)):
    caller_sub = caller["sub"]
    with get_conn() as conn:
        if not has_admin_on_resource(conn, caller_sub, resource):
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "message": "Caller is not the resource owner or admin"},
            )
        rows = conn.execute(
            "SELECT subject, resource, action, effect, granted_by, created_at FROM grants WHERE resource=?",
            (resource,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── GET /audit ────────────────────────────────────────────────────────────────

@router.get("/audit")
def audit_log(resource: str = Query(...), caller: dict = Depends(require_auth)):
    caller_sub = caller["sub"]
    with get_conn() as conn:
        if not has_admin_on_resource(conn, caller_sub, resource):
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "message": "Caller is not the resource owner or admin"},
            )
        rows = conn.execute(
            "SELECT event, subject, resource, action, actor, created_at FROM audit_log WHERE resource=? ORDER BY id DESC",
            (resource,),
        ).fetchall()
    return [dict(r) for r in rows]
