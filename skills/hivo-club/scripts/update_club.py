#!/usr/bin/env python3
"""
Update a Club's name or description.

Usage:
    python scripts/update_club.py <club_id> [--name NAME] [--description DESC]

At least one field must be provided. Only owner or admin can update.

Example:
    python scripts/update_club.py club_a1b2... --name "New Name" --description "New desc"
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
        print("Usage: python scripts/update_club.py <club_id> [--name NAME] [--description DESC]", file=sys.stderr)
        sys.exit(1)

    club_id = sys.argv[1]
    body = {}
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--name" and i + 1 < len(args):
            body["name"] = args[i + 1]; i += 2
        elif args[i] == "--description" and i + 1 < len(args):
            body["description"] = args[i + 1]; i += 2
        else:
            print(f"Unknown argument: {args[i]}", file=sys.stderr)
            sys.exit(1)

    if not body:
        print("Usage: python scripts/update_club.py <club_id> [--name NAME] [--description DESC]", file=sys.stderr)
        sys.exit(1)

    config = _load_config()
    url = f"{config['club_url'].rstrip('/')}/clubs/{club_id}"
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
        print(f"Club:        {result['club_id']}")
        print(f"Name:        {result['name']}")
        print(f"Description: {result.get('description') or '(none)'}")
        print(f"Owner:       {result['owner_sub']}")
        print(f"Updated:     {result['updated_at']}")
    except urllib.error.HTTPError as exc:
        err = json.loads(exc.read())
        print(f"Error {exc.code}: {err.get('error')} — {err.get('message')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
