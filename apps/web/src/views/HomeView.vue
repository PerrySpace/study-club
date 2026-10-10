<script setup lang="ts">
/**
 * HomeView —— 首页 / 学习地图入口（S-04 每日任务）。
 *
 * 今日任务 = 错题重练（优先）+ 到期复习 + 新学，由**服务端**生成并下发
 * （`GET /learning/state` 的 `daily_task`）。客户端只做两件事：
 * 展示，以及把「完成了哪些字」提交回去。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';

import { useChildStore, useContentStore, useLearningStore } from '@study-club/core';

import BaseButton from '@/components/base/BaseButton.vue';
import BaseCard from '@/components/base/BaseCard.vue';
import BaseEmpty from '@/components/base/BaseEmpty.vue';
import BaseProgress from '@/components/base/BaseProgress.vue';
import StatTile from '@/components/biz/StatTile.vue';
import { useToast } from '@/composables/useToast';
import { gradeLabel } from '@/utils/format';

const router = useRouter();
const childStore = useChildStore();
const content = useContentStore();
const learning = useLearningStore();
const toast = useToast();

const { current } = storeToRefs(childStore);
const { dailyTask } = storeToRefs(learning);

const loading = ref(false);

const counts = computed(() => ({
  newCount: dailyTask.value?.new_chars.length ?? 0,
  reviewCount: dailyTask.value?.review_chars.length ?? 0,
  wrongCount: dailyTask.value?.wrong_chars.length ?? 0,
}));

/**
 * 今日任务完成进度。
 *
 * 分子分母**都取服务端已算好的值**（`completed_count` / `total_count`），客户端不再自己数。
 * `total_count` 在服务端已按 `dict.fromkeys` 去重 —— 同一个字可能既在「到期复习」
 * 又在「错题重练」，客户端若把三类相加会把分母算大，进度条永远到不了 100%。
 * 早先这里就是自己在客户端 Set 去重，与出参字段名一起错位，导致整块卡片恒为 0。
 */
const taskProgress = computed(() => {
  const task = dailyTask.value;
  if (!task) return null;
  const total = task.total_count;
  const done = task.completed_count;
  return { done, total, ratio: total ? Math.min(1, done / total) : 0 };
});

const totalToday = computed(() => taskProgress.value?.total ?? 0);

const poemsForChild = computed(() =>
  current.value ? content.poemsOfGrade(current.value.grade).slice(0, 3) : [],
);

// 统计一律取服务端聚合值（`progress`），不再用本地数组长度代替 ——
// 数组可能因分页/上限被截断，用它当总数会悄悄偏小
const learnedCount = computed(() => learning.progress?.total_learned ?? 0);
const wrongCount = computed(() => learning.progress?.wrong_count ?? 0);

async function refresh(): Promise<void> {
  if (!current.value) return;
  loading.value = true;
  try {
    await learning.loadState(current.value._id);
  } catch {
    toast.warn('今日任务加载失败，请稍后重试');
  } finally {
    loading.value = false;
  }
}

onMounted(refresh);
watch(() => current.value?._id, refresh);

function startDaily(): void {
  void router.push({ name: 'lesson', params: { lessonId: 'daily' } });
}
</script>

<template>
  <section class="stack--lg stack">
    <BaseEmpty
      v-if="!current"
      title="还没有孩子档案"
      description="先建立一个档案，才能记录学习进度。"
    >
      <BaseButton @click="router.push({ name: 'settings' })">去创建档案</BaseButton>
    </BaseEmpty>

    <template v-else>
      <header class="hello">
        <p class="hello__hi">你好，{{ current.nickname }}！</p>
        <p class="hello__meta text-muted">
          {{ gradeLabel(current.grade) }} · 连续学习 {{ current.stats.streak_days }} 天
        </p>
      </header>

      <BaseCard title="今日任务" :subtitle="`共 ${totalToday} 个字`">
        <div class="stack">
          <BaseProgress
            v-if="taskProgress"
            :value="taskProgress?.ratio ?? 0"
            :label="`已完成 ${taskProgress?.done ?? 0} / ${taskProgress?.total ?? 0}`"
          />

          <div class="grid">
            <StatTile label="新学" :value="counts.newCount" tone="primary" hint="认识新字" />
            <StatTile label="到期复习" :value="counts.reviewCount" hint="按记忆曲线安排" />
            <StatTile
              label="错题重练"
              :value="counts.wrongCount"
              :tone="counts.wrongCount ? 'danger' : 'default'"
              hint="优先完成"
            />
          </div>

          <BaseButton size="lg" block :disabled="totalToday === 0" @click="startDaily">
            {{ totalToday === 0 ? '今天任务已完成 🎉' : '开始今日学习' }}
          </BaseButton>
        </div>
      </BaseCard>

      <div class="grid--2 grid">
        <BaseCard title="学习地图" subtitle="按单元逐关解锁">
          <p class="text-muted text-sm">看不清从哪开始？地图会告诉你下一关。</p>
          <template #footer>
            <BaseButton variant="secondary" block @click="router.push({ name: 'map' })">打开地图</BaseButton>
          </template>
        </BaseCard>

        <BaseCard title="古诗学习" :subtitle="`${gradeLabel(current.grade)}推荐`">
          <ul v-if="poemsForChild.length" class="poem-list">
            <li v-for="poem in poemsForChild" :key="poem._id">
              <button
                type="button"
                class="poem-list__item tap clickable"
                @click="router.push({ name: 'poem', params: { poemId: poem._id } })"
              >
                <span class="poem-list__title">{{ poem.title }}</span>
                <span class="text-sm text-muted">{{ poem.dynasty }} · {{ poem.author }}</span>
              </button>
            </li>
          </ul>
          <BaseEmpty v-else title="暂无古诗内容" description="内容包更新后会出现在这里。" icon="📖" />
        </BaseCard>
      </div>

      <BaseCard title="复习与错题" subtitle="记忆曲线 + 错题沉淀">
        <div class="grid grid--2">
          <StatTile label="已学字" :value="learnedCount" hint="含所有复习状态" />
          <StatTile label="待解决错题" :value="wrongCount" tone="danger" />
        </div>
        <template #footer>
          <div class="row row--wrap">
            <BaseButton variant="secondary" @click="router.push({ name: 'review' })">去复习</BaseButton>
            <BaseButton variant="secondary" @click="router.push({ name: 'wrong' })">看错题本</BaseButton>
          </div>
        </template>
      </BaseCard>
    </template>
  </section>
</template>

<style scoped>
.hello {
  display: flex;
  flex-direction: column;
  gap: var(--space-2xs);
}

.hello__hi {
  font-size: var(--font-xl);
  font-weight: 700;
}

.poem-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.poem-list__item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: 100%;
  padding: var(--space-sm);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
  text-align: left;
}

.poem-list__title {
  font-size: var(--font-lg);
  font-weight: 600;
}
</style>
