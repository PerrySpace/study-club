/**
 * 后端接口客户端（后台专用）。
 *
 * 为什么不在 packages/core 里加 admin 方法：core 的纪律是「零平台依赖 + 学科无关」，
 * 而管理后台是**单机内部工具**、与学科和跨端都无关（05-1 §1.3）。
 * 因此后台自带一个薄封装，只做三件事：拼 baseURL、解信封、带 admin Token。
 *
 * 约定与 apps/web 保持一致：非 2xx 但响应体仍是合法业务信封时**不抛网络错**，
 * 而是解出业务 code 抛 ApiError —— 否则「口令错误」会被显示成「网络异常」。
 */

export interface ApiEnvelope<T> {
  code: number;
  message: string;
  request_id?: string;
  data?: T;
  errors?: Array<{ field: string; reason: string }>;
}

/** 业务错误（信封 code != 0）。 */
export class ApiError extends Error {
  readonly code: number;
  readonly errors?: Array<{ field: string; reason: string }>;

  constructor(code: number, message: string, errors?: Array<{ field: string; reason: string }>) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.errors = errors;
  }
}

/** 网络层失败（后端不可达 / 超时）。 */
export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NetworkError';
  }
}

/** 后端未配置管理员口令时的业务码（镜像 apps/api/app/core/errors.py）。 */
export const FEATURE_DISABLED = 40302;
export const FORBIDDEN = 40301;
export const TOKEN_EXPIRED = 40101;
export const TOKEN_INVALID = 40102;

/** Token 失效类错误：需要清会话并回到登录页。 */
export function isAuthError(err: unknown): boolean {
  return err instanceof ApiError && (err.code === TOKEN_EXPIRED || err.code === TOKEN_INVALID || err.code === FORBIDDEN);
}

const TOKEN_KEY = 'sc.admin.token';
const EXPIRES_KEY = 'sc.admin.expires_at';

let accessToken: string | null = null;

function resolveBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_API_BASE_URL?.trim();
  if (fromEnv) return fromEnv.replace(/\/+$/, '');
  // 未显式配置时按「同主机的 8000 端口」推断，方便用局域网 IP 直接打开后台
  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname || 'localhost'}:8000/api/v1`;
}

export const API_BASE_URL = resolveBaseUrl();

// ---------------------------------------------------------------------------
// Token 持久化（后台是单人工具，放 localStorage 可接受；退出即清除）
// ---------------------------------------------------------------------------
function readStoredToken(): string | null {
  try {
    const expiresAt = Number(localStorage.getItem(EXPIRES_KEY) ?? '0');
    if (expiresAt && Date.now() >= expiresAt) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(EXPIRES_KEY);
      return null;
    }
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getAccessToken(): string | null {
  if (accessToken === null) accessToken = readStoredToken();
  return accessToken;
}

export function setAccessToken(token: string, expiresInSeconds = 0): void {
  accessToken = token;
  try {
    localStorage.setItem(TOKEN_KEY, token);
    if (expiresInSeconds > 0) {
      localStorage.setItem(EXPIRES_KEY, String(Date.now() + expiresInSeconds * 1000));
    } else {
      localStorage.removeItem(EXPIRES_KEY);
    }
  } catch {
    /* 隐私模式下写入失败不影响本次会话 */
  }
}

export function clearAccessToken(): void {
  accessToken = null;
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EXPIRES_KEY);
  } catch {
    /* 同上 */
  }
}

// ---------------------------------------------------------------------------
// 请求
// ---------------------------------------------------------------------------
export type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

interface RequestOptions {
  params?: Record<string, unknown>;
  data?: unknown;
  timeoutMs?: number;
}

function buildUrl(path: string, params?: Record<string, unknown>): string {
  const url = API_BASE_URL + path;
  if (!params) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.append(key, String(value));
  }
  const qs = search.toString();
  return qs ? `${url}?${qs}` : url;
}

function isEnvelope(body: unknown): body is ApiEnvelope<unknown> {
  return (
    typeof body === 'object' &&
    body !== null &&
    'code' in body &&
    typeof (body as { code: unknown }).code === 'number'
  );
}

export async function request<T>(method: Method, path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    // 与 apps/web 同一套客户端标识头（后端解析出 ClientContext，便于排查）
    'X-Client-Client': 'admin',
    'X-Client-Platform': 'web',
    'X-Client-Form': 'desktop',
    'X-Client-Version': __APP_VERSION__,
  };
  const hasBody = options.data !== undefined && method !== 'GET';
  // ⛔ FormData 必须让浏览器自己设 multipart/form-data 的 boundary，
  // 手动设 Content-Type 会把 boundary 抹掉，后端收不到文件（表现为「上传总是失败」）。
  const isFormData = typeof FormData !== 'undefined' && options.data instanceof FormData;
  if (hasBody && !isFormData) headers['Content-Type'] = 'application/json';
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), options.timeoutMs ?? 15000);

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.params), {
      method,
      headers,
      body: hasBody
        ? isFormData
          ? (options.data as FormData)
          : JSON.stringify(options.data)
        : undefined,
      signal: controller.signal,
      cache: 'no-store',
      credentials: 'omit',
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new NetworkError('请求超时，请确认后端服务是否正常');
    }
    throw new NetworkError('无法连接后端服务，请确认 api 容器已启动');
  } finally {
    window.clearTimeout(timer);
  }

  if (response.status === 204) return undefined as T;

  let body: unknown = null;
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    try {
      body = await response.json();
    } catch {
      body = null;
    }
  }

  if (isEnvelope(body)) {
    const envelope = body as ApiEnvelope<T>;
    if (envelope.code !== 0) {
      throw new ApiError(envelope.code, envelope.message || '请求失败', envelope.errors);
    }
    return envelope.data as T;
  }

  if (!response.ok) {
    throw new ApiError(response.status, `请求失败（HTTP ${response.status}）`);
  }
  return body as T;
}
