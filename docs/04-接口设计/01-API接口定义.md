# 04-1 API 接口定义

> 本文档用于设计评审与前后端并行开发。
> **最终事实来源是 FastAPI 自动生成的 OpenAPI 文档**（`/docs` 与 `/openapi.json`），本文件与代码不一致时以代码为准。

---

## 〇、接口概览（先读这一节）

**服务端是唯一真源**：账号、设备会话、儿童档案、学习记录、复习状态、错题、每日任务、徽章、同步对象，以及全部内容数据，都以服务端 MongoDB 为准；浏览器只保留四类本地键（`sc.session` / `sc.deviceId` / `sc.currentChild` / `sc.loginMemory`），不含任何业务数据（见 [02-3 存储与后端策略](../02-系统架构/03-存储与后端策略.md)）。

- 统一前缀 `/api/v1`；响应信封 `{code, message, data|errors, request_id}`，成功 `code = 0`。
- 鉴权：`Authorization: Bearer <access_token>`（JWT Access + 可吊销 Refresh）。
- 内容经 `content/*.json` 导入 MongoDB 后，由 `GET /content/bootstrap` 一次下发全量。

| 分组 | 前缀 | 职责 | 状态 |
| --- | --- | --- | --- |
| 基础 | `/health` `/config` `/assets` | 健康探测、公开运行配置、素材下发 | ✅ |
| 认证 | `/auth` | 邀请码身份、恢复码、会话 | ✅ |
| 档案 | `/children` | 儿童档案增删改查与统计 | ✅ |
| 内容 | `/content` | 字库 / 古诗 / 单元 / 关卡 / 故事 / 短文 / 徽章 | ✅ |
| 学习 | `/learning` | 答题、复习、错题、进度、导出 | ✅ |
| 报告 | `/reports` | 服务端聚合的学情报告 | ✅ |
| 统计 | `/stats` | 匿名聚合计数 | ✅ |
| 反馈 | `/feedbacks` | 用户反馈与内容纠错 | ✅ |
| 同步 | `/sync` | 端到端加密的云端家庭档案 | ✅ |
| 管理后台 | `/admin` | 单管理员内容 / 邀请码 / 用户 / 配置 | ✅ |

