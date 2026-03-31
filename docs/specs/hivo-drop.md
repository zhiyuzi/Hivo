# hivo-drop 技术规格

## 1. 定位

> 面向 agent 的文件存储与分享服务。支持任意格式文件（文本/HTML/二进制），可设为公开供其他 agent 或人类查看。核心用途之一：agent 存储 HTML 给人类阅读。

域名：`https://drop.hivo.ink`

---

## 2. 数据模型（SQLite3）

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

---

## 3. 存储

- 正文存 Cloudflare R2（S3 兼容 API）
- R2 key 格式：`{iss_hash}/{sub}/{path}`
- 目录通过 key 中的 `/` 分隔符模拟，R2 `list()` 支持 `prefix` + `delimiter` 做目录枚举
- 元数据存 SQLite，不依赖 R2 的 metadata

---

## 4. 可见性规则

- **默认私有**：上传时 `visibility` 不填则为 `private`
- **显式公开**：通过 `PATCH /files/{path}` 设置 `visibility=public`，此时生成 `share_id`
- **撤销公开**：设回 `private`，`share_id` 作废
- 私有文件通过认证 API 访问（Bearer token）
- 公开文件通过 `/p/{share_id}` 访问，**不需要认证**
- 未认证访问私有文件一律返回 `404`（隐藏存在性）

---

## 5. 覆写保护

- `overwrite` 参数默认 `false`
- 服务端在写入流程内部判断文件是否已存在，**不依赖客户端先调 exists 检查**
- `overwrite=false` 且文件已存在 → 返回 `409 Conflict`
- `overwrite=true` → 覆盖写入
- `HEAD /files/{path}` 可用于客户端提示，但不是强一致保证

---

## 6. 允许的内容类型

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

---

## 7. HTML 公开托管安全方案

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

---

## 8. API 路由

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 生态索引页（Markdown） | 无 |
| PUT | `/files/{path:path}` | 上传文件 | Bearer |
| GET | `/files/{path:path}` | 获取文件原文 | Bearer |
| HEAD | `/files/{path:path}` | 检查文件是否存在 | Bearer |
| DELETE | `/files/{path:path}` | 删除文件 | Bearer |
| PATCH | `/files/{path:path}` | 修改元数据（visibility 等） | Bearer |
| GET | `/list?prefix=` | 列出文件/目录 | Bearer |
| GET | `/p/{share_id}` | 公开访问（无需认证） | 无 |
| GET | `/health` | 健康检查 | 无 |

---

## 8.1 GET / 响应

`Content-Type: text/markdown; charset=utf-8`

```markdown
Hey, agent.

I'm hivo-drop, part of Hivo. I handle file upload, storage, and sharing for you.

For the full skill suite and everything else Hivo offers: https://hivo.ink
```

---

## 9. Token 验证流程

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

---

## 10. 上传限制

| 限制项 | 默认值 | 说明 |
|--------|--------|------|
| 单文件大小上限 | 1 MB | 覆盖文本/HTML/二进制均适用 |
| 每 agent 文件数上限 | 100 | 超出后返回 `403`，需删除旧文件或提升配额 |

- 上传时服务端检查 `Content-Length`，超出直接返回 `413 Request Entity Too Large`
- 文件数检查在写入前执行，超出返回 `403 Forbidden`（附 error: `quota_exceeded`）
- 配额值未来由独立的 Quota 服务管理，v1 先用固定默认值

---

## 11. 错误响应格式

```json
{
  "error": "quota_exceeded",
  "message": "File count limit reached (100)"
}
```

| 状态码 | error 示例 | 场景 |
|--------|-----------|------|
| 401 | `invalid_token` | Bearer token 无效、过期、签名错误、aud 不匹配 |
| 403 | `quota_exceeded` | 文件数超出配额 |
| 404 | `not_found` | 文件不存在（或无权访问时隐藏存在性） |
| 409 | `conflict` | PUT 上传时文件已存在且未指定 overwrite=true |
| 413 | `file_too_large` | 文件大小超出 1 MB 上限 |
| 422 | `validation_error` | 请求参数不合法（路径格式错误等） |

---

## 12. Skill：hivo-drop

位于 `skills/hivo-drop/`。它是 `servers/hivo-drop` 的完整 skill 代理，覆盖文件上传、下载、删除、列表及可见性管理全流程。所有操作均需 Bearer token，token 由 hivo-identity skill 提供。

### 前置条件

`skills/hivo-identity` 必须已安装并完成注册（`assets/identity.json` 和 `assets/private_key.pem` 存在）。hivo-drop 的所有脚本在运行时自动调用 `../hivo-identity/scripts/get_token.py hivo-drop` 获取 Bearer token，无需用户手动提供。

### 目录结构

```
hivo-drop/
  SKILL.md          ← skill 描述与使用说明
  scripts/
    upload.py       ← 上传文件（PUT /files/{path}）
    download.py     ← 下载文件（GET /files/{path}）
    delete.py       ← 删除文件（DELETE /files/{path}）
    list.py         ← 列出文件（GET /list?prefix=）
    share.py        ← 设置可见性（PATCH /files/{path}），公开时返回分享 URL
  assets/
    config.json     ← drop_url，读取 hivo-drop 服务地址
```

### scripts 行为

所有脚本共用两个辅助函数（各自内联）：

- `_load_config()` — 读取 `assets/config.json`，返回 `drop_url`
- `_get_token()` — 调用 `../hivo-identity/scripts/get_token.py hivo-drop`，返回 access_token

路径定位方式（不依赖运行时工作目录）：

```python
from pathlib import Path
ASSETS_DIR = Path(__file__).parent.parent / "assets"
IDENTITY_GET_TOKEN = Path(__file__).parent.parent.parent / "hivo-identity" / "scripts" / "get_token.py"
```

**upload.py**

调用方式：`python scripts/upload.py <local_file> <remote_path> [--overwrite]`

1. 读取本地文件，检测 Content-Type（基于文件扩展名，fallback `application/octet-stream`）
2. 获取 Bearer token
3. `PUT /files/{remote_path}?overwrite=true/false`，附 `Content-Type` 和 `Content-Length`
4. 打印结果：`Uploaded: {path} ({size} bytes)`

**download.py**

调用方式：`python scripts/download.py <remote_path> [local_file]`

1. 获取 Bearer token
2. `GET /files/{remote_path}`
3. 若提供 `local_file`：写入磁盘，打印 `Saved: {local_file}`
4. 若未提供：内容写入 stdout（适合文本文件管道使用）

**delete.py**

调用方式：`python scripts/delete.py <remote_path>`

1. 获取 Bearer token
2. `DELETE /files/{remote_path}`
3. 打印 `Deleted: {path}`

**list.py**

调用方式：`python scripts/list.py [prefix]`

1. 获取 Bearer token
2. `GET /list?prefix={prefix}`
3. 表格打印：path、content_type、visibility、size

**share.py**

调用方式：`python scripts/share.py <remote_path> public|private`

1. 获取 Bearer token
2. `PATCH /files/{remote_path}` with `{"visibility": "public"|"private"}`
3. 若设为 public：打印 `Public URL: {drop_url}/p/{share_id}`
4. 若设为 private：打印 `File is now private. Share link revoked.`

### assets/config.json

```json
{"drop_url": "https://drop.hivo.ink"}
```

唯一配置项。所有脚本运行时读取此文件作为服务地址。可改为私有部署地址。
