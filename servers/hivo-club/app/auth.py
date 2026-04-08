"""JWT verification for hivo-club (EdDSA/Ed25519, fetches JWKS from hivo-identity)."""
import base64
import json
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import Header, HTTPException

from .config import settings

_jwks_cache: list[dict] = []


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def get_jwks() -> list[dict]:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    keys = []
    for issuer in settings.trusted_issuers.split(","):
        issuer = issuer.strip()
        try:
            resp = httpx.get(f"{issuer}/jwks.json", timeout=5)
            resp.raise_for_status()
            keys.extend(resp.json().get("keys", []))
        except Exception:
            pass
    _jwks_cache = keys
    return keys


def verify_token(token: str) -> dict:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature

    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid_token")

    try:
        header = json.loads(_b64url_decode(parts[0]))
        payload = json.loads(_b64url_decode(parts[1]))
        signing_input = f"{parts[0]}.{parts[1]}".encode()
        sig = _b64url_decode(parts[2])
    except Exception:
        raise ValueError("invalid_token")

    kid = header.get("kid")
    pub_keys = get_jwks()
    matched = None
    for jwk in pub_keys:
        if kid and jwk.get("kid") == kid:
            matched = jwk
            break
    if not matched and pub_keys:
        matched = pub_keys[0]
    if not matched:
        _jwks_cache.clear()
        pub_keys = get_jwks()
        for jwk in pub_keys:
            if kid and jwk.get("kid") == kid:
                matched = jwk
                break
        if not matched and pub_keys:
            matched = pub_keys[0]
    if not matched:
        raise ValueError("invalid_token")

    try:
        x_bytes = _b64url_decode(matched["x"])
        pub = Ed25519PublicKey.from_public_bytes(x_bytes)
        pub.verify(sig, signing_input)
    except (InvalidSignature, Exception):
        raise ValueError("invalid_token")

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if payload.get("exp", 0) < now_ts:
        raise ValueError("invalid_token")

    trusted = settings.trusted_issuers_list()
    if payload.get("iss") not in trusted:
        raise ValueError("invalid_token")

    aud = payload.get("aud")
    if aud and aud != "hivo-club":
        raise ValueError("invalid_token")

    return payload


def require_auth(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "message": "Missing Bearer token"},
        )
    token = authorization[7:]
    try:
        payload = verify_token(token)
        payload["_token"] = token
        return payload
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "message": "Token is invalid or expired"},
        )
