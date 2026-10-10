<script setup lang="ts">
/**
 * MapView —— 学习地图（S-01）：**两层**结构。
 *
 *   第 1 层：三选一（识字 / 故事 / 古诗）—— 见 TrackPicker
 *   第 2 层：该类型的闯关链路图 —— 见 TrackCanvas
 *
 * ## 为什么改成两层
 * 之前把所有关卡按单元混成一条列表，两个问题：
 *   ① 孩子（尤其不识字的孩子）无法判断「该学识字还是该读故事」，
 *      等于让他自己做决策；
 *   ② 关卡一多就是一屏列表，**没有「旅程感」**，看不出走了多远。
 * 先选方向、再看路之后，每一屏的语义都单一且清楚。
 *
 * 关卡数据来自服务端自动生成（见 core 的 `algorithms/lessons.ts`），按 `track` 分线；
 * 解锁状态由本机学习流水（lesson_complete）推导。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRoute, useRouter } from 'vue-router';

import { useChildStore, useContentStore, useCore } from '@study-club/core';
import type { Lesson } from '@study-club/core';

import BaseButton from '@/components/base/BaseButton.vue';
import BaseEmpty from '@/components/base/BaseEmpty.vue';
import TrackCanvas from '@/components/biz/TrackCanvas.vue';
import TrackPicker from '@/components/biz/TrackPicker.vue';
import { useToast } from '@/composables/useToast';
import { gradeLabel } from '@/utils/format';
import { routeForLesson, trackOf } from '@/utils/levels';

const route = useRoute();
const router = useRouter();
const childStore = useChildStore();
const content = useContentStore();
const toast = useToast();

const { current } = storeToRefs(childStore);
/**
 * 已完成关卡 → **星星数**（0–3）。
 *
 * ⚠️ 为什么不是 Set：地图节点上要点亮星星，而星星是「上次做得怎么样」的记录，
 * 只记「做过没有」就没有星星可显示 —— 于是孩子看到的永远是空星或满星，
 * 「星星按情况点亮」这件事在地图上根本不存在。
 *
 * 同一关多次完成时取**最好成绩**（max）：星星是奖励，不该因为重练一次
 * 失手就把已经得到的星星收回去。
 */
const completed = ref<Map<string, number>>(new Map());
const loading = ref(false);

/** 当前选中的内容线；`null` = 停在首屏三选一。 */
const activeTrack = ref<'literacy' | 'poem' | 'story' | null>(
  (route.query.track as 'literacy' | 'poem' | 'story' | undefined) ?? null,
);

/** 已完成关卡的 id 集合（`trackCounts` / 解锁判定用）。 */
const completedIds = computed(() => new Set(completed.value.keys()));

const stats = computed(() =>
  current.value ? content.trackCounts(current.value.grade, completedIds.value) : {},
);

/** 当前线的关卡。 */
const lessons = computed<Lesson[]>(() => {
  const child = current.value;
  const track = activeTrack.value;
  if (!child || !track) return [];
  return content
    .lessonsOfTrack(child.grade, track)
    .filter((l) => trackOf(l) === track);
});

const TRACK_TITLE: Record<string, string> = {
  literacy: '识字',
  poem: '古诗',
  story: '故事',
};

const activeTitle = computed(() =>
  activeTrack.value ? (TRACK_TITLE[activeTrack.value] ?? '学习') : '',
);

/** 关卡显示名：优先运营 override 的标签名，其次内容原名。 */
function labelOf(lesson: Lesson): string {
  return lesson.tag_label?.trim() || lesson.title;
}

const progressPct = computed(() => {
  if (!lessons.value.length) return 0;
  const done = lessons.value.filter((l) => completedIds.value.has(l._id)).length;
  return Math.round((done / lessons.value.length) * 100);
});

/**
 * 关卡解锁：首关恒可玩；其后要求**同一线上的前一关**已完成。
 *
 * 判据是「顺序」而不是 `required_lesson_id` 字段：自动生成的关卡在服务端就算好了
 * 解锁链，但客户端用「前一关」直接判定口径更直观，也不会因为某次生成结果变化而失效。
 *
 * @param index 该关在当前线里的序号（第 N 关）。`lesson` 本身用不到 ——
 *   刻意**不接收**它：一旦开始用 `lesson.required_lesson_id`，就等于把这个判定
 *   与服务端生成规则耦合起来了。
 */
function isUnlocked(_lesson: Lesson, index: number): boolean {
  if (index === 0) return true;
  const prev = lessons.value[index - 1];
  return prev ? completedIds.value.has(prev._id) : true;
}

/**
 * 下一关（第一个未完成且已解锁的关卡）。
 *
 * 地图上的「继续」按钮用它 —— 孩子从任何入口回到地图时，都不该还要自己
 * 在赛道上找「我刚才学到哪了」。
 */
