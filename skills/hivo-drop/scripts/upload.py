#!/usr/bin/env python3
"""
Upload a local file to hivo-drop.

Usage:
    python scripts/upload.py <local_file> <remote_path> [--overwrite]

    local_file    path to the file on disk
    remote_path   logical path inside hivo-drop (e.g. docs/report.html)
    --overwrite   replace an existing file at that path

The script obtains a Bearer token automatically via the hivo-identity skill.

Example:
    python scripts/upload.py report.html docs/report.html
    python scripts/upload.py data.json results/data.json --overwrite
"""

import json
import mimetypes
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
    args = sys.argv[1:]
    overwrite = "--overwrite" in args
    args = [a for a in args if a != "--overwrite"]

    if len(args) < 2:
        print("Usage: python scripts/upload.py <local_file> <remote_path> [--overwrite]", file=sys.stderr)
        sys.exit(1)

    local_file = Path(args[0])
    remote_path = args[1].lstrip("/")

    if not local_file.exists():
        print(f"Error: local file not found: {local_file}", file=sys.stderr)
        sys.exit(1)

    data = local_file.read_bytes()
    content_type, _ = mimetypes.guess_type(str(local_file))
    if not content_type:
        content_type = "application/octet-stream"

    config = _load_config()
    drop_url = config["drop_url"].rstrip("/")
    token = _get_token()

    url = f"{drop_url}/files/{remote_path}"
    if overwrite:
        url += "?overwrite=true"

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
        },
        method="PUT",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        print(f"Uploaded: {result['path']} ({result['size']} bytes)")
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
