/**
 * auth store —— 账号会话（**服务端唯一身份**）。
 *
 * 身份一律由服务端签发：不存在「先不注册、纯本机」的本地身份模式，
 * 因此没有 `LocalIdentity` / `IDENTITY_MODE` / `chooseMode()`；能用的前提就是有 `Session`。
 *
 * 登录态的判定口径（重要）：
 *   - `isAuthenticated` **只看 `session`**，不看 `account`。
 *     因为 `account` 是 `/auth/me` 的产物，网络抖动时拿不到；
 *     若把它算进判定，一次断网就会把已登录用户踢回登录页。
 *   - 真正判「Token 失效」的只有服务端返回 40101 / 40102，那时才清 session。
 */

import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { BizError, ERROR_CODE, SESSION_STORAGE_KEY } from '../constants';
import type { Account, Session } from '../types/identity';
import { useCore } from './context';

/** Token 失效的两个码：过期与非法。其余错误（含网络异常）不应清会话。 */
const TOKEN_DEAD_CODES: number[] = [ERROR_CODE.TOKEN_EXPIRED, ERROR_CODE.TOKEN_INVALID];

export const useAuthStore = defineStore('auth', () => {
  const account = ref<Account | null>(null);
  const session = ref<Session | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  /** 引导是否跑完：路由守卫据此决定「先等」还是「已可判定」。 */
  const ready = ref(false);

  const isAuthenticated = computed(() => !!session.value);

  function persistSession(s: Session | null): void {
    const { platform, api } = useCore();
    if (s) platform.preference.set(SESSION_STORAGE_KEY, JSON.stringify(s));
    else platform.preference.remove(SESSION_STORAGE_KEY);
    session.value = s;
    api?.setAccessToken(s?.access_token ?? null);
  }

  function readSession(): Session | null {
    const raw = useCore().platform.preference.get(SESSION_STORAGE_KEY);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as Session;
      // 半截数据（缺 token）等同于没有，避免带着坏 Token 去请求
      return parsed?.access_token ? parsed : null;
    } catch {
      return null;
    }
  }

  /** 允许外壳在自行调用 ApiClient 后回填会话（例如注册需自控恢复码全流程时）。 */
  function adoptSession(input: { account: Account; tokens: AuthTokensLike }): void {
    account.value = input.account;
    persistSession(toSession(input.account._id, input.tokens));
  }

  function toSession(accountId: string, tokens: AuthTokensLike): Session {
    return {
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
      // 存绝对时间戳而非 expires_in：这样刷新页面后不用重新计算，也不会因时钟漂移错判
      expires_at: Date.now() + tokens.expires_in * 1000,
      account_id: accountId,
    };
  }

  /**
   * 启动引导：恢复会话 → 校验身份。
   * 幂等，可被路由守卫重复调用（`ready` 后直接返回）。
   */
  async function bootstrap(force = false): Promise<void> {
    if (ready.value && !force) return;
    const { api } = useCore();
    const saved = readSession();

    if (!saved || !api) {
      persistSession(null);
      account.value = null;
      ready.value = true;
      return;
    }

    // 先把 Token 挂上，后续请求才带得上 Authorization
    persistSession(saved);
    loading.value = true;
    try {
      account.value = await api.me();
    } catch (err) {
      if (err instanceof BizError && TOKEN_DEAD_CODES.includes(err.code)) {
        // 确定失效：清干净，交给守卫跳登录
        persistSession(null);
        account.value = null;
      }
      // 其余错误（网络不可达等）**保留会话**，让用户留在页面上看到可重试的错误态，
      // 而不是莫名其妙被登出 —— 登出会让人以为账号出了问题。
    } finally {
      loading.value = false;
      ready.value = true;
    }
  }

  async function register(input: {
    username?: string | null;
    phone?: string | null;
    inviteCode: string | null;
    passcode: string;
    displayName: string;
    avatarKey: string;
  }): Promise<{ recoveryCode: string | null }> {
    const { api, flags } = useCore();
    if (!flags.enableInviteAuth) throw new BizError(ERROR_CODE.FEATURE_DISABLED, '账号注册当前已关闭');
    if (!api) throw new BizError(ERROR_CODE.UPSTREAM_UNAVAILABLE, '服务端不可达，请稍后重试');

    loading.value = true;
    error.value = null;
    try {
      const res = await api.register({
        username: input.username ?? null,
        phone: input.phone ?? null,
        invite_code: input.inviteCode,
        passcode: input.passcode,
        display_name: input.displayName,
        avatar_key: input.avatarKey,
      });
      account.value = res.account;
      persistSession(toSession(res.account._id, res.tokens));
      ready.value = true;
      // ⚠️ 恢复码仅此一次可返；UI 必须完成强制抄写确认后再丢弃
      return { recoveryCode: res.recovery_code ?? null };
    } catch (err) {
      error.value = err instanceof Error ? err.message : '注册失败';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function login(identifier: string, passcode: string): Promise<void> {
    const { api } = useCore();
    if (!api) throw new BizError(ERROR_CODE.UPSTREAM_UNAVAILABLE, '服务端不可达，请稍后重试');

    loading.value = true;
    error.value = null;
    try {
      const res = await api.login({ identifier, passcode });
      account.value = res.account;
      persistSession(toSession(res.account._id, res.tokens));
      ready.value = true;
    } catch (err) {
      error.value = err instanceof Error ? err.message : '登入失败';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  /**
   * 登出：先尽力吊销服务端 Refresh Token，再清本地。
   * 顺序不能反 —— 先清本地就拿不到 refresh_token 去吊销了，会留下一个可用的长期凭证。
   */
  async function logout(): Promise<void> {
    const rt = session.value?.refresh_token ?? null;
    try {
      await useCore().api?.logout(rt);
    } catch {
      // 服务端不可达也必须能登出：本地清干净，凭证过期后自然失效
    }
    persistSession(null);
    account.value = null;
  }

  /** 注销并删除云端数据（合规必需）。 */
  async function deleteAccount(): Promise<void> {
    const { api } = useCore();
    if (!api) throw new BizError(ERROR_CODE.UPSTREAM_UNAVAILABLE, '服务端不可达，请稍后重试');
    await api.deleteAccount();
    persistSession(null);
    account.value = null;
  }

  return {
    account,
    session,
    loading,
    error,
    ready,
    isAuthenticated,
    bootstrap,
    adoptSession,
    register,
    login,
    logout,
    deleteAccount,
  };
});

/** 与 `ApiClient.AuthTokens` 同形；此处独立声明避免 store 反向依赖 api 层。 */
interface AuthTokensLike {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}
