/**
 * apps/web 启动入口。
 *
 * 顺序（顺序即契约）：
 *   0. installInteractionGuards() 装上防误触守卫 —— 必须**早于**首屏渲染，
 *      否则第一个交互（点字卡）就可能在守卫到位前被浏览器选中
 *   1. createPlatform() 组装适配器 + 仓储 + ApiClient + 内容源，并 setCoreContext()
 *   2. createApp + Pinia + Router
 *   3. auth.bootstrap() 恢复会话 —— **必须在拉任何业务数据之前**，
 *      因为所有业务数据都要带 Authorization，而 Token 正是在这一步挂到 ApiClient 上的
 *   4. 已登录才预取 child / content（未登录时拉也拉不到，只会白白报 401 并让首屏闪错）
 *   5. mount
 *   6. 注册 Service Worker（失败静默，不影响主流程）
 */

import { createApp } from 'vue';
import { createPinia } from 'pinia';

import { useAuthStore, useChildStore, useContentStore, useSiteConfigStore } from '@study-club/core';

import App from './App.vue';
import { createPlatform } from './platform';
import { installInteractionGuards } from './platform/dom-guard';
import { registerServiceWorker } from './platform/pwa';
import { createAppRouter } from './router';
import { useUiStore } from './stores/ui';

import './styles/base.css';
import './styles/components.css';
// 学习页「一屏」骨架（必须晚于 base/components：它是覆盖层，见文件内注释）
import './styles/learn-screen.css';

async function bootstrap(): Promise<void> {
  // 0. 防误触：长按选中 / 拖拽 / 捏合缩放（见 platform/dom-guard.ts）
  installInteractionGuards();

  // 1. 平台与核心上下文
  createPlatform();

  const app = createApp(App);
  const pinia = createPinia();
  app.use(pinia);

  // 站点公开配置：无需登录，且决定「邀请码是否必填」等运行期行为
  // （服务端 app_settings 为真源，后台可热改）。失败静默降级到构建期开关。
  await useSiteConfigStore(pinia).load().catch(() => undefined);

  // 2. 路由（路由表由能力开关生成：关闭的能力其路由不注册）
  const router = createAppRouter();
  app.use(router);

  // 3. 会话恢复：先拿到 Token，后续请求才带得上鉴权头
  const auth = useAuthStore(pinia);
  await auth.bootstrap();

  // 4. 已登录才预取。未登录时这两步注定失败，跳过可让首屏直接落到登录页而不闪错误。
  if (auth.isAuthenticated) {
    const child = useChildStore(pinia);
    const content = useContentStore(pinia);
    // 这里刻意吞掉异常：预取只是「让首屏更快」，失败了页面自己还有加载/重试逻辑，
    // 不该因为预热失败就卡住整个启动。
    await child.load().catch(() => undefined);
    await content.load().catch(() => undefined);
  }

  app.mount('#app');

  // 5. PWA
  const ui = useUiStore(pinia);
  registerServiceWorker({
    onOfflineReady: () => ui.pushToast('已可离线使用，添加到主屏幕更方便', 'success'),
  });
}

void bootstrap();
