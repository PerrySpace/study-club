/**
 * 接口客户端 —— 业务代码唯一的 HTTP 入口。
 *
 * 职责（见 06-1 §2.5）：
 *   1. 统一 baseURL 与超时
 *   2. 请求拦截：注入客户端标识头与 Authorization
 *   3. 响应拦截：统一解包 { code, message, data }，非 0 抛业务异常
 *   4. 后端不可达 → 抛 NetworkError，调用方静默降级（本地功能继续可用）
 *   5. 掩藏能力：开关关闭时**不发起请求**，直接抛 FeatureDisabledError
 */

import {
  AUTH_REFRESH_PATH,
  BizError,
  ERROR_CODE,
  NetworkError,
  TOKEN_DEAD_CODES,
} from '../constants';
import type { FeatureFlags } from '../flags';
import type { HttpAdapter, LoggerAdapter } from '../platform/types';
import type { ApiEnvelope, ApiSuccess, ClientCapabilities, SitePublicConfig } from '../types/api';
import type { Account, Child } from '../types/identity';
import type {
  AnswerRecord,
  AnswerResult,
  AnswerSubmission,
  ChildBadge,
  DailyTask,
  LearningRecord,
  LearningState,
  LessonCompletion,
  ReviewState,
  WrongQuestion,
} from '../types/learning';

/**
 * 信封判定：`code === 0` 即成功。
 *
 * 为什么需要显式守卫：`ApiFailure.code` 是 `number`（含 0），TS 无法仅凭
 * `envelope.code !== 0` 把联合类型收窄到成功分支，因此用类型谓词一次收窄。
 */
function isSuccess<T>(envelope: ApiEnvelope<T>): envelope is ApiSuccess<T> {
  return envelope.code === 0;
}

