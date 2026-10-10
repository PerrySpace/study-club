/**
 * 断点与设备形态（phone / tablet / desktop）。
 *
 * 纪律：断点数值只能来自 packages/tokens（06-1 §2.9.3），本文件不写魔法数字。
 * 形态按**容器可用宽度**判定 —— 观察外壳根节点而非仅 window，
 * 这样 iPad 分屏后宽度 < 768 会自动降级为手机布局（见 02-2 §4.5）。
 */

import { onMounted, onUnmounted } from 'vue';
import { storeToRefs } from 'pinia';
import type { Ref } from 'vue';

import { observeDeviceForm } from '@/platform/breakpoint';
import { useUiStore } from '@/stores/ui';

export interface UseBreakpointOptions {
  /** 观察的容器；缺省观察 documentElement */
  target?: Ref<HTMLElement | null>;
}

export function useBreakpoint(options: UseBreakpointOptions = {}) {
  const ui = useUiStore();
  const { deviceForm, isPhone, isTablet, isDesktop, useBottomNav, denseLayout } =
    storeToRefs(ui);

  let stop: (() => void) | null = null;

  onMounted(() => {
    const el = options.target?.value ?? document.documentElement;
    stop = observeDeviceForm(el, (form) => ui.setDeviceForm(form));
  });

  onUnmounted(() => {
    stop?.();
    stop = null;
  });

  return { deviceForm, isPhone, isTablet, isDesktop, useBottomNav, denseLayout };
}
