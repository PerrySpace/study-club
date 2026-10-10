/**
 * 阅读承接：短文「读得下来吗」的判定与排序 —— 识字学科专属逻辑。
 *
 * 判据：这段逻辑换成英语分级读物还成立吗？**成立** —— 但它依赖
 * 「字库 + 已学字」这套识字口径（`character_chars` 是汉字字面），
 * 且排序目标是幼儿识字读本，因此放在学科包而不是 core。
 *
 * 为什么这是关键一环：孩子认了字却读不了东西，识字就停在"认卡片"上，
 * 学过的字也不会在语境里复现，遗忘得快。竞品的做法是**用学过的字编读本**，
 * 每本只有十来个字，翻开每个字都认识。本文件负责判断
 * 「哪几篇现在读得下来」，把读不了的先收起来 —— 读得费劲的读本比没有读本更打击人。
 */

export interface PassageCoverage {
  /** 去重后的总字数 */
  total: number;
  /** 其中已学（在字库且已学过）的字数 */
  known: number;
  /** 尚未学过的字（家长带读用），按首次出现顺序 */
  unknownChars: string[];
  /** 覆盖率 0–1 */
  ratio: number;
}

/** 计算某篇短文对「当前已学字集合」的覆盖率。 */
export function passageCoverage(characterChars: string[], known: Set<string>): PassageCoverage {
  const unique = Array.from(new Set(characterChars.filter((c) => c && c.trim())));
  const unknownChars = unique.filter((c) => !known.has(c));
  const knownCount = unique.length - unknownChars.length;
  return {
    total: unique.length,
    known: knownCount,
    unknownChars,
    ratio: unique.length ? knownCount / unique.length : 0,
  };
}

export interface PassageCandidate<T> {
  item: T;
  coverage: PassageCoverage;
}

export interface RankOptions {
  /** 覆盖率低于此值视为"读不下来"，直接不收（默认 0.8）。 */
  minRatio?: number;
  /** 最多返回几篇（不传则不限）。 */
  limit?: number;
}

/**
 * 挑出「现在读得下来」的短文，按**越好读越靠前**排序。
 *
 * 排序口径：覆盖率降序 → 字数升序 → 原顺序。
 * 为什么覆盖率优先而不是字数优先：孩子在意的是"我认识几个字"，
 * 一篇 20 字认识 19 个，比一篇 8 字认识 6 个更让他有成就感；
 * 覆盖率相同时再按短优先，减少疲劳。
 */
export function rankPassages<T extends { character_chars: string[] }>(
  items: T[],
  known: Set<string>,
  options: RankOptions = {},
): PassageCandidate<T>[] {
  const minRatio = options.minRatio ?? 0.8;
  const candidates: Array<PassageCandidate<T> & { index: number }> = [];

  items.forEach((item, index) => {
    const coverage = passageCoverage(item.character_chars, known);
    if (coverage.ratio < minRatio) return;
    candidates.push({ item, coverage, index });
  });

  candidates.sort((a, b) => {
    if (b.coverage.ratio !== a.coverage.ratio) return b.coverage.ratio - a.coverage.ratio;
    if (a.coverage.total !== b.coverage.total) return a.coverage.total - b.coverage.total;
    return a.index - b.index;
  });

  const ranked = candidates.map(({ item, coverage }) => ({ item, coverage }));
  return typeof options.limit === 'number' ? ranked.slice(0, Math.max(0, options.limit)) : ranked;
}
