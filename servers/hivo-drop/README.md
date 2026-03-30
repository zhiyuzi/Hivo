# agent-drop

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

File storage and sharing service for the Hivo ecosystem. Agents upload files (text, HTML, binary) and optionally share them publicly via a stable URL.

**Live:** https://drop.hivo.ink

---

## Features

- Upload any file format — text types render inline, binary downloads as attachment
- Private by default; make public with one PATCH call, get a stable share link
- Bearer token auth (EdDSA JWT) issued by a trusted agent-identity service
- Strict CSP on all public HTML — no script execution, safe for agent-generated content
- SQLite metadata + Cloudflare R2 (S3-compatible) object storage

## API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | — | Service index (Markdown) |
| GET | `/README.md` | — | Full documentation |
| PUT | `/files/{path}` | Bearer | Upload file |
| GET | `/files/{path}` | Bearer | Download file |
| HEAD | `/files/{path}` | Bearer | Check file existence |
| DELETE | `/files/{path}` | Bearer | Delete file |
| PATCH | `/files/{path}` | Bearer | Update visibility |
| GET | `/list?prefix=` | Bearer | List files |
| GET | `/p/{share_id}` | — | Public access |
| GET | `/health` | — | Health check |

Full API docs: `GET /README.md` on the running service.

## Quick Start

```bash
# Get a Bearer token (requires agent-identity-credential skill)
TOKEN=$(python scripts/get_token.py agent-drop)

# Upload a file
curl -X PUT https://drop.hivo.ink/files/hello.html \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: text/html" \
  --data-binary "<h1>Hello from agent</h1>"

# Make it public
curl -X PATCH https://drop.hivo.ink/files/hello.html \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"visibility": "public"}'
# Response includes share_id → https://drop.hivo.ink/p/{share_id}
```

## Deployment

```bash
cp .env.example .env
# Edit .env with your R2 credentials and trusted issuer

uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Development

```bash
uv sync --group dev
uv run pytest
```

## Limits

| Item | Default |
|------|---------|
| Max file size | 1 MB |
| Max files per agent | 100 |

## License

MIT
