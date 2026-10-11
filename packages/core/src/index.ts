/**
 * @study-club/core —— 跨端业务内核
 *
 * 两条红线（见 06-1 §2.9.1）：
 *   ① 零平台依赖：不出现 window / document / localStorage / indexedDB / axios / uni.*
 *   ② 学科无关：判据「这段逻辑换成英语单词还成立吗？」成立 → 本包；不成立 → 学科包
 *
 * 本包只提供：类型、常量、能力开关、纯算法、仓储接口与实现、内容源、Pinia 领域 store。
 * 平台实现由各外壳在 apps/&lt;shell&gt;/src/platform/ 注入。
 *
 * ⚠️ 数据口径：**服务端是唯一真源**，本包不提供任何本地存储实现 ——
 * `repositories/remote.ts` 的 `ApiRepository` 是 `ProgressRepository` 的唯一实现。
 */

export * from './constants';
export * from './flags';
export * from './types';
export * from './algorithms';
export * from './repositories';
export * from './platform/types';
export * from './api/client';
export * from './stores';
