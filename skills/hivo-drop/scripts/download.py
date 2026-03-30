#!/usr/bin/env python3
"""
Download a file from hivo-drop.

Usage:
    python scripts/download.py <remote_path> [local_file]

    remote_path   logical path inside hivo-drop (e.g. docs/report.html)
    local_file    where to save the file; if omitted, content is written to stdout

The script obtains a Bearer token automatically via the hivo-identity skill.

Example:
    python scripts/download.py docs/report.html report.html
    python scripts/download.py notes/memo.txt
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
        print("Usage: python scripts/download.py <remote_path> [local_file]", file=sys.stderr)
        sys.exit(1)

    remote_path = sys.argv[1].lstrip("/")
    local_file = Path(sys.argv[2]) if len(sys.argv) >= 3 else None

    config = _load_config()
    drop_url = config["drop_url"].rstrip("/")
    token = _get_token()

    url = f"{drop_url}/files/{remote_path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
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

    if local_file:
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_bytes(data)
        print(f"Saved: {local_file}")
    else:
        sys.stdout.buffer.write(data)


if __name__ == "__main__":
    main()
