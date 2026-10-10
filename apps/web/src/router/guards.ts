/**
 * 路由守卫：登录守卫 + 档案守卫 + 能力开关守卫。
 *
 * ⚠️ 关键变更：旧版的第①条纪律是「『先不注册』永远可用，不得出现强制注册墙」，
 * 因此守卫只把人送去引导页。本轮存储口径改为「彻底服务端、必须先登录」后，
 * 这条纪律**被有意废止**：现在没有会话就一律去登录页。
 *
 * 三条现行纪律：
 *   ① 未登录 → 登录页（`requiresAuth: false` 的白名单除外），并带上 `redirect` 以便登录后回原页；
 *   ② 「登录了但还没有孩子档案」→ 引导页（不是登录页，账号是好的，缺的是档案）；
 *   ③ 守卫里不写平台 API，一律走仓储层与偏好适配器。
 */

import { hasCoreContext, useAuthStore, useChildStore, useContentStore, useCore } from '@study-club/core';
import type { Router, RouteLocationRaw } from 'vue-router';

/** 不需要登录即可访问的路由名（与 router/index.ts 的 `requiresAuth: false` 呼应）。 */
const PUBLIC_ROUTE_NAMES = new Set<string>(['login', 'register', 'not-found']);

/** 登录态下不应再停留的页面（已在登录页却又登录成功时）。 */
const AUTH_ENTRY_ROUTE_NAMES = new Set<string>(['login', 'register']);

/**
 * 收集到目标路由的跳转对象。
 * 只在 `redirect` 非首页时带上，避免登录后 URL 上挂一个没意义的 `?redirect=/`。
 */
function loginRedirect(router: Router, fullPath: string): RouteLocationRaw {
  const target: RouteLocationRaw = router.hasRoute('login') ? { name: 'login' } : { name: 'not-found' };
  if (fullPath && fullPath !== '/') {
    return { ...(target as object), query: { redirect: fullPath }, replace: true } as RouteLocationRaw;
  }
  return { ...(target as object), replace: true } as RouteLocationRaw;
}

export function installGuards(router: Router): void {
  router.beforeEach(async (to) => {
    if (!hasCoreContext()) return true;

    // ---- 能力开关守卫（兜底）：关闭的能力即使被直接输入 URL 也拒绝 ----
    const feature = to.meta.feature;
    if (feature && !useCore().flags[feature]) {
      return { name: 'home', replace: true };
    }

    const routeName = String(to.name ?? '');
    const requiresAuth = to.meta.requiresAuth !== false && !PUBLIC_ROUTE_NAMES.has(routeName);

    // ---- 登录守卫 ----
    const auth = useAuthStore();
    // 会话恢复只做一次；`ready` 之后这里不再重复打 /auth/me
    if (!auth.ready) await auth.bootstrap();

    if (requiresAuth && !auth.isAuthenticated) {
      return loginRedirect(router, to.fullPath);
    }
    if (!requiresAuth && auth.isAuthenticated && AUTH_ENTRY_ROUTE_NAMES.has(routeName)) {
      return { name: 'home', replace: true };
    }
    if (!requiresAuth) return true;

    // ---- 档案守卫：账号没问题，缺的是孩子档案 ----
    const child = useChildStore();
    if (!child.loaded) {
      try {
        await child.load();
      } catch {
        // 拉不到档案不应把人卡死在守卫里：放行到目标页，由页面展示可重试的错误态。
        // （守卫里静默吞异常在这里是合理的例外，因为它没有「空数据」的误导性 —— 页面还有自己的加载逻辑。）
        return true;
      }
    }

    const requiresChild = to.meta.requiresChild !== false;
    if (requiresChild && !child.current) {
      return { name: 'onboarding', replace: true };
    }
    if (!requiresChild && routeName === 'onboarding' && child.current) {
      return { name: 'home', replace: true };
    }

    // ---- 内容包：进入学习页前确保已加载 ----
    // 失败不阻塞：内容源报错时页面展示明确错误态与重试按钮，而不是把人挡在守德里。
    if (requiresChild) {
      try {
        await useContentStore().load();
      } catch {
        // 同上
      }
    }

    return true;
  });

  router.afterEach((to) => {
    const title = to.meta.title;
    document.title = title ? `${title} · 学习俱乐部` : '学习俱乐部';
  });
}
