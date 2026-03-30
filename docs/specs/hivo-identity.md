# hivo-identity 技术规格

## 1. 定位

> 面向 agent 的公开身份与令牌签发服务。支持自注册（公钥登记）、凭证换取 token、JWKS 公钥发布，以及被下游微服务信任。

域名：`https://id.hivo.ink`

---

## 2. 身份模型

三层设计：

| 层 | 字段 | 说明 |
|----|------|------|
| 内部主键 | `sub` | 不透明、稳定、不可变。格式 `agt_` + UUIDv7 |
| 可读用户名 | `handle` | `@` 风格，如 `writer@acme`。不是 email，但格式熟悉 |
| 可选邮箱 | `email` | 预留字段，v1 可空。未来用于通知/找回/邮箱绑定 |

### handle 格式约束

- 格式：`{name}@{namespace}`，如 `writer@acme`
- `name` 和 `namespace` 各自：字母（大小写均可）、数字、连字符，2-32 字符
- 不允许特殊符号（`.`、`_`、空格等）
- `@` 后的 namespace 只是命名空间标识符，**不关联任何组织实体**
- `a1@foo` 和 `a2@foo` 可能属于同一组织，也可能不是——hivo-identity 不关心
- 组织/团队的归属关系由其他微服务（如 hivo-group）决定
- handle 全局唯一

---

## 3. 数据模型（SQLite3）

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

---

## 4. 注册流程（公钥登记）

采用公私钥模式，**不使用密码**。

流程：

1. Agent 本地生成 Ed25519 密钥对
2. Agent 调用 `POST /register`，提交 `handle` + 公钥（JWK 格式）
3. 服务端返回一个 `challenge`（nonce）
4. Agent 用私钥签署 challenge，调用 `POST /register/verify`
5. 服务端验证签名，确认 agent 确实持有对应私钥
6. 注册完成，返回 `sub`

这个 challenge-proof 步骤是**必须的**，防止任何人用别人的公钥注册。

---

## 5. Token 设计

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

### Token 有效期

| Token | 有效期 | 说明 |
|-------|--------|------|
| access_token | 1 小时 | 过期后用 refresh_token 刷新 |
| refresh_token | 30 天 | 过期后需重新用 private_key_jwt 换取 |

- access_token 过期 → 调用 `POST /token/refresh` 刷新
- refresh_token 过期 → 调用 `POST /token` 重新用私钥签 assertion 换取
- Agent 持有私钥即可随时重新获取 token，不存在"永久失效"

---

## 6. API 路由

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 生态索引页（Markdown） | 无 |
| POST | `/register` | 提交 handle + JWK 公钥，返回 challenge | 无 |
| POST | `/register/verify` | 提交 challenge 签名，完成注册 | 无 |
| POST | `/token` | 用 private_key_jwt 换取 access_token；请求体须含 `audience`（必填） | 无（自证明） |
| POST | `/token/refresh` | 用 refresh_token 刷新 | refresh_token |
| GET | `/me` | 当前 token 对应的身份信息 | Bearer |
| GET | `/.well-known/openid-configuration` | OIDC Discovery 元数据 | 无 |
| GET | `/jwks.json` | 服务端签名公钥集合 | 无 |
| GET | `/health` | 健康检查 | 无 |

---

## 7. 错误响应格式

```json
{
  "error": "handle_taken",
  "message": "Handle writer@acme is already registered"
}
```

| 状态码 | error 示例 | 场景 |
|--------|-----------|------|
| 400 | `invalid_assertion` | /token 的 JWT assertion 格式错误或签名无效 |
| 400 | `challenge_expired` | /register/verify 的 challenge 已过期 |
| 400 | `challenge_failed` | /register/verify 的签名验证失败 |
| 401 | `invalid_token` | /me、/token/refresh 的 token 无效或过期 |
| 409 | `handle_taken` | /register 的 handle 已被注册 |
| 422 | `validation_error` | 请求参数不合法（handle 格式错误等） |
| 429 | `rate_limited` | 请求频率超限 |

---

## 8. OIDC Discovery（最小子集）

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

## 9. Skill：hivo-identity

位于 `skills/hivo-identity/`。封装注册、鉴权、token 管理全流程，供 agent 在运行时直接调用。

### 目录结构

```
hivo-identity/
  SKILL.md
  scripts/
    register.py     ← 生成 Ed25519 密钥对，完成注册，写入 assets/
    get_token.py    ← 读取私钥，生成 assertion，换取 access_token，支持缓存与自动刷新
    me.py           ← 调用 GET /me，打印当前身份信息
  assets/
    config.json     ← issuer_url，唯一提交到 git 的 assets 文件
    .gitignore      ← 排除 private_key.pem、token_cache.json
```

### scripts/register.py

调用方式：`python scripts/register.py <handle>`

1. 生成 Ed25519 密钥对
2. 调用 `POST /register` 提交 handle + 公钥，获取 challenge
3. 用私钥签署 challenge，调用 `POST /register/verify` 完成注册
4. 写入 `assets/private_key.pem`、`assets/public_key.jwk`、`assets/identity.json`

路径定位（不依赖运行时工作目录）：
```python
from pathlib import Path
ASSETS_DIR = Path(__file__).parent.parent / "assets"
```

### scripts/get_token.py

调用方式：`python scripts/get_token.py <audience>`，audience 必填。

三步策略（按顺序尝试）：

| 步骤 | 条件 | 动作 |
|------|------|------|
| 1 | 缓存 access_token 有效期 > 60s | 直接返回 |
| 2 | access_token 过期，refresh_token 有效 | 调用 `POST /token/refresh` |
| 3 | refresh_token 过期或不存在 | 用私钥签 assertion，调用 `POST /token` |

token 缓存写入 `assets/token_cache.json`（gitignored），按 audience 分别存储。

### scripts/me.py

调用方式：`python scripts/me.py`

调用 `GET /me`，打印：sub、handle、status、created_at。内部调用 `get_token.py hivo-identity` 获取 Bearer token。

### assets/config.json

```json
{"issuer_url": "https://id.hivo.ink"}
```
