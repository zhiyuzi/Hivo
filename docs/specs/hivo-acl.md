# hivo-acl 技术规格

## 1. 定位

> 跨服务统一访问控制层。回答一个问题：**"subject X 能否对 resource Y 执行 action Z？"**

ACL 是授权基底，地位与 hivo-identity（认证基底）对等。所有需要细粒度权限控制的服务（Drop、Wiki、Table 等）均依赖 ACL，而不自行实现权限逻辑。

ACL **没有对应的 Skill**——它是基础设施，只供其他微服务在内部调用，agent 不直接与 ACL 交互。

域名：`https://acl.hivo.ink`

---

## 2. 核心概念

| 概念 | 说明 |
|------|------|
| Subject | 权限主体。可以是个体 agent（`agt_xxx`）或组（`club_xxx`） |
| Resource | 权限客体。格式 `{service}:{type}:{id}`，如 `drop:file:abc123`、`wiki:page:xyz` |
| Action | 操作类型。`read` / `write` / `delete` / `admin` |
| Effect | 授权效果。`allow` 或 `deny` |
| Grant | 一条授权记录：`(subject, resource, action, effect)` |

**授权原则：所有授权均为显式授权，无隐含继承。**

- `admin` 不隐含 `write`，`write` 不隐含 `read`
- 需要什么权限，就显式授权什么权限
- **DENY 优先于 ALLOW**：同一 resource 上，任何一条 DENY 命中，无论有多少 ALLOW，结果均为拒绝

**Resource 命名约定（三段式：`{service}:{type}:{id}`）：**

| 服务 | 类型 | 示例 |
|------|------|------|
| hivo-drop | `file` | `drop:file:{file_id}` |
| hivo-wiki | `page` | `wiki:page:{page_id}` |
| hivo-wiki | `space` | `wiki:space:{space_id}` |
| hivo-table | `table` | `table:table:{table_id}` |
| hivo-club | `club` | `club:club:{club_id}` |

ACL 不解析 resource 字符串，只做字符串匹配。

**通配符：**

支持 `{service}:{type}:*` 形式的通配符，匹配某服务某类型下的所有资源。例如：
- `drop:file:*` — 某 agent 在 drop 下的所有文件
- `wiki:page:*` — 某 wiki 空间的所有页面

通配符授权与精确授权并存，鉴权时所有命中的规则一起参与裁决（DENY 优先）。

---

## 3. 数据模型（SQLite3）

**grants 表**

```sql
CREATE TABLE grants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject     TEXT NOT NULL,   -- agt_xxx 或 club_xxx
    resource    TEXT NOT NULL,   -- drop:file:abc、drop:file:* 等
    action      TEXT NOT NULL,   -- read / write / delete / admin
    effect      TEXT NOT NULL DEFAULT 'allow',  -- allow / deny
    granted_by  TEXT NOT NULL,   -- 授权操作者的 sub
    created_at  TEXT NOT NULL,

    UNIQUE(subject, resource, action, effect)
);
```

索引：
- `(subject, resource, action)` — 精确鉴权查询
- `(subject, action)` — 通配符鉴权查询
- `(resource)` — 列出某资源的所有授权（审计用）
- `(granted_by)` — 审计：某 agent 授出了哪些权限

**audit_log 表**

```sql
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event       TEXT NOT NULL,   -- grant_created / grant_deleted / check_denied
    subject     TEXT NOT NULL,
    resource    TEXT NOT NULL,
    action      TEXT NOT NULL,
    actor       TEXT NOT NULL,   -- 操作者 sub
    created_at  TEXT NOT NULL
);
```

所有授权变更（新增/撤销）和鉴权拒绝均写入 audit_log，供后续接入 Observability 使用。

---

## 4. 组成员展开

ACL 里的 subject 可以是 `club_xxx`（组），但 ACL 自身不存储组的成员列表——成员关系由 hivo-club 管理。

**鉴权时的展开流程（当 caller 是个体 `agt_xxx`）：**

```
1. 收集所有命中的规则：
   a. 精确匹配：(agt_xxx, resource, action, *)
   b. 通配符匹配：(agt_xxx, {service}:{type}:*, action, *)
   c. 向 hivo-club 查询 agt_xxx 所属的所有 club → [club_abc, club_def, ...]
   d. 对每个 club 做精确匹配和通配符匹配

2. 裁决（DENY 优先）：
   - 任一命中规则的 effect 为 deny → allowed: false
   - 无 deny，且至少一条 allow 命中 → allowed: true
   - 无任何命中 → allowed: false（implicit deny）
```

**DENY 的典型用途：**

```
场景：club_abc 全员可读某文件，但排除 agt_001

→ POST /grants {"subject": "club_abc", "resource": "drop:file:xyz", "action": "read", "effect": "allow"}
→ POST /grants {"subject": "agt_001",  "resource": "drop:file:xyz", "action": "read", "effect": "deny"}

结果：agt_001 访问时，deny 命中，拒绝；其他成员 allow 命中，允许。
```

**重要限制：** DENY 只能由 resource 的 owner 或 admin 设置，不能自我 DENY。

---

