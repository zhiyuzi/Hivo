# Hivo 技术规格

## 1. 项目总览

### 1.1 仓库结构

整个项目是一个 monorepo，根目录为 `hivo/`：

```
hivo/
  servers/
    hivo-identity/           ← 微服务：身份注册、token 签发
    hivo-drop/               ← 微服务：文件存储与公开分享
  skills/
    hivo-identity/           ← Skill：hivo-identity 的完整 skill 代理
    hivo-drop/               ← Skill：hivo-drop 的完整 skill 代理
  docs/                      ← 本文档所在位置
```

### 1.2 各目录职责

| 目录 | 类型 | 职责 |
|------|------|------|
| `servers/hivo-identity` | 微服务 | 身份注册、token 签发、JWKS 公钥发布 |
| `servers/hivo-drop` | 微服务 | 文件存储与公开分享（支持任意格式，文本/HTML/二进制均可） |
| `skills/hivo-identity` | Skill | hivo-identity 的完整 skill 代理，覆盖注册、鉴权、token 管理全流程 |
| `skills/hivo-drop` | Skill | hivo-drop 的完整 skill 代理，覆盖上传、下载、分享、visibility 管理全流程 |

### 1.3 服务关系与耦合原则

依赖关系：

```
servers/hivo-identity          ← 底层，不依赖任何其他服务
servers/hivo-drop              ← 依赖 hivo-identity（token 验证）
skills/hivo-identity           ← 依赖 servers/hivo-identity（注册与换 token）
skills/hivo-drop               ← 依赖 servers/hivo-drop（文件操作）
```

**耦合原则（必须遵守）：**

- 每个目录只能显式引用它直接依赖的上游，**不得引用与自身无依赖关系的其他目录**
- 以 Skill 为例：`skills/hivo-identity` 的职责是管理凭据，它依赖 `servers/hivo-identity`，所以可以引用 hivo-identity 的 URL 和接口。但它与 hivo-drop 没有直接依赖，因此 SKILL.md 里**不得出现 hivo-drop 的名字或 URL**
- `.md` 文件同样是代码，适用高内聚、低耦合原则：该依赖的写清楚，不该依赖的不要提
- 生态发现（"有哪些服务"）由根域名 `https://hivo.ink` 负责，不是每个具体 skill 的职责

简记：**谁调用谁，谁才能提谁。**

### 1.4 技术栈

- 微服务：uv + FastAPI + SQLite3 + Pydantic
- hivo-drop 额外依赖 Cloudflare R2
- Skills：纯 Python 脚本，无框架依赖

### 1.5 根域名入口

`https://hivo.ink` 作为整个生态的运行时发现入口，返回 `Content-Type: text/markdown; charset=utf-8`：

```markdown
# Hivo

Open infrastructure for agents.

## Services
- https://id.hivo.ink — Hivo Identity: registration & authentication
- https://drop.hivo.ink — Hivo Drop: file storage & sharing

## Getting Started
1. Install the `hivo-identity` skill — it handles keypair generation, registration, and token acquisition for you.
2. If you prefer manual integration, read the identity service docs: GET https://id.hivo.ink/README.md
3. Read each service's README: GET {service_url}/README.md
```

每个微服务的 `/` 和 `/README.md` 提供该服务的详细使用文档。根域名只负责告知"有哪些服务、在哪"。

### 1.6 运行时自描述约定

所有微服务必须实现以下两个路由，返回 `Content-Type: text/markdown; charset=utf-8`：

| 路由 | 内容 | 用途 |
|------|------|------|
| `GET /` | 服务概览（角色、issuer、核心路由列表） | agent 快速了解这是什么服务 |
| `GET /README.md` | 完整 API 文档（所有端点的请求/响应格式、错误码） | agent 获取足够上下文后调用服务 |

设计原则：**服务把自己的使用说明内嵌在自己里面**。agent 不需要依赖任何外部文档，只需 HTTP 请求即可自主获取所有必要信息。`GET /` 是元信息入口，agent 读完后若需要更多细节，自行请求 `GET /README.md`。

`/` 的内容模板必须在首行包含 `Docs: GET /README.md`，并在路由列表中将 `GET /README.md` 列为第一条。

### 1.7 部署模式

- **公有云**：你自己部署一套，面向全球 agent 开放
- **私有部署**：企业克隆仓库自行部署，通过 `iss` 区分不同部署实例

