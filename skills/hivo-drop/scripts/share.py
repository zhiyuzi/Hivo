#!/usr/bin/env python3
"""
Set file visibility in hivo-drop (public or private).

Usage:
    python scripts/share.py <remote_path> public|private

    remote_path   logical path inside hivo-drop (e.g. docs/report.html)
    public        make the file publicly accessible, prints the share URL
    private       revoke public access

The script obtains a Bearer token automatically via the hivo-identity skill.

Example:
    python scripts/share.py docs/report.html public
    # → Public URL: https://drop.hivo.ink/p/a1b2c3d4-...

    python scripts/share.py docs/report.html private
    # → File is now private. Share link revoked.
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
        return {"drop_url": "https://drop.hivo.ink"}
    return json.loads(config_path.read_text())


def _get_token() -> str:
    if not IDENTITY_GET_TOKEN.exists():
        print(
            "Error: hivo-identity skill not found.\n"
            f"Expected: {IDENTITY_GET_TOKEN}\n"
            "Install hivo-identity skill alongside hivo-drop (sibling directories).",
            file=sys.stderr,
        )
        sys.exit(1)
    result = subprocess.run(
        [sys.executable, str(IDENTITY_GET_TOKEN), "hivo-drop"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, end="", file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout.strip()


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[2] not in ("public", "private"):
        print("Usage: python scripts/share.py <remote_path> public|private", file=sys.stderr)
        sys.exit(1)

    remote_path = sys.argv[1].lstrip("/")
    visibility = sys.argv[2]

    config = _load_config()
    drop_url = config["drop_url"].rstrip("/")
    token = _get_token()

    url = f"{drop_url}/files/{remote_path}"
    body = json.dumps({"visibility": visibility}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="PATCH",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            err = json.loads(raw)
        except Exception:
            err = {"error": "http_error", "message": raw.decode(errors="replace")}
        print(f"Error {exc.code}: {err.get('error')} — {err.get('message')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)

    if visibility == "public":
        share_id = result.get("share_id")
        if share_id:
            print(f"Public URL: {drop_url}/p/{share_id}")
        else:
            print("File is public but no share_id returned (unexpected).", file=sys.stderr)
            sys.exit(1)
    else:
        print("File is now private. Share link revoked.")


if __name__ == "__main__":
    main()
