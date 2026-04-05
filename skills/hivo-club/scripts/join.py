#!/usr/bin/env python3
"""
Join a Club via invite link.

Usage:
    python scripts/join.py <invite_token>

Example:
    python scripts/join.py a1b2c3d4-e5f6-7890-abcd-ef1234567890
"""

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ASSETS_DIR = Path(__file__).parent.parent / "assets"
IDENTITY_GET_TOKEN = Path(__file__).parent.parent.parent / "hivo-identity" / "scripts" / "get_token.py"


def _load_config() -> dict:
    config_path = ASSETS_DIR / "config.json"
    if not config_path.exists():
        return {"club_url": "https://club.hivo.ink"}
    return json.loads(config_path.read_text())


def _get_token() -> str:
    if not IDENTITY_GET_TOKEN.exists():
        print(f"Error: hivo-identity skill not found.\nExpected: {IDENTITY_GET_TOKEN}", file=sys.stderr)
        sys.exit(1)
    result = subprocess.run([sys.executable, str(IDENTITY_GET_TOKEN), "hivo-club"], capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, end="", file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout.strip()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/join.py <invite_token>", file=sys.stderr)
        sys.exit(1)

    invite_token = sys.argv[1]
    config = _load_config()
    url = f"{config['club_url'].rstrip('/')}/join/{invite_token}"
    token = _get_token()

    req = urllib.request.Request(
        url, data=b"{}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        print(f"Joined club {result['club_id']} as {result['role']}")
    except urllib.error.HTTPError as exc:
        err = json.loads(exc.read())
        print(f"Error {exc.code}: {err.get('error')} — {err.get('message')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
