# 06-2 React 原型迁移方案

> 本文档定义现有 React 原型如何处置：哪些资产值得保留、哪些必须重写、按什么顺序迁移。

---

## 一、总体策略

### 1.1 核心决策

> **不做 React / Vue 双框架共存，而是"新建 + 平移归档"。**

理由：原型规模不大（约 3600 行 TS/TSX），双框架共存或渐进式替换都会带来构建复杂度与状态耦合的额外成本；**新建 Vue3 工程 + 原型平移归档**更干净、可逐页对照验证。

**操作方式**：把根目录现有文件整体移入 `legacy/` 目录，保留可运行状态（可通过独立命令启动），作为功能参照与视觉对照。新工程在 `apps/` 下从零建设。

### 1.2 迁移的额外约束：按多端标准一次建成

迁移**不是**"把 React 换成 Vue3"，而是**一次性把架构建成能支撑多端的形态**。因为多端的复用成本在 Phase 0 就被决定了 —— 如果 `packages/core` 的边界没守住，Phase 2 做小程序时等于重做整个前端。

因此迁移阶段必须额外完成这四件事：

| 必须完成 | 为什么现在做 | 不做会怎样 |
| --- | --- | --- |
| 建立 `packages/core`，把算法、store、类型、接口契约放进去 | Phase 2 要平移给 uni-app | 逻辑锁死在 `apps/web` 里，小程序端要重写全部业务逻辑 |
| 建立平台能力抽象层（`PlatformCapabilities` + 适配器） | 隔离浏览器 API | `stores` 里散落 `localStorage`/`fetch`，uni-app 无法复用 |
| Web 端从第一天就写响应式三档（手机 / iPad / 桌面） | 事后补响应式 = 重写布局 | iPad 与桌面端体验崩坏，或返工重排 |
| 设计变量提炼到 `packages/tokens`（而非 `apps/web` 内部） | Web 与 uni-app 共用同一套色板/断点 | 两端视觉分叉，改一处颜色要改两遍 |

