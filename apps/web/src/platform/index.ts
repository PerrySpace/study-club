/**
 * 平台组装 —— apps/web 的启动入口（见 06-1 §2.1 / §2.9.2）。
 *
 * 组装全部适配器 → 仓储（**服务端实现**）+ ApiClient + 内容源 → setCoreContext()。
 * 业务代码此后只通过 `usePlatform()` / `useCore()` 访问平台能力，
 * **不再出现任何浏览器 API**。
 *
 * 平台上下文只暴露 `preference`（会话 Token / 设备标识 / UI 偏好），不暴露业务数据存储。
 *   - 仓储由 `ApiRepository` 提供 —— 服务端是唯一真源
 *   - 内容源为 `HttpSource`
 *   - 因此 **ApiClient 成为必需**：没有后端地址就没有可用产品，
 *     启动时直接给出可诊断的错误，而不是让用户面对一个空壳页面。
 */

import {
  ApiClient,
  ApiRepository,
  CLIENT,
  HttpSource,
  PLATFORM,
  resolveFlags,
  setCoreContext,
} from '@study-club/core';
import type {
  ClockAdapter,
  ContentSource,
  FeatureFlags,
  LoggerAdapter,
  PlatformContext,
} from '@study-club/core';
import type { DeviceForm } from '@study-club/tokens';

import { detectDeviceForm } from './breakpoint';
import { detectCapabilities } from './capabilities';
import { createHttpAdapter } from './http';
import { createSpeechAdapter } from './speech';
import { createPreferenceAdapter, ensureDeviceId } from './storage';

// 登录记忆的读写出口（视图层只从 `@/platform` 拿，不直接碰 localStorage）。
export { readLoginMemory, writeLoginMemory } from './storage';
export type { RememberedLogin } from './storage';

/**
 * 接口基址。已不再是「可选增强」：内容与学习数据都在服务端，
 * 缺失即无法工作，因此构建期没配就立刻报警（构建/启动阶段发现，别拖到用户点开才发现）。
 */
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

function createClock(): ClockAdapter {
  return { now: () => new Date() };
}

/** 本地日志：**不接任何云监控**（见 06-1 §2.7），设置页可导出。 */
function createLogger(): LoggerAdapter {
  const enabled = import.meta.env.DEV;
  const emit =
    (level: 'debug' | 'info' | 'warn' | 'error') =>
    (msg: string, meta?: unknown): void => {
      if (!enabled && level === 'debug') return;
      const line = `[study-club] ${msg}`;
      if (meta === undefined) console[level](line);
      else console[level](line, meta);
    };
  return { debug: emit('debug'), info: emit('info'), warn: emit('warn'), error: emit('error') };
}

/** 构建期环境变量 → 能力开关（只读一次，纪律 ①）。 */
function resolveWebFlags(): FeatureFlags {
  return resolveFlags(import.meta.env as unknown as Record<string, string | undefined>, {});
}

let platformContext: PlatformContext | null = null;

export function createPlatform(): PlatformContext {
  if (!API_BASE_URL) {
    // 早失败 + 明确指引：这比「页面能打开但什么都拉不到」好排查得多。
    throw new Error(
        'VITE_API_BASE_URL 未配置。内容与学习数据均已改为服务端存储，缺少接口地址无法运行；' +
        '请在 apps/web/.env.local 中配置，例如 ' +
        'VITE_API_BASE_URL=http://localhost:8000/api/v1（生产环境走同源反代，写相对路径 /api/v1）',
    );
  }

  const flags = resolveWebFlags();
  const logger = createLogger();
  const http = createHttpAdapter();
  const preference = createPreferenceAdapter();
  const capabilities = detectCapabilities();

  const platform: PlatformContext = {
    preference,
    http,
    clock: createClock(),
    logger,
    // 语音：浏览器原生免费能力（TTS + ASR）。不支持的内核会拿到空实现，
    // 由业务组件按 `canSpeak/canListen` 走降级，而不是渲染一个点了没反应的按钮。
    speech: createSpeechAdapter(),
    capabilities,
    client: {
      client: CLIENT.web,
      platform: PLATFORM.web,
      deviceForm: detectDeviceForm(),
      version: __APP_VERSION__,
      // 本机设备标识：登录时随 body.client 上报，服务端据此给每台设备独立的会话记录
      // （多地同时登入的前提，详见 storage.ts 的 ensureDeviceId 注释）。
      clientId: ensureDeviceId(),
    },
  };

  const api = new ApiClient({
    baseUrl: API_BASE_URL,
    http,
    flags,
    client: platform.client,
    capabilities,
    logger,
  });

  // 仓储层：服务端唯一真源（浏览器不再持有任何业务数据）。
  const repositories = { progress: new ApiRepository(api) };

  const contentSource: ContentSource = new HttpSource(api, logger);

  setCoreContext({ flags, platform, repositories, api, contentSource });

  platformContext = platform;
  return platform;
}

/** 当前平台上下文（含可变的 client.deviceForm）。 */
export function getPlatform(): PlatformContext {
  if (!platformContext) throw new Error('createPlatform() 尚未调用');
  return platformContext;
}

/** 断点变化时同步 client.deviceForm（供请求头使用）。 */
export function syncDeviceForm(form: DeviceForm): void {
  if (platformContext) platformContext.client.deviceForm = form;
}

// ---------------------------------------------------------------------------
// 少量 DOM 能力（下载 / 剪贴板 / 选文件）—— 同样收敛在本目录，
// 避免在视图层散落 `document` / `navigator`（06-1 §2.9.2）。
// ---------------------------------------------------------------------------

/** 复制文本到剪贴板。 */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // 剪贴板在非安全上下文/无权限时不可用，交给调用方提示手动抄写。
  }
  return false;
}

/** 触发浏览器下载一个 JSON 文件（数据导出，见 01-3 I-04）。 */
export function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

// 说明：原先这里还有一个 `pickJsonFile()`（选本地 JSON 文件用于「导入进度」）。
// 数据真源搬到服务端后导入功能已移除（换设备登录即可），该函数随之删除 ——
// 留着一个「能把外部文件读进来」的入口，很容易被误用成一条绕过服务端的写路径。
