/**
 * 字源图解析 —— 把 `character.glyph` 统一成「能渲染的东西」。
 *
 * ## 为什么需要它
 * `glyph` 字段历史上只放 **emoji**（水 → 💧）。现在运营希望能填**图片**：
 *  - 外链图片：`https://.../shui.png`
 *  - 站内素材 id：`as_0123...`（素材中心上传后拿到的 id）
 *  - emoji 本身（保持向后兼容）
 *
 * 三种形态混在一个字符串里，**每个渲染点自己 if-else 一定会漏** ——
 * 事实上就已经有两处渲染（`CharCard`、`QuestionCard`）各自硬编码了 emoji 分支。
 * 收敛到这里之后，新增渲染点只要调 `resolveGlyph()`。
 *
 * ## 优先级：图片 > emoji
 * emoji 是零素材成本的兜底；一旦配了图，图比 emoji 更有表现力。
 * 但**图片加载失败必须回落到 emoji**，否则网络抖动会让「看图选字」变成空白题干。
 */

export type GlyphKind = 'image' | 'emoji';

export interface ResolvedGlyph {
  kind: GlyphKind;
  /** 图片地址（kind=image 时有效） */
  src?: string;
  /** 展示文本：图片时是 alt，emoji 时是符号本身 */
  text: string;
}

/** 站内素材 id 的 id 前缀（见 core 的素材约定）。 */
const ASSET_PREFIX = 'as_';

/** 素材下发是公开端点：`<img>` 无法携带 Authorization。 */
export function assetUrl(assetId: string): string {
  return `/api/v1/assets/${assetId}`;
}

function isHttpUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

/**
 * 解析字源图。
 *
 * @param raw `character.glyph` 原始值（可能是 null/空/外链/素材 id/emoji）
 */
export function resolveGlyph(raw: string | null | undefined): ResolvedGlyph | null {
  const value = (raw ?? '').trim();
  if (!value) return null;

  // 1) 站内素材 id —— 素材中心上传后拿到的 id
  if (value.startsWith(ASSET_PREFIX)) {
    return { kind: 'image', src: assetUrl(value), text: value };
  }

  // 2) 外链图片
  if (isHttpUrl(value)) {
    return { kind: 'image', src: value, text: value };
  }

  // 3) emoji（历史形态，保持向后兼容）
  return { kind: 'emoji', text: value };
}