/**
 * 内容源（ContentSource）—— 内容分发的客户端落点。
 *
 * 内容全部由服务端管理，客户端唯一的内容源是 `HttpSource`：
 * 登录后从 `/content/bootstrap` 一次拉取全量内容。
 *
 * 为什么是「一次拉全量」而不是分页：
 * 内容规模不大（几百字 + 几十首诗 + 若干关卡），分页要走多个并发请求，
 * 于是必然要处理「部分成功」的一致性问题（字表拉到了、古诗没拉到，怎么渲染？）。
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
 * 拉取时使用的年级上界。
 *
 * 取 **30** = 后端 `runtime_config.GRADE_MAX`，语义是「不限」：`grade <= 30`
 * 等价于「全量」，客户端一次拿到所有可用内容 —— 包括**学龄前（0）**与后台
 * 扩展出的 7/8/9 年级。
 *
 * ⛔ 不要写死成 6。后台年级是**可配置**的（设置里能增删，本仓已扩到 9），
 * 写死 6 会让那些年级的内容在客户端**怎么都拉不到** —— 服务端明明存着，
 * 表现却是「导入没生效」，而两端代码都看不出哪里不对。
 */
export const CONTENT_FETCH_MAX_GRADE = 30;

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
