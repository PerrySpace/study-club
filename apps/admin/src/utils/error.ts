/**
 * 统一错误反馈：把接口异常翻译成给单人使用者看的中文提示。
 *
 * 处理三类：
 *  1. Token 失效 / 越权 → 清会话并回登录页（不弹重复的错误框）
 *  2. 业务错误（ApiError） → 显示后端 message，带上字段级 errors
 *  3. 网络错误（NetworkError） → 提示后端不可达
 */

import { ElMessage } from 'element-plus';

import { ApiError, NetworkError, isAuthError } from '@/api/client';
import router from '@/router';
import { useSessionStore } from '@/stores/session';

/** 返回可直接展示在页面上的文案（同时弹一条 message）。 */
export function reportError(err: unknown, fallback = '操作失败'): string {
  if (isAuthError(err)) {
    useSessionStore().invalidate();
    void router.replace({ name: 'login' });
    return '登录状态已失效，请重新登录';
  }

  let message = fallback;
  if (err instanceof ApiError) {
    message = err.message || fallback;
    const details = err.errors?.map((item) => `${item.field}：${item.reason}`).join('；');
    if (details) message = `${message}（${details}）`;
  } else if (err instanceof NetworkError) {
    message = err.message;
  } else if (err instanceof Error && err.message) {
    message = err.message;
  }

  ElMessage.error(message);
  return message;
}
