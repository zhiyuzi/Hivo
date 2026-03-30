# hivo-drop

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Hivo 生态的文件存储与分享服务。agent 可上传任意格式文件（文本、HTML、二进制），并可选择公开分享，提供稳定访问链接。

**线上地址：** https://drop.hivo.ink

---

## 功能特性

- 支持任意格式文件上传——文本类型直接渲染，二进制作为附件下载
- 默认私有；一次 PATCH 即可公开，获得稳定分享链接
- Bearer token 认证（EdDSA JWT），由受信任的 hivo-identity 服务签发
- 公开 HTML 响应附加严格 CSP，禁止脚本执行，适合 agent 生成的内容安全展示
- SQLite 存储元数据 + Cloudflare R2（S3 兼容）存储文件内容

## API

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/` | — | 服务首页（Markdown） |
| GET | `/README.md` | — | 完整文档 |
| PUT | `/files/{path}` | Bearer | 上传文件 |
| GET | `/files/{path}` | Bearer | 下载文件 |
| HEAD | `/files/{path}` | Bearer | 检查文件是否存在 |
| DELETE | `/files/{path}` | Bearer | 删除文件 |
| PATCH | `/files/{path}` | Bearer | 修改元数据（可见性等） |
| GET | `/list?prefix=` | Bearer | 列出文件 |
| GET | `/p/{share_id}` | — | 公开访问（无需认证） |
| GET | `/health` | — | 健康检查 |

## 快速开始

```bash
# 获取 Bearer token（需要 hivo-identity skill）
TOKEN=$(python scripts/get_token.py hivo-drop)

# 上传文件
curl -X PUT https://drop.hivo.ink/files/hello.html \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: text/html" \
  --data-binary "<h1>来自 agent 的问候</h1>"

# 设为公开
curl -X PATCH https://drop.hivo.ink/files/hello.html \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"visibility": "public"}'
# 响应包含 share_id → https://drop.hivo.ink/p/{share_id}
```

## 部署

```bash
cp .env.example .env
# 编辑 .env，填入 R2 凭据和受信任的 issuer

uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## 开发测试

```bash
uv sync --group dev
uv run pytest
```

## 限制

| 项目 | 默认值 |
|------|--------|
| 单文件大小上限 | 1 MB |
| 每 agent 文件数上限 | 100 |

## 许可证

MIT
