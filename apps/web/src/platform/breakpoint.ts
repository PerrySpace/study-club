/**
 * 平台实现：断点判定（容器可用宽度 → device_form）。
 *
 * 纪律（06-1 §2.9.3）：**禁止在组件里写魔法数字断点**，一律用 packages/tokens
 * 的 `BREAKPOINTS` / `resolveDeviceForm`。
 *
 * 形态按**可用宽度**判定，不按设备型号：iPad 分屏后宽度 < 768 时降级为手机布局
 * （见 02-2 §4.5）。
 */

import { resolveDeviceForm } from '@study-club/tokens';
import type { DeviceForm } from '@study-club/tokens';

/** 由可用宽度解析形态。 */
export function formFromWidth(width: number): DeviceForm {
  return resolveDeviceForm(width);
}

/**
 * 探测初始形态。
 * 优先用传入容器（外壳根节点）的可用宽度，缺省回退到文档元素宽度。
 */
export function detectDeviceForm(container?: HTMLElement | null): DeviceForm {
  const width =
    container?.clientWidth ??
    (typeof document !== 'undefined' ? document.documentElement.clientWidth : 0);
  return formFromWidth(width);
}

/** 观察容器宽度变化（ResizeObserver），回调形态变化。返回取消函数。 */
export function observeDeviceForm(
  container: HTMLElement,
  onChange: (form: DeviceForm) => void,
): () => void {
  let last = detectDeviceForm(container);
  onChange(last);

  if (typeof ResizeObserver === 'undefined') {
    const onResize = (): void => {
      const next = detectDeviceForm(container);
      if (next !== last) {
        last = next;
        onChange(next);
      }
    };
    window.addEventListener('resize', onResize, { passive: true });
    return () => window.removeEventListener('resize', onResize);
  }

  const observer = new ResizeObserver(() => {
    const next = detectDeviceForm(container);
    if (next !== last) {
      last = next;
      onChange(next);
    }
  });
  observer.observe(container);
  return () => observer.disconnect();
}
