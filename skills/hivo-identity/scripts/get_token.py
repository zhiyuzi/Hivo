#!/usr/bin/env python3
"""
Obtain an access token for this agent from hivo-identity.

Usage:
    python scripts/get_token.py <audience>

    audience  the service this token is intended for (e.g. the target service name)

Token caching:
  Access tokens (valid 1 hour) and refresh tokens (valid 30 days) are cached in
  assets/token_cache.json.  On each run the script tries, in order:
    1. Return a cached access token that still has >60s remaining.
    2. Use the cached refresh token to get a new pair from POST /token/refresh.
    3. Fall back to the full private_key_jwt assertion flow via POST /token.
  Steps 2 and 3 update the cache automatically.

Example:
    TOKEN=$(python scripts/get_token.py <audience>)
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
CACHE_FILE = ASSETS_DIR / "token_cache.json"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _jwt_exp(token: str) -> int:
    """Return the exp claim from a JWT payload, or 0 on any error."""
    try:
        part = token.split(".")[1]
        padding = 4 - len(part) % 4
        if padding != 4:
            part += "=" * padding
        return json.loads(base64.urlsafe_b64decode(part)).get("exp", 0)
    except Exception:
        return 0


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


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_cache(cache: dict) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def _build_assertion(sub: str, aud: str, private_key) -> str:
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


def _try_refresh(iss: str, audience: str, cache: dict) -> tuple[str | None, str | None]:
    """Attempt to refresh via cached refresh token.
    Returns (access_token, refresh_token) on success, (None, None) on failure."""
    refresh_token = cache.get(audience, {}).get("refresh_token")
    if not refresh_token:
        return None, None
    try:
        body = json.dumps({"refresh_token": refresh_token}).encode()
        req = urllib.request.Request(
            f"{iss}/token/refresh",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        return data.get("access_token"), data.get("refresh_token")
    except Exception:
        # Refresh token expired or invalid — fall through to assertion flow
        return None, None


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/get_token.py <audience>", file=sys.stderr)
        sys.exit(1)
    audience = sys.argv[1]

    cache = _load_cache()
    now = int(time.time())

    # 1. Cached access token still valid (60s buffer avoids serving a token that expires in transit)
    cached_access = cache.get(audience, {}).get("access_token")
    if cached_access and _jwt_exp(cached_access) > now + 60:
        print(cached_access)
        return

    identity = _load_identity()
    sub: str = identity["sub"]
    iss: str = identity["iss"]

    # 2. Refresh token
    new_access, new_refresh = _try_refresh(iss, audience, cache)
    if new_access:
        cache[audience] = {"access_token": new_access, "refresh_token": new_refresh}
        _save_cache(cache)
        print(new_access)
        return

    # 3. Full assertion flow
    private_key = _load_private_key()
    assertion = _build_assertion(sub, f"{iss}/token", private_key)
    resp = _post(
        f"{iss}/token",
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
            "audience": audience,
        },
    )

    access_token = resp["access_token"]
    cache[audience] = {
        "access_token": access_token,
        "refresh_token": resp.get("refresh_token"),
    }
    _save_cache(cache)
    print(access_token)


if __name__ == "__main__":
    main()
