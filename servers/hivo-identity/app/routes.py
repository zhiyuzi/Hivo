import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from .config import settings
from .db import get_conn
from .keys import get_all_public_keys, get_current_signing_key
from .models import (
    MeResponse, RefreshRequest, RegisterRequest, RegisterResponse,
    TokenRequest, TokenResponse, VerifyRequest, VerifyResponse,
)
from .tokens import (
    create_access_token, create_refresh_token,
    verify_access_token, verify_agent_assertion, verify_challenge_signature,
)

router = APIRouter()

_INDEX_MD = """\
Hey, agent.

I'm hivo-identity, part of Hivo. I handle registration and token management for you.

For the full skill suite and everything else Hivo offers: https://hivo.ink
"""



def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _err(status: int, error: str, message: str):
    return JSONResponse(status_code=status, content={"error": error, "message": message})


def _get_bearer(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"error": "invalid_token", "message": "Missing Bearer token"})
    return authorization[7:]


def _require_auth(authorization: Optional[str] = Header(default=None)) -> dict:
    token = _get_bearer(authorization)
    pub_keys = get_all_public_keys()
    try:
        payload = verify_access_token(token, pub_keys)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "message": "Token is invalid or expired"},
        )
    return payload


# ── Public pages ──────────────────────────────────────────────────────────────

@router.get("/", response_class=PlainTextResponse)
def index():
    return PlainTextResponse(
        _INDEX_MD,
        media_type="text/markdown; charset=utf-8",
    )


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/.well-known/openid-configuration")
def oidc_config():
    base = settings.issuer_url
    return {
        "issuer": base,
        "token_endpoint": f"{base}/token",
        "jwks_uri": f"{base}/jwks.json",
        "userinfo_endpoint": f"{base}/me",
        "registration_endpoint": f"{base}/register",
        "token_endpoint_auth_methods_supported": ["private_key_jwt"],
        "token_endpoint_auth_signing_alg_values_supported": ["EdDSA"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["EdDSA"],
    }


@router.get("/jwks.json")
def jwks():
    keys = get_all_public_keys()
    return {"keys": keys}


# ── Registration ──────────────────────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(req: RegisterRequest):
    now_iso = _now_iso()
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM pending_registrations WHERE expires_at <= ?", (now_iso,)
        )
        existing = conn.execute(
            "SELECT sub FROM subjects WHERE handle = ?", (req.handle,)
        ).fetchone()
        if existing:
            return _err(409, "handle_taken", f"Handle {req.handle} is already registered")

        challenge = secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        conn.execute(
            "INSERT INTO pending_registrations (challenge, handle, jwk_pub, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (challenge, req.handle, json.dumps(req.jwk_pub), expires_at, _now_iso()),
        )

    return RegisterResponse(challenge=challenge)


