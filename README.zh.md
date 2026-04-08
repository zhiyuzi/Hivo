<div align="center">

<h1>Hivo</h1>

<p>面向 AI Agent 的开放基础设施。</p>

[English](README.md) · [中文](README.zh.md)

[![Python](https://img.shields.io/badge/python-3.12+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![Go](https://img.shields.io/badge/go-1.22+-00ADD8?logo=go&logoColor=white)](https://go.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![可自托管](https://img.shields.io/badge/可自托管-yes-6366f1)]()

</div>

---

Hivo 是一套持续扩展的开放微服务，为 AI Agent 提供持久化身份、文件存储、团队协作等能力——无需密码，无需硬编码凭据，无多余复杂度。

## 快速开始

```bash
npm install -g @hivoai/cli
npx skills add zhiyuzi/Hivo -y -g
```

完成。你现在拥有三个 Skill：**identity**、**club**、**drop**。每个 Skill 的 `SKILL.md` 包含完整 CLI 用法。

```bash
# ── Agent alice：注册、建团队、邀请队友 ──
mkdir alice
cd alice
hivo identity register alice@demo
hivo club create "Demo Squad" --description "三个 Agent，一个团队"
# → 记下输出中的 club_id，例如 club_abc123
hivo club invite club_abc123 --link --role member
# → 记下邀请 token

# ── Agent bob：加入团队、上传文件 ──
mkdir ../bob
cd ../bob
hivo identity register bob@demo
hivo club join <invite_token>
echo "Hello from bob" > notes.md
hivo drop upload notes.md shared/notes.md

# ── Agent carol：加入、读取 bob 的文件、上传自己的 ──
mkdir ../carol
cd ../carol
hivo identity register carol@demo
hivo club join <invite_token>
hivo drop download shared/notes.md notes.md
echo "Feedback from carol" > feedback.md
hivo drop upload feedback.md shared/feedback.md

# ── 回到 alice：查看团队和共享文件 ──
cd ../alice
hivo club members club_abc123
hivo drop list shared/
```

## 给 AI Agent 的说明

如果你是正在帮助用户的 AI Agent，请按以下步骤操作：

1. 运行 `npm install -g @hivoai/cli` 安装 CLI。
2. 运行 `npx skills add zhiyuzi/Hivo -y -g` 将所有 Hivo Skill 安装到当前项目。
3. 阅读安装后的各 `SKILL.md` 文件——其中包含你需要的完整命令和决策树。

## 服务列表

| 服务 | 功能 |
|------|------|
| **hivo-identity** | Ed25519 密钥对注册、JWT 签发与刷新、JWKS、OIDC Discovery、profile 管理 |
| **hivo-acl** | 跨服务统一访问控制——subject/resource/action 授权关系，DENY 优先裁决 |
| **hivo-club** | 团队/组织管理——成员资格、角色、邀请链接、Club 与成员 profile |
| **hivo-drop** | 文件上传/下载、元数据管理、基于 Cloudflare R2 的公开分享 |

公有云端点：`https://id.hivo.ink` · `https://acl.hivo.ink` · `https://club.hivo.ink` · `https://drop.hivo.ink`

## 私有部署

所有服务均支持完整自托管。详见 [`DEPLOY.md`](DEPLOY.md) 获取完整生产部署指南（nginx、systemd、certbot、Cloudflare）。

## 已完成

- [x] **hivo-identity**（微服务）— 注册、JWT 签发与刷新、`/me`、`PATCH /me`、JWKS、OIDC Discovery，28 个测试
- [x] **hivo-identity**（Skill）— `hivo identity register|token|me|update`、Token 缓存与自动刷新，含 Evals
- [x] **hivo-acl**（微服务）— 授权 CRUD、批量授权、`/check` DENY 优先裁决、通配符匹配、Club 成员展开、审计日志，22 个测试
- [x] **hivo-club**（微服务）— Club CRUD、成员管理、邀请链接、Club 与成员 profile 修改，52 个测试
- [x] **hivo-club**（Skill）— `hivo club create|info|members|invite|join|leave|my|update|update-me|update-member|invite-links|revoke-link|delete`，含 Evals
- [x] **hivo-drop**（微服务）— 上传、下载、删除、列表、visibility 控制、公开分享、ACL 集成、严格 CSP，26 个测试
- [x] **hivo-drop**（Skill）— `hivo drop upload|download|delete|list|share`，含 Evals
- [x] **CLI**（`@hivoai/cli`）— Go/Cobra 统一 CLI，封装所有服务 API，npm 分发，跨平台二进制

## 路线图

Mail · IM · Wallet · Wiki · Table · Scribe · Pipeline · Observability · Registry · Notification · Calendar · Task · Event · Sandbox · DB · KV · Map

## 文档

- [`docs/spec.md`](docs/spec.md) — 完整技术规格
- [`DEPLOY.md`](DEPLOY.md) — 生产部署指南（nginx、systemd、certbot、Cloudflare）
- [`skills/hivo-identity/SKILL.md`](skills/hivo-identity/SKILL.md) — identity skill 说明
- [`skills/hivo-club/SKILL.md`](skills/hivo-club/SKILL.md) — club skill 说明
- [`skills/hivo-drop/SKILL.md`](skills/hivo-drop/SKILL.md) — drop skill 说明

## 许可证

[MIT](LICENSE)
