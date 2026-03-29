"""JWT verification for agent-drop: validates tokens from trusted agent-identity issuers."""
import base64
import json
import threading
import time
from datetime import datetime, timezone

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from .config import settings

# ── JWKS cache ────────────────────────────────────────────────────────────────

_cache_lock = threading.Lock()
_jwks_cache: dict[str, tuple[list[dict], float]] = {}  # iss -> (keys, fetched_at)
_CACHE_TTL = 300  # 5 minutes


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _public_key_from_jwk(jwk: dict) -> Ed25519PublicKey:
    import cryptography.hazmat.primitives.asymmetric.ed25519 as ed25519_mod
    x_bytes = _b64url_decode(jwk["x"])
    return ed25519_mod.Ed25519PublicKey.from_public_bytes(x_bytes)


def _fetch_jwks(iss: str) -> list[dict]:
    """Fetch JWKS from issuer. Raises on failure."""
    url = f"{iss.rstrip('/')}/jwks.json"
    resp = httpx.get(url, timeout=5.0)
    resp.raise_for_status()
    return resp.json()["keys"]


def get_jwks(iss: str) -> list[dict]:
    """Return cached JWKS for issuer, refreshing if stale."""
    now = time.monotonic()
    with _cache_lock:
        if iss in _jwks_cache:
            keys, fetched_at = _jwks_cache[iss]
            if now - fetched_at < _CACHE_TTL:
                return keys
    keys = _fetch_jwks(iss)
    with _cache_lock:
        _jwks_cache[iss] = (keys, now)
    return keys


def invalidate_jwks_cache(iss: str | None = None) -> None:
    """For testing: clear cache for one issuer or all."""
    with _cache_lock:
        if iss:
            _jwks_cache.pop(iss, None)
        else:
            _jwks_cache.clear()


# ── JWT verification ──────────────────────────────────────────────────────────

def _jwt_decode_unverified(token: str) -> tuple[dict, dict, bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    header = json.loads(_b64url_decode(parts[0]))
    payload = json.loads(_b64url_decode(parts[1]))
    signing_input = f"{parts[0]}.{parts[1]}".encode()
    sig = _b64url_decode(parts[2])
    return header, payload, signing_input, sig


def verify_token(token: str) -> dict:
    """
    Verify a Bearer token from a trusted agent-identity issuer.
    Returns the JWT payload (sub, iss, handle, aud, exp).
    Raises ValueError with a short error code on any failure.
    """
    try:
        header, payload, signing_input, sig = _jwt_decode_unverified(token)
    except Exception:
        raise ValueError("invalid_token")

    iss = payload.get("iss", "")
    if iss not in settings.trusted_issuers_list():
        raise ValueError("invalid_token")

    aud = payload.get("aud", "")
    if aud != "agent-drop":
        raise ValueError("invalid_token")

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if payload.get("exp", 0) < now_ts:
        raise ValueError("invalid_token")

    kid = header.get("kid")
    try:
        keys = get_jwks(iss)
    except Exception:
        raise ValueError("invalid_token")

    matched = None
    for k in keys:
        if kid and k.get("kid") == kid:
            matched = k
            break
    if not matched and keys:
        matched = keys[0]
    if not matched:
        raise ValueError("invalid_token")

    try:
        pub = _public_key_from_jwk(matched)
        pub.verify(sig, signing_input)
    except (InvalidSignature, Exception):
        raise ValueError("invalid_token")

    return payload