---

## 2. Service A：hivo-identity

### 2.1 定位

> 面向 agent 的公开身份与令牌签发服务。支持自注册（公钥登记）、凭证换取 token、JWKS 公钥发布，以及被下游微服务信任。

### 2.2 身份模型

三层设计：

| 层 | 字段 | 说明 |
|----|------|------|
| 内部主键 | `sub` | 不透明、稳定、不可变。格式 `agt_` + UUIDv7 |
| 可读用户名 | `handle` | `@` 风格，如 `writer@acme`。不是 email，但格式熟悉 |
| 可选邮箱 | `email` | 预留字段，v1 可空。未来用于通知/找回/邮箱绑定 |

### 2.3 handle 格式约束

- 格式：`{name}@{namespace}`，如 `writer@acme`
- `name` 和 `namespace` 各自：字母（大小写均可）、数字、连字符，2-32 字符
- 不允许特殊符号（`.`、`_`、空格等）
- `@` 后的 namespace 只是命名空间标识符，**不关联任何组织实体**
- `a1@foo` 和 `a2@foo` 可能属于同一组织，也可能不是——hivo-identity 不关心
- 组织/团队的归属关系由其他微服务（如 hivo-group）决定
- handle 全局唯一

### 2.4 数据模型（SQLite3）

**subjects 表**

```sql
CREATE TABLE subjects (
    sub         TEXT PRIMARY KEY,          -- agt_ + UUIDv7
    handle      TEXT NOT NULL UNIQUE,      -- writer@acme
    email       TEXT,                      -- 可空，预留
    display_name TEXT,
    status      TEXT NOT NULL DEFAULT 'active',  -- active / disabled
    jwk_pub     TEXT NOT NULL,             -- agent 公钥（JWK JSON）
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

**signing_keys 表**（服务自己的签名密钥）

```sql
CREATE TABLE signing_keys (
    kid         TEXT PRIMARY KEY,          -- key id（UUIDv4）
    alg         TEXT NOT NULL,             -- EdDSA
    private_key TEXT NOT NULL,             -- 服务端私钥（加密存储）
    public_key  TEXT NOT NULL,             -- 对应公钥（JWK JSON）
    is_current  INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);
```

**pending_registrations 表**（注册 challenge 临时存储）

```sql
CREATE TABLE pending_registrations (
    challenge   TEXT PRIMARY KEY,             -- 随机 nonce
    handle      TEXT NOT NULL,
    jwk_pub     TEXT NOT NULL,                -- 待注册的公钥（JWK JSON）
    expires_at  TEXT NOT NULL,                -- 过期时间（10 分钟）
    created_at  TEXT NOT NULL
);
```

- challenge 有效期 10 分钟
- 查询前先删除所有已过期行，再按条件查询（opportunistic cleanup）
- `/register/verify` 成功后立即删除对应行

**refresh_tokens 表**

```sql
CREATE TABLE refresh_tokens (
    token_hash  TEXT PRIMARY KEY,             -- refresh_token 的 SHA-256
    sub         TEXT NOT NULL,                -- 关联的 agent
    audience    TEXT NOT NULL,                -- token 的目标服务，随 access_token 一起签发
    expires_at  TEXT NOT NULL,                -- 过期时间（30 天）
    created_at  TEXT NOT NULL
);
```

- 存储 token 的 hash 而非明文，防止数据库泄露后 token 被直接使用
- 查询前先删除所有已过期行，再按条件查询（opportunistic cleanup）
- `/token/refresh` 时验证 hash 匹配且未过期
- 签发新 refresh_token 时删除旧的（单 token 轮换）

### 2.5 注册流程（公钥登记）

采用公私钥模式，**不使用密码**。

流程：

1. Agent 本地生成 Ed25519 密钥对
2. Agent 调用 `POST /register`，提交 `handle` + 公钥（JWK 格式）
3. 服务端返回一个 `challenge`（nonce）
4. Agent 用私钥签署 challenge，调用 `POST /register/verify`
5. 服务端验证签名，确认 agent 确实持有对应私钥
6. 注册完成，返回 `sub`

这个 challenge-proof 步骤是**必须的**，防止任何人用别人的公钥注册。

### 2.6 Token 设计

**access_token**（JWT，服务端用自己的私钥签）：

```json
{
  "iss": "https://id.hivo.ink",
  "sub": "agt_01JV8Y...",
  "aud": "<resource_service>",
  "handle": "writer@acme",
  "exp": 1770000000,
  "iat": 1769996400
}
```

`aud` 由调用方在 `POST /token` 时传入，标识 token 的目标服务。hivo-identity 不预设任何默认值——它只签名，不知道下游有哪些服务。

- 标准 claim：`iss`、`sub`、`aud`、`exp`、`iat`
- 自定义 claim：`handle`
- 签名算法：EdDSA（Ed25519）

**换取 token 的方式**：`private_key_jwt`（RFC 7523 风格）

1. Agent 用自己的私钥签一个短期 JWT assertion
2. 发送到 `POST /token`
3. 服务端用 agent 注册时登记的公钥验证
4. 验证通过后签发 access_token + refresh_token

### 2.7 API 路由

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 服务索引页（Markdown） | 无 |
| GET | `/README.md` | 完整使用文档（Markdown） | 无 |
| POST | `/register` | 提交 handle + JWK 公钥，返回 challenge | 无 |
| POST | `/register/verify` | 提交 challenge 签名，完成注册 | 无 |
| POST | `/token` | 用 private_key_jwt 换取 access_token；请求体须含 `audience`（必填） | 无（自证明） |
| POST | `/token/refresh` | 用 refresh_token 刷新 | refresh_token |
| GET | `/me` | 当前 token 对应的身份信息 | Bearer |
| GET | `/.well-known/openid-configuration` | OIDC Discovery 元数据 | 无 |
| GET | `/jwks.json` | 服务端签名公钥集合 | 无 |
| GET | `/health` | 健康检查 | 无 |

### 2.8 首页 `/` 内容模板

返回 `Content-Type: text/markdown; charset=utf-8`：

```markdown
# Hivo Identity

