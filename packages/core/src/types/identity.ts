/**
 * 身份域类型 —— 与 03-2 §三 对应。
 * 身份方式：邀请码 + 自设口令（Ed25519 离线签名 / 服务端校验），无手机号、无微信、无实名。
 */

import type { AccessTier, AccountStatus, LevelType } from '../constants';

export interface Account {
  _id: string;
  /** 用户名（注册时可选填，唯一） */
  username: string | null;
  /** 手机号（注册时可选填，唯一）；用于登录，不作为身份实名 */
  phone: string | null;
  display_name: string;
  avatar_key: string;
  e2e_enabled: boolean;
  role: 'learner' | 'admin';
  status: AccountStatus;
  access_tier: AccessTier;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * 本地会话（Token 只存 localStorage 的 `preference`，不落业务库）。
 *
 * ⚠️ 这是**唯一**仍留在浏览器端的持久化数据，属刻意例外而非疏漏：
 * 路由守卫必须在同步阶段就知道「有没有登录」，异步存储会让每次刷新闪一下登录页。
 * 除 Token 外的所有业务数据（档案、进度、错题、答题明细）一律只存服务端。
 *
 * 已移除 `LocalIdentity`：存储口径改为「彻底服务端、必须先登录」后，
 * 「本机身份」这个概念不再存在，登录态的唯一真源就是本 `Session`。
 */
export interface Session {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  account_id: string;
}

export interface ChildStats {
  total_learned: number;
  mastered: number;
  streak_days: number;
  last_study_at: string | null;
}

export interface Child {
  _id: string;
  nickname: string;
  avatar_key: string;
  grade: number;
  birth_year: number | null;
  unit_preference: 'self' | 'custom';
  daily_new_char_target: number;
  daily_review_target: number;
  daily_time_limit_min: number;
  status: 'active' | 'archived';
  stats: ChildStats;
  created_at: string;
}

export const DEFAULT_CHILD_SETTINGS = {
  unit_preference: 'self' as const,
  daily_new_char_target: 8,
  daily_review_target: 20,
  daily_time_limit_min: 20,
  status: 'active' as const,
};

/**
 * ⛔ 【已退役】年级文案表。
 *
 * 年级现在是**后台可配置的**（任意年级，如「幼小衔接」「七年级」），
 * 所以查这张写死的表必然查不到自定义档位 —— 会退化成「7 年级」这种
 * 对运营毫无意义的文案。
 *
 * 改用：`gradeLabel()` / `gradeOptions()`（`apps/web/src/utils/format.ts`），
 * 它们从 siteConfig store 取服务端下发的年级表。
 * 本常量保留仅为让「年级不再硬编码」这件事在代码里留痕，请勿再引用。
 */
export const GRADE_LABELS: Record<number, string> = {
  0: '学龄前',
  1: '一年级',
  2: '二年级',
  3: '三年级',
  4: '四年级',
  5: '五年级',
  6: '六年级',
};

/**
 * ⛔ 【已退役】按年级取难度档位。
 *
 * 写死 1–6 的直接后果：7 年级及以上会**静默落到 `bridge`（幼小衔接）** ——
 * 一个七年级孩子的内容难度被当成学龄前，界面完全看不出异常。
 * 年级已改为后台可配置，这类「越界即降级」的映射不该再存在。
 *
 * 保留仅为留痕，请勿再引用。
 */
export function levelForGrade(grade: number): LevelType {
  if (grade <= 0) return 'sprout';
  const map: Record<number, LevelType> = {
    1: 'grade1',
    2: 'grade2',
    3: 'grade3',
    4: 'grade4',
    5: 'grade5',
    6: 'grade6',
  };
  return map[grade] ?? 'bridge';
}
