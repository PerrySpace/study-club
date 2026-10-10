/**
 * 平台实现：Service Worker 注册与**版本更新推动**。
 *
 * 为什么不能只依赖 `registerType: 'autoUpdate'`：
 *   autoUpdate 只保证「新 SW 就绪后会自行接管并刷新页面」，
 *   **不保证浏览器会主动去问有没有新版本**。浏览器自带的更新检查有 24h 节流，
 *   而 PWA 常驻标签页几乎不会触发导航 —— 结果就是发版后用户长时间看不到新版，
 *   再叠加对外 CDN 对 `/sw.js` 的缓存，旧 SW 能"赖"很久。
 *
 * 这里显式接管更新检查：注册完成立刻查一次 + 定时轮询 + 回到前台时查一次。
 * 一旦发现新版本，autoUpdate 会自动 skipWaiting 并刷新，无需用户操作。
 */

import { registerSW } from 'virtual:pwa-register';

export interface PwaHooks {
  onOfflineReady?: () => void;
  onNeedRefresh?: () => void;
  onError?: (error: unknown) => void;
}

/**
 * 更新检查间隔（20 分钟）。
 * 太密会在长驻页面上白白打请求，太疏则发版后用户要等很久才看到新版。
 */
const UPDATE_INTERVAL_MS = 20 * 60 * 1000;

/**
 * 注册 Service Worker，并推动版本更新。
 *
 * 失败一律静默（PWA 只是增强，不该影响主流程）。
 */
export function registerServiceWorker(hooks: PwaHooks = {}): void {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return;

  try {
    registerSW({
      immediate: true,
      onOfflineReady: () => hooks.onOfflineReady?.(),
      onNeedRefresh: () => hooks.onNeedRefresh?.(),
      onRegisterError: (error) => hooks.onError?.(error),
      onRegisteredSW: (_swUrl, registration) => {
        if (registration) scheduleUpdateChecks(registration);
      },
    });
  } catch (error) {
    hooks.onError?.(error);
  }
}

/**
 * 安排持续的新版本检查。
 *
 * ⚠️ 显式调用 `registration.update()` 而不是等浏览器自己查，是因为：
 *   浏览器对同一 registration 的**自动**更新检查有 24h 节流；
 *   而 `update()` 由脚本主动触发，不受该节流限制。
 *   SW 脚本的更新请求以 `cache: 'no-cache'` 发出（强制回源校验），
 *   因此即便 CDN 给 `/sw.js` 带了 `max-age`，也仍能拿到最新内容。
 */
function scheduleUpdateChecks(registration: ServiceWorkerRegistration): void {
  if (typeof window === 'undefined' || typeof document === 'undefined') return;

  const check = (): void => {
    // 离线时检查必然失败，跳过以免刷屏；恢复联网时会由 online 事件补一次
    if (navigator.onLine === false) return;
    // 失败静默：更新检查是尽力而为，超时/断网都不该冒泡到用户
    void registration.update().catch(() => undefined);
  };

  // 注册完成先查一次：用户刚打开页面，正是最可能赶上新版本的时刻
  check();

  window.setInterval(check, UPDATE_INTERVAL_MS);

  // 从后台切回前台：用户主动回到应用，是最该「顺手看看有没有新版」的时机
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') check();
  });

  window.addEventListener('online', check);
}

/** 供「设置」页手动触发更新（autoUpdate 下通常无需用户操作）。 */
export function reloadForUpdate(): void {
  if (typeof window === 'undefined') return;
  window.location.reload();
}
