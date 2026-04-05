#!/usr/bin/env python3
"""
Revoke an invite link for a Club.

Usage:
    python scripts/revoke_invite_link.py <club_id> <token>
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
    if len(sys.argv) < 3:
        print("Usage: python scripts/revoke_invite_link.py <club_id> <token>", file=sys.stderr)
        sys.exit(1)

    club_id = sys.argv[1]
    link_token = sys.argv[2]
    config = _load_config()
    url = f"{config['club_url'].rstrip('/')}/clubs/{club_id}/invite-links/{link_token}"
    token = _get_token()

    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="DELETE",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            pass
        print("Invite link revoked.")
    except urllib.error.HTTPError as exc:
        err = json.loads(exc.read())
        print(f"Error {exc.code}: {err.get('error')} — {err.get('message')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
