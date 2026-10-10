# 02-3 uni-app 跨端方案与微信小程序适配

> **本文档只约束 Web 阶段的跨端纪律**（`packages/core` 边界、视图层选择器、大资源策略、平台能力抽象、条件编译）；**微信小程序与 iOS / Android App 属预留能力，当前不写、不构建、不注册、不备案**，其工程细节收敛为文末「预留清单」，不进入当前排期。终端形态与响应式规范见 [02-2 多端适配与响应式设计规范](./02-多端适配与响应式设计规范.md)。

---

## 一、Web 阶段必须遵守的跨端纪律

这些纪律**现在就要执行**：多端的复用成本在第一天就被决定，Web 端写的时候不遵守，将来做小程序就是重做前端。

### 1.1 `packages/core` 的边界（红线）

| 允许 | 禁止 |
| --- | --- |
| 纯 TS 函数、类型、常量 | 任何 `window` / `document` / `navigator` |
| Pinia store（业务状态） | `localStorage` / `indexedDB` / `uni.getStorage` |
| 通过接口调用平台能力 | `axios` / `uni.request` 直接调用 |
| 依赖注入 / 工厂函数 | `import ... from '@dcloudio/uni-app'` |
| 纯算法与数据转换 | 任何 UI 组件、样式、模板 |

**第二条边界：学科无关。** 判据：**这段逻辑换成英语单词还成立吗？** 成立 → 放 `packages/core`；不成立（拼音比对、汉字笔顺、古诗文结构等语文专属逻辑）→ 放学科包 `packages/subject-hanzi`。学科走 **URL 路径** `/hanzi` `/english` `/math`，`packages/core` 中不得出现任何学科名。

**CI 强制检查**：用 ESLint 的 `no-restricted-globals` / `no-restricted-imports` 阻断 `core` 中的平台 API 引用，违反即构建失败。

### 1.2 `packages/core` 子目录约定

| 目录 | 放什么 |
| --- | --- |
| `api/contracts/` | 接口契约（TS 类型） |
| `api/adapters/` | HTTP 适配器接口与实现注入点 |
| `repositories/` | `LocalRepository` / `SyncRepository` / `HttpRepository` |
| `stores/` | Pinia store（领域状态） |
| `algorithms/` | 学科无关算法：SRS 调度、题型框架、F0 提取 |
| `platform/` | 平台能力接口定义（只定义，不实现） |
| `flags/` | 能力开关定义与默认值 |
| `types/` | TS 类型与接口契约 |
| `constants/` | 枚举、断点、错误码 |

### 1.3 平台能力抽象层（关键设计）

`core` 只认接口，各外壳提供实现（依赖倒置）：

```ts
// packages/core/platform/types.ts —— 接口定义（core 内）
export interface HttpAdapter {
  request<T>(config: HttpRequestConfig): Promise<T>;
}
export interface StorageAdapter {
  get<T>(key: string): Promise<T | null>;
  set<T>(key: string, value: T): Promise<void>;
  remove(key: string): Promise<void>;
}
export interface RecorderAdapter {
  /** 录制一段音频，返回 16kHz 单声道 PCM（Float32Array，归一化到 [-1,1]） */
  recordOnce(options: { durationMs: number }): Promise<{ pcm: Float32Array; sampleRate: number }>;
  /** 是否支持录制过程中拿到实时帧（用于实时音高曲线） */
  readonly supportsRealtimeFrames: boolean;
}
export interface PushAdapter { subscribe(topic: string): Promise<void>; }
export interface ShareAdapter { share(payload: SharePayload): Promise<void>; }
```

```ts
// apps/web/src/platform/index.ts    —— Web 实现
// apps/mobile/src/platform/index.ts —— uni 实现（预留）
export function createPlatform(): PlatformBundle {
  return { http: createWebHttpAdapter(), storage: createWebStorageAdapter(), /* ... */ };
}
```

**唯一的分支判断出现在这里。** 业务代码永远通过 `usePlatform()` 拿能力，不写 `if (isMiniProgram)`。若没有这层抽象，`stores` 里会出现大量 `uni.request` 调用，Web 端复用率从 95% 掉到 0。

**运行时能力探测**（启动时探测一次，产出能力对象注入 core）：

```ts
// packages/core/platform/types.ts
export interface PlatformCapabilities {
  runtime: 'web' | 'miniprogram' | 'app';
  form: 'phone' | 'tablet' | 'desktop';   // 形态按可用宽度判定，不按设备
  canRecord: boolean;
  canLocalAsr: boolean;
  canRealtimeAudioAnalysis: boolean;
  canHandwritingPressure: boolean;
  canPush: boolean;
  canInstallPwa: boolean;
  storageQuotaMB: number;
}
```

### 1.4 视图层与选择器约束

小程序 CSS **只支持 class/id 选择器**（不支持 `*` 通配与部分伪类），且存在样式隔离。因此 **Web 端从第一天就只用 class 选择器**，`:deep()` 谨慎使用，不依赖标签选择器与全局样式穿透。

> 这条约束现在执行，将来视图层重写时才不需要返工。

### 1.5 大资源不进首包

