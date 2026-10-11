# 数据设计

> 本文是面向用户与贡献者的导读，完整设计见 [03-1 MongoDB 集合设计](https://gitee.com/perry-space/study-club/blob/master/docs/03-数据设计/01-MongoDB集合设计.md) 与 [03-2 数据字典](https://gitee.com/perry-space/study-club/blob/master/docs/03-数据设计/02-数据字典.md)（Gitee）。

学习俱乐部（study-club）的全部业务数据保存在**服务端 MongoDB 7**。**MongoDB 是服务端唯一真源**：账号、儿童档案、学习记录、复习状态、错题、每日任务、徽章、同步密文与全部内容都以服务端为准；浏览器只保留四类凭据与 UI 偏好键（`sc.session` / `sc.deviceId` / `sc.currentChild` / `sc.loginMemory`），**不承载任何业务数据**。

## 一、集合怎么划

集合按**域**划分，一个域一层职责，跨域只通过外键关联：

| 域 | 管的什么 | 主要集合 |
| --- | --- | --- |
| **身份域** | 邀请码身份、设备会话、云端密文、统计与反馈 | `accounts` `invites` `recovery_codes` `devices` `sync_objects` `stats_events` `feedbacks` |
| **内容域** | 汉字 / 古诗 / 单元 / 关卡 / 故事 / 短文 / 徽章 / 素材 | `characters` `poems` `curriculum_units` `lessons` `stories` `readings` `badges` `assets` |
| **学习域** | 学习主体与学习过程中产生的数据 | `children` `learning_records` `answer_records` `char_review_states` `wrong_questions` `daily_tasks` `child_badges` |
| **系统域** | 审计日志、内容包清单、站点运行配置 | `audit_logs` `content_manifest` `app_settings` |

> 集合命名统一小写 `snake_case` 复数；字段名同样 `snake_case`，前端转 camelCase。主键为 MongoDB `ObjectId`，对外暴露为字符串；时间一律 UTC `ISODate`。

## 二、各域职责与主要集合

### 身份域

| 集合 | 职责 | 状态 |
| --- | --- | --- |
| `accounts` | 邀请码身份主体，**不存任何身份信息**（无手机号、邮箱、真实姓名） | ✅ |
| `invites` | 邀请码发放、用量与吊销，**只存哈希** | ✅ |
| `recovery_codes` | 忘记口令时的自救通道，一次性 | ✅ |
| `devices` | 设备与会话，支撑登录吊销与分端分析 | ✅ 可选 |
| `sync_objects` | 云端家庭档案密文块，**服务端不可解密** | ✅ 可选（默认关） |
| `stats_events` | 匿名统计，**只存聚合计数、无个人标识** | ✅ 可选 |
| `feedbacks` | 用户反馈与内容纠错 | ✅ 可选 |

### 内容域

| 集合 | 职责 | 说明 |
| --- | --- | --- |
| `characters` | 汉字主表（**全系统最重要**） | 核心资产，字段与内容包 JSON 一致 |
| `poems` | 古诗 | 原文取自开源数据集，注音 / 赏析自编 |
| `curriculum_units` | **自编单元** | 按主题 / 难度编排，**非出版社映射** |
| `lessons` | 关卡（课程编排） | 关联单元与古诗 |
| `stories` | 故事与儿歌 | — |
| `readings` | 识字短文（阅读承接） | 只用已学字编写，覆盖率 ≥ 75% |
| `badges` | 徽章定义 | 数据驱动，可直接新增 |
| `assets` | 素材（音频 / 图片 / 笔顺） | `copyright` 必填，引用只存 `_ref` |

### 学习域与系统域

| 集合 | 职责 |
| --- | --- |
| `children` | 儿童档案（**学习主体的唯一真源**） |
| `learning_records` | 学习行为流水，追加型、永不更新 |
| `answer_records` | 答题明细（`char` 有意反范式） |
| `char_review_states` | 每字复习状态（SRS 核心） |
| `wrong_questions` | 错题本，同字多次答错累加计数 |
| `daily_tasks` | 每日任务，用户当天首次进入时懒生成 |
| `child_badges` | 已获徽章 |
| `audit_logs` | 操作审计（**绝不记明文码 / 口令 / 密文载荷**） |
| `content_manifest` | 内容包清单（承接 `content/manifest.json`） |
| `app_settings` | 站点运行配置（单文档 `_id = "site"`，改完即生效） |

## 三、哪张集合是唯一真源

- **`children` 是学习主体的唯一真源**：儿童档案（昵称、年级、学习目标、累计统计）全部存这里；儿童不单独注册账号，挂在 `accounts` 下，一个账号可对应 1–N 个儿童。
- **`char_review_states` 是复习调度的唯一真源**：每个字的间隔、难度系数与下次复习时间以服务端为准，客户端只渲染到期结果，保证跨设备口径一致。
- **内容域集合是内容的唯一真源**：`content/**/*.json` 是导入种子，导入 MongoDB 后由 `/content/*` 接口下发；**内容以 MongoDB 为准**。
- 浏览器**只保留四类凭据与 UI 偏好键**，不含任何业务数据。

> ⚠️ 云端家庭档案（`sync_objects`）**默认关闭**；开启时**默认端到端加密**，密钥由用户口令在客户端派生（Argon2id），服务端无论如何都解不开。

## 四、数据字典去哪看

字段级定义集中维护在 [03-2 数据字典](https://gitee.com/perry-space/study-club/blob/master/docs/03-数据设计/02-数据字典.md)（**单一事实来源**，其他文档引用而不复制）。它包含：

| 部分 | 内容 |
| --- | --- |
| **通用约定** | 命名、时间、金额、空值、素材引用、软删除规则 |
| **各集合字段表** | 字段 / 类型 / 必填 / 唯一 / 说明 |
| **枚举值汇总** | 学段、年级、题型、字形结构、内容状态、账号角色、学习事件、SRS 状态等 |

> 内容域字段与 `content/` 目录下的内容包 JSON **一一对应**，可原样导入导出；集合与索引由后端按数据字典幂等创建，避免两处定义漂移。

## 继续阅读

- 接口怎么下发数据 → [API 接口](/docs/api)
- 内容怎么生产 → [内容体系与创作](/docs/content)
- 数据存在哪、后端做什么 → [存储与后端策略](/docs/storage)
