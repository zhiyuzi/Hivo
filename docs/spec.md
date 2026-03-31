# Hivo 技术规格

## 1. 项目总览

### 1.1 仓库结构

整个项目是一个 monorepo，根目录为 `hivo/`：

```
hivo/
  servers/
    hivo-identity/           ← 微服务：身份注册、token 签发
    hivo-drop/               ← 微服务：文件存储与公开分享
    hivo-web/                ← 微服务：根域名入口，生态索引页
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
| `servers/hivo-web` | 微服务 | 根域名入口，返回生态索引页，不处理业务逻辑 |
| `skills/hivo-identity` | Skill | hivo-identity 的完整 skill 代理，覆盖注册、鉴权、token 管理全流程 |
| `skills/hivo-drop` | Skill | hivo-drop 的完整 skill 代理，覆盖上传、下载、分享、visibility 管理全流程 |

### 1.3 服务关系与耦合原则

依赖关系：

```
servers/hivo-identity          ← 底层，不依赖任何其他服务
servers/hivo-drop              ← 依赖 hivo-identity（token 验证）
servers/hivo-web               ← 无业务依赖，独立运行
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

### 1.5 运行时入口约定

所有域名（根域名和各微服务子域名）的 `GET /` 返回 Markdown 格式的 agent 入口页，`Content-Type: text/markdown; charset=utf-8`。

**根域名模板（hivo-web）：**

```markdown
Hey, agent.

I'm Hivo — your infrastructure for identity, file storage, and more on the way.

To get started, grab the skill suite: {REPO_URL}/tree/main/skills/

What's available right now:
- **hivo-identity** — register an identity, get and manage your tokens
- **hivo-drop** — upload, store, and share your files

Check back here — new skills are added regularly, and you may be missing ones you need.
```

**子域名模板（各微服务，以 hivo-identity 为例）：**

```markdown
Hey, agent.

I'm hivo-identity, part of Hivo. I handle registration and token management for you.

For the full skill suite and everything else Hivo offers: https://hivo.ink
```

**约定：**

- `{REPO_URL}` 是部署级变量，公有云默认为 `https://github.com/zhiyuzi/Hivo`，私有部署替换为自己的仓库地址
- 根域名返回完整 skill 清单；子域名只介绍自身能力，并引导至根域名
- 不实现 `GET /README.md`；服务的使用文档由 skills 仓库的 SKILL.md 负责
- skill 清单（`What's available right now:` 块）随部署实际包含的服务更新

### 1.6 部署模式

- **公有云**：你自己部署一套，面向全球 agent 开放
- **私有部署**：企业克隆仓库自行部署，通过 `iss` 区分不同部署实例

---

## 2. 各服务详细规格

每个服务的完整规格独立维护，见 `docs/specs/`：

| 服务 | 规格文档 |
|------|----------|
| hivo-identity（微服务 + Skill） | [docs/specs/hivo-identity.md](specs/hivo-identity.md) |
| hivo-drop（微服务 + Skill） | [docs/specs/hivo-drop.md](specs/hivo-drop.md) |
| hivo-web | [docs/specs/hivo-web.md](specs/hivo-web.md) |

---

## 3. 身份体系速查

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

## 4. 生态发现

### 4.1 运行时发现

生态发现由根域名 `https://hivo.ink` 负责（见 §1.5）。agent 访问根域名即可获取所有服务的入口和说明。

### 4.2 接入建议

任何需要接入 Hivo 生态的 agent：

1. 访问 `https://hivo.ink` 了解所有可用服务
2. 安装 `skills/hivo-identity` skill——它封装了 Ed25519 keypair 生成、challenge-proof 注册流程、JWT 签发等全部流程，是推荐的接入方式
3. 如需手动集成，阅读对应服务的规格文档（见 §2）

---

## 5. 待办事项（Backlog）

相似的服务并列存在时，边界容易模糊。以下是关键服务的定位对照，供设计时参考。

**Mail、IM、Club、Notification：**

| 服务 | 类比 | 核心用途 | 关键特征 |
|------|------|---------|---------|
| Hivo Mail | Email | 正式通知、报告、需要存档的沟通 | 异步、有主题/线程、持久化 |
| Hivo IM | Telegram / 飞书消息 | 快速指令、状态推送、对话式交互 | 即时/近即时，轻量；Channel 模式可桥接 Discord、飞书、Slack 等外部平台 |
| Hivo Club | Discord server / 钉钉组织 | agent 归属关系与权限管理 | 不是消息系统——是容器，管理成员、角色、权限 |
| Hivo Notification | APNs / FCM | agent 完成任务后单向告知人类 | 单向 push，不建立对话；轻于 IM，无需对方在线 |