Role: issuer / authentication service
Issuer: https://id.hivo.ink
Docs: GET /README.md

## Core Routes
- GET /README.md — Full documentation (read this first)
- POST /register — Register agent (public key enrollment)
- POST /register/verify — Complete registration (challenge verification)
- POST /token — Exchange private_key_jwt for access_token
- POST /token/refresh — Refresh access_token
- GET /me — Current identity info
- GET /.well-known/openid-configuration — OIDC Discovery metadata
- GET /jwks.json — Signing public keys
- GET /health — Health check

## Identity Model
- Primary key: sub
- Human-readable name: handle
- Token format: JWT (EdDSA)
```

### 2.9 Token 有效期

| Token | 有效期 | 说明 |
|-------|--------|------|
| access_token | 1 小时 | 过期后用 refresh_token 刷新 |
| refresh_token | 30 天 | 过期后需重新用 private_key_jwt 换取 |

- access_token 过期 → 调用 `POST /token/refresh` 刷新
- refresh_token 过期 → 调用 `POST /token` 重新用私钥签 assertion 换取
- Agent 持有私钥即可随时重新获取 token，不存在"永久失效"

### 2.10 错误响应格式

所有错误响应统一为 JSON：

```json
{
  "error": "handle_taken",
  "message": "Handle writer@acme is already registered"
}
```

常用状态码：

| 状态码 | error 示例 | 场景 |
|--------|-----------|------|
| 400 | `invalid_assertion` | /token 的 JWT assertion 格式错误或签名无效 |
| 400 | `challenge_expired` | /register/verify 的 challenge 已过期 |
| 400 | `challenge_failed` | /register/verify 的签名验证失败 |
| 401 | `invalid_token` | /me、/token/refresh 的 token 无效或过期 |
| 409 | `handle_taken` | /register 的 handle 已被注册 |
| 422 | `validation_error` | 请求参数不合法（handle 格式错误等） |
| 429 | `rate_limited` | 请求频率超限 |

### 2.11 OIDC Discovery（最小子集）

`GET /.well-known/openid-configuration` 返回：

```json
{
  "issuer": "https://id.hivo.ink",
  "token_endpoint": "https://id.hivo.ink/token",
  "jwks_uri": "https://id.hivo.ink/jwks.json",
  "userinfo_endpoint": "https://id.hivo.ink/me",
  "registration_endpoint": "https://id.hivo.ink/register",
  "token_endpoint_auth_methods_supported": ["private_key_jwt"],
  "token_endpoint_auth_signing_alg_values_supported": ["EdDSA"],
  "subject_types_supported": ["public"],
  "id_token_signing_alg_values_supported": ["EdDSA"]
}
```

v1 做 OIDC-like 最小子集，不追求完整合规。

---

## 3. Service B：hivo-drop

### 3.1 定位

> 面向 agent 的文件存储与分享服务。支持任意格式文件（文本/HTML/二进制），可设为公开供其他 agent 或人类查看。核心用途之一：agent 存储 HTML 给人类阅读。

### 3.2 数据模型（SQLite3）

**files 表**

```sql
CREATE TABLE files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_sub   TEXT NOT NULL,             -- 文件所有者 (iss:sub)
    owner_iss   TEXT NOT NULL,             -- 签发方
    path        TEXT NOT NULL,             -- 用户定义的路径，如 docs/report.html
    r2_key      TEXT NOT NULL,             -- R2 中的实际 key
    content_type TEXT NOT NULL,            -- text/html, text/markdown 等
    visibility  TEXT NOT NULL DEFAULT 'private',  -- private / public
    share_id    TEXT UNIQUE,               -- 公开时生成的分享 ID（UUIDv4，防枚举）
    size        INTEGER NOT NULL,
    sha256      TEXT NOT NULL,
    etag        TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,

    UNIQUE(owner_iss, owner_sub, path)
);
```

索引：
- `(owner_iss, owner_sub, path)` — 文件定位
- `(share_id)` — 公开访问
- `(owner_iss, owner_sub, visibility)` — 列出公开/私有文件

### 3.3 存储

- 正文存 Cloudflare R2（S3 兼容 API）
- R2 key 格式：`{iss_hash}/{sub}/{path}`
- 目录通过 key 中的 `/` 分隔符模拟，R2 `list()` 支持 `prefix` + `delimiter` 做目录枚举
- 元数据存 SQLite，不依赖 R2 的 metadata

### 3.4 可见性规则

- **默认私有**：上传时 `visibility` 不填则为 `private`
- **显式公开**：通过 `PATCH /files/{path}` 设置 `visibility=public`，此时生成 `share_id`
- **撤销公开**：设回 `private`，`share_id` 作废
- 私有文件通过认证 API 访问（Bearer token）
- 公开文件通过 `/p/{share_id}` 访问，**不需要认证**
- 未认证访问私有文件一律返回 `404`（隐藏存在性）

### 3.5 覆写保护

- `overwrite` 参数默认 `false`
- 服务端在写入流程内部判断文件是否已存在，**不依赖客户端先调 exists 检查**
- `overwrite=false` 且文件已存在 → 返回 `409 Conflict`
- `overwrite=true` → 覆盖写入
- `HEAD /files/{path}` 可用于客户端提示，但不是强一致保证

### 3.6 允许的内容类型

支持任意格式文件（文本或二进制）。文本类型可在浏览器直接渲染，二进制类型仅供下载。

**文本 allowlist（可渲染）：**

- `text/plain`
- `text/markdown`
- `text/html`
- `text/css`
- `text/javascript`
- `application/json`
- `application/xml`
- `application/yaml`
- `application/toml`

**二进制：** 接受任意 `Content-Type`，公开访问时以 `Content-Disposition: attachment` 下载，不渲染。

判断依据：上传时的 `Content-Type` 头。不依赖文件扩展名。

### 3.7 HTML 公开托管安全方案

HTML 公开展示是核心功能。安全约束：

1. **同域名隔离**：公开文件通过 `drop.hivo.ink/p/{share_id}` 访问，与认证 API 共用域名但路径隔离
2. **无 cookie**：hivo-drop 使用 Bearer token 认证，不设置任何 cookie，公开路径无登录态可窃取
3. **严格 CSP**：公开 HTML 响应头添加：
   ```
   Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src https: data:; font-src https:;
   ```
   - 禁止 `script-src`（不允许执行 JS）
   - 允许内联样式（agent 生成的 HTML 通常用内联样式）
   - 允许加载外部图片和字体
4. **额外安全头**：
   ```
   X-Content-Type-Options: nosniff
   X-Frame-Options: DENY
   ```
5. **sandbox 属性**：如果通过 iframe 嵌入，加 `sandbox` 属性限制能力

这样 agent 可以上传带样式的 HTML 给人类看，但不会被用来做 XSS、钓鱼页或脚本注入。

### 3.8 API 路由

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 服务索引页（Markdown） | 无 |
| GET | `/README.md` | 完整使用文档（Markdown） | 无 |
| PUT | `/files/{path:path}` | 上传文件 | Bearer |
| GET | `/files/{path:path}` | 获取文件原文 | Bearer |
| HEAD | `/files/{path:path}` | 检查文件是否存在 | Bearer |
| DELETE | `/files/{path:path}` | 删除文件 | Bearer |
| PATCH | `/files/{path:path}` | 修改元数据（visibility 等） | Bearer |
| GET | `/list?prefix=` | 列出文件/目录 | Bearer |
| GET | `/p/{share_id}` | 公开访问（无需认证） | 无 |
| GET | `/health` | 健康检查 | 无 |

### 3.9 首页 `/` 内容模板

返回 `Content-Type: text/markdown; charset=utf-8`：

```markdown
# Hivo Drop

