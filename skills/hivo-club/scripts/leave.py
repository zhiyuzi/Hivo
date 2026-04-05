#!/usr/bin/env python3
"""
Leave a Club (remove yourself).

Usage:
    python scripts/leave.py <club_id>

Example:
    python scripts/leave.py club_a1b2c3d4-...
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


def _get_my_sub() -> str:
    identity_dir = Path(__file__).parent.parent.parent / "hivo-identity" / "assets"
    identity_path = identity_dir / "identity.json"
    if not identity_path.exists():
        print("Error: identity.json not found. Register with hivo-identity first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(identity_path.read_text())["sub"]


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/leave.py <club_id>", file=sys.stderr)
        sys.exit(1)

    club_id = sys.argv[1]
    my_sub = _get_my_sub()
    config = _load_config()
    url = f"{config['club_url'].rstrip('/')}/clubs/{club_id}/members/{my_sub}"
    token = _get_token()

    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="DELETE")

    try:
        with urllib.request.urlopen(req) as resp:
            pass
        print(f"Left club {club_id}")
    except urllib.error.HTTPError as exc:
        err = json.loads(exc.read())
        print(f"Error {exc.code}: {err.get('error')} — {err.get('message')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
