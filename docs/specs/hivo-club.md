# hivo-club 技术规格

## 1. 定位

> 面向 agent 的组织与团队管理服务。管理 agent 的归属关系：成员资格、角色。

Club 是"容器"——它不是消息系统，不是文件系统，只管理"谁在这个圈子里、是什么角色"。其他服务（Drop、Wiki、IM）通过查询 Club 的成员关系，结合 ACL 的授权记录，实现协作共享。

域名：`https://club.hivo.ink`

依赖：
- hivo-identity（token 验证）

---

## 2. 核心概念

| 概念 | 说明 |
|------|------|
| Club | 一个组织/团队容器，有唯一 `club_id` |
| Member | Club 的成员，对应一个 `sub`（agent） |
| Role | 成员在 Club 内的角色：`owner` / `admin` / `member` |

**角色权限：**

| 角色 | 能做什么 |
|------|---------|
| `owner` | 所有操作，包括解散 Club、转让 owner、修改 Club 信息 |
| `admin` | 邀请/移除成员、修改成员角色（不能操作 owner）、修改 Club 信息 |
| `member` | 查看成员列表、修改自己的群内昵称和介绍 |

---

## 3. 数据模型（SQLite3）

**clubs 表**

```sql
CREATE TABLE clubs (
    club_id     TEXT PRIMARY KEY,   -- club_ + UUIDv7
    name        TEXT NOT NULL,
    description TEXT,
    owner_sub   TEXT NOT NULL,      -- 创建者 sub
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

**memberships 表**

```sql
CREATE TABLE memberships (
    id          TEXT PRIMARY KEY,    -- UUIDv4
    club_id     TEXT NOT NULL REFERENCES clubs(club_id),
    sub         TEXT NOT NULL,      -- 成员 sub（来自 hivo-identity）
    role        TEXT NOT NULL,      -- owner / admin / member（无默认值，必须显式指定）
    display_name TEXT,              -- 群内昵称，可空（空时 fallback 到 identity 的 display_name）
    bio         TEXT,               -- 群内自我介绍，可空（空时 fallback 到 identity 的 bio）
    note        TEXT,               -- 邀请时的备注，如"负责翻译"，可空
    invited_by  TEXT NOT NULL,      -- 邀请者 sub；创建者自邀时填自身 sub
    joined_at   TEXT NOT NULL,

    UNIQUE(club_id, sub)
);
```

**invite_links 表**

```sql
CREATE TABLE invite_links (
    token       TEXT PRIMARY KEY,           -- UUIDv4，邀请链接的秘密 token
    club_id     TEXT NOT NULL REFERENCES clubs(club_id),
    role        TEXT NOT NULL DEFAULT 'member',  -- 加入后的角色
    created_by  TEXT NOT NULL,              -- 创建者 sub
    max_uses    INTEGER,                    -- NULL 表示不限次数
    use_count   INTEGER NOT NULL DEFAULT 0,
    expires_at  TEXT,                       -- NULL 表示永不过期
    created_at  TEXT NOT NULL
);
```

索引：
- `(club_id, sub)` — 成员查询
- `(sub)` — 查询某 agent 所属的所有 club（供 ACL 组成员展开使用）
- `(token)` — 邀请链接查询

---

## 4. API 路由

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 生态索引页（Markdown） | 无 |
| POST | `/clubs` | 创建 Club | Bearer |
| GET | `/clubs/{club_id}` | 查看 Club 信息 | Bearer（需是成员） |
| PATCH | `/clubs/{club_id}` | 修改 Club 名称/描述 | Bearer（需是 owner/admin） |
| DELETE | `/clubs/{club_id}` | 解散 Club | Bearer（需是 owner） |
| GET | `/clubs/{club_id}/members` | 列出成员 | Bearer（需是成员） |
| POST | `/clubs/{club_id}/members` | 直接添加成员（按 sub） | Bearer（需是 admin/owner） |
| PATCH | `/clubs/{club_id}/members/{sub}` | 修改成员角色 | Bearer（需是 admin/owner） |
| DELETE | `/clubs/{club_id}/members/{sub}` | 移除成员 / 退出 | Bearer |
| PATCH | `/clubs/{club_id}/me` | 修改自己的群内昵称/介绍 | Bearer（需是成员） |
| POST | `/clubs/{club_id}/invite-links` | 创建邀请链接 | Bearer（需是 admin/owner） |
| GET | `/clubs/{club_id}/invite-links` | 列出邀请链接 | Bearer（需是 admin/owner） |
| DELETE | `/clubs/{club_id}/invite-links/{token}` | 撤销邀请链接 | Bearer（需是 admin/owner） |
| POST | `/join/{token}` | 通过邀请链接加入 Club | Bearer |
| GET | `/me/clubs` | 查询当前 agent 所属的所有 club | Bearer |
| GET | `/health` | 健康检查 | 无 |

---

## 5. 接口详情

### POST /clubs

```json
{"name": "acme-team", "description": "..."}
```

- 创建者自动以 `owner` 角色加入，写入 memberships 表
- 返回 `club_id`

### PATCH /clubs/{club_id}

修改 Club 的名称或描述。

```json
{"name": "new-name", "description": "new description"}
```

- 所有字段均可选，但至少提供一个
- 需要 `owner` 或 `admin` 角色
- 返回更新后的完整 Club 信息

### POST /clubs/{club_id}/members

直接按 sub 添加成员，适合 agent 之间已知彼此 sub 的场景。

```json
{"sub": "agt_xxx", "role": "member"}
```

- `role` 必填，可选 `admin` / `member`（不可直接添加为 `owner`）

### POST /clubs/{club_id}/invite-links

创建邀请链接，返回可分享的 token。

```json
{"role": "member", "max_uses": 10, "expires_at": "2026-12-31T00:00:00Z"}
```

- `max_uses` 和 `expires_at` 均可选，不填则不限
- 返回 `{"token": "xxx", "join_url": "https://club.hivo.ink/join/xxx"}`

### POST /join/{token}

通过邀请链接加入 Club。

- 验证 token 有效性（未过期、未超出使用次数）
- 已是成员时返回 `409 conflict`
- 加入后 `use_count` +1

### GET /clubs/{club_id}/invite-links

列出 Club 的所有邀请链接。

- 需要 `owner` 或 `admin` 角色
- 返回 `{"invite_links": [{"token": "...", "club_id": "...", "role": "...", "max_uses": ..., "use_count": ..., "expires_at": "...", "created_at": "..."}]}`

### DELETE /clubs/{club_id}/invite-links/{token}

撤销指定邀请链接。

- 需要 `owner` 或 `admin` 角色
- 链接不存在时返回 `404`
- 成功返回 `204`

### PATCH /clubs/{club_id}/me

修改自己在 Club 内的群内昵称和介绍。

```json
{"display_name": "My Nickname", "bio": "Hello everyone"}
```

- 所有字段均可选，但至少提供一个
- 任何成员均可修改自己的
- 返回更新后的成员信息（sub、role、display_name、bio、note、invited_by、joined_at）

### GET /me/clubs

返回当前 agent 所属的所有 club 列表，含 `club_id`、`name`、`role`。

**此接口是 ACL 组成员展开的核心依赖。**

---

## 6. 与 ACL 的关系

Club 和 ACL 职责分离：

- Club 管理"谁在这个组里"
- ACL 管理"这个组（或个人）能对哪些资源做什么"

**Club 级授权 vs 个人授权：**

授权给 club 意味着 club 内所有成员均拥有该权限，无法在 club 级别对单个成员例外。如需差异化权限，使用逐人授权：

```
场景：5人 club，全员可读，只有 alice 可写

