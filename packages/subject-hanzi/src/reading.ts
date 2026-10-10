/**
 * 跟读判定与朗读文案 —— 识字学科专属逻辑（**不得写进 packages/core**）。
 *
 * 判据：这段逻辑换成英语单词跟读还成立吗？不成立 → 属学科包。
 *
 * ⚠️ 本文件的判定只回答**一个**问题：「孩子有没有读到目标字词」。
 * 它**不是**发音评分：
 *   - 浏览器原生 ASR 只给最终文本，中文几乎不给置信度；
 *   - 声调（mā / má / mǎ / mà）在识别文本里完全不可见。
 * 因此「把『妈』读成『马』判通过」是**已知且被接受**的行为 ——
 * 我们宁可宽松（保护孩子的积极性），也不用一个看起来精确、实则在骗人的分数。
 * 真要发音打分，必须接云端音素级评测（`enableCloudAssessment` 开关），
 * 没接就不能给分。
 */

/** 语音识别文本的归一化：去掉空白与常见标点，只留下可比对的字符。 */
function normalizeSpeech(text: string): string {
  return text
    .replace(/[\s\u3000]+/g, '')
    .replace(/[，。、！？；：""''（）《》〈〉【】,.;:!?'"()<>[\]{}~—…·\-_/\\|]/g, '')
    .toLowerCase();
}

/**
 * 目标字词被识别文本「覆盖」的比例（0–1）。
 *
 * 算法：把目标字符串拆成字符，逐个去识别结果里找（**找到就消耗掉一个**，
 * 避免「一个字重读三遍」被算成三个字都读到了）。
 * 用覆盖率而不是「完全相等」，是因为孩子跟读时经常多读一两个字
 * （比如读词时把量词带上），严格相等会大量误判。
 */
export function readingCoverage(transcript: string, target: string): number {
  const want = normalizeSpeech(target);
  if (!want) return 0;

  const pool = normalizeSpeech(transcript).split('');
  if (!pool.length) return 0;

  let hit = 0;
  for (const ch of want) {
    const idx = pool.indexOf(ch);
    if (idx >= 0) {
      pool.splice(idx, 1);
      hit += 1;
    }
  }
  return hit / want.length;
}

/** 覆盖率阈值：单字要求完全命中；词句允许漏一到两字。 */
export function readingThreshold(target: string): number {
  const len = normalizeSpeech(target).length;
  if (len <= 1) return 1;
  if (len <= 3) return 2 / 3;
  return 0.7;
}

/**
 * 跟读是否「读到了」。
 *
 * @param transcript 识别到的文本（可能为空串 —— 空串一律判不通过）
 * @param target     目标字词（汉字 / 词语 / 诗句）
 */
export function readingMatches(transcript: string, target: string): boolean {
  if (!normalizeSpeech(transcript)) return false;
  return readingCoverage(transcript, target) >= readingThreshold(target);
}

/**
 * 朗读（TTS）时的「读什么」与语速。
 *
 * 汉字单字用慢速（声调要靠拖长才听得出来），整句恢复正常语速 ——
 * 句子里逐字放慢会让句子失去韵律，孩子反而更听不懂。
 */
export interface ReadingPlan {
  text: string;
  rate: number;
}

export function readingPlanForChar(char: string): ReadingPlan {
  return { text: char, rate: 0.7 };
}

export function readingPlanForWord(word: string): ReadingPlan {
  // 两个字以上的词用 0.8：比单字快一点，比正常慢一点。
  return { text: word, rate: word.length > 2 ? 0.9 : 0.8 };
}

export function readingPlanForSentence(sentence: string): ReadingPlan {
  return { text: sentence, rate: 0.95 };
}
