#!/usr/bin/env python3
"""
Delete a file from hivo-drop.

Usage:
    python scripts/delete.py <remote_path>

    remote_path   logical path inside hivo-drop (e.g. docs/report.html)

The script obtains a Bearer token automatically via the hivo-identity skill.

Example:
    python scripts/delete.py docs/old-report.html
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
    if len(sys.argv) < 2:
        print("Usage: python scripts/delete.py <remote_path>", file=sys.stderr)
        sys.exit(1)

    remote_path = sys.argv[1].lstrip("/")

    config = _load_config()
    drop_url = config["drop_url"].rstrip("/")
    token = _get_token()

    url = f"{drop_url}/files/{remote_path}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="DELETE",
    )

    try:
        with urllib.request.urlopen(req):
            pass
        print(f"Deleted: {remote_path}")
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


if __name__ == "__main__":
    main()
