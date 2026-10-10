<script setup lang="ts">
/**
 * ReportView —— 家长报告（S-13 / P-01）。
 *
 * ⚠️ 所有统计口径都来自**服务端**（`GET /learning/state` 的 progress + 报告接口的 trend）。
 * 旧版在这里用 `listAnswerRecords(500)` 把明细拉到本地再算正确率 —— 那既有采样上限
 * （超过 500 条就不准），又和服务端算的 `progress.accuracy` 不是同一套分母。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';

import { useChildStore, useContentStore, useCore, useLearningStore } from '@study-club/core';
import type { LearningOverview } from '@study-club/core';

import BaseButton from '@/components/base/BaseButton.vue';
import BaseCard from '@/components/base/BaseCard.vue';
import BaseEmpty from '@/components/base/BaseEmpty.vue';
import StatTile from '@/components/biz/StatTile.vue';
import TrendChart from '@/components/charts/TrendChart.vue';
import { useExportImport } from '@/composables/useExportImport';
import { gradeLabel, percent } from '@/utils/format';

interface ChildSummary {
  id: string;
  nickname: string;
  grade: number;
  learned: number;
  mastered: number;
  accuracy: number;
}

const router = useRouter();
const childStore = useChildStore();
const content = useContentStore();
const learning = useLearningStore();
const { exportChild } = useExportImport();

const { current, children } = storeToRefs(childStore);

const overview = ref<LearningOverview | null>(null);
const summaries = ref<ChildSummary[]>([]);
const loading = ref(false);

const weakChars = computed(() =>
  [...learning.wrongQuestions]
    .filter((w) => !w.resolved)
    .sort((a, b) => b.wrong_count - a.wrong_count)
    .slice(0, 8)
    .map((w) => ({
      ...w,
      pinyin: content.charByText.get(w.char)?.pinyin ?? '',
      meaning: content.charByText.get(w.char)?.meaning ?? '',
    })),
);

async function loadSummary(childId: string, nickname: string, grade: number): Promise<ChildSummary> {
  // 每个孩子一次 `/learning/state`（不带每日任务）即可拿到三个聚合值，
  // 不必再把答题明细拉到本地自己算 —— 那样既慢又会和服务端口径不一致。
  const state = await useCore().repositories.progress.getState(childId);
  return {
    id: childId,
    nickname,
    grade,
    learned: state.progress.total_learned,
    mastered: state.progress.mastered,
    accuracy: state.progress.accuracy,
  };
}

async function load(): Promise<void> {
  const child = current.value;
  if (!child) {
    overview.value = null;
    summaries.value = [];
    return;
  }
  loading.value = true;
  try {
    await learning.loadChildData(child._id);
    overview.value = await learning.overview(child._id);
    summaries.value = await Promise.all(
      children.value.map((c) => loadSummary(c._id, c.nickname, c.grade)),
    );
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(() => current.value?._id, load);

function doExport(): void {
  if (current.value) void exportChild(current.value._id);
}
</script>

<template>
  <section class="stack--lg stack selectable">
    <BaseEmpty v-if="!current" title="还没有孩子档案" description="建立档案后才能生成报告。">
      <BaseButton @click="router.push({ name: 'settings' })">去创建档案</BaseButton>
    </BaseEmpty>

    <template v-else>
      <header class="report-head">
        <div>
          <h2 class="title-lg">{{ current.nickname }} 的学习报告</h2>
          <p class="text-muted text-sm">{{ gradeLabel(current.grade) }} · 数据来自服务端记录</p>
        </div>
        <BaseButton variant="secondary" @click="doExport">导出进度</BaseButton>
      </header>

      <BaseEmpty
        v-if="overview && overview.total_learned === 0"
        title="还没有学习记录"
        description="完成一次学习后，这里会出现掌握率与趋势。"
        icon="📊"
      />

      <template v-if="overview && overview.total_learned > 0">
        <BaseCard title="掌握情况">
          <div class="grid">
            <StatTile label="已学字" :value="overview.total_learned" tone="primary" />
            <StatTile label="已掌握" :value="overview.mastered" tone="success" hint="间隔 > 60 天" />
            <StatTile label="正确率" :value="percent(overview.accuracy)" />
          </div>
        </BaseCard>

        <div class="grid grid--2">
          <BaseCard title="近 7 天趋势">
            <TrendChart :points="overview.trend" />
          </BaseCard>

          <BaseCard title="复习与错题">
            <div class="grid grid--2">
              <StatTile label="复习中" :value="overview.reviewing" />
              <StatTile label="学习中" :value="overview.learning" />
              <StatTile label="今日到期" :value="overview.due_count" tone="primary" />
              <StatTile label="待解决错题" :value="overview.wrong_count" tone="danger" />
            </div>
            <p class="text-sm text-muted report-note">连续学习 {{ overview.streak_days }} 天</p>
          </BaseCard>
        </div>

        <BaseCard title="薄弱字" subtitle="按错误次数排序，建议优先复习">
          <BaseEmpty v-if="!weakChars.length" title="暂无明显薄弱字" description="保持得不错！" icon="💪" />
          <ul v-else class="weak-list">
            <li v-for="row in weakChars" :key="row._id" class="weak-item">
              <span class="weak-item__char">{{ row.char }}</span>
              <span class="weak-item__main">
                <span class="weak-item__pinyin">{{ row.pinyin }}</span>
                <span class="text-sm text-muted">{{ row.meaning }}</span>
              </span>
              <span class="text-sm text-muted">错 {{ row.wrong_count }} 次</span>
            </li>
          </ul>
        </BaseCard>

        <BaseCard v-if="summaries.length > 1" title="多孩子对比" subtitle="账号下档案对比（P-03）">
          <ul class="compare-list">
            <li v-for="item in summaries" :key="item.id" class="compare-item">
              <span class="compare-item__name">{{ item.nickname }}</span>
              <span class="text-sm text-muted">{{ gradeLabel(item.grade) }}</span>
              <span class="compare-item__stat">已学 {{ item.learned }}</span>
              <span class="compare-item__stat">掌握 {{ item.mastered }}</span>
              <span class="compare-item__stat">正确率 {{ percent(item.accuracy) }}</span>
            </li>
          </ul>
        </BaseCard>
      </template>
    </template>
  </section>
</template>

<style scoped>
.report-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-md);
  flex-wrap: wrap;
}

.report-note {
  margin-top: var(--space-sm);
}

.weak-list,
.compare-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.weak-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-sm);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
}

.weak-item__char {
  font-size: var(--font-xl);
  font-weight: 600;
}

.weak-item__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.weak-item__pinyin {
  color: var(--color-info);
}

.compare-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-wrap: wrap;
  padding: var(--space-sm);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
}

.compare-item__name {
  font-weight: 600;
}

.compare-item__stat {
  font-size: var(--font-sm);
}
</style>
