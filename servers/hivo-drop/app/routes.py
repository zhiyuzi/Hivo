import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from .auth import verify_token
from .config import settings
from .db import get_conn
from .models import FileMetadata, ListEntry, PatchRequest
from .storage import delete_object, download_object, make_r2_key, upload_object

router = APIRouter()

# ── Static content ─────────────────────────────────────────────────────────────

_INDEX_MD = """\
Hey, agent.

I'm hivo-drop, part of Hivo. I handle file upload, storage, and sharing for you.

For the full skill suite and everything else Hivo offers: https://hivo.ink
"""


_RENDERABLE_TYPES = {
    "text/plain",
    "text/markdown",
    "text/html",
    "text/css",
    "text/javascript",
    "application/json",
    "application/xml",
    "application/yaml",
    "application/toml",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _err(status: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, "message": message})


def _require_auth(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "message": "Missing Bearer token"},
        )
    token = authorization[7:]
    try:
        return verify_token(token)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "message": "Token is invalid or expired"},
        )


def _validate_path(path: str) -> str:
    path = path.strip("/")
    if not path or ".." in path.split("/"):
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_error", "message": "Invalid file path"},
        )
    return path


# ── Public pages ───────────────────────────────────────────────────────────────

@router.get("/", response_class=PlainTextResponse)
def index():
    return PlainTextResponse(_INDEX_MD, media_type="text/markdown; charset=utf-8")


@router.get("/health")
def health():
    return {"status": "ok"}


# ── Public share ───────────────────────────────────────────────────────────────

@router.get("/p/{share_id}")
def public_get(share_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT r2_key, content_type, size FROM files WHERE share_id = ? AND visibility = 'public'",
            (share_id,),
        ).fetchone()
    if not row:
        return _err(404, "not_found", "File not found")

    try:
        data = download_object(row["r2_key"])
    except FileNotFoundError:
        return _err(404, "not_found", "File not found")

    ct = row["content_type"].split(";")[0].strip()
    renderable = ct in _RENDERABLE_TYPES

    headers = {
        "Content-Security-Policy": (
            "default-src 'none'; style-src 'unsafe-inline'; "
            "img-src https: data:; font-src https:;"
        ),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }
    if renderable:
        headers["Content-Disposition"] = "inline"
    else:
        headers["Content-Disposition"] = "attachment"

    return Response(content=data, media_type=row["content_type"], headers=headers)


# ── Authenticated file operations ──────────────────────────────────────────────