> **掩藏分组**（写契约与开关，但**不注册路由、不打包、不可达**）见 [第十二章](#十二掩藏接口契约保留不注册路由)。

---

## 一、通用约定

### 1.1 基础信息

| 项 | 约定 |
| --- | --- |
| Base URL | `/api/v1`（web 由 nginx 把 `/api/` 同源反代到后端，见 [02-3 §九](../02-系统架构/03-存储与后端策略.md#九部署与配置)） |
| 数据格式 | JSON（`Content-Type: application/json`） |
| 字符编码 | UTF-8 |
| 时间格式 | ISO 8601 UTC，如 `2026-10-08T09:12:00Z` |
| 认证方式 | `Authorization: Bearer <access_token>` |
| 版本策略 | 路径版本 `/api/v1`，破坏性变更升版本号 |

### 1.2 统一响应结构

**成功**

```json
{
  "code": 0,
  "message": "ok",
  "data": { },
  "request_id": "uuid"
}
```

**失败**

```json
{
  "code": 40001,
  "message": "参数校验失败",
  "errors": [
    { "field": "grade", "reason": "必须是 1-6 之间的整数" }
  ],
  "request_id": "uuid"
}
```

> `code = 0` 表示成功，**HTTP 状态码同时保持语义正确**（200/201/400/401/403/404/409/413/415/429/500）。

### 1.3 分页约定

**请求**

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` | int | 1 | 页码，从 1 开始 |
| `page_size` | int | 20 | 每页条数，**最大 100** |

**响应**

```json
{
  "code": 0,
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 137,
      "total_pages": 7
    }
  }
}
```

### 1.4 错误码规范

| 区段 | 含义 | 示例 |
| --- | --- | --- |
| `0` | 成功 | — |
| `400xx` | 请求参数错误 | `40001` 参数校验失败 |
| `401xx` | 认证失败 | `40101` Token 过期 / `40103` 邀请码或密码不正确 |
| `403xx` | 权限不足 / 能力未启用 | `40301` 无权访问该儿童档案 / `40302` 能力未启用 |
| `404xx` | 资源不存在 | `40401` 汉字不存在 / `40403` 儿童档案不存在 |
| `406xx` | 部分成功 | `40601` 批量导入部分失败 |
| `409xx` | 状态冲突 | `40902` 内容已存在 |
| `413xx` / `415xx` | 上传被拒 | `41301` 素材过大 / `41501` 不支持的媒体类型 |
| `429xx` | 频率限制 | `42901` 请求过于频繁 |
| `500xx` | 服务端错误 | `50001` 内部错误 / `50003` 存储不可用 |

**常用业务错误码**

| 码 | 含义 | 前端处理 |
| --- | --- | --- |
| `40101` | Access Token 过期 | 静默刷新 Token 后重试 |
| `40102` | Token 无效 | 跳转登录 |
| `40103` | 邀请码或密码不正确（统一文案，防枚举） | 提示 |
| `40105` | 账号已锁定 | 提示稍后重试 |
| `40301` | 无权访问该儿童档案 | 提示并返回档案选择页 |
| `40401` | 汉字不存在 | 提示 |
| `42901` | 请求过于频繁 | 提示稍后重试 |

### 1.5 幂等性

| 场景 | 机制 |
| --- | --- |
| 答题批量补报 | 每条记录带客户端生成的 `client_record_id`，服务端按 `(child_id, client_record_id)` 唯一索引去重 |
| 内容创建 | 唯一字段冲突返回 `40902` |
| 内容导入 | 幂等 upsert，可反复重跑 |

### 1.6 客户端标识与多端约定

**所有请求必须携带以下请求头**，由各端统一的 API 客户端注入（业务代码不感知）：

| 请求头 | 必填 | 取值 | 用途 |
| --- | --- | --- | --- |
| `X-Client-Client` | ✅ | `web` / `miniprogram` / `app` | 外壳类型 |
| `X-Client-Platform` | ✅ | `ios` / `android` / `harmony` / `web` | 系统平台 |
| `X-Client-Form` | ✅ | `phone` / `tablet` / `desktop` | 形态（**按可用宽度判定，不按设备型号**） |
| `X-Client-Version` | ✅ | 语义化版本，如 `2.1.0` | 客户端版本 |
| `X-Client-Capabilities` | ⚠️ | 逗号分隔能力名 | 运行时能力集（机制见 [06-1 §2.8](../06-工程规范/01-开发规范与前端架构.md#28-能力开关与仓储层规范)） |

**为什么必须**：

1. 服务端据此把 `client` / `platform` / `device_form` 写入 `learning_records`（见 [03-2](../03-数据设计/02-数据字典.md)），支撑分端分析
2. **服务端按 `X-Client-Version` 做兼容降级**——旧版本客户端会长期存在，不能假定人人即时升级
3. 排查"只在某个端出现"的缺陷时，可直接按端过滤请求日志

**`X-Client-Capabilities`（能力集上报）**

```
X-Client-Capabilities: record,local_asr,realtime_audio,handwriting,push
```

> 此处只约定**请求头契约**。能力集的取值与服务端降级规则见 [06-1 §2.8](../06-工程规范/01-开发规范与前端架构.md#28-能力开关与仓储层规范)；客户端能力分级见 [02-2 §七](../02-系统架构/02-多端适配与响应式设计规范.md#七能力探测与降级)。

### 1.7 向后兼容（硬要求）

客户端可能长期停留在旧版本，因此**兼容不是最佳实践而是硬要求**：

| 规则 | 说明 |
| --- | --- |
| 字段**只增不改不删** | 新增字段必须可选；删除字段须先经历"废弃期"（≥ 3 个月，期间双写） |
| 枚举值**只增** | 客户端遇到未知枚举值必须兜底渲染，**不得崩溃** |
| 错误码不复用 | 同一码不得改变含义 |
| 破坏性变更走 `/api/v2` | v1 至少并行保留 3 个月 |

### 1.8 内容下发

内容以仓库内 `content/*.json` 维护（Git 版本化），经 `scripts/seed` 或后台 `/admin/content/import` 导入 MongoDB，再由接口下发：

| 通道 | 接口 | 说明 |
| --- | --- | --- |
| 一次拉全量 | `GET /content/bootstrap` | 登录后调用：清单 + 字库 + 古诗 + 单元 + 关卡 + 故事 + 短文 + 徽章，首屏依赖收敛到单个请求 |
| 增量读取 | `GET /content/{collection}` 及子资源接口 | 按需读取单个字 / 诗 / 单元 / 关卡 |

> 字段与接口响应同源：内容包字段名/类型 = MongoDB 集合 = `/content/*` 响应 = [03-2 数据字典](../03-数据设计/02-数据字典.md)。内容分发链路详见 [02-3 §三](../02-系统架构/03-存储与后端策略.md#三内容即仓库content-as-repo)。

---

## 二、基础接口 `/health` · `/config` · `/assets`

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| GET | `/health` | 健康探测，返回 `status` / `content_version` / `server_time` | ❌ |
| GET | `/config` | 公开运行配置：`require_invite` / `registration_open` / `announcement` / `defaults` / `gameplay` / `grades` | ❌ |
| GET | `/assets/{asset_id}` | 素材文件下载（图片 / 音频 / 笔顺），强 `ETag` + 长缓存 | ❌ |

> `GET /config` 与 `GET /health`、`GET /assets/{id}` 均**免登录**：登录页要先探测服务端是否可用，注册页与引导页在登录前就要读年级表与玩法配置；素材会被 `<img>` / `<audio>` 直接引用，标签不会携带 Authorization 头（详见 `apps/api/app/views/assets.py`）。敏感项（密钥、DB 地址等）一律不下发。

---

## 三、认证与身份 `/auth`

> 身份方式为**邀请码 + 自设密码**（用户名 + 密码注册登入，邀请码按 `require_invite` 开关可选，见 [02-5 邀请码身份与准入体系](../02-系统架构/05-邀请码身份与准入体系.md)）；手机号 / 短信 OTP、微信授权登录、账号绑定属 ⛔ 掩藏，见 [第十二章](#十二掩藏接口契约保留不注册路由)。

### 3.1 注册与登入（✅ 当前）

> 主入口是 `POST /auth/register` 与 `POST /auth/login`；下方的 `/auth/invite/*`
> 是同一套身份模型的**兼容旧路径**（保留以兼容已分享的旧链接与旧版本）。
> 请求体结构一致，仅 `identifier` 的解析优先级不同（`identifier → account → invite_code`）。

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| POST | `/auth/register` | **统一注册**：用户名 + 密码；邀请码按开关可选 | ❌ |
| POST | `/auth/login` | **统一登入**：`identifier` 可填用户名 | ❌ |
| POST | `/auth/invite/verify` | 仅校验邀请码是否可用（注册前预检，不消耗次数） | ❌ |
| POST | `/auth/invite/register` | 用邀请码 + 密码注册，创建匿名账号与家庭档案 | ❌ |
| POST | `/auth/invite/login` | 邀请码 + 密码登入 | ❌ |
| POST | `/auth/recovery/reset` | 用恢复码重置密码（并重派生加密密钥） | ❌ |
| POST | `/auth/refresh` | 刷新 Access Token | ❌ |
| POST | `/auth/logout` | 退出登录（吊销该设备 Refresh Token） | ✅ |
| GET | `/auth/me` | 当前账号摘要（家庭昵称、档案数、是否开启端到端加密） | ✅ |
| DELETE | `/auth/account` | **注销并删除云端数据**（合规必需） | ✅ |

**`POST /auth/invite/register` 请求 / 响应**

```json
// 请求
{
  "invite_code": "HANZI-4K9F-7QX2",
  "pin": "••••••",
  "display_name": "小明家",
  "client": { "client_id": "dev_xxx", "platform": "web", "app_version": "1.0.0" },  // client_id=设备标识，见下「硬性约定 4」
  "e2e_enabled": true
}

// 响应
{
  "code": 0,
  "data": {
    "account_id": "acc_xxx",
    "access_token": "...",
    "refresh_token": "...",
    "expires_in": 3600,
    "recovery_code": "RCVR-••••-••••-••••-••••",   // ⚠️ 仅此一次返回，之后无法再取
    "e2e_enabled": true
  }
}
```

> ⚠️ **四条硬性约定**：
>
> 1. **错误信息统一**：邀请码无效、已用尽、密码错误一律返回 `40103`「邀请码或密码不正确」，**绝不区分原因**（防用户与邀请码枚举）。
> 2. **`recovery_code` 只返回一次**，服务端只存哈希；前端必须强制用户抄写确认。
> 3. **限流与锁定**：限流 10 次/10 分钟、连续 5 次失败锁定 15 分钟。
>    ⚠️ 限流键是**客户端形态指纹**（client/platform/device_form/version 的哈希），
>    **刻意不含 `client_id`** —— 它是客户端可控值，拼进限流键等于允许「换个 id 换一个计数桶」来绕过限流。
> 4. **`client.client_id` 是设备身份，不是用户身份**：客户端必须上报一个**持久化的随机 id**
>    （web 端存 `localStorage['sc.deviceId']`）。服务端按 `(account_id, client_id)` 存 `devices`
>    会话记录，**一台设备一条**，因此多台设备可同时在线、各自登出互不影响。
>    若不上报，服务端退化为按形态指纹认设备，同形态的两台设备会互相覆盖 Refresh Token
>    （现象：一台登录，另一台被踢下线）。

> **签名码**：邀请码支持 Ed25519 签名校验——公钥随开源代码公开，私钥仅维护者持有，客户端本地验签。

### 3.2 云端档案同步（✅ 当前，默认关闭 + 默认端到端加密）

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| GET | `/sync/manifest` | 取云端档案清单与版本（用于增量同步，返回的是**密文块索引**） | ✅ |
| POST | `/sync/push` | 上传变更（密文） | ✅ |
| GET | `/sync/pull` | 拉取远端变更（密文） | ✅ |
| GET | `/sync/salt` | 取 KDF 盐（用于密码派生加密密钥） | ✅ |

> ⚠️ **服务端只存密文**：`push` / `pull` 的载荷在客户端用「密码 → Argon2id → 密钥」加密，服务端**无法解密**。因此联调时看到的是不可读的 blob，这是设计使然（见 [02-3 §七](../02-系统架构/03-存储与后端策略.md#七数据可迁移性与备份)）。

### 3.3 邀请码管理（✅ 自托管后台）

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| POST | `/admin/invites/batch` | 批量生成邀请码（指定数量、有效期、`channel`、`note`） | 管理员 |
| GET | `/admin/invites` | 邀请码列表（只返回 `code_hint`，**不返回完整码**） | 管理员 |
| POST | `/admin/invites/{id}/revoke` | 吊销邀请码 | 管理员 |

### 3.4 ⛔ 掩藏：账号体系（需企业主体）

> 手机号 / 短信 OTP、微信授权登录、账号绑定属 ⛔ 掩藏，**契约保留、不注册路由**。完整清单见 [第十二章](#十二掩藏接口契约保留不注册路由)。

---

## 四、儿童档案 `/children`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/children` | 获取当前账号下全部儿童档案 |
| POST | `/children` | 新建儿童档案 |
| GET | `/children/{child_id}` | 获取档案详情 |
| PATCH | `/children/{child_id}` | 更新档案 |
| DELETE | `/children/{child_id}` | 删除档案（软删除） |
| GET | `/children/{child_id}/stats` | 学习统计概览 |

### POST `/children`

**请求**

```json
{
  "nickname": "小明",
  "avatar_key": "rabbit",
  "grade": 2,
  "birth_year": 2018,
  "unit_preference": "self",
  "daily_new_char_target": 8,
  "daily_review_target": 12,
  "daily_time_limit_min": 20
}
```

**响应**：`201` + 完整档案对象

> **隐私约束**：接口**不接受**真实姓名、照片、精确生日、学校名等字段。传递这些字段返回 `40001`。这是架构级的合规设计，不是可选项。

---

## 五、内容 `/content`

> 内容已全部由后台管理、属于「登录后才可见」的受控数据，因此本组接口**都要求登录**（唯一例外是素材文件 `GET /assets/{id}`，见第二章）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/content/bootstrap` | 登录后一次拉取全量内容（清单 + 字库 + 古诗 + 单元 + 关卡 + 故事 + 短文 + 徽章） |
| GET | `/content/manifest` | 内容包清单 |
| GET | `/content/characters` | 汉字列表（支持筛选） |
| GET | `/content/characters/{char_id}` | 汉字详情 |
| GET | `/content/characters/by-char/{char}` | 按字符查询 |
| GET | `/content/characters/batch` | 批量获取（`ids` 参数，逗号分隔） |
| GET | `/content/characters/{char_id}/similar` | 形近字 |
| GET | `/content/poems` | 古诗列表 |
| GET | `/content/poems/{poem_id}` | 古诗详情（含逐句注音与释义） |
| GET | `/content/poems/{poem_id}/quiz` | 生成古诗练习题 |
| GET | `/content/poems/by-char/{char}` | 按汉字反查古诗句 |
| GET | `/content/stories` | 识字短文列表（孩子端第三条线，含短文与儿歌） |
| GET | `/content/stories/{story_id}` | 短文详情 |
| GET | `/content/units` | 自编单元列表 |
| GET | `/content/units/{unit_id}` | 单元详情（含字表） |
| GET | `/content/lessons` | 关卡列表（含解锁状态） |
| GET | `/content/lessons/{lesson_id}` | 关卡详情 |
| GET | `/content/lessons/{lesson_id}/questions` | **生成该关卡题目** |
| GET | `/content/badges` | 徽章定义列表 |
| GET | `/content/badges/{code}` | 徽章详情 |

**汉字列表查询参数**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `grade` | int | 年级筛选 |
| `level` | string | 学段筛选 |
| `tags` | string | 标签，逗号分隔 |
| `unit_id` | string | 按自编单元 |
| `status` | string | 仅后台可用，默认 `published` |
| `keyword` | string | 搜索汉字、释义、组词 |

**汉字列表响应示例**

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "6512a1...",
        "char": "水",
        "pinyin": "shuǐ",
        "tone": 3,
        "meaning": "喝的水，也指河里的水。",
        "words": ["喝水", "水果", "河水"],
        "image_url": "https://cdn.example.com/image/char/水.webp",
        "audio_url": "https://cdn.example.com/audio/char/水.mp3",
        "stroke_count": 4,
        "grade": 1,
        "difficulty": 1,
        "tags": ["自然", "生活"]
      }
    ],
    "pagination": { "page": 1, "page_size": 20, "total": 137, "total_pages": 7 }
  }
}
```

> **素材 URL 已展开**：列表与详情接口返回 `image_url` / `audio_url`，由服务端从 `assets` 解析。前端无需二次请求素材。

**`/content/lessons/{lesson_id}/questions` 响应**

```json
{
  "code": 0,
  "data": {
    "lesson_id": "6513...",
    "questions": [
      {
        "question_id": "q_uuid",
        "type": "image-choice",
        "character_id": "6512...",
        "stem": "选出图片对应的汉字",
        "image_url": "https://cdn.../水.webp",
        "options": [
          { "id": "6512...", "char": "水" },
          { "id": "6513...", "char": "永" },
          { "id": "6514...", "char": "冰" }
        ],
        "answer_character_id": "6512..."
      }
    ]
  }
}
```

> **题目生成为服务端行为**：题型策略可随玩法配置热更新，并基于孩子的历史表现调整。

---

## 六、学习 `/learning`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/learning/state` | 首页/进度页状态聚合（进度 + 今日任务 + 到期复习 + 已获徽章） |
| GET | `/learning/daily-task` | 获取今日任务（不存在则懒生成） |
| POST | `/learning/answer` | 提交单题作答 |
| POST | `/learning/answer/batch` | 批量提交作答（补报） |
| POST | `/learning/lesson/complete` | 提交关卡完成 |
| GET | `/learning/review/due` | 获取到期应复习字 |
| GET | `/learning/wrong-questions` | 错题本 |
| POST | `/learning/wrong-questions/{id}/resolve` | 标记订正 |
| GET | `/learning/progress` | 学习进度总览 |
| GET | `/learning/review-states` | 复习状态全量（导出 / 还原用） |
| GET | `/learning/badges` | 该孩子已获徽章 |
| GET | `/learning/records` | 学习流水 |
| GET | `/learning/answers` | 答题明细 |
| GET | `/learning/export` | 导出该孩子完整学习数据包（备份手段） |

### GET `/learning/daily-task`

**请求参数**：`child_id`

**响应**

```json
{
  "code": 0,
  "data": {
    "date": "2026-10-08",
    "status": "in_progress",
    "new_chars": [ { "id": "...", "char": "水" } ],
    "review_chars": [ { "id": "...", "char": "火" } ],
    "wrong_chars": [ { "id": "...", "char": "永" } ],
    "completed_count": 3,
    "total_count": 20
  }
}
```

### POST `/learning/answer`

**请求**

```json
{
  "child_id": "6512...",
  "character_id": "6513...",
  "question_type": "audio-choice",
  "answer": "水",
  "correct_answer": "水",
  "is_correct": true,
  "response_ms": 2340,
  "session_id": "uuid",
  "occurred_at": "2026-10-08T09:10:00Z",
  "client_record_id": "uuid"
}
```

**服务端副作用**（一次请求内完成）：
1. 写入 `answer_records`
2. `upsert` 更新 `char_review_states`（跑 SRS 算法）
3. 若答错，`upsert` 更新 `wrong_questions`
4. 若订正，更新 `wrong_questions.resolved`

**响应**

```json
{
  "code": 0,
  "data": {
    "is_correct": true,
    "next_review_at": "2026-10-14T00:00:00Z",
    "interval_days": 6,
    "newly_earned_badges": [
      { "code": "ten_chars", "title": "十字达人" }
    ]
  }
}
```

> **徽章即时判定**：答题后立即返回新解锁的徽章，前端可即时弹窗，避免额外请求。

### POST `/learning/answer/batch`

**请求**

```json
{
  "child_id": "6512...",
  "records": [ { "client_record_id": "uuid", "...": "..." } ]
}
```

**说明**：用于批量补报。服务端按 `(child_id, client_record_id)` 去重，返回成功与跳过的计数。

```json
{
  "code": 0,
  "data": { "accepted": 48, "skipped_duplicate": 2 }
}
```

---

## 七、报告 `/reports`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/reports/child/{child_id}/overview` | 学情总览 |
| GET | `/reports/child/{child_id}/trend` | 学习趋势（按天/周） |
| GET | `/reports/child/{child_id}/mastery` | 掌握率分布 |
| GET | `/reports/child/{child_id}/weak-chars` | 薄弱字清单 |
| GET | `/reports/child/{child_id}/weekly` | 周报 |

**`/reports/child/{child_id}/overview` 响应**

```json
{
  "code": 0,
  "data": {
    "child": { "nickname": "小明", "grade": 2 },
    "summary": {
      "total_learned": 320,
      "mastered": 210,
      "learning": 95,
      "struggling": 15,
      "streak_days": 15,
      "total_duration_min": 840
    },
    "period": { "from": "2026-09-01", "to": "2026-10-08" },
    "recent_7d": {
      "studied_days": 6,
      "chars_learned": 48,
      "accuracy": 0.89
    }
  }
}
```

---

## 八、统计与反馈 `/stats` · `/feedbacks`

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| POST | `/stats/events` | 匿名聚合计数上报 | ❌ |
| POST | `/feedbacks` | 提交反馈或内容纠错（允许匿名） | 可选 |

### POST `/stats/events`

**请求**

```json
{
  "events": [
    {
      "event_name": "lesson_complete",
      "content_ref": "u-g1-01",
      "client": "web",
      "device_form": "desktop",
      "client_version": "1.2.0",
      "count": 1,
      "bucket_date": "2026-10-08"
    }
  ]
}
```

> ⚠️ **隐私红线**：请求体 `extra="forbid"`，出现 `account_id` / `child_id` / `client_id` 直接 `40001`。统计接口无需登录——必须能在未注册状态下静默上报。允许/禁止清单见 [02-3 §八](../02-系统架构/03-存储与后端策略.md#八匿名统计与隐私边界)。

### POST `/feedbacks`

**请求**

```json
{
  "category": "content_error",
  "content_ref": "6512...",
  "message": "「水」的拼音注音有误",
  "contact": "",
  "client": "web"
}
```

**响应**：`201` + 反馈对象。`contact` 为自愿留存，可为空。

---

## 九、端到端加密同步 `/sync`

见 [3.2](#32-云端档案同步-当前默认关闭--默认端到端加密)。服务端只存 `cipher_payload`，**不做任何解密**；密钥由用户密码在客户端派生。

---

## 十、管理后台 `/admin`

**单管理员后台（不做 RBAC）**：所有接口需管理员身份，且写操作记入 `audit_logs`。管理员密码（Argon2id）换管理员 JWT，或使用 `X-Admin-Password` 头。

### 10.1 登录与概览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/admin/login` | 用管理员密码换 JWT（密码哈希未配置时能力整体不可用） |
| GET | `/admin/overview` | 内容完整度 + 素材体量 + 邀请码体量（只读聚合） |
| GET | `/admin/registry` | 内容类型注册表（后台据此渲染表格与表单） |
| GET | `/admin/audit-logs` | 操作审计日志 |

### 10.2 站点配置（配置中心）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/config` | 读取当前站点运行配置（邀请码开关 / 是否开放注册 / 公告 / 默认学习目标 / 玩法 / 年级表） |
| PUT | `/admin/config` | 热更新站点配置：写 DB 并刷新进程缓存，**不需要重启** |

### 10.3 用户管理

账号相关接口的实际路径是 `/admin/users/*`（**不是** `/admin/accounts/*`）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/users` | 账号列表。支持 `keyword` / `status` / `role` / `has_children` / `registered_from` / `registered_to` 筛选；手机号**只出掩码** |
| GET | `/admin/users/stats` | 账号体量聚合（总数 / 分状态 / 有无手机号 / 孩子档案数） |
| GET | `/admin/users/{id}` | 账号详情（含档案数） |
| GET | `/admin/users/{id}/report` | 账号级学习报告（已认 / 掌握 / 正确率 / 趋势） |
| PATCH | `/admin/users/{id}` | **编辑展示资料**：`display_name` / `avatar_key` / `access_tier`。`extra="forbid"`，越权字段 422 |
| POST | `/admin/users/{id}/status` | 启用 / 禁用（可逆） |
| DELETE | `/admin/users/{id}` | **注销**（不可逆）：释放邀请码、撤销全部会话，**保留孩子档案与学习数据** |
| POST | `/admin/users/bulk/status` | 批量启用 / 禁用（上限 100）。返回成功与失败的 id，不静默吞掉失败项 |

> ⚠️ **注销与删除云端数据是两件事**：`DELETE /admin/users/{id}` 是软删，
> 保留学习数据 —— 这是儿童数据最小化的底线。需要真正清除数据时走导出/注销账号流程，
> 不在后台提供「一键抹掉」。

> ⛔ `/admin/roles`（多角色 RBAC）**本期不做**（单人维护下多角色属过度设计，**与企业主体无关**，见 [05-1 内容管理与用户管理体系](../05-管理后台/01-内容管理与用户管理体系.md)）；
> 当前只做单管理员，**不建角色表、不做权限矩阵**，`role` 字段也不可编辑。

### 10.4 素材中心

> ⚠️ 具体路径（`/assets/bind`、`/assets/stats`）必须声明在 `/assets/{asset_id}` 之前，否则会被路径参数吃掉。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/admin/assets` | 上传素材（图片 / 音频 / 笔顺 JSON），返回素材元数据 |
| GET | `/admin/assets` | 素材列表（`type` / `keyword` / `include_deleted`） |
| GET | `/admin/assets/stats` | 素材体量统计 |
| POST | `/admin/assets/bind` | 把素材绑定到内容（`asset_id=null` 即解绑） |
| GET | `/admin/assets/{id}` | 素材详情 |
| DELETE | `/admin/assets/{id}` | 归档素材（检查引用后） |

### 10.5 内容导入 / 导出

> ⚠️ 固定路径段（`/content/import`、`/content/import/preview`、`/content/{collection}/template`、`/content/{collection}/export`）必须声明在 `/content/{collection}` 之前，否则会被路径参数吃掉。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/content/import/preview` | 各来源文件的条数与库内现有量 |
| POST | `/admin/content/import` | 从仓库 `content/*.json` 或上传载荷导入（幂等 upsert，`dry_run` 只统计不落库） |
| GET | `/admin/content/{collection}/export` | 导出某类内容为可回写仓库的 JSON（按当前筛选） |
| GET | `/admin/content/{collection}/template` | 下载导入模板：字段说明 + 一条示例；派生字段标 `derived` |
| GET | `/admin/characters/grade-counts` | 字库按年级计数（后台年级分类 Tab 的徽标） |

### 10.6 内容通用 CRUD

内容 CRUD 是一套**数据驱动**的通用接口：集合差异由 `content_registry` 的数据描述（`GET /admin/registry`）声明。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/content/{collection}` | 列表（分页 + `status` / `keyword` / `grade` / `level` 筛选） |
| POST | `/admin/content/{collection}` | 新建（`_id` 由服务端按类型规则派生） |
| PATCH | `/admin/content/{collection}/{id}` | 更新（`version` 自增） |
| DELETE | `/admin/content/{collection}/{id}` | **下架**（软删：置 `status=offline`，不物理删除） |

> `collection` 取值：`characters` / `poems` / `curriculum_units` / `lessons` / `stories` / `badges`。

---

## 十一、接口总览表

### 11.1 ✅ 当前（无需企业主体）

| 模块 | 接口数 | 状态 | 说明 |
| --- | --- | --- | --- |
| `/health` `/config` `/assets` | 3 | ✅ 部署 | 健康探测、公开配置、素材下发 |
| `/auth` | 10 | ✅ 部署 | 邀请码身份 + 恢复码 + 会话 |
| `/children` | 6 | ✅ 部署 | 儿童档案 |
| `/content` | 22 | ✅ 部署 | 字库 / 古诗 / 单元 / 关卡 / 故事 / 短文 / 徽章 |
| `/learning` | 14 | ✅ 部署 | 学习、复习、错题、进度、导出 |
| `/reports` | 5 | ✅ 部署 | 学情报告（服务端聚合） |
| `/stats` `/feedbacks` | 2 | ✅ 部署 | 匿名统计与反馈 |
| `/sync` | 4 | ✅ 部署 | 端到端加密同步（默认关闭） |
| `/admin` | 32 | ✅ 部署 | 单管理员内容 / 邀请码 / 用户 / 配置 |
| **小计** | **约 98** | — | — |

### 11.2 ⛔ 掩藏 / 本期不做（契约保留）

| 能力 | 开关名 | 契约位置 | 状态 |
| --- | --- | --- | --- |
| 手机号 / 微信账号（短信 OTP、微信授权登录、账号绑定） | `enableAccountAuth` | [§3.4](#34--掩藏账号体系需企业主体) | ⛔ 契约保留、不注册路由 |
| 支付与订阅（`/billing`） | `enablePayment` | — | ⛔ 契约保留、不注册路由 |
| 多角色 RBAC（`/admin/roles`） | `enableAccountAuth` | [§10.3](#103-用户管理) | ⛔ **本期不做**（与企业主体无关） |
| 服务端推送与设备登记（`/devices/*`） | `enableNativeApp` | — | ⛔ 契约保留、不注册路由 |
| 微信小程序 / iOS·Android App | `enableMiniprogram` / `enableNativeApp` | — | ⛔ 契约保留、不注册路由 |

> **掩藏 = 写契约与开关，但不注册路由、不打包、不可达**；能力开关默认关，且**禁止被运行期远端配置打开**（见 [02-3 §六](../02-系统架构/03-存储与后端策略.md#六掩藏层写代码但不启用)）。上表中**只有多角色 RBAC 属「本期不做」**（单人维护下过度设计、**与企业主体无关**），其余均为**需企业主体**的合规约束。

**多端相关约定速查**（详见 [1.6](#16-客户端标识与多端约定) / [1.7](#17-向后兼容硬要求)）：

| 约定 | 要求 |
| --- | --- |
| 请求头 | 所有请求必带 `X-Client-Client` / `X-Client-Platform` / `X-Client-Form` / `X-Client-Version` |
| 能力集 | 携带 `X-Client-Capabilities`，服务端据此决定降级行为 |
| 字段兼容 | **只增不改不删**；枚举值只增；客户端遇未知枚举必须兜底不崩 |
| 版本策略 | 破坏性变更走 `/api/v2`，v1 并行保留 ≥ 3 个月 |

---

## 十二、掩藏接口（契约保留、不注册路由）

以下能力**写契约与开关，但不注册任何路由**，即使客户端被绕过也调不到（其中**多角色 RBAC 属「本期不做」**，与企业主体无关；其余属**需企业主体**的掩藏能力）：

| 能力 | 开关名 | 说明 |
| --- | --- | --- |
| 手机号 / 短信 OTP、微信授权登录、账号绑定 | `enableAccountAuth` | 需企业主体，契约保留 |
| 支付与订阅 `/billing` | `enablePayment` | 需企业主体（商户号），契约保留 |
| 多角色 RBAC `/admin/roles` | `enableAccountAuth` | **本期不做**：单管理员体系下多角色属过度设计（与企业主体无关） |
| 服务端推送与设备登记 `/devices/*` | `enableNativeApp` | 需推送服务，契约保留 |
| 微信小程序 / iOS·Android App | `enableMiniprogram` / `enableNativeApp` | 需企业主体，契约保留 |

> ⚠️ 普通用户接口里只有「设备会话」是已实现的：服务端在登录/刷新时按 `(account_id, client_id)` 写入 `devices` 集合（用于登录吊销），但**不对外暴露 `/devices/*` 路由**。

---

## 十三、前后端并行开发建议

1. **先冻结本文件的通用约定章节**（响应结构、错误码、分页），一旦确定不再改动。
2. 前端用 Mock 数据按本文档先行开发，接口路径与字段名严格对齐。
3. 后端优先实现 `/auth`、`/children`、`/content/bootstrap`、`/learning/state` 四个接口，即可支撑最小联调闭环。
4. 每个接口实现后，用 FastAPI 的 `/docs` 与本文档做一次比对，有出入则更新本文档。

---

## 十四、下一步

接口定义完成后：

- **邀请码身份与准入的完整设计与安全模型** → [02-5 邀请码身份与准入体系](../02-系统架构/05-邀请码身份与准入体系.md)
- 存储策略与服务端职责分层 → [02-3 存储与后端策略](../02-系统架构/03-存储与后端策略.md)
- 集合设计与数据字典（含 `accounts` / `invites`） → [03-1 集合设计](../03-数据设计/01-MongoDB集合设计.md)、[03-2 数据字典](../03-数据设计/02-数据字典.md)
- 内容管理与贡献流程 → [05-1 内容管理与用户管理体系](../05-管理后台/01-内容管理与用户管理体系.md)
- 编码规范与目录约定 → [06-1 开发规范与前端架构](../06-工程规范/01-开发规范与前端架构.md)
- 多端形态与能力分级 → [02-2 多端适配与响应式设计规范](../02-系统架构/02-多端适配与响应式设计规范.md)
- 未来可优化方向 → [02-4 架构演进与优化方向](../02-系统架构/04-架构演进与优化方向.md)