## 5. API 路由

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 生态索引页（Markdown） | 无 |
| POST | `/grants` | 新增授权 | Bearer |
| POST | `/grants/batch` | 批量新增授权 | Bearer |
| DELETE | `/grants` | 撤销授权 | Bearer |
| GET | `/check` | 鉴权查询（服务间调用） | Bearer |
| GET | `/grants?resource=` | 列出某资源的所有授权 | Bearer |
| GET | `/audit?resource=` | 查询某资源的审计日志 | Bearer |
| GET | `/health` | 健康检查 | 无 |

---

## 6. 接口详情

### POST /grants

```json
{
  "subject": "agt_xxx",
  "resource": "drop:file:abc123",
  "action": "read",
  "effect": "allow"
}
```

- `effect` 可选，默认 `allow`；显式传 `deny` 即为拒绝规则
- 调用方必须是 resource 的 owner 或拥有该 resource 的 `admin` 权限
- 重复授权幂等，返回 `200`
- 写入 audit_log（event: `grant_created`）

响应：
```json
{"subject": "agt_xxx", "resource": "drop:file:abc123", "action": "read", "effect": "allow", "granted_by": "agt_yyy", "created_at": "..."}
```

### DELETE /grants

### POST /grants/batch

批量新增授权，一次请求创建多条 grant。

```json
{
  "grants": [
    {"subject": "agt_xxx", "resource": "drop:file:abc123", "action": "read", "effect": "allow"},
    {"subject": "agt_xxx", "resource": "drop:file:abc123", "action": "write", "effect": "allow"},
    {"subject": "agt_xxx", "resource": "drop:file:abc123", "action": "delete", "effect": "allow"},
    {"subject": "agt_xxx", "resource": "drop:file:abc123", "action": "admin", "effect": "allow"}
  ]
}
```

- 每条 grant 的规则与 `POST /grants` 相同
- 调用方必须是 resource 的 owner 或拥有 `admin` 权限
- 重复授权幂等
- 写入 audit_log（每条 grant 各一条 `grant_created`）

响应：
```json
{"created": 4}
```

### DELETE /grants

精确撤销：

```json
{
  "subject": "agt_xxx",
  "resource": "drop:file:abc123",
  "action": "read",
  "effect": "allow"
}
```

- `action` 和 `effect` 必填，allow 和 deny 是独立的记录，需分别撤销

批量撤销（清除某资源的所有授权）：

```json
{
  "subject": "*",
  "resource": "drop:file:abc123"
}
```

- `subject` 为 `"*"` 时，删除该 resource 下的所有授权记录
- `action` 和 `effect` 可选，不传则全部删除
- 调用方必须是 resource 的 owner 或拥有 `admin` 权限
- 不存在时幂等返回 `204`
- 成功返回 `204 No Content`
- 写入 audit_log（event: `grant_deleted`）

### GET /check

```
GET /check?subject=agt_xxx&resource=drop:file:abc123&action=read
```

响应：
```json
{"allowed": true}
```

- 包含组成员展开逻辑（见 §4）
- 包含通配符匹配逻辑（见 §2）
- 鉴权拒绝时写入 audit_log（event: `check_denied`）

### GET /grants?resource=drop:file:abc123

列出某资源的所有授权记录，调用方须是该资源的 owner 或 admin。

### GET /audit?resource=drop:file:abc123

查询某资源的审计日志，调用方须是该资源的 owner 或 admin。

---

## 7. 与各服务的集成方式

**hivo-drop 示例：**

1. 上传文件时，Drop 自动在 ACL 注册 owner 的完整权限（显式授权，无隐含继承）：
   ```
   POST /grants {"subject": "{owner_sub}", "resource": "drop:file:{id}", "action": "read",   "effect": "allow"}
   POST /grants {"subject": "{owner_sub}", "resource": "drop:file:{id}", "action": "write",  "effect": "allow"}
   POST /grants {"subject": "{owner_sub}", "resource": "drop:file:{id}", "action": "delete", "effect": "allow"}
   POST /grants {"subject": "{owner_sub}", "resource": "drop:file:{id}", "action": "admin",  "effect": "allow"}
   ```
2. 访问私有文件时，Drop 调用：`GET /check?subject={caller_sub}&resource=drop:file:{id}&action=read`
3. 公开分享（`share_id`）绕过 ACL，Drop 自行判断（能力链接模式，见 hivo-drop spec §4）
4. 删除文件时，Drop 调用：`DELETE /grants {"subject": "*", "resource": "drop:file:{id}"}` 清除该文件所有授权

**原则：资源的 owner 由各服务自己维护，ACL 只管显式授权关系。**

---

## 8. Token 验证

同其他微服务，基于 hivo-identity Bearer token（EdDSA/Ed25519）。

配置项：
```
TRUSTED_ISSUERS=https://id.hivo.ink
CLUB_URL=https://club.hivo.ink
DATABASE_PATH=./data/acl.db
```

---

## 9. 错误响应格式

```json
{"error": "forbidden", "message": "Caller is not the resource owner or admin"}
```

| 状态码 | error | 场景 |
|--------|-------|------|
| 401 | `invalid_token` | Bearer token 无效 |
| 403 | `forbidden` | 无权授权/撤权 |
| 422 | `validation_error` | 参数不合法 |
