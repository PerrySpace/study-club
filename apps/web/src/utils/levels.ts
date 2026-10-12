/**
 * 关卡流转 —— 三条线（识字 / 古诗 / 故事）各自的落地页与「下一关」。
 *
 * ## 为什么需要一个专门的文件
 * 关卡改自动生成之后，`lesson.character_ids` 的含义**随 track 变化**：
 * 识字线装的是字 id，古诗线装的是诗 id，故事线装的是故事 id
 * （生成器把「一条内容」当作一关的来源，见 core/algorithms/lessons.ts）。
 * 于是「点某一关该去哪个页面」这件事就有了一层映射 —— 以前所有关卡都进
 * LessonView，古诗关和故事关因此会落到「这里暂时没有可练的字」的空状态上，
 * 这就是**关卡跳不出去、流程没有闭环**的根因。
 *
 * 三个视图（Lesson / Poem / Story）都要算「下一关」，把映射与查找放在一处，
 * 避免三处各写一份、改一处漏两处。
 */

import type { RouteLocationRaw } from 'vue-router';

import type { Lesson } from '@study-club/core';

export type Track = 'literacy' | 'poem' | 'story';

/**
 * 关卡所属内容线。
 *
 * `track` 缺失（历史数据）时按 id 前缀兜底：生成器用 `{track}:{grade}:{序号}`。
 */
export function trackOf(lesson: Lesson | undefined | null): Track {
  const raw = lesson?.track ?? String(lesson?._id ?? '').split(':')[0];
  return raw === 'poem' || raw === 'story' ? raw : 'literacy';
}

/** 关卡承载的内容 id（古诗=诗 id，故事=故事 id）。 */
export function contentIdOf(lesson: Lesson): string {
  return lesson.character_ids[0] ?? '';
}

/**
 * 关卡 → 目标路由。
 *
 * 古诗/故事页必须知道「自己是第几关」才能记关卡完成流水
 * （`lesson_complete.lesson_id`），但它们的路由参数是内容 id（诗/故事），
 * 所以关卡 id 用 query 带上；页面在 query 缺失时还能按内容 id 反查（见下）。
 */
export function routeForLesson(lesson: Lesson): RouteLocationRaw {
  const track = trackOf(lesson);
  if (track === 'poem') {
    return {
      name: 'poem',
      params: { poemId: contentIdOf(lesson) },
      query: { lesson: lesson._id },
    };
  }
  if (track === 'story') {
    return {
      name: 'story',
      params: { storyId: contentIdOf(lesson) },
      query: { lesson: lesson._id },
    };
  }
  return { name: 'lesson', params: { lessonId: lesson._id } };
}

/** 同一条线上的下一关；已是最后一关则返回 null。 */
export function nextLesson(lessons: Lesson[], lessonId: string): Lesson | null {
  const index = lessons.findIndex((l) => l._id === lessonId);
  if (index < 0) return null;
  return lessons[index + 1] ?? null;
}

/**
 * 某条线的入口关卡（该线的第一关）—— 「换个方向继续」时用。
 *
 * 为什么取第一关、而不是「第一个未完成的」：关卡页此刻拿不到完整的完成记录
 * （`learning` store 只存当前会话，完整记录要另发一次 `listLearningRecords`），
 * 为一颗按钮多发一次请求不划算。第一关重玩无害（只可能把星星刷高）；
 * 想接着上次的位置，走「回地图」—— 地图页的主按钮本来就是「继续第 N 关」。
 */
export function entryLessonOfTrack(lessons: Lesson[], track: Track): Lesson | null {
  return lessons.find((l) => trackOf(l) === track) ?? null;
}

/**
 * 按内容 id 反查关卡（query 里没带 lesson 时用）。
 *
 * 诗/故事在各自线上都是「一关一条内容」，所以 `character_ids[0]` 就是内容 id，
 * 这个反查是确定的。
 */
export function lessonByContentId(lessons: Lesson[], contentId: string): Lesson | null {
  if (!contentId) return null;
  return lessons.find((l) => contentIdOf(l) === contentId) ?? null;
}

/**
 * 星星（0–3）。
 *
 * ⚠️ 与 `learning.completeLesson` 的默认口径一致：正确率 ≥0.9 → 3 星，
 * ≥0.7 → 2 星，≥0.5 → 1 星。视图有更具体的口径时（古诗/故事的完成方式
 * 不是答题正确率）自行传 `stars`，不要改这里的阈值 —— 改了会让三条线的
 * 星星不可比，家长看地图时「3 星」的含义就不唯一了。
 */
export function starsForAccuracy(accuracy: number): number {
  if (accuracy >= 0.9) return 3;
  if (accuracy >= 0.7) return 2;
  if (accuracy >= 0.5) return 1;
  return 0;
}
