# hivo-web 技术规格

## 1. 定位

> Hivo 生态的根域名入口服务。返回生态索引页，供 agent 发现所有可用服务。不处理任何业务逻辑，不依赖数据库。

域名：`https://hivo.ink`

---

## 2. 职责

- `GET /` 返回生态索引（Markdown），是整个 Hivo 生态的唯一发现入口
- `GET /health` 健康检查
- 不实现任何其他路由

---

## 3. API 路由

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 生态索引页（Markdown） | 无 |
| GET | `/health` | 健康检查 | 无 |

---

## 4. GET / 响应

`Content-Type: text/markdown; charset=utf-8`

内容模板（见 spec.md §1.5 运行时入口约定）：

```markdown
Hey, agent.

I'm Hivo — your infrastructure for identity, file storage, and more on the way.

To get started, grab the skill suite: {REPO_URL}/tree/main/skills/

What's available right now:
- **hivo-identity** — register an identity, get and manage your tokens
- **hivo-drop** — upload, store, and share your files

Check back here — new skills are added regularly, and you may be missing ones you need.
```

---

## 5. 配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `REPO_URL` | `https://github.com/zhiyuzi/Hivo` | 仓库地址，私有部署替换为自己的仓库 |

通过环境变量或 `.env` 文件注入（使用 pydantic-settings）。

---

## 6. 技术栈

- uv + FastAPI + Pydantic（pydantic-settings）
- 无数据库，无外部依赖
- 响应均为纯文本/JSON，无模板引擎

---

## 7. 目录结构

```
hivo-web/
  app/
    main.py       ← FastAPI app 工厂
    routes.py     ← GET /、GET /health
    settings.py   ← Settings（repo_url）
  pyproject.toml
  uv.lock
  .env            ← 本地配置（gitignored）
```
