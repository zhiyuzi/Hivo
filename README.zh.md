<div align="center">

<h1>Hivo</h1>

<p>面向 AI Agent 的开放基础设施。</p>

[English](README.md) · [中文](README.zh.md)

[![Python](https://img.shields.io/badge/python-3.12+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![可自托管](https://img.shields.io/badge/可自托管-yes-6366f1)]()

</div>

---

Hivo 是一套持续扩展的开放微服务，为 AI Agent 提供持久化身份、文件存储等能力——无需密码，无需硬编码凭据，无多余复杂度。

使用任意服务，克隆本仓库并加载对应的 Skill 即可。每个 Skill 目录下的 `SKILL.md` 包含完整使用说明。

```
skills/hivo-identity/   ← 身份注册与 Token 管理
skills/hivo-club/       ← 团队/组织管理、成员资格与角色
skills/hivo-drop/       ← 文件上传、下载与公开分享
```

每个服务端点的 `GET /` 也会返回纯文本生态索引，指向本仓库。

---

## 部署

### 服务列表

| 服务 | 功能 |
|------|------|
| **hivo-identity** | Ed25519 密钥对注册、JWT 签发与刷新、JWKS 公钥发布、OIDC Discovery、profile 管理 |
| **hivo-acl** | 跨服务统一访问控制——管理 subject/resource/action 授权关系，DENY 优先裁决 |
| **hivo-club** | 团队/组织管理——成员资格、角色、邀请链接、Club 与成员 profile 管理 |
| **hivo-drop** | 文件上传/下载、元数据管理、基于 Cloudflare R2 的公开分享 |

公有云端点：`https://id.hivo.ink` · `https://acl.hivo.ink` · `https://club.hivo.ink` · `https://drop.hivo.ink`

### 本地运行

```bash
# hivo-identity — 监听 :8001
cd servers/hivo-identity
uv sync
uv run uvicorn app.main:app --reload --port 8001

# hivo-acl — 监听 :8004
cd servers/hivo-acl
uv sync
uv run uvicorn app.main:app --reload --port 8004

# hivo-club — 监听 :8003（需要 hivo-identity 进行 token 验证）
cd servers/hivo-club
uv sync
uv run uvicorn app.main:app --reload --port 8003

# hivo-drop — 监听 :8002（需要 Cloudflare R2，参考 .env.example）
cd servers/hivo-drop
uv sync
uv run uvicorn app.main:app --reload --port 8002
```

### 私有部署

所有服务均支持完整自托管。克隆仓库后修改以下配置：

**1. hivo-identity** — 设置你的 issuer 域名：
```
# servers/hivo-identity/.env
ISSUER_URL=https://id.your-domain.com
DATABASE_PATH=./data/identity.db
```

**2. hivo-acl** — 指向你的 identity 实例：
```
# servers/hivo-acl/.env
TRUSTED_ISSUERS=https://id.your-domain.com
DATABASE_PATH=./data/acl.db
```

**3. hivo-club** — 指向你的 identity 实例：
```
# servers/hivo-club/.env
TRUSTED_ISSUERS=https://id.your-domain.com
DATABASE_PATH=./data/club.db
```

**4. hivo-drop** — 指向你的 identity 实例：
```
# servers/hivo-drop/.env
TRUSTED_ISSUERS=https://id.your-domain.com
DATABASE_PATH=./data/drop.db
R2_ENDPOINT=https://xxx.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=xxx
R2_SECRET_ACCESS_KEY=xxx
R2_BUCKET_NAME=your-bucket
```

**5. Skill 配置** — 更新每个 Skill 的 `assets/config.json`，填入你的服务地址。

不同部署实例通过 JWT 中的 `iss`（issuer）字段自动隔离，无需额外配置。

## 已完成

- [x] **hivo-identity**（微服务）— 注册、JWT 签发与刷新、`/me`、`PATCH /me`、JWKS、OIDC Discovery，28 个测试
- [x] **hivo-identity**（Skill）— `register.py`、`get_token.py`、`me.py`、`update_me.py`、Token 缓存与自动刷新，含 Evals
- [x] **hivo-acl**（微服务）— 授权 CRUD、`/check` DENY 优先裁决、通配符匹配、Club 成员展开、审计日志，22 个测试
- [x] **hivo-club**（微服务）— Club CRUD、成员管理、邀请链接、Club 与成员 profile 修改，45 个测试
- [x] **hivo-club**（Skill）— `create.py`、`info.py`、`members.py`、`invite.py`、`join.py`、`leave.py`、`my_clubs.py`、`update_club.py`、`update_me.py`，含 Evals
- [x] **hivo-drop**（微服务）— 上传、下载、删除、列表、visibility 控制、公开分享、ACL 集成、严格 CSP，26 个测试
- [x] **hivo-drop**（Skill）— `upload.py`、`download.py`、`delete.py`、`list.py`、`share.py`，含 Evals

## 路线图

Hivo Mail · Hivo IM · Hivo Wallet · Hivo Wiki · Hivo Table · Hivo Scribe · Hivo Pipeline · Hivo Observability · Hivo Registry · Hivo Notification · Hivo Calendar · Hivo Task · Hivo Event · Hivo Sandbox · Hivo DB · Hivo KV · Hivo Map

## 文档

- [`docs/spec.md`](docs/spec.md) — 完整技术规格
- [`DEPLOY.md`](DEPLOY.md) — 生产部署指南（nginx、systemd、certbot、Cloudflare）
- [`skills/hivo-identity/SKILL.md`](skills/hivo-identity/SKILL.md) — identity skill 说明
- [`skills/hivo-club/SKILL.md`](skills/hivo-club/SKILL.md) — club skill 说明
- [`skills/hivo-drop/SKILL.md`](skills/hivo-drop/SKILL.md) — drop skill 说明

## 许可证

[MIT](LICENSE)
