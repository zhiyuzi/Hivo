# Hivo 开发进度

## 整体顺序

```
hivo-identity          ← 信任根，其他一切依赖它，优先完成
hivo-identity ← 注册和鉴权工具，开发调试其他服务时需要
hivo-drop              ← 文件存储服务，依赖 hivo-identity 做鉴权
Hivo              ← 生态发现 skill，最后完成（依赖前面都稳定）
```

---

## 已完成

### hivo-identity（微服务）

- [x] 项目初始化：uv + pyproject.toml + Git 仓库
- [x] 数据模型：subjects、signing_keys、pending_registrations、refresh_tokens 四张表
- [x] 服务签名密钥：首次启动自动生成 Ed25519 密钥对
- [x] 注册流程：`POST /register` + `POST /register/verify`（challenge-proof）
- [x] Token 签发：`POST /token`（private_key_jwt assertion）
- [x] Token 刷新：`POST /token/refresh`（单次轮换）
- [x] 身份查询：`GET /me`
- [x] 公钥发布：`GET /jwks.json`
- [x] OIDC Discovery：`GET /.well-known/openid-configuration`
- [x] 健康检查：`GET /health`
- [x] 运行时自描述：`GET /`（服务概览）+ `GET /README.md`（完整 API 文档）
- [x] Opportunistic cleanup（查询前清理过期数据）
- [x] 错误响应统一格式
- [x] 22 个单元测试，全部通过
- [x] 中英文双语 README + badges + MIT LICENSE
- [x] `audience` 解耦：`POST /token` 的 audience 改为调用方必填，不再硬编码 `"hivo-drop"`
- [x] `refresh_tokens` 表新增 `audience` 列；`/token/refresh` 自动从 DB 沿用，无需调用方重传
- [x] 已有 DB 自动 migration（idempotent `ALTER TABLE ADD COLUMN`）

### hivo-identity（Skill）

- [x] `scripts/register.py`：生成密钥对，完成注册，写入 assets/
- [x] `scripts/get_token.py`：读取私钥，生成 assertion，换取 access_token
- [x] `assets/config.json`：部署配置（`issuer_url`），唯一提交到 git 的 assets 文件；register.py 优先读取此文件
- [x] `SKILL.md`：skill 描述与使用说明
- [x] Git 仓库初始化
- [x] skill-creator eval（3 个测试用例，全部通过；skill 比 baseline 快约 2 倍）
- [x] `get_token.py` 新增 `<audience>` 必填命令行参数，传入 `POST /token` 请求体

### hivo-drop（微服务）

- [x] 项目初始化：uv + pyproject.toml + Git 仓库（3 commits）
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
- [x] 运行时自描述：`GET /`（Markdown 首页）+ `GET /README.md`（完整文档）
- [x] 错误响应统一格式 `{"error": "...", "message": "..."}`
- [x] agent 隔离：文件按 `owner_iss + owner_sub` 归属，跨 agent 返回 404
- [x] 24 个单元测试，全部通过（mock JWKS、FakeStorage、temp SQLite，无需真实 R2/网络）
- [x] 中英文双语 README + .env.example + MIT LICENSE

---

## 待办

### Hivo（Skill）

- [ ] `SKILL.md`：生态发现入口，描述所有服务及使用方式
- [ ] Git 仓库初始化

---

## Backlog（暂不实现）

来自 spec 第 7 节：

- hivo-identity：速率限制（`429 rate_limited`）
- hivo-identity：`PATCH /me`（修改 display_name / email）
- Hivo Mail（独立微服务）
- Quota 管理（独立微服务，hivo-drop 配额动态调整）
- Hivo Group（独立微服务，组织/团队管理）
- Hivo Pay（独立微服务，支付）
