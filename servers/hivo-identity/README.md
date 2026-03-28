# agent-identity

[![Python](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![uv](https://img.shields.io/badge/uv-managed-DE5FE9?logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![EdDSA](https://img.shields.io/badge/signing-EdDSA%2FEd25519-4A90D9)](https://en.wikipedia.org/wiki/EdDSA)
[![License](https://img.shields.io/badge/license-MIT-22C55E)](LICENSE)

> Agent identity registration and JWT issuance service.

**Public cloud instance**: `https://id.agentinfra.cloud` &nbsp;|&nbsp; [中文](README.zh.md)

---

## What it does

agent-identity is the **trust root** of the agentinfra ecosystem. It:

- Issues each agent a stable, immutable identity (`sub`)
- Registers agents via public key enrollment (Ed25519) — no passwords
- Signs JWT access tokens for downstream services (e.g. agent-drop) to verify

Downstream services fetch the public key from `/jwks.json` and verify tokens locally — no runtime callbacks to agent-identity required.

---

## Self-hosting

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

### 1. Clone and install

```bash
git clone <repo-url> agent-identity
cd agent-identity
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```ini
ISSUER_URL=https://id.yourdomain.com   # Written into JWT iss claim
DATABASE_PATH=./data/identity.db       # SQLite database path
```

> **Important:** `ISSUER_URL` is the trust domain identifier embedded in every issued token. Downstream services use it to distinguish deployments. Do not change it after going live.

### 3. Run (development)

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000` for the service documentation.

### 4. Run (production)

Use Gunicorn with UvicornWorker:

```bash
uv run gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:8000
```

Put nginx or Caddy in front for TLS termination.

**systemd unit** (`/etc/systemd/system/agent-identity.service`):

```ini
[Unit]
Description=agent-identity service
After=network.target

[Service]
WorkingDirectory=/opt/agent-identity
EnvironmentFile=/opt/agent-identity/.env
ExecStart=/opt/agent-identity/.venv/bin/gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 127.0.0.1:8000
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```

### 5. Data directory

The SQLite database is created automatically at startup. Ensure the data directory is writable and backed up in production.

---

## API reference

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/` | Service overview (Markdown) | None |
| GET | `/README.md` | Full API docs (Markdown) | None |
| POST | `/register` | Submit handle + public key, receive challenge | None |
| POST | `/register/verify` | Submit signed challenge, complete registration | None |
| POST | `/token` | Exchange `private_key_jwt` for access token | None (self-attested) |
| POST | `/token/refresh` | Refresh access token | refresh_token |
| GET | `/me` | Current identity info | Bearer |
| GET | `/.well-known/openid-configuration` | OIDC Discovery metadata | None |
| GET | `/jwks.json` | Service signing public keys | None |
| GET | `/health` | Health check | None |

Full request/response schemas: `GET /README.md` on a running instance.

---

## Registration flow

```
1. Generate an Ed25519 key pair locally
2. POST /register  →  submit handle + public key (JWK)  →  receive challenge
3. Sign the challenge bytes with your private key (raw Ed25519 signature)
4. POST /register/verify  →  submit challenge + base64url signature  →  receive sub
```

The challenge is valid for 10 minutes and is single-use.

---

## Token flow

After registration, to obtain tokens:

```
1. Build a private_key_jwt  (JWT signed with your key, iss=sub, aud=<ISSUER_URL>/token, exp=now+5m)
2. POST /token  →  access_token (1 hour) + refresh_token (30 days)
3. access_token expired  →  POST /token/refresh
4. refresh_token expired  →  repeat step 1–2
```

The access token is a standard JWT (EdDSA). Downstream services verify it with the public key from `/jwks.json` — no calls back to agent-identity.

---

## Development

```bash
# Install with dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Run tests (verbose)
uv run pytest -v
```

---

## Private deployment notes

- Set `ISSUER_URL` in `.env` to your own domain
- Configure downstream services with `TRUSTED_ISSUERS=<your ISSUER_URL>`
- Different `iss` values mean different trust domains — data is fully isolated
