# Hivo 开发进度

## 已完成

### hivo-identity（微服务）

- [x] 项目初始化：uv + pyproject.toml
- [x] 数据模型：subjects、signing_keys、pending_registrations、refresh_tokens 四张表
- [x] 服务签名密钥：首次启动自动生成 Ed25519 密钥对
- [x] 注册流程：`POST /register` + `POST /register/verify`（challenge-proof）
- [x] Token 签发：`POST /token`（private_key_jwt assertion，audience 由调用方必填）
- [x] Token 刷新：`POST /token/refresh`（单次轮换，audience 自动沿用）
- [x] 身份查询：`GET /me`
- [x] 公钥发布：`GET /jwks.json`
- [x] OIDC Discovery：`GET /.well-known/openid-configuration`
- [x] 健康检查：`GET /health`
- [x] 生态索引页：`GET /`（统一模板，含 REPO_URL）
- [x] Opportunistic cleanup（查询前清理过期数据）
- [x] 错误响应统一格式
- [x] 22 个单元测试，全部通过
- [x] `refresh_tokens` 表新增 `audience` 列；已有 DB 自动 migration（idempotent `ALTER TABLE ADD COLUMN`）

### hivo-identity（Skill）

- [x] `scripts/register.py`：生成 Ed25519 密钥对，完成 challenge-proof 注册，写入 assets/
- [x] `scripts/get_token.py`：读取私钥，生成 assertion，换取 access_token；支持 token 缓存（60s buffer）、refresh token 自动刷新、fallback assertion 流程
- [x] `scripts/me.py`：调用 `GET /me`，打印 sub / handle / status / created_at
- [x] `assets/config.json`：`issuer_url`，唯一提交到 git 的 assets 文件
- [x] `assets/.gitignore`：排除 private_key.pem 和 token_cache.json
- [x] `SKILL.md`：全英文，含 CRITICAL 前置说明、精确命令、Decision tree
- [x] Evals：3 个测试用例，描述性 + 真实 e2e（10/10）

### hivo-drop（微服务）

- [x] 项目初始化：uv + pyproject.toml
- [x] 数据模型：files 表 + 3 个 SQLite 索引，WAL 模式
- [x] Cloudflare R2 集成（S3 兼容 API，boto3）
- [x] JWT 验证（从 hivo-identity 的 /jwks.json 获取公钥，5 分钟缓存）
- [x] 文件上传：`PUT /files/{path}`（大小限制 1MB、文件数配额 100、overwrite 保护）
- [x] 文件下载：`GET /files/{path}`
- [x] 文件检查：`HEAD /files/{path}`（返回 X-Visibility、X-Share-Id）
- [x] 文件删除：`DELETE /files/{path}`
- [x] 元数据修改：`PATCH /files/{path}`（visibility 切换，public 时生成 UUIDv4 share_id）
- [x] 文件列表：`GET /list?prefix=`
- [x] 公开访问：`GET /p/{share_id}`（无需认证，严格 CSP + X-Frame-Options: DENY）
- [x] 健康检查：`GET /health`
- [x] 生态索引页：`GET /`（统一模板，含 REPO_URL）
- [x] 错误响应统一格式 `{"error": "...", "message": "..."}`
- [x] agent 隔离：文件按 `owner_iss + owner_sub` 归属，跨 agent 返回 404
- [x] 24 个单元测试，全部通过

### hivo-drop（Skill）

- [x] `scripts/upload.py`：上传本地文件，自动检测 Content-Type，支持 `--overwrite`
- [x] `scripts/download.py`：下载到本地文件或 stdout
- [x] `scripts/delete.py`：删除文件
- [x] `scripts/list.py`：列出文件（可按 prefix 过滤），表格输出含 visibility 和 size
- [x] `scripts/share.py`：设置 visibility（public 返回分享 URL，private 撤销链接）
- [x] 所有脚本自动调用 `../hivo-identity/scripts/get_token.py hivo-drop` 获取 Bearer token
- [x] `assets/config.json`：`drop_url`，唯一提交到 git 的 assets 文件
- [x] `SKILL.md`：全英文，含 CRITICAL 前置说明（先读 hivo-identity SKILL.md）、精确命令、Decision tree
- [x] Evals：4 个测试用例，描述性（12/12）+ 真实 e2e（20/20）

---

## Backlog

详见 `docs/spec.md` Backlog 章节，以 spec 为权威来源。以下为摘要：

- hivo-identity：速率限制（`429 rate_limited`）
- hivo-identity：`PATCH /me`（修改 display_name / email）
- Hivo Mail（独立微服务，agent 可收发消息）
- Quota（独立微服务，hivo-drop 配额动态调整）
- Hivo Group（独立微服务，组织/团队管理）
- Hivo Pay（独立微服务，支付）
- Hivo Calendar（独立微服务，日历与日程）
- Hivo Task（独立微服务，任务管理）
- Hivo Event / Cron（独立微服务，定时任务回调）
- Hivo DB（独立微服务，关系型数据库）
- Hivo KV（独立微服务，键值存储）
- Hivo Map（独立微服务，地图与地理位置）
