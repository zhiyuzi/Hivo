#!/usr/bin/env python3
"""
Invite a member or create an invite link for a Club.

Usage:
    python scripts/invite.py <club_id> --sub <agent_sub> [--role member|admin]
    python scripts/invite.py <club_id> --link [--role member|admin] [--max-uses N] [--expires DATETIME]

Examples:
    python scripts/invite.py club_abc123 --sub agt_friend --role member
    python scripts/invite.py club_abc123 --link --max-uses 5
    python scripts/invite.py club_abc123 --link --expires 2025-12-31T23:59:59Z
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
    args = sys.argv[1:]
    if len(args) < 2:
        print("Usage: python scripts/invite.py <club_id> --sub <sub> | --link [options]", file=sys.stderr)
        sys.exit(1)

    club_id = args[0]
    role = "member"
    sub = None
    link_mode = False
    max_uses = None
    expires_at = None

    i = 1
    while i < len(args):
        if args[i] == "--sub" and i + 1 < len(args):
            sub = args[i + 1]; i += 2
        elif args[i] == "--link":
            link_mode = True; i += 1
        elif args[i] == "--role" and i + 1 < len(args):
            role = args[i + 1]; i += 2
        elif args[i] == "--max-uses" and i + 1 < len(args):
            max_uses = int(args[i + 1]); i += 2
        elif args[i] == "--expires" and i + 1 < len(args):
            expires_at = args[i + 1]; i += 2
        else:
            i += 1

    if not sub and not link_mode:
        print("Error: specify --sub <agent_sub> or --link", file=sys.stderr)
        sys.exit(1)

    config = _load_config()
    url = f"{config['club_url'].rstrip('/')}/clubs/{club_id}/invite"
    token = _get_token()

    body: dict = {"role": role}
    if sub:
        body["sub"] = sub
    if max_uses is not None:
        body["max_uses"] = max_uses
    if expires_at:
        body["expires_at"] = expires_at

    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        if "token" in result:
            print(f"Invite link token: {result['token']}")
            if result.get("expires_at"):
                print(f"Expires: {result['expires_at']}")
            if result.get("max_uses"):
                print(f"Max uses: {result['max_uses']}")
        else:
            print(f"Invited: {result['sub']} as {result['role']}")
    except urllib.error.HTTPError as exc:
        err = json.loads(exc.read())
        print(f"Error {exc.code}: {err.get('error')} — {err.get('message')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
