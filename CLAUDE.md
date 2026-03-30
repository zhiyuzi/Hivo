# Hivo

面向 agent 的开放基础设施。

## 仓库结构

```
hivo/
  servers/
    hivo-identity/             ← 微服务：身份注册、token 签发
    hivo-drop/                 ← 微服务：文件存储与公开分享
  skills/
    hivo-identity/             ← Skill：agent-identity 的完整 skill 代理，覆盖注册、鉴权、token 管理全流程
    hivo-drop/                 ← Skill：hivo-drop 的完整 skill 代理，覆盖上传、下载、分享、visibility 管理全流程
  docs/                        ← 技术规格文档
```

## 技术规格

实现前必读：[docs/spec.md](docs/spec.md)

## 技术栈

- 微服务：uv + FastAPI + SQLite3 + Pydantic
- hivo-drop 额外依赖 Cloudflare R2（S3 兼容 API）
- Skill：纯 Python 脚本，无框架依赖

## 域名

- 根入口：https://hivo.ink
- hivo-identity：https://id.hivo.ink
- hivo-drop：https://drop.hivo.ink

## 开发约定

- monorepo，所有代码在同一 git 仓库，servers/ 和 skills/ 各自独立管理依赖
- 所有 ID 格式：sub 用 `agt_` + UUIDv7，kid 用 UUIDv4，share_id 用 UUIDv4
- 错误响应统一格式：`{"error": "snake_case_code", "message": "..."}`
- 认证方式：Bearer JWT（EdDSA/Ed25519 签名）
- 不使用密码，agent 用公私钥体系注册和鉴权
