---
name: hivo-drop
description: Manage files in the Hivo Drop storage service. Use this skill whenever the user asks to upload, download, delete, list, or share files via hivo-drop. Also use it when the user needs a public URL for a file, wants to make a file public or private, or asks about storage quota.
---

# Hivo Drop

> **CRITICAL — Before starting, MUST use the Read tool to read `../hivo-identity/SKILL.md`.**
> All hivo-drop operations require a valid Bearer token. The token is obtained automatically via the hivo-identity skill's `get_token.py` — but hivo-identity must be registered first (`assets/identity.json` and `assets/private_key.pem` must exist). If not registered yet, complete registration following `../hivo-identity/SKILL.md` before proceeding here.

This skill manages files in the Hivo Drop storage service. It bundles five scripts:

| Script | Purpose |
|--------|---------|
| `scripts/upload.py` | Upload a local file to hivo-drop |
| `scripts/download.py` | Download a file from hivo-drop |
| `scripts/delete.py` | Delete a file from hivo-drop |
| `scripts/list.py` | List files (optionally filtered by path prefix) |
| `scripts/share.py` | Set file visibility to public or private |

Files in `assets/`:

| File | Committed? | Description |
|------|-----------|-------------|
| `assets/config.json` | Yes | `drop_url` — read by all scripts on every run as the service endpoint |

---

## Requirements

All scripts require Python 3.12+. No additional packages needed beyond what hivo-identity already requires (`cryptography`).

---

## Workflow

### Upload a file

```bash
python scripts/upload.py <local_file> <remote_path>
# Overwrite an existing file:
python scripts/upload.py <local_file> <remote_path> --overwrite
```

`<remote_path>` is the logical path inside hivo-drop (e.g. `docs/report.html`). Content-Type is detected from the file extension automatically.

**Example:**
```bash
python scripts/upload.py report.html docs/report.html
python scripts/upload.py data.json results/data.json --overwrite
```

Output: `Uploaded: docs/report.html (4312 bytes)`

---

### Download a file

```bash
# Save to a local file:
python scripts/download.py <remote_path> <local_file>
# Print to stdout (useful for text files):
python scripts/download.py <remote_path>
```

**Example:**
```bash
python scripts/download.py docs/report.html report.html
python scripts/download.py notes/memo.txt
```

---

### Delete a file

```bash
python scripts/delete.py <remote_path>
```

**Example:**
```bash
python scripts/delete.py docs/old-report.html
```

Output: `Deleted: docs/old-report.html`

---

### List files

```bash
# List all files:
python scripts/list.py
# Filter by prefix:
python scripts/list.py docs/
```

Output: table with path, content_type, visibility, size.

---

### Share a file (set visibility)

```bash
# Make public — prints the public URL:
python scripts/share.py <remote_path> public
# Make private — revokes the share link:
python scripts/share.py <remote_path> private
```

**Example:**
```bash
python scripts/share.py docs/report.html public
# → Public URL: https://drop.hivo.ink/p/a1b2c3d4-...

python scripts/share.py docs/report.html private
# → File is now private. Share link revoked.
```

Public files are accessible to anyone via the printed URL — no authentication required.

---

## Limits

| Limit | Value |
|-------|-------|
| Max file size | 1 MB |
| Max files per agent | 100 |

Exceeding either limit returns an error. Delete old files to free quota.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `hivo-identity skill not found` | hivo-identity not installed alongside hivo-drop | Install skills together; they must be sibling directories |
| `assets/identity.json not found` | hivo-identity not registered | Follow `../hivo-identity/SKILL.md` to register first |
| `Error 401: invalid_token` | Token expired or wrong audience | `get_token.py` will refresh automatically; if it persists, re-check hivo-identity registration |
| `Error 409: conflict` | File already exists | Add `--overwrite` flag to upload.py |
| `Error 413: file_too_large` | File exceeds 1 MB | Split or compress the file before uploading |
| `Error 403: quota_exceeded` | 100-file limit reached | Run `list.py` and delete unused files with `delete.py` |
| `Error 404: not_found` | File doesn't exist or is private | Check path with `list.py`; ensure file was uploaded |

---

## When helping the user

### Exact commands — use these verbatim

```bash
# Upload
python scripts/upload.py <local_file> <remote_path>
python scripts/upload.py <local_file> <remote_path> --overwrite

# Download
python scripts/download.py <remote_path> <local_file>
python scripts/download.py <remote_path>           # stdout

# Delete
python scripts/delete.py <remote_path>

# List
python scripts/list.py
python scripts/list.py <prefix>

# Share (make public — prints URL)
python scripts/share.py <remote_path> public
# Unshare (make private)
python scripts/share.py <remote_path> private
```

> **Do not invent flags or paths. The commands above are the only correct forms.**

### Decision tree

- **Prerequisite check**: Before any operation, verify `../hivo-identity/assets/identity.json` exists. If not, stop and follow hivo-identity registration flow.
- **Upload**: ask for local file path and desired remote path. Then run `upload.py`. If 409, ask whether to overwrite.
- **Share / get public URL**: run `upload.py` first if needed, then `share.py <path> public`. Show the returned URL to the user.
- **List files**: run `list.py` (with optional prefix) to show what files exist and their visibility.
- **Delete**: confirm the path with the user, then run `delete.py`.
- **Download**: ask where to save, then run `download.py <remote_path> <local_file>`.
- **Token**: you do not need to manage tokens — all scripts call `../hivo-identity/scripts/get_token.py hivo-drop` automatically.
