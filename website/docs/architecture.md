# 总体架构

> 本文是面向用户与贡献者的导读，完整设计见 [02-1 系统总体架构与技术选型](https://gitee.com/perry-space/study-club/blob/master/docs/02-系统架构/01-系统总体架构与技术选型.md)（Gitee）。

在「不做需要企业主体的能力 + 全部免费开放 + 项目开源 + 可自托管」的条件下，系统采用
**服务端权威 + 内容即仓库 + 单机自托管后端**的架构。

## 一、分层结构

```
┌──────────────────────────────────────────────────────────┐
│                用户设备（浏览器 / PWA）                     │
│   apps/web   Vue3 + Vite + Pinia                          │
│   手机 · iPad · 桌面   三档响应式 + PWA                     │
│   packages/core  ⭐ 零平台依赖 + 学科无关业务内核            │
│   算法 · stores · 类型 · 接口契约 · 能力开关 · 仓储接口      │
└──────────────────────────┬───────────────────────────────┘
                           │ HTTPS  /api/v1/*（同源反代）
╔══════════════════════════▼═══════════════════════════════╗
║  ✅ 云端后台（自托管 · Docker Compose 单机 · 服务器自有）   ║
║  FastAPI + MongoDB 7：内容读取 · 邀请码身份 · 儿童档案      ║
║  · 学习与复习（服务端算）· 学情报告 · 匿名统计 · 素材托管    ║
║  apps/admin  单管理员内容后台（Vue3 + Element Plus）        ║
╚═══════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════╗
║  ⛔ 掩 藏 层（需企业主体 · 写代码但开关关闭 · 不打包 · 不部署）║
║  手机号/微信账号 · 支付订阅 · 推送 · 小程序 · iOS/Android App ║
╚═══════════════════════════════════════════════════════════╝
```

> 三条线：① 前端 + 云端后台 + 管理后台 = **已实现**；② 学习数据与内容全部以服务端 MongoDB 为唯一真源；③ 掩藏层 = 需企业主体，**代码与契约在、开关全关、不打包**。

## 二、设计原则

| 原则 | 具体做法 |
| --- | --- |
| **服务端权威** | 学习数据、档案、进度、内容以服务端为唯一真源；浏览器只保留凭据与 UI 偏好 |
| **内容与代码分离** | 内容存放在独立的 `content/` 目录，以 JSON 分发；贡献者不需要懂前端 |
| **内容即仓库** | Git 承担内容管理职责（版本、评审、回滚、审计） |
| **仓储层抽象** | 业务只依赖接口与 API 客户端；数据访问统一走 `packages/core` |
| **能力开关默认关闭** | 需企业主体的能力代码存在但不可达、不打包、不可调 |
| **多端同源，内核复用** | 业务逻辑一律写在 `packages/core`（零平台依赖） |
| **单机可维护** | 组件数压到最少（FastAPI + MongoDB + nginx），不引 Redis / MQ / K8s / 微服务 |
| **契约先行** | 接口统一前缀 `/api/v1`，响应信封 `{code, message, data\|errors, request_id}` |

## 三、多端与复用边界

**当前交付**：手机 / iPad / 桌面浏览器三档响应式（Web + PWA）。
**预留形态**：微信小程序 + iOS / Android App —— 属**掩藏能力**（`enableMiniprogram` / `enableNativeApp`），开关关闭、不打包、不可达。

| 层 | 复用方式 |
| --- | --- |
| 算法、状态、类型、接口契约、能力开关 | ✅ 100% 复用（`packages/core`，零 DOM / 零平台 API） |
| 平台能力（录音、存储、通知） | ❌ 各端实现，通过接口注入（依赖倒置） |
| 视图层（页面与组件） | ❌ 各端重写 |

> ⚠️ **关键纪律**：`packages/core` 中一旦出现 `window`、`document`、`uni.xxx`，复用率会从 95% 直接掉到 0。

### 学科无关红线

产品后续可能从语文扩到英语、数学，因此 `packages/core` 还必须**与学科无关**。判据一句话：

> **这段逻辑换成英语单词还成立吗？** 成立 → 放 `packages/core`；不成立 → 放学科包。

学科走 **URL 路径** `/hanzi` `/english` `/math`，**不是子域**。

## 四、技术选型摘要

| 层 | 选型 |
| --- | --- |
| 前端 | Vue 3（Composition API）+ TypeScript + Vite + Pinia + vue-router + vite-plugin-pwa |
| 学生端 UI | 自研组件 + 设计变量包（`packages/tokens`） |
| 管理端 UI | Element Plus |
| 后端 | Python 3.12 + FastAPI + Uvicorn + Pydantic v2 |
| 数据库 | MongoDB 7（motor 异步），**服务端唯一真源** |
| 缓存 | ❌ 不采用 Redis（会话用 JWT + `devices` 吊销；内容量小可全量加载） |
| 部署 | Docker Compose 分服务独立编排 + `network_mode: host` + nginx 同源反代 |

## 五、内容分发：内容即仓库

| 环节 | 实现 |
| --- | --- |
| 维护 | 仓库内 JSON（`content/` 目录） |
| 校验 | JSON Schema + CI 脚本（拼音一致性、重复条目等） |
| 导入 | `scripts/seed`（按表拆分）或管理后台导入，upsert 幂等 |
| 下发 | `GET /content/bootstrap` 一次拉全量 + 子资源接口按需读取 |
| 版本 | `content_version` + `min_app_version` + `checksum` |
| 素材 | 服务端托管（`assets` 集合 + 落盘目录），内容文档只存引用 |

## 六、部署形态

单机 Docker Compose，1C1G 起；`docker compose up` 即起，密钥只走环境变量。

| 项 | 要求 |
| --- | --- |
| 编排 | `deploy/` 下四份**独立** compose：`mongo` / `api` / `web` / `admin` |
| 网络 | 均 `network_mode: host`，不做端口映射 |
| 前端托管 | `web` 容器用 nginx 托管构建产物 + `/api/` 同源反代到 `127.0.0.1:8000` |
| 成本 | 约 ¥0/月（服务器自有） |

## 七、目录结构（节选）

```
study-club/
├── apps/
│   ├── web/      # ✅ 学生端 + 家长视图（Vue3 + Vite）
│   ├── admin/    # ✅ 单管理员内容后台（Vue3 + Element Plus）
│   └── api/      # ✅ 云端后台（FastAPI + MongoDB）
├── packages/
│   ├── core/           # ⭐ 零平台依赖 + 学科无关业务内核
│   ├── subject-hanzi/  # 识字专属逻辑
│   └── tokens/         # 设计变量（断点 / 触控热区 / 色彩）
├── content/      # ⭐ 内容即仓库（JSON + Schema + sources.json）
├── deploy/       # ⭐ 分服务独立编排（mongo / api / web / admin）
├── scripts/      # ✅ 运维脚本（按用途与服务分目录）
└── docs/         # 完整设计文档
```

## 下一步

- 数据存哪、后端做什么 → [存储与后端策略](./storage.md)
- 注册登入与准入 → [邀请码身份与准入](./identity.md)
- 断点与降级规则 → [多端适配](./responsive.md)
