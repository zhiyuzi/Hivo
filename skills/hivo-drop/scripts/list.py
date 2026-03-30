#!/usr/bin/env python3
"""
List files in hivo-drop.

Usage:
    python scripts/list.py [prefix]

    prefix   optional path prefix to filter results (e.g. docs/)

The script obtains a Bearer token automatically via the hivo-identity skill.

Example:
    python scripts/list.py
    python scripts/list.py docs/
"""

import json
import subprocess
import sys
import urllib.error
import urllib.parse
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


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def main() -> None:
    prefix = sys.argv[1] if len(sys.argv) >= 2 else ""

    config = _load_config()
    drop_url = config["drop_url"].rstrip("/")
    token = _get_token()

    params = urllib.parse.urlencode({"prefix": prefix}) if prefix else ""
    url = f"{drop_url}/list"
    if params:
        url += f"?{params}"

    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

    try:
        with urllib.request.urlopen(req) as resp:
            files = json.loads(resp.read())
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

    if not files:
        print("No files found.")
        return

    col_path = max(len(f["path"]) for f in files)
    col_ct = max(len(f["content_type"]) for f in files)
    col_path = max(col_path, 4)
    col_ct = max(col_ct, 12)

    header = f"{'PATH':<{col_path}}  {'CONTENT-TYPE':<{col_ct}}  {'VISIBILITY':<10}  SIZE"
    print(header)
    print("-" * len(header))
    for f in files:
        print(
            f"{f['path']:<{col_path}}  {f['content_type']:<{col_ct}}  "
            f"{f['visibility']:<10}  {_fmt_size(f['size'])}"
        )
    print(f"\n{len(files)} file(s)")


if __name__ == "__main__":
    main()
