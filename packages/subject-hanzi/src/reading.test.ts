import { describe, expect, it } from 'vitest';

import {
  readingCoverage,
  readingMatches,
  readingPlanForChar,
  readingPlanForSentence,
  readingPlanForWord,
} from './reading';

/**
 * 语速是**产品口径**，不是随手可调的常量。
 *
 * 句子基速接近成人语速（0.95）时，6 岁孩子第一遍基本听不清。这里把边界钉住，
 * 以后谁想调快，测试会先拦一次，
 * 让「调快」变成一个需要解释的决定，而不是顺手改个数字。
 */
describe('朗读语速', () => {
  it('整句不超过 0.8（跟读得上的上限）', () => {
    expect(readingPlanForSentence('床前明月光，疑是地上霜。').rate).toBeLessThanOrEqual(0.8);
  });

  it('单字比词语慢、词语比整句慢', () => {
    const char = readingPlanForChar('水').rate;
    const word = readingPlanForWord('月亮').rate;
    const sentence = readingPlanForSentence('床前明月光').rate;
    expect(char).toBeLessThan(word);
    expect(word).toBeLessThan(sentence);
  });

  it('都不低于 0.5（再慢就变成逐字蹦，失去声调对比）', () => {
    for (const plan of [
      readingPlanForChar('水'),
      readingPlanForWord('月亮'),
      readingPlanForSentence('床前明月光'),
    ]) {
      expect(plan.rate).toBeGreaterThanOrEqual(0.5);
    }
  });
});

describe('跟读判定', () => {
  it('诗句带标点时也能命中', () => {
    expect(readingMatches('床前明月光疑是地上霜', '床前明月光，疑是地上霜。')).toBe(true);
  });

  it('只读了半句诗不算通过（长句阈值 0.7）', () => {
    expect(readingMatches('床前明月光', '床前明月光，疑是地上霜。')).toBe(false);
  });

  it('覆盖率按「消耗字符」计算，重复读同一个字不加分', () => {
    expect(readingCoverage('水水水', '水果')).toBeCloseTo(0.5, 5);
  });

  it('空识别结果一律不通过', () => {
    expect(readingMatches('', '水')).toBe(false);
  });
});
