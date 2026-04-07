<div align="center">

<h1>Hivo</h1>

<p>Open infrastructure for AI agents.</p>

[English](README.md) · [中文](README.zh.md)

[![Python](https://img.shields.io/badge/python-3.12+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![Go](https://img.shields.io/badge/go-1.22+-00ADD8?logo=go&logoColor=white)](https://go.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![Self-hostable](https://img.shields.io/badge/self--hostable-yes-6366f1)]()

</div>

---

Hivo is a growing suite of open microservices that give AI agents persistent identity, file storage, team collaboration, and more — without passwords, without hardcoded credentials, and without unnecessary complexity.

## Quick Start

```bash
npm install -g @hivoai/cli
npx skills add zhiyuzi/Hivo -y
```

That's it. You now have three skills: **identity**, **club**, **drop**. Each skill's `SKILL.md` describes the full CLI usage.

```bash
# Register an identity
hivo identity register

# Upload a file and share it
hivo drop upload report.html docs/report.html
hivo drop share docs/report.html public

# Create a team
hivo club create "My Team"
```

## For AI Agents

If you are an AI agent helping a user, follow these steps:

1. Run `npm install -g @hivoai/cli` to install the CLI.
2. Run `npx skills add zhiyuzi/Hivo -y` to install all Hivo skills into the current project.
3. Read the installed `SKILL.md` files for each skill — they contain the exact commands and decision trees you need.

Do **not** use the `-g` flag on `npx skills add`. Each agent should install skills in its own working directory, because `.hivo/identity.json` is stored locally as the agent's identity marker.

## Services

| Service | What it does |
|---------|-------------|
| **hivo-identity** | Ed25519 keypair registration, JWT issuance & refresh, JWKS, OIDC Discovery, profile management |
| **hivo-acl** | Cross-service access control — subject/resource/action grants with DENY-priority evaluation |
| **hivo-club** | Team/org management — membership, roles, invite links, club & member profiles |
| **hivo-drop** | File upload/download, metadata, public sharing via Cloudflare R2 |

Public endpoints: `https://id.hivo.ink` · `https://acl.hivo.ink` · `https://club.hivo.ink` · `https://drop.hivo.ink`

## Self-Hosting

All services are fully self-hostable. See [`DEPLOY.md`](DEPLOY.md) for the complete production deployment guide (nginx, systemd, certbot, Cloudflare).

## What's Built

- [x] **hivo-identity** (microservice) — registration, JWT issuance & refresh, `/me`, `PATCH /me`, JWKS, OIDC Discovery, 28 tests
- [x] **hivo-identity** (skill) — `hivo identity register|token|me|update`, token caching & auto-refresh, evals
- [x] **hivo-acl** (microservice) — grants CRUD, batch grants, `/check` with DENY-priority, wildcard matching, club member expansion, audit log, 22 tests
- [x] **hivo-club** (microservice) — club CRUD, membership management, invite links, club & member profile updates, 52 tests
- [x] **hivo-club** (skill) — `hivo club create|info|members|invite|join|leave|my|update|update-me|update-member|invite-links|revoke-link|delete`, evals
- [x] **hivo-drop** (microservice) — upload, download, delete, list, visibility control, public sharing, ACL integration, strict CSP, 26 tests
- [x] **hivo-drop** (skill) — `hivo drop upload|download|delete|list|share`, evals
- [x] **CLI** (`@hivoai/cli`) — Go/Cobra unified CLI wrapping all services, npm distribution, cross-platform binaries

## Roadmap

Mail · IM · Wallet · Wiki · Table · Scribe · Pipeline · Observability · Registry · Notification · Calendar · Task · Event · Sandbox · DB · KV · Map

## Documentation

- [`docs/spec.md`](docs/spec.md) — full technical specification
- [`DEPLOY.md`](DEPLOY.md) — production deployment guide (nginx, systemd, certbot, Cloudflare)
- [`skills/hivo-identity/SKILL.md`](skills/hivo-identity/SKILL.md) — identity skill reference
- [`skills/hivo-club/SKILL.md`](skills/hivo-club/SKILL.md) — club skill reference
- [`skills/hivo-drop/SKILL.md`](skills/hivo-drop/SKILL.md) — drop skill reference

## License

[MIT](LICENSE)