Role: file storage and sharing service
Auth: Bearer token issued by trusted issuer
Docs: GET /README.md

## Core Routes
- GET /README.md — Full documentation (read this first)
- PUT /files/{path} — Upload file
- GET /files/{path} — Get file content
- HEAD /files/{path} — Check file existence
- DELETE /files/{path} — Delete file
- PATCH /files/{path} — Update metadata (visibility, etc.)
- GET /list?prefix= — List files/directories
- GET /p/{share_id} — Public access (no auth required)
- GET /health — Health check

## Rules
- Accepts any file format (text types rendered inline, binary as attachment download)
- Default visibility: private
- Default overwrite: false
- Max file size: 1 MB
- Max files per agent: 100 (default)
```

### 3.10 Token 验证流程

hivo-drop 收到请求后：

1. 提取 `Authorization: Bearer <token>`
2. 解析 JWT，读取 `iss`
3. 检查 `iss` 是否在受信任 issuer 列表中
4. 从 `iss` 对应的 `/jwks.json` 获取公钥（带缓存）
5. 验证 JWT 签名
6. 检查 `aud` 是否与本服务名一致（不匹配则拒绝）
7. 检查 `exp` 是否过期
8. 提取 `sub`、`handle`，识别用户身份

配置项：
```
TRUSTED_ISSUERS=https://id.hivo.ink
```

### 3.11 上传限制

| 限制项 | 默认值 | 说明 |
|--------|--------|------|
| 单文件大小上限 | 1 MB | 覆盖文本/HTML/二进制均适用 |
| 每 agent 文件数上限 | 100 | 超出后返回 `403`，需删除旧文件或提升配额 |

- 上传时服务端检查 `Content-Length`，超出直接返回 `413 Request Entity Too Large`
- 文件数检查在写入前执行，超出返回 `403 Forbidden`（附 error: `quota_exceeded`）
- 配额值未来由独立的 Quota 服务管理，v1 先用固定默认值

### 3.12 错误响应格式

所有错误响应统一为 JSON：

```json
{
  "error": "quota_exceeded",
  "message": "File count limit reached (100)"
}
```

常用状态码：

| 状态码 | error 示例 | 场景 |
|--------|-----------|------|
| 401 | `invalid_token` | Bearer token 无效、过期、签名错误、aud 不匹配 |
| 403 | `quota_exceeded` | 文件数超出配额 |
| 404 | `not_found` | 文件不存在（或无权访问时隐藏存在性） |
| 409 | `conflict` | PUT 上传时文件已存在且未指定 overwrite=true |
| 413 | `file_too_large` | 文件大小超出 1 MB 上限 |
| 422 | `validation_error` | 请求参数不合法（路径格式错误等） |

---

## 4. 身份体系速查

```
iss        — 哪个身份服务签发的（区分部署）
sub        — 这个 agent 是谁（内部主键）
handle     — 可读用户名（展示用）
aud        — 这个 token 给谁用（资源服务校验）
```

唯一身份 = `iss + sub`
文件归属 = `iss + sub`（owner）
配额/计费 = `sub`（per-agent）

---

## 5. 生态发现

### 5.1 运行时发现

生态发现由根域名 `https://hivo.ink` 负责（见 §1.5）。agent 访问根域名即可获取所有服务的入口和说明。

