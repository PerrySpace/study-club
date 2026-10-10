/**
 * 视口高度（响应式，px）。
 *
 * 用途：学习页里那些**尺寸写死在 JS 里**的元素（典型是手写板的米字格边长），
 * 需要一个「跟屏幕高度一起变」的输入源。能用 CSS 表达的自适应一律用 CSS
 * （见 styles/learn-screen.css 的 `.learn-page`），这里只解决 CSS 够不着的那部分。
 *
 * 纪律：浏览器 API 不写在本文件，走 platform/viewport（06-1 §2.9）。
 */

import { onMounted, onUnmounted, ref } from 'vue';
import type { Ref } from 'vue';

import { observeViewportHeight, readViewportHeight } from '@/platform/viewport';

export function useViewportHeight(): Ref<number> {
  // 初值立刻取，保证首帧就用得上（不必等 onMounted 再补一次）
  const height = ref(readViewportHeight());
  let stop: (() => void) | null = null;

  onMounted(() => {
    stop = observeViewportHeight((value) => {
      height.value = value;
    });
  });

  onUnmounted(() => {
    stop?.();
    stop = null;
  });

  return height;
}