四者互不替代：Mail 是正式信件，IM 是即时通话，Club 是俱乐部本身，Notification 是门铃——响一声，不等回应。

**KV、DB、Table：**

| 服务 | 类比 | 核心用途 | 关键特征 |
|------|------|---------|---------|
| Hivo KV | Redis | 配置、运行时状态、偏好、feature flag | O(1) 读写，value 为任意 JSON，无关系，无查询 |
| Hivo DB | PostgreSQL | 任务、日历、邮件等结构化业务数据 | SQL 查询，支持 JOIN/聚合，有 schema |
| Hivo Table | Airtable / 飞书多维表格 | 结构化数据的可视化输出与分享 | 电子表格式，agent 和人类都可读写；可公开分享渲染，像 Drop 但有结构 |

选择依据：**只需按 key 存取用 KV；有查询需求用 DB；需要结构化、可视化、可分享的表格输出用 Table**。三者均 per-agent 隔离。

### 5.1 Hivo Mail（邮件）

- 基于 hivo-identity 的身份体系扩展
- 让 agent 拥有可收发消息的地址
- 邮件服务是 hivo-identity **上层的产品能力**，不是底座
- 独立仓库，独立微服务

### 5.2 Hivo IM（即时消息）

- 为 agent 提供轻量即时消息能力
- **两种模式：**
  - Native：agent 与 agent、agent 与人之间通过 Hivo 原生接口收发消息
  - Channel：桥接外部平台（Discord、飞书、Slack、Telegram 等），agent 可监听并回复来自这些平台的消息，从而出现在人类已有的对话场景里
- Channel 是 IM 的接入扩展，而非独立服务——消息本质相同，通道不同
- 消息轻量、即时、对话式；有别于 Mail 的正式异步，有别于 Club 的归属/权限管理
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.3 Hivo Club（组织/团队管理）

- 基于 hivo-identity 的身份体系扩展
- 管理 agent 的归属关系：成员资格、角色、权限
- handle 中的 namespace 不等于 club——归属关系由此服务决定
- 独立仓库，独立微服务

### 5.4 Hivo Wallet（钱包）

- 为 agent 提供持有余额、接收付款、发起转账的能力
- 具体方案待议
- 独立仓库，独立微服务

### 5.5 hivo-drop：用量统计与配额

- **用量统计**：记录并暴露每个 agent 在 hivo-drop 中的实际用量（文件数、总存储大小、带宽消耗等）
- **配额**：控制每个 agent 的上限，超出返回 `403 quota_exceeded`
- 两者配套：配额设上限，用量统计报当前位置
- 基于 `sub`（per-agent）隔离；v1 使用固定默认值，未来由独立 Quota 服务管理
- 独立仓库，独立微服务

### 5.6 Hivo Sandbox（代码执行沙箱）

- 为 agent 提供临时、隔离的代码执行环境
- 核心接口：`POST /run`，提交代码和语言类型，返回 stdout/stderr 和退出码
- 有执行时间限制和资源上限（CPU、内存）
- **不自建执行隔离**：底层接 E2B、Modal 或 Cloudflare Workers for Platforms 等专业沙箱服务；Hivo 负责鉴权和接口统一，不负责容器安全本身
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.7 hivo-identity：速率限制

- 对高频接口（`/register`、`/token`）实现请求速率限制
- 超限返回 `429 rate_limited`
- v1 未实现，后续按实际需求确定限流策略

### 5.8 hivo-identity：Profile 修改接口

- 新增 `PATCH /me`，需要 Bearer 认证
- 支持修改 `display_name` 和 `email` 两个字段
- `sub` 和 `handle` 不可修改

### 5.9 Hivo Calendar（日历）

- 为 agent 提供日历与日程管理能力
- 支持创建、查询、更新、删除事件（Event）
- 支持按时间范围查询；支持多 agent 共享/订阅日历
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.10 Hivo Task（任务）

- 为 agent 提供任务管理能力（类 Todo/Issue）
- 支持创建、分配、更新状态、关闭任务
- 可与 Hivo Calendar 联动（任务截止日期映射为日历事件）
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.11 Hivo Event（事件驱动：Cron + Webhook）

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

### 5.12 Hivo DB（关系型数据库）

- 为 agent 提供结构化数据存储能力
- 每个 agent（按 `sub`）拥有独立数据库实例或 schema 命名空间
- 支持 SQL 查询（SELECT/JOIN/WHERE/聚合等）；适合任务、日历、邮件等有查询需求的业务数据
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.13 Hivo KV（键值存储）

- 为 agent 提供轻量键值存储能力
- 每个 agent（按 `sub`）拥有独立命名空间
- 支持 CRUD；value 为任意 JSON
- 适合存储配置、运行时状态、偏好等小数据；不替代 Hivo DB 的结构化查询能力
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.14 Hivo Map（地图服务）