export interface ApiClientOptions {
  baseUrl: string;
  http: HttpAdapter;
  flags: FeatureFlags;
  client: {
    client: string;
    platform: string;
    deviceForm: string;
    version: string;
    /** 本机设备标识（随机 id，非用户信息）；缺省时服务端会退化成按客户端形态认设备。 */
    clientId?: string;
  };
  capabilities: ClientCapabilities;
  logger?: LoggerAdapter;
  timeoutMs?: number;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export class ApiClient {
  private accessToken: string | null = null;
  /**
   * 静默刷新钩子：由 auth store 注入（见 `setTokenRefresher`）。
   *
   * 为什么是回调而不是直接依赖 store：core 里 api 层与 store 层不能互相 import
   * （会成环，且 store 需要 pinia 实例才能构造）。反转依赖后，api 只认「给一个函数」。
   */
  private tokenRefresher: (() => Promise<string | null>) | null = null;
  /** 单飞：并发的多个 401 共用同一次刷新，避免 N 个请求各自轮换 Refresh Token。 */
  private refreshInFlight: Promise<string | null> | null = null;

  constructor(private readonly opts: ApiClientOptions) {}

  setAccessToken(token: string | null): void {
    this.accessToken = token;
  }

  /**
   * 注册「Access Token 失效时怎么静默换新」。
   *
   * 传 `null` 可注销。约定：返回新的 access token 表示换成功（本类会自己挂上），
   * 返回 `null` 表示换不到（会话已经不可救，调用方会收到原始的业务错误）。
   */
  setTokenRefresher(fn: (() => Promise<string | null>) | null): void {
    this.tokenRefresher = fn;
  }

  /**
   * 登录 / 注册请求体里的 `client` 段。
   *
   * ⚠️ 只有这两类请求需要它 —— 服务端**仅**在这里读取 `client_id` 来建会话记录
   * （其余请求靠请求头与 Authorization 定位）。把设备 id 放进 body 而不是请求头，
   * 是因为 `ClientInfo` 这个契约字段早就存在（04-1 §二），复用它可以不新增协议面。
   */
  private clientInfo(): { client_id?: string; platform: string; app_version: string } {
    const { client } = this.opts;
    return { client_id: client.clientId, platform: client.platform, app_version: client.version };
  }

  private headers(extra?: Record<string, string>): Record<string, string> {
    const { client, capabilities, flags } = this.opts;
    const caps: string[] = [];
    for (const [k, v] of Object.entries(capabilities)) if (v) caps.push(k);

    return {
      'Content-Type': 'application/json',
      'X-Client-Client': client.client,
      'X-Client-Platform': client.platform,
      'X-Client-Form': client.deviceForm,
      'X-Client-Version': client.version,
      ...(flags.enableStats || caps.length > 0 ? { 'X-Client-Capabilities': caps.join(',') } : {}),
      ...(this.accessToken ? { Authorization: `Bearer ${this.accessToken}` } : {}),
      ...(extra ?? {}),
    };
  }

  /** 统一请求 + 信封解包。 */
  async request<T>(
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
    path: string,
    payload?: { params?: Record<string, unknown>; data?: unknown },
  ): Promise<T> {
    return this.send<T>(method, path, payload, true);
  }

  /**
   * 真正发一次请求。
   *
   * `allowRefresh` 控制这一次还允不允许「401 静默刷新后重试」——
   * **只允许一次**，否则服务端一直返 40101 时会变成死循环。
   */
  private async send<T>(
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
    path: string,
    payload: { params?: Record<string, unknown>; data?: unknown } | undefined,
    allowRefresh: boolean,
  ): Promise<T> {
    let envelope: ApiEnvelope<T>;
    try {
      envelope = await this.opts.http.request<ApiEnvelope<T>>({
        method,
        url: this.opts.baseUrl + path,
        params: payload?.params,
        data: payload?.data,
        headers: this.headers(),
        timeoutMs: this.opts.timeoutMs ?? 8000,
      });
    } catch (err) {
      this.opts.logger?.warn('接口请求失败（将降级到本地功能）', { path, err });
      throw new NetworkError();
    }

    if (isSuccess(envelope)) return envelope.data;

    if (allowRefresh && this.canRefreshOn(envelope.code, path)) {
      const fresh = await this.refreshOnce();
      if (fresh) return this.send<T>(method, path, payload, false);
    }

    throw new BizError(envelope.code, envelope.message, envelope.errors);
  }

  /** 哪些失败值得先刷新再重试：只有「Token 过期 / 失效」，且不能是刷新接口自身。 */
  private canRefreshOn(code: number, path: string): boolean {
    return (
      this.tokenRefresher !== null &&
      path !== AUTH_REFRESH_PATH &&
      TOKEN_DEAD_CODES.includes(code)
    );
  }

  /** 单飞刷新：并发 401 只会真的调一次 `tokenRefresher`。 */
  private refreshOnce(): Promise<string | null> {
    if (this.refreshInFlight) return this.refreshInFlight;
    const pending = Promise.resolve()
      .then(() => this.tokenRefresher?.() ?? null)
      .catch(() => null)
      .then((token) => {
        this.refreshInFlight = null;
        if (token) this.accessToken = token;
        return token;
      });
    this.refreshInFlight = pending;
    return pending;
  }

  // ---------------- 健康检查 ----------------
  health(): Promise<{ status: string; content_version?: string }> {
    return this.request('GET', '/health');
  }

  // ---------------- 站点公开配置（无需登录） ----------------
  /**
   * 启动时读取运营配置（邀请码是否必填 / 是否开放注册 / 公告 / 默认学习目标 / 玩法配置）。
   *
   * 返回类型直接引用 `SitePublicConfig`，不再就地写一份字面量类型 ——
   * 就地写的那份会随字段增加而漂移，而漂移的表现是「后端加了字段，前端类型说没有」。
   */
  publicConfig(): Promise<SitePublicConfig> {
    return this.request('GET', '/config');
  }

  // ---------------- 账号身份（用户名 / 手机号） ----------------
  /** 注册：用户名与手机号**至少填一个**；邀请码按开关可选。 */
  register(input: {
    username?: string | null;
    phone?: string | null;
    invite_code: string | null;
    passcode: string;
    display_name: string;
    avatar_key: string;
  }): Promise<{ account: Account; tokens: AuthTokens; recovery_code: string | null }> {
    return this.request('POST', '/auth/register', {
      data: { ...input, client: this.clientInfo() },
    });
  }

  /** 登录：`identifier` 可填用户名或手机号。 */
  login(input: {
    identifier: string;
    passcode: string;
  }): Promise<{ account: Account; tokens: AuthTokens }> {
    return this.request('POST', '/auth/login', {
      data: { ...input, client: this.clientInfo() },
    });
  }

  // ---------------- 邀请码身份（兼容旧通道） ----------------
  inviteVerify(code: string): Promise<{ valid: boolean; access_tier: string }> {
    return this.request('POST', '/auth/invite/verify', { data: { invite_code: code } });
  }

  inviteRegister(input: {
    invite_code: string | null;
    passcode: string;
    display_name: string;
    avatar_key: string;
  }): Promise<{ account: Account; tokens: AuthTokens; recovery_code: string | null }> {
    return this.request('POST', '/auth/register', {
      data: { ...input, client: this.clientInfo() },
    });
  }

  inviteLogin(input: {
    identifier: string;
    passcode: string;
  }): Promise<{ account: Account; tokens: AuthTokens }> {
    return this.request('POST', '/auth/login', {
      data: { ...input, client: this.clientInfo() },
    });
  }

  refresh(refreshToken: string): Promise<AuthTokens> {
    return this.request('POST', '/auth/refresh', { data: { refresh_token: refreshToken } });
  }

  me(): Promise<Account> {
    return this.request('GET', '/auth/me');
  }

  /** 登出：吊销该设备的 Refresh Token（服务端按 refresh_token 定位设备）。 */
  logout(refreshToken?: string | null): Promise<{ revoked: boolean }> {
    return this.request('POST', '/auth/logout', {
      data: { refresh_token: refreshToken ?? null },
    });
  }

  /** 注销并删除云端数据（合规必需，见 R-06）。 */
  deleteAccount(): Promise<{ ok: boolean }> {
    return this.request('DELETE', '/auth/account');
  }

  // ---------------- 儿童档案 ----------------
  listChildren(): Promise<{ items: Child[] }> {
    return this.request('GET', '/children');
  }

  getChild(id: string): Promise<Child> {
    return this.request('GET', `/children/${encodeURIComponent(id)}`);
  }

  createChild(input: Partial<Child> & { nickname: string }): Promise<Child> {
    return this.request('POST', '/children', { data: input });
  }

  updateChild(id: string, patch: Partial<Child>): Promise<Child> {
    return this.request('PATCH', `/children/${encodeURIComponent(id)}`, { data: patch });
  }

  deleteChild(id: string): Promise<{ deleted: boolean; child_id: string }> {
    return this.request('DELETE', `/children/${encodeURIComponent(id)}`);
  }

  // ---------------- 内容（登录后可见） ----------------
  /** 一次性引导：清单 + 字库 + 古诗 + 单元 + 关卡 + 故事 + 徽章。 */
  contentBootstrap(grade: number, includeFullChars = true): Promise<Record<string, unknown>> {
    return this.request('GET', '/content/bootstrap', {
      params: { grade, include_full_chars: includeFullChars },
    });
  }

  contentManifest(): Promise<Record<string, unknown>> {
    return this.request('GET', '/content/manifest');
  }

  lessonQuestions(lessonId: string): Promise<{ lesson_id: string; title: string; questions: unknown[] }> {
    return this.request('GET', `/content/lessons/${encodeURIComponent(lessonId)}/questions`);
  }

  // ---------------- 学习 ----------------
  /** 服务端学习状态总览：进度 + 今日任务 + 到期复习 + 徽章。 */
  learningState(childId: string, includeDaily = true): Promise<LearningState> {
    return this.request('GET', '/learning/state', {
      params: { child_id: childId, include_daily: includeDaily },
    });
  }

  dailyTask(childId: string, date?: string): Promise<DailyTask> {
    return this.request('GET', '/learning/daily-task', {
      params: { child_id: childId, ...(date ? { date } : {}) },
    });
  }

  submitAnswer(input: AnswerSubmission): Promise<AnswerResult> {
    return this.request('POST', '/learning/answer', { data: input });
  }

  submitAnswersBatch(
    childId: string,
    records: AnswerSubmission[],
  ): Promise<{ accepted: number; skipped_duplicate: number }> {
    return this.request('POST', '/learning/answer/batch', {
      data: { child_id: childId, records },
    });
  }

  completeLesson(input: LessonCompletion): Promise<{ record_id: string; newly_earned_badges: [] }> {
    return this.request('POST', '/learning/lesson/complete', { data: input });
  }

  reviewStates(childId: string, characterId?: string): Promise<{ items: ReviewState[]; total: number }> {
    return this.request('GET', '/learning/review-states', {
      params: { child_id: childId, ...(characterId ? { character_id: characterId } : {}) },
    });
  }

  wrongQuestions(childId: string): Promise<{ items: WrongQuestion[] }> {
    return this.request('GET', '/learning/wrong-questions', { params: { child_id: childId } });
  }

  resolveWrongQuestion(childId: string, wrongId: string): Promise<{ resolved: boolean; id: string }> {
    return this.request('POST', `/learning/wrong-questions/${encodeURIComponent(wrongId)}/resolve`, {
      params: { child_id: childId },
    });
  }

  childBadges(childId: string): Promise<{ items: ChildBadge[]; total: number }> {
    return this.request('GET', '/learning/badges', { params: { child_id: childId } });
  }

  learningRecords(childId: string, limit = 200): Promise<{ items: LearningRecord[]; total: number }> {
    return this.request('GET', '/learning/records', { params: { child_id: childId, limit } });
  }

  answerRecords(childId: string, limit = 2000): Promise<{ items: AnswerRecord[]; total: number }> {
    return this.request('GET', '/learning/answers', { params: { child_id: childId, limit } });
  }

  /** 导出该孩子的完整学习数据包（P0 数据可迁移性）。 */
  exportChildData(childId: string): Promise<Record<string, unknown>> {
    return this.request('GET', '/learning/export', { params: { child_id: childId } });
  }

  // ---------------- 报告 ----------------
  reportOverview(childId: string): Promise<Record<string, unknown>> {
    return this.request('GET', `/reports/child/${encodeURIComponent(childId)}/overview`);
  }

  reportTrend(childId: string, days = 7): Promise<{ items: Array<{ date: string; learned: number; correct: number; total: number }> }> {
    return this.request('GET', `/reports/child/${encodeURIComponent(childId)}/trend`, { params: { days } });
  }

  reportWeakChars(childId: string, limit = 50): Promise<Record<string, unknown>> {
    return this.request('GET', `/reports/child/${encodeURIComponent(childId)}/weak-chars`, {
      params: { limit },
    });
  }

  // ---------------- 匿名统计（只上报聚合行为计数） ----------------
  reportStats(events: Array<Record<string, unknown>>): Promise<{ accepted: number }> {
    return this.request('POST', '/stats/events', { data: { events } });
  }

  // ---------------- 反馈 ----------------
  submitFeedback(input: {
    category: string;
    message: string;
    content_ref?: string | null;
    contact?: string | null;
  }): Promise<{ ok: boolean }> {
    return this.request('POST', '/feedbacks', { data: input });
  }
}

/** 掩藏能力存在时的一律拒绝（四道防线之③：调用即抛错）。 */
export function assertFeatureEnabled(flags: FeatureFlags, key: keyof FeatureFlags): void {
  if (!flags[key]) {
    throw new BizError(ERROR_CODE.FEATURE_DISABLED, '该能力当前未开启');
  }
}
