/**
 * ui store —— **仅外壳特有状态**（弹窗、Toast、断点、外壳形态）。
 *
 * 领域状态（auth / child / content / learning）一律在 packages/core/stores，
 * 本 store 不得出现任何学习数据（见 06-1 §2.2）。
 */

import { defineStore } from 'pinia';
import { computed, ref } from 'vue';

import { BREAKPOINTS, CONTENT_MAX } from '@study-club/tokens';
import type { DeviceForm } from '@study-club/tokens';

import type { ShellForm, ToastItem, ToastLevel } from '@/types';
import { detectDeviceForm } from '@/platform/breakpoint';
import { syncDeviceForm } from '@/platform';

export const useUiStore = defineStore('ui', () => {
  // ---- 断点 / 形态（初始值经 platform/breakpoint 探测，store 内不出现浏览器 API） ----
  const deviceForm = ref<DeviceForm>(detectDeviceForm());
  const shellForm = ref<ShellForm>('default');

  const isPhone = computed(() => deviceForm.value === 'phone');
  const isTablet = computed(() => deviceForm.value === 'tablet');
  const isDesktop = computed(() => deviceForm.value === 'desktop');
  /** 手机底部 TabBar / iPad+ 侧栏 */
  const useBottomNav = computed(() => deviceForm.value === 'phone');
  /** 大屏信息密度增量（双栏/三栏） */
  const denseLayout = computed(() => deviceForm.value !== 'phone');

  function setDeviceForm(next: DeviceForm): void {
    if (deviceForm.value === next) return;
    deviceForm.value = next;
    // 同步到 client 标识，用于本地流水与请求头（形态按可用宽度，非设备型号）。
    syncDeviceForm(next);
  }

  function setShellForm(form: ShellForm): void {
    shellForm.value = form;
  }

  // ---- Toast ----
  const toasts = ref<ToastItem[]>([]);
  let toastSeq = 0;

  function pushToast(message: string, level: ToastLevel = 'info', duration = 2400): number {
    const id = ++toastSeq;
    toasts.value = [...toasts.value, { id, level, message, duration }];
    if (duration > 0) setTimeout(() => dismissToast(id), duration);
    return id;
  }

  function dismissToast(id: number): void {
    toasts.value = toasts.value.filter((t) => t.id !== id);
  }

  // ---- 模态 ----
  const modal = ref<{ open: boolean; title: string; message: string }>({
    open: false,
    title: '',
    message: '',
  });

  function openModal(title: string, message: string): void {
    modal.value = { open: true, title, message };
  }

  function closeModal(): void {
    modal.value = { ...modal.value, open: false };
  }

  // ---- 布局常量（供视图读取，避免在组件里写魔法数字） ----
  const layout = {
    breakpoints: BREAKPOINTS,
    contentMax: CONTENT_MAX,
  };

  return {
    deviceForm,
    shellForm,
    isPhone,
    isTablet,
    isDesktop,
    useBottomNav,
    denseLayout,
    layout,
    setDeviceForm,
    setShellForm,
    toasts,
    pushToast,
    dismissToast,
    modal,
    openModal,
    closeModal,
  };
});