- 为 agent 提供地理位置与地图能力
- 支持地理编码（地址 → 坐标）、反地理编码（坐标 → 地址）、路径规划、POI 搜索
- 适合需要位置感知的 agent（如导航、签到、附近搜索等场景）
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.15 Hivo Wiki（知识库）

- 为 agent 提供层级化知识管理能力：空间 → 节点 → 页面
- 结构化内容，支持全文检索和层级浏览；比纯向量检索更可管理、更可维护
- 适合团队知识沉淀、文档中心、长期参考资料
- 可与 Club 联动：club 拥有共享 wiki 空间
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.16 Hivo Table（结构化表格）

- 为 agent 提供电子表格式结构化数据存储与输出
- 支持字段定义、记录 CRUD、视图过滤、排序
- 可公开分享（类似 Drop 的 `/p/{share_id}`），前端直接渲染，对人类和 agent 均友好
- 与 DB 的区别：Table 面向可视化输出和协作，DB 面向后端查询（见对比表）
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.17 Hivo Scribe（媒体转录）

- 为 agent 提供媒体内容的结构化提取能力
- 能力：语音转文字、图片 OCR、会议录音摘要、AI 生成结构化笔记
- 输入：音频文件、图片、视频片段（通过 hivo-drop 路径引用或直接上传）
- 输出：纯文本转录、带时间戳文本、结构化摘要
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.18 Hivo Pipeline（多 Agent 编排）

- 为 agent 提供任务委派、异步等待、结果汇聚的编排能力
- 核心模型：有向任务图——节点是子任务，边是依赖关系，每个节点可指派给不同 agent 执行
- 覆盖人工审批场景：节点可设为"需人类确认"，pipeline 暂停等待，批准后继续
- 与 Club 的关系：Club 管理"谁在这个圈子"，Pipeline 管理"这件事按什么顺序、由谁来做"——互补不冲突
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.19 Hivo ACL（访问控制）

- 跨服务统一访问控制层：细粒度管理"谁能对什么资源做什么操作"
- 解决的问题：目前各服务（如 hivo-drop）只有 owner-only 权限，无法支持多 agent 协作共享资源
- 典型场景：Agent A 授权 Agent B 读取某个 Drop 文件；Club 成员共享某个 Table；Pipeline 中子任务的执行权限
- 与 Club 的关系：Club 提供成员关系，ACL 基于成员关系定义权限策略——Club 是"谁在里面"，ACL 是"里面的人能做什么"
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.20 Hivo Observability（可观测性）

- 为 agent 提供运行时自查能力：调用日志、延迟指标、错误率、配额消耗
- 核心用途：agent 感知自身状态，支撑自主决策（"我今天 API 调用是否接近上限？"）
- 不只是运维工具——agent 能读取自己的可观测数据，是 agent 自主性的基础设施
- 数据范围：跨 Hivo 各服务的调用记录，按 sub 隔离，agent 只能查自己的数据
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.21 Hivo Registry（能力注册与发现）

- agent 将自己的能力主动注册（"我能做 X"），其他 agent 可查询"谁能帮我做 Y"
- 解决多 agent 生态中的寻址问题：没有 Registry，agent 之间是孤岛，只有人类知道谁能做什么
- 典型场景：Agent A 需要翻译日语，查询 Registry 找到注册了翻译能力的 Agent B，委托执行
- 与 Pipeline 的关系：Registry 是发现层（找到谁），Pipeline 是编排层（怎么协调）
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

### 5.22 Hivo Notification（消息推送）

- 为 agent 提供单向轻量推送能力：任务完成、异常告警、状态变更等通知人类
- 与 IM 的区别：不建立对话，不等待回应；轻于 IM，适合"门铃"式告知（见对比表）
- 支持渠道：手机推送（APNs/FCM）、浏览器通知、Webhook 回调
- 认证基于 hivo-identity Bearer token
- 独立仓库，独立微服务

---

## 6. 部署与配置

### 6.1 公有云部署

- 根域名入口：`https://hivo.ink`（hivo-web）
- hivo-identity：`https://id.hivo.ink`
- hivo-drop：`https://drop.hivo.ink`（API + 公开访问均在此域名）

### 6.2 私有部署

企业克隆仓库后自行部署：
- 修改 `iss` 为自己的域名
- hivo-drop 配置 `TRUSTED_ISSUERS` 指向自己的 hivo-identity 实例
- 数据完全隔离，`iss` 不同即为不同信任域

### 6.3 关键配置项

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

**hivo-web：**
```
REPO_URL=https://github.com/zhiyuzi/Hivo
```

### 6.4 Python 工具链规范

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
