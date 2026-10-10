/**
 * 管理员会话：只保存 admin JWT 与登录状态（不做 RBAC，见 05-1 §二）。
 */

import { defineStore } from 'pinia';
import { computed, ref } from 'vue';

import { adminApi } from '@/api/admin';
import { clearAccessToken, getAccessToken, setAccessToken } from '@/api/client';

export const useSessionStore = defineStore('admin-session', () => {
  const token = ref<string | null>(getAccessToken());

  const isAuthenticated = computed(() => Boolean(token.value));

  async function login(password: string): Promise<void> {
    const result = await adminApi.login(password);
    setAccessToken(result.access_token, result.expires_in);
    token.value = result.access_token;
  }

  function logout(): void {
    clearAccessToken();
    token.value = null;
  }

  /** 收到 401/403 时由调用方触发，避免带着失效 Token 反复请求。 */
  function invalidate(): void {
    logout();
  }

  return { token, isAuthenticated, login, logout, invalidate };
});
