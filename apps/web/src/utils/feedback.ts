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
 */

export const PRAISE_WORDS: readonly string[] = [
  '读得真棒！',
  '太厉害了，一遍就对了！',
  '声音真好听，读对啦！',
  '真不错，就是这样读！',
  '太棒了，一字不差！',
  '好厉害，小兔给你点赞！',
  '读得又响亮又清楚！',
];

export const ENCOURAGE_WORDS: readonly string[] = [
  '再试一次吧',
  '没关系，我们再来一遍',
  '差一点点了，再读一次',
  '别着急，大胆读出来',
  '跟着小兔，再试一遍',
  '已经很接近啦，再来一次',
];

let lastPraiseIndex = -1;
let lastEncourageIndex = -1;

function pickFrom(pool: readonly string[], lastIndex: number): number {
  if (pool.length <= 1) return 0;
  let index = Math.floor(Math.random() * pool.length);
  // 抽到上一次那个就顺延一位，保证「换口味」
  if (index === lastIndex) index = (index + 1) % pool.length;
  return index;
}

/** 随机抽一句表扬（不会与上一次重复）。 */
export function pickPraise(): string {
  lastPraiseIndex = pickFrom(PRAISE_WORDS, lastPraiseIndex);
  return PRAISE_WORDS[lastPraiseIndex] ?? PRAISE_WORDS[0]!;
}

/** 随机抽一句鼓励（不会与上一次重复）。 */
export function pickEncouragement(): string {
  lastEncourageIndex = pickFrom(ENCOURAGE_WORDS, lastEncourageIndex);
  return ENCOURAGE_WORDS[lastEncourageIndex] ?? ENCOURAGE_WORDS[0]!;
}
