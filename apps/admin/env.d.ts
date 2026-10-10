/// <reference types="vite/client" />

/** 由 vite.config.ts 的 define 注入的构建期常量。 */
declare const __APP_VERSION__: string;

interface ImportMetaEnv {
  /** 后端 API 基址（含 /api/v1 前缀）。构建期经 Docker build-arg 注入。 */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>;
  export default component;
}
