# agent-identity

面向 agent 的身份注册与 JWT 签发服务。

**公有云实例**：`https://id.agentinfra.cloud`

---

## 定位

agent-identity 是整个 agentinfra 生态的**信任根**。它负责：

- 为每个 agent 颁发不可变的唯一身份（`sub`）
- 通过公私钥体系（Ed25519）完成注册，不使用密码
- 签发 JWT access token，供下游服务（如 agent-drop）验证身份

下游服务通过 `/jwks.json` 获取公钥，独立验证 token，不需要实时回调 agent-identity。

---

## 自行部署

### 前置条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

### 1. 克隆并安装依赖

```bash
git clone <repo-url> agent-identity
cd agent-identity
uv sync
```

### 2. 配置环境变量

复制示例文件后按需修改：

```bash
cp .env.example .env
```

`.env` 内容：

```ini
ISSUER_URL=https://id.yourdomain.com   # 你的服务域名，写入 JWT 的 iss 字段
DATABASE_PATH=./data/identity.db       # SQLite 数据库路径
```

> `ISSUER_URL` 决定了 JWT 的 `iss` claim，下游服务靠它区分信任域。一旦上线不要改。

### 3. 本地运行（开发）

```bash
uv run uvicorn app.main:app --reload --port 8000
```

访问 `http://localhost:8000` 查看服务文档。

### 4. 生产部署

使用 Gunicorn + UvicornWorker：

```bash
uv run gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:8000
```

推荐在前面挂 nginx/Caddy 做 TLS 终止和反向代理。

**systemd 示例**（`/etc/systemd/system/agent-identity.service`）：

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

### 5. 数据目录

服务启动时自动创建 SQLite 数据库，默认路径 `./data/identity.db`。生产环境确保该目录有写权限，并做好备份。

---

## API 速览

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 服务简介（Markdown） | 无 |
| GET | `/README.md` | 完整 API 文档（Markdown） | 无 |
| POST | `/register` | 提交 handle + 公钥，获取 challenge | 无 |
| POST | `/register/verify` | 签名验证，完成注册，返回 `sub` | 无 |
| POST | `/token` | 用 `private_key_jwt` 换取 access_token | 无（自证明） |
| POST | `/token/refresh` | 刷新 access_token | refresh_token |
| GET | `/me` | 当前身份信息 | Bearer |
| GET | `/.well-known/openid-configuration` | OIDC Discovery 元数据 | 无 |
| GET | `/jwks.json` | 服务端签名公钥 | 无 |
| GET | `/health` | 健康检查 | 无 |

完整请求/响应格式见 `GET /README.md`（服务启动后访问）。

---

## 注册流程

```
1. 本地生成 Ed25519 密钥对
2. POST /register  → 提交 handle + 公钥（JWK 格式）→ 得到 challenge
3. 用私钥签署 challenge 字节（raw Ed25519 签名）
4. POST /register/verify → 提交 challenge + base64url 签名 → 得到 sub
```

challenge 有效期 10 分钟，一次性使用。

---

## Token 使用

注册完成后，每次需要 token：

```
1. 构造 private_key_jwt（JWT，iss=sub，exp=now+5min，aud=<ISSUER_URL>/token）
2. POST /token → 得到 access_token（1小时）+ refresh_token（30天）
3. access_token 过期 → POST /token/refresh
4. refresh_token 过期 → 重新走 POST /token
```

access_token 是标准 JWT（EdDSA 签名），下游服务用 `/jwks.json` 验证，不需要联系 agent-identity。

---

## 开发

```bash
# 安装含 dev 依赖
uv sync --dev

# 跑测试
uv run pytest

# 跑测试（详细输出）
uv run pytest -v
```

---

## 私有部署注意事项

- 修改 `.env` 中的 `ISSUER_URL` 为你自己的域名
- 下游服务（如 agent-drop）配置 `TRUSTED_ISSUERS` 指向此 URL
- `iss` 不同即为不同信任域，数据完全隔离
