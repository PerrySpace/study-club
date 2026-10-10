/**
 * 平台实现：HTTP 适配器（fetch）。
 *
 * 职责：统一超时（AbortController）、查询串拼装、JSON 解包。
 *
 * ⚠️ 与 packages/core `ApiClient` 的约定（重要，见交付说明「发现的 core 问题」）：
 *   ApiClient 会捕获 HttpAdapter 抛出的**任何**异常并统一转成 `NetworkError`。
 *   若这里对「非 2xx」一律抛错，则后端返回的业务信封（如口令错误 401 + code=40104）
 *   会被吞掉，用户只能看到「网络异常」。
 *   因此本适配器采用：**非 2xx 但响应体仍是合法业务信封（含数字 code）时，原样返回**，
 *   交由 ApiClient 解包并抛 `BizError`；其余非 2xx（网关 502、404 HTML 等）一律抛错，
 *   由 ApiClient 转 `NetworkError` 走静默降级。
 */

import type { HttpAdapter } from '@study-club/core';

const DEFAULT_TIMEOUT_MS = 8000;

export class HttpError extends Error {
  readonly status: number;
  readonly url: string;

  constructor(status: number, url: string, message: string) {
    super(message);
    this.name = 'HttpError';
    this.status = status;
    this.url = url;
  }
}

function buildUrl(url: string, params?: Record<string, unknown>): string {
  if (!params) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    search.append(key, String(value));
  }
  const qs = search.toString();
  if (!qs) return url;
  return url.includes('?') ? `${url}&${qs}` : `${url}?${qs}`;
}

/** 判断响应体是否为本项目的业务信封（{ code: number, ... }）。 */
function isApiEnvelope(body: unknown): boolean {
  return (
    typeof body === 'object' &&
    body !== null &&
    'code' in body &&
    typeof (body as { code: unknown }).code === 'number'
  );
}

async function parseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function createHttpAdapter(): HttpAdapter {
  return {
    async request<T>(config: {
      method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
      url: string;
      params?: Record<string, unknown>;
      data?: unknown;
      headers?: Record<string, string>;
      timeoutMs?: number;
    }): Promise<T> {
      const url = buildUrl(config.url, config.params);
      const controller = new AbortController();
      const timeout = window.setTimeout(
        () => controller.abort(),
        config.timeoutMs ?? DEFAULT_TIMEOUT_MS,
      );

      const hasBody = config.data !== undefined && config.method !== 'GET';
      const headers: Record<string, string> = { ...(config.headers ?? {}) };
      if (hasBody && !headers['Content-Type']) headers['Content-Type'] = 'application/json';

      try {
        const response = await fetch(url, {
          method: config.method,
          headers,
          body: hasBody ? JSON.stringify(config.data) : undefined,
          signal: controller.signal,
          // 离线优先：不使用浏览器 HTTP 缓存，内容缓存由 Service Worker 负责。
          cache: 'no-store',
          credentials: 'omit',
        });

        if (response.status === 204) return undefined as T;

        const body = await parseBody(response);

        if (!response.ok) {
          // 业务信封（如 401 + code）原样返回给 ApiClient 解包。
          if (isApiEnvelope(body)) return body as T;
          throw new HttpError(response.status, url, `请求失败（HTTP ${response.status}）`);
        }

        return body as T;
      } catch (err) {
        if (err instanceof HttpError) throw err;
        if (err instanceof DOMException && err.name === 'AbortError') {
          throw new HttpError(0, url, '请求超时');
        }
        throw new HttpError(0, url, err instanceof Error ? err.message : '网络异常');
      } finally {
        window.clearTimeout(timeout);
      }
    },
  };
}
