"""JWT creation and verification for hivo-identity."""
import base64
import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.exceptions import InvalidSignature

from .config import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _jwt_encode(header: dict, payload: dict, private_key: Ed25519PrivateKey) -> str:
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{h}.{p}".encode()
    sig = private_key.sign(signing_input)
    return f"{h}.{p}.{_b64url_encode(sig)}"


def _jwt_decode_unverified(token: str) -> tuple[dict, dict, bytes, bytes]:
    """Returns (header, payload, signing_input_bytes, sig_bytes)."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    header = json.loads(_b64url_decode(parts[0]))
    payload = json.loads(_b64url_decode(parts[1]))
    signing_input = f"{parts[0]}.{parts[1]}".encode()
    sig = _b64url_decode(parts[2])
    return header, payload, signing_input, sig


def _public_key_from_jwk(jwk: dict) -> Ed25519PublicKey:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    x_bytes = _b64url_decode(jwk["x"])
    from cryptography.hazmat.primitives.serialization import load_der_public_key
    # Reconstruct from raw bytes
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    import cryptography.hazmat.primitives.asymmetric.ed25519 as ed25519_mod
    return ed25519_mod.Ed25519PublicKey.from_public_bytes(x_bytes)


def create_access_token(
    sub: str, handle: str, kid: str, private_key: Ed25519PrivateKey, audience: str
) -> str:
    now = _now()
    exp = now + timedelta(hours=1)
    payload = {
        "iss": settings.issuer_url,
        "sub": sub,
        "aud": audience,
        "handle": handle,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    header = {"alg": "EdDSA", "typ": "JWT", "kid": kid}
    return _jwt_encode(header, payload, private_key)


def create_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash)."""
    raw = secrets.token_urlsafe(48)
    h = hashlib.sha256(raw.encode()).hexdigest()
    return raw, h


def verify_access_token(token: str, public_keys: list[dict]) -> dict:
    """Verify access token signature and expiry. Returns payload."""
    try:
        header, payload, signing_input, sig = _jwt_decode_unverified(token)
    except Exception:
        raise ValueError("invalid_token")

    kid = header.get("kid")
    matched_key = None
    for jwk in public_keys:
        if kid and jwk.get("kid") == kid:
            matched_key = jwk
            break
    if not matched_key and public_keys:
        matched_key = public_keys[0]
    if not matched_key:
        raise ValueError("invalid_token")

    try:
        pub = _public_key_from_jwk(matched_key)
        pub.verify(sig, signing_input)
    except InvalidSignature:
        raise ValueError("invalid_token")

    now_ts = int(_now().timestamp())
    if payload.get("exp", 0) < now_ts:
        raise ValueError("invalid_token")

    if payload.get("iss") != settings.issuer_url:
        raise ValueError("invalid_token")

    return payload


def verify_agent_assertion(token: str, jwk_pub: dict) -> dict:
    """Verify a private_key_jwt assertion signed by the agent. Returns payload."""
    try:
        header, payload, signing_input, sig = _jwt_decode_unverified(token)
    except Exception:
        raise ValueError("invalid_assertion")

    try:
        pub = _public_key_from_jwk(jwk_pub)
        pub.verify(sig, signing_input)
    except (InvalidSignature, Exception):
        raise ValueError("invalid_assertion")

    now_ts = int(_now().timestamp())
    if payload.get("exp", 0) < now_ts:
        raise ValueError("invalid_assertion")

    return payload


def verify_challenge_signature(challenge: str, signature_b64: str, jwk_pub: dict) -> bool:
    """Verify that signature is a valid Ed25519 sig of challenge bytes using jwk_pub."""
    try:
        sig = _b64url_decode(signature_b64)
        pub = _public_key_from_jwk(jwk_pub)
        pub.verify(sig, challenge.encode())
        return True
    except (InvalidSignature, Exception):
        return False
