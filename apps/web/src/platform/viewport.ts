/**
 * 平台实现：视口高度观察（浏览器 API 只在本层出现，见 06-1 §2.9）。
 *
 * ## 为什么这件事不能只靠 CSS
 * 手写板（WritingPad）的米字格边长是**内联像素值** —— canvas 的绘制分辨率、
 * 显示尺寸、描红字号都由它换算（`pointFrom` 用 `getBoundingClientRect()` 反推坐标，
 * 内联样式优先级又高于任何 CSS 规则），所以媒体查询改不动它。
 * 矮屏上沿用固定 268px，会把「重写 / 看笔顺」连同底部的「下一步」一起顶出屏幕。
 * 于是由 JS 量出视口高度，换算成合适的边长传进去。
 *
 * ## 为什么优先 `visualViewport`
 * iOS Safari 上键盘弹出、地址栏收放时 `innerHeight` **不变**，只有
 * `visualViewport.height` 会跟着变；用后者才能避免「一输入，布局就崩」。
 * 老内核没有 `visualViewport`，退回 `innerHeight`（此时高度变化主要由旋转触发，
 * 而我们同时监听了 `orientationchange`，够用）。
 */

/** 当前视口高度（px）。无 window（SSR / 测试环境）时返回 0。 */
export function readViewportHeight(): number {
  if (typeof window === 'undefined') return 0;
  const height = window.visualViewport?.height ?? window.innerHeight ?? 0;
  return Math.round(height);
}

/**
 * 观察视口高度变化（旋转 / 地址栏收放 / 分屏 / 键盘）。
 * 回调会**立即执行一次**（避免调用方还要自己补一次初值）。返回取消函数。
 */
export function observeViewportHeight(onChange: (height: number) => void): () => void {
  const emit = (): void => onChange(readViewportHeight());
  const vv = typeof window === 'undefined' ? undefined : window.visualViewport;

  emit();
  // 三处都听：resize 覆盖桌面缩放与分屏，orientationchange 覆盖部分
  // 只在旋转时更新、不发 resize 的旧内核，visualViewport 覆盖 iOS 地址栏/键盘。
  window.addEventListener('resize', emit, { passive: true });
  window.addEventListener('orientationchange', emit, { passive: true });
  vv?.addEventListener('resize', emit);

  return () => {
    window.removeEventListener('resize', emit);
    window.removeEventListener('orientationchange', emit);
    vv?.removeEventListener('resize', emit);
  };
}