@router.put("/files/{path:path}")
async def upload_file(
    path: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    overwrite: bool = False,
):
    payload = _require_auth(authorization)
    path = _validate_path(path)
    iss, sub = payload["iss"], payload["sub"]

    # Size check
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_file_size:
        return _err(413, "file_too_large", f"File exceeds {settings.max_file_size} bytes")

    content_type = request.headers.get("content-type", "application/octet-stream")
    data = await request.body()

    if len(data) > settings.max_file_size:
        return _err(413, "file_too_large", f"File exceeds {settings.max_file_size} bytes")

    sha256 = hashlib.sha256(data).hexdigest()
    r2_key = make_r2_key(iss, sub, path)
    now = _now_iso()

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM files WHERE owner_iss = ? AND owner_sub = ? AND path = ?",
            (iss, sub, path),
        ).fetchone()

        if existing and not overwrite:
            return _err(409, "conflict", f"File '{path}' already exists. Use overwrite=true to replace.")

        if not existing:
            # Quota check
            count = conn.execute(
                "SELECT COUNT(*) FROM files WHERE owner_iss = ? AND owner_sub = ?",
                (iss, sub),
            ).fetchone()[0]
            if count >= settings.max_files_per_agent:
                return _err(403, "quota_exceeded", f"File count limit reached ({settings.max_files_per_agent})")

        upload_object(r2_key, data, content_type)

        if existing:
            conn.execute(
                """UPDATE files SET content_type = ?, size = ?, sha256 = ?, updated_at = ?
                   WHERE owner_iss = ? AND owner_sub = ? AND path = ?""",
                (content_type, len(data), sha256, now, iss, sub, path),
            )
        else:
            conn.execute(
                """INSERT INTO files
                   (owner_sub, owner_iss, path, r2_key, content_type, size, sha256, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sub, iss, path, r2_key, content_type, len(data), sha256, now, now),
            )

    status = 200 if existing else 201
    return JSONResponse(
        status_code=status,
        content={"path": path, "size": len(data), "sha256": sha256},
    )


@router.get("/files/{path:path}")
def get_file(
    path: str,
    authorization: Optional[str] = Header(default=None),
):
    payload = _require_auth(authorization)
    path = _validate_path(path)
    iss, sub = payload["iss"], payload["sub"]

    with get_conn() as conn:
        row = conn.execute(
            "SELECT r2_key, content_type FROM files WHERE owner_iss = ? AND owner_sub = ? AND path = ?",
            (iss, sub, path),
        ).fetchone()

    if not row:
        return _err(404, "not_found", "File not found")

    try:
        data = download_object(row["r2_key"])
    except FileNotFoundError:
        return _err(404, "not_found", "File not found")

    return Response(content=data, media_type=row["content_type"])


@router.head("/files/{path:path}")
def head_file(
    path: str,
    authorization: Optional[str] = Header(default=None),
):
    payload = _require_auth(authorization)
    path = _validate_path(path)
    iss, sub = payload["iss"], payload["sub"]

    with get_conn() as conn:
        row = conn.execute(
            "SELECT content_type, size, visibility, share_id FROM files WHERE owner_iss = ? AND owner_sub = ? AND path = ?",
            (iss, sub, path),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404)

    headers = {
        "Content-Type": row["content_type"],
        "Content-Length": str(row["size"]),
        "X-Visibility": row["visibility"],
    }
    if row["share_id"]:
        headers["X-Share-Id"] = row["share_id"]

    return Response(status_code=200, headers=headers)


@router.delete("/files/{path:path}")
def delete_file(
    path: str,
    authorization: Optional[str] = Header(default=None),
):
    payload = _require_auth(authorization)
    path = _validate_path(path)
    iss, sub = payload["iss"], payload["sub"]

    with get_conn() as conn:
        row = conn.execute(
            "SELECT r2_key FROM files WHERE owner_iss = ? AND owner_sub = ? AND path = ?",
            (iss, sub, path),
        ).fetchone()
        if not row:
            return _err(404, "not_found", "File not found")
        delete_object(row["r2_key"])
        conn.execute(
            "DELETE FROM files WHERE owner_iss = ? AND owner_sub = ? AND path = ?",
            (iss, sub, path),
        )

    return Response(status_code=204)


@router.patch("/files/{path:path}")
def patch_file(
    path: str,
    req: PatchRequest,
    authorization: Optional[str] = Header(default=None),
):
    payload = _require_auth(authorization)
    path = _validate_path(path)
    iss, sub = payload["iss"], payload["sub"]

    if req.visibility not in ("public", "private", None):
        return _err(422, "validation_error", "visibility must be 'public' or 'private'")

    now = _now_iso()

    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, visibility, share_id, content_type, size, sha256, created_at FROM files "
            "WHERE owner_iss = ? AND owner_sub = ? AND path = ?",
            (iss, sub, path),
        ).fetchone()
        if not row:
            return _err(404, "not_found", "File not found")

        visibility = req.visibility if req.visibility is not None else row["visibility"]
        share_id = row["share_id"]

        if visibility == "public" and not share_id:
            share_id = str(uuid.uuid4())
        elif visibility == "private":
            share_id = None

        conn.execute(
            "UPDATE files SET visibility = ?, share_id = ?, updated_at = ? "
            "WHERE owner_iss = ? AND owner_sub = ? AND path = ?",
            (visibility, share_id, now, iss, sub, path),
        )

    return FileMetadata(
        path=path,
        content_type=row["content_type"],
        visibility=visibility,
        share_id=share_id,
        size=row["size"],
        sha256=row["sha256"],
        created_at=row["created_at"],
        updated_at=now,
    )


@router.get("/list")
def list_files(
    prefix: str = "",
    authorization: Optional[str] = Header(default=None),
):
    payload = _require_auth(authorization)
    iss, sub = payload["iss"], payload["sub"]

    with get_conn() as conn:
        if prefix:
            rows = conn.execute(
                "SELECT path, content_type, visibility, size, updated_at FROM files "
                "WHERE owner_iss = ? AND owner_sub = ? AND path LIKE ? "
                "ORDER BY path",
                (iss, sub, f"{prefix}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT path, content_type, visibility, size, updated_at FROM files "
                "WHERE owner_iss = ? AND owner_sub = ? ORDER BY path",
                (iss, sub),
            ).fetchall()

    return [
        ListEntry(
            path=r["path"],
            content_type=r["content_type"],
            visibility=r["visibility"],
            size=r["size"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]
