/**
 * vite-plugin-pwa 的虚拟模块类型声明。
 *
 * 这里手写一份最小声明，而不是引用 `vite-plugin-pwa/client`：
 * 前者让 `vue-tsc --noEmit` 不依赖插件是否已安装，降低「clone 即跑」的门槛。
 */
declare module 'virtual:pwa-register' {
  export interface RegisterSWOptions {
    immediate?: boolean;
    onNeedRefresh?: () => void;
    onOfflineReady?: () => void;
    /** @deprecated 插件会在提供 onRegisteredSW 时不调用它 */
    onRegistered?: (swUrl?: string) => void;
    /** 拿到 registration 才能主动 `registration.update()`，用于推动版本更新 */
    onRegisteredSW?: (
      swScriptUrl: string,
      registration?: ServiceWorkerRegistration,
    ) => void;
    onRegisterError?: (error: unknown) => void;
  }
  export function registerSW(
    options?: RegisterSWOptions,
  ): (reloadPage?: boolean) => Promise<void>;
}
