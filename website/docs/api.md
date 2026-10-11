# API 接口

> 本文是面向用户与贡献者的导读，完整设计见 [04-1 API 接口定义](https://gitee.com/perry-space/study-club/blob/master/docs/04-接口设计/01-API接口定义.md)（Gitee）。**最终事实来源是 FastAPI 自动生成的 OpenAPI 文档**（`/docs` 与 `/openapi.json`），文档与代码不一致时以代码为准。

后端为 Python 3.12 + FastAPI + MongoDB 7（motor 异步）。**服务端是唯一真源**，接口统一前缀 `/api/v1`。

## 一、通用约定

| 项 | 约定 |
| --- | --- |
| Base URL | `/api/v1`（web 由 nginx 把 `/api/` 同源反代到后端） |
| 数据格式 | JSON，UTF-8；时间 ISO 8601 UTC |
| 认证 | `Authorization: Bearer <access_token>`（JWT Access + 可吊销 Refresh） |

**统一响应信封** —— 成功：

```json
{ "code": 0, "message": "ok", "data": { }, "request_id": "uuid" }
```

失败：

```json
{
  "code": 40001,
  "message": "参数校验失败",
  "errors": [ { "field": "grade", "reason": "必须是 1-6 之间的整数" } ],
  "request_id": "uuid"
}
```

> `code = 0` 表示成功，**HTTP 状态码同时保持语义正确**（200/201/400/401/403/404/409/429/500）。

**分页**：请求 `page`（默认 1）/ `page_size`（默认 20，最大 100）；响应 `data.items` + `data.pagination`。

**所有请求必带客户端请求头**：`X-Client-Client` / `X-Client-Platform` / `X-Client-Form` / `X-Client-Version`（可选 `X-Client-Capabilities`），由各端统一的 API 客户端注入，业务代码不感知。

## 二、按分组的主要接口

| 分组 | 前缀 | 职责 | 代表接口 |
| --- | --- | --- | --- |
| 基础 | `/health` `/config` `/assets` | 健康探测、公开运行配置、素材下发（**免登录**） | `GET /health` · `GET /config` · `GET /assets/{id}` |
| 认证 | `/auth` | 邀请码身份、恢复码、会话 | `POST /auth/register` · `POST /auth/login` · `POST /auth/recovery/reset` |
| 档案 | `/children` | 儿童档案增删改查与统计 | `GET/POST /children` · `PATCH /children/{id}` |
| 内容 | `/content` | 字库 / 古诗 / 单元 / 关卡 / 故事 / 短文 / 徽章 | `GET /content/bootstrap` · `GET /content/lessons/{id}/questions` |
| 学习 | `/learning` | 答题、复习、错题、进度、导出 | `GET /learning/daily-task` · `POST /learning/answer` |
| 报告 | `/reports` | 服务端聚合的学情报告 | `GET /reports/child/{id}/overview` · `.../weekly` |
| 统计 | `/stats` | 匿名聚合计数上报（**免登录**） | `POST /stats/events` |
| 反馈 | `/feedbacks` | 用户反馈与内容纠错（允许匿名） | `POST /feedbacks` |
| 同步 | `/sync` | 端到端加密的云端家庭档案 | `GET /sync/manifest` · `POST /sync/push` |
| 管理后台 | `/admin` | 单管理员内容 / 邀请码 / 用户 / 配置 | `GET /admin/overview` · `PUT /admin/config` |

> 约 98 个已部署接口。**内容全部「登录后才可见」**，唯一例外是素材文件 `GET /assets/{id}`。

### 认证（✅ 当前）

身份方式为**邀请码 + 自设口令**：用户名 + 口令注册登入，邀请码按 `REQUIRE_INVITE` 开关可选。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/register` | 统一注册：用户名 + 口令，邀请码按开关可选 |
| POST | `/auth/login` | 统一登入，`identifier` 可填用户名 |
| POST | `/auth/invite/verify` | 注册前预检邀请码是否可用（不消耗次数） |
| POST | `/auth/recovery/reset` | 用恢复码重置口令 |
| POST | `/auth/refresh` | 刷新 Access Token |
| POST | `/auth/logout` | 退出登录（吊销该设备 Refresh Token） |
| GET | `/auth/me` | 当前账号摘要 |
| DELETE | `/auth/account` | 注销并删除云端数据 |

> ⚠️ 四条硬性约定：错误信息统一 `40103`（防枚举）；`recovery_code` **只返回一次**；连续失败锁定 + 限流；`client_id` 是**设备身份**不是用户身份。

### 内容下发

| 通道 | 接口 | 说明 |
| --- | --- | --- |
| 一次拉全量 | `GET /content/bootstrap` | 登录后调用：清单 + 字库 + 古诗 + 单元 + 关卡 + 故事 + 短文 + 徽章，首屏依赖收敛到单个请求 |
| 增量读取 | `GET /content/{collection}` 及子资源接口 | 按需读取单个字 / 诗 / 单元 / 关卡 |
| 生成题目 | `GET /content/lessons/{id}/questions` | 题型策略随玩法配置热更新，并基于历史表现调整 |

> 题目生成为**服务端行为**；列表与详情接口返回的 `image_url` / `audio_url` 已由服务端从 `assets` 解析，前端无需二次请求素材。

## 三、掩藏接口（契约保留、不注册路由）

以下能力**写契约与开关，但不注册任何路由、不打包、不可达**，即使客户端被绕过也调不到：

| 能力 | 开关名 | 状态 |
| --- | --- | --- |
| 手机号 / 短信 OTP、微信授权登录、账号绑定 | `enableAccountAuth` | ⛔ 契约保留、不注册路由 |
| 支付与订阅 `/billing` | `enablePayment` | ⛔ 契约保留、不注册路由 |
| 多角色 RBAC `/admin/roles` | `enableAccountAuth` | ⛔ **本期不做**（与企业主体无关） |
| 服务端推送与设备登记 `/devices/*` | `enableNativeApp` | ⛔ 契约保留、不注册路由 |
| 微信小程序 / iOS·Android App | `enableMiniprogram` / `enableNativeApp` | ⛔ 契约保留、不注册路由 |

> 掩藏能力均需企业主体；**多角色 RBAC 属「本期不做」**（与企业主体无关）。开关默认关，且**禁止被运行期远端配置打开**。

## 四、兼容性硬要求

客户端可能长期停留在旧版本，因此兼容不是最佳实践而是硬要求：

| 规则 | 说明 |
| --- | --- |
| 字段**只增不改不删** | 新增字段必须可选；删除字段须先经历废弃期 |
| 枚举值**只增** | 客户端遇未知枚举值必须兜底渲染，**不得崩溃** |
| 错误码不复用 | 同一码不得改变含义 |
| 破坏性变更走 `/api/v2` | v1 至少并行保留一段时间 |

## 继续阅读

- 数据怎么存 → [数据设计](/docs/data)
- 内容怎么下发 → [内容体系与创作](/docs/content)
- 身份与准入 → [邀请码身份与准入](/docs/identity)