### 5.2 接入建议

任何需要接入 Hivo 生态的 agent：

1. 访问 `https://hivo.ink` 了解所有可用服务
2. 安装 `skills/hivo-identity` skill——它封装了 Ed25519 keypair 生成、challenge-proof 注册流程、JWT 签发等全部流程，是推荐的接入方式
3. 如需手动集成，阅读各服务的 `GET /README.md`

---

## 6. Skill：hivo-identity

### 6.1 定位

位于 `skills/hivo-identity/`。它是 `servers/hivo-identity` 的完整 skill 代理，覆盖注册、鉴权、token 管理全流程——生成 Ed25519 密钥对、完成 challenge-proof 注册、换取和刷新 access token，供 agent 在运行时直接调用。

### 6.2 目录结构

```
hivo-identity/
  SKILL.md          ← skill 描述与使用说明
  scripts/
    register.py     ← 生成 Ed25519 密钥对，向 hivo-identity 完成注册，将结果写入 assets/
    get_token.py    ← 读取私钥，生成 assertion，换取 access_token，输出供 agent 使用
  assets/
    .gitignore      ← 只含一行：private_key.pem
    private_key.pem ← 生成后写入，不提交 git
    public_key.jwk  ← 对应公钥，可提交
    identity.json   ← 注册结果：sub、handle、iss 等，可提交
```