> ⚠️ 这四件事**只在迁移期做成本最低**。等 `apps/web` 写完 20 个页面再回头拆 `core`，代价是数倍。详见 [06-1 2.9 跨端与多端约定](./01-开发规范与前端架构.md#29-跨端与多端约定红线)。

### 1.3 迁移的四条原则

1. **视觉照搬，逻辑重写**：配色、间距、动效尽量 1:1 保留（用户已经认可这套视觉）；但数据流、状态管理、组件划分全部重做。
2. **数据源切换是迁移的真正分界线**：页面从"读组件内硬编码常量"改为"经仓储层读内容包 / 云端"，才算真正迁移完成。
3. **不做数据迁移**：原型只有单机 IndexedDB 数据，且没有真实用户，**不需要迁移历史进度**。
4. **来源不明的内容一律重建**：出版社课文映射、自动填充字库、来路不明素材**带着版权风险**，宁可重做也不将就（这是开源项目的底线）。

---

## 二、资产分级

### 2.1 A 级：直接复用（几乎不改）

| 资产 | 位置 | 复用方式 |
| --- | --- | --- |
| **视觉设计体系** | `src/App.css`（2189 行） | **最高价值资产**。提炼为 `styles/tokens.css` + 组件样式，配色/间距/圆角/阴影全部保留 |
| 汉字基础数据 | `src/utils/charData.ts`（519 行） | 提取为字库的初始导入数据（拼音、笔画数），作为内容生产的基础骨架 |
| 训练模式定义 | `src/supportData.ts` 的 `trainingModes` | 作为关卡设计的参考，转为数据配置 |
| 学习计划模板 | `src/supportData.ts` 的 `studyPlanTemplates` | 作为计划模块的初始设计输入 |
| 拼音处理逻辑 | `src/utils/speech.ts` 中的拼音拼接思路 | 逻辑简单，参考后重写 |
| PWA 配置 | `vite.config.ts` | manifest、图标、workbox 配置沿用 |

### 2.2 B 级：改造复用（保留思路，重新实现）

| 资产 | 位置 | 处理方式 |
| --- | --- | --- |
| 学习地图 | `MapScreen.tsx`（72 行） | 视觉与解锁逻辑保留，数据改为接口拉取 |
| 字卡组件 | `CharacterCard.tsx`（95 行） | 视觉保留，素材字段从 `imageGlyph`（Emoji）改为 `image_url` |
| 笔顺动画 | `LessonScreen.tsx` + `hanzi-writer` | **保留 hanzi-writer 方案**，改为从接口读笔顺数据 |
| 答题面板 | `QuizPanel.tsx`（100 行） | 视觉保留，题目生成从组件内散落逻辑改为 `packages/core/algorithms` 纯函数 |
| 题型生成逻辑 | `utils/quiz.ts`（40 行） | **逻辑迁移到 `packages/core/algorithms`**（纯函数，多端复用、可单测），前端只做渲染 |
| 成就系统 | `BadgeScreen.tsx` + `useProgressStore.deriveBadges` | 规则从硬编码改为数据驱动（`badges.condition`） |
| 学情报告 | `ReportScreen.tsx`（106 行） | 视觉保留，数据改为接口，增加趋势维度 |
| 故事找字 | `StoryScreen.tsx`（67 行） | 视觉保留，内容从接口拉取 |
| 分级字库 | `LibraryScreen.tsx`（159 行） | 增加筛选排序，数据接口化 |
| 顶部导航 | `Header.tsx`（18 行） | 直接改造 |

### 2.3 C 级：重写

| 资产 | 位置 | 原因 |
| --- | --- | --- |
| **应用外壳与路由** | `App.tsx`（233 行） | `useState` 切页面 + 集中式状态管理，**必须换成 Vue Router + 拆分 Store** |
| **状态管理** | `useProgressStore.ts`（85 行） | 单一 store 承担全部状态，按 [06-1 文档](./01-开发规范与前端架构.md#22-状态管理划分) 拆为 6 个 store |
| **本地存储层** | `storage.ts`（35 行） | 单 key IndexedDB → **多档案 + 仓储层**（`LocalRepository` 为默认主存储，可选 `SyncRepository`） |
| 类型定义 | `types.ts`（84 行） | 与 `content/` schema 对齐后重写，禁止两套类型并存 |
| 专项训练 | `TrainingScreen.tsx`（727 行） | **单个文件 727 行**，混合了 9 个板块，必须按板块拆分重组 |
| 创意工坊 | `StudioScreen.tsx`（74 行） | 玩法单薄，且依赖的 `createdSentences` 需重新设计 |
| 语音反馈 | `VoiceFeedback.tsx`（21 行） | 演示性质，重写为真实声调检测 |

> ⚠️ **存储层为本地优先**：IndexedDB 为多档案**主存储**，仓储层统一出入口，服务端仅作可选同步镜像。

### 2.4 D 级：废弃

| 资产 | 原因 |
| --- | --- |
| `src/data.ts` 中 52 个精编汉字 | 数据本身可复用（作为种子），但**文件形态废弃** —— 内容必须进 `content/` 目录 |
| `curriculum.ts` 的 3500 条自动填充字库 | ⚠️ **必须废弃**。含大量生僻字（丂、丄、丅），是"看似很全"的假数据，不可面向用户 |
| `supportData.ts` 的 58 个出版社课文单元 | ⛔ **必须废弃**。单元顺序与课文标题涉**出版社汇编权**，开源即侵权风险（见 [01-4 三](../01-产品规划/04-免费开放与开源策略.md)） |
| 来源不明的素材（Emoji 配图、来路不明音频） | ⛔ **必须废弃**。开源项目不得包含无法溯源授权的资产；重建时改用白名单数据源（见 [01-4 5.2](../01-产品规划/04-免费开放与开源策略.md#52-可用数据源白名单)） |
| `src/index.css`（42 行） | 合并进新的基础样式 |
| `src/lib-modal.css`（174 行） | 重构为组件样式 |
| `hanzi-writer.d.ts`（24 行） | 新版有官方类型，视情况保留 |

### 2.5 根目录遗留脚本（需清理）

根目录存在若干开发期一次性脚本，迁移时应归档或删除：

| 文件 | 判断 |
| --- | --- |
| `expand_lib.py` ~ `expand_lib5.py` | 字库扩展脚本（5 个版本迭代），**产物即那批占位数据，一并废弃** |
| `fix_ts.py` / `fix_ts.js` / `fix2.py` / `fix3.py` | 类型修复一次性脚本，删除 |
| `check_brackets.py` / `test.js` | 临时校验脚本，删除 |
| `update_data.py` | 视内容而定，大概率一次性，删除 |

> 这些脚本的存在本身说明原型阶段的内容生产是**靠脚本批量生成**的，而非人工精编 —— 这也印证了 [01-1 现状评估](../01-产品规划/01-原型资产与重构范围.md) 中的判断。

---

## 三、逐文件映射表

| 原文件 | 行数 | 新位置 | 处理 |
| --- | --- | --- | --- |
| `src/App.css` | 2189 | `apps/web/src/styles/` | ✅ 提炼为 tokens + 组件样式 |
| `src/App.tsx` | 233 | `App.vue` + `router/` | 🔄 重写 |
| `src/main.tsx` | 10 | `main.ts` | 🔄 重写 |
| `src/index.css` | 42 | `styles/base.css` | ♻️ 合并 |
| `src/lib-modal.css` | 174 | 组件样式 | ♻️ 重构 |
| `src/types.ts` | 84 | `packages/core/types` | 🔄 重写 |
| `src/storage.ts` | 35 | `packages/core/repositories/LocalRepository.ts` + `apps/web/src/platform/storage.ts` | 🔄 重写为仓储层 |
| `src/useProgressStore.ts` | 85 | `stores/*.ts`（6 个） | 🔄 重写 |
| `src/data.ts` | 688 | `content/characters/*.json` | 📦 精编数据作种子导入后废弃 |
| `src/curriculum.ts` | 174 | — | ⛔ 废弃（占位数据） |
| `src/supportData.ts` | 168 | `content/lessons/*.json`（训练模式、计划模板）+ ⛔ 出版社课文单元废弃 | 📦 部分导入 / ⛔ 出版社课文单元废弃 |
| `src/utils/charData.ts` | 519 | `content/characters/*.json` 初始种子 | 📦 数据导入（须核对来源许可） |
| `src/utils/quiz.ts` | 40 | `packages/core/algorithms` | ➡️ 迁到内核（纯函数，多端复用） |
| `src/utils/speech.ts` | 50 | `composables/useAudio.ts` + 保留 TTS 兜底 | 🔄 重写 |
| `src/components/Header.tsx` | 18 | `components/biz/AppHeader.vue` | ♻️ 改造 |
| `src/components/MapScreen.tsx` | 72 | `views/MapView.vue` | ♻️ 改造 |
| `src/components/CharacterCard.tsx` | 95 | `components/biz/CharacterCard.vue` | ♻️ 改造 |
| `src/components/LessonScreen.tsx` | 68 | `views/LessonView.vue` | ♻️ 改造 |
| `src/components/QuizPanel.tsx` | 100 | `components/biz/QuizPanel.vue` | ♻️ 改造 |
| `src/components/StoryScreen.tsx` | 67 | `views/StoryView.vue` | ♻️ 改造 |
| `src/components/LibraryScreen.tsx` | 159 | `views/LibraryView.vue` | ♻️ 改造 |
| `src/components/ReportScreen.tsx` | 106 | `views/ReportView.vue` | ♻️ 改造 |
| `src/components/BadgeScreen.tsx` | 48 | `views/BadgeView.vue` | ♻️ 改造 |
| `src/components/StudioScreen.tsx` | 74 | `views/StudioView.vue` | 🔄 重写 |
| `src/components/TrainingScreen.tsx` | 727 | 拆为多个 `views/training/*` | 🔄 重写并拆分 |
| `src/components/VoiceFeedback.tsx` | 21 | `components/biz/ToneFeedback.vue` | 🔄 重写 |
| `src/hanzi-writer.d.ts` | 24 | — | ❓ 视新版类型情况 |

**统计**（共 27 个文件）：直接复用 / 数据导入 4 项，改造复用 11 项，重写 9 项，废弃 1 项，部分导入部分废弃 1 项（`supportData.ts`），待定 1 项。

---

## 四、CSS 资产复用方案（最高价值）

`App.css` 的 2189 行是本项目**最值得保留的资产** —— 儿童产品的视觉打磨成本很高，而用户已经认可当前效果。

### 4.1 提炼步骤

```
1. 提取设计变量 → packages/tokens（CSS 变量 + TS 常量）⭐ 跨端共用
   颜色、间距、字号、圆角、阴影、动画时长
   + 断点常量、触控热区尺寸、安全区、内容最大宽度

2. 提取基础样式 → apps/web/src/styles/base.css
   reset、全局字体、滚动条、通用工具类

3. 按组件拆分剩余样式
   各 .vue 文件的 <style scoped> 中

4. 补齐响应式三档（手机 / iPad / 桌面）
   原型只有 768 / 1024 两个断点，统一为三档：`<768` 手机 / `768–1279` iPad / `≥1280` 桌面（见 06-1 2.9.3）

5. 删除未使用的样式（2189 行中必有冗余）
   用 PurgeCSS 或人工核对
```

### 4.2 保留要点

| 类别 | 说明 |
| --- | --- |
| 配色 | `#ffd166`（主色）、`#f5fff8`（背景）、`#32b67a`（成功）等全部保留 |
| 圆角与阴影 | 儿童产品偏柔和，风格保留 |
| 动效 | 星级动画、徽章弹出等保留 |
| 字体 | 中文适合用系统字体栈，避免引入过重字体文件 |
| 响应式断点 | 原型只有 `768px` / `1024px`，统一为**三档**（`<768` / `768–1279` / `≥1280`）并补 iPad 双栏、桌面三栏布局；触控热区统一放大到 ≥ 56px |

### 4.3 改进点

| 问题 | 改进 |
| --- | --- |
| 2189 行集中在单文件 | 按组件拆分，便于维护 |
| 可能含未使用样式 | 迁移时清理 |
| 硬编码颜色值 | 改为 CSS 变量 |
| 布局按手机写死 | 补齐三档响应式（iPad 双栏、桌面三栏） |
| 触控热区偏小 | 统一 ≥ 56px，主操作 ≥ 64px（儿童手指定位精度低） |
| 底部固定元素未处理安全区 | 补 `env(safe-area-inset-bottom)` |
| `hover` 样式未隔离 | 包进 `@media (hover: hover)`，防触屏"粘住" |
| 使用深层后代选择器 | 收敛为 class 选择器（为 Phase 2 uni-app 迁移降本） |
| 缺少深色模式 | 本期不做，但变量化后预留 |

---

## 五、迁移执行顺序

### 阶段 1：环境准备

- [ ] 现有文件移入 `legacy/`，记录启动方式
- [ ] 建立 Monorepo 结构与 `apps/web` 骨架
- [ ] **建立 `packages/core` 与 `packages/tokens`**（多端复用的地基，必须在写第一个页面之前）
- [ ] **建立仓储层抽象**（`LocalRepository` 默认 + `SyncRepository` 可选）与平台能力抽象层
- [ ] **建立能力开关体系**（`packages/core/flags`，默认全关）
- [ ] **建立开源工程文件**：`LICENSE` / `LICENSE-CONTENT` / `CONTRIBUTING.md` / `THIRD_PARTY_NOTICES.md` / `.env.example`
- [ ] **配置 CI**：类型检查 + lint + 内容 Schema 校验 + **密钥扫描（gitleaks）** + `core` 平台 API 阻断
- [ ] 从 `App.css` 提炼 `packages/tokens`（含断点、触控热区、安全区常量）
- [ ] 搭建路由、Store、API 层的基础封装
- [ ] **搭建三档响应式外壳**（`AppShell` + 断点工具），后续页面统一挂载
- [ ] 清理根目录遗留脚本（**不得进入公开仓库**）

### 阶段 2：页面迁移（按价值排序）

| 顺序 | 页面 | 理由 |
| --- | --- | --- |
| 1 | **注册登入（邀请码）** / 儿童档案选择 | 原型无此页，是身份与准入的前置（见 [02-5](../02-系统架构/05-邀请码身份与准入体系.md)） |
| 2 | 学习地图 | 入口页，验证内容经仓储层加载跑通 |
| 3 | 字卡学习 | 核心页，验证笔顺与音频 |
| 4 | 答题 | 核心页，验证题目生成（内核纯函数） |
| 5 | 每日任务 | 验证 SRS 与本地调度 |
| 6 | 学情报告 | 家长价值呈现 |
| 7 | 古诗模块 | 全新模块 |
| 8 | 分级字库 | 数据量最大 |
| 9 | 故事、成就 | 相对独立 |
| 10 | 专项训练、创意工坊 | 最后处理，需重新设计 |

### 阶段 3：能力增强

- [ ] 声调检测（本地 F0，算法放 `packages/core/algorithms`，供后续 uni-app 复用）
- [ ] 离线队列
- [ ] 家长端
- [ ] **iPad 专项**：双栏布局、横竖屏、Apple Pencil 手写（`useHandwriting`）
- [ ] **桌面专项**：三栏布局、快捷键、报告导出
- [ ] **多端验收走查**：按 [02-2 第九章](../02-系统架构/02-多端适配与响应式设计规范.md#九多端测试矩阵与验收)的设备矩阵真机验证

### 阶段 4：下线原型

- [ ] 新版本功能验证通过
- [ ] `legacy/` 移出仓库或归档分支

---

## 六、风险与注意事项

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 视觉还原走样 | 用户已认可现有视觉，改坏损失大 | **逐页截图对照**，建立视觉回归清单（含 iPad 双栏与桌面三栏截图） |
| CSS 拆分遗漏 | 样式丢失、布局错乱 | 迁移后逐页人工走查（非自动化能覆盖） |
| 题型逻辑迁到内核后行为不一致 | 用户感知题目变化 | 用原型 `utils/quiz.ts` 的输出做回归比对 |
| 占位字库被误导入生产 | 用户体验严重受损 | **导入前严格筛选**，只保留人工精编数据 |
| **内容版权风险** | 开源即侵权，法律风险 | **出版社课文映射与来源不明素材一律废弃**；只从白名单数据源重建，逐项登记 `sources.json` |
| 双份代码并存期维护成本 | 修 bug 要改两处 | **冻结原型**，只读不改 |
| **`core` 边界被破坏** | 多端复用失效，等于重做前端 | CI lint 阻断；架构评审把"是否引入平台 API"列为必查项 |
| **仓储层被绕过** | 接云端后台时全量返工 | ESLint 禁止组件直连 `localStorage`/`indexedDB`；review 清单必查 |
| 响应式事后补 | iPad / 桌面布局返工，三档都要重排 | 迁移期就搭好 `AppShell` 三档外壳，页面统一挂载 |
| **密钥/占位数据入公开仓库** | 永久留痕、隐私与法务风险 | 第一次公开推送前跑 gitleaks 全历史扫描；`.env` 从未入库 |

---

## 七、迁移完成判定

满足以下全部条件，方可认为迁移完成：

1. `legacy/` 目录不再被构建引用
2. 新版本所有页面视觉与原型一致（或有明确改进）
3. 内容全部来自 `content/` 内容包（经仓储层），前端无任何硬编码内容
4. 占位字库与出版社课文映射数据未进入仓库
5. 根目录一次性脚本已清理
6. 核心流程有自动化测试覆盖
7. **`packages/core` 通过 CI lint 检查，无任何平台 API 引用**
8. **手机 / iPad / 桌面三档布局均通过真机走查**（含横竖屏与安全区）
9. **新增能力已在[能力矩阵](../02-系统架构/02-多端适配与响应式设计规范.md#71-能力矩阵)登记，并提供降级路径**
10. **开源工程文件齐备**（LICENSE / CONTRIBUTING / THIRD_PARTY_NOTICES / .env.example）
11. **CI 密钥扫描通过**，全历史无密钥、无本机绝对路径
12. **能力开关默认全关**，构建产物中不含认证 / 企业能力相关代码（`enablePayment` / `enableAccountAuth` 关闭时）
