#!/usr/bin/env python3
"""
Show the current agent's identity information from hivo-identity.

Usage:
    python scripts/me.py

Reads assets/identity.json to find the issuer, obtains a Bearer token via
get_token.py (using the token cache), then calls GET /me and prints the result.
"""

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ASSETS_DIR = Path(__file__).parent.parent / "assets"


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


def _get_token(audience: str) -> str:
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "get_token.py"), audience],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr, end="")
        sys.exit(1)
    return result.stdout.strip()


def main() -> None:
    identity = _load_identity()
    iss: str = identity["iss"]

    token = _get_token("hivo-identity")

    req = urllib.request.Request(
        f"{iss}/me",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
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

    print(f"sub:          {data['sub']}")
    print(f"handle:       {data['handle']}")
    print(f"status:       {data['status']}")
    print(f"created_at:   {data['created_at']}")


if __name__ == "__main__":
    main()
