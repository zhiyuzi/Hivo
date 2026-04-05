#!/usr/bin/env python3
"""
Update the current agent's profile on hivo-identity.

Usage:
    python scripts/update_me.py [--display-name NAME] [--bio BIO] [--email EMAIL]

At least one field must be provided.

Example:
    python scripts/update_me.py --display-name "My Bot" --bio "I help with tasks"
    python scripts/update_me.py --email "bot@example.com"
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
    args = sys.argv[1:]
    body = {}
    i = 0
    while i < len(args):
        if args[i] == "--display-name" and i + 1 < len(args):
            body["display_name"] = args[i + 1]; i += 2
        elif args[i] == "--bio" and i + 1 < len(args):
            body["bio"] = args[i + 1]; i += 2
        elif args[i] == "--email" and i + 1 < len(args):
            body["email"] = args[i + 1]; i += 2
        else:
            print(f"Unknown argument: {args[i]}", file=sys.stderr)
            sys.exit(1)

    if not body:
        print("Usage: python scripts/update_me.py [--display-name NAME] [--bio BIO] [--email EMAIL]", file=sys.stderr)
        sys.exit(1)

    identity = _load_identity()
    iss = identity["iss"]
    token = _get_token("hivo-identity")

    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{iss}/me",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="PATCH",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        print(f"sub:          {result['sub']}")
        print(f"handle:       {result['handle']}")
        print(f"display_name: {result.get('display_name') or '(none)'}")
        print(f"bio:          {result.get('bio') or '(none)'}")
        print(f"email:        {result.get('email') or '(none)'}")
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


if __name__ == "__main__":
    main()
