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
# Agent Identity Service

Role: issuer / authentication service
Issuer: {issuer}
Docs: GET /README.md

## Core Routes
- GET /README.md — Full documentation (read this first)
- POST /register — Register agent (public key enrollment)
- POST /register/verify — Complete registration (challenge verification)
- POST /token — Exchange private_key_jwt for access_token
- POST /token/refresh — Refresh access_token
- GET /me — Current identity info
- GET /.well-known/openid-configuration — OIDC Discovery metadata
- GET /jwks.json — Signing public keys
- GET /health — Health check

## Identity Model
- Primary key: sub
- Human-readable name: handle
- Token format: JWT (EdDSA)
"""

_README_MD = """\
# Agent Identity Service — Full Documentation

## Registration

1. Generate an Ed25519 key pair locally.
2. POST /register with your handle and public key (JWK format).
3. Receive a `challenge` nonce in the response.
4. Sign the challenge bytes with your private key (Ed25519, raw signature).
5. POST /register/verify with the challenge and base64url-encoded signature.
6. Receive your `sub` (permanent identifier).

### POST /register

Request body (JSON):
```json
{
  "handle": "myagent@acme",
  "jwk_pub": {"kty": "OKP", "crv": "Ed25519", "x": "<base64url>"}
}
```

Response:
```json
{"challenge": "<nonce>"}
```

### POST /register/verify

Request body (JSON):
```json
{
  "challenge": "<nonce from /register>",
  "signature": "<base64url Ed25519 signature of challenge bytes>"
}
```

Response:
```json
{"sub": "agt_01...", "handle": "myagent@acme"}
```

## Token Exchange

### POST /token

Exchange a `private_key_jwt` assertion for an access_token.

The assertion is a JWT signed with your Ed25519 private key:
```json
{
  "iss": "<your sub>",
  "sub": "<your sub>",
  "aud": "https://id.agentinfra.cloud/token",
  "iat": <now>,
  "exp": <now + 300>
}
```

Request body (JSON):
```json
{
  "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
  "assertion": "<signed JWT>"
}
```

Response:
```json
{
  "access_token": "<JWT>",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "<opaque token>"
}
```

### POST /token/refresh

Request body (JSON):
```json
{"refresh_token": "<token>"}
```

Response: same as /token.

## Identity Info

### GET /me

Requires: `Authorization: Bearer <access_token>`

Response:
```json
{
  "sub": "agt_01...",
  "handle": "myagent@acme",
  "status": "active",
  "created_at": "2024-01-01T00:00:00+00:00"
}
```

## Public Keys

### GET /jwks.json

Returns the service's Ed25519 signing public keys in JWKS format.
Downstream services use this to verify access tokens without calling back to agent-identity.

Response:
```json
{
  "keys": [
    {"kty": "OKP", "crv": "Ed25519", "x": "<base64url>", "kid": "<uuid>"}
  ]
}
```

### GET /.well-known/openid-configuration

OIDC Discovery metadata (minimal subset). Use this to discover endpoint URLs programmatically.

Response:
```json
{
  "issuer": "<ISSUER_URL>",
  "token_endpoint": "<ISSUER_URL>/token",
  "jwks_uri": "<ISSUER_URL>/jwks.json",
  "userinfo_endpoint": "<ISSUER_URL>/me",
  "registration_endpoint": "<ISSUER_URL>/register",
  "token_endpoint_auth_methods_supported": ["private_key_jwt"],
  "token_endpoint_auth_signing_alg_values_supported": ["EdDSA"]
}
```

## Health

### GET /health

Returns `200 OK` when the service is running.

Response:
```json
{"status": "ok"}
```

## Error Format

```json
{"error": "error_code", "message": "Human readable message"}
```

Common error codes:

| Status | error | Scenario |
|--------|-------|----------|
| 400 | `invalid_assertion` | /token JWT assertion malformed or signature invalid |
| 400 | `challenge_expired` | /register/verify challenge not found or expired |
| 400 | `challenge_failed` | /register/verify signature verification failed |
| 401 | `invalid_token` | /me or /token/refresh token invalid or expired |
| 409 | `handle_taken` | /register handle already registered |
| 422 | `validation_error` | Request parameters invalid (bad handle format, etc.) |
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
        _INDEX_MD.format(issuer=settings.issuer_url),
        media_type="text/markdown; charset=utf-8",
    )


@router.get("/README.md", response_class=PlainTextResponse)
def readme():
    return PlainTextResponse(_README_MD, media_type="text/markdown; charset=utf-8")


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
