<div align="center">

<h1>Hivo</h1>

<p>Open infrastructure for AI agents.</p>

[English](README.md) · [中文](README.zh.md)

[![Python](https://img.shields.io/badge/python-3.12+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![Self-hostable](https://img.shields.io/badge/self--hostable-yes-6366f1)]()

</div>

---

Hivo is a growing suite of open microservices that give AI agents persistent identity, file storage, and other capabilities — without passwords, without hardcoded credentials, and without unnecessary complexity.

To use any service, clone this repository and load the corresponding skill. Each skill's `SKILL.md` contains everything needed to get started.

```
skills/hivo-identity/   ← identity registration & token management
skills/hivo-club/       ← team/org management, membership & roles
skills/hivo-drop/       ← file upload, download, and public sharing
```

Each service also returns a plain-text ecosystem index at `GET /` pointing back here.

---

## Deploying

### Services

| Service | What it does |
|---------|-------------|
| **hivo-identity** | Ed25519 keypair registration, JWT issuance & refresh, JWKS publishing, OIDC Discovery, profile management |
| **hivo-acl** | Cross-service access control — manages subject/resource/action grants with DENY-priority evaluation |
| **hivo-club** | Team/org management — membership, roles, invite links, club & member profile management |
| **hivo-drop** | File upload/download, metadata control, public sharing via Cloudflare R2 |

Public endpoints: `https://id.hivo.ink` · `https://acl.hivo.ink` · `https://club.hivo.ink` · `https://drop.hivo.ink`

### Running Locally

```bash
# hivo-identity — runs on :8001
cd servers/hivo-identity
uv sync
uv run uvicorn app.main:app --reload --port 8001

# hivo-acl — runs on :8004
cd servers/hivo-acl
uv sync
uv run uvicorn app.main:app --reload --port 8004

# hivo-club — runs on :8003 (requires hivo-identity for token verification)
cd servers/hivo-club
uv sync
uv run uvicorn app.main:app --reload --port 8003

# hivo-drop — runs on :8002 (requires Cloudflare R2, see .env.example)
cd servers/hivo-drop
uv sync
uv run uvicorn app.main:app --reload --port 8002
```

### Self-Hosting

All services are fully self-hostable. Clone the repo and update the following:

**1. hivo-identity** — set your own issuer domain:
```
# servers/hivo-identity/.env
ISSUER_URL=https://id.your-domain.com
DATABASE_PATH=./data/identity.db
```

**2. hivo-acl** — point it at your identity instance:
```
# servers/hivo-acl/.env
TRUSTED_ISSUERS=https://id.your-domain.com
DATABASE_PATH=./data/acl.db
```

**3. hivo-club** — point it at your identity instance:
```
# servers/hivo-club/.env
TRUSTED_ISSUERS=https://id.your-domain.com
DATABASE_PATH=./data/club.db
```

**4. hivo-drop** — point it at your identity instance:
```
# servers/hivo-drop/.env
TRUSTED_ISSUERS=https://id.your-domain.com
DATABASE_PATH=./data/drop.db
R2_ENDPOINT=https://xxx.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=xxx
R2_SECRET_ACCESS_KEY=xxx
R2_BUCKET_NAME=your-bucket
```

**5. Skills** — update each skill's `assets/config.json` with your service URLs.

Agents on different deployments are automatically isolated by their `iss` (issuer) claim — no further configuration needed.

## What's Built

- [x] **hivo-identity** (microservice) — registration, JWT issuance & refresh, `/me`, `PATCH /me`, JWKS, OIDC Discovery, 28 tests
- [x] **hivo-identity** (skill) — `register.py`, `get_token.py`, `me.py`, `update_me.py`, token caching & auto-refresh, evals
- [x] **hivo-acl** (microservice) — grants CRUD, `/check` with DENY-priority, wildcard matching, club member expansion, audit log, 22 tests
- [x] **hivo-club** (microservice) — club CRUD, membership management, invite links, club & member profile updates, 52 tests
- [x] **hivo-club** (skill) — `create.py`, `info.py`, `members.py`, `invite.py`, `join.py`, `leave.py`, `my_clubs.py`, `update_club.py`, `update_me.py`, `list_invite_links.py`, `revoke_invite_link.py`, evals
- [x] **hivo-drop** (microservice) — upload, download, delete, list, visibility control, public sharing, ACL integration, strict CSP, 26 tests
- [x] **hivo-drop** (skill) — `upload.py`, `download.py`, `delete.py`, `list.py`, `share.py`, evals

## Roadmap

Hivo Mail · Hivo IM · Hivo Wallet · Hivo Wiki · Hivo Table · Hivo Scribe · Hivo Pipeline · Hivo Observability · Hivo Registry · Hivo Notification · Hivo Calendar · Hivo Task · Hivo Event · Hivo Sandbox · Hivo DB · Hivo KV · Hivo Map

## Documentation

- [`docs/spec.md`](docs/spec.md) — full technical specification
- [`DEPLOY.md`](DEPLOY.md) — production deployment guide (nginx, systemd, certbot, Cloudflare)
- [`skills/hivo-identity/SKILL.md`](skills/hivo-identity/SKILL.md) — identity skill reference
- [`skills/hivo-club/SKILL.md`](skills/hivo-club/SKILL.md) — club skill reference
- [`skills/hivo-drop/SKILL.md`](skills/hivo-drop/SKILL.md) — drop skill reference

## License

[MIT](LICENSE)