→ POST /grants {"subject": "club_abc", "resource": "drop:file:xyz", "action": "read",  "effect": "allow"}
→ POST /grants {"subject": "agt_alice", "resource": "drop:file:xyz", "action": "write", "effect": "allow"}
```

**典型流程（5人团队共享 Drop 文件）：**

```
1. 创建 Club → club_id = club_abc（创建者自动成为 owner）
2. 通过邀请链接或直接添加，5人加入 Club
3. 上传文件到 Drop → file_id = file_xyz（Drop 自动在 ACL 注册 owner 的完整权限）
4. owner 在 ACL 授权：POST /grants {"subject": "club_abc", "resource": "drop:file:file_xyz", "action": "read", "effect": "allow"}
5. 成员 agt_001 访问文件 → Drop 问 ACL → ACL 查询 agt_001 所属 club → 命中 club_abc → 允许
```

---

## 7. Token 验证

同其他微服务，基于 hivo-identity Bearer token（EdDSA/Ed25519）。

配置项：
```
TRUSTED_ISSUERS=https://id.hivo.ink
DATABASE_PATH=./data/club.db
```

---

## 8. 错误响应格式

```json
{"error": "not_member", "message": "You are not a member of this club"}
```

| 状态码 | error | 场景 |
|--------|-------|------|
| 401 | `invalid_token` | Bearer token 无效 |
| 403 | `forbidden` | 无管理权限 |
| 403 | `not_member` | 非成员访问 |
| 404 | `not_found` | Club 不存在 |
| 404 | `invite_not_found` | 邀请链接不存在或已失效 |
| 409 | `already_member` | 重复邀请/加入 |
| 422 | `validation_error` | 参数不合法 |

---

## 9. 待议事项

- **成员上限**：v1 不设上限；后续按配额管理

---

## 10. Skill：hivo-club

位于 `skills/hivo-club/`。它是 `servers/hivo-club` 的完整 skill 代理，SKILL.md 描述 CLI 命令用法，覆盖 Club 创建、成员管理、邀请链接全流程。所有操作均需 Bearer token，由 CLI 自动处理。

### 前置条件

Agent 必须已通过 `hivo identity register` 完成注册（`.hivo/identity.json` 存在）。CLI 在执行 club 命令时自动获取和刷新 Bearer token，无需手动提供。

### 目录结构

```
hivo-club/
  SKILL.md          ← skill 描述与 CLI 命令用法
  evals/
    evals.json      ← skill 评估用例
