/**
 * 间隔重复复习调度 —— 阈值与**只读**判断。
 *
 * ⚠️ 调度的「写」路径（`applyReview` / `createReviewState`）已整体移除：
 * 复习参数由服务端计算并拥有（`apps/api/app/controllers/srs.py`），
 * 客户端只把服务端返回的 `ReviewState` 翻译成界面要的判断。
 *
 * 为什么不能在客户端留一份写路径：两边各算一份，早晚会漂移；
 * 更麻烦的是服务端一旦调整参数（例如把第二次间隔从 6 天改成 4 天），
 * 客户端的旧算法会在用户设备上长期残留（PWA 缓存），
 * 造成「同一个班的孩子，一个显示 6 天、一个显示 4 天」这类无法解释的现象。
 *
 * 本文件是纯函数、**学科无关**（换成英语单词同样成立），因此属 packages/core。
 * `SRS` 中的阈值必须与后端 `srs.py` 保持一致。
 */

import type { ReviewState } from '../types/learning';

export const SRS = {
  /** 初始难度系数（展示用；计算在服务端） */
  initialEase: 2.5,
  /** 难度系数下限 */
  minEase: 1.3,
  /** 难度系数上限 */
  maxEase: 2.8,
  /** 答对时难度系数增量 */
  easeUp: 0.1,
  /** 答错时难度系数减量 */
  easeDown: 0.2,
  /** 掌握阈值（天）：interval_days 超过即视为已掌握 */
  masteredIntervalDays: 60,
} as const;

export function addDays(base: Date, days: number): Date {
  const d = new Date(base.getTime());
  d.setUTCDate(d.getUTCDate() + days);
  return d;
}

/**
 * 是否到期（`next_review_at <= now`）。
 *
 * ⚠️ 判断「今天该复习哪些字」时**优先用服务端的 `state.due_reviews`**：
 * 服务端可能因时区归一化或补算而与本地时钟有毫秒级/边界差异。
 * 本函数适用于单个状态的即时展示（例如刷完一题后本地立刻改提示）。
 */
export function isDue(state: ReviewState, now: Date = new Date()): boolean {
  return new Date(state.next_review_at).getTime() <= now.getTime();
}

/** 已掌握（间隔超过阈值）。 */
export function isMastered(state: ReviewState): boolean {
  return state.interval_days > SRS.masteredIntervalDays;
}
