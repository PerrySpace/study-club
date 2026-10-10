/**
 * 阶段检测编排 —— 识字学科专属逻辑（**不得写进 packages/core**）。
 *
 * 为什么需要它（对标主流识字产品的复习闭环）：
 * 只推新字、从不回头，是识字产品最常见的失败模式 —— 一百个新字学完，
 * 回头看认得的只剩二十个。竞品的通行做法是把复习拆成三层：
 * **每日回顾 / 阶段检测 / 定期复习**。本文件负责中间那层：
 * 在「学新字」的队列里**按固定节奏插入旧字抽查**，让孩子在还没忘的时候
 * 先自己从记忆里把字调出来（提取练习，比再给他看一遍动画有效得多）。
 *
 * 设计约束：
 * - **纯函数**，不依赖时间、随机数、平台 API —— 因此可单测、可复现。
 * - 泛型 `<T>`：只要求调用方给「新字题数组」和「旧字题数组」，
 *   题目的形状由学科包之外决定（本文件不 import 学科包里的 Question）。
 * - **不偷换顺序**：新字题的原顺序原样保留，抽查题只做**插入**。
 *   学新字的顺序本身是有教学设计的（由易到难、同偏旁归类），打乱它是另一回事。
 */

export type StageQueueKind = 'learn' | 'stage';

export interface StageQueueItem<T> {
  kind: StageQueueKind;
  /** 第几次阶段检测（从 1 开始）；`learn` 项为 0 */
  checkpoint: number;
  question: T;
}

export interface InterleaveOptions {
  /** 每学 N 个新字插入一次抽查。小于 2 视为不插（一题一测没有意义）。 */
  every: number;
  /** 每次抽查出几道旧字题（默认 1）。 */
  perCheck?: number;
  /** 最多插入几次（默认 3）—— 一节十几分钟的课里插太多次会打断节奏。 */
  maxChecks?: number;
  /**
   * 新字数不足 `every` 时的兜底：设为 true 时，即便一轮都没凑够，
   * 也在最后追加一次抽查（`every` 大于本次新字数时才用得上）。
   */
  alwaysOneCheck?: boolean;
}

/** 归一化选项：把越界/非法输入收敛成可用值（调用方传什么都不该崩）。 */
function normalize(options: InterleaveOptions) {
  const every = Math.max(0, Math.floor(options.every || 0));
  return {
    every,
    perCheck: Math.max(1, Math.floor(options.perCheck ?? 1)),
    maxChecks: Math.max(0, Math.floor(options.maxChecks ?? 3)),
    alwaysOneCheck: options.alwaysOneCheck === true,
  };
}

/**
 * 把新字题与旧字抽查题交织成一条答题队列。
 *
 * @param learn     新字题（按教学顺序）
 * @param stagePool 旧字抽查题池（按「最该复习」排序，由调用方决定）
 */
export function interleaveStageTests<T>(
  learn: T[],
  stagePool: T[],
  options: InterleaveOptions,
): StageQueueItem<T>[] {
  const { every, perCheck, maxChecks, alwaysOneCheck } = normalize(options);
  const out: StageQueueItem<T>[] = learn.map((question) => ({
    kind: 'learn' as const,
    checkpoint: 0,
    question,
  }));

  // 池子空 → 无从抽查；节奏关掉 / 上限为 0 → 保持纯新字队列
  if (!stagePool.length || every < 2 || maxChecks === 0) return out;

  let poolCursor = 0;
  /** 从池子里取 `count` 道；取完即止（不循环复用，同一段里不重复出同一道题）。 */
  const take = (count: number): T[] => {
    const picked: T[] = [];
    while (picked.length < count && poolCursor < stagePool.length) {
      picked.push(stagePool[poolCursor]);
      poolCursor += 1;
    }
    return picked;
  };

  const checkpoints: Array<{ afterIndex: number; picks: T[] }> = [];
  for (let boundary = every; boundary <= learn.length; boundary += every) {
    if (checkpoints.length >= maxChecks) break;
    const picks = take(perCheck);
    if (!picks.length) break;
    checkpoints.push({ afterIndex: boundary, picks });
  }

  if (!checkpoints.length && alwaysOneCheck && learn.length) {
    const picks = take(perCheck);
    if (picks.length) checkpoints.push({ afterIndex: learn.length, picks });
  }

  // 从后往前插入：前面的下标不会被后面的插入推走
  for (let i = checkpoints.length - 1; i >= 0; i -= 1) {
    const { afterIndex, picks } = checkpoints[i];
    const block: StageQueueItem<T>[] = picks.map((question) => ({
      kind: 'stage' as const,
      checkpoint: i + 1,
      question,
    }));
    out.splice(afterIndex, 0, ...block);
  }

  return out;
}

/** 队列里一共有几次阶段检测（用于进度条上先告诉孩子"中间会查两次"）。 */
export function countCheckpoints<T>(queue: StageQueueItem<T>[]): number {
  return queue.reduce((max, item) => (item.checkpoint > max ? item.checkpoint : max), 0);
}

/**
 * 从队列里取「要提交给服务端的字」—— 阶段检测题与新字题一视同仁，
 * 都按 normal 作答上报（复习状态由服务端算，客户端不区分对待）。
 */
export function queueCharacters<T extends { char: string }>(
  queue: StageQueueItem<T>[],
): string[] {
  return Array.from(new Set(queue.map((item) => item.question.char)));
}
