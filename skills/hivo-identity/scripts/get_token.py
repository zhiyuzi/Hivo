#!/usr/bin/env python3
"""
Obtain an access token for this agent from agent-identity.

Usage:
    python scripts/get_token.py <audience>

    audience  the service this token is intended for, e.g. "agent-drop"

Reads assets/identity.json and assets/private_key.pem (written by register.py),
then exchanges a signed JWT assertion for an access token and prints it to stdout.

The token is valid for 1 hour.  Re-run this script to get a fresh one.

Example:
    TOKEN=$(python scripts/get_token.py agent-drop)
    curl -H "Authorization: Bearer $TOKEN" <service_url>
"""

import base64
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ASSETS_DIR = Path(__file__).parent.parent / "assets"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _load_identity() -> dict:
    path = ASSETS_DIR / "identity.json"
    if not path.exists():
        print(
            "Error: assets/identity.json not found.\n"
            "Run register.py first to set up credentials.",
            file=sys.stderr,
        )
        sys.exit(1)
    return json.loads(path.read_text())


def _load_private_key():
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    path = ASSETS_DIR / "private_key.pem"
    if not path.exists():
        print(
            "Error: assets/private_key.pem not found.\n"
            "Run register.py first to set up credentials.",
            file=sys.stderr,
        )
        sys.exit(1)
    return load_pem_private_key(path.read_bytes(), password=None)


def _build_assertion(sub: str, aud: str, private_key) -> str:
    """Build a signed JWT assertion for the token endpoint."""
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "EdDSA", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(
        json.dumps(
            {"iss": sub, "sub": sub, "aud": aud, "iat": now, "exp": now + 300},
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    sig = _b64url(private_key.sign(signing_input))
    return f"{header}.{payload}.{sig}"


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
        print("Usage: python scripts/get_token.py <audience>", file=sys.stderr)
        sys.exit(1)
    audience = sys.argv[1]

    identity = _load_identity()
    sub: str = identity["sub"]
    iss: str = identity["iss"]

    private_key = _load_private_key()

    aud = f"{iss}/token"
    assertion = _build_assertion(sub, aud, private_key)

    resp = _post(
        f"{iss}/token",
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
            "audience": audience,
        },
    )

    print(resp["access_token"])


if __name__ == "__main__":
    main()
