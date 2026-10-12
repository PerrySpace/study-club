/**
 * 反馈词库 —— 表扬与鼓励的随机池。
 *
 * 为什么是「池」而不是固定一句：固定文案孩子很快听腻，随机轮换能保持
 * 表扬的新鲜感（启蒙产品的常规做法，对标洪恩/悟空的多变的夸奖语）。
 *
 * 两条口径：
 *   - **表扬词**是完整一句（自带标点），可直接作为反馈正文；
 *   - **鼓励词**不带结尾标点 —— 调用方通常还要接行动指引
 *     （如「，慢慢读『水』」），所以句尾留给调用方拼接。
 *
 * 随机但**不连续重复**：上一轮刚用过的词，下一轮不再出现。
 * 逻辑放 web 层而非学科包：这是中文产品的文案口径，英语跟读复用组件时
 * 可以注入自己的词库（见 ReadAlongButton 的 props）。
 *
 * ⚠️ 词库里提到伙伴的地方一律写占位符 `{伙伴}`，**不要写死「小兔」**：
 *    伙伴的名字来自孩子选的头像（`AVATAR_LABELS`），写死会让选了熊猫的孩子
 *    被叫「小兔」——「我选的没生效」最典型的形态，且只在非默认头像上复现。
 */

import { avatarLabel, DEFAULT_AVATAR } from '@study-club/core';

/** 伙伴名的占位符。词库里凡是提到伙伴的地方都用它。 */
export const COMPANION_PLACEHOLDER = '{伙伴}';

export const PRAISE_WORDS: readonly string[] = [
  '读得真棒！',
  '太厉害了，一遍就对了！',
  '声音真好听，读对啦！',
  '真不错，就是这样读！',
  '太棒了，一字不差！',
  '好厉害，{伙伴}给你点赞！',
  '读得又响亮又清楚！',
];

export const ENCOURAGE_WORDS: readonly string[] = [
  '再试一次吧',
  '没关系，我们再来一遍',
  '差一点点了，再读一次',
  '别着急，大胆读出来',
  '跟着{伙伴}，再试一遍',
  '已经很接近啦，再来一次',
];

let lastPraiseIndex = -1;
let lastEncourageIndex = -1;

/**
 * 把占位符换成伙伴名。
 * 调用方没传名字时回落到**默认头像的名字**（与界面上的默认伙伴一致），
 * 而不是把字面上的 `{伙伴}` 端给孩子看。
 */
function withCompanion(text: string, name?: string): string {
  return text.split(COMPANION_PLACEHOLDER).join(name?.trim() || avatarLabel(DEFAULT_AVATAR));
}

function pickFrom(pool: readonly string[], lastIndex: number): number {
  if (pool.length <= 1) return 0;
  let index = Math.floor(Math.random() * pool.length);
  // 抽到上一次那个就顺延一位，保证「换口味」
  if (index === lastIndex) index = (index + 1) % pool.length;
  return index;
}

/** 随机抽一句表扬（不会与上一次重复）。`companionName` 用于替换词库里的 `{伙伴}`。 */
export function pickPraise(companionName?: string): string {
  lastPraiseIndex = pickFrom(PRAISE_WORDS, lastPraiseIndex);
  return withCompanion(PRAISE_WORDS[lastPraiseIndex] ?? PRAISE_WORDS[0]!, companionName);
}

/** 随机抽一句鼓励（不会与上一次重复）。`companionName` 用于替换词库里的 `{伙伴}`。 */
export function pickEncouragement(companionName?: string): string {
  lastEncourageIndex = pickFrom(ENCOURAGE_WORDS, lastEncourageIndex);
  return withCompanion(ENCOURAGE_WORDS[lastEncourageIndex] ?? ENCOURAGE_WORDS[0]!, companionName);
}
