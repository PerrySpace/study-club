/**
 * 内容源（ContentSource）—— 内容分发的客户端落点。
 *
 * ⚠️ 与「本地优先」版本的重大差异：内容已改为**全部由后天管理**，
 * 因此原来的四条路径收敛为一条：
 *
 *   ① ~~BundledSource 随包构建~~      —— 已移除：内容不再随前端包分发
 *   ② ~~RemoteSource  远端静态覆盖~~  —— 已移除：真源是 MongoDB，不再有「静态 JSON 覆盖」
 *   ③ HttpSource（当前唯一）           —— 登录后从 `/content/bootstrap` 一次拉全量
 *   ④ 完整后端接口                     —— 即 ③
 *
 * 为什么改成「一次拉全量」而不是继续分页：
 * 内容已经不大（几百字 + 几十首诗 + 若干关卡），但分页要走 7 个并发请求，
 * 于是必然要处理「部分成功」的一致性问题（一个字表拉到了、古诗没拉到，怎么渲染？）。
 * `/content/bootstrap` 一次聚合下发，把首屏依赖收敛到单个请求，
 * 也让「内容版本」与「客户端缓存」的关系变得可判定。
 *
 * 兼容性硬约束仍然生效：内容包必须带 min_app_version；
 * 远端要求更高版本时**老客户端必须忽略该更新**（否则「字段不认识 → 渲染崩溃」）。
 */

import type { ApiClient } from '../api/client';
import type { LoggerAdapter } from '../platform/types';
import type { ContentBundle } from '../types/content';
import { EMPTY_BUNDLE as EMPTY } from '../types/content';

/**
 * 拉取时使用的年级上界：取 6（小学最高年级），
 * 于是 `grade <= 6` 的筛选等价于「全量字库」，客户端一次拿到所有可用内容。
 */
export const CONTENT_FETCH_MAX_GRADE = 6;

export interface ContentSource {
  readonly kind: 'http';
  load(): Promise<ContentBundle>;
}

/** 语义化版本比较：a <= b 返回 true。 */
export function versionLte(a: string, b: string): boolean {
  const pa = a.split('.').map((n) => Number.parseInt(n, 10) || 0);
  const pb = b.split('.').map((n) => Number.parseInt(n, 10) || 0);
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i += 1) {
    const x = pa[i] ?? 0;
    const y = pb[i] ?? 0;
    if (x !== y) return x < y;
  }
  return true;
}

/** 唯一的内容源：登录后从服务端 `/content/bootstrap` 拉全量内容。 */
export class HttpSource implements ContentSource {
  readonly kind = 'http' as const;

  constructor(
    private readonly api: ApiClient,
    private readonly logger?: LoggerAdapter,
  ) {}

  async load(): Promise<ContentBundle> {
    try {
      const res = (await this.api.contentBootstrap(CONTENT_FETCH_MAX_GRADE, true)) as unknown as {
        manifest?: ContentBundle['manifest'];
        characters?: ContentBundle['characters'];
        poems?: ContentBundle['poems'];
        units?: ContentBundle['units'];
        lessons?: ContentBundle['lessons'];
        stories?: ContentBundle['stories'];
        readings?: ContentBundle['readings'];
        badges?: ContentBundle['badges'];
      };
      return {
        manifest: res.manifest ?? EMPTY.manifest,
        characters: res.characters ?? [],
        poems: res.poems ?? [],
        units: res.units ?? [],
        lessons: res.lessons ?? [],
        stories: res.stories ?? [],
        // 短文是后加的内容类：老后端不返回该字段时给空数组，而不是 undefined，
        // 免得每个消费点都要写 `?? []`
        readings: res.readings ?? [],
        badges: res.badges ?? [],
      };
    } catch (err) {
      // ⚠️ 不静默降级成空内容：内容已无「随包兜底」，
      // 假装拿到空内容会让用户看到「一个字都没有」的空白页，
      // 不如把异常抛给调用方（登录态失效 / 网络断了，UI 给明确提示）。
      this.logger?.warn('内容拉取失败（已无随包兜底，交由 UI 展示错误态）', err);
      throw err;
    }
  }
}

export { EMPTY_BUNDLE } from '../types/content';
