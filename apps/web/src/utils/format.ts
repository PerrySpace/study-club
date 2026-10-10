/**
 * 展示用格式化工具（纯函数，无平台依赖）。
 */

import { useSiteConfigStore } from '@study-club/core';

/**
 * 年级文案。
 *
 * ⛔ 年级不再写死 1–6（后台可任意增删，如「幼小衔接」「七年级」），
 * 因此**不能**再从常量表查 —— 查不到会退化成「7 年级」，
 * 对自定义档位就错了。现在从 siteConfig store 取服务端下发的年级表；
 * 配置未加载时用年级号兜底，保证任何时候都有文案
 * （宁可显示「7 年级」，也不要让界面上出现空格子）。
 *
 * ⚠️ 本函数在 Pinia 初始化**之后**才可调用（它依赖 store）。
 * 本项目里它都在视图/组合式函数内使用，满足这个前提。
 */
export function gradeLabel(grade: number): string {
  const siteConfig = useSiteConfigStore();
  return siteConfig.gradeLabels[grade] ?? `${grade} 年级`;
}

/**
 * 建档 / 设置页的年级下拉选项（启用项，按 id 升序）。
 *
 * 排序理由：运营在后台增删年级时的排列顺序可能与「年级大小」无关，
 * 直接沿用配置顺序会出现「七年级排在一年级前面」这种明显错乱的下拉。
 */
export function gradeOptions(): Array<{ value: number; label: string }> {
  const siteConfig = useSiteConfigStore();
  return siteConfig.grades.map((g) => ({ value: g.id, label: g.label }));
}

export function percent(value: number): string {
  if (!Number.isFinite(value)) return '0%';
  return `${Math.round(value * 100)}%`;
}

/** ISO → `M月D日`（本地时区展示，存储仍为 UTC ISO）。 */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

/** ISO → `YYYY-MM-DD` */
export function isoDay(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toISOString().slice(0, 10);
}

export function todayKey(): string {
  return new Date().toISOString().slice(0, 10);
}