| 资源 | 体积 | 策略 |
| --- | --- | --- |
| F0 提取算法（纯 JS/WASM） | 几十 KB | **内联进主包**（核心能力，不能延后） |
| 声调模板数据 | < 50KB | 随主包或首次进入评测时拉取 |
| 本地 ASR 模型 | 20–60MB | **首屏绝不加载**；用户首次进入跟读功能时后台下载，写 Cache Storage |
| 音频素材 | 单条 20–60KB | 进入单元时预取，LRU 淘汰 |
| 笔顺数据 | 单字 2–5KB | 进入字卡时拉取 |

> 小程序不存在「后台下载大模型」这条路（无长时任务 + 包体积硬限），这是小程序只能做 Lite 版的根本原因。相关性能预算见 [02-2 第八章](./02-多端适配与响应式设计规范.md#八分端性能预算)。

### 1.6 条件编译约定

uni-app 通过**条件编译**在同一份代码里写平台差异。原则：**能用运行时能力探测（`PlatformCapabilities`）解决的就不要用条件编译**；条件编译只用于「编译期必须不同」的地方。

```ts
// #ifdef MP-WEIXIN
// 小程序专属：一次性订阅消息引导（预留）
// #endif
// #ifdef APP-PLUS
// App 专属：原生推送注册（预留）
// #endif
// #ifdef H5
// H5 专属
// #endif
```

| 用途 | 是否用条件编译 |
| --- | --- |
| 平台能力实现（录音/存储/网络） | ✅ 编译期分离，减小包体 |
| 订阅消息 / 推送注册（预留） | ✅ 平台 API 不同 |
| 分享参数（小程序卡片 vs App） | ✅ 载体不同 |
| 功能开关（如「本地 ASR 是否可用」） | ❌ 用运行时能力探测，避免同一端不同版本行为分叉 |
| 样式微调（安全区、导航栏高度） | ✅ `#ifdef` + 平台常量 |

### 1.7 端覆盖边界

**iPad 走 Web / PWA，不做 iPad 版 App。**

| 端 | 载体 | 理由 |
| --- | --- | --- |
| iPhone / Android 手机 | （预留）App | 推送、录音质量 |
| iPad | **Web + PWA 添加到主屏** | PWA 在 iPadOS 上体验接近原生；省掉一整套平板 App 适配与审核成本 |
| 微信小程序 | （预留）小程序 | 获客渠道 |
| 鸿蒙 | 暂不覆盖 | 预留，见第二章 |

---

## 二、预留清单（当前不写、不构建）

> 判定标准：以下能力**均需要企业主体或额外审核流程**，因此当前只保留契约与开关，**不打包、不部署**。掩藏机制见 [02-4 第四章](./04-本地优先与后端策略.md#四能力开关体系前端掩藏的实现机制)；能力开关的唯一定义处见 [02-4 §4.2](./04-本地优先与后端策略.md#42-能力开关清单)。

| 能力 | 开关名 | 契约位置 | 状态 |
| --- | --- | --- | --- |
| 微信小程序（含分包方案、包体积治理、录音兼容） | `enableMiniprogram` | `apps/mobile` 骨架 | ⛔ 需企业主体，不启用 |
| iOS / Android App（含打包、原生能力、上架材料） | `enableNativeApp` | `apps/mobile` 骨架 | ⛔ 需企业主体，不启用 |
| 账号打通（`code` → `openid` / `unionid`） | `enableAccountAuth` | [04-1 §10 预留接口](../04-接口设计/01-API接口定义.md) | ⛔ 需企业主体，不启用 |
| 小程序订阅消息（推送） | `enableMiniprogram` | 随小程序预留 | ⛔ 随小程序预留 |
| ICP 备案（域名） | — | [02-4 §7.1](./04-本地优先与后端策略.md#71-部署位置与备案决策) | ⏸️ 境内服务器部署时按需（个人主体可做非经营性备案） |
| 小程序备案 / 类目资质 / 软件著作权 | — | — | ⛔ 随小程序 / App 预留 |
| 发布、灰度与崩溃监控 | — | — | ⛔ 随小程序 / App 预留；错误上报统一**自托管或本地日志** |
| 鸿蒙（鸿蒙 NEXT） | `enableNativeApp` | — | ⏸️ 远期；触发条件：鸿蒙设备占比 > 5% 时再评估 |

> **技术路线**：预留阶段锁定 **uni-app（JS / TS 版）**，不使用 uni-app x（UTS 版）——后者语言非标准 TS、小程序支持范围有限，与「Web 优先 + 内核复用」路线冲突。若未来必须覆盖鸿蒙，优先评估 uni-app 工程上鸿蒙的实际可用度，而非切换到 uni-app x。
>
> **本项目不采用支付宝 / 抖音小程序**：uni-app 虽可编译它们，但本项目的外壳范围仅限 Web（当前）、微信小程序与 App（预留）。

---

## 三、下一步

- 终端形态、断点与降级规则 → [02-2 多端适配与响应式设计规范](./02-多端适配与响应式设计规范.md)
- 总体架构与后端 → [02-1 系统总体架构与技术选型](./01-系统总体架构与技术选型.md)
- 能力开关与仓储层机制 → [02-4 本地优先与后端策略](./04-本地优先与后端策略.md)
- 前端目录与平台抽象层编码约定 → [06-1 开发规范与前端架构](../06-工程规范/01-开发规范与前端架构.md)
- 端类型与设备数据字段 → [03-2 数据字典](../03-数据设计/02-数据字典.md)
- 客户端平台标识与接口约定 → [04-1 API 接口定义](../04-接口设计/01-API接口定义.md)
