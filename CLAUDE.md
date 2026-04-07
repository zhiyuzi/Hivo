# Hivo

面向 agent 的开放基础设施。

## 仓库结构

```
hivo/
  servers/
    hivo-identity/             ← 微服务：身份注册、token 签发、profile 修改
    hivo-acl/                  ← 微服务：跨服务统一访问控制（授权基底）
    hivo-club/                 ← 微服务：组织/团队管理、成员资格与角色
    hivo-drop/                 ← 微服务：文件存储与公开分享
    hivo-web/                  ← 微服务：根域名入口，生态索引页
  cli/                         ← Go CLI 工具（hivo），封装所有微服务 API
  npm/                         ← npm 分发包（@hivoai/cli）
  skills/
    hivo-identity/             ← Skill：hivo-identity 的完整 skill 代理，描述 CLI 命令用法
    hivo-club/                 ← Skill：hivo-club 的完整 skill 代理，描述 CLI 命令用法
    hivo-drop/                 ← Skill：hivo-drop 的完整 skill 代理，描述 CLI 命令用法
  .github/workflows/           ← CI/CD（交叉编译、GitHub Release、npm 发布）
  docs/                        ← 技术规格文档
```

## 技术规格

实现前必读：[docs/spec.md](docs/spec.md)

## 技术栈

- 微服务：uv + FastAPI + SQLite3 + Pydantic
- hivo-drop 额外依赖 Cloudflare R2（S3 兼容 API）
- CLI：Go + Cobra，分发方式为 npm（`@hivoai/cli`）+ GitHub Releases 二进制
- Skill：SKILL.md 描述 CLI 命令用法，供 AI Agent 加载

## 域名

- 根入口：https://hivo.ink
- hivo-identity：https://id.hivo.ink
- hivo-acl：https://acl.hivo.ink
- hivo-club：https://club.hivo.ink
- hivo-drop：https://drop.hivo.ink

## 开发约定

- monorepo，所有代码在同一 git 仓库，servers/ 和 skills/ 各自独立管理依赖
- 所有 ID 格式：sub 用 `agt_` + UUIDv7，kid 用 UUIDv4，share_id 用 UUIDv4
- 错误响应统一格式：`{"error": "snake_case_code", "message": "..."}`
- 认证方式：Bearer JWT（EdDSA/Ed25519 签名）
- 不使用密码，agent 用公私钥体系注册和鉴权
