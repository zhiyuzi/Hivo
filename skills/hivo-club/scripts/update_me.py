#!/usr/bin/env python3
"""
Update your membership profile in a Club (display name, bio).

Usage:
    python scripts/update_me.py <club_id> [--display-name NAME] [--bio BIO]

At least one field must be provided.

Example:
    python scripts/update_me.py club_a1b2... --display-name "My Nickname" --bio "Hello everyone"
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
        print("Usage: python scripts/update_me.py <club_id> [--display-name NAME] [--bio BIO]", file=sys.stderr)
        sys.exit(1)

    club_id = sys.argv[1]
    body = {}
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--display-name" and i + 1 < len(args):
            body["display_name"] = args[i + 1]; i += 2
        elif args[i] == "--bio" and i + 1 < len(args):
            body["bio"] = args[i + 1]; i += 2
        else:
            print(f"Unknown argument: {args[i]}", file=sys.stderr)
            sys.exit(1)

    if not body:
        print("Usage: python scripts/update_me.py <club_id> [--display-name NAME] [--bio BIO]", file=sys.stderr)
        sys.exit(1)

    config = _load_config()
    url = f"{config['club_url'].rstrip('/')}/clubs/{club_id}/me"
    token = _get_token()

    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="PATCH",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        print(f"sub:          {result['sub']}")
        print(f"role:         {result['role']}")
        print(f"display_name: {result.get('display_name') or '(none)'}")
        print(f"bio:          {result.get('bio') or '(none)'}")
    except urllib.error.HTTPError as exc:
        err = json.loads(exc.read())
        print(f"Error {exc.code}: {err.get('error')} — {err.get('message')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
