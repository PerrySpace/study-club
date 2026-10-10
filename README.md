# study-club

> 面向小学阶段的游戏化识字系统 —— **免费开放、本地优先、可自托管、面向开源**
>
> 代码许可 **MIT** · 内容许可 **CC BY-SA 4.0**

⚠️ **当前阶段：第一版可运行（v0.1）。** 设计文档已定稿（15 份 / 约 6,650 行），
monorepo 骨架、内容包、云端后台（FastAPI + MongoDB）、Web PWA 三档响应式前端、
单管理员内容后台（`apps/admin`）与 Docker Compose 分服务编排均已落地，
可直接本地起全栈联调 —— 见 **[快速开始](#快速开始本地测试)**。

> `study-club` 是**仓库代号**（不涉及商标，可自由使用），与产品中文名**解耦**；代号不得当作产品名对外使用。对外命名前请自行完成一遍商标与同名排查。

---

## 缘起

闲下来想给孩子找个识字启蒙的应用，翻了几款都觉得差点意思 —— 广告比内容多，点两下就撞上付费墙，内容也控制不了。

既然都不合心意，那就自己写一个。于是花两天时间，手搓了这个简易版。

---

## 这是什么

一个小学 1–6 年级的**课内识字 + 古诗文启蒙**应用。

| 项 | 内容 |
| --- | --- |
| 目标用户 | 小学在读学生（主）、家长（陪伴与查看）、语文教师（选配） |
| 商业模式 | **免费开放**：无付费墙、无会员、无广告、无内购 |
| 身份方式 | **邀请码注册登入**（邀请码 + 自设口令）——不需要手机号、不需要微信、**不需要企业主体** |
| 当前覆盖终端 | 手机 / iPad / 桌面浏览器（Web + PWA）三档响应式 |
| 数据归属 | 默认只存用户设备（IndexedDB）；可选云端家庭档案，**默认关闭且默认端到端加密** |

**技术上它是什么：** 一个**本地优先（Local-First）**应用——不连后端时功能完整；内容以**仓库内 JSON** 分发（改内容不必发版）；需要企业主体的能力（手机号/微信账号、支付、小程序、App）**写契约但默认关闭、不打包、不部署**（"掩藏"）。

---

## 快速开始（本地测试）

```bash
cp .env.example .env          # 首次：生成环境变量（含端口与开关）
scripts/dev/bootstrap.sh      # 建目录、生成密钥、准备图标等（可选，一步到位）
scripts/dev/up-all.sh         # 按 db → api → web 顺序起全栈（各自独立编排）
scripts/seed/seed.sh          # 首次运行：导入初始化数据（按表/功能拆分）

# 管理后台（可选，内部工具）：须先在 .env 填 ADMIN_PASSWORD_HASH
scripts/api/hash-password.sh  # 交互式生成 Argon2id 口令哈希 → 填入 .env
scripts/api/restart.sh        # 让 api 读到新哈希
scripts/admin/up.sh           # 起后台 → http://localhost:8081/
```

> 四个服务**各自独立编排**（`deploy/mongo`、`deploy/api`、`deploy/web`、`deploy/admin` 四份 compose），
> 均使用 `network_mode: host` —— 容器直接占用宿主端口，**不做端口映射**。
> `scripts/dev/up-all.sh` 只是按依赖顺序依次调用它们，不改变「单独构建」的设计。
> 管理后台**不在 `up-all.sh` 的默认链路里**（它是内部工具，建议按需启动）。

### 访问地址

| 用途 | 地址 | 端口来源 |
| --- | --- | --- |
| **学生端 / 家长端（主要入口）** | `http://localhost:8080/` | `WEB_PORT` |
| 局域网设备（手机 / iPad 同 WiFi） | `http://<宿主局域网 IP>:8080/` | `WEB_PORT` |
| **管理后台（单管理员，内部工具）** | `http://localhost:8081/` | `ADMIN_PORT` |
| 后端 API | `http://localhost:8000/api/v1` | `API_PORT` |
| 接口文档（Swagger） | `http://localhost:8000/docs` | `API_PORT` |
| 健康检查 | `http://localhost:8000/api/v1/health` | `API_PORT` |
| MongoDB | `mongodb://localhost:27017/study_club` | `MONGO_PORT` |

> ⚠️ **管理后台必须先配置口令才能用**：`/admin/login` 在 `ADMIN_PASSWORD_HASH` 为空时
> 直接返回 `FEATURE_DISABLED`。生成并填入：
>
> ```bash
> scripts/api/hash-password.sh          # 交互式输入口令，输出一行可直接粘贴的配置
> # 把那一行整行贴进 .env（⚠️ 含单引号，别去掉），然后重启 api：
> scripts/api/restart.sh
> scripts/admin/up.sh                   # 起后台（→ 8081）
> ```
>
> ⚠️ **那一行的单引号不能去掉**：Argon2 哈希含大量 `$`，Docker Compose 的 dotenv
> 解析未加引号的值时会把 `$m`、`$xxxx` 当变量引用替换成空串，哈希被改坏，
> 症状是「口令明明对，却一直返回 `40301 管理员口令不正确`」。
>
> 管理后台是**单人使用的内部工具**（`05-1 §1.3`），**不要暴露到公网**；不用时
> `scripts/admin/down.sh` 关掉即可。

**查本机局域网 IP**（手机 / iPad 测试用）：

```bash
ipconfig getifaddr en0        # macOS Wi-Fi；有线为 en1 或 bridge0
```

> ⚠️ 手机连不上时按这个顺序查：① 是否与电脑同一 WiFi；② 容器是否 `network_mode: host`
> （host 网络下服务监听 `0.0.0.0`，无需额外绑定）；③ macOS 系统设置 → 网络 → 防火墙是否放行。
>
> 只测前端、不起容器时可用 dev server：`scripts/web/dev.sh` → `http://<局域网 IP>:5173/`
> （`vite.config.ts` 已设 `server.host: true`，否则局域网设备连不上）。

### 常用运维脚本（按用途与服务分目录）

```
scripts/
├── lib/common.sh      # 公共函数（日志 / 路径 / 环境加载）
├── db/                # start stop reset backup restore shell logs init-indexes
├── api/               # build up down logs restart hash-password gen-invite-keys issue-invites
├── web/               # dev build up down logs
├── admin/             # dev build up down logs（管理后台，建议按需启动）
├── seed/              # seed.sh + data/*.json（每张表/每个功能一个文件）
├── content/           # 内容构建、Schema 校验、清单生成
└── dev/               # up-all / down-all / status / bootstrap
```

---

## 文档在哪

完整设计与工程文档在 **[`docs/`](./docs/README.md)**（入口即文档地图）。

| 编号 | 文档 | 回答什么问题 |
| --- | --- | --- |
| 01-1 | [原型资产与重构范围](./docs/01-产品规划/01-原型资产与重构范围.md) | 现有原型有什么、数据成色如何、重构要解决什么 |
| 01-2 | [产品定位与内容体系设计](./docs/01-产品规划/02-产品定位与内容体系设计.md) | 做什么内容、内容长什么样 |
| 01-3 | [功能清单与优先级路线图](./docs/01-产品规划/03-功能清单与优先级路线图.md) | 先做什么、分几期做 |
| **01-4** | [**免费开放与开源策略**](./docs/01-产品规划/04-免费开放与开源策略.md) | 免费边界、许可选择、**内容版权红线** |
| 02-1 | [系统总体架构与技术选型](./docs/02-系统架构/01-系统总体架构与技术选型.md) | 系统怎么搭、哪些能部署、哪些要掩藏 |
| 02-2 | [多端适配与响应式设计规范](./docs/02-系统架构/02-多端适配与响应式设计规范.md) | 手机 / iPad / 桌面怎么分档 |
| 02-3 | [uni-app 跨端方案与小程序适配](./docs/02-系统架构/03-uni-app跨端方案与小程序适配.md) | 跨端纪律（Web 阶段必守）+ 小程序 / App 预留 |
| 02-4 | [本地优先与后端策略](./docs/02-系统架构/04-本地优先与后端策略.md) | 本地优先怎么跑、能力怎么隐藏、云端后台怎么部署 |
| **02-5** | [**邀请码身份与准入体系**](./docs/02-系统架构/05-邀请码身份与准入体系.md) | 注册登入怎么做、跨设备同步如何无需企业主体 |
| 03-1 / 03-2 | [集合设计](./docs/03-数据设计/01-MongoDB集合设计.md) · [数据字典](./docs/03-数据设计/02-数据字典.md) | 数据怎么存、每个字段什么意思 |
| 04-1 | [API 接口定义](./docs/04-接口设计/01-API接口定义.md) | 内容包契约与后台接口（含掩藏层） |
| 05-1 | [内容管理与用户管理体系](./docs/05-管理后台/01-内容管理与用户管理体系.md) | 内容怎么管（仓库驱动 / 单管理员后台） |
| 06-1 / 06-2 | [开发规范与前端架构](./docs/06-工程规范/01-开发规范与前端架构.md) · [React 原型迁移方案](./docs/06-工程规范/02-React原型迁移方案.md) | 代码怎么写、现有代码怎么处理 |

**按角色阅读路径**（产品 / 前端 / 后端 / 内容 / 设计）见 [docs/README.md §五](./docs/README.md)。

---

## 技术栈（约定）

| 层 | 选型 |
| --- | --- |
| 前端（Web） | Vue 3 + TypeScript + Vite（手机 / iPad / 桌面三档响应式 + PWA） |
| 跨端内核 | **`packages/core`** —— 算法 / stores / 类型 / 契约 / 开关，**零平台依赖 + 学科无关** |
| 状态管理 | Pinia |
| 数据存储 | **IndexedDB + Cache Storage**（运行时主存储，无数据库依赖） |
| 身份与准入 | **邀请码 + 自设口令**（Ed25519 离线签名码 / 服务端校验） |
| 内容分发 | **仓库内 JSON + 远端静态覆盖 + 可选后端接口** |
| 云端后台 | Python 3.12 + **FastAPI** + MongoDB 7（邀请码身份 / 内容接口 / 匿名统计 / 可选 E2E 同步） |
| 部署 | **Docker Compose 分服务独立编排**（mongo / api / web 各一份）+ `network_mode: host` + nginx |
| 端口（默认） | Web `8080` · API `8000` · MongoDB `27017`（均在 `.env` 中可改） |

> ⚠️ **两条最要紧的纪律**
> 1. `packages/core` 中一旦出现 `window` / `document` / `uni.xxx`，跨端复用率会从 95% 掉到 0；且核心逻辑必须**与学科无关**（判据：*这段逻辑换成英语单词还成立吗？*）
> 2. **所有数据访问必须走仓储层**，禁止组件内直接操作 IndexedDB / localStorage —— 这是"将来能一行不改接后端"的唯一保证

---

## 内容版权红线

本项目**开源**，因此：

- ⛔ **不提供任何教材映射数据**（部编版 / 人教版的单元顺序、课文标题涉出版社汇编权）
- ⛔ **不收录无法溯源授权的素材**（来源不明的配图、音频）
- ✅ 内容数据源必须登记到 `content/sources.json` 与 `THIRD_PARTY_NOTICES.md` 后才可入库

详见 [docs/01-产品规划/04-免费开放与开源策略.md](./docs/01-产品规划/04-免费开放与开源策略.md)。

---

## 工作目录规划

```
study-club/
├── docs/                  # 设计与工程文档（15 份，入口 docs/README.md）
├── apps/
│   ├── web/               # ✅ 学生端 + 家长端 Web PWA（手机 / iPad / 桌面三档）:8080
│   ├── api/               # ✅ FastAPI 云端后台（可选增强，非必需依赖）      :8000
│   ├── admin/             # ✅ 单管理员内容后台（桌面，内部工具）            :8081
│   └── mobile/            # uni-app 跨端外壳（小程序 + App）                ⏸️ 预留
├── packages/
│   ├── core/              # ⭐ 跨端内核：契约 / 仓储 / stores / 算法 / 开关（零平台依赖 + 学科无关）
│   ├── subject-hanzi/     # ✅ 识字学科包（识字专属逻辑不得写进 core）
│   ├── tokens/            # ✅ 设计变量（三档断点 / 触控热区 / 色彩）
│   └── ui-web/            # ⏳ Web 端公共组件（当前组件在 apps/web 内）
├── content/               # ⭐ 内容即仓库（JSON + Schema + sources.json）
├── deploy/                # ⭐ 分服务独立编排：mongo / api / web / admin 各一份 docker-compose
├── scripts/               # ⭐ 部署与运维脚本（按用途与服务分目录）
└── licenses/              # 第三方许可与署名
```

完整目录树见 [06-1 第一章](./docs/06-工程规范/01-开发规范与前端架构.md)。

---

## 待办（下一步）

- [x] monorepo 骨架（`packages/core` + `packages/tokens` + `packages/subject-hanzi` + `apps/web` + `apps/api`）
- [x] `content/` 内容仓库与 JSON Schema + 校验脚本（`scripts/content/validate.mjs`）
- [x] Web PWA 三档响应式（手机 / iPad / 桌面）+ 本地优先仓储层 + 能力开关
- [x] 云端后台（邀请码身份 / 内容接口 / 匿名统计 / 可选 E2E 同步 / 单管理员）
- [x] Docker Compose 分服务编排（host 网络）+ `scripts/` 部署运维脚本 + 按表拆分的初始化数据
- [x] `apps/admin` 单管理员内容后台（桌面）：口令登录 / 概览 / 邀请码 / 字库
- [ ] 后台补 P0 剩余页：古诗管理（含注音校验）、单元与关卡编排、字库批量导入导出
- [ ] 把原型中真正精编的 52 条内容迁入 `content/`（并补齐拼音 / 释义 / 音频）
- [ ] CI：内容 Schema 校验 + `vue-tsc` 类型检查 + 掩藏能力「不打包」断言

---

## 许可

| 对象 | 许可 |
| --- | --- |
| 代码 | [MIT](./LICENSE) |
| 内容与文档 | CC BY-SA 4.0 |
| 第三方资产 | 随分发，登记于 `THIRD_PARTY_NOTICES.md` |
