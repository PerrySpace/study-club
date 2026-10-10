/**
 * 外壳本地类型（仅 Web 端使用，不进 packages/core）。
 */

import type { DeviceForm } from '@study-club/tokens';

/** 应用外壳形态：默认外壳（带导航）或沉浸外壳（关卡/引导页）。 */
export type ShellForm = 'default' | 'immersive';

/** 导航项定义（TabBar 与 SideNav 共用同一份数据）。 */
export interface NavItem {
  name: string;
  path: string;
  label: string;
  icon: string;
  /** 仅这些形态显示（默认三档全显示） */
  forms?: DeviceForm[];
  /** 是否进手机底部 TabBar（手机 4–5 项，见 02-2 §3.2） */
  inTabBar?: boolean;
}

/** 全局 Toast 级别。 */
export type ToastLevel = 'info' | 'success' | 'warn' | 'error';

export interface ToastItem {
  id: number;
  level: ToastLevel;
  message: string;
  /** 毫秒；0 表示手动关闭 */
  duration: number;
}
