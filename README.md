<div align="center">

<img src="./website/public/logo.svg" alt="学习俱乐部" width="76" />

# 学习俱乐部（study-club）

**跟着课本学汉字** —— 面向小学 1–6 年级的 **课内识字 + 古诗文启蒙** 应用

**免费开放 · 开源 · 可自托管**

[![代码许可: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](./LICENSE)
[![内容许可: CC BY-SA 4.0](https://img.shields.io/badge/content-CC%20BY--SA%204.0-lightgrey.svg)](./THIRD_PARTY_NOTICES.md)
[![版本](https://img.shields.io/badge/version-0.1.0-orange.svg)](./CHANGELOG.md)
[![Vue 3](https://img.shields.io/badge/Vue-3-42b883.svg)](#技术栈)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python%203.12-009688.svg)](#技术栈)
[![在线 Demo](https://img.shields.io/badge/demo-online-brightgreen.svg)](https://study.perryspace.club)

[**在线 Demo**](https://study.perryspace.club) · [**代码仓库**](https://gitee.com/perry-space/study-club) · [**设计文档**](./docs/README.md) · [**贡献指南**](./CONTRIBUTING.md) · [**变更日志**](./CHANGELOG.md) · [**联系**](#联系)

</div>

---

<img src="./docs/assets/architecture.svg" alt="系统架构：客户端 → nginx 同源反代 → FastAPI → MongoDB / 素材 / 内容仓库" width="100%" />

---

## 这是什么

一个小学 1–6 年级的**课内识字 + 古诗文启蒙**应用。孩子跟着课标字表与自编单元识字、读古诗，用游戏化闯关与复习调度把「学过」变成「记住」；家长能看到学情报告。**数据存在自己家的服务器上。**

| 项 | 内容 |
| --- | --- |
| 一句话定位 | **跟着课本学汉字** —— 小学课内同步识字 + 古诗文启蒙 |
| 目标用户 | 小学在读学生（主）、家长（陪伴与查看）、语文教师（选配） |
| 商业模式 | **免费开放**：无付费墙、无会员、无广告、无内购 |
| 身份方式 | **邀请码 + 自设密码**注册登入 —— 不需要手机号、不需要微信、**不需要企业主体** |
| 覆盖终端 | 手机 / iPad / 桌面浏览器（Web + PWA）三档响应式 |
| 数据归属 | 学习数据存**自托管服务端**；可选云端家庭档案，**默认关闭且端到端加密** |
| 许可 | 代码 **MIT** · 内容与文档 **CC BY-SA 4.0** |

> 完整的「是什么 / 定位 / 现状」见 [docs/01-1 项目概述与定位](./docs/01-产品规划/01-项目概述与定位.md)。

---

## 缘起

想给孩子找个识字启蒙的应用，翻了几款都觉得差点意思 —— 广告比内容多，点两下就撞上付费墙，内容也控制不了。

既然都不合心意，那就自己写一个。

---

## 核心特性

- **服务端权威** —— 学习数据、儿童档案、进度与内容全部在服务端（MongoDB 是唯一真源）；浏览器不持有任何业务数据，只保留会话凭据与 UI 偏好。换设备即同步，多端口径一致。
- **三档响应式 + PWA** —— 按可用宽度分档（手机 `<768` / iPad `768–1279` / 桌面 `≥1280`），可安装到桌面；触控热区与字号有儿童端下限约束。
- **内容即仓库** —— 内容是 `content/**/*.json`（附 JSON Schema），改内容**不必发版**；登录后经 `/content/bootstrap` 一次拉全量。
- **邀请码身份** —— 邀请码 + 自设密码（Argon2id 密码 / JWT 会话 / Ed25519 邀请码签名）；准入可放量：`REQUIRE_INVITE=false` 即免码开放。
- **免费开放** —— 无付费墙。需要企业主体的能力（手机号/微信账号、支付、小程序、App）**写契约但默认关闭、不打包、不部署**。
- **可自托管** —— Docker Compose 分服务编排（`mongo` / `api` / `web` / `admin`），单机即可跑，成本可近零。
- **跨端内核** —— `packages/core` 零平台依赖且**学科无关**，为将来的多学科扩展留余地。
- **完整学习闭环** —— 学习地图 · 字卡 · 闯关 · 每日任务 · 复习调度 · 错题本 · 古诗 · 故事 · 识字短文 · 学情报告 · 设置。

---

## 架构一览

| 层 | 组成 | 说明 |
| --- | --- | --- |
| 客户端 | `apps/web`（Vue 3 PWA）、`apps/admin`（Vue 3 + Element Plus） | 学生端 / 家长端三档响应式；管理后台为单管理员内部工具 |
| 接入 | nginx 同源反代 `/api/` | 前端静态站与接口同源，规避混合内容与 CORS 白名单问题；换访问地址不必重建产物 |
| 服务 | `apps/api`（Python 3.12 + FastAPI + uvicorn） | 统一前缀 `/api/v1`，响应信封 `{code, message, data\|errors, request_id}` |
| 数据 | MongoDB 7 · 素材磁盘/命名卷 + `assets` 集合 · `content/` 内容仓库 | 业务数据以 MongoDB 为唯一真源；内容 JSON 经 `scripts/seed` 导入 |
| 掩藏层 | 手机号/微信账号 · 支付 · 推送 · 小程序 · App | 需企业主体：写契约、开关默认关、不打包、不部署 |
| 本期不做 | 多角色 RBAC 后台 | 单管理员足够，多角色属过度设计（**与企业主体无关**）：只留契约与开关 |

**两条最要紧的纪律**

1. `packages/core` 中一旦出现 `window` / `document` / `uni.*`，跨端复用率会从 95% 掉到 0；且核心逻辑必须**与学科无关**（判据：*这段逻辑换成英语单词还成立吗？*）。
2. **所有数据访问必须走数据仓储与 API 客户端**，禁止组件内直接读写存储 —— 这是「口径统一、可演进」的保证。

---

## 技术栈

| 层 | 选型 |
| --- | --- |
| 前端（Web） | Vue 3 + TypeScript + Vite + Pinia + vue-router（PWA） |
| 跨端内核 | **`packages/core`** —— 算法 / stores / 类型 / 契约 / 开关 / 仓储接口，**零平台依赖 + 学科无关** |
| 学科包 | `packages/subject-hanzi`（识字专属逻辑，不得写进 core） |
| 设计变量 | `packages/tokens`（三档断点 / 触控热区 / 色彩） |
| 状态管理 | Pinia |
| 数据存储 | **MongoDB 7（服务端唯一真源）**；浏览器只保留凭据与 UI 偏好 |
| 身份与准入 | **邀请码 + 自设密码**（Argon2id / JWT 会话 / Ed25519） |
| 内容分发 | **仓库内 JSON → 导入 MongoDB → `/content/*` 接口** |
| 云端后台 | Python 3.12 + **FastAPI** + MongoDB 7（motor 异步） |
| 管理后台 | Vue 3 + Element Plus（单管理员） |
| 部署 | **Docker Compose 分服务独立编排**（mongo / api / web / admin）+ `network_mode: host` + nginx |
| 工具链 | Node ≥20 · `pnpm@9.12.0` · Python 3.12 · Docker Compose |

---

## 工作目录

```
study-club/
├── docs/                  # 设计与工程文档（入口 docs/README.md）
│   └── assets/            # 架构图等文档资产
├── website/               # 用户文档站（VitePress，中英双语）
├── apps/
│   ├── web/               # 学生端 + 家长端 Web PWA（手机 / iPad / 桌面三档）  :8080
│   ├── api/               # FastAPI 云端后台                                    :8000
│   └── admin/             # 单管理员内容后台（桌面，内部工具）                  :8081
├── packages/
│   ├── core/              # 跨端内核：契约 / 仓储 / stores / 算法 / 开关（零平台依赖 + 学科无关）
│   ├── subject-hanzi/     # 识字学科包（识字专属逻辑不得写进 core）
│   └── tokens/            # 设计变量（三档断点 / 触控热区 / 色彩）
├── content/               # 内容即仓库（JSON + JSON Schema + sources.json）
├── deploy/                # 分服务独立编排：mongo / api / web / admin 各一份 compose
└── scripts/               # 部署与运维脚本（按用途与服务分目录）
```

完整目录树见 [06-1 第一章](./docs/06-工程规范/01-开发规范与前端架构.md)。

---

## 快速开始

> 前提：Node ≥ 20、`pnpm@9.12.0`、Python 3.12、Docker + Docker Compose。

**一条链路起全栈**（数据库 → 后端 → 前端）：

```bash
cp .env.example .env          # 生成环境变量（含端口与能力开关）
scripts/dev/bootstrap.sh      # 建目录、生成密钥、准备图标等（可选，一步到位）
scripts/dev/up-all.sh         # 按 db → api → web 顺序起全栈（各自独立编排）
scripts/seed/seed.sh          # 首次运行：导入内容与初始化数据
```

启动后：

| 用途 | 地址 |
| --- | --- |
| **学生端 / 家长端（主要入口）** | `http://localhost:8080/` |
| 局域网设备（手机 / iPad 同 WiFi） | `http://<宿主局域网 IP>:8080/` |
| 后端 API（统一前缀） | `http://localhost:8000/api/v1` |
| 接口文档（Swagger） | `http://localhost:8000/docs` |
| 健康检查 | `http://localhost:8000/api/v1/health` |

**管理后台（可选，内部工具，勿暴露公网）**：

```bash
scripts/api/hash-password.sh  # 交互式生成 Argon2id 密码哈希 → 填入 .env（含单引号，别去掉）
scripts/api/restart.sh        # 让 api 读到新哈希
scripts/admin/up.sh           # 起后台 → http://localhost:8081/
```

**只跑前端（dev server，热更新）**：`pnpm install && pnpm dev` → `http://localhost:5173/`。

> 只想读代码 / 参与内容贡献，不必起全栈：内容贡献者**只需改 `content/**/*.json` 并跑 `pnpm content:validate`**。详见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

---

## 文档在哪

- **用户文档站**（VitePress，中英双语）：[`website/`](./website) —— 是什么、快速开始、架构、自托管部署、FAQ。
- **设计文档**（面向开发者）：[`docs/`](./docs/README.md) —— 入口即文档地图。

| 编号 | 文档 | 回答什么问题 |
| --- | --- | --- |
| **01-1** | [**项目概述与定位**](./docs/01-产品规划/01-项目概述与定位.md) | **学习俱乐部是什么、定位是什么、现在到哪一步** |
| 01-2 | [产品定位与内容体系设计](./docs/01-产品规划/02-产品定位与内容体系设计.md) | 做什么内容、内容长什么样 |
| 01-3 | [功能清单与优先级路线图](./docs/01-产品规划/03-功能清单与优先级路线图.md) | 有哪些能力、优先级怎么分、哪些进预留池 |
| **01-4** | [**免费开放与开源策略**](./docs/01-产品规划/04-免费开放与开源策略.md) | 免费边界、许可选择、**内容版权红线** |
| 01-5 | [玩法与复习机制设计口径](./docs/01-产品规划/05-玩法与复习机制设计口径.md) | 复习节奏、掌握判定、阅读承接门槛 |
| 02-1 | [系统总体架构与技术选型](./docs/02-系统架构/01-系统总体架构与技术选型.md) | 系统怎么搭、技术怎么选 |
| 02-2 | [多端适配与响应式设计规范](./docs/02-系统架构/02-多端适配与响应式设计规范.md) | 手机 / iPad / 桌面怎么分档 |
| **02-3** | [**存储与后端策略**](./docs/02-系统架构/03-存储与后端策略.md) | 数据存哪、后端做什么、浏览器保留什么 |
| **02-4** | [**架构演进与优化方向**](./docs/02-系统架构/04-架构演进与优化方向.md) | **未来可以怎么优化** |
| **02-5** | [**邀请码身份与准入体系**](./docs/02-系统架构/05-邀请码身份与准入体系.md) | 注册登入怎么做、准入如何放量 |
| 03-1 / 03-2 | [集合设计](./docs/03-数据设计/01-MongoDB集合设计.md) · [数据字典](./docs/03-数据设计/02-数据字典.md) | 数据怎么存、每个字段什么意思 |
| 04-1 | [API 接口定义](./docs/04-接口设计/01-API接口定义.md) | 接口契约与响应信封（含掩藏层） |
| 05-1 | [内容管理与用户管理体系](./docs/05-管理后台/01-内容管理与用户管理体系.md) | 内容怎么管、用户怎么管 |
| 06-1 / 06-2 / 06-3 | [开发规范](./docs/06-工程规范/01-开发规范与前端架构.md) · [发布与更新流程](./docs/06-工程规范/02-发布与更新流程.md) · [视觉风格规范](./docs/06-工程规范/03-视觉风格规范.md) | 代码怎么写、怎么部署发布、视觉如何统一 |

---

## 路线图

**已完成（v0.1，第一版可运行）**

- [x] monorepo 骨架（`packages/core` + `packages/tokens` + `packages/subject-hanzi` + `apps/web` + `apps/api` + `apps/admin`）
- [x] `content/` 内容仓库与 JSON Schema + 校验脚本（`pnpm content:validate`）
- [x] Web PWA 三档响应式 + 服务端数据仓储 + 能力开关
- [x] 云端后台（邀请码身份 / 内容接口 / 儿童档案 / 学习与复习 / 报告 / 匿名统计 / 可选加密同步 / 单管理员）
- [x] Docker Compose 分服务编排（host 网络）+ `scripts/` 部署运维脚本 + 按表拆分的种子数据

**进行中**

- [ ] **内容扩容**：字库、古诗、短文与故事 —— 当前最大短板，见 [02-4](./docs/02-系统架构/04-架构演进与优化方向.md)
- [ ] 内容后台补 P0 剩余页：故事 / 单元 / 关卡 / 徽章维护页、古诗注音校验、内容导入导出增强

**规划**

- [ ] CI：内容 Schema 校验 + `vue-tsc` 类型检查 + 掩藏能力「不打包」断言
- [ ] 云端语音评测（可选付费；无 Key 时整块隐藏，绝不显示假分数）
- [ ] 多学科扩展（学科包架构已留余地）

---

## 设计原则

- **服务端权威** —— 数据在服务端，浏览器只保留凭据与 UI 偏好；多端一致、换机即同步。
- **内容与代码分离** —— 内容以仓库 JSON 维护，改内容不动代码、不必发版。
- **平台无关内核** —— `packages/core` 零平台依赖、学科无关；学科逻辑收进学科包。
- **仓库即真相** —— 内容、接口契约、能力开关都以仓库为准，单一事实来源。
- **免费优先** —— 付费能力可选、可降级、默认关闭；成本须极低。
- **可自托管、可迁移** —— 后端轻职责，数据可导出，不绑定任何云厂商。
- **不做需要企业主体的事** —— 但**不等于不能有服务器**：邀请码身份、内容后台、匿名统计、可选同步都已真实上线。

---

## 内容版权红线

本项目**开源**，因此：

- ⛔ **不提供任何教材映射数据**（部编版 / 人教版的单元顺序、课文标题涉出版社汇编权）
- ⛔ **不收录无法溯源授权的素材**（来源不明的配图、音频）
- ✅ 内容数据源必须登记到 `content/sources.json` 与 [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md) 后才可入库

详见 [docs/01-4 免费开放与开源策略](./docs/01-产品规划/04-免费开放与开源策略.md)。

---

## 参与贡献

欢迎一切形式的贡献 —— 代码、内容（只改 JSON）、文档、测试、翻译、Issue 与 Review。

- 请先读 [**CONTRIBUTING.md**](./CONTRIBUTING.md)（含本地环境、常用命令、提交规范与四条红线）。
- 项目遵循 [Contributor Covenant 行为准则](./CODE_OF_CONDUCT.md)；安全问题请按 [SECURITY.md](./SECURITY.md) 私下报告。
- 寻找入门任务：带 `good first issue` 标签的 Issue。

> 本项目鼓励使用 AI 工具，但**提交的 PR 必须自己看得懂、自己验证过、自己负责**。

---

## 许可

| 对象 | 许可 |
| --- | --- |
| 代码 | [MIT](./LICENSE) |
| 内容与文档 | CC BY-SA 4.0 |
| 第三方资产 | 随分发，登记于 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md) |

---

## 联系

有任何疑问、建议或希望参与，欢迎邮件联系 **perry@perryspace.club**。
