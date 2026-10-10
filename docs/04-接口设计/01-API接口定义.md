# 04-1 API 接口定义

> 本文档用于设计评审与前后端并行开发。
> **最终事实来源是 FastAPI 自动生成的 OpenAPI 文档**（`/docs` 与 `/openapi.json`），本文件与代码不一致时以代码为准。

---

## 〇、接口分层（先读这一节）

系统有三种数据来源，**同一份数据结构、同一套解析逻辑**。接口文档按此分层阅读：

| 层 | 形式 | 需要后端 | 当前状态 | 说明 |
| --- | --- | --- | --- | --- |
| **A. 静态内容包** | 仓库内 JSON（随包构建 / 远端静态托管） | ❌ | ✅ **默认** | 内容的主路径，见 1.8 |
| **B. 云端后台接口** | HTTP + JSON | ✅（已有服务器） | ✅ **部署目标** | 邀请码身份、云端档案、匿名统计、内容后台、反馈 |
| **C. 掩藏接口** | HTTP + JSON | ✅ | ⛔ **需企业主体** | 见 [第十章](#十接口总览表) 掩藏表 |

> ⚠️ **三层必须产出同一份数据结构**，因此**内容包 JSON Schema 与接口响应结构同源**（字段定义唯一来源：[03-2 数据字典](../03-数据设计/02-数据字典.md)）。这样「有后端」与「无后端」的客户端行为完全一致。
>
> ⚠️ **层 B 是「已部署」而非「预留」**：云端后台会真实上线。但**客户端必须能在层 B 不可达时完整运行**——所有层 B 接口都必须可降级（内容落到层 A、身份落到本地、统计静默丢弃）。

---

## 一、通用约定

### 1.1 基础信息

| 项 | 约定 |
| --- | --- |
| Base URL | `https://api.example.com/api/v1` |
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

> `code = 0` 表示成功，**HTTP 状态码同时保持语义正确**（200/400/401/403/404/429/500）。

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
| `401xx` | 认证失败 | `40101` Token 过期 / `40102` Token 无效 |
| `403xx` | 权限不足 | `40301` 无权访问该儿童档案 |
| `404xx` | 资源不存在 | `40401` 汉字不存在 / `40402` 古诗不存在 |
| `409xx` | 状态冲突 | `40902` 内容已存在 |
| `429xx` | 频率限制 | `42901` 请求过于频繁 |
| `500xx` | 服务端错误 | `50001` 内部错误 / `50002` 第三方服务不可用 |

**常用业务错误码**

| 码 | 含义 | 前端处理 |
| --- | --- | --- |
| `40101` | Access Token 过期 | 静默刷新 Token 后重试 |
| `40102` | Token 无效 | 跳转登录 |
| `40301` | 无权访问该儿童档案 | 提示并返回档案选择页 |
| `40401` | 汉字不存在 | 提示 |
| `42901` | 请求过于频繁 | 提示稍后重试 |

### 1.5 幂等性

| 场景 | 机制 |
| --- | --- |
| 离线答题批量上报 | 每条记录带客户端生成的 `client_record_id`，服务端去重 |
| 内容创建 | 唯一字段冲突返回 `40902` |

### 1.6 客户端标识与多端约定

**所有请求必须携带以下请求头**，由各端 `HttpAdapter` 统一注入（业务代码不感知）：

| 请求头 | 必填 | 取值 | 用途 |
| --- | --- | --- | --- |
| `X-Client-Client` | ✅ | `web` / `miniprogram` / `app` | 外壳类型 |
| `X-Client-Platform` | ✅ | `ios` / `android` / `harmony` / `web` | 系统平台 |
| `X-Client-Form` | ✅ | `phone` / `tablet` / `desktop` | 形态（**按可用宽度判定，不按设备型号**） |
| `X-Client-Version` | ✅ | 语义化版本，如 `2.1.0` | 客户端版本 |
| `X-Client-Capabilities` | ⚠️ | 逗号分隔能力名 | 运行时能力集（机制见 [06-1 §2.8](../06-工程规范/01-开发规范与前端架构.md#28-能力开关与仓储层规范)） |

**为什么必须**：

1. 服务端据此把 `client` / `platform` / `device_form` 写入 `learning_records`（见 [03-2](../03-数据设计/02-数据字典.md)），支撑分端分析
2. **服务端按 `X-Client-Version` 做兼容降级**——小程序无法强制升级，旧版本客户端会长期存在
3. 排查"只在某个端出现"的缺陷时，可直接按端过滤请求日志

**`X-Client-Capabilities`（能力集上报）**

```
X-Client-Capabilities: record,local_asr,realtime_audio,handwriting,offline,push
```

> 此处只约定**请求头契约**。能力集的取值、服务端降级规则与前端实现机制见 [06-1 §2.8](../06-工程规范/01-开发规范与前端架构.md#28-能力开关与仓储层规范)；客户端能力分级见 [02-2 §7](../02-系统架构/02-多端适配与响应式设计规范.md#七能力分级与降级)。

### 1.7 向后兼容（硬要求）

小程序无法强制升级，App 也有大量未升级用户，因此**兼容不是最佳实践而是硬要求**：

| 规则 | 说明 |
| --- | --- |
| 字段**只增不改不删** | 新增字段必须可选；删除字段须先经历"废弃期"（≥ 3 个月，期间双写） |
| 枚举值**只增** | 客户端遇到未知枚举值必须兜底渲染，**不得崩溃** |
| 错误码不复用 | 同一码不得改变含义 |
| 破坏性变更走 `/api/v2` | v1 至少并行保留 3 个月 |

---

### 1.8 静态内容包契约（层 A，不走 HTTP 接口）

这是**内容的主路径**——内容以文件形式随仓库分发或由静态托管提供，**不需要任何后端**。

**① 清单文件 `content/manifest.json`**

```json
{
  "content_version": "1.3.0",
  "min_app_version": "1.0.0",
  "updated_at": "2026-10-08T00:00:00Z",
  "counts": { "characters": 500, "poems": 75, "units": 24, "lessons": 96 },
  "files": [
    { "path": "characters/grade-1.json", "checksum": "sha256:...", "bytes": 182340, "count": 500 },
    { "path": "poems/required-75.json", "checksum": "sha256:...", "bytes": 41200, "count": 75 },
    { "path": "lessons/units.json",    "checksum": "sha256:...", "bytes": 9800,  "count": 24 }
  ]
}
```

**② 客户端加载与更新流程**

```
启动
 ├─ 读本地缓存 manifest（首启用随包内容）
 ├─ 静默请求远端 manifest.json（静态托管；超时 3s）
 │    ├─ 成功 → 比对 content_version 与各文件 checksum
 │    │         ├─ min_app_version ≤ 当前版本 → 下载变更文件 → 写入 Cache Storage
 │    │         └─ min_app_version >  当前版本 → ⚠️ 忽略该更新（不提示、不报错）
 │    └─ 失败 / 超时 → 静默忽略
 └─ 用可用内容渲染（绝不阻塞启动）
```

**③ 硬性约定**

| 约定 | 说明 |
| --- | --- |
| 字段与接口响应同源 | 内容包的字段名/类型 = `/content/*` 接口响应结构 = `03-2 数据字典` |
| 必须带 `min_app_version` | 防止新内容在老客户端上渲染崩溃 |
| 用 checksum 而非时间戳判断更新 | CDN 缓存会导致时间戳不可靠 |
| 更新失败必须静默 | 内容更新绝不能阻塞或报错 |
| 单文件条目数上限 | 建议 ≤ 500 条/文件，便于增量下载与 diff 审查 |
| 素材引用用相对路径 | 存 `assets/...` 相对路径而非绝对 URL，便于整体迁移 |

> **与后端接口的关系**：形态 B 部署后，`/content/*` 接口**返回完全相同的结构**，客户端可无感切换（由 `enableContentApi` 决定）。内容包契约与接口响应并列为一等契约。

---

## 二、认证与身份模块 `/auth` · `/devices`

> 身份方式为 **邀请码 + 自设口令**（见 [02-5 邀请码身份与准入体系](../02-系统架构/05-邀请码身份与准入体系.md)）；短信 OTP 与微信授权登录属 ⛔ 掩藏，见 [第十章](#十接口总览表)。离线签名码由客户端本地验签，无需后端。

### 2.1 账号身份（用户名 / 手机号 + 口令，✅ 当前）

> 主入口是 `POST /auth/register` 与 `POST /auth/login`；下方的 `/auth/invite/*`
> 是同一套身份模型的**兼容旧路径**（客户端已不再调用，保留以兼容已分享的旧链接与旧版本）。
> 请求体结构完全一致，仅 `identifier` 的解析优先级不同（`identifier → account → invite_code`）。

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| POST | `/auth/register` | **统一注册**：用户名 / 手机号（至少一个）+ 口令；邀请码按开关可选 | ❌ |
| POST | `/auth/login` | **统一登入**：`identifier` 可填用户名或手机号 | ❌ |
| POST | `/auth/invite/verify` | 仅校验邀请码是否可用（注册前预检，不消耗次数） | ❌ |
| POST | `/auth/invite/register` | 用邀请码 + 口令注册，创建匿名账号与家庭档案 | ❌ |
| POST | `/auth/invite/login` | 邀请码 + 口令登入 | ❌ |
| POST | `/auth/recovery/reset` | 用恢复码重置口令（并重派生加密密钥） | ❌ |
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
> 1. **错误信息统一**：邀请码无效、已用尽、口令错误一律返回 `40101`「邀请码或口令不正确」，**绝不区分原因**（防用户与邀请码枚举）。
> 2. **`recovery_code` 只返回一次**，服务端只存哈希；前端必须强制用户抄写确认。
> 3. **限流与锁定**：限流 10 次/10 分钟、连续 5 次失败锁定 15 分钟。
>    ⚠️ 限流键是**客户端形态指纹**（client/platform/device_form/version 的哈希），
>    **刻意不含 `client_id`** —— 它是客户端可控值，拼进限流键等于允许「换个 id 换一个计数桶」来绕过限流。
> 4. **`client.client_id` 是设备身份，不是用户身份**：客户端必须上报一个**持久化的随机 id**
>    （web 端存 `localStorage['sc.deviceId']`）。服务端按 `(account_id, client_id)` 存 `devices`
>    会话记录，**一台设备一条**，因此多台设备可同时在线、各自登出互不影响。
>    若不上报，服务端退化为按形态指纹认设备，同形态的两台设备会互相覆盖 Refresh Token
>    （现象：一台登录，另一台被踢下线）。

### 2.2 离线签名邀请码（⏸️ 无后端形态）

**不走接口**——客户端用内置公钥对码内签名本地验签，无需任何网络请求。

```
code = base32(payload) || base32(ed25519_sign(privkey, payload))
payload = { ver, tier, expires_at, batch, nonce }
```

> 公钥随开源代码公开；私钥仅维护者持有。用途：形态 A（无服务器）也能实现邀请制。详见 [02-5 6.1](../02-系统架构/05-邀请码身份与准入体系.md#61--离线签名邀请码无需后端)。

### 2.3 云端档案同步（✅ 当前，默认关闭 + 默认端到端加密）

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| GET | `/sync/manifest` | 取云端档案清单与版本（用于增量同步，返回的是**密文块索引**） | ✅ |
| POST | `/sync/push` | 上传本地变更（密文） | ✅ |
| GET | `/sync/pull` | 拉取远端变更（密文） | ✅ |
| GET | `/sync/salt` | 取 KDF 盐（用于口令派生加密密钥） | ✅ |

> ⚠️ **服务端只存密文**：`push` / `pull` 的载荷在客户端用「口令 → Argon2id → 密钥」加密，服务端**无法解密**。因此联调时看到的是不可读的 blob，这是设计使然（见 [02-5 4.5](../02-系统架构/05-邀请码身份与准入体系.md#45--端到端加密同步推荐)）。

### 2.4 邀请码管理（✅ 自托管后台）

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| POST | `/admin/invites/batch` | 批量生成邀请码（指定数量、有效期、`max_uses`） | 管理员 |
| GET | `/admin/invites` | 邀请码列表（只返回 `code_hint`，**不返回完整码**） | 管理员 |
| POST | `/admin/invites/{id}/revoke` | 吊销邀请码 | 管理员 |

### 2.5 ⛔ 掩藏：账号体系（需企业主体）

> 短信 OTP（`/auth/account/otp/*`）、微信授权登录（`/auth/account/wechat`）、账号绑定（`/auth/account/bind`，即将来把邀请码账号升级为实名账号的退路）属 ⛔ 掩藏，**契约保留、不启用**。完整清单见 [第十章](#十接口总览表)。

---

### 设备与推送 `/devices`

多端上线后，同一账号会在 Web / 小程序 / App 及多台设备上登录，需登记设备与会话以支持登录吊销、推送与分端分析（集合定义见 [03-1 §七](../03-数据设计/01-MongoDB集合设计.md#七系统与同步域)）。

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| POST | `/devices/register` | 登录后登记/更新当前设备与推送标识 | ✅ |
| POST | `/devices/subscribe` | 上报已订阅的推送主题（**小程序一次性订阅**） | ✅ |
| DELETE | `/devices/{device_id}` | 注销设备（退出登录 / 关闭推送） | ✅ |

**POST `/devices/register`**

```json
{
  "client": "app",
  "platform": "ios",
  "device_form": "phone",
  "push_provider": "apns",
  "push_token": "…",
  "app_version": "1.3.0",
  "os_version": "iOS 19.1",
  "device_model": "iPhone17,2"
}
```

> **说明**：
> - `push_token` 为 `null` 时（如 Web 端、小程序端）只登记设备、不注册推送，服务端据此跳过该设备的推送投递。
> - 服务端按 `push_token` 做 **upsert**：同一设备重复登录不会产生多条记录。
> - 推送失败（token 失效）时服务端把 `enabled` 置 `false` 而非删除，便于统计卸载率。

**POST `/devices/subscribe`**

```json
{ "topics": ["daily_task"], "granted_count": 1 }
```

> ⚠️ **小程序订阅消息为一次性授权**：每授权一次只能收一条。因此该接口会被**高频调用**（每次完成学习引导订阅时），服务端以"累加剩余可发次数"的方式处理，不做幂等去重。发完即失效，需持续引导。

---

## 三、儿童档案 `/children`

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

## 四、内容模块 `/content`

### 4.1 汉字

| 方法 | 路径 | 说明 | 认证 |
| --- | --- | --- | --- |
| GET | `/content/characters` | 列表查询（支持筛选） | ✅ |
| GET | `/content/characters/{char_id}` | 汉字详情 | ✅ |
| GET | `/content/characters/by-char/{char}` | 按字符查询 | ✅ |
| GET | `/content/characters/batch` | 批量获取（用 `ids` 参数） | ✅ |
| GET | `/content/characters/{char_id}/similar` | 形近字 | ✅ |

**列表查询参数**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `grade` | int | 年级筛选 |
| `level` | string | 学段筛选 |
| `tags` | string | 标签，逗号分隔 |
| `unit_id` | string | 按自编单元 |
| `status` | string | 仅后台可用，默认 `published` |
| `keyword` | string | 搜索汉字、释义、组词 |

**响应示例**

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

### 4.2 古诗

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/content/poems` | 列表（按年级/主题/来源筛选） |
| GET | `/content/poems/{poem_id}` | 详情（含逐句注音与释义） |
| GET | `/content/poems/{poem_id}/quiz` | 生成古诗练习题 |
| GET | `/content/poems/by-char/{char}` | 按汉字反查古诗句 |

**查询参数**：`grade`、`theme_tags`、`source`（`课标必背`/`蒙学经典`/`拓展`）、`keyword`

### 4.3 故事与自编单元

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/content/stories` | 故事列表 |
| GET | `/content/stories/{story_id}` | 故事详情 |
| GET | `/content/units` | 自编单元列表 |
| GET | `/content/units/{unit_id}` | 单元详情（含字表） |

### 4.4 关卡

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/content/lessons` | 关卡列表（含解锁状态） |
| GET | `/content/lessons/{lesson_id}` | 关卡详情 |
| GET | `/content/lessons/{lesson_id}/questions` | **生成该关卡题目** |

> **题目生成为服务端行为**：迁移到服务端的好处是题目可基于用户历史表现动态调整，且题型策略可热更新。

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

---

## 五、学习模块 `/learning`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/learning/daily-task` | 获取今日任务（不存在则懒生成） |
| POST | `/learning/answer` | 提交单题作答 |
| POST | `/learning/answer/batch` | 批量上报（离线补偿） |
| POST | `/learning/lesson/complete` | 提交关卡完成 |
| GET | `/learning/review/due` | 获取到期应复习字 |
| GET | `/learning/wrong-questions` | 错题本 |
| POST | `/learning/wrong-questions/{id}/resolve` | 标记订正 |
| GET | `/learning/progress` | 学习进度总览 |

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

**说明**：用于离线模式补偿上报。服务端按 `client_record_id` 去重，返回成功与跳过的计数。

```json
{
  "code": 0,
  "data": { "accepted": 48, "skipped_duplicate": 2 }
}
```

---

## 六、测评模块 `/assessment`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/assessment/tone-template/{char_id}` | 获取标准声调模板（F0 曲线） |
| POST | `/assessment/tone` | 提交声调评测结果 |
| POST | `/assessment/pronounce` | 提交语音做精细评测（`enableCloudAssessment`，可选云端增强，**默认关闭**，无 Key 整块隐藏） |
| GET | `/assessment/pronounce/quota` | 查询剩余评测次数 |

### 6.1 声调评测（本地优先方案）

**设计说明**：F0 提取与声调比对**在客户端完成**（详见架构文档语音评测章节），服务端只负责提供标准模板与记录成绩。

**GET `/assessment/tone-template/{char_id}` 响应**

```json
{
  "code": 0,
  "data": {
    "char": "水",
    "pinyin": "shuǐ",
    "tone": 3,
    "template_curve": [0.52, 0.48, 0.41, 0.35, 0.33, 0.38, 0.47, 0.55],
    "tolerance": 0.18
  }
}
```

**POST `/assessment/tone` 请求**

```json
{
  "child_id": "6512...",
  "character_id": "6513...",
  "detected_curve": [0.50, 0.46, 0.40, 0.36, 0.34, 0.39, 0.45, 0.53],
  "tone_score": 0.87,
  "passed": true,
  "duration_ms": 820
}
```

### 6.2 精细发音评测（云端方案，按量计费）

**POST `/assessment/pronounce`**

**请求**：`multipart/form-data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `child_id` | string | 儿童档案 |
| `character_id` | string | 目标汉字 |
| `audio` | file | 音频，16kHz 单声道，≤ 10 秒 |

**响应**

```json
{
  "code": 0,
  "data": {
    "overall_score": 82,
    "accuracy": 85,
    "fluency": 78,
    "tone_score": 90,
    "phoneme_details": [
      { "phoneme": "sh", "score": 88, "issue": null },
      { "phoneme": "u", "score": 84, "issue": null },
      { "phoneme": "i", "score": 72, "issue": "声调偏低，注意第三声先降后升" }
    ],
    "quota_remaining": 47
  }
}
```

> **合规约束**：上传的语音**仅用于本次评测，评测完成后立即删除，不落地存储、不用于模型训练**。此约束需在接口实现中强制执行，并在隐私政策中明确告知。

---

## 七、报告模块 `/reports`

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

## 八、⛔ 掩藏：支付与订阅 `/billing`

> 支付与订阅需企业主体（商户号），⛔ 掩藏，**契约保留、不启用**。完整清单见 [第十章](#十接口总览表)。

---

## 九、管理后台 `/admin`

**单管理员后台（不做 RBAC）**：所有接口需管理员身份，且写操作记入 `audit_logs`。

### 9.1 内容管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/characters` | 字库列表（含草稿） |
| POST | `/admin/characters` | 新建汉字 |
| PATCH | `/admin/characters/{id}` | 修改汉字 |
| DELETE | `/admin/characters/{id}` | 下架 |
| POST | `/admin/characters/import` | **批量导入（Excel/CSV）** |
| GET | `/admin/characters/export` | 批量导出 |
| POST | `/admin/characters/{id}/submit-review` | 提交审核 |
| POST | `/admin/characters/{id}/approve` | **审核通过并上架** |
| POST | `/admin/characters/{id}/reject` | 驳回 |
| GET | `/admin/characters/quality-check` | 内容质量检查报告 |
| GET | `/admin/characters/{id}/versions` | 版本历史 |
| POST | `/admin/characters/{id}/rollback` | 版本回滚 |

**批量导入**

**请求**：`multipart/form-data`，字段 `file`（.xlsx/.csv）、`mode`（`insert` / `upsert`）、`dry_run`（bool）

**响应**

```json
{
  "code": 0,
  "data": {
    "total_rows": 500,
    "created": 480,
    "updated": 15,
    "failed": 5,
    "errors": [
      { "row": 12, "field": "pinyin", "reason": "拼音格式不正确" },
      { "row": 88, "field": "meaning", "reason": "释义为空" }
    ]
  }
}
```

> **`dry_run=true` 时只校验不写入**，用于导入前预检。这是内容运营最常用的功能，应优先实现。

### 9.2 古诗与其他内容

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST/PATCH/DELETE | `/admin/poems` `/admin/poems/{id}` | 古诗 CRUD |
| POST | `/admin/poems/import` | 古诗批量导入 |
| GET/POST/PATCH/DELETE | `/admin/stories` `/admin/stories/{id}` | 故事 CRUD |
| GET/POST/PATCH/DELETE | `/admin/units` `/admin/units/{id}` | 自编单元与字表 |
| GET/POST/PATCH/DELETE | `/admin/lessons` `/admin/lessons/{id}` | 关卡编排 |

### 9.3 素材管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/admin/assets/upload` | 上传素材（返回素材 ID） |
| POST | `/admin/assets/batch-upload` | 批量上传 |
| POST | `/admin/assets/{id}/bind` | 批量绑定到汉字/古诗 |
| GET | `/admin/assets` | 素材列表 |
| DELETE | `/admin/assets/{id}` | 归档素材（检查引用后） |

### 9.4 账号与审计

账号相关接口的实际路径是 `/admin/users/*`（**不是** `/admin/accounts/*`）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/users` | 账号列表。支持 `keyword` / `status` / `has_children` / `registered_from` / `registered_to` 筛选；手机号**只出掩码** |
| GET | `/admin/users/stats` | 账号体量聚合（总数 / 分状态 / 有无手机号 / 孩子档案数） |
| GET | `/admin/users/{id}` | 账号详情（含档案数） |
| PATCH | `/admin/users/{id}` | **编辑展示资料**：`display_name` / `avatar_key` / `access_tier`。`extra="forbid"`，越权字段 422 |
| POST | `/admin/users/{id}/status` | 启用 / 禁用（可逆） |
| DELETE | `/admin/users/{id}` | **注销**（不可逆）：释放邀请码、撤销全部会话，**保留孩子档案与学习数据** |
| POST | `/admin/users/bulk/status` | 批量启用 / 禁用（上限 100）。返回成功与失败的 id，不静默吞掉失败项 |
| GET | `/admin/users/{id}/report` | 账号级学习报告（已认 / 掌握 / 正确率 / 趋势） |
| GET | `/admin/children` | 儿童档案列表 |
| GET | `/admin/audit-logs` | 操作审计日志 |

> ⚠️ **注销与删除云端数据是两件事**：`DELETE /admin/users/{id}` 是软删，
> 保留学习数据 —— 这是儿童数据最小化的底线。需要真正清除数据时走导出/注销账号流程，
> 不在后台提供「一键抹掉」。

> ⛔ `/admin/roles`（多角色 RBAC）属**掩藏**（需企业主体，见 05-1「单管理员后台、不做 RBAC」）；
> 当前只做单管理员，**不建角色表、不做权限矩阵**，`role` 字段也不可编辑。

### 9.5 内容维护

内容 CRUD 是一套**数据驱动**的通用接口：集合差异由 `content_registry` 的数据描述。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/registry` | 内容类型描述（必填字段 / 可搜索字段 / 筛选字段 / 是否有模板） |
| GET | `/admin/content/{collection}` | 列表（分页 + `status` / `keyword` / `grade` / `level` 筛选） |
| POST | `/admin/content/{collection}` | 新建（`_id` 由服务端按类型规则派生） |
| PATCH | `/admin/content/{collection}/{id}` | 更新（`version` 自增） |
| DELETE | `/admin/content/{collection}/{id}` | **下架**（软删：置 `status=offline`，不物理删除） |
| GET | `/admin/content/{collection}/export` | 导出为可回写仓库的 JSON（剔除时间戳） |
| GET | `/admin/content/{collection}/template` | **下载模板**：字段说明 + 一条示例；派生字段标 `derived` |
| POST | `/admin/content/import` | 导入（幂等 upsert，可反复重跑） |
| GET | `/admin/content/import/preview` | 各来源文件的条数与库内现有量 |

> ⚠️ `/content/import/preview` 与 `/content/{collection}/template` **必须声明在
> `/content/{collection}` 之前**，否则固定路径段会被路径参数吃掉。

### 9.6 运营看板

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/overview` | 内容完整度概览（只给聚合计数，不下钻个体） |
| GET | `/admin/dashboard/content` | 内容覆盖与质量分布（规划中） |
| GET | `/admin/dashboard/learning` | 学习效果（掌握率、错误率）（规划中） |

---

## 十、接口总览表

### 10.1 ✅ 当前（层 A + 层 B，不需要企业主体）

| 模块 | 接口数 | 状态 | 说明 |
| --- | --- | --- | --- |
| **静态内容包**（非 HTTP） | — | ✅ **主路径** | 见 [1.8](#18-静态内容包契约层-a不走-http-接口) |
| `/auth/invite/*` `/auth/recovery/*` | 8 | ✅ 部署 | **邀请码身份 + 恢复码** |
| `/sync/*` | 4 | ✅ 部署 | 云端档案同步（**默认关闭 + 端到端加密**） |
| `/children` | 4 | ✅ 部署 | 家庭档案下的孩子档案 |
| `/content` | 9 | ✅ 部署 | 云端后台内容接口（与静态内容包**同结构**） |
| `/learning` | 6 | ✅ 部署 | 学习与复习（本地为主，可选上报） |
| `/assessment` | 2 | ✅ 部署 | 声调评测（本地计算，接口仅用于可选云端增强代理） |
| `/reports` | 3 | ✅ 部署 | 学情报告（本地生成，可选云端聚合） |
| `/stats` | 3 | ✅ 部署 | **匿名统计上报**（聚合计数，无个人标识） |
| `/feedback` | 2 | ✅ 部署 | 用户反馈与内容纠错 |
| `/admin/invites/*` `/admin/content/*` | 12 | ✅ 部署 | **单管理员**内容后台与邀请码管理 |
| **小计** | **约 53** | — | — |

### 10.2 ⛔ 掩藏（需企业主体，契约保留）

| 能力 | 开关名 | 契约位置 | 状态 |
| --- | --- | --- | --- |
| 手机号 / 微信账号（短信 OTP、微信授权登录、账号绑定） | `enableAccountAuth` | §2.5 / §9.4 | ⛔ 需企业主体，不启用 |
| 支付与订阅（`/billing`） | `enablePayment` | §八 | ⛔ 需企业主体，不启用 |
| 多角色 RBAC 内容后台（`/admin/roles`、`/admin/users`） | `enableAccountAuth` | §9.4 | ⛔ 需企业主体，不启用 |
| 服务端推送（`/devices` 推送订阅部分） | `enableNativeApp` | §二 | ⛔ 需企业主体，不启用 |
| 微信小程序 / iOS·Android App | `enableMiniprogram` / `enableNativeApp` | [02-3 预留清单](../02-系统架构/03-uni-app跨端方案与小程序适配.md#二预留清单当前不写不构建) | ⛔ 需企业主体，不启用 |

> **总量**：当前约 53 个可用接口 + 约 18 个掩藏接口 = **71+**。内容通过静态包而非接口下发，因此读接口很少。

**多端相关约定速查**（详见 [1.6](#16-客户端标识与多端约定) / [1.7](#17-向后兼容硬要求)）：

| 约定 | 要求 |
| --- | --- |
| 请求头 | 所有请求必带 `X-Client-Client` / `X-Client-Platform` / `X-Client-Form` / `X-Client-Version` |
| 能力集 | 携带 `X-Client-Capabilities`，服务端据此决定下发内容与功能开关 |
| 字段兼容 | **只增不改不删**；枚举值只增；客户端遇未知枚举必须兜底不崩 |
| 版本策略 | 破坏性变更走 `/api/v2`，v1 并行保留 ≥ 3 个月（小程序无法强制升级） |

---

## 十一、前后端并行开发建议

1. **先冻结本文件的通用约定章节**（响应结构、错误码、分页），一旦确定不再改动。
2. 前端用 Mock 数据按本文档先行开发，接口路径与字段名严格对齐。
3. 后端优先实现 `/auth`、`/children`、`/content/characters`、`/learning/daily-task` 四个接口，即可支撑最小联调闭环。
4. 每个接口实现后，用 FastAPI 的 `/docs` 与本文档做一次比对，有出入则更新本文档。

---

## 十二、下一步

接口定义完成后：

- **邀请码身份与准入的完整设计与安全模型** → [02-5 邀请码身份与准入体系](../02-系统架构/05-邀请码身份与准入体系.md)
- 后端分层与形态选择（形态 A/B/C） → [02-4 本地优先与后端策略](../02-系统架构/04-本地优先与后端策略.md)
- 集合设计与数据字典（含 `accounts` / `invites`） → [03-1 集合设计](../03-数据设计/01-MongoDB集合设计.md)、[03-2 数据字典](../03-数据设计/02-数据字典.md)
- 内容管理与贡献流程 → [05-1 内容管理与用户管理体系](../05-管理后台/01-内容管理与用户管理体系.md)
- 编码规范与目录约定 → [06-1 开发规范与前端架构](../06-工程规范/01-开发规范与前端架构.md)
- 多端形态与降级规则 → [02-2 多端适配与响应式设计规范](../02-系统架构/02-多端适配与响应式设计规范.md)
- 小程序与 App 工程实现（**备查，当前不启动**） → [02-3 uni-app 跨端方案与小程序适配](../02-系统架构/03-uni-app跨端方案与小程序适配.md)
