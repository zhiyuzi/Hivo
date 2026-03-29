# AgentInfra

面向 agent 的开放基础设施。

## 仓库结构

```
agentinfra/
  agent-identity/             ← 微服务：身份注册、token 签发
  agent-drop/                 ← 微服务：文件存储与公开分享
  agentinfra/                 ← Skill：生态发现入口
  agent-identity-credential/  ← Skill：持有 agent 身份凭据
  docs/                       ← 技术规格文档
```

## 技术规格

实现前必读：[docs/spec.md](docs/spec.md)

## 技术栈

- 微服务：FastAPI + SQLite3 + Pydantic
- agent-drop 额外依赖 Cloudflare R2（S3 兼容 API）
- Skill：纯 Python 脚本，无框架依赖

## 域名

- 根入口：https://agentinfra.cloud
- agent-identity：https://id.agentinfra.cloud
- agent-drop：https://drop.agentinfra.cloud

## 开发约定

- 每个子目录是独立 git 仓库，不共享依赖
- 所有 ID 格式：sub 用 `agt_` + UUIDv7，kid 用 UUIDv4，share_id 用 UUIDv4
- 错误响应统一格式：`{"error": "snake_case_code", "message": "..."}`
- 认证方式：Bearer JWT（EdDSA/Ed25519 签名）
- 不使用密码，agent 用公私钥体系注册和鉴权
