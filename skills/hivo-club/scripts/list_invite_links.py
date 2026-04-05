#!/usr/bin/env python3
"""
List all invite links for a Club.

Usage:
    python scripts/list_invite_links.py <club_id>
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
        print("Usage: python scripts/list_invite_links.py <club_id>", file=sys.stderr)
        sys.exit(1)

    club_id = sys.argv[1]
    config = _load_config()
    url = f"{config['club_url'].rstrip('/')}/clubs/{club_id}/invite-links"
    token = _get_token()

    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        links = data.get("invite_links", [])
        if not links:
            print("No invite links.")
            return
        for link in links:
            line = f"  token={link['token']}  role={link['role']}  uses={link['use_count']}"
            if link.get("max_uses"):
                line += f"/{link['max_uses']}"
            if link.get("expires_at"):
                line += f"  expires={link['expires_at']}"
            print(line)
    except urllib.error.HTTPError as exc:
        err = json.loads(exc.read())
        print(f"Error {exc.code}: {err.get('error')} — {err.get('message')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
