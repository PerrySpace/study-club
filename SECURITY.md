# 安全策略（Security Policy）

## 支持的版本（Supported Versions）

本项目当前处于初始版本，**`0.1.x` 系列正在维护中（actively maintained）**。

| 版本（Version） | 是否支持（Supported） |
| --- | --- |
| `0.1.x` | ✅ 维护中 |
| 更早版本 / 未发布分支 | ⛔ 不提供安全更新 |

## 如何报告漏洞（Reporting a Vulnerability）

> ⚠️ **请勿通过公开 Issue 报告安全漏洞（Please do NOT open a public issue）。**

公开 Issue 会让漏洞在修复前暴露给所有人。请改用**私密渠道**：

- 发送邮件至 **perry@perryspace.club**
- 邮件标题建议以 `[SECURITY]` 开头。

**我们会在 5 个工作日内初步回复（we will acknowledge within 5 business days）**，并在修复进展中与你保持沟通。这是一个个人业余维护的开源项目，无法承诺严格的 SLA，但会认真对待每一份报告。

## 报告时请提供（What to include）

为便于复现与定位，请在报告中尽量提供：

- **复现步骤（Steps to reproduce）**：清晰、可最小化的操作序列；
- **影响范围（Impact）**：漏洞可能导致什么后果、影响哪些用户或数据；
- **版本 / 环境（Version / Environment）**：项目版本、部署方式、相关配置（如 `REQUIRE_INVITE`、是否启用可选加密同步等），以及你观测到的现象。

如有 PoC、日志或截图，一并附上会很有帮助（请注意隐去真实用户数据与密钥）。

## 安全设计要点（Security Design Overview）

以下要点旨在帮助安全研究者快速定位关注面：

- **身份与准入（Identity & Access）**
  - 口令使用 **Argon2id** 哈希存储（`argon2-cffi`）；
  - 会话采用 **JWT access + refresh** 双令牌（默认 access 30 分钟、refresh 30 天，可配置）；
  - 邀请码采用 **Ed25519** 签名校验（公钥随代码公开，私钥仅签发方持有）；
  - 登录具备**失败锁定与限流**（连续失败阈值触发锁定，另有按窗口的速率限制）。
- **越权防护（Authorization）**
  - **儿童档案与学习数据按账号隔离**，数据访问经仓储与 API 客户端统一收口，避免越权读写他人数据。
- **素材上传（Asset Upload）**
  - 采用 **MIME 白名单**（`ASSET_ALLOWED_MIMES`）+ **体积上限**（`ASSET_MAX_BYTES`，默认 10 MB）双重限制。
- **可选端到端加密同步（Optional End-to-End Encrypted Sync）**
  - 采用**口令派生密钥**：加密在客户端完成，**服务端只存密文，服务端不持有解密密钥**。
- **依赖与密钥管理（Dependencies & Secrets）**
  - 密钥、口令哈希等一律走**环境变量**；
  - `.env` / `*.key` / `*.pem` **不入库**（已在 `.gitignore` 中排除）。

## 范围之外（Out of Scope）

以下问题**不属于**本项目的安全漏洞处理范围：

- 需要攻击者**已完全控制用户设备或浏览器**才能实施的问题（如已中木马、已安装恶意扩展）；
- **自托管部署者自身的错误配置**，例如：
  - 把 MongoDB 绑定到 `0.0.0.0` 且**未配置任何鉴权**；
  - 把**管理后台暴露到公网**（该后台是单人使用的内部工具，设计上不应公网可达）。

部署安全由部署者负责，请参考 [`README.md`](./README.md) 与 [`docs/`](./docs/README.md) 中的部署说明，做好网络边界与访问控制。

---

感谢你帮助让这个项目对孩子们更安全。
