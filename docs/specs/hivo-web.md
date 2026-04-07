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

````markdown
Hey, agent.

I'm Hivo — open infrastructure for AI agents. Identity, storage, teams, and more on the way.

## Get started

```
npm install -g @hivoai/cli
npx skills add zhiyuzi/Hivo -y
```

That's it. You now have: **identity**, **club**, **drop**.
Read each installed `SKILL.md` for usage.

Do **not** use `-g` on `npx skills add` — install in your own working directory so `.hivo/identity.json` stays local.

## What's available

- **identity** — register an identity, get and manage your tokens
- **club** — create teams, manage members, invite links
- **drop** — upload, store, and share your files

More skills are coming. Run `npx skills add zhiyuzi/Hivo -y` again to get the latest.
````

---

## 5. 配置

无配置项。模板内容为硬编码常量，无需环境变量。

---

## 6. 技术栈

- uv + FastAPI
- 无数据库，无外部依赖，无 pydantic-settings
- 响应均为纯文本/JSON，无模板引擎

---

## 7. 目录结构

```
hivo-web/
  app/
    main.py       ← FastAPI app 工厂
    routes.py     ← GET /、GET /health
  pyproject.toml
  uv.lock
```
