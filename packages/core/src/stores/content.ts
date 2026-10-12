/**
 * content store —— 内容包加载与查询。
 *
 * 内容真源现在是**服务端 MongoDB + 后台管理**：`content/*.json` 只在导入时读一次。
 * 客户端通过 `HttpSource`（`GET /content/bootstrap`）一次性拿到清单+字库+古诗+单元+关卡+故事+徽章，
 * 不再有「随包内容 / 远端静态覆盖」这两条旧路径，本 store 只认结构不认来源。
 *
 * 加载失败**不吞异常**（见 HttpSource 注释）：内容拉不到却渲染成空列表，
 * 家长会以为「字都没了」，比明确报错并给重试按钮糟得多。
 */

import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { EMPTY_BUNDLE } from '../types/content';
import type {
  Badge,
  Character,
  ContentBundle,
  CurriculumUnit,
  Lesson,
  Poem,
  Story,
} from '../types/content';
import { TRACKS } from '../algorithms/lessons';
import { useCore } from './context';

export const useContentStore = defineStore('content', () => {
  const bundle = ref<ContentBundle>(EMPTY_BUNDLE);
  const loaded = ref(false);
  const loading = ref(false);

  const characterMap = computed(() => {
    const m = new Map<string, Character>();
    for (const c of bundle.value.characters) m.set(c._id, c);
    return m;
  });

  const charByText = computed(() => {
    const m = new Map<string, Character>();
    for (const c of bundle.value.characters) m.set(c.char, c);
    return m;
  });

  const unitMap = computed(() => {
    const m = new Map<string, CurriculumUnit>();
    for (const u of bundle.value.units) m.set(u._id, u);
    return m;
  });

  async function load(force = false): Promise<void> {
    if (loaded.value && !force) return;
    loading.value = true;
    try {
      bundle.value = await useCore().contentSource.load();
      loaded.value = true;
    } finally {
      loading.value = false;
    }
  }

  function charactersByIds(ids: string[]): Character[] {
    return ids.map((id) => characterMap.value.get(id)).filter((c): c is Character => !!c);
  }

  function lessonsOfGrade(grade: number): Lesson[] {
    const unitIds = new Set(
      bundle.value.units.filter((u) => u.grade_num === grade).map((u) => u._id),
    );
    return bundle.value.lessons
      .filter((l) => (l.unit_id ? unitIds.has(l.unit_id) : true))
      .sort((a, b) => a.order - b.order);
  }

  /**
   * 按**内容线**取关卡（识字 / 故事 / 古诗）。
   *
   * 为什么要这个而不是复用 `lessonsOfGrade`：关卡现在是**自动生成**的，
   * `unit_id` 一律为 null（不再挂到「单元」上），所以按单元筛的那条路已经失效。
   * 客户端地图首屏是「三选一 → 该类型的关卡链路图」，正需要这条按线取的口径。
   *
   * `track` 缺失（老数据）时按 id 前缀兜底：生成器用 `{track}:{grade}:{序号}`，
   * 因此前缀判定对历史数据同样有效。
   */
  function lessonsOfTrack(grade: number, track: string): Lesson[] {
    return bundle.value.lessons
      .filter((l) => l.status === 'published')
      .filter((l) => (l.grade ?? 1) <= grade)
      .filter((l) => (l.track ?? String(l._id).split(':')[0]) === track)
      .sort((a, b) => (a.grade ?? 1) - (b.grade ?? 1) || a.order - b.order);
  }

  /**
   * 三条线各自的关卡数 —— 首屏三个知识块要显示「还有多少关」。
   *
   * @param grade 孩子年级（只统计该年级及以下的关卡）
   * @param completed 已完成的关卡 id 集合（由调用方从学习流水算来）
   */
  function trackCounts(
    grade: number,
    completed: ReadonlySet<string> = new Set(),
  ): Record<string, { total: number; done: number }> {
    const out: Record<string, { total: number; done: number }> = {};
    for (const track of TRACKS) {
      const list = lessonsOfTrack(grade, track);
      out[track] = { total: list.length, done: list.filter((l) => completed.has(l._id)).length };
    }
    return out;
  }

  function unitsOfGrade(grade: number): CurriculumUnit[] {
    return bundle.value.units
      .filter((u) => u.grade_num === grade)
      .sort((a, b) => a.order - b.order);
  }

  function candidateNewCharacterIds(grade: number): string[] {
    return bundle.value.characters
      .filter((c) => c.status === 'published' && c.grade <= grade)
      .sort((a, b) => a.difficulty - b.difficulty || a.stroke_count - b.stroke_count)
      .map((c) => c._id);
  }

  function poemsOfGrade(grade: number): Poem[] {
    return bundle.value.poems
      .filter((p) => p.status === 'published' && p.grade <= grade)
      .sort((a, b) => a.difficulty - b.difficulty);
  }

  function stories(): Story[] {
    return bundle.value.stories.filter((s) => s.status === 'published');
  }

  function badges(): Badge[] {
    return bundle.value.badges.filter((b) => b.status === 'active').sort((a, b) => a.order - b.order);
  }

  return {
    bundle,
    loaded,
    loading,
    characterMap,
    charByText,
    unitMap,
    load,
    charactersByIds,
    lessonsOfGrade,
    lessonsOfTrack,
    trackCounts,
    unitsOfGrade,
    candidateNewCharacterIds,
    poemsOfGrade,
    stories,
    badges,
  };
});
