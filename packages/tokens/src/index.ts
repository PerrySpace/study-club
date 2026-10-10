/**
 * @study-club/tokens —— 设计变量与断点的唯一定义处
 *
 * 纪律（见 docs/06-工程规范/01-开发规范与前端架构.md §2.9.3）：
 *   - 组件里禁止写魔法数字断点（`window.innerWidth > 900`），一律引用本包常量。
 *   - 颜色/尺寸禁止散落硬编码，统一走 CSS 变量。
 */

/** 三档断点（按可用宽度判定，不按设备型号）。 */
export const BREAKPOINTS = {
  /** 手机：< 768 */
  phone: 0,
  /** iPad / 平板：768–1279 */
  tablet: 768,
  /** 桌面：>= 1280 */
  desktop: 1280,
} as const;

export type DeviceForm = 'phone' | 'tablet' | 'desktop';

/** 按可用宽度解析设备形态。 */
export function resolveDeviceForm(width: number): DeviceForm {
  if (width >= BREAKPOINTS.desktop) return 'desktop';
  if (width >= BREAKPOINTS.tablet) return 'tablet';
  return 'phone';
}

/** 内容区最大宽度（大屏增加栏数，不放大单个元素）。 */
export const CONTENT_MAX = 880;

/** 触控热区（见 06-1 §2.9.3）。 */
export const TAP = {
  min: 56,
  primary: 64,
  gap: 12,
} as const;

/** 儿童端正文字号绝对下限。 */
export const FONT_MIN = 16;
export const FONT_BODY_MIN = 18;

/** 三档布局的栏数（手机 1 / iPad 2 / 桌面 3）。 */
export const LAYOUT_COLUMNS: Record<DeviceForm, number> = {
  phone: 1,
  tablet: 2,
  desktop: 3,
};
