/**
 * 业务代码获取平台能力的**唯一入口**（见 06-1 §2.9.2）。
 *
 * ❌ 禁止：`navigator.xxx` / `window.matchMedia(...)` 直接写在组件里。
 * ✅ 正确：`const { capabilities } = usePlatform();`
 */

import { computed } from 'vue';

import { useCore } from '@study-club/core';
import type { FeatureFlags } from '@study-club/core';

export function usePlatform() {
  const core = useCore();

  return {
    platform: core.platform,
    // 注意：这里**没有** storage。浏览器不再保存任何业务数据（IndexedDB 适配器已删除），
    // preference 仅用于会话 Token 与少量 UI 偏好，需要业务存储请走 core.repositories。
    preference: core.platform.preference,
    http: core.platform.http,
    clock: core.platform.clock,
    logger: core.platform.logger,
    // 语音能力（朗读 / 跟读）。组件里**不要**直接用 speechSynthesis，
    // 请用 `useSpeech()` —— 它额外维护「是否播放中/识别中」的响应式状态。
    speech: core.platform.speech,
    capabilities: core.platform.capabilities,
    client: core.platform.client,
    repositories: core.repositories,
    api: core.api,
    contentSource: core.contentSource,
    flags: core.flags,
    /** 能力开关判定（开关值启动时求值一次，运行中不散落读取）。 */
    isEnabled: (key: keyof FeatureFlags): boolean => core.flags[key],
    hasBackend: computed(() => core.api !== null),
  };
}
