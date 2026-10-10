/// <reference types="vite/client" />

/** 由 vite.config.ts 的 define 注入的构建期常量。 */
declare const __APP_VERSION__: string;

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_CDN_BASE?: string;
  readonly VITE_ENABLE_INVITE_AUTH?: string;
  readonly VITE_ENABLE_CONTENT_API?: string;
  readonly VITE_ENABLE_REMOTE_CONTENT?: string;
  readonly VITE_ENABLE_STATS?: string;
  readonly VITE_ENABLE_ACCOUNT_AUTH?: string;
  readonly VITE_ENABLE_PAYMENT?: string;
  readonly VITE_ENABLE_MINIPROGRAM?: string;
  readonly VITE_ENABLE_NATIVE_APP?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>;
  export default component;
}