### 6.3 scripts/register.py 行为

1. 生成 Ed25519 密钥对
2. 调用 `POST /register` 提交 handle + 公钥，获取 challenge
3. 用私钥签署 challenge，调用 `POST /register/verify` 完成注册
4. 将私钥写入 `assets/private_key.pem`，公钥写入 `assets/public_key.jwk`，注册结果写入 `assets/identity.json`

路径定位方式（不依赖运行时工作目录）：

```python
from pathlib import Path
ASSETS_DIR = Path(__file__).parent.parent / "assets"
```

### 6.4 scripts/get_token.py 行为

调用方式：`python scripts/get_token.py <audience>`，`audience` 为必填参数，标识 token 的目标服务（如 `hivo-drop`）。

1. 从命令行参数读取 `audience`，缺失则报错退出
2. 读取 `assets/identity.json`，获取 `sub` 和 `iss`
3. 读取 `assets/private_key.pem`，加载私钥
4. 构造 assertion（JWT）：
   - `iss` = `sub`
   - `sub` = `sub`
   - `aud` = `{iss}/token`
   - `iat` = 当前时间
   - `exp` = 当前时间 + 5 分钟
5. 用私钥对 assertion 签名（EdDSA）
6. 调用 `POST {iss}/token`，提交 assertion 和 audience，获取 access_token 和 refresh_token
7. 将 access_token 输出到 stdout，供 agent 使用

路径定位方式同 `register.py`，不依赖运行时工作目录：

```python
from pathlib import Path
ASSETS_DIR = Path(__file__).parent.parent / "assets"
```

### 6.5 .gitignore

```
assets/private_key.pem
```

`public_key.jwk` 和 `identity.json` 可以提交，它们不是秘密。

---

## 7. 待办事项（Backlog）

### 7.1 Hivo Mail（邮件）

- 基于 hivo-identity 的身份体系扩展
- 让 agent 拥有可收发消息的地址
- 邮件服务是 hivo-identity **上层的产品能力**，不是底座
- 独立仓库，独立微服务

### 7.2 Quota（hivo-drop 配额）

- 控制每个 agent 在 hivo-drop 中可上传的文件数量
- 基于 `sub`（per-agent）做配额管理
- v1 使用固定默认值（100），未来可支持动态调整
- 独立仓库，独立微服务

### 7.3 Hivo Group（组织/团队管理）

- 基于 hivo-identity 的身份体系扩展
- 管理 agent 的组织/团队归属关系
- handle 中的 namespace 不等于 group——归属关系由此服务决定
- 独立仓库，独立微服务

### 7.4 Hivo Pay（支付）

- 为 agent 提供支付能力
- 具体方案待议
- 独立仓库，独立微服务

### 7.5 hivo-identity：速率限制

- 对高频接口（`/register`、`/token`）实现请求速率限制
- 超限返回 `429 rate_limited`
- v1 未实现，后续按实际需求确定限流策略

### 7.6 hivo-identity：Profile 修改接口

- 新增 `PATCH /me`，需要 Bearer 认证
- 支持修改 `display_name` 和 `email` 两个字段
- `sub` 和 `handle` 不可修改

### 7.7 Hivo Calendar（日历）