const nextTodo = computed<{ lesson: Lesson; index: number } | null>(() => {
  for (let i = 0; i < lessons.value.length; i += 1) {
    const lesson = lessons.value[i];
    if (lesson && !completedIds.value.has(lesson._id) && isUnlocked(lesson, i)) {
      return { lesson, index: i };
    }
  }
  return null;
});

async function loadProgress(): Promise<void> {
  if (!current.value) return;
  loading.value = true;
  try {
    const records = await useCore().repositories.progress.listLearningRecords(current.value._id, 500);
    const map = new Map<string, number>();
    for (const r of records) {
      if (r.event_type !== 'lesson_complete' || !r.lesson_id) continue;
      const stars = typeof r.stars === 'number' ? r.stars : 0;
      // 同一关多次完成取最好成绩
      map.set(r.lesson_id, Math.max(map.get(r.lesson_id) ?? 0, stars));
    }
    completed.value = map;
  } catch {
    toast.warn('学习进度读取失败');
  } finally {
    loading.value = false;
  }
}

function pickTrack(track: 'literacy' | 'poem' | 'story'): void {
  activeTrack.value = track;
  // 同步到 URL：刷新/返回时能停在同一层，也方便家长分享当前进度
  void router.replace({ name: 'map', query: { track } });
}

function backToPicker(): void {
  activeTrack.value = null;
  void router.replace({ name: 'map' });
}

/**
 * 进入关卡。
 *
 * ⛔ 不能一律跳 `lesson`：古诗关与故事关的 `character_ids` 装的是诗/故事 id，
 * 进识字页必然落到空状态 —— 这是「点了关卡进不去」的直接原因。
 * 真正该去哪一页由 `routeForLesson` 按 track 决定，三条线共用一份映射。
 */
function startLesson(lesson: Lesson): void {
  void router.push(routeForLesson(lesson));
}

onMounted(loadProgress);
watch(() => current.value?._id, loadProgress);
watch(
  () => route.query.track,
  (t) => {
    if (t === 'literacy' || t === 'poem' || t === 'story') activeTrack.value = t;
    else if (!route.query.track) activeTrack.value = null;
  },
);
</script>

<template>
  <section class="stack--lg stack">
    <BaseEmpty
      v-if="!current"
      title="还没有孩子档案"
      description="先建立档案，学习地图才会按年级展示内容。"
    >
      <BaseButton @click="router.push({ name: 'settings' })">去创建档案</BaseButton>
    </BaseEmpty>

    <template v-else>
      <header class="head">
        <!-- BaseButton 只支持 md / lg；「换一个」是次要操作，用默认的 md -->
        <BaseButton v-if="activeTrack" variant="ghost" @click="backToPicker">
          ‹ 换一个
        </BaseButton>
        <h2 class="title-lg">
          {{ activeTrack ? `${activeTitle}闯关` : `${gradeLabel(current.grade)}学习地图` }}
        </h2>
        <span v-if="activeTrack" class="head__progress">{{ progressPct }}%</span>
      </header>

      <!-- 第 1 层：三选一 -->
      <template v-if="!activeTrack">
        <TrackPicker :stats="stats" @pick="pickTrack" />
        <p class="hint">先选一个方向，再进去看闯关路线。</p>
      </template>

      <!-- 第 2 层：该类型的闯关链路图 -->
      <template v-else>
        <BaseEmpty
          v-if="!lessons.length"
          title="这一类还没有内容"
          :description="`内容包更新后，${activeTitle}关卡会自动出现在这里。`"
          icon="🗺️"
        >
          <BaseButton @click="backToPicker">返回</BaseButton>
        </BaseEmpty>

        <TrackCanvas
          v-else
          :lessons="lessons"
          :completed="completedIds"
          :stars="completed"
          :is-unlocked="isUnlocked"
          @select="startLesson"
        />

        <!-- 继续按钮：完成一关回来时，不必在赛道上自己找「学到哪了」 -->
        <BaseButton
          v-if="nextTodo"
          size="lg"
          block
          @click="startLesson(nextTodo.lesson)"
        >
          继续第 {{ nextTodo.index + 1 }} 关 · {{ labelOf(nextTodo.lesson) }}
        </BaseButton>

        <p v-if="lessons.length" class="hint">
          灰色的关卡要先完成前一关才能进。走过的路变绿，已完成的关卡下方是得到的星星。
        </p>
      </template>
    </template>
  </section>
</template>

<style scoped>
.head {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.head__progress {
  margin-left: auto;
  padding: 2px var(--space-sm);
  border-radius: var(--radius-pill);
  background: var(--color-surface-alt);
  color: var(--color-text-muted);
  font-size: var(--font-sm);
  font-weight: 600;
}

.hint {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--font-sm);
  text-align: center;
}
</style>
