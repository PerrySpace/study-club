/**
 * 核心上下文 —— 依赖注入容器。
 *
 * core 不自己创建任何平台实现；外壳在启动时调用 setCoreContext() 注入。
 * 这是「从纯本地到轻同步再到账号云同步只换注入」的落点（见 02-4 §5.3）。
 */

import type { ApiClient } from '../api/client';
import type { FeatureFlags } from '../flags';
import type { PlatformContext } from '../platform/types';
import type { ContentSource } from '../repositories/content';
import type { ProgressRepository, Repositories } from '../repositories/types';

export interface CoreContext {
  flags: FeatureFlags;
  platform: PlatformContext;
  /** 只有 progress —— 身份仓储随「本地身份」一并移除，登录态真源是 Session。 */
  repositories: { progress: ProgressRepository };
  api: ApiClient | null;
  contentSource: ContentSource;
}

let context: CoreContext | null = null;

export function setCoreContext(ctx: CoreContext): void {
  context = ctx;
}

export function useCore(): CoreContext {
  if (!context) {
    throw new Error('CoreContext 尚未初始化：请在外壳启动时调用 setCoreContext()');
  }
  return context;
}

export function hasCoreContext(): boolean {
  return context !== null;
}

export type { Repositories };
