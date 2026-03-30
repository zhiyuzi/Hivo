#!/usr/bin/env python3
"""
Register this agent with hivo-identity.

Usage:
    python scripts/register.py <handle> [issuer_url]

    handle      e.g. myagent@acme  (name@namespace, letters/digits/hyphens, 2-32 chars each)
    issuer_url  default: read from assets/config.json, fallback https://id.hivo.ink

Writes to assets/:
    private_key.pem   Ed25519 private key  — KEEP SECRET, never commit
    public_key.jwk    Corresponding public key (JWK)   — gitignored, regenerable
    identity.json     Registration result: sub, handle, iss  — gitignored, per-deployment
"""

import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ASSETS_DIR = Path(__file__).parent.parent / "assets"
_FALLBACK_ISSUER = "https://id.hivo.ink"


def _default_issuer() -> str:
    config_path = ASSETS_DIR / "config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8")).get("issuer_url", _FALLBACK_ISSUER)
        except Exception:
            pass
    return _FALLBACK_ISSUER


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _generate_keypair():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.generate()


def _private_key_to_pem(private_key) -> bytes:
    from cryptography.hazmat.primitives import serialization
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _public_key_to_jwk(private_key) -> dict:
    from cryptography.hazmat.primitives import serialization
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {"kty": "OKP", "crv": "Ed25519", "x": _b64url(pub_bytes)}


def _post(url: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            err = json.loads(raw)
        except Exception:
            err = {"error": "http_error", "message": raw.decode(errors="replace")}
        print(f"HTTP {exc.code} — {err.get('error')}: {err.get('message')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    handle = sys.argv[1]
    issuer_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else _default_issuer()

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Generate keypair ──────────────────────────────────────────────
    print("Generating Ed25519 keypair...", file=sys.stderr)
    private_key = _generate_keypair()
    jwk_pub = _public_key_to_jwk(private_key)

    # ── Step 2: POST /register ────────────────────────────────────────────────
    print(f"Registering '{handle}' with {issuer_url} ...", file=sys.stderr)
    resp = _post(f"{issuer_url}/register", {"handle": handle, "jwk_pub": jwk_pub})
    challenge: str = resp["challenge"]
    print("Received challenge.", file=sys.stderr)

    # ── Step 3: Sign challenge ────────────────────────────────────────────────
    sig_bytes = private_key.sign(challenge.encode())
    signature = _b64url(sig_bytes)

    # ── Step 4: POST /register/verify ─────────────────────────────────────────
    print("Verifying signature...", file=sys.stderr)
    resp = _post(
        f"{issuer_url}/register/verify",
        {"challenge": challenge, "signature": signature},
    )
    sub: str = resp["sub"]
    print(f"Registration successful.  sub={sub}", file=sys.stderr)

    # ── Step 5: Write assets ──────────────────────────────────────────────────
    (ASSETS_DIR / "private_key.pem").write_bytes(_private_key_to_pem(private_key))
    (ASSETS_DIR / "public_key.jwk").write_text(json.dumps(jwk_pub, indent=2) + "\n")
    (ASSETS_DIR / "identity.json").write_text(
        json.dumps({"sub": sub, "handle": handle, "iss": issuer_url}, indent=2) + "\n"
    )

    print(f"\nCredentials written to {ASSETS_DIR}/", file=sys.stderr)
    print("  private_key.pem  ← keep secret, never commit", file=sys.stderr)
    print("  public_key.jwk   ← safe to commit", file=sys.stderr)
    print("  identity.json    ← safe to commit", file=sys.stderr)


if __name__ == "__main__":
    main()
