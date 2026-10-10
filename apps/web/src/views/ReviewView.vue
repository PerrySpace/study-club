<script setup lang="ts">
/**
 * ReviewView —— 到期复习（S-05 间隔重复）。
 * 只负责「哪些字到期」与入口；真正的复习会话复用 LessonView（/lesson/due）。
 *
 * ⚠️ 「哪些字算到期」由**服务端**判定（`state.due_reviews` / `progress.due_count`）。
 * 旧版在客户端用 `isDue()` 自己比时间，与服务端的判定必然会有微妙差异
 * （时区、下次复习时间的取整、服务端补算），家长会在两个页面上看到不同的数字。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';

import { useChildStore, useContentStore, useLearningStore } from '@study-club/core';

import BaseButton from '@/components/base/BaseButton.vue';
import BaseCard from '@/components/base/BaseCard.vue';
import BaseEmpty from '@/components/base/BaseEmpty.vue';
import SpeakButton from '@/components/biz/SpeakButton.vue';
import StatTile from '@/components/biz/StatTile.vue';
import { formatDate } from '@/utils/format';

const router = useRouter();
const childStore = useChildStore();
const content = useContentStore();
const learning = useLearningStore();

const { current } = storeToRefs(childStore);
const loading = ref(false);

/** 服务端给的到期清单（已按紧急度排好序，客户端不再重排）。 */
const dueReviews = computed(() => learning.state?.due_reviews ?? []);

const stats = computed(() => {
  const p = learning.progress;
  return {
    due: p?.due_count ?? dueReviews.value.length,
    mastered: p?.mastered ?? 0,
    reviewing: p?.reviewing ?? 0,
    learning: p?.learning ?? 0,
  };
});

const rows = computed(() =>
  dueReviews.value.slice(0, 40).map((due) => {
    const char = content.characterMap.get(due.character_id);
    return {
      id: due.character_id,
      char: char?.char ?? due.char ?? '？',
      pinyin: char?.pinyin ?? '',
      meaning: char?.meaning ?? '',
      interval: due.interval_days,
      nextAt: due.next_review_at,
    };
  }),
);

async function load(): Promise<void> {
  if (!current.value) return;
  loading.value = true;
  try {
    await learning.loadState(current.value._id, false);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(() => current.value?._id, load);

function start(): void {
  void router.push({ name: 'lesson', params: { lessonId: 'due' } });
}
</script>

<template>
  <section class="stack--lg stack">
    <BaseEmpty
      v-if="!current"
      title="还没有孩子档案"
      description="建立档案后才能安排复习计划。"
    >
      <BaseButton @click="router.push({ name: 'settings' })">去创建档案</BaseButton>
    </BaseEmpty>

    <template v-else>
      <BaseCard title="复习概况" subtitle="间隔重复由服务端按记忆曲线安排">
        <div class="grid">
          <StatTile label="今日到期" :value="stats.due" tone="primary" hint="优先复习" />
          <StatTile label="复习中" :value="stats.reviewing" />
          <StatTile label="已掌握" :value="stats.mastered" tone="success" hint="间隔超过 60 天" />
        </div>
        <template #footer>
          <BaseButton size="lg" block :disabled="stats.due === 0" @click="start">
            {{ stats.due === 0 ? '今天没有到期复习 🎉' : `开始复习（${stats.due} 个字）` }}
          </BaseButton>
        </template>
      </BaseCard>

      <BaseCard title="到期的字" :subtitle="`共 ${stats.due} 个`">
        <BaseEmpty v-if="!rows.length" title="暂无到期字" description="学过的字会在合适的时间自动出现。" icon="✅" />
        <ul v-else class="review-list">
          <li v-for="row in rows" :key="row.id" class="review-item">
            <span class="review-item__char">{{ row.char }}</span>
            <span class="review-item__main">
              <span class="review-item__pinyin">{{ row.pinyin }}</span>
              <span class="text-sm text-muted">{{ row.meaning }}</span>
            </span>
            <SpeakButton :text="row.char" :rate="0.7" label="听" size="sm" variant="ghost" />
            <span class="review-item__meta text-sm text-muted">
              间隔 {{ row.interval }} 天 · {{ formatDate(row.nextAt) }}
            </span>
          </li>
        </ul>
      </BaseCard>
    </template>
  </section>
</template>

<style scoped>
.review-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.review-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-sm);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
}

.review-item__char {
  font-size: var(--font-xl);
  font-weight: 600;
}

.review-item__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.review-item__pinyin {
  color: var(--color-info);
}

.review-item__meta {
  margin-left: auto;
  text-align: right;
}
</style>