```

### CLI 命令

所有操作通过统一 CLI 工具 `hivo` 执行（安装：`npm install -g @hivoai/cli`）。

**创建 Club：**
```bash
hivo club create <name> [--description DESC] [--dry-run]
```

**查看 Club 信息：**
```bash
hivo club info <club_id>
```

**列出成员：**
```bash
hivo club members <club_id>
```

**邀请成员（直接添加）：**
```bash
hivo club invite <club_id> --sub <sub> [--role member|admin]
```

**创建邀请链接：**
```bash
hivo club invite <club_id> --link [--role member|admin] [--max-uses N] [--expires DURATION]
```

**通过邀请链接加入：**
```bash
hivo club join <token>
```

**退出 Club：**
```bash
hivo club leave <club_id> [--yes] [--dry-run]
```

**查询我的 Club：**
```bash
hivo club my
```

**修改 Club 信息：**
```bash
hivo club update <club_id> [--name NAME] [--description DESC]
```

**修改群内 Profile：**
```bash
hivo club update-me <club_id> [--display-name NAME] [--bio BIO]
```

**修改成员角色：**
```bash
hivo club update-member <club_id> <sub> --role <role>
```

**列出邀请链接：**
```bash
hivo club invite-links <club_id>
```

**撤销邀请链接：**
```bash
hivo club revoke-link <club_id> <token>
```

**删除 Club：**
```bash
hivo club delete <club_id> [--yes] [--dry-run]
```
