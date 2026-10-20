/**
 * useTrackProgress —— 「这条线是不是全部学完了」的唯一判据。
 *
 * 为什么不能拿「没有下一关」当判据：孩子可以从首页的「古诗学习」直接打开
 * 最后一首 —— 此时 `nextLesson` 同样是 `null`，但整条线一关都没做。
 * 用 `!next` 触发「全部闯关完成」的庆祝，就会对着一首刚读完的诗说
 * 「你把整条线都学完了」，这是我们最不该撒的谎。
 *
 * 判据因此直接读**完成流水**（与地图页同一份数据）：该线每一关都有
 * `lesson_complete` 记录，才算学完。
 */

import { useChildStore, useCore } from '@study-club/core';

/** 一次拉多少条流水。与地图页一致：足够覆盖一个孩子几年的学习记录。 */
const RECORD_LIMIT = 500;

export function useTrackProgress() {
  const childStore = useChildStore();
  const core = useCore();

  /**
   * 给定这条线的全部关卡 id，判断是否**每一关**都完成过。
   *
   * 失败时返回 `false`（宁可不庆祝，也不误报）—— 调用方不要把异常当成
   * 「没学完」去提示用户，那只会让孩子看到一个莫名其妙的错误。
   */
  async function hasCompletedAll(lessonIds: readonly string[]): Promise<boolean> {
    const child = childStore.current;
    if (!child || !lessonIds.length) return false;
    try {
      const records = await core.repositories.progress.listLearningRecords(child._id, RECORD_LIMIT);
      const done = new Set(
        records
          .filter((r) => r.event_type === 'lesson_complete' && r.lesson_id)
          .map((r) => r.lesson_id as string),
      );
      return lessonIds.every((id) => done.has(id));
    } catch {
      return false;
    }
  }

  return { hasCompletedAll };
}
