/**
 * Toast —— 走 ui store（纯内存），组件侧只关心调用。
 */

import { storeToRefs } from 'pinia';

import { useUiStore } from '@/stores/ui';
import type { ToastLevel } from '@/types';

export function useToast() {
  const ui = useUiStore();
  const { toasts } = storeToRefs(ui);

  return {
    toasts,
    show: (message: string, level: ToastLevel = 'info', duration = 2400): number =>
      ui.pushToast(message, level, duration),
    success: (message: string): number => ui.pushToast(message, 'success'),
    warn: (message: string): number => ui.pushToast(message, 'warn', 3200),
    error: (message: string): number => ui.pushToast(message, 'error', 3600),
    dismiss: (id: number): void => ui.dismissToast(id),
  };
}