@router.post("/register/verify", response_model=VerifyResponse, status_code=201)
def register_verify(req: VerifyRequest):
    now_iso = _now_iso()
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM pending_registrations WHERE expires_at <= ?", (now_iso,)
        )
        row = conn.execute(
            "SELECT handle, jwk_pub, expires_at FROM pending_registrations WHERE challenge = ?",
            (req.challenge,),
        ).fetchone()
        if not row:
            return _err(400, "challenge_expired", "Challenge not found or has expired")

        jwk_pub = json.loads(row["jwk_pub"])
        if not verify_challenge_signature(req.challenge, req.signature, jwk_pub):
            return _err(400, "challenge_failed", "Signature verification failed")

        # Check handle still available (race condition guard)
        existing = conn.execute(
            "SELECT sub FROM subjects WHERE handle = ?", (row["handle"],)
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM pending_registrations WHERE challenge = ?", (req.challenge,))
            return _err(409, "handle_taken", f"Handle {row['handle']} is already registered")

        import uuid_utils
        sub = "agt_" + str(uuid_utils.uuid7())

        conn.execute(
            "INSERT INTO subjects (sub, handle, jwk_pub, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (sub, row["handle"], row["jwk_pub"], now_iso, now_iso),
        )
        conn.execute("DELETE FROM pending_registrations WHERE challenge = ?", (req.challenge,))

    return VerifyResponse(sub=sub, handle=row["handle"])


# ── Token ─────────────────────────────────────────────────────────────────────

@router.post("/token", response_model=TokenResponse)
def token(req: TokenRequest):
    try:
        _, payload, _, _ = _decode_assertion_unverified(req.assertion)
    except Exception:
        return _err(400, "invalid_assertion", "JWT assertion is malformed")

    sub = payload.get("sub") or payload.get("iss")
    if not sub:
        return _err(400, "invalid_assertion", "Assertion missing sub claim")

    with get_conn() as conn:
        agent = conn.execute(
            "SELECT sub, handle, jwk_pub, status FROM subjects WHERE sub = ?", (sub,)
        ).fetchone()

    if not agent:
        return _err(400, "invalid_assertion", "Unknown agent sub")
    if agent["status"] != "active":
        return _err(400, "invalid_assertion", "Agent account is disabled")

    jwk_pub = json.loads(agent["jwk_pub"])
    try:
        verify_agent_assertion(req.assertion, jwk_pub)
    except ValueError:
        return _err(400, "invalid_assertion", "Assertion signature is invalid or expired")

    kid, private_key, _ = get_current_signing_key()
    access_token = create_access_token(agent["sub"], agent["handle"], kid, private_key, req.audience)
    raw_refresh, refresh_hash = create_refresh_token()

    expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    with get_conn() as conn:
        conn.execute("DELETE FROM refresh_tokens WHERE sub = ?", (agent["sub"],))
        conn.execute(
            "INSERT INTO refresh_tokens (token_hash, sub, audience, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (refresh_hash, agent["sub"], req.audience, expires_at, _now_iso()),
        )

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/token/refresh", response_model=TokenResponse)
def token_refresh(req: RefreshRequest):
    token_hash = hashlib.sha256(req.refresh_token.encode()).hexdigest()
    now_iso = _now_iso()

    with get_conn() as conn:
        conn.execute(
            "DELETE FROM refresh_tokens WHERE expires_at <= ?", (now_iso,)
        )
        row = conn.execute(
            "SELECT sub, audience FROM refresh_tokens WHERE token_hash = ?", (token_hash,)
        ).fetchone()
        if not row:
            return _err(401, "invalid_token", "Refresh token is invalid or expired")

        agent = conn.execute(
            "SELECT sub, handle, status FROM subjects WHERE sub = ?", (row["sub"],)
        ).fetchone()
        if not agent or agent["status"] != "active":
            return _err(401, "invalid_token", "Agent not found or disabled")

        kid, private_key, _ = get_current_signing_key()
        access_token = create_access_token(agent["sub"], agent["handle"], kid, private_key, row["audience"])
        raw_refresh, new_hash = create_refresh_token()
        expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

        conn.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))
        conn.execute(
            "INSERT INTO refresh_tokens (token_hash, sub, audience, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_hash, agent["sub"], row["audience"], expires_at, _now_iso()),
        )

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=MeResponse)
def me(payload: dict = Depends(_require_auth)):
    sub = payload["sub"]
    with get_conn() as conn:
        agent = conn.execute(
            "SELECT sub, handle, email, display_name, status, created_at FROM subjects WHERE sub = ?",
            (sub,),
        ).fetchone()
    if not agent:
        raise HTTPException(status_code=401, detail={"error": "invalid_token", "message": "Agent not found"})
    return MeResponse(
        sub=agent["sub"],
        handle=agent["handle"],
        email=agent["email"],
        display_name=agent["display_name"],
        status=agent["status"],
        created_at=agent["created_at"],
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _decode_assertion_unverified(token: str):
    from .tokens import _jwt_decode_unverified
    return _jwt_decode_unverified(token)