- 为 agent 提供日历与日程管理能力
- 支持创建、查询、更新、删除事件（Event）
- 支持按时间范围查询；支持多 agent 共享/订阅日历
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 7.8 Hivo Task（任务）

- 为 agent 提供任务管理能力（类 Todo/Issue）
- 支持创建、分配、更新状态、关闭任务
- 可与 Hivo Calendar 联动（任务截止日期映射为日历事件）
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 7.9 Hivo Event（事件驱动：Cron + Webhook）

**Cron（确定做）：**
- 为 agent 注册定时任务，到时间后由平台回调 agent 指定 URL
- 平台主动触发，逻辑清晰，实现成本低
- 认证基于 hivo-identity Bearer token；回调时附带签名验证
- 独立仓库，独立微服务

**Webhook（待议，倾向不做）：**
- 设想：agent 在平台注册监听规则，外部系统（如 GitHub、Stripe）推事件到平台，平台再转发给 agent
- 问题一：实现成本高——不同第三方验签方式各异（HMAC-SHA256 header 名、格式均不同），需逐一适配
- 问题二：定位模糊——平台变成"外部系统与 agent 之间的中间人"，职责边界不清晰
- 问题三：agent 完全可以自己暴露 HTTP 端点直接接收外部推送，不需要平台中转
- **结论**：Cron 是刚需，Webhook 中转价值有限，暂不做。如未来有明确需求场景再议。

### 7.10 Hivo DB（关系型数据库）

- 为 agent 提供结构化数据存储能力
- 每个 agent（按 `sub`）拥有独立数据库实例或 schema 命名空间
- 支持 SQL 查询（SELECT/JOIN/WHERE/聚合等）；适合任务、日历、邮件等有查询需求的业务数据
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 7.11 Hivo KV（键值存储）

- 为 agent 提供轻量键值存储能力
- 每个 agent（按 `sub`）拥有独立命名空间
- 支持 CRUD；value 为任意 JSON
- 适合存储配置、运行时状态、偏好等小数据；不替代 Hivo DB 的结构化查询能力
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 7.12 Hivo Map（地图服务）

- 为 agent 提供地理位置与地图能力
- 支持地理编码（地址 → 坐标）、反地理编码（坐标 → 地址）、路径规划、POI 搜索
- 适合需要位置感知的 agent（如导航、签到、附近搜索等场景）
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

---

## 8. 部署与配置

### 8.1 公有云部署

- 根域名入口：`https://hivo.ink`
- hivo-identity：`https://id.hivo.ink`
- hivo-drop：`https://drop.hivo.ink`（API + 公开访问均在此域名）

### 8.2 私有部署

企业克隆仓库后自行部署：
- 修改 `iss` 为自己的域名
- hivo-drop 配置 `TRUSTED_ISSUERS` 指向自己的 hivo-identity 实例
- 数据完全隔离，`iss` 不同即为不同信任域

### 8.3 关键配置项

**hivo-identity：**
```
ISSUER_URL=https://id.hivo.ink
DATABASE_PATH=./data/identity.db
SIGNING_KEY_ALG=EdDSA
```

**hivo-drop：**
```
TRUSTED_ISSUERS=https://id.hivo.ink
DATABASE_PATH=./data/drop.db
R2_ENDPOINT=https://xxx.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=xxx
R2_SECRET_ACCESS_KEY=xxx
R2_BUCKET_NAME=hivo-drop
```

### 8.4 Python 工具链规范

所有微服务统一使用 [uv](https://docs.astral.sh/uv/) 管理 Python 依赖，不使用 pip / poetry / pipenv。

**依赖声明**：使用 `pyproject.toml`，不使用 `requirements.txt`。

**安装依赖**（让 uv 自动解析最新版，不手写版本号）：

```bash
uv add fastapi uvicorn[standard] pydantic pydantic-settings ...
uv add --dev pytest httpx
```

**同步环境**：

```bash
uv sync        # 生产依赖
uv sync --dev  # 含开发依赖
```

**运行命令**（始终通过 uv，使用 .venv 内的解释器）：

```bash
uv run uvicorn app.main:app --reload   # 开发
uv run pytest                          # 测试
uv run gunicorn app.main:app \         # 生产
  -k uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:8000
```

**生产进程管理**：使用 Gunicorn + `uvicorn.workers.UvicornWorker`。Gunicorn 负责多进程管理，UvicornWorker 处理异步请求。`uv.lock` 提交到 git，保证环境可复现。
